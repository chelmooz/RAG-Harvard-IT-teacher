"""
RAG Engine v6.0 — AMD BC-250 (Cyan Skillfish / RDNA2)
=======================================================
CORRECTIFS v6.0 appliqués :
  - FIX BUG#2 : f-string SQL supprimé → deux requêtes paramétrées distinctes
  - FIX BUG#3 : pool asyncpg unique — réutilise get_db() de database.py
  - FIX BUG#4 : ON CONFLICT protégé par UNIQUE(file_id, chunk_index) dans database.py
  - FIX W4   : half() avant torch.compile() (ordre corrigé)
  - FIX W10  : schéma rag_chunks supprimé ici — database.py est la seule source de vérité

ARCHITECTURE v6.1 (DIP + SRP) :
  - EmbeddingProvider injecté (Protocol) — pas de SentenceTransformer direct
  - LLMClient injecté (Protocol) — pas de httpx direct
  - Pool DB partagé via database.get_db()
  - Responsabilités séparées (PR P1) :
      * Retriever  → recherche vectorielle (HNSW pgvector)
      * Indexer    → indexation + stats + maintenance de la collection
      * Generator  → génération LLM (Ollama) + construction des prompts
  - RAGEngine = facade / composition root qui orchestre les trois.
"""

import asyncio
import os
from typing import Any

import asyncpg
import numpy as np
from loguru import logger

# ── ROCm / PyTorch ─────────────────────────────────────────────────────────────
# HSA_OVERRIDE_GFX_VERSION=10.1.3 DOIT être défini AVANT d'importer torch.
# Sans cette variable, ROCm ne reconnaît pas le BC-250 (gfx1013 absent de la
# liste officielle) et tombe silencieusement en mode CPU.
os.environ.setdefault("HSA_OVERRIDE_GFX_VERSION", "10.1.3")
os.environ.setdefault("PYTORCH_HIP_ALLOC_CONF", "max_split_size_mb:512")

import torch
from sentence_transformers import SentenceTransformer

from .config import get_settings
from .protocols import EmbeddingProvider, LLMClient

_settings = get_settings()


# ── Détection GPU AMD ──────────────────────────────────────────────────────────

def _get_device() -> torch.device:
    """
    CRITIQUE BC-250 : La GDDR6 est unifiée entre CPU et GPU.
    On force le device 'cuda' (alias ROCm sous PyTorch) pour que les
    tenseurs vivent déjà sur la mémoire GPU — pas de copie DMA.
    """
    if torch.cuda.is_available():  # ROCm expose l'API CUDA
        dev = torch.device("cuda:0")
        props = torch.cuda.get_device_properties(0)
        logger.info(
            f"🟢 GPU AMD détecté : {props.name} | "
            f"{props.total_memory // 1024**2} Mo GDDR6 unifiée | "
            f"{_settings.AMD_RDNA2_CUS} CUs configurés "
            f"({'débloqué 40 CU' if _settings.AMD_CU_UNLOCK_APPLIED else 'stock 24 CU'})"
        )
        return dev
    logger.warning("⚠️  Pas de GPU ROCm détecté — exécution CPU (performances dégradées)")
    return torch.device("cpu")


DEVICE = _get_device()


# ── LocalEmbeddingProvider (implémentation concrète du Protocol) ───────────────

class LocalEmbeddingProvider:
    """
    Implémentation locale de EmbeddingProvider utilisant SentenceTransformer.
    Remplace l'ancien EmbeddingEngine interne.
    """

    # Calibré pour 24 CUs RDNA2 (64) ; mis à l'échelle si 40 CU débloqués.
    # EMBEDDING_BATCH_SIZE (.env) reste la valeur d'autorité si définie.
    BATCH_SIZE = max(
        64,
        round(64 * _settings.AMD_RDNA2_CUS / 24)
    ) if not os.environ.get("EMBEDDING_BATCH_SIZE") else int(os.environ["EMBEDDING_BATCH_SIZE"])
    MODEL_NAME = "BAAI/bge-m3"  # 1024 dims — remplace paraphrase-multilingual-mpnet (768d, obsolète)

    def __init__(self, model_name: str = MODEL_NAME):
        logger.info(f"📦 Chargement modèle d'embeddings → {model_name}")
        self.model = SentenceTransformer(model_name, device=str(DEVICE))

        if DEVICE.type != "cpu":
            # FIX W4 : half() EN PREMIER — le modèle est fp16 avant la compilation
            self.model = self.model.half()
            logger.info("🔢 Modèle converti en fp16 (−50 % VRAM GDDR6)")

            # torch.compile : fusionne les kernels RDNA2, réduit l'overhead Python
            # Appliqué APRÈS half() pour que le graphe compilé soit fp16
            try:
                logger.info("⚡ Compilation torch.compile (mode=reduce-overhead)...")
                self.model = torch.compile(self.model, mode="reduce-overhead")
                logger.info("✅ torch.compile réussi")
            except Exception as e:
                logger.warning(f"⚠️  torch.compile échoué : {e} — mode standard")

        logger.info("✅ LocalEmbeddingProvider prêt")

    def encode(self, texts: list[str]) -> np.ndarray:
        """
        Encode une liste de textes en vecteurs normalisés.

        convert_to_numpy=False : le tenseur reste sur la GDDR6 unifiée.
        .cpu().float().numpy() : unique transfert GPU→CPU pour asyncpg.
        """
        with torch.inference_mode():  # Plus rapide que no_grad() sous Python 3.13
            vecs = self.model.encode(
                texts,
                batch_size=self.BATCH_SIZE,
                normalize_embeddings=True,   # → produit scalaire = cosine
                convert_to_numpy=False,      # Reste sur GPU RDNA2
                show_progress_bar=False,
            )
        return vecs.cpu().float().numpy()    # Unique transfert GPU→CPU

    def encode_single(self, text: str) -> np.ndarray:
        return self.encode([text])[0]


# ── Retriever (responsabilité unique : recherche vectorielle) ──────────────────

class Retriever:
    """
    Recherche les chunks les plus proches via pgvector HNSW.

    DIP : EmbeddingProvider injecté (pas d'instance interne SentenceTransformer).
    Le pool est partagé via attach_pool() (initialisé par database.get_db()).
    """

    def __init__(self, embedding_provider: EmbeddingProvider):
        self.embedding_provider = embedding_provider
        self._pool: asyncpg.Pool | None = None

    def attach_pool(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @staticmethod
    def _build_retrieve_sql(
        query_vec, top_k: int, threshold: float, metier_filter: str | None
    ) -> tuple[str, list]:
        vec = query_vec.tolist()
        limit = top_k * 2
        if metier_filter:
            sql = """
                WITH ranked AS (
                    SELECT content, metadata, file_id, filename,
                           1 - (embedding <=> $1::vector) AS score
                    FROM rag_chunks
                    WHERE metadata->>'metier' = $4
                    ORDER BY embedding <=> $1::vector
                    LIMIT $2
                )
                SELECT content, metadata, file_id, filename, score FROM ranked WHERE score >= $3 ORDER BY score DESC;
            """
            return sql, [vec, limit, threshold, metier_filter]
        sql = """
            WITH ranked AS (
                SELECT content, metadata, file_id, filename,
                       1 - (embedding <=> $1::vector) AS score
                FROM rag_chunks
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            )
            SELECT content, metadata, file_id, filename, score FROM ranked WHERE score >= $3 ORDER BY score DESC;
        """
        return sql, [vec, limit, threshold]

    async def _search(
        self, query_vec, top_k: int, threshold: float, metier_filter: str | None
    ) -> list[dict[str, Any]]:
        sql, params = self._build_retrieve_sql(query_vec, top_k, threshold, metier_filter)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        results = []
        for i, row in enumerate(rows[:top_k]):
            results.append({
                "text":     row["content"],
                "metadata": dict(row["metadata"]),
                "score":    float(row["score"]),
                "rank":     i + 1,
            })
        return results

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.72,   # Aligné sur config.py RAG_THRESHOLD
        metier_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Recherche les chunks les plus proches via pgvector HNSW.

        FIX BUG#2 : ZÉRO f-string dans le SQL.
        Deux requêtes paramétrées distinctes selon la présence du filtre métier.
        Tous les paramètres sont liés via asyncpg ($1, $2, $3, $4) → pas d'injection.

        OPTIMISATION BC-250 :
        - encode_single via provider injecté (asyncio.to_thread pour ne pas bloquer asyncio).
        - vecteur numpy passé directement à asyncpg (pas de sérialisation JSON).
        - WHERE métier en SQL natif AVANT le tri vectoriel → moins de chunks à trier.
        - LIMIT top_k*2 puis slicing Python : over-fetch améliore le recall HNSW.
        """
        query_vec = await asyncio.to_thread(
            self.embedding_provider.encode_single, query
        )
        results = await self._search(query_vec, top_k, threshold, metier_filter)
        logger.info(
            f"📚 {len(results)}/{top_k} chunks ≥ seuil {threshold} "
            f"(métier: {metier_filter or 'tous'})"
        )
        return results

    async def check_db_health(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.fetchval("SELECT 1;")


# ── Indexer (responsabilité unique : indexation + stats + maintenance) ─────────

class Indexer:
    """
    Indexe les chunks et gère la collection pgvector (stats + reset).

    DIP : EmbeddingProvider injecté (pas d'instance interne SentenceTransformer).
    Le pool est partagé via attach_pool() (initialisé par database.get_db()).
    """

    def __init__(self, embedding_provider: EmbeddingProvider):
        self.embedding_provider = embedding_provider
        self._pool: asyncpg.Pool | None = None

    def attach_pool(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @staticmethod
    def _validate_embeddings(
        embeddings: np.ndarray, filename: str
    ) -> None:
        if not np.isfinite(embeddings).all():
            nan_chunks = int(np.sum(~np.isfinite(embeddings).any(axis=1)))
            logger.error(
                f"❌ {nan_chunks} vecteurs NaN détectés dans « {filename} » "
                f"— probable OOM GPU partiel — indexation annulée"
            )
            raise RuntimeError(
                f"{nan_chunks} embeddings NaN dans {filename} — vérifiez la VRAM disponible"
            )

    @staticmethod
    def _build_index_records(
        chunks: list[dict[str, Any]],
        embeddings: np.ndarray,
        file_id: str,
        filename: str,
    ) -> list[tuple]:
        records = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings, strict=True)):
            meta = {
                "source": filename,
                "chunking_method": chunk.get("metadata", {}).get(
                    "chunking_method", "unknown"
                ),
                **chunk.get("metadata", {}),
            }
            records.append((
                file_id,
                filename,
                i,
                chunk["text"],
                meta,
                emb.tolist(),
            ))
        return records

    async def index_chunks(
        self,
        chunks: list[dict[str, Any]],
        file_id: str,
        filename: str,
    ):
        """
        Indexe des chunks avec embeddings batch GPU + INSERT bulk asyncpg.

        OPTIMISATION BC-250 :
        - Un seul appel GPU pour TOUS les textes du fichier (vectorisation totale).
        - executemany() envoie toutes les lignes en une transaction.
        - ON CONFLICT DO NOTHING protégé par UNIQUE(file_id, chunk_index) dans DB
          (FIX BUG#4) → réindexer un fichier ne crée pas de doublons.
        """
        if not chunks:
            logger.warning("⚠️  Aucun chunk à indexer")
            return

        texts = [c["text"] for c in chunks]
        logger.info(f"🔢 Encodage batch : {len(texts)} chunks pour « {filename} »...")

        embeddings = await asyncio.to_thread(
            self.embedding_provider.encode, texts
        )

        self._validate_embeddings(embeddings, filename)

        records = self._build_index_records(chunks, embeddings, file_id, filename)

        async with self._pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO rag_chunks
                    (file_id, filename, chunk_index, content, metadata, embedding)
                VALUES ($1, $2, $3, $4, $5, $6::vector)
                ON CONFLICT ON CONSTRAINT rag_chunks_file_chunk_unique DO NOTHING;
                """,
                records,
            )

        logger.info(f"✅ {len(records)} chunks indexés pour « {filename} »")

    async def get_collection_stats(self) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM rag_chunks;")
            files = await conn.fetchval(
                "SELECT COUNT(DISTINCT file_id) FROM rag_chunks;"
            )
        return {
            "total_chunks":    total,
            "total_documents": files,
            "collection_name": "rag_chunks (pgvector HNSW)",
            "backend":         "PostgreSQL + pgvector v6.1",
        }

    async def reset_collection(self):
        """Vide la table rag_chunks et réinitialise les séquences."""
        async with self._pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM rag_chunks;")
            logger.warning(
                f"⚠️  RESET COLLECTION : {count} chunks vont être supprimés — irréversible"
            )
            await conn.execute("TRUNCATE TABLE rag_chunks RESTART IDENTITY;")
            logger.warning("✅ Collection réinitialisée (TRUNCATE + RESTART IDENTITY)")

    async def check_db_health(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.fetchval("SELECT 1;")


# ── Generator (responsabilité unique : génération LLM + prompts) ────────────────

class Generator:
    """
    Génère la réponse finale via le LLM injecté (Ollama).

    DIP : LLMClient injecté (pas de httpx direct).
    Construit les prompts système / complet (logique pure, testable).
    """

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    @staticmethod
    def _build_system_prompt(system_prompt: str) -> str:
        if system_prompt:
            return system_prompt
        return (
            "Tu es un assistant pédagogique spécialisé en cybersécurité et "
            "administration réseau (TSSR, AIS, DevOps). "
            "Réponds en français de manière structurée et pédagogique. "
            "Cite toujours tes sources entre parenthèses, exemple : (Source : nom_du_document). "
            "Utilise les sources fournies dans le contexte pour justifier tes réponses. "
            "Si l'information est absente du contexte, réponds : "
            "« Je ne trouve pas cette information dans les documents disponibles. »"
        )

    @staticmethod
    def _build_full_prompt(query: str, context: str | None = None) -> str:
        if context:
            return (
                f"Contexte (sources documentaires) :\n{context}\n\n"
                f"Question : {query}"
            )
        return (
            f"Question : {query}\n\n"
            "Aucun document pertinent trouvé dans la base. "
            "Si tu ne peux pas répondre avec les documents disponibles, "
            "dis-le clairement sans inventer d'information."
        )

    async def generate(
        self,
        query: str,
        context: str | None = None,
        system_prompt: str = "",
    ) -> str:
        safe_system = self._build_system_prompt(system_prompt)
        full_prompt = self._build_full_prompt(query, context)
        return await self.llm_client.generate(full_prompt, safe_system)


# ── RAGEngine (facade / composition root) ──────────────────────────────────────

class RAGEngine:
    """
    Orchestrateur RAG v6.1 — PostgreSQL + pgvector HNSW.

    DIP appliqué :
    - EmbeddingProvider injecté (pas d'instance interne)
    - LLMClient injecté (pas de httpx direct)
    - Pool DB partagé via database.get_db()

    SRP (PR P1) : les responsabilités sont déléguées à Retriever / Indexer /
    Generator. RAGEngine reste la facade utilisée par l'API (endpoints /chat,
    /documents, /indexing…) et par PGVectorStore.
    """

    def __init__(
        self,
        db_url: str,
        embedding_provider: EmbeddingProvider,
        llm_client: LLMClient,
        ollama_host: str = None,
        model_name: str = "qwen3:14b",
    ):
        self.db_url = db_url
        self.ollama_host = ollama_host or get_settings().OLLAMA_HOST
        self.model_name = model_name

        # Dépendances injectées
        self.embedding_provider = embedding_provider
        self.llm_client = llm_client

        # Composants (SRP) — chaque responsabilité est isolée et testable
        self._retriever = Retriever(embedding_provider)
        self._indexer = Indexer(embedding_provider)
        self._generator = Generator(llm_client)

        # Pool partagé (initialisé dans initialize())
        self._pool: asyncpg.Pool | None = None

    # ── Initialisation ─────────────────────────────────────────────────────────

    async def initialize(self):
        """
        Récupère le pool partagé de database.py et vérifie Ollama via client injecté.
        """
        logger.info("🔧 Initialisation RAG Engine v6.1...")

        # Réutiliser le pool global — init_db() a déjà créé les tables
        from .database import get_db
        self._pool = await get_db()
        self._retriever.attach_pool(self._pool)
        self._indexer.attach_pool(self._pool)

        logger.info("✅ Pool pgvector partagé (database.py)")

        try:
            await self.check_ollama_health()
            logger.info(f"✅ Ollama opérationnel — modèle : {self.model_name}")
        except Exception as e:
            logger.warning(f"⚠️  Ollama non disponible au démarrage : {e}")

    # ── Délégation Retriever ──────────────────────────────────────────────────

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.72,
        metier_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self._retriever.retrieve(query, top_k, threshold, metier_filter)

    # ── Délégation Indexer ────────────────────────────────────────────────────

    async def index_chunks(
        self,
        chunks: list[dict[str, Any]],
        file_id: str,
        filename: str,
    ):
        return await self._indexer.index_chunks(chunks, file_id, filename)

    async def get_collection_stats(self) -> dict[str, Any]:
        return await self._indexer.get_collection_stats()

    async def reset_collection(self):
        return await self._indexer.reset_collection()

    # ── Délégation Generator ──────────────────────────────────────────────────

    async def generate(
        self,
        query: str,
        context: str | None = None,
        system_prompt: str = "",
    ) -> str:
        return await self._generator.generate(query, context, system_prompt)

    # ── Health checks ──────────────────────────────────────────────────────────

    async def check_ollama_health(self):
        return await self.llm_client.check_health()

    async def check_db_health(self):
        await self._retriever.check_db_health()

    # ── Fermeture ─────────────────────────────────────────────────────────────

    async def close(self):
        """
        Ferme le client HTTP Ollama via le client injecté.
        NE ferme PAS self._pool — c'est le pool partagé de database.py,
        fermé par close_db() au shutdown de l'application FastAPI.
        """
        if hasattr(self.llm_client, 'close'):
            await self.llm_client.close()
        logger.info("✅ RAG Engine v6.1 fermé (pool DB géré par database.py)")
