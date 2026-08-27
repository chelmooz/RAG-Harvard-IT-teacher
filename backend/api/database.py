"""
Database v6.0 — Prof IA (AMD BC-250)
======================================
Source de vérité unique pour :
  - Le pool asyncpg partagé (réutilisé par RAGEngine — FIX BUG#3)
  - Le schéma PostgreSQL complet (conversations, RAG, évaluations — FIX W10)
  - Les index HNSW et conversations

CORRECTIFS v6.0 :
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
import json

import asyncpg
from loguru import logger

from .config import get_settings

# FIX BUG#4 : import du codec pgvector pour asyncpg.
# register_vector() est appelé PAR CONNEXION via le callback init= de create_pool
# (voir _init_connection). asyncpg n'enregistre PAS non plus le codec JSONB tout
# seul : _init_connection enregistre aussi jsonb (encoder/decoder) pour éviter les
# DataError sur les colonnes metadata / rag_sources (JSONB).
try:
    from pgvector.asyncpg import register_vector
except ImportError:
    register_vector = None
    logger.warning("⚠️  pgvector.asyncpg non disponible — vérifiez : pip install pgvector")

settings = get_settings()

_pool: asyncpg.Pool | None = None
_init_lock = asyncio.Lock()   # FIX W13 : évite les doubles initialisations concurrentes


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Callback d'init du pool (appelée par connexion physique).

    FIX P0-1 + P0-2 : register_vector doit être appelé SUR LA CONNEXION (pas sur
    le pool), et asyncpg n'enregistre PAS automatiquement le codec JSONB — sans
    lui, l'insertion/lecture de métadonnées JSONB échoue (DataError, ou str au
    lieu de dict). On enregistre les deux ici, une fois pour toutes.
    """
    if register_vector is not None:
        await register_vector(conn)
        logger.info("✅ Codec pgvector enregistré sur la connexion")
    else:
        logger.error("❌ register_vector indisponible — les requêtes vectorielles échoueront")
    await conn.set_type_codec(
        "jsonb", schema="pg_catalog",
        encoder=json.dumps, decoder=json.loads, format="text",
    )


async def _create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        settings.DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=60,
        statement_cache_size=200,
        init=_init_connection,
    )


async def _create_extensions(conn: asyncpg.Connection) -> None:
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')


async def _create_conversations_table(conn: asyncpg.Connection) -> None:
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
            model_name       VARCHAR(100) DEFAULT 'qwen3:14b',
            metier           VARCHAR(50),
            CONSTRAINT valid_metier
                CHECK (metier IN ('TSSR', 'AIS', 'DevOps') OR metier IS NULL)
        );
    """)


async def _create_evaluations_table(conn: asyncpg.Connection) -> None:
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


async def _create_issues_table(conn: asyncpg.Connection) -> None:
    """
    MT-00.04 — Recrée response_issues (supprimée en PR 4).

    Stocke les défauts détectés par le Juge / Avocat du diable.
    evaluation_run_id + contrainte UNIQUE (conversation_id, evaluation_run_id,
    issue_type, claim_hash) garantissent l'idempotence (MT-02.06) : deux passes
    d'évaluation identiques ne créent qu'une seule ligne par claim.
    """
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS response_issues (
            id                BIGSERIAL PRIMARY KEY,
            conversation_id   UUID REFERENCES conversations(id) ON DELETE CASCADE,
            evaluation_run_id UUID NOT NULL DEFAULT uuid_generate_v4(),
            issue_type        VARCHAR(50) NOT NULL
                              CHECK (issue_type IN (
                                  'hallucination', 'incomplete', 'off-topic',
                                  'low_relevance', 'no_citations',
                                  'hallucination_markers', 'other'
                              )),
            claim_hash        CHAR(64),
            description       TEXT,
            detected_at       TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (conversation_id, evaluation_run_id, issue_type, claim_hash)
        );
        """
    )


async def _create_rag_chunks_table(conn: asyncpg.Connection) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS rag_chunks (
            id          BIGSERIAL PRIMARY KEY,
            file_id     TEXT NOT NULL,
            filename    TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content     TEXT NOT NULL,
            metadata    JSONB DEFAULT '{}',
            embedding   vector(1024),
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT rag_chunks_file_chunk_unique
                UNIQUE (file_id, chunk_index)
        );
    """)


async def _create_tables(conn: asyncpg.Connection) -> None:
    await _create_conversations_table(conn)
    await _create_evaluations_table(conn)
    await _create_issues_table(conn)
    await _create_rag_chunks_table(conn)


async def _migrate_embedding_dim(conn: asyncpg.Connection) -> None:
    current_dim = await conn.fetchval("""
        SELECT atttypmod
        FROM pg_attribute
        WHERE attrelid = 'rag_chunks'::regclass
          AND attname = 'embedding'
    """)
    if current_dim is not None and current_dim != 1024:
        row_count = await conn.fetchval("SELECT count(*) FROM rag_chunks")
        if row_count > 0:
            raise RuntimeError(
                f"rag_chunks.embedding existe en dimension {current_dim} "
                f"(ancien modèle), pas 1024 (BGE-M3), et contient {row_count} "
                "lignes. Migration requise AVANT de redémarrer : "
                "1) sauvegarder si besoin, 2) DROP INDEX idx_rag_embedding_hnsw, "
                "3) TRUNCATE rag_chunks (les vecteurs de l'ancien modèle ne "
                "sont PAS convertibles — un simple ALTER COLUMN TYPE échouera "
                "ou produira des vecteurs faux), 4) ré-indexer tous les "
                "documents sources avec BGE-M3. Voir Prof-IA-v5-Documentation-"
                "BC250.md §2 (migration embedding)."
            )
        else:
            logger.warning(
                f"⚠️  rag_chunks.embedding en dimension {current_dim}, pas "
                "1024 — table vide, correction automatique du schéma."
            )
            await conn.execute("DROP INDEX IF EXISTS idx_rag_embedding_hnsw;")
            await conn.execute(
                "ALTER TABLE rag_chunks ALTER COLUMN embedding TYPE vector(1024);"
            )


async def _create_indexes(conn: asyncpg.Connection) -> None:
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_rag_embedding_hnsw
        ON rag_chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_rag_file_id
        ON rag_chunks (file_id);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_rag_metier
        ON rag_chunks ((metadata->>'metier'));
    """)
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
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_issues_conversation
        ON response_issues(conversation_id);
    """)


async def init_db() -> asyncpg.Pool:
    global _pool

    _pool = await _create_pool()

    async with _pool.acquire() as conn:
        await _create_extensions(conn)
        await _create_tables(conn)
        await _migrate_embedding_dim(conn)
        await _create_indexes(conn)

        version = await conn.fetchval("SELECT version();")
        logger.info(f"✅ PostgreSQL : {version[:60]}")

    logger.info("✅ Schéma v6.0 initialisé (pgvector HNSW + UNIQUE rag_chunks)")
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


async def save_feedback(
    conn: asyncpg.Connection,
    conversation_id: str,
    human_rating: int | None,
    human_feedback: str | None,
    is_golden: bool,
) -> None:
    """
    Enregistre (ou met à jour) le feedback humain d'une conversation.

    Ferme la boucle humain-dans-la-boucle : les réponses jugées exemplaires
    (is_golden=true) alimentent response_evaluations, d'où experimental/fine_tuning/train.py
    exporte ensuite le jeu SFT. ON CONFLICT gère le cas d'un feedback multiple
    sur la même conversation (UNIQUE(conversation_id)).
    """
    await conn.execute(
        """
        INSERT INTO response_evaluations
            (conversation_id, human_rating, human_feedback, is_golden)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (conversation_id) DO UPDATE SET
            human_rating   = EXCLUDED.human_rating,
            human_feedback = EXCLUDED.human_feedback,
            is_golden      = EXCLUDED.is_golden,
            evaluated_at   = NOW()
        """,
        conversation_id, human_rating, human_feedback, is_golden,
    )


async def save_auto_evaluation(
    conn: asyncpg.Connection,
    conversation_id: str,
    auto_score: float,
    auto_criteria: dict,
    evaluation_run_id: str,
    issues: list[dict] | None = None,
) -> None:
    """
    Enregistre l'auto-évaluation (Juge + Avocat) SANS écraser le feedback humain.

    UPSERT symétrique : seuls auto_score / auto_criteria / evaluated_at sont
    écrits — human_rating / human_feedback / is_golden sont préservés (la boucle
    humain reste la source de vérité pour le fine-tuning). Les issues (claims
    contestés par l'Avocat) sont insérées dans response_issues avec
    evaluation_run_id pour l'idempotence (MT-02.06).
    """
    await conn.execute(
        """
        INSERT INTO response_evaluations
            (conversation_id, auto_score, auto_criteria, evaluated_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (conversation_id) DO UPDATE SET
            auto_score    = EXCLUDED.auto_score,
            auto_criteria = EXCLUDED.auto_criteria,
            evaluated_at  = NOW()
        """,
        conversation_id, auto_score, json.dumps(auto_criteria),
    )

    if issues:
        for issue in issues:
            await conn.execute(
                """
                INSERT INTO response_issues
                    (conversation_id, evaluation_run_id, issue_type, claim_hash, description)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (conversation_id, evaluation_run_id, issue_type, claim_hash)
                DO NOTHING
                """,
                conversation_id,
                issue["evaluation_run_id"],
                issue["issue_type"],
                issue["claim_hash"],
                issue["description"],
            )
