"""
Configuration v1.4 — Prof IA (BC-250 / BGE-M3 CPU + llama.cpp hôte Vulkan)
========================================================================
Calibrée pour :
  - 16 Go GDDR6 unifiée (amdgpu.gttsize=12288 → 12 Go VRAM disponibles)
  - 6 cœurs Zen 2 / 24 CUs RDNA2
  - PyTorch 2.11+ CPU / Python 3.13

GPU (G2-T00) : le chemin GPU de v1.4 est **Vulkan/RADV, sur l'hôte** via
llama.cpp (ADR-002). Le backend n'exécute **rien** sur GPU : BGE-M3 et le
reranker sont CPU. ROCm n'est pas le chemin cible — les champs AMD/ROCm
conservés ici sont LEGACY et servent encore au calcul CPU de `BATCH_SIZE`.

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

from functools import lru_cache

from pydantic_settings import BaseSettings

from .validators import (
    _validate_amd_cus,
    _validate_api_token,
    _validate_cors,
    _validate_database_url,
    _validate_token_source,
)


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

    # ── llama.cpp hôte (ADR-002/003) ──────────────────────────────
    # Endpoint canonique pour l'inférence LLM (le vocabulaire Ollama des
    # tickets v1.4 est historique — GLOSSARY.md). Injecté via
    # docker-compose.yml : extra_hosts llama-host:172.30.50.1 (ADR-003).
    # CONTRAT UNIQUE backend → LLM (G2-T02) : le backend ne possède AUCUNE
    # variable de sélection de modèle — le modèle (Qwen2.5-7B-Instruct Q6_K)
    # est configuré sur le service llama.cpp host/systemd (décision XZ #1).
    LLAMA_SERVER_URL: str = "http://llama-host:8081"

    # ── llama.cpp — options d'appel API (client HTTP, G2-T02) ─────
    # L'ancien bloc OLLAMA_* (10 champs) a été supprimé par G2-T02.
    # Seules les options qui appartiennent réellement au client HTTP
    # (payload /v1/chat/completions) sont conservées ici, renommées en
    # vocabulaire llama.cpp/OpenAI. Mapping depuis l'ancien bloc :
    #   temperature → temperature (identique)
    #   top_p       → top_p       (identique)
    #   top_k       → top_k       (identique)
    #   num_predict → max_tokens  (renommage OpenAI)
    # Options de PROCESSUS llama.cpp — configurées sur le service
    # llama.cpp (systemd/flags), JAMAIS comme settings FastAPI (XZ r.4) :
    #   num_ctx  → -c (contexte serveur)      num_thread → n_threads (lanceur)
    #   num_gpu  → -ngl (lanceur)             f16_kv     → cache KV (serveur)
    #   + -ctk, -ctv, -np, -fa, -b, -ub, --jinja (lanceur/serveur)
    # Valeurs calibrées BC-250 : points de départ à mesurer, pas garanties.
    LLAMA_TEMPERATURE: float = 0.3
    LLAMA_TOP_P:       float = 0.9
    LLAMA_TOP_K:       int   = 40
    LLAMA_MAX_TOKENS:  int   = 1024

    # ── AMD BC-250 — LEGACY (non actif en v1.4, G2-T00) ──────────────────────
    # Champs CONSERVÉS pour ne pas casser `LocalEmbeddingProvider.BATCH_SIZE`,
    # qui en dérive (CPU throughput). Ils ne pilotent plus aucun chemin GPU :
    # ROCm n'est pas le chemin v1.4 (ADR-002 « Conséquences et risques » — « optionnel et non décidé »),
    # le GPU de v1.4 est Vulkan/RADV via llama.cpp sur l'hôte.
    # `HSA_OVERRIDE_GFX_VERSION` n'est plus injecté : voir `_inject_rocm_env`
    # (LEGACY, non appelé).
    HSA_OVERRIDE_GFX_VERSION: str = "10.1.3"  # LEGACY — non injecté (G2-T00)
    # Budget LOGIQUE historique (partagé avec le calcul CPU de BATCH_SIZE).
    # Le plafond kernel réel est posé via ttm.pages_limit=3014656 (Bazzite :
    # `rpm-ostree kargs --append-if-missing="ttm.pages_limit=3014656"`) +
    # UMA_SIZE=512 Mo (CMOS bc250memcfg) → split serveur 12 Go GPU / 4 Go CPU
    # (cf. vault/docs/superpowers/specs/
    # 2026-08-26-bc250-bazzite-deployment.md). Le triplet
    # gttsize=14750/pages_limit/page_pool_size=3959290 (~15 Go) est ÉVITÉ :
    # il pomperait la RAM CPU sur un système unifié 16 Go.
    AMD_GTT_SIZE_MB:          int = 12288
    # 24 = stock (16 CUs fusionnés en firmware). Après déblocage 40 CU
    # (déblocage 40 CU via UMR, cf. scripts/bc250/40cu-unlock/bc250-cu-live-manager.sh), passer à 40
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

    # ── Auto-évaluation (Juge + Avocat du diable) ───────────────
    # Quality-first : temperature=0 (déterministe), format=json.
    # Exécution SÉQUENTIELLE (un seul appel LLM à la fois) — pas de gather.
    # NOTE (G2-T02) : EVAL_NUM_CTX/EVAL_NUM_PREDICT sont des paramètres de
    # payload applicatif (appel d'évaluation), PAS des options de processus
    # llama.cpp — leur migration d'API reste au périmètre T07.
    EVAL_TIMEOUT_S:   float = 15.0
    EVAL_NUM_PREDICT: int   = 150
    EVAL_NUM_CTX:     int   = 2048
    # 1.0 = toutes les conversations évaluées (quality-first).
    # Réductible (0.5 / 0.3) si la charge dépasse le budget BC-250.
    EVAL_SAMPLE_RATE: float = 1.0

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

    v1.4 (G2-T00) : n'injecte PLUS aucune variable ROCm dans l'environnement.
    Avant, `_inject_rocm_env(s)` était appelé ici, AVANT que torch ne soit
    importé ailleurs — ce qui faisait de ROCm un chemin actif implicite alors
    que le chemin GPU de v1.4 est Vulkan/RADV via llama.cpp sur l'hôte
    (ADR-002 « Conséquences et risques » : « ROCm reste optionnel et non décidé »).

    La fonction `_inject_rocm_env` reste dans `validators.py`, marquée LEGACY et
    non appelée, pour ne pas effacer la trace de la décision.

    Note : lru_cache garantit que les setdefault éventuels ne sont appelés
    qu'une fois — correct en production, à désactiver dans les tests unitaires.
    """
    s = Settings()

    _validate_token_source(s)
    _validate_database_url(s)
    _validate_api_token(s)
    _validate_cors(s)
    _validate_amd_cus(s)
    return s
