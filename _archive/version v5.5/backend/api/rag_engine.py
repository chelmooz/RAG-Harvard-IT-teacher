"""
RAG Engine v5.4 — AMD BC-250 (Cyan Skillfish / RDNA2)
=======================================================
CORRECTIFS v5.4 appliqués :
  - FIX BUG#2 : f-string SQL supprimé → deux requêtes paramétrées distinctes
  - FIX BUG#3 : pool asyncpg unique — réutilise get_db() de database.py
  - FIX BUG#4 : ON CONFLICT protégé par UNIQUE(file_id, chunk_index) dans database.py
  - FIX W4   : half() avant torch.compile() (ordre corrigé)
  - FIX W10  : schéma rag_chunks supprimé ici — database.py est la seule source de vérité

OPTIMISATIONS BC-250 CONSERVÉES :
  - Mémoire GDDR6 unifiée : zéro copie CPU↔GPU via tenseurs partagés
  - 24 CUs RDNA2 : batch d'embeddings vectorisé sur ROCm 7.2
  - asyncpg + pgvector HNSW (PostgreSQL) en remplacement de ChromaDB
  - Python 3.13 : asyncio.to_thread pour les appels GPU bloquants
"""

import asyncio
import os
from typing import List, Dict, Any, Optional

import httpx
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
            f"{props.total_memory // 1024**2} Mo GDDR6 unifiée"
        )
        return dev
    logger.warning("⚠️  Pas de GPU ROCm détecté — exécution CPU (performances dégradées)")
    return torch.device("cpu")


DEVICE = _get_device()


# ── EmbeddingEngine ────────────────────────────────────────────────────────────

class EmbeddingEngine:
    """
    Moteur d'embeddings vectorisé pour les 24 CUs RDNA2.

    Design :
    - SentenceTransformer en batch de BATCH_SIZE=64 → utilisation maximale des CUs.
    - fp16 : divise la VRAM par 2, suffisant pour la similarité cosine.
    - normalize_embeddings=True : produit scalaire = similarité cosine (2× plus rapide).

    FIX W4 : .half() appliqué AVANT torch.compile().
    Inverser l'ordre invalide la compilation triton (le graphe compilé devient fp32).
    """

    BATCH_SIZE = 64      # Calibré pour 24 CUs RDNA2
    MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

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

        logger.info("✅ EmbeddingEngine prêt")

    def encode(self, texts: List[str]) -> np.ndarray:
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


# ── RAGEngine ──────────────────────────────────────────────────────────────────

class RAGEngine:
    """
    Moteur RAG v5.4 — PostgreSQL + pgvector HNSW.

    FIX BUG#3 : RAGEngine réutilise le pool asyncpg de database.py via get_db().
    Plus de double create_pool() → économie de ~80 Mo de connexions sur la GDDR6.

    FIX W10 : le schéma (CREATE TABLE, CREATE INDEX) est uniquement dans database.py.
    RAGEngine ne crée plus rien au démarrage — database.py est la seule source de vérité.
    """

    def __init__(
        self,
        db_url: str,
        ollama_host: str = "http://localhost:11434",
        model_name: str = "mistral:7b-instruct",
        embedding_model: str = EmbeddingEngine.MODEL_NAME,
    ):
        self.db_url = db_url
        self.ollama_host = ollama_host
        self.model_name = model_name

        # FIX BUG#3 : _pool assigné depuis get_db() dans initialize(),
        # pas via create_pool() → un seul pool pour toute l'application
        self._pool: Optional[asyncpg.Pool] = None
        self.embedding_engine = EmbeddingEngine(embedding_model)

        # Timeout généreux pour Ollama sur BC-250 (CPU+GPU GDDR6 partagé)
        self.http_client = httpx.AsyncClient(timeout=180.0)

    # ── Initialisation ─────────────────────────────────────────────────────────

    async def initialize(self):
        """
        Récupère le pool partagé de database.py et vérifie Ollama.

        FIX BUG#3 + FIX W10 :
        - Pas de create_pool() ici → on réutilise le pool global init_db().
        - Pas de CREATE TABLE/INDEX ici → géré exclusivement par database.init_db().
        Cette séparation des responsabilités garantit un schéma cohérent
        et évite deux définitions divergentes de rag_chunks.
        """
        logger.info("🔧 Initialisation RAG Engine v5.4...")

        # Réutiliser le pool global — init_db() a déjà créé les tables
        from .database import get_db
        self._pool = await get_db()

        logger.info("✅ Pool pgvector partagé (database.py)")

        try:
            await self.check_ollama_health()
            logger.info(f"✅ Ollama opérationnel — modèle : {self.model_name}")
        except Exception as e:
            logger.warning(f"⚠️  Ollama non disponible au démarrage : {e}")

    # ── Retrieval ──────────────────────────────────────────────────────────────

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.72,   # Aligné sur config.py RAG_THRESHOLD
        metier_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Recherche les chunks les plus proches via pgvector HNSW.

        FIX BUG#2 : ZÉRO f-string dans le SQL.
        Deux requêtes paramétrées distinctes selon la présence du filtre métier.
        Tous les paramètres sont liés via asyncpg ($1, $2, $3, $4) → pas d'injection.

        OPTIMISATION BC-250 :
        - encode_single sur GPU RDNA2 (asyncio.to_thread pour ne pas bloquer asyncio).
        - vecteur numpy passé directement à asyncpg (pas de sérialisation JSON).
        - WHERE métier en SQL natif AVANT le tri vectoriel → moins de chunks à trier.
        - LIMIT top_k*2 puis slicing Python : over-fetch améliore le recall HNSW.
        """
        query_vec = await asyncio.to_thread(
            self.embedding_engine.encode_single, query
        )

        if metier_filter:
            # Requête avec filtre métier — $4 lié par asyncpg, zéro interpolation
            sql = """
                WITH ranked AS (
                    SELECT content, metadata, file_id, filename,
                           1 - (embedding <=> $1::vector) AS score
                    FROM rag_chunks
                    WHERE metadata->>'metier' = $4
                    ORDER BY embedding <=> $1::vector
                    LIMIT $2
                )
                SELECT * FROM ranked WHERE score >= $3 ORDER BY score DESC;
            """
            params: list = [query_vec.tolist(), top_k * 2, threshold, metier_filter]
        else:
            # Requête sans filtre — strictement paramétrée
            sql = """
                WITH ranked AS (
                    SELECT content, metadata, file_id, filename,
                           1 - (embedding <=> $1::vector) AS score
                    FROM rag_chunks
                    ORDER BY embedding <=> $1::vector
                    LIMIT $2
                )
                SELECT * FROM ranked WHERE score >= $3 ORDER BY score DESC;
            """
            params = [query_vec.tolist(), top_k * 2, threshold]

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

        logger.info(
            f"📚 {len(results)}/{top_k} chunks ≥ seuil {threshold} "
            f"(métier: {metier_filter or 'tous'})"
        )
        return results

    # ── Indexation ─────────────────────────────────────────────────────────────

    async def index_chunks(
        self,
        chunks: List[Dict[str, Any]],
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

        # Unique appel GPU — tous les embeddings d'un fichier en une passe
        embeddings = await asyncio.to_thread(
            self.embedding_engine.encode, texts
        )

        # Guard NaN — OOM GPU partiel sur GDDR6 unifiée BC-250
        if not np.isfinite(embeddings).all():
            nan_chunks = int(np.sum(~np.isfinite(embeddings).any(axis=1)))
            logger.error(
                f"❌ {nan_chunks} vecteurs NaN détectés dans « {filename} » "
                f"— probable OOM GPU partiel — indexation annulée"
            )
            raise RuntimeError(
                f"{nan_chunks} embeddings NaN dans {filename} — vérifiez la VRAM disponible"
            )
        logger.debug(f"✅ Embeddings validés (shape={embeddings.shape}, finite=True)")

        records = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
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
                i,                 # chunk_index — UNIQUE avec file_id (FIX BUG#4)
                chunk["text"],
                meta,
                emb.tolist(),      # pgvector accepte list[float]
            ))

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

    # ── Génération ─────────────────────────────────────────────────────────────

    async def generate(
        self,
        query: str,
        context: Optional[str] = None,
        system_prompt: str = "",
    ) -> str:
        """
        Génère une réponse via Ollama avec paramètres BC-250.

        num_ctx=4096  : calibré pour 12 Go VRAM (amdgpu.gttsize=12288).
        num_thread=6  : utilise les 6 cœurs Zen 2.
        num_gpu=-1    : FIX BUG#5 — charge TOUTES les layers sur GPU.
                        num_gpu représente le nombre de LAYERS (pas de CUs !).
                        Mistral 7B Q4_K_M ≈ 32 layers. Mettre 24 ne chargeait
                        que 75 % du modèle sur GPU, le reste en RAM CPU.
                        -1 = comportement optimal recommandé par Ollama.
        f16_kv=True   : KV-cache fp16 → -50 % VRAM.
        temperature=0.3 : déterministe → réponses courtes = moins de VRAM.
        stream=False  : évite la fragmentation mémoire sur réponses partielles.
        """
        if context:
            full_prompt = (
                f"Contexte (sources documentaires) :\n{context}\n\n"
                f"Question : {query}\n\n"
                "Réponds en français en te basant EXCLUSIVEMENT sur le contexte. "
                "Cite toujours tes sources (« Selon [Source]... »). "
                "Si l'information est absente du contexte, dis-le clairement."
            )
        else:
            full_prompt = (
                f"Question : {query}\n\n"
                "Aucun document pertinent trouvé dans la base. "
                "Reformule ou précise ta demande."
            )

        try:
            response = await self.http_client.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model":  self.model_name,
                    "prompt": full_prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p":       0.9,
                        "top_k":       40,
                        "num_predict": 1024,
                        "num_ctx":     4096,   # Calibré pour 12 Go VRAM BC-250
                        "num_thread":  6,      # = nb cœurs Zen 2
                        "num_gpu":     99,     # force toutes les 32 layers Mistral 7B sur GPU (convention Ollama)
                        "f16_kv":      True,   # KV-cache fp16 → -50 % VRAM
                    },
                },
            )
            response.raise_for_status()
            return response.json().get("response", "Erreur : réponse Ollama vide")

        except Exception as e:
            logger.error(f"❌ Erreur génération Ollama : {e}")
            return f"Erreur lors de la génération : {e}"

    # ── Stats & Maintenance ────────────────────────────────────────────────────

    async def get_collection_stats(self) -> Dict[str, Any]:
        async with self._pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM rag_chunks;")
            files = await conn.fetchval(
                "SELECT COUNT(DISTINCT file_id) FROM rag_chunks;"
            )
        return {
            "total_chunks":    total,
            "total_documents": files,
            "collection_name": "rag_chunks (pgvector HNSW)",
            "backend":         "PostgreSQL + pgvector v5.1",
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

    # ── Health checks ──────────────────────────────────────────────────────────

    async def check_ollama_health(self):
        r = await self.http_client.get(f"{self.ollama_host}/api/tags")
        r.raise_for_status()

    async def check_db_health(self):
        async with self._pool.acquire() as conn:
            await conn.fetchval("SELECT 1;")

    async def check_chroma_health(self):
        """Alias de compatibilité — ChromaDB supprimé en v5, remplacé par pgvector."""
        await self.check_db_health()

    # ── Fermeture ──────────────────────────────────────────────────────────────

    async def close(self):
        """
        Ferme le client HTTP Ollama.
        NE ferme PAS self._pool — c'est le pool partagé de database.py,
        fermé par close_db() au shutdown de l'application FastAPI.
        """
        await self.http_client.aclose()
        logger.info("✅ RAG Engine v5.4 fermé (pool DB géré par database.py)")
