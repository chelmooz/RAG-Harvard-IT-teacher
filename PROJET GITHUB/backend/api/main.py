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
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from fastapi import FastAPI, File, HTTPException, UploadFile, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from dataclasses import dataclass
from pydantic import BaseModel

from .config import get_settings


@dataclass(slots=True)
class ConversationRecord:
    """Regroupe les données de conversation pour _persist_conversation (SRP)."""
    session_id: str
    query: str
    response: str
    context: Optional[str]
    chunks: List[dict]
    rag_used: bool
    threshold: float
    elapsed_ms: int
    metier: Optional[str]
    model_name: str = ""
from .database import init_db, close_db, get_db
from .rag_engine import RAGEngine
from .document_processor import DocumentProcessor

settings = get_settings()

# ── Dataclass pour _persist_conversation (SRP) ──────────────────────────────────


@dataclass
class ConversationRecord:
    """Regroupe les données de conversation pour _persist_conversation (SRP)."""
    session_id: str
    query: str
    response: str
    context: Optional[str]
    chunks: List[Dict[str, Any]]
    rag_used: bool
    threshold: float
    elapsed_ms: int
    metier: Optional[str]
    model_name: str

# ── Authentification API ──────────────────────────────────────────────────────
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


async def verify_api_token(request: Request):
    """Vérifie le token API dans le header Authorization.
    Les endpoints publics sont exemptés. Le token est comparé à settings.API_TOKEN."""
    if request.url.path in PUBLIC_PATHS:
        return True
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {settings.API_TOKEN}":
        return True
    raise HTTPException(
        status_code=401,
        detail="Token API invalide ou manquant. Ajoutez Authorization: Bearer <token>"
    )


# ── Instances globales ─────────────────────────────────────────────────────────
_rag_engine: Optional[RAGEngine] = None
_doc_processor: Optional[DocumentProcessor] = None


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

    # FIX BUG#4 : init_db() appelle maintenant register_vector(pool)
    # Le codec pgvector est enregistré avant toute requête vectorielle.
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

# CORS — toutes origines autorisées (réseau local isolé, LAN derrière pare-feu)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # credentials=False obligatoire avec allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
# MODÈLES PYDANTIC
# ══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    metier: Optional[str] = None          # Filtre : "TSSR" | "AIS" | "DevOps"
    top_k: Optional[int] = None
    threshold: Optional[float] = None


class ChatResponse(BaseModel):
    response: str
    sources: List[dict]
    session_id: str
    rag_used: bool
    chunks_retrieved: int
    response_time_ms: int


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    ollama: str
    gpu: str
    embedding_model: str


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
    PostgreSQL + pgvector, Ollama ROCm, GPU AMD BC-250.
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

def _build_context(chunks: List[dict]) -> tuple[bool, Optional[str]]:
    """Construit le contexte RAG à partir des chunks récupérés."""
    if not chunks:
        return False, None
    parts = []
    for i, c in enumerate(chunks, 1):
        src = c["metadata"].get("source", "inconnu")
        parts.append(f"[Source {i} — {src}]\n{c['text']}")
    return True, "\n\n---\n\n".join(parts)


def _build_sources(chunks: List[dict]) -> List[dict]:
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
                    session_id, user_query, model_response,
                    rag_context, rag_sources, rag_used,
                    chunks_used, rag_threshold, response_time_ms,
                    model_name, metier
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                """,
                record.session_id, record.query, record.response, record.context,
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

    asyncio.create_task(_persist_conversation(
        ConversationRecord(
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

    return ChatResponse(
        response=response_text,
        sources=_build_sources(chunks),
        session_id=session_id,
        rag_used=rag_used,
        chunks_retrieved=len(chunks),
        response_time_ms=elapsed_ms,
    )


@app.get("/chat/history", tags=["Chat"])
async def get_history(
    session_id: Optional[str] = None,
    metier: Optional[str] = None,
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
    metier: Optional[str] = None,
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
        raise HTTPException(status_code=400, detail=str(e))

    try:
        chunks = await proc.process_document(file_path, file.filename)

        # Injection du filtre métier dans les métadonnées
        if metier:
            for c in chunks:
                c["metadata"]["metier"] = metier

        await rag.index_chunks(chunks, file_id, file.filename)

    except Exception as e:
        logger.error(f"❌ Erreur indexation {file.filename} : {e}")
        raise HTTPException(status_code=500, detail=f"Erreur d'indexation : {e}")

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
        deleted = await conn.fetchval(
            "DELETE FROM rag_chunks WHERE file_id = $1 RETURNING COUNT(*)",
            file_id
        )
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
        raise HTTPException(status_code=400, detail=str(e))
    return stats


@app.post("/indexing/reset", tags=["Indexation"])
async def reset_collection(
    rag: RAGEngine = Depends(get_rag_engine),
    _=Depends(verify_api_token),
):
    """Vide entièrement la collection RAG (TRUNCATE). Action irréversible."""
    await rag.reset_collection()
    return {"status": "reset", "message": "Collection vidée (TRUNCATE + RESTART IDENTITY)"}
