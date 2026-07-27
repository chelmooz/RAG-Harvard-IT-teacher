"""
Configuration v6.0 — Prof IA (AMD BC-250 / Cyan Skillfish)
============================================================
Calibrée pour :
  - 16 Go GDDR6 unifiée (amdgpu.gttsize=12288 → 12 Go VRAM disponibles)
  - 6 cœurs Zen 2 / 24 CUs RDNA2
  - ROCm 7.2 + PyTorch 2.11+ / Python 3.13

CORRECTIFS v6.0 :
  - pg18    : PostgreSQL 18.2 (cohérent avec toute la documentation)
  - Ports   : tout ouvert — réseau local isolé (LAN derrière pare-feu)
  - CORS    : toutes origines autorisées (*)
  - JWT     : validation assouplie — token utilisé pour l'auth GitHub datasets
CORRECTIFS v6.0 CONSERVÉS :
  - FIX BUG#1 : main.py créé
  - FIX BUG#2 : Dockerfiles créés
  - FIX BUG#3 : nginx.conf créé
  - FIX BUG#4 : register_vector() dans database.py
  - FIX BUG#5 : num_gpu=-1 dans rag_engine.py
"""

import os
import secrets
from functools import lru_cache
from pydantic_settings import BaseSettings
from loguru import logger


class Settings(BaseSettings):

    # ── Application ─────────────────────────────────────────────
    APP_NAME:    str  = "Prof IA v6.0 (BC-250)"
    APP_VERSION: str  = "6.0.0"
    DEBUG:       bool = False

    # ── PostgreSQL (unique backend : conversations + vecteurs) ──
    # pgvector remplace ChromaDB — un seul moteur, latence ~1-3 ms
    # OBLIGATOIRE : définir DATABASE_URL dans .env
    # Exemple : postgresql://user:password@localhost:5432/prof_ia_v5
    DATABASE_URL: str = ""

    # ── Ollama ───────────────────────────────────────────────────
    OLLAMA_HOST:  str = "http://localhost:11434"
    # Q4_K_M = 4,5 Go → laisse ~7,5 Go pour embeddings + KV-cache
    OLLAMA_MODEL: str = "mistral:7b-instruct-q4_K_M"

    # ── ROCm / AMD BC-250 ────────────────────────────────────────
    HSA_OVERRIDE_GFX_VERSION: str = "10.1.3"  # Cyan Skillfish → gfx1013
    AMD_GTT_SIZE_MB:          int = 12288      # = amdgpu.gttsize (paramètre kernel)
    AMD_ZEN2_CORES:           int = 6
    AMD_RDNA2_CUS:            int = 24

    # ── RAG (pgvector) ───────────────────────────────────────────
    RAG_THRESHOLD:  float = 0.72  # seuil de similarité cosine
    RAG_TOP_K:      int   = 5
    CHUNK_SIZE:     int   = 400   # chars — plus dense = meilleur recall HNSW
    CHUNK_OVERLAP:  int   = 80    # recouvrement pour préserver le contexte

    # ── Embeddings ───────────────────────────────────────────────
    EMBEDDING_MODEL:      str = (
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    )
    EMBEDDING_BATCH_SIZE: int = 64  # optimal pour 24 CUs RDNA2

    # ── Fine-tuning & Logging ────────────────────────────────────
    ENABLE_LOGGING:   bool  = True
    AUTO_EVALUATE:    bool  = True
    GOLDEN_THRESHOLD: float = 0.85

    # ── Sécurité ─────────────────────────────────────────────────
    # CLÉ OBLIGATOIRE en production : définir JWT_SECRET dans .env
    # Génération : python -c "import secrets; print(secrets.token_urlsafe(32))"
    # Par défaut : aléatoire (changé à chaque redémarrage si .env absent).
    JWT_SECRET:   str = ""
    # Token API pour authentifier les requêtes frontend
    # Doit être identique côté client (REACT_APP_API_TOKEN)
    # Par défaut : identique à JWT_SECRET si non défini séparément
    API_TOKEN:    str = ""
    # Toutes origines autorisées — usage LAN uniquement
    CORS_ORIGINS: str = "*"

    # ── Chemins ──────────────────────────────────────────────────
    UPLOAD_DIR: str = "/app/data/uploads"
    MODELS_DIR: str = "/app/models"
    LOGS_DIR:   str = "/app/data/logs"

    # v6.0 : validateur JWT supprimé — token libre pour auth GitHub datasets

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """
    Retourne les settings en singleton (lru_cache).

    Injecte les variables ROCm dans l'environnement process si non définies,
    AVANT que torch soit importé ailleurs dans le code.
    Note : lru_cache garantit que os.environ.setdefault n'est appelé qu'une fois
    — correct en production, à désactiver dans les tests unitaires si nécessaire.
    """
    s = Settings()

    if not s.JWT_SECRET:
        s.JWT_SECRET = secrets.token_urlsafe(32)
        logger.warning(
            "⚠️  JWT_SECRET non défini dans .env — clé aléatoire générée. "
            "Les sessions seront invalidées au redémarrage. "
            "Ajoutez JWT_SECRET=<votre_clé> dans .env pour la persistance."
        )

    if not s.DATABASE_URL:
        raise ValueError(
            "DATABASE_URL obligatoire dans .env. "
            "Exemple : DATABASE_URL=postgresql://user:password@localhost:5432/prof_ia_v5"
        )

    if not s.API_TOKEN:
        s.API_TOKEN = s.JWT_SECRET
        if not s.API_TOKEN:
            s.API_TOKEN = secrets.token_urlsafe(32)
            logger.warning(
                "⚠️  API_TOKEN non défini dans .env — clé aléatoire générée. "
                "Ajoutez API_TOKEN=<votre_clé> dans .env pour la persistance."
            )

    if s.CORS_ORIGINS == "*" and not s.DEBUG:
        logger.warning(
            "⚠️  CORS_ORIGINS='*' en mode non DEBUG — restreignez les origines "
            "dans .env (ex: CORS_ORIGINS=http://localhost:3000) en production."
        )

    os.environ.setdefault("HSA_OVERRIDE_GFX_VERSION", s.HSA_OVERRIDE_GFX_VERSION)
    os.environ.setdefault(
        "PYTORCH_HIP_ALLOC_CONF",
        f"max_split_size_mb:{s.AMD_GTT_SIZE_MB // s.AMD_RDNA2_CUS}"
    )
    return s
