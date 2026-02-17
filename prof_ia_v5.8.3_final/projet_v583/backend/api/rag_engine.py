"""
RAG Engine v5.8 ALL-IN-ONE — AMD BC-250 (Cyan Skillfish / RDNA2)
=================================================================
Architecture v5.8 ALL-IN-ONE :
  - Backend vectoriel : ChromaDB (collection universelle prof_ia_all)
  - Modèle embeddings : all-MiniLM-L6-v2 (384d, léger, stable BC-250)
                        → DOIT correspondre à import_datasets.py
  - Architecture      : collection unique — zéro confusion de routage
  - PostgreSQL        : conversations, ratings, dataset export (database.py)

Algorithmes RAG :
  - 3 modes de retrieval : précis / explore / synthèse
  - MMR (Maximal Marginal Relevance) — diversification des chunks
  - Multi-Query expansion — mode synthèse uniquement
  - ROCm / AMD BC-250 : fp16, torch.compile, HSA_OVERRIDE_GFX_VERSION
  - NaN guard .all(axis=1) — protection contre les vecteurs corrompus

Distances ChromaDB :
  ChromaDB retourne distance = 1 - cosine_similarity ∈ [0, 2]
  → threshold similarité 0.72 ↔ distance ≤ 0.28
  La conversion est faite dans _fetch_candidates().
"""

import asyncio
import json
import os
import re
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal

import httpx
import numpy as np
from loguru import logger

# ── ROCm / PyTorch ─────────────────────────────────────────────────────────────
os.environ.setdefault("HSA_OVERRIDE_GFX_VERSION", "10.1.3")
os.environ.setdefault("PYTORCH_HIP_ALLOC_CONF", "max_split_size_mb:512")

import torch
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

# ── Type pour les modes RAG ─────────────────────────────────────────────────────
QueryMode = Literal["précis", "explore", "synthèse"]


# ── Détection GPU AMD ───────────────────────────────────────────────────────────

def _get_device() -> torch.device:
    if torch.cuda.is_available():
        dev = torch.device("cuda:0")
        props = torch.cuda.get_device_properties(0)
        logger.info(
            f"🟢 GPU AMD détecté : {props.name} | "
            f"{props.total_memory // 1024**2} Mo GDDR6 unifiée"
        )
        return dev
    logger.warning("⚠️  Pas de GPU ROCm détecté — exécution CPU (BC-250 absent)")
    return torch.device("cpu")


DEVICE = _get_device()


# ── EmbeddingEngine ─────────────────────────────────────────────────────────────

class EmbeddingEngine:
    """
    Moteur d'embeddings AMD BC-250 optimisé.

    MODÈLE v5.8 : all-MiniLM-L6-v2 (384 dimensions)
      - Doit correspondre au modèle utilisé dans import_datasets.py
      - 384d vs 768d (v5.7) : 2× moins de VRAM → plus stable sur 16 GB unifiée
      - Multilingue suffisant pour les datasets FR/EN utilisés
      - Batch size 32 : safe pour ROCm BC-250 (64 peut OOM sur gros datasets)
    """
    BATCH_SIZE = 32                                               # AMD BC-250 safe
    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"        # 384 dims — v5.8

    def __init__(self, model_name: str = MODEL_NAME):
        logger.info(f"📦 Chargement modèle embeddings → {model_name}")
        self.model = SentenceTransformer(model_name, device=str(DEVICE))

        if DEVICE.type != "cpu":
            self.model = self.model.half()                        # fp16 : −50% VRAM
            logger.info("🔢 Modèle converti en fp16")
            try:
                self.model = torch.compile(self.model, mode="reduce-overhead")
                logger.info("⚡ torch.compile activé (reduce-overhead)")
            except Exception as e:
                logger.warning(f"⚠️  torch.compile échoué : {e} — mode standard")

        logger.info("✅ EmbeddingEngine v5.8 prêt (384 dims)")

    def encode(self, texts: List[str]) -> np.ndarray:
        """Encode en batch — toujours float32 en sortie (stable pour ChromaDB)."""
        with torch.inference_mode():
            vecs = self.model.encode(
                texts,
                batch_size=self.BATCH_SIZE,
                normalize_embeddings=True,       # cosine = produit scalaire
                convert_to_numpy=False,
                show_progress_bar=False,
            )
        return vecs.cpu().float().numpy()

    def encode_single(self, text: str) -> np.ndarray:
        return self.encode([text])[0]


# ── RAGEngine v5.8 ALL-IN-ONE ───────────────────────────────────────────────────

class RAGEngine:
    """
    Moteur RAG v5.8 ALL-IN-ONE.
    Interface publique identique à v5.7 (drop-in replacement).

    Stockage vectoriel : ChromaDB (collection 'prof_ia_all')
    Stockage conversations : PostgreSQL (inchangé — géré par database.py)
    """

    # Distance ChromaDB ↔ seuil similarité : sim = 1 - dist
    # threshold_sim=0.72 → max_distance=0.28
    DEFAULT_THRESHOLD = 0.72

    def __init__(
        self,
        db_url: str = "",                           # conservé pour compat main.py v5.7
        ollama_host: str = "http://localhost:11434",
        model_name: str = "mistral:7b-instruct",
        embedding_model: str = EmbeddingEngine.MODEL_NAME,
        chromadb_path: str = "/app/chromadb_data",
    ):
        # db_url conservé mais non utilisé pour le RAG (conversations via database.py)
        self.db_url      = db_url
        self.ollama_host = ollama_host
        self.model_name  = model_name
        self.chromadb_path = chromadb_path

        self.embedding_engine = EmbeddingEngine(embedding_model)
        self.http_client = httpx.AsyncClient(timeout=240.0)

        # ChromaDB initialisé en synchrone (pas d'async natif ChromaDB)
        logger.info(f"📂 ChromaDB path : {self.chromadb_path}")
        self._chroma_client = chromadb.PersistentClient(
            path=self.chromadb_path,
            settings=Settings(anonymized_telemetry=False)
        )
        self._collection = None      # chargé dans initialize()

    # ── Initialisation ──────────────────────────────────────────────────────────

    async def initialize(self):
        """
        Charge la collection ChromaDB et vérifie Ollama.
        Appelé par le lifespan FastAPI au démarrage.
        """
        logger.info("🔧 Initialisation RAG Engine v5.8 ALL-IN-ONE...")

        # Charger ou créer la collection prof_ia_all
        try:
            self._collection = self._chroma_client.get_collection(name="prof_ia_all")
            count = self._collection.count()
            logger.info(f"✅ Collection 'prof_ia_all' chargée : {count} chunks")
        except Exception:
            # Collection absente → créer une collection vide
            # (sera peuplée par import_datasets.py ou upload de documents)
            self._collection = self._chroma_client.create_collection(
                name="prof_ia_all",
                metadata={"description": "Prof IA v5.8 — collection universelle ALL-IN-ONE"}
            )
            logger.warning(
                "⚠️  Collection 'prof_ia_all' créée vide. "
                "Lancez import_datasets.py pour indexer les datasets."
            )

        try:
            await self.check_ollama_health()
            logger.info(f"✅ Ollama opérationnel — modèle : {self.model_name}")
        except Exception as e:
            logger.warning(f"⚠️  Ollama non disponible au démarrage : {e}")

        logger.info("✅ RAG Engine v5.8 ALL-IN-ONE prêt")

    # ══════════════════════════════════════════════════════════════════════════════
    # ALGORITHME MMR — Maximal Marginal Relevance (identique v5.6)
    # ══════════════════════════════════════════════════════════════════════════════

    def _mmr_rerank(
        self,
        query_vec: np.ndarray,
        candidates: List[Dict[str, Any]],
        top_k: int,
        lambda_param: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Sélectionne top_k chunks en équilibrant pertinence et diversité.
        Formule : score(c) = λ · sim(c, query) − (1−λ) · max(sim(c, sélectionné))
        lambda=0.7 : 70% pertinence / 30% diversité.
        """
        if not candidates or len(candidates) <= top_k:
            return candidates[:top_k]

        texts = [c["text"] for c in candidates]
        try:
            cand_vecs = self.embedding_engine.encode(texts)
        except Exception as e:
            logger.warning(f"⚠️  MMR encodage échoué ({e}) — fallback top-k classique")
            return candidates[:top_k]

        selected_indices: List[int] = []
        remaining = list(range(len(candidates)))

        for _ in range(min(top_k, len(candidates))):
            if not remaining:
                break
            best_idx, best_score = None, float("-inf")
            for i in remaining:
                relevance = float(np.dot(query_vec, cand_vecs[i]))
                max_sim_sel = (
                    max(float(np.dot(cand_vecs[i], cand_vecs[j])) for j in selected_indices)
                    if selected_indices else 0.0
                )
                score = lambda_param * relevance - (1 - lambda_param) * max_sim_sel
                if score > best_score:
                    best_score = score
                    best_idx = i
            if best_idx is not None:
                selected_indices.append(best_idx)
                remaining.remove(best_idx)

        result = [candidates[i] for i in selected_indices]
        logger.info(f"🎯 MMR : {len(candidates)} → {len(result)} chunks (λ={lambda_param})")
        return result

    # ══════════════════════════════════════════════════════════════════════════════
    # MULTI-QUERY EXPANSION (identique v5.6)
    # ══════════════════════════════════════════════════════════════════════════════

    async def _expand_query(self, query: str, n: int = 3) -> List[str]:
        """Génère n reformulations via Ollama pour élargir le retrieval."""
        prompt = (
            f"Génère exactement {n} reformulations différentes de cette question "
            f"pour une recherche documentaire en français. "
            f"Réponds UNIQUEMENT avec un JSON valide : "
            f'["reformulation1", "reformulation2", "reformulation3"]\n\n'
            f"Question : {query}"
        )
        try:
            response = await self.http_client.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.4,
                        "num_predict": 200,
                        "num_ctx": 512,
                        "num_gpu": -1,
                    },
                },
                timeout=30.0,
            )
            response.raise_for_status()
            raw = response.json().get("response", "")
            if "<think>" in raw:
                raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            match = re.search(r"\[.*?\]", raw, re.DOTALL)
            if match:
                queries = json.loads(match.group())
                valid = [q for q in queries if isinstance(q, str) and q.strip()][:n]
                logger.info(f"🔍 Multi-Query : {len(valid)} reformulations générées")
                return [query] + valid
        except Exception as e:
            logger.warning(f"⚠️  Multi-Query échoué ({e}) — query originale seule")
        return [query]

    # ══════════════════════════════════════════════════════════════════════════════
    # RETRIEVAL PRINCIPAL — 3 modes (précis / explore / synthèse)
    # ══════════════════════════════════════════════════════════════════════════════

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = DEFAULT_THRESHOLD,
        metier_filter: Optional[str] = None,
        mode: QueryMode = "précis",
        mmr_lambda: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Retrieval adaptatif :
          précis   → top-k cosine classique (~0.5s)
          explore  → over-fetch × 3 + MMR (~1.5s)
          synthèse → Multi-Query + over-fetch + MMR (~4-6s)

        metier_filter : 'TSSR' | 'AIS' | 'DevOps' | None (tous)
          → En ALL-IN-ONE, None est recommandé pour les questions mixtes.
          → Le filtre reste disponible pour des besoins pédagogiques précis.
        """
        if mode == "synthèse":
            expanded_queries = await self._expand_query(query, n=3)
        else:
            expanded_queries = [query]

        # Encoder toutes les queries en batch GPU
        all_queries_vecs = await asyncio.to_thread(
            self.embedding_engine.encode, expanded_queries
        )
        query_vec = all_queries_vecs[0]

        # Over-fetch selon le mode
        fetch_multiplier = {"précis": 2, "explore": 3, "synthèse": 2}[mode]
        fetch_k = top_k * fetch_multiplier

        # Requêtes ChromaDB (une par sous-query) + déduplication
        seen_ids: set = set()
        all_candidates: List[Dict[str, Any]] = []

        for q_vec in all_queries_vecs:
            rows = await asyncio.to_thread(
                self._fetch_candidates, q_vec, fetch_k, threshold, metier_filter
            )
            for row in rows:
                uid = row["chunk_uid"]
                if uid not in seen_ids:
                    seen_ids.add(uid)
                    all_candidates.append(row)

        if not all_candidates:
            logger.info("📭 Aucun chunk trouvé au-dessus du seuil")
            return []

        logger.info(
            f"📥 Pool candidats : {len(all_candidates)} chunks "
            f"(mode={mode}, {len(expanded_queries)} query(ies))"
        )

        # Re-ranking selon le mode
        if mode == "précis":
            all_candidates.sort(key=lambda x: x["score"], reverse=True)
            results = all_candidates[:top_k]
        else:
            results = await asyncio.to_thread(
                self._mmr_rerank, query_vec, all_candidates, top_k, mmr_lambda
            )

        for i, r in enumerate(results):
            r["rank"] = i + 1

        logger.info(
            f"✅ {len(results)}/{top_k} chunks retenus "
            f"(mode={mode}, seuil={threshold}, métier={metier_filter or 'tous'})"
        )
        return results

    def _fetch_candidates(
        self,
        query_vec: np.ndarray,
        fetch_k: int,
        threshold: float,
        metier_filter: Optional[str],
    ) -> List[Dict[str, Any]]:
        """
        Requête ChromaDB synchrone (appelée via asyncio.to_thread).

        CONVERSION distance → similarité :
          ChromaDB cosine renvoie distance = 1 - cosine_sim ∈ [0, 2]
          sim = 1 - distance → on filtre sim >= threshold
          soit distance <= (1 - threshold)
        """
        if self._collection is None:
            return []

        max_distance = 1.0 - threshold      # ex: threshold=0.72 → max_dist=0.28

        # Filtre optionnel par métier (metadata ChromaDB)
        where_filter = {"source": {"$eq": metier_filter}} if metier_filter else None

        try:
            kwargs = {
                "query_embeddings": [query_vec.tolist()],
                "n_results": min(fetch_k, self._collection.count() or 1),
                "include": ["documents", "metadatas", "distances"],
            }
            if where_filter:
                kwargs["where"] = where_filter

            results = self._collection.query(**kwargs)
        except Exception as e:
            logger.error(f"❌ Erreur ChromaDB query : {e}")
            return []

        candidates = []
        if not results or not results["documents"]:
            return []

        docs      = results["documents"][0]
        metas     = results["metadatas"][0] if results["metadatas"] else [{}] * len(docs)
        distances = results["distances"][0] if results["distances"] else [1.0] * len(docs)
        ids       = results["ids"][0]       if results.get("ids")   else [str(i) for i in range(len(docs))]

        for doc, meta, dist, uid in zip(docs, metas, distances, ids):
            sim = 1.0 - dist
            if sim >= threshold:
                candidates.append({
                    "text":      doc,
                    "metadata":  meta or {},
                    "score":     sim,
                    "file_id":   meta.get("file_id", uid) if meta else uid,
                    "chunk_uid": uid,
                })

        return candidates

    # ── Indexation (documents uploadés via l'interface) ─────────────────────────

    async def index_chunks(
        self,
        chunks: List[Dict[str, Any]],
        file_id: str,
        filename: str,
    ):
        """
        Indexe les chunks d'un document uploadé dans prof_ia_all.

        COMPATIBILITÉ v5.8 : les documents uploadés rejoignent la même
        collection universelle que les datasets pré-indexés. Ils portent
        la métadonnée source='upload' pour les distinguer si besoin.

        NaN guard .all(axis=1) conservé (FIX v5.7.1).
        """
        if not chunks:
            logger.warning("⚠️  Aucun chunk à indexer")
            return
        if self._collection is None:
            raise RuntimeError("Collection ChromaDB non initialisée")

        texts = [c["text"] for c in chunks]
        logger.info(f"🔢 Encodage batch : {len(texts)} chunks pour «{filename}»...")

        embeddings = await asyncio.to_thread(self.embedding_engine.encode, texts)

        # NaN guard — FIX v5.7.1 : .all(axis=1) détecte les vecteurs partiellement NaN
        if not np.isfinite(embeddings).all():
            nan_chunks = int(np.sum(~np.isfinite(embeddings).all(axis=1)))
            logger.error(f"❌ {nan_chunks} vecteurs NaN/inf — probable OOM GPU — annulé")
            raise RuntimeError(f"{nan_chunks} embeddings NaN dans {filename}")

        # Préparer les données ChromaDB
        docs, metas, ids, embs = [], [], [], []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            chunk_meta = chunk.get("metadata", {})
            docs.append(chunk["text"])
            metas.append({
                "source":   chunk_meta.get("metier", "upload"),
                "file_id":  file_id,
                "filename": filename,
                "chunk_id": str(i),
                **{k: str(v) for k, v in chunk_meta.items()
                   if k not in ("metier",) and isinstance(v, (str, int, float, bool))},
            })
            ids.append(f"{file_id}_{i}")
            embs.append(emb.tolist())

        # Insertion par batch de 512 (ChromaDB recommandation)
        BATCH = 512
        for start in range(0, len(docs), BATCH):
            end = start + BATCH
            self._collection.upsert(              # upsert = idempotent (re-indexation safe)
                documents=docs[start:end],
                embeddings=embs[start:end],
                metadatas=metas[start:end],
                ids=ids[start:end],
            )

        logger.info(f"✅ {len(docs)} chunks indexés dans 'prof_ia_all' pour «{filename}»")

    # ── Génération (identique v5.6) ─────────────────────────────────────────────

    async def generate(
        self,
        query: str,
        context: Optional[str] = None,
        system_prompt: str = "",
        mode: QueryMode = "précis",
    ) -> str:
        """
        Génère une réponse via Ollama.
        Paramètres num_ctx adaptés au mode (précis=4096 / explore=8192 / synthèse=16384).
        Filtre <think>...</think> pour DeepSeek R1.
        """
        is_deepseek = "deepseek" in self.model_name.lower()
        num_ctx_map = {"précis": 4096, "explore": 8192, "synthèse": 16384}
        num_ctx     = num_ctx_map.get(mode, 4096)

        if context:
            mode_instruction = {
                "précis":   "Réponds de façon précise et concise.",
                "explore":  "Les sources couvrent plusieurs angles. Intègre les différentes perspectives.",
                "synthèse": "Produis une réponse exhaustive, structurée et nuancée à partir de toutes les sources.",
            }[mode]

            if is_deepseek:
                full_prompt = (
                    f"Sources documentaires :\n\n{context}\n\n"
                    f"Question : {query}\n\n"
                    f"Instruction : {mode_instruction} "
                    "Raisonne étape par étape, réponds en français "
                    "en te basant EXCLUSIVEMENT sur les sources. "
                    "Cite tes sources (« Selon [Source]... »)."
                )
            else:
                full_prompt = (
                    f"Contexte (sources documentaires) :\n{context}\n\n"
                    f"Question : {query}\n\n"
                    f"{mode_instruction} "
                    "Réponds en français en te basant EXCLUSIVEMENT sur le contexte. "
                    "Cite tes sources (« Selon [Source]... »). "
                    "Si l'information est absente, dis-le clairement."
                )
        else:
            full_prompt = (
                f"Question : {query}\n\n"
                "Aucun document pertinent trouvé dans la base. "
                "Reformule ou précise ta demande."
            )

        options = {
            "num_ctx":    num_ctx,
            "num_thread": 6,
            "num_gpu":    -1,       # FIX RAG-01 : toutes layers GPU
            "f16_kv":     True,
        }
        if is_deepseek:
            options.update({"temperature": 0.6, "top_p": 0.92, "top_k": 50, "num_predict": 2048})
        else:
            num_predict_map = {"précis": 1024, "explore": 1536, "synthèse": 2048}
            options.update({
                "temperature": 0.3,
                "top_p": 0.9,
                "top_k": 40,
                "num_predict": num_predict_map.get(mode, 1024),
            })

        logger.info(f"🤖 Génération mode={mode} | num_ctx={num_ctx} | modèle={self.model_name}")

        try:
            response = await self.http_client.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model":   self.model_name,
                    "prompt":  full_prompt,
                    "system":  system_prompt,
                    "stream":  False,
                    "options": options,
                },
            )
            response.raise_for_status()
            raw = response.json().get("response", "Erreur : réponse Ollama vide")

            if is_deepseek and "<think>" in raw:
                clean = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
                logger.debug(f"🧠 DeepSeek <think> filtré ({len(raw)-len(clean)} chars)")
                return clean if clean else raw

            return raw

        except Exception as e:
            logger.error(f"❌ Erreur génération Ollama : {e}")
            return f"Erreur lors de la génération : {e}"

    # ── Stats & Maintenance ─────────────────────────────────────────────────────

    async def get_collection_stats(self) -> Dict[str, Any]:
        """Statistiques de la collection ChromaDB pour /indexing/status."""
        if self._collection is None:
            return {"total_chunks": 0, "total_documents": 0, "collection_name": "prof_ia_all"}

        total = self._collection.count()

        # Compter les documents distincts (par file_id dans metadata)
        try:
            sample = self._collection.get(include=["metadatas"])
            file_ids = set(
                m.get("file_id", "") for m in (sample["metadatas"] or []) if m
            )
            total_docs = len(file_ids)
        except Exception:
            total_docs = 0

        return {
            "total_chunks":    total,
            "total_documents": total_docs,
            "collection_name": "prof_ia_all (ChromaDB — ALL-IN-ONE)",
            "backend":         "ChromaDB v0.4 + all-MiniLM-L6-v2 (384d)",
            "rag_modes":       ["précis", "explore", "synthèse"],
        }

    async def get_datasets_stats(self) -> Dict[str, Any]:
        """
        Statistiques détaillées par métier — endpoint /datasets/stats (v5.8).
        """
        if self._collection is None:
            return {"total_documents": 0, "by_metier": {}, "architecture": "all-in-one"}

        try:
            total = self._collection.count()
            all_metas = self._collection.get(include=["metadatas"])
            metiers: Dict[str, int] = {}
            for meta in (all_metas["metadatas"] or []):
                src = (meta or {}).get("source", "Unknown")
                metiers[src] = metiers.get(src, 0) + 1

            return {
                "architecture":    "all-in-one",
                "collection":      "prof_ia_all",
                "total_documents": total,
                "by_metier":       metiers,
            }
        except Exception as e:
            logger.error(f"Erreur get_datasets_stats : {e}")
            return {"total_documents": 0, "by_metier": {}, "architecture": "all-in-one"}

    async def reset_collection(self):
        """
        ⚠️  RESET COMPLET : supprime TOUS les chunks (datasets + uploads).
        À utiliser uniquement pour réindexation complète.
        """
        if self._collection is None:
            return
        count = self._collection.count()
        logger.warning(f"⚠️  RESET 'prof_ia_all' : {count} chunks supprimés")
        self._chroma_client.delete_collection(name="prof_ia_all")
        self._collection = self._chroma_client.create_collection(
            name="prof_ia_all",
            metadata={"description": "Prof IA v5.8 — collection universelle ALL-IN-ONE"}
        )
        logger.warning("✅ Collection 'prof_ia_all' réinitialisée (vide)")

    # ── Health checks ───────────────────────────────────────────────────────────

    async def check_ollama_health(self):
        r = await self.http_client.get(f"{self.ollama_host}/api/tags")
        r.raise_for_status()

    async def check_db_health(self):
        """PostgreSQL health check (conversations DB — inchangé)."""
        from .database import get_db
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1;")

    async def check_chroma_health(self):
        """ChromaDB health check — vérifie que la collection répond."""
        if self._collection is None:
            raise RuntimeError("Collection ChromaDB non initialisée")
        _ = self._collection.count()

    async def close(self):
        await self.http_client.aclose()
        logger.info("✅ RAG Engine v5.8 fermé")
