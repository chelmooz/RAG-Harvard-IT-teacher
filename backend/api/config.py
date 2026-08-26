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
  - JWT     : aucun JWT émis — API_TOKEN sert uniquement à sécuriser l'API locale (pas d'accès GitHub)
CORRECTIFS v6.0 CONSERVÉS :
  - FIX BUG#1 : main.py créé
  - FIX BUG#2 : Dockerfiles créés
  - FIX BUG#3 : nginx.conf créé
  - FIX BUG#4 : register_vector() dans database.py
  - FIX BUG#5 : num_gpu=99 (toutes les couches GPU) dans rag_engine.py
  - FIX BUG#6 : JWT_SECRET renommé API_TOKEN_SOURCE (pas de JWT émis)
"""

import os
import secrets
from functools import lru_cache

from loguru import logger
from pydantic_settings import BaseSettings


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
    # Défaut : localhost pour dev local ; en Docker, injecté via docker-compose.yml
    OLLAMA_HOST:  str = "http://localhost:11434"
    # Qwen3-14B Q4_K_M (~9,3 Go) — remplace Mistral 7B (2023, obsolète).
    # Laisse ~2,7 Go de marge sur le budget 12 Go (AMD_GTT_SIZE_MB) pour le
    # KV-cache : contexte à garder modeste (RAG_TOP_K=5, chunks courts).
    # Qwen3 supporte le mode "thinking" — désactivé par défaut pour un RAG
    # factuel (ajouter /no_think au prompt système si besoin de le forcer).
    OLLAMA_MODEL: str = "qwen3:14b"

    # ── ROCm / AMD BC-250 ────────────────────────────────────────
    HSA_OVERRIDE_GFX_VERSION: str = "10.1.3"  # Cyan Skillfish → gfx1013
    # Budget LOGIQUE utilisé par l'appli (PYTORCH_HIP_ALLOC_CONF). Le vrai
    # plafond kernel est posé via ttm.pages_limit=3014656 (Bazzite :
    # `rpm-ostree kargs --append-if-missing="ttm.pages_limit=3014656"`) +
    # UMA_SIZE=512 Mo (CMOS bc250memcfg) → split serveur 12 Go GPU / 4 Go CPU
    # (cf. install.sh étape 3/9 et vault/docs/superpowers/specs/
    # 2026-08-26-bc250-bazzite-deployment.md). Le triplet
    # gttsize=14750/pages_limit/page_pool_size=3959290 (~15 Go) est ÉVITÉ :
    # il pomperait la RAM CPU sur un système unifié 16 Go.
    AMD_GTT_SIZE_MB:          int = 12288
    # 24 = stock (16 CUs fusionnés en firmware). Après déblocage 40 CU
    # (scripts/unlock-40cu.sh, cf. install.sh étape 9/9), passer à 40
    # dans .env — NE JAMAIS mettre 40 ici sans avoir vérifié au préalable
    # `sudo dmesg | grep active_cu_number` (doit afficher 40, pas 24).
    AMD_RDNA2_CUS:            int = 24
    # true uniquement si le module amdgpu patché (bc250-40cu-unlock) est
    # chargé ET vérifié via dmesg. Sert à afficher un avertissement cohérent
    # au démarrage — ne modifie aucun registre matériel à lui seul.
    AMD_CU_UNLOCK_APPLIED:    bool = False

    # ── RAG (pgvector) ───────────────────────────────────────────
    RAG_THRESHOLD:  float = 0.72  # seuil de similarité cosine
    RAG_TOP_K:      int   = 5
    CHUNK_SIZE:     int   = 400   # chars — plus dense = meilleur recall HNSW
    CHUNK_OVERLAP:  int   = 80    # recouvrement pour préserver le contexte

    # ── Embeddings ───────────────────────────────────────────────
    # BGE-M3 (BAAI, Apache 2.0) — remplace paraphrase-multilingual-mpnet
    # (2021, obsolète sur MTEB 2026). Meilleur choix local pour retrieval FR.
    # ⚠️ Dimension 1024 (vs 768 avant) — cf. database.py vector(1024) et
    # rag_engine.py. Changement de modèle = changement d'espace vectoriel :
    # TOUS les documents existants doivent être ré-indexés, un simple
    # redimensionnement de colonne ne suffit pas (vecteurs incompatibles).
    EMBEDDING_MODEL:      str = "BAAI/bge-m3"
    EMBEDDING_BATCH_SIZE: int = 64  # optimal pour 24 CUs RDNA2

    # ── Fine-tuning & Logging ────────────────────────────────────
    ENABLE_LOGGING:   bool  = True
    # NOTE : l'auto-scoring (LLM-juge) n'est PAS encore câblé dans v6.0.
    # AUTO_EVALUATE=False => aucune note automatique n'est générée ; le
    # marquage is_golden repose uniquement sur le feedback humain via POST
    # /feedback. Le job d'auto-scoring est un développement futur (voir README §7).
    AUTO_EVALUATE:    bool  = False
    GOLDEN_THRESHOLD: float = 0.85

# ── Sécurité ─────────────────────────────────────────────────
    # Clé source pour générer API_TOKEN si non défini explicitement.
    # NOM IMPORTANT : bien que nommée JWT_SECRET, elle n'est PAS utilisée
    # pour signer/vérifier des JWT (aucun JWT n'est émis). Elle sert
    # uniquement de fallback aléatoire pour API_TOKEN (Bearer token statique).
    # Génération : python -c "import secrets; print(secrets.token_urlsafe(32))"
    # Par défaut : aléatoire (changée à chaque redémarrage si .env absent).
    API_TOKEN_SOURCE:   str = ""
    # Token API pour authentifier les requêtes frontend (Bearer token statique)
    # Doit être identique côté client (REACT_APP_API_TOKEN)
    # Par défaut : identique à API_TOKEN_SOURCE si non défini séparément
    API_TOKEN:    str = ""
    # Défaut restreint (localhost) — en prod, listez les origines exactes dans .env
    # (ex: CORS_ORIGINS=http://localhost:3000,http://192.168.1.11:3000).
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

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


@lru_cache
def get_settings() -> Settings:
    """
    Retourne les settings en singleton (lru_cache).

    Injecte les variables ROCm dans l'environnement process si non définies,
    AVANT que torch soit importé ailleurs dans le code.
    Note : lru_cache garantit que os.environ.setdefault n'est appelé qu'une fois
    — correct en production, à désactiver dans les tests unitaires si nécessaire.
    """
    s = Settings()

    _validate_token_source(s)
    _validate_database_url(s)
    _validate_api_token(s)
    _validate_cors(s)
    _validate_amd_cus(s)
    _inject_rocm_env(s)
    return s


def _validate_token_source(s: Settings) -> None:
    if not s.API_TOKEN_SOURCE:
        s.API_TOKEN_SOURCE = secrets.token_urlsafe(32)
        logger.warning(
            "⚠️  API_TOKEN_SOURCE non défini dans .env — clé aléatoire générée. "
            "Les sessions seront invalidées au redémarrage. "
            "Ajoutez API_TOKEN_SOURCE=<votre_clé> dans .env pour la persistance."
        )


def _validate_database_url(s: Settings) -> None:
    if not s.DATABASE_URL:
        raise ValueError(
            "DATABASE_URL obligatoire dans .env. "
            "Exemple : DATABASE_URL=postgresql://user:password@localhost:5432/prof_ia_v5"
        )


def _validate_api_token(s: Settings) -> None:
    if not s.API_TOKEN:
        s.API_TOKEN = s.API_TOKEN_SOURCE
        if not s.API_TOKEN:
            s.API_TOKEN = secrets.token_urlsafe(32)
            logger.warning(
                "⚠️  API_TOKEN non défini dans .env — clé aléatoire générée. "
                "Ajoutez API_TOKEN=<votre_clé> dans .env pour la persistance."
            )


def _validate_cors(s: Settings) -> None:
    if s.CORS_ORIGINS == "*" and not s.DEBUG:
        logger.warning(
            "⚠️  CORS_ORIGINS='*' en mode non DEBUG — restreignez les origines "
            "dans .env (ex: CORS_ORIGINS=http://localhost:3000) en production."
        )


def _validate_amd_cus(s: Settings) -> None:
    if s.AMD_RDNA2_CUS not in (24, 40):
        logger.warning(
            f"⚠️  AMD_RDNA2_CUS={s.AMD_RDNA2_CUS} inhabituel (24=stock, 40=débloqué). "
            "Vérifiez votre .env."
        )
    if s.AMD_RDNA2_CUS == 40 and not s.AMD_CU_UNLOCK_APPLIED:
        logger.warning(
            "⚠️  AMD_RDNA2_CUS=40 mais AMD_CU_UNLOCK_APPLIED=False — "
            "si le module amdgpu patché (bc250-40cu-unlock) n'est pas chargé, "
            "cette valeur est juste un mensonge de config qui fausse "
            "PYTORCH_HIP_ALLOC_CONF et EMBEDDING_BATCH_SIZE. "
            "Vérifiez avec : sudo dmesg | grep active_cu_number"
        )
    if s.AMD_RDNA2_CUS == 24 and s.AMD_CU_UNLOCK_APPLIED:
        logger.warning(
            "⚠️  AMD_CU_UNLOCK_APPLIED=True mais AMD_RDNA2_CUS=24 — "
            "mettez AMD_RDNA2_CUS=40 dans .env pour que le calcul mémoire en profite."
        )


def _inject_rocm_env(s: Settings) -> None:
    os.environ.setdefault("HSA_OVERRIDE_GFX_VERSION", s.HSA_OVERRIDE_GFX_VERSION)
    os.environ.setdefault(
        "PYTORCH_HIP_ALLOC_CONF",
        f"max_split_size_mb:{s.AMD_GTT_SIZE_MB // s.AMD_RDNA2_CUS}"
    )
