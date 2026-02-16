"""
Database v5.4 — Prof IA (AMD BC-250)
======================================
Source de vérité unique pour :
  - Le pool asyncpg partagé (réutilisé par RAGEngine — FIX BUG#3)
  - Le schéma PostgreSQL complet (conversations, RAG, évaluations — FIX W10)
  - Les index HNSW et conversations

CORRECTIFS v5.4 :
  - FIX BUG#4 : contrainte UNIQUE(file_id, chunk_index) ajoutée sur rag_chunks
  - FIX W10   : seul database.py définit le schéma — rag_engine.py ne crée plus rien
  - FIX W13   : get_db() thread-safe via asyncio.Lock (évite les races à l'init)

POURQUOI asyncpg plutôt que SQLAlchemy ?
  asyncpg communique en protocole binaire PostgreSQL natif — 3-5× plus rapide
  que SQLAlchemy async sur des requêtes vectorielles JSONB répétitives.
  Moins d'allocations Python → moins de pression sur le GC Python 3.13
  en contexte de mémoire unifiée GDDR6.
"""

import asyncio
import asyncpg
from typing import Optional
from loguru import logger
from .config import get_settings

# FIX BUG#4 : import du codec pgvector pour asyncpg.
# register_vector() DOIT être appelé sur le pool AVANT toute requête vectorielle.
# Sans cet enregistrement, asyncpg ne sait pas sérialiser/désérialiser le type
# PostgreSQL 'vector' et lève DataError ou 'cannot adapt type list'.
try:
    from pgvector.asyncpg import register_vector
except ImportError:
    register_vector = None
    logger.warning("⚠️  pgvector.asyncpg non disponible — vérifiez : pip install pgvector")

settings = get_settings()

_pool: Optional[asyncpg.Pool] = None
_init_lock = asyncio.Lock()   # FIX W13 : évite les doubles initialisations concurrentes


async def init_db() -> asyncpg.Pool:
    """
    Crée le pool asyncpg unique et applique le schéma complet.

    OPTIMISATION BC-250 :
    - min_size=2 / max_size=10 : évite de saturer les 16 Go GDDR6 partagés
      (chaque connexion PG alloue ~8 Mo de buffers côté serveur).
    - statement_cache_size=200 : prépare les requêtes pgvector une seule fois
      → zéro re-parsing SQL pour les appels répétitifs de retrieve().
    - command_timeout=60 : cohérent avec le timeout Ollama de RAGEngine.
    """
    global _pool

    _pool = await asyncpg.create_pool(
        settings.DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=60,
        statement_cache_size=200,
    )

    # FIX BUG#4 : enregistrement du codec pgvector sur le pool.
    # Cet appel est OBLIGATOIRE pour que asyncpg sache encoder/décoder
    # le type PostgreSQL 'vector' (list[float] ↔ vector(768)).
    # Sans lui, index_chunks() et retrieve() lèvent une DataError au runtime.
    if register_vector is not None:
        await register_vector(_pool)
        logger.info("✅ Codec pgvector enregistré sur le pool asyncpg")
    else:
        logger.error("❌ register_vector indisponible — les requêtes vectorielles échoueront")

    async with _pool.acquire() as conn:

        # ── Extensions ──────────────────────────────────────────────────────
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

        # ── Table conversations ──────────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                session_id       VARCHAR(255) NOT NULL,
                timestamp        TIMESTAMPTZ DEFAULT NOW(),
                user_query       TEXT NOT NULL,
                model_response   TEXT NOT NULL,
                rag_context      TEXT,
                rag_sources      JSONB,
                rag_used         BOOLEAN DEFAULT true,
                chunks_used      INTEGER,
                rag_threshold    FLOAT,
                response_time_ms INTEGER,
                model_name       VARCHAR(100) DEFAULT 'mistral:7b-instruct-q4_K_M',
                metier           VARCHAR(50),
                user_metadata    JSONB,
                CONSTRAINT valid_metier
                    CHECK (metier IN ('TSSR', 'AIS', 'DevOps') OR metier IS NULL)
            );
        """)

        # ── Table évaluations ────────────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS response_evaluations (
                id                SERIAL PRIMARY KEY,
                conversation_id   UUID REFERENCES conversations(id) ON DELETE CASCADE,
                evaluated_at      TIMESTAMPTZ DEFAULT NOW(),
                auto_score        FLOAT CHECK (auto_score BETWEEN 0 AND 1),
                auto_criteria     JSONB,
                human_rating      INTEGER CHECK (human_rating BETWEEN 1 AND 5),
                human_feedback    TEXT,
                is_golden         BOOLEAN DEFAULT false,
                improved_response TEXT,
                UNIQUE(conversation_id)
            );
        """)

        # ── Table incidents ──────────────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS response_issues (
                id               SERIAL PRIMARY KEY,
                conversation_id  UUID REFERENCES conversations(id) ON DELETE CASCADE,
                issue_type       VARCHAR(50) NOT NULL,
                detected_at      TIMESTAMPTZ DEFAULT NOW(),
                description      TEXT,
                resolved         BOOLEAN DEFAULT false,
                resolved_at      TIMESTAMPTZ,
                resolution_notes TEXT,
                CONSTRAINT valid_issue_type CHECK (
                    issue_type IN (
                        'hallucination', 'incomplete', 'off-topic',
                        'low_relevance', 'no_citations',
                        'hallucination_markers', 'other'
                    )
                )
            );
        """)

        # ── Table vectorielle RAG ────────────────────────────────────────────
        # FIX BUG#4 : contrainte UNIQUE(file_id, chunk_index) ajoutée.
        # Sans cette contrainte, ON CONFLICT DO NOTHING dans index_chunks()
        # est inopérant → doublons à chaque réindexation.
        # FIX W10 : défini ICI UNIQUEMENT — rag_engine.py ne crée plus cette table.
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id          BIGSERIAL PRIMARY KEY,
                file_id     TEXT NOT NULL,
                filename    TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content     TEXT NOT NULL,
                metadata    JSONB DEFAULT '{}',
                -- 768 dims : paraphrase-multilingual-mpnet-base-v2
                embedding   vector(768),
                created_at  TIMESTAMPTZ DEFAULT NOW(),
                -- FIX BUG#4 : contrainte UNIQUE nommée pour ON CONFLICT explicite
                CONSTRAINT rag_chunks_file_chunk_unique
                    UNIQUE (file_id, chunk_index)
            );
        """)

        # ── Index vectoriel HNSW ─────────────────────────────────────────────
        # O(log n) vs O(n) pour IVFFlat — optimal pour < 500 k chunks.
        # m=16, ef_construction=64 : bon compromis recall/vitesse pour 24 CUs RDNA2.
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rag_embedding_hnsw
            ON rag_chunks USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
        """)

        # ── Index auxiliaires RAG ────────────────────────────────────────────
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rag_file_id
            ON rag_chunks (file_id);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rag_metier
            ON rag_chunks ((metadata->>'metier'));
        """)

        # ── Index conversations ──────────────────────────────────────────────
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_timestamp
            ON conversations(timestamp DESC);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_session
            ON conversations(session_id);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_metier
            ON conversations(metier);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_eval_golden
            ON response_evaluations(is_golden)
            WHERE is_golden = true;
        """)

        version = await conn.fetchval("SELECT version();")
        logger.info(f"✅ PostgreSQL : {version[:60]}")

    logger.info("✅ Schéma v5.4 initialisé (pgvector HNSW + UNIQUE rag_chunks)")
    return _pool


async def get_db() -> asyncpg.Pool:
    """
    Retourne le pool partagé, en l'initialisant si nécessaire.

    FIX W13 : asyncio.Lock() évite qu'une rafale de requêtes au démarrage
    déclenche plusieurs init_db() concurrents (race condition).
    """
    global _pool
    if _pool is None:
        async with _init_lock:
            # Double-check après acquisition du lock
            if _pool is None:
                await init_db()
    return _pool


async def close_db():
    """Ferme proprement le pool au shutdown de l'application FastAPI."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("✅ Pool PostgreSQL fermé")
