"""
Configuration v5.8 ALL-IN-ONE — Prof IA (AMD BC-250 / Cyan Skillfish)
======================================================================
Calibrée pour :
  - 16 Go GDDR6 unifiée (amdgpu.gttsize=12288 → 12 Go VRAM disponibles)
  - 6 cœurs Zen 2 / 24 CUs RDNA2
  - ROCm 7.2 + PyTorch 2.11+ / Python 3.13

Architecture v5.8 ALL-IN-ONE :
  - Backend vectoriel RAG : ChromaDB (collection prof_ia_all)
  - Modèle embeddings     : all-MiniLM-L6-v2 (384d) — stable BC-250
                            DOIT correspondre à import_datasets.py
  - CHROMADB_PATH         : volume copié via WinSCP sur le BC-250
  - PostgreSQL            : conversations, ratings, dataset export

Modes RAG disponibles :
  précis   — top-5 cosine classique                     (~0.5s retrieval)
  explore  — top-12 + MMR 70/30 pertinence/diversité    (~1.5s retrieval)
  synthèse — Multi-Query + top-20 + MMR exhaustif       (~4-6s retrieval)

Modèles LLM supportés :
  mistral:7b-instruct-q4_K_M   (~4.5 Go VRAM)
  deepseek-r1:7b               (~4.7 Go VRAM)
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    # ── Application ─────────────────────────────────────────────
    APP_NAME:    str  = "Prof IA v5.8.3 ALL-IN-ONE (BC-250)"
    APP_VERSION: str  = "5.8.3"
    DEBUG:       bool = False

    # ── PostgreSQL ──────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql://REDACTED_USER@localhost:5432/prof_ia_v5"
    )

    # ── Ollama ───────────────────────────────────────────────────
    OLLAMA_HOST:  str = "http://localhost:11434"
    # Modèle actif — supportés : mistral:7b-instruct-q4_K_M | deepseek-r1:7b
    # Q4_K_M ~4.5 Go | DeepSeek R1 7B Q4 ~4.7 Go → marge VRAM OK sur BC-250
    OLLAMA_MODEL: str = "mistral:7b-instruct-q4_K_M"

    # ── ROCm / AMD BC-250 ────────────────────────────────────────
    HSA_OVERRIDE_GFX_VERSION: str = "10.1.3"
    AMD_GTT_SIZE_MB:          int = 12288
    AMD_ZEN2_CORES:           int = 6
    AMD_RDNA2_CUS:            int = 24

    # ── RAG — Mode PRÉCIS (défaut) ───────────────────────────────
    # Rapide, top-5 meilleurs chunks. Idéal questions simples.
    RAG_THRESHOLD:  float = 0.72
    RAG_TOP_K:      int   = 5
    CHUNK_SIZE:     int   = 400
    CHUNK_OVERLAP:  int   = 80

    # ── RAG — Mode EXPLORE ───────────────────────────────────────
    # MMR 12 chunks : 70% pertinence / 30% diversité.
    # Évite la répétition pour des réponses plus riches.
    RAG_TOP_K_EXPLORE:   int   = 12
    MMR_LAMBDA:          float = 0.7
    NUM_CTX_EXPLORE:     int   = 8192

    # ── RAG — Mode SYNTHÈSE ──────────────────────────────────────
    # Multi-Query + MMR 20 chunks. Exploite le grand budget token.
    # Génère 3 sous-requêtes pour une couverture maximale.
    RAG_TOP_K_SYNTHESIS: int  = 20
    MULTI_QUERY_COUNT:   int  = 3
    MULTI_QUERY_ENABLED: bool = True
    NUM_CTX_SYNTHESIS:   int  = 16384

    # ── Embeddings ───────────────────────────────────────────────
    # MIGRATION v5.8 : all-MiniLM-L6-v2 (384d) remplace paraphrase-multilingual
    # DOIT correspondre au modèle utilisé dans import_datasets.py
    # 384d vs 768d : 2× moins de VRAM → plus stable sur 16 GB unifiée BC-250
    EMBEDDING_MODEL:      str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_BATCH_SIZE: int = 32          # AMD BC-250 : 32 safe (64 risque OOM)

    # ── ChromaDB (ALL-IN-ONE v5.8) ───────────────────────────────
    # Chemin absolu dans le container Docker (volume monté depuis l'hôte)
    # Pré-indexé par import_datasets.py, copié via WinSCP sur le BC-250
    CHROMADB_PATH: str = "/app/chromadb_data"

    # ── Fine-tuning & Logging ────────────────────────────────────
    ENABLE_LOGGING:   bool  = True
    AUTO_EVALUATE:    bool  = True
    GOLDEN_THRESHOLD: float = 0.85

    # ── Sécurité ─────────────────────────────────────────────────
    JWT_SECRET:   str = "user"
    CORS_ORIGINS: str = "*"

    # ── Chemins ──────────────────────────────────────────────────
    UPLOAD_DIR: str = "/app/data/uploads"
    MODELS_DIR: str = "/app/models"
    LOGS_DIR:   str = "/app/data/logs"

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    s = Settings()
    os.environ.setdefault("HSA_OVERRIDE_GFX_VERSION", s.HSA_OVERRIDE_GFX_VERSION)
    os.environ.setdefault(
        "PYTORCH_HIP_ALLOC_CONF",
        f"max_split_size_mb:{s.AMD_GTT_SIZE_MB // s.AMD_RDNA2_CUS}"
    )
    return s
