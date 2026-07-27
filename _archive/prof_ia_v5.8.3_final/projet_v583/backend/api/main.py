"""
Prof IA v5.8.3 ALL-IN-ONE — Point d'entrée FastAPI (AMD BC-250 / Cyan Skillfish)
================================================================================
CHANGELOG v5.8.3 :
  [C1] PyTorch ROCm activé dans Dockerfile (GPU RDNA2 utilisé pour les embeddings)
  [C2] Port backend 8000 (externe = interne, plus simple — Frontend:3000 / Backend:8000)
  [C3] CORS : ajout de http://192.168.1.11:3000 et :8000 dans allow_origins
  [C4] Nouveaux endpoints de contrôle des services :
         GET  /services/status           → pastilles santé dashboard (Option A)
         POST /services/{name}/restart   → redémarrer un service (Option B)
         POST /services/{name}/stop      → arrêter un service
         POST /services/{name}/start     → démarrer un service

Architecture des endpoints :
  GET  /health                  — santé globale (PostgreSQL + ChromaDB + Ollama + GPU)
  GET  /services/status         — état de chaque conteneur Docker (running/stopped/...)
  POST /services/{name}/restart — redémarrer un service nommé
  POST /services/{name}/stop    — arrêter un service nommé
  POST /services/{name}/start   — démarrer un service nommé
  GET  /datasets/stats          — répartition par métier (ChromaDB)
  POST /documents/upload        — upload et indexation dans prof_ia_all
  GET  /documents/list          — liste des documents indexés
  DELETE /documents/{file_id}   — suppression d'un document
  GET  /indexing/status         — statistiques de la collection RAG
  POST /indexing/directory      — indexation d'un répertoire complet
  POST /indexing/reset          — reset complet ChromaDB
  POST /login                   — authentification (retourne token session 12h)
  POST /logout                  — invalider la session
  POST /chat                    — requête RAG (retrieval + génération)
  GET  /chat/history            — historique des conversations
  POST /chat/{id}/rate          — notation d'une conversation
  GET  /models/available        — modèles disponibles
  POST /models/switch           — changer de modèle LLM
"""

import time
import uuid
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from .config import get_settings
from .database import init_db, close_db, get_db
from .rag_engine import RAGEngine
from .document_processor import DocumentProcessor

settings = get_settings()

# ══════════════════════════════════════════════════════════════════════════════
# AUTHENTIFICATION LOCALE — Réseau 192.168.1.x isolé
# ══════════════════════════════════════════════════════════════════════════════

ALLOWED_CLIENT_IP = "192.168.1.16"
SERVER_IP          = "192.168.1.11"

API_USERNAME = "user"
API_PASSWORD = "user"

_active_sessions: dict = {}
SESSION_DURATION = 12 * 3600  # 12 heures

PUBLIC_PATHS = {"/health", "/login", "/docs", "/openapi.json", "/redoc"}

# ── Mapping nom service → nom conteneur Docker ─────────────────────────────────
# Utilisé par les endpoints /services/{name}/restart|stop|start
SERVICE_MAP = {
    "postgres":  "prof-ia-postgres-v58",
    "ollama":    "prof-ia-ollama-rocm",
    "backend":   "prof-ia-backend-v58",
    "frontend":  "prof-ia-frontend-v58",
}

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
    global _rag_engine, _doc_processor

    logger.info("🚀 Démarrage Prof IA v5.8.3 ALL-IN-ONE (AMD BC-250)...")

    await init_db()
    logger.info("✅ Base de données PostgreSQL initialisée")

    _rag_engine = RAGEngine(
        db_url=settings.DATABASE_URL,
        ollama_host=settings.OLLAMA_HOST,
        model_name=settings.OLLAMA_MODEL,
        embedding_model=settings.EMBEDDING_MODEL,
        chromadb_path=settings.CHROMADB_PATH,
    )
    await _rag_engine.initialize()
    logger.info("✅ RAG Engine v5.8.2 initialisé (ChromaDB ALL-IN-ONE)")

    _doc_processor = DocumentProcessor(upload_dir=settings.UPLOAD_DIR)
    logger.info("✅ Document Processor initialisé")
    logger.info(f"🟢 Prof IA v5.8.3 prêt — Frontend:3000 / Backend:8000")

    yield

    logger.info("🔴 Arrêt de Prof IA v5.8.2...")
    if _rag_engine:
        await _rag_engine.close()
    await close_db()
    logger.info("✅ Arrêt propre effectué")


# ── Application FastAPI ────────────────────────────────────────────────────────
app = FastAPI(
    title="Prof IA v5.8.3 ALL-IN-ONE (BC-250)",
    version="5.8.3",
    description="Système RAG optimisé AMD BC-250 (Cyan Skillfish / RDNA2)",
    lifespan=lifespan,
)


# ══════════════════════════════════════════════════════════════════════════════
# MIDDLEWARE 1 — IP WHITELIST + SESSION AUTH
# ══════════════════════════════════════════════════════════════════════════════
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """
    Authentification locale v5.8.2 :
      1. IP whitelist : 192.168.1.16 (client unique) ou 127.0.0.1 (Docker interne)
      2. Token de session valide (sauf /login, /health, /docs)
    """
    client_ip = request.client.host if request.client else "inconnu"
    path      = request.url.path
    method    = request.method

    # IPs autorisées : client connu + serveur lui-même + Docker bridge
    allowed_ips = {ALLOWED_CLIENT_IP, SERVER_IP, "127.0.0.1", "::1"}
    is_docker   = client_ip.startswith("172.")

    if client_ip not in allowed_ips and not is_docker:
        logger.warning(f"🚫 ACCÈS REFUSÉ — IP non autorisée : {client_ip} → {method} {path}")
        return JSONResponse(
            status_code=403,
            content={"detail": f"Accès refusé : IP {client_ip} non autorisée"}
        )

    if path in PUBLIC_PATHS:
        return await call_next(request)

    token = request.headers.get("X-Session-Token") or request.cookies.get("session_token")

    if not token or token not in _active_sessions:
        logger.warning(f"🔐 ACCÈS NON AUTHENTIFIÉ — {client_ip} → {method} {path}")
        return JSONResponse(
            status_code=401,
            content={"detail": "Non authentifié. POST /login avec {username, password}"}
        )

    session = _active_sessions[token]

    if time.time() - session["logged_at"] > SESSION_DURATION:
        del _active_sessions[token]
        return JSONResponse(
            status_code=401,
            content={"detail": "Session expirée. Reconnectez-vous via POST /login"}
        )

    logger.info(f"✅ {client_ip} ({session['username']}) → {method} {path}")
    return await call_next(request)


# [C3] CORS — origines autorisées corrigées v5.8.2
# Le navigateur charge le frontend depuis http://192.168.1.11:3000
# et envoie ses requêtes AJAX vers http://192.168.1.11:8000
# Ces deux origines DOIVENT être dans allow_origins pour que le navigateur accepte les réponses
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://192.168.1.16",
        "http://192.168.1.16:3000",
        "http://192.168.1.16:8000",
        "http://192.168.1.11:3000",   # [C3] AJOUT — frontend servi depuis le serveur
        "http://192.168.1.11:8000",   # [C3] AJOUT — backend accédé depuis serveur
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
# MODÈLES PYDANTIC
# ══════════════════════════════════════════════════════════════════════════════
class LoginRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    metier: Optional[str] = None
    top_k: Optional[int] = None
    threshold: Optional[float] = None
    system_prompt: Optional[str] = ""
    mode: str = "précis"

class ChatResponse(BaseModel):
    response: str
    sources: List[dict]
    session_id: str
    conversation_id: Optional[str] = None
    rag_used: bool
    chunks_retrieved: int
    response_time_ms: int
    model_used: str
    mode_used: str

class RatingRequest(BaseModel):
    rating: int

class ModelSwitchRequest(BaseModel):
    model_id: str

class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    ollama: str
    gpu: str
    embedding_model: str


# ══════════════════════════════════════════════════════════════════════════════
# AUTH — Login / Logout
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/login", tags=["Auth"])
async def login(request: Request, credentials: LoginRequest):
    """Authentification locale — user/user — session 12 heures."""
    client_ip = request.client.host if request.client else "inconnu"

    if credentials.username != API_USERNAME or credentials.password != API_PASSWORD:
        logger.warning(f"🔐 ÉCHEC LOGIN — {client_ip} | user='{credentials.username}'")
        raise HTTPException(status_code=401, detail="Identifiants incorrects")

    token = secrets.token_hex(32)
    _active_sessions[token] = {
        "username":  credentials.username,
        "ip":        client_ip,
        "logged_at": time.time(),
    }

    logger.info(
        f"🔑 LOGIN OK — {client_ip} | user='{credentials.username}' | "
        f"token={token[:8]}... | sessions_actives={len(_active_sessions)}"
    )

    return {
        "status":       "authenticated",
        "token":        token,
        "username":     credentials.username,
        "expires_in_h": 12,
    }


@app.post("/logout", tags=["Auth"])
async def logout(request: Request):
    """Invalide la session courante."""
    client_ip = request.client.host if request.client else "inconnu"
    token = request.headers.get("X-Session-Token") or request.cookies.get("session_token")

    if token and token in _active_sessions:
        session = _active_sessions.pop(token)
        logger.info(f"🚪 LOGOUT — {client_ip} | user='{session['username']}'")
        return {"status": "logged_out"}
    return {"status": "no_active_session"}


# ══════════════════════════════════════════════════════════════════════════════
# [C4] CONTRÔLE DES SERVICES DOCKER — Dashboard santé
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/services/status", tags=["Services"])
async def get_services_status():
    """
    [C4 — Option A] Retourne l'état de chaque conteneur Docker.

    Utilisé par le dashboard frontend pour afficher les pastilles de santé :
      - running  → pastille VERTE
      - exited   → pastille ROUGE
      - starting → pastille ORANGE
      - unknown  → pastille GRISE

    Exemple de réponse :
      {
        "postgres":  {"status": "running", "health": "healthy",  "indicator": "green"},
        "ollama":    {"status": "running", "health": "none",     "indicator": "green"},
        "backend":   {"status": "running", "health": "healthy",  "indicator": "green"},
        "frontend":  {"status": "running", "health": "none",     "indicator": "green"},
      }
    """
    try:
        import docker
        client = docker.from_env()
    except Exception as e:
        logger.error(f"❌ Docker SDK non accessible : {e}")
        return {"error": "Docker socket non accessible", "detail": str(e)}

    result = {}
    for service_name, container_name in SERVICE_MAP.items():
        try:
            container  = client.containers.get(container_name)
            status     = container.status          # running | exited | paused | restarting
            health     = "none"
            health_obj = container.attrs.get("State", {}).get("Health")
            if health_obj:
                health = health_obj.get("Status", "none")   # healthy | unhealthy | starting

            # Calcul de l'indicateur visuel
            if status == "running" and health in ("healthy", "none"):
                indicator = "green"
            elif status == "running" and health == "starting":
                indicator = "orange"
            elif status == "running" and health == "unhealthy":
                indicator = "orange"
            else:
                indicator = "red"

            result[service_name] = {
                "container": container_name,
                "status":    status,
                "health":    health,
                "indicator": indicator,
            }

        except docker.errors.NotFound:
            result[service_name] = {
                "container": container_name,
                "status":    "not_found",
                "health":    "unknown",
                "indicator": "red",
            }
        except Exception as e:
            result[service_name] = {
                "container": container_name,
                "status":    "error",
                "health":    str(e),
                "indicator": "red",
            }

    return result


@app.post("/services/{service_name}/restart", tags=["Services"])
async def restart_service(service_name: str):
    """
    [C4 — Option B] Redémarre un service Docker nommé.

    Équivalent de : docker compose restart <service>
    Services disponibles : postgres | ollama | backend | frontend

    Note : si vous redémarrez 'backend', cette requête ne recevra pas de réponse
    car le conteneur s'arrête pendant le redémarrage (c'est normal).
    """
    if service_name not in SERVICE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Service inconnu. Valeurs : {', '.join(SERVICE_MAP.keys())}"
        )

    container_name = SERVICE_MAP[service_name]

    try:
        import docker
        client    = docker.from_env()
        container = client.containers.get(container_name)
        container.restart(timeout=10)
        logger.info(f"🔄 Service redémarré : {service_name} ({container_name})")
        return {"status": "restarting", "service": service_name, "container": container_name}
    except Exception as e:
        logger.error(f"❌ Erreur restart {service_name} : {e}")
        raise HTTPException(status_code=500, detail=f"Erreur restart : {e}")


@app.post("/services/{service_name}/stop", tags=["Services"])
async def stop_service(service_name: str):
    """
    [C4 — Option B] Arrête un service Docker nommé.
    Équivalent de : docker compose stop <service>
    """
    if service_name not in SERVICE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Service inconnu. Valeurs : {', '.join(SERVICE_MAP.keys())}"
        )

    container_name = SERVICE_MAP[service_name]

    try:
        import docker
        client    = docker.from_env()
        container = client.containers.get(container_name)
        container.stop(timeout=10)
        logger.info(f"⏹️  Service arrêté : {service_name} ({container_name})")
        return {"status": "stopped", "service": service_name, "container": container_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur stop : {e}")


@app.post("/services/{service_name}/start", tags=["Services"])
async def start_service(service_name: str):
    """
    [C4 — Option B] Démarre un service Docker arrêté.
    Équivalent de : docker compose start <service>
    """
    if service_name not in SERVICE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Service inconnu. Valeurs : {', '.join(SERVICE_MAP.keys())}"
        )

    container_name = SERVICE_MAP[service_name]

    try:
        import docker
        client    = docker.from_env()
        container = client.containers.get(container_name)
        container.start()
        logger.info(f"▶️  Service démarré : {service_name} ({container_name})")
        return {"status": "started", "service": service_name, "container": container_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur start : {e}")


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
async def health_check(rag: RAGEngine = Depends(get_rag_engine)):
    """
    Vérifie l'état de tous les composants.
    Endpoint public (pas de token requis) — utilisé par les healthchecks Docker.
    """
    import torch

    try:
        await rag.check_db_health()
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    try:
        await rag.check_chroma_health()
        chroma_status = "ok"
    except Exception as e:
        chroma_status = f"error: {e}"

    try:
        await rag.check_ollama_health()
        ollama_status = f"ok ({settings.OLLAMA_MODEL})"
    except Exception as e:
        ollama_status = f"unavailable: {e}"

    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        gpu_status = f"ok — {props.name} | {props.total_memory // 1024**2} Mo GDDR6 (ROCm)"
    else:
        gpu_status = "cpu-only (ROCm non détecté — vérifier HSA_OVERRIDE_GFX_VERSION)"

    overall = "healthy" if db_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        version="5.8.3",
        database=f"postgres:{db_status} | chromadb:{chroma_status}",
        ollama=ollama_status,
        gpu=gpu_status,
        embedding_model=settings.EMBEDDING_MODEL,
    )


# ══════════════════════════════════════════════════════════════════════════════
# CHAT / RAG
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest, rag: RAGEngine = Depends(get_rag_engine)):
    """Pipeline RAG complet : retrieval ChromaDB + génération Ollama ROCm."""
    t_start = time.monotonic()
    session_id = request.session_id or str(uuid.uuid4())
    mode = request.mode if request.mode in ("précis", "explore", "synthèse") else "précis"

    if request.top_k:
        top_k = request.top_k
    elif mode == "synthèse":
        top_k = settings.RAG_TOP_K_SYNTHESIS
    elif mode == "explore":
        top_k = settings.RAG_TOP_K_EXPLORE
    else:
        top_k = settings.RAG_TOP_K

    threshold = request.threshold or settings.RAG_THRESHOLD

    logger.info(f"💬 Chat — mode={mode} | top_k={top_k} | modèle={settings.OLLAMA_MODEL}")

    chunks = await rag.retrieve(
        query=request.query,
        top_k=top_k,
        threshold=threshold,
        metier_filter=request.metier,
        mode=mode,
        mmr_lambda=settings.MMR_LAMBDA,
    )

    rag_used = len(chunks) > 0
    context  = None
    if rag_used:
        parts = []
        for i, c in enumerate(chunks, 1):
            src = c["metadata"].get("source", "inconnu")
            parts.append(f"[Source {i} — {src}]\n{c['text']}")
        context = "\n\n---\n\n".join(parts)

    response_text = await rag.generate(
        query=request.query,
        context=context,
        system_prompt=request.system_prompt or "",
        mode=mode,
    )

    elapsed_ms = int((time.monotonic() - t_start) * 1000)

    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversations (
                    session_id, user_query, model_response,
                    rag_context, rag_sources, rag_used,
                    chunks_used, rag_threshold, response_time_ms,
                    model_name, metier, query_mode
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                """,
                session_id, request.query, response_text,
                context,
                [{"text": c["text"], "score": c["score"],
                  "source": c["metadata"].get("source")} for c in chunks],
                rag_used, len(chunks), threshold, elapsed_ms,
                settings.OLLAMA_MODEL, request.metier, mode,
            )
    except Exception as e:
        logger.warning(f"⚠️  Persistance conversation échouée : {e}")

    conv_id = None
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            conv_id = await conn.fetchval(
                "SELECT id FROM conversations WHERE session_id=$1 ORDER BY timestamp DESC LIMIT 1",
                session_id
            )
    except Exception:
        pass

    return ChatResponse(
        response=response_text,
        sources=[{
            "rank":   c["rank"],
            "text":   c["text"][:200] + "..." if len(c["text"]) > 200 else c["text"],
            "score":  round(c["score"], 4),
            "source": c["metadata"].get("source", "inconnu"),
        } for c in chunks],
        session_id=session_id,
        conversation_id=str(conv_id) if conv_id else None,
        rag_used=rag_used,
        chunks_retrieved=len(chunks),
        response_time_ms=elapsed_ms,
        model_used=settings.OLLAMA_MODEL,
        mode_used=mode,
    )


@app.get("/chat/history", tags=["Chat"])
async def get_history(
    session_id: Optional[str] = None,
    metier: Optional[str] = None,
    limit: int = 20,
):
    pool = await get_db()
    async with pool.acquire() as conn:
        if session_id:
            rows = await conn.fetch(
                """SELECT id, session_id, timestamp, user_query, model_response,
                          rag_used, chunks_used, response_time_ms, metier
                   FROM conversations WHERE session_id = $1
                   ORDER BY timestamp DESC LIMIT $2""",
                session_id, limit
            )
        elif metier:
            rows = await conn.fetch(
                """SELECT id, session_id, timestamp, user_query, model_response,
                          rag_used, chunks_used, response_time_ms, metier
                   FROM conversations WHERE metier = $1
                   ORDER BY timestamp DESC LIMIT $2""",
                metier, limit
            )
        else:
            rows = await conn.fetch(
                """SELECT id, session_id, timestamp, user_query, model_response,
                          rag_used, chunks_used, response_time_ms, metier
                   FROM conversations ORDER BY timestamp DESC LIMIT $1""",
                limit
            )
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# MODÈLES
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/models/available", tags=["Modèles"])
async def get_available_models():
    return {
        "current_model": settings.OLLAMA_MODEL,
        "models": [
            {
                "id":          "mistral:7b-instruct-q4_K_M",
                "name":        "Mistral 7B",
                "description": "Rapide et précis — idéal pour questions directes",
                "vram_gb":     4.5,
                "latency":     "~3-5 secondes",
                "pull_cmd":    "ollama pull mistral:7b-instruct-q4_K_M",
                "active":      settings.OLLAMA_MODEL == "mistral:7b-instruct-q4_K_M",
            },
            {
                "id":          "deepseek-r1:7b",
                "name":        "DeepSeek R1 7B",
                "description": "Raisonnement étape par étape — analyse complexe",
                "vram_gb":     4.7,
                "latency":     "~8-15 secondes",
                "pull_cmd":    "ollama pull deepseek-r1:7b",
                "active":      settings.OLLAMA_MODEL == "deepseek-r1:7b",
            },
        ]
    }


@app.post("/models/switch", tags=["Modèles"])
async def switch_model(request: ModelSwitchRequest, rag: RAGEngine = Depends(get_rag_engine)):
    allowed = {"mistral:7b-instruct-q4_K_M", "deepseek-r1:7b"}
    if request.model_id not in allowed:
        raise HTTPException(status_code=400, detail=f"Modèle non supporté : {', '.join(allowed)}")
    old_model = rag.model_name
    rag.model_name = request.model_id
    settings.OLLAMA_MODEL = request.model_id
    logger.info(f"🔄 Modèle changé : {old_model} → {request.model_id}")
    return {"status": "switched", "old_model": old_model, "new_model": request.model_id}


# ══════════════════════════════════════════════════════════════════════════════
# NOTATION
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/chat/{conversation_id}/rate", tags=["Chat"])
async def rate_conversation(conversation_id: str, request: RatingRequest):
    if not (1 <= request.rating <= 5):
        raise HTTPException(status_code=400, detail="La note doit être entre 1 et 5")
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            result = await conn.fetchval(
                "UPDATE conversations SET user_rating = $1 WHERE id = $2::uuid RETURNING id",
                request.rating, conversation_id,
            )
        if result is None:
            raise HTTPException(status_code=404, detail="Conversation introuvable")
        return {
            "conversation_id":      conversation_id,
            "rating":               request.rating,
            "stars":                "⭐" * request.rating,
            "status":               "saved",
            "fine_tuning_eligible": request.rating >= 4,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/ratings/stats", tags=["Chat"])
async def get_ratings_stats():
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT user_rating, COUNT(*) AS count,
                   ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
            FROM conversations WHERE user_rating IS NOT NULL
            GROUP BY user_rating ORDER BY user_rating DESC
        """)
        total_rated   = await conn.fetchval("SELECT COUNT(*) FROM conversations WHERE user_rating IS NOT NULL")
        golden_count  = await conn.fetchval("SELECT COUNT(*) FROM conversations WHERE user_rating >= 4")
    return {
        "total_rated":       total_rated,
        "golden_examples":   golden_count,
        "fine_tuning_ready": golden_count >= 50,
        "distribution":      [dict(r) for r in rows],
    }


# ══════════════════════════════════════════════════════════════════════════════
# DATASET FINE-TUNING
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/dataset/stats", tags=["Dataset"])
async def get_dataset_stats_endpoint():
    from .database import get_dataset_stats
    return await get_dataset_stats()


@app.post("/dataset/export", tags=["Dataset"])
async def export_dataset(min_rating: int = 4, format: str = "jsonl"):
    from .database import get_high_rated_conversations
    import json
    from datetime import datetime

    conversations = await get_high_rated_conversations(min_rating)
    if not conversations:
        return {"status": "error", "message": f"Aucune conversation avec rating >= {min_rating}"}

    dataset_dir = Path("/app/fine_tuning/dataset")
    dataset_dir.mkdir(parents=True, exist_ok=True)
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename    = f"dataset_rating{min_rating}_{timestamp}.{format}"
    filepath    = dataset_dir / filename

    if format == "jsonl":
        with open(filepath, "w", encoding="utf-8") as f:
            for conv in conversations:
                entry = {
                    "messages": [
                        {"role": "system",
                         "content": f"Tu es un assistant IA spécialisé en {conv['metier'] or 'formation professionnelle'}."},
                        {"role": "user",      "content": conv["query"]},
                        {"role": "assistant", "content": conv["response"]},
                    ],
                    "metadata": {
                        "conversation_id": conv["id"],
                        "metier":  conv["metier"],
                        "rating":  conv["rating"],
                        "model":   conv["model_used"],
                        "mode":    conv["query_mode"],
                        "timestamp": conv["timestamp"].isoformat() if conv["timestamp"] else None,
                    }
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    elif format == "csv":
        import csv
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id","query","response","metier","rating","model_used","timestamp"])
            writer.writeheader()
            writer.writerows(conversations)

    return {"status": "success", "count": len(conversations), "filepath": str(filepath), "filename": filename}


# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENTS
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/documents/upload", tags=["Documents"])
async def upload_document(
    file: UploadFile = File(...),
    metier: Optional[str] = None,
    rag: RAGEngine = Depends(get_rag_engine),
    proc: DocumentProcessor = Depends(get_doc_processor),
):
    if metier and metier not in ("TSSR", "AIS", "DevOps"):
        raise HTTPException(status_code=400, detail="metier doit être : TSSR, AIS ou DevOps")

    file_id = str(uuid.uuid4())
    try:
        file_path = await proc.save_file(file, file_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        chunks = await proc.process_document(file_path, file.filename)
        if metier:
            for c in chunks:
                c["metadata"]["metier"] = metier
        await rag.index_chunks(chunks, file_id, file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'indexation : {e}")

    return {"file_id": file_id, "filename": file.filename, "chunks_created": len(chunks), "metier": metier, "status": "indexed"}


@app.get("/documents/list", tags=["Documents"])
async def list_documents(rag: RAGEngine = Depends(get_rag_engine)):
    if rag._collection is None:
        return []
    try:
        result = rag._collection.get(where={"source": {"$eq": "upload"}}, include=["metadatas"])
    except Exception:
        return []
    docs: dict = {}
    for meta in (result.get("metadatas") or []):
        fid = meta.get("file_id", "inconnu")
        if fid not in docs:
            docs[fid] = {"file_id": fid, "filename": meta.get("filename","inconnu"), "chunks": 0, "metier": meta.get("metier","upload")}
        docs[fid]["chunks"] += 1
    return list(docs.values())


@app.delete("/documents/{file_id}", tags=["Documents"])
async def delete_document(file_id: str, rag: RAGEngine = Depends(get_rag_engine)):
    if rag._collection is None:
        raise HTTPException(status_code=503, detail="Collection ChromaDB non initialisée")
    try:
        existing    = rag._collection.get(where={"file_id": {"$eq": file_id}}, include=["metadatas"])
        chunks_count= len(existing.get("ids") or [])
    except Exception:
        chunks_count = 0
    if chunks_count == 0:
        raise HTTPException(status_code=404, detail=f"Document '{file_id}' introuvable")
    try:
        rag._collection.delete(where={"file_id": {"$eq": file_id}})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur suppression : {e}")
    upload_path = Path(settings.UPLOAD_DIR)
    for f in upload_path.rglob(f"{file_id}.*"):
        if f.is_file():
            f.unlink()
            break
    return {"file_id": file_id, "chunks_deleted": chunks_count, "status": "deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# INDEXATION
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/datasets/stats", tags=["Indexation"])
async def get_datasets_stats(rag: RAGEngine = Depends(get_rag_engine)):
    return await rag.get_datasets_stats()


@app.get("/indexing/status", tags=["Indexation"])
async def indexing_status(rag: RAGEngine = Depends(get_rag_engine)):
    return await rag.get_collection_stats()


@app.post("/indexing/directory", tags=["Indexation"])
async def index_directory(directory: str, rag: RAGEngine = Depends(get_rag_engine), proc: DocumentProcessor = Depends(get_doc_processor)):
    try:
        return await proc.index_directory(directory, rag)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/indexing/reset", tags=["Indexation"])
async def reset_collection(confirm: str, rag: RAGEngine = Depends(get_rag_engine)):
    """
    ⚠️ Vide entièrement ChromaDB. Irréversible.
    Paramètre requis : confirm=RESET_CONFIRMED
    """
    if confirm != "RESET_CONFIRMED":
        raise HTTPException(status_code=400, detail="Ajouter ?confirm=RESET_CONFIRMED pour confirmer l'effacement")
    await rag.reset_collection()
    return {"status": "reset", "message": "Collection 'prof_ia_all' vidée"}
