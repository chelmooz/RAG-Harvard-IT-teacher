"""
Prof IA v6.0 — Point d'entrée FastAPI (AMD BC-250 / Cyan Skillfish)
====================================================================
CORRECTIFS v6.0 :
  - FIX BUG#1 : Ce fichier était absent — application ne pouvait pas démarrer
  - FIX BUG#4 : register_vector() appelé au startup (voir database.py v6.0)
  - FIX BUG#5 : num_gpu corrigé dans RAGEngine (voir rag_engine.py v6.0)

Architecture des endpoints :
  GET  /health              — santé de l'application (DB + Ollama + GPU)
  POST /documents/upload    — upload et indexation d'un document
  GET  /documents/list      — liste des documents indexés
  DELETE /documents/{file_id} — suppression d'un document
  GET  /indexing/status     — statistiques de la collection RAG
  POST /indexing/directory  — indexation d'un répertoire complet
  POST /chat                — requête RAG (retrieval + génération)
  GET  /chat/history        — historique des conversations
"""

import asyncio
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .config import get_settings
from .database import close_db, get_db, init_db, save_feedback
from .document_processor import DocumentProcessor
from .rag_engine import RAGEngine
from .schemas import (
    ChatRequest,
    ChatResponse,
    ConversationRecord,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
)

settings = get_settings()

# ── Authentification API ──────────────────────────────────────────────────────
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


async def verify_api_token(request: Request):
    """Vérifie le token API dans le header Authorization.
    Les endpoints publics sont exemptés. Le token est comparé à settings.API_TOKEN."""
    if request.url.path in PUBLIC_PATHS:
        return True
    auth = request.headers.get("Authorization", "")
    expected = f"Bearer {settings.API_TOKEN}"
    if secrets.compare_digest(auth, expected):
        return True
    raise HTTPException(
        status_code=401,
        detail="Token API invalide ou manquant. Ajoutez Authorization: Bearer <token>"
    )


# ── Instances globales ─────────────────────────────────────────────────────────
_rag_engine: RAGEngine | None = None
_doc_processor: DocumentProcessor | None = None

_bg_tasks: set = set()


def get_rag_engine() -> RAGEngine:
    if _rag_engine is None:
        raise HTTPException(status_code=503, detail="RAG Engine non initialisé")
    return _rag_engine


def get_doc_processor() -> DocumentProcessor:
    if _doc_processor is None:
        raise HTTPException(status_code=503, detail="Document Processor non initialisé")
    return _doc_processor


# ── Lifecycle ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup : init DB (pgvector + register_vector — FIX BUG#4) + RAGEngine.
    Shutdown : fermeture propre HTTP client + pool PostgreSQL.
    """
    global _rag_engine, _doc_processor

    logger.info("🚀 Démarrage Prof IA v6.0 (AMD BC-250)...")

    # FIX BUG#4 : le codec pgvector (+ jsonb) est enregistré par le callback
    # init=_init_connection de create_pool (voir database.py) — une fois par connexion.
    await init_db()
    logger.info("✅ Base de données initialisée (pgvector enregistré)")

    _rag_engine = RAGEngine(
        db_url=settings.DATABASE_URL,
        ollama_host=settings.OLLAMA_HOST,
        model_name=settings.OLLAMA_MODEL,
        embedding_model=settings.EMBEDDING_MODEL,
    )
    await _rag_engine.initialize()
    logger.info("✅ RAG Engine initialisé")

    _doc_processor = DocumentProcessor(upload_dir=settings.UPLOAD_DIR)
    logger.info("✅ Document Processor initialisé")

    logger.info(f"🟢 Prof IA v6.0 prêt — {settings.APP_NAME}")

    yield  # Application en service

    # Shutdown
    logger.info("🔴 Arrêt de Prof IA v6.0...")
    if _rag_engine:
        await _rag_engine.close()
    if _doc_processor:
        _doc_processor.unload_whisper()
    await close_db()
    logger.info("✅ Arrêt propre effectué")


# ── Application FastAPI ────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Système RAG optimisé AMD BC-250 (Cyan Skillfish / RDNA2)",
    lifespan=lifespan,
)

# CORS — piloté par settings.CORS_ORIGINS (.env), plus de wildcard codé en dur.
# CORS_ORIGINS="*" reste possible en dev (voir warning _validate_cors), mais
# en production il faut lister les origines exactes (ex: http://192.168.1.11:3000).
_cors_origins = (
    ["*"] if settings.CORS_ORIGINS.strip() == "*"
    else [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,   # credentials=False obligatoire si "*" est dans allow_origins
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
async def health_check(
    rag: RAGEngine = Depends(get_rag_engine),
    _=Depends(verify_api_token),
):
    """
    Vérifie l'état de tous les composants :
    PostgreSQL + pgvector, Ollama (Vulkan), GPU AMD BC-250 (ROCm embeddings).
    """
    import torch

    # DB
    try:
        await rag.check_db_health()
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    # Ollama
    try:
        await rag.check_ollama_health()
        ollama_status = f"ok ({settings.OLLAMA_MODEL})"
    except Exception as e:
        ollama_status = f"unavailable: {e}"

    # GPU AMD
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        gpu_status = f"ok — {props.name} | {props.total_memory // 1024**2} Mo GDDR6"
    else:
        gpu_status = "cpu-only (ROCm non détecté)"

    overall = "healthy" if db_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        version=settings.APP_VERSION,
        database=db_status,
        ollama=ollama_status,
        gpu=gpu_status,
        embedding_model=settings.EMBEDDING_MODEL,
    )


# ══════════════════════════════════════════════════════════════════════════════
# CHAT / RAG
# ══════════════════════════════════════════════════════════════════════════════

def _build_context(chunks: list[dict]) -> tuple[bool, str | None]:
    """Construit le contexte RAG à partir des chunks récupérés."""
    if not chunks:
        return False, None
    parts = []
    for i, c in enumerate(chunks, 1):
        src = c["metadata"].get("source", "inconnu")
        parts.append(f"[Source {i} — {src}]\n{c['text']}")
    return True, "\n\n---\n\n".join(parts)


def _build_sources(chunks: list[dict]) -> list[dict]:
    """Prépare la liste des sources pour la réponse."""
    return [{
        "rank": c["rank"],
        "text": c["text"][:200] + "..." if len(c["text"]) > 200 else c["text"],
        "score": round(c["score"], 4),
        "source": c["metadata"].get("source", "inconnu"),
    } for c in chunks]


async def _persist_conversation(record: ConversationRecord):
    """Persiste la conversation en base de données."""
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversations (
                    id, session_id, user_query, model_response,
                    rag_context, rag_sources, rag_used,
                    chunks_used, rag_threshold, response_time_ms,
                    model_name, metier
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                """,
                record.id, record.session_id, record.query, record.response, record.context,
                [{"text": c["text"], "score": c["score"],
                  "source": c["metadata"].get("source")} for c in record.chunks],
                record.rag_used, len(record.chunks), record.threshold, record.elapsed_ms,
                record.model_name, record.metier,
            )
    except Exception as e:
        logger.warning(f"⚠️  Persistance conversation échouée : {e}")


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(
    request: ChatRequest,
    rag: RAGEngine = Depends(get_rag_engine),
    _=Depends(verify_api_token),
):
    """
    Pipeline RAG complet :
    1. Embeddings de la query sur GPU RDNA2
    2. Recherche HNSW dans pgvector
    3. Génération Ollama avec contexte
    4. Persistance de la conversation en DB
    """
    t_start = time.monotonic()
    session_id = request.session_id or str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    top_k = request.top_k or settings.RAG_TOP_K
    threshold = request.threshold or settings.RAG_THRESHOLD

    chunks = await rag.retrieve(
        query=request.query, top_k=top_k,
        threshold=threshold, metier_filter=request.metier,
    )
    rag_used, context = _build_context(chunks)
    response_text = await rag.generate(
        query=request.query, context=context,
    )
    elapsed_ms = int((time.monotonic() - t_start) * 1000)

    _task = asyncio.create_task(_persist_conversation(
        ConversationRecord(
            id=conversation_id,
            session_id=session_id,
            query=request.query,
            response=response_text,
            context=context,
            chunks=chunks,
            rag_used=rag_used,
            threshold=threshold,
            elapsed_ms=elapsed_ms,
            metier=request.metier,
            model_name=settings.OLLAMA_MODEL,
        )
    ))
    _bg_tasks.add(_task)
    _task.add_done_callback(_bg_tasks.discard)

    return ChatResponse(
        response=response_text,
        sources=_build_sources(chunks),
        session_id=session_id,
        rag_used=rag_used,
        chunks_retrieved=len(chunks),
        response_time_ms=elapsed_ms,
        conversation_id=conversation_id,
    )


@app.post("/feedback", response_model=FeedbackResponse, tags=["Feedback"])
async def submit_feedback(
    payload: FeedbackRequest,
    _=Depends(verify_api_token),
):
    """
    Feedback humain sur une réponse (boucle d'amélioration humain-dans-la-boucle).

    Reçoit l'ID de conversation renvoyé par /chat et l'enregistre dans
    response_evaluations. Les réponses marquées is_golden=true alimentent
    ensuite fine_tuning/train.py (export SFT JSONL).
    """
    if payload.human_rating is not None and not (1 <= payload.human_rating <= 5):
        raise HTTPException(status_code=400, detail="human_rating doit être entre 1 et 5")
    pool = await get_db()
    async with pool.acquire() as conn:
        await save_feedback(
            conn,
            payload.conversation_id,
            payload.human_rating,
            payload.human_feedback,
            payload.is_golden,
        )
    return FeedbackResponse(
        status="ok",
        conversation_id=payload.conversation_id,
        is_golden=payload.is_golden,
    )


@app.get("/chat/history", tags=["Chat"])
async def get_history(
    session_id: str | None = None,
    metier: str | None = None,
    limit: int = 20,
    _=Depends(verify_api_token),
):
    """Récupère l'historique des conversations."""
    pool = await get_db()
    async with pool.acquire() as conn:
        if session_id:
            rows = await conn.fetch(
                """SELECT id, session_id, timestamp, user_query, model_response,
                          rag_used, chunks_used, response_time_ms, metier
                   FROM conversations
                   WHERE session_id = $1
                   ORDER BY timestamp DESC LIMIT $2""",
                session_id, limit
            )
        elif metier:
            rows = await conn.fetch(
                """SELECT id, session_id, timestamp, user_query, model_response,
                          rag_used, chunks_used, response_time_ms, metier
                   FROM conversations
                   WHERE metier = $1
                   ORDER BY timestamp DESC LIMIT $2""",
                metier, limit
            )
        else:
            rows = await conn.fetch(
                """SELECT id, session_id, timestamp, user_query, model_response,
                          rag_used, chunks_used, response_time_ms, metier
                   FROM conversations
                   ORDER BY timestamp DESC LIMIT $1""",
                limit
            )
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENTS
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/documents/upload", tags=["Documents"])
async def upload_document(
    file: UploadFile = File(...),
    metier: str | None = None,
    rag: RAGEngine = Depends(get_rag_engine),
    proc: DocumentProcessor = Depends(get_doc_processor),
    _=Depends(verify_api_token),
):
    """
    Upload, extraction et indexation d'un document.
    Formats supportés : PDF, TXT, MD, DOCX, PPTX, XLSX, MP3, MP4, WAV.
    """
    if metier and metier not in ("TSSR", "AIS", "DevOps"):
        raise HTTPException(
            status_code=400,
            detail="metier doit être : TSSR, AIS ou DevOps"
        )

    file_id = str(uuid.uuid4())

    try:
        file_path = await proc.save_file(file, file_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        chunks = await proc.process_document(file_path, file.filename)

        # Injection du filtre métier dans les métadonnées
        if metier:
            for c in chunks:
                c["metadata"]["metier"] = metier

        await rag.index_chunks(chunks, file_id, file.filename)

    except Exception as e:
        logger.error(f"❌ Erreur indexation {file.filename} : {e}")
        raise HTTPException(status_code=500, detail=f"Erreur d'indexation : {e}") from e

    return {
        "file_id": file_id,
        "filename": file.filename,
        "chunks_created": len(chunks),
        "metier": metier,
        "status": "indexed",
    }


@app.get("/documents/list", tags=["Documents"])
async def list_documents(
    _=Depends(verify_api_token),
):
    """Liste tous les documents indexés avec leur nombre de chunks."""
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT file_id, filename,
                      COUNT(*) AS chunks,
                      MIN(created_at) AS indexed_at,
                      MAX(metadata->>'metier') AS metier
               FROM rag_chunks
               GROUP BY file_id, filename
               ORDER BY indexed_at DESC"""
        )
    return [dict(r) for r in rows]


@app.delete("/documents/{file_id}", tags=["Documents"])
async def delete_document(
    file_id: str,
    _=Depends(verify_api_token),
):
    """Supprime un document et tous ses chunks de la base vectorielle."""
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "DELETE FROM rag_chunks WHERE file_id = $1 RETURNING id",
            file_id,
        )
        deleted = len(rows)
        # Suppression du fichier physique si présent
        upload_path = Path(settings.UPLOAD_DIR)
        for ext in (".pdf", ".txt", ".md", ".docx", ".pptx", ".xlsx",
                    ".mp3", ".mp4", ".wav"):
            f = upload_path / f"{file_id}{ext}"
            if f.exists():
                f.unlink()
                break

    return {"file_id": file_id, "chunks_deleted": deleted, "status": "deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# INDEXATION
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/indexing/status", tags=["Indexation"])
async def indexing_status(
    rag: RAGEngine = Depends(get_rag_engine),
    _=Depends(verify_api_token),
):
    """Statistiques de la collection RAG (total chunks, documents, backend)."""
    return await rag.get_collection_stats()


@app.post("/indexing/directory", tags=["Indexation"])
async def index_directory(
    directory: str,
    rag: RAGEngine = Depends(get_rag_engine),
    proc: DocumentProcessor = Depends(get_doc_processor),
    _=Depends(verify_api_token),
):
    """
    Indexe en parallèle tous les fichiers d'un répertoire.
    Utilise asyncio.TaskGroup (Python 3.13) pour le parallélisme.
    """
    try:
        stats = await proc.index_directory(directory, rag)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return stats


@app.post("/indexing/reset", tags=["Indexation"])
async def reset_collection(
    rag: RAGEngine = Depends(get_rag_engine),
    _=Depends(verify_api_token),
):
    """Vide entièrement la collection RAG (TRUNCATE). Action irréversible."""
    await rag.reset_collection()
    return {"status": "reset", "message": "Collection vidée (TRUNCATE + RESTART IDENTITY)"}
