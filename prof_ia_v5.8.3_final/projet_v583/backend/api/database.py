"""
Database v5.8 ALL-IN-ONE — Prof IA (AMD BC-250)
================================================
Responsabilité : gestion exclusive du stockage PostgreSQL.

Contenu de ce fichier :
  - Pool asyncpg partagé (thread-safe via asyncio.Lock)
  - Schéma PostgreSQL : conversations, évaluations, incidents
  - Export dataset fine-tuning (conversations ⭐4-5)
  - Statistiques dashboard

Ce fichier NE gère PAS les vecteurs RAG.
Les vecteurs sont dans ChromaDB (rag_engine.py + chromadb_data/).

Optimisations BC-250 :
  - asyncpg protocole binaire natif : 3-5× plus rapide que SQLAlchemy async
  - min_size=2 / max_size=10 : évite de saturer les 16 Go GDDR6 partagés
  - statement_cache_size=200 : zéro re-parsing SQL pour les appels répétitifs
  - command_timeout=60 : cohérent avec le timeout Ollama de RAGEngine
"""

import asyncio
import asyncpg
from typing import Optional
from loguru import logger
from .config import get_settings

settings = get_settings()

_pool: Optional[asyncpg.Pool] = None
_init_lock = asyncio.Lock()   # évite les doubles initialisations concurrentes


async def init_db() -> asyncpg.Pool:
    """
    Crée le pool asyncpg unique et applique le schéma PostgreSQL.
    Appelé par le lifespan FastAPI au démarrage (main.py).
    """
    global _pool

    _pool = await asyncpg.create_pool(
        settings.DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=60,
        statement_cache_size=200,
    )

    async with _pool.acquire() as conn:

        # ── Extension UUID ───────────────────────────────────────────────────
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

        # ── Table conversations ──────────────────────────────────────────────
        # Stocke chaque échange utilisateur ↔ Professeur IA.
        # user_rating (1-5 ⭐) alimente le dataset fine-tuning via /dataset/export.
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
                query_mode       VARCHAR(20) DEFAULT 'précis',
                user_rating      SMALLINT CHECK (user_rating BETWEEN 1 AND 5),
                CONSTRAINT valid_metier
                    CHECK (metier IN ('TSSR', 'AIS', 'DevOps') OR metier IS NULL)
            );
        """)

        # Migrations douces (compatibilité bases existantes)
        await conn.execute("""
            ALTER TABLE conversations
            ADD COLUMN IF NOT EXISTS query_mode VARCHAR(20) DEFAULT 'précis';
        """)
        await conn.execute("""
            ALTER TABLE conversations
            ADD COLUMN IF NOT EXISTS user_rating SMALLINT
            CHECK (user_rating BETWEEN 1 AND 5);
        """)

        # ── Table évaluations automatiques ──────────────────────────────────
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

        # ── Table incidents de réponse ───────────────────────────────────────
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

        # ── Index sur conversations ──────────────────────────────────────────
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

    logger.info("✅ Schéma v5.8 initialisé (conversations + évaluations)")
    return _pool


async def get_db() -> asyncpg.Pool:
    """
    Retourne le pool partagé, en l'initialisant si nécessaire.
    asyncio.Lock() évite les races condition au démarrage.
    """
    global _pool
    if _pool is None:
        async with _init_lock:
            if _pool is None:
                await init_db()
    return _pool


async def get_high_rated_conversations(min_rating: int = 4):
    """
    Récupère les conversations bien notées (≥ min_rating) pour l'export dataset.
    Utilisé par POST /dataset/export dans main.py.
    """
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                id,
                user_query       AS query,
                model_response   AS response,
                rag_context      AS context,
                metier,
                model_name       AS model_used,
                query_mode,
                user_rating      AS rating,
                timestamp
            FROM conversations
            WHERE user_rating >= $1
            ORDER BY timestamp DESC
        """, min_rating)

        return [dict(row) for row in rows]


async def get_dataset_stats():
    """
    Retourne les statistiques du dataset pour le dashboard.
    Utilisé par GET /dataset/stats dans main.py.
    """
    pool = await get_db()
    async with pool.acquire() as conn:

        rating_stats = await conn.fetch("""
            SELECT user_rating AS rating, COUNT(*) AS count
            FROM conversations
            WHERE user_rating IS NOT NULL
            GROUP BY user_rating
            ORDER BY user_rating DESC
        """)

        metier_stats = await conn.fetch("""
            SELECT
                metier,
                COUNT(*)                        AS count,
                AVG(user_rating)::numeric(3,2)  AS avg_rating
            FROM conversations
            WHERE user_rating >= 4
            GROUP BY metier
            ORDER BY count DESC
        """)

        total = await conn.fetchval("""
            SELECT COUNT(*) FROM conversations WHERE user_rating IS NOT NULL
        """)

        high_quality = await conn.fetchval("""
            SELECT COUNT(*) FROM conversations WHERE user_rating >= 4
        """)

        return {
            "total_rated":        total,
            "high_quality_count": high_quality,
            "fine_tuning_ready":  high_quality >= 50,
            "by_rating":  [dict(row) for row in rating_stats],
            "by_metier":  [dict(row) for row in metier_stats],
        }


async def close_db():
    """Ferme proprement le pool au shutdown de l'application FastAPI."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("✅ Pool PostgreSQL fermé")
