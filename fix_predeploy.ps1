function Write-Utf8NoBom($path, $content) {
    [System.IO.File]::WriteAllText($path, $content, (New-Object System.Text.UTF8Encoding $false))
}

$dockerComposeContent = @'
# =============================================================================
# Prof IA v6.0 — docker-compose AMD BC-250 (Cyan Skillfish / RDNA2)
# =============================================================================
# CORRECTIFS v6.0 :
#   pg18  : PostgreSQL 18.2 + pgvector (cohérent avec toute la documentation)
#   Ports : tous les services accessibles sur 0.0.0.0 (réseau local isolé)
#   CORS  : toutes origines autorisées (* — usage LAN uniquement)
#   JWT   : token libre, pas de contrainte (auth GitHub datasets)
#   root  : pas de restriction utilisateur dans les conteneurs
# =============================================================================

services:

  # PostgreSQL 18.2 + pgvector
  postgres:
    image: pgvector/pgvector:pg18
    container_name: prof-ia-postgres-v6.0
    restart: unless-stopped
    environment:
      POSTGRES_DB:              prof_ia_v5
      POSTGRES_USER:            user
      # OBLIGATOIRE : pas de fallback faible. `docker compose up` échoue si
      # POSTGRES_PASSWORD n'est pas défini dans .env (voir .env.example).
      POSTGRES_PASSWORD:        ${POSTGRES_PASSWORD:?"POSTGRES_PASSWORD manquant dans .env — obligatoire (plus de fallback faible)"}
      POSTGRES_INITDB_ARGS:     "--encoding=UTF8"
      # scram-sha-256 : authentification par mot de passe réelle.
      # (trust acceptait TOUTE connexion sans mot de passe — faille critique corrigée)
      POSTGRES_HOST_AUTH_METHOD: scram-sha-256
    command: >
      postgres
        -c shared_buffers=2GB
        -c effective_cache_size=6GB
        -c work_mem=256MB
        -c maintenance_work_mem=1GB
        -c max_parallel_workers_per_gather=3
        -c max_worker_processes=6
        -c wal_compression=zstd
        -c random_page_cost=1.1
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      # Loopback uniquement — plus exposé sur le LAN. Le backend accède via
      # le réseau Docker interne (prof-ia-network), pas via ce port publié.
      - "127.0.0.1:5432:5432"
    networks:
      - prof-ia-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d prof_ia_v5"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Ollama — Vulkan (RADV) pour l'inférence LLM.
  # ROCm ne supporte pas gfx1013 (rocBLAS sans binaires pour cette cible,
  # voir Prof-IA-v5-Documentation-BC250.md §1). L'image ollama/ollama
  # standard (PAS le tag :rocm) embarque le backend Vulkan depuis les
  # versions récentes : Ollama tente ROCm au démarrage, échoue proprement
  # sur gfx1013, et bascule automatiquement sur Vulkan (RADV) — comportement
  # documenté par la communauté BC-250 (akandr/bc250, thelamer/bc250-ollama-openwebui).
  # Les embeddings (SentenceTransformer, backend/api/rag_engine.py) restent
  # inchangés : ROCm si dispo, sinon repli CPU — voir DEVICE dans rag_engine.py.
  ollama:
    image: ollama/ollama:latest
    container_name: prof-ia-ollama-vulkan
    restart: unless-stopped
    devices:
      - /dev/dri:/dev/dri            # accès Vulkan (RADV) — pas besoin de /dev/kfd (ROCm)
    group_add:
      - video
      - render
    environment:
      # PAS de HSA_OVERRIDE_GFX_VERSION / ROCR_VISIBLE_DEVICES ici : ce sont
      # des variables ROCm, sans effet (ni utilité) sur le chemin Vulkan.
      OLLAMA_KEEP_ALIVE:        "24h"
      OLLAMA_NUM_PARALLEL:      "1"
      OLLAMA_MAX_LOADED_MODELS: "1"
      # GGML_VK_VISIBLE_DEVICES: "0"  # décommenter si plusieurs devices Vulkan détectés
    volumes:
      - ollama_data:/root/.ollama
    ports:
      # Loopback uniquement — Ollama n'a pas d'authentification propre.
      # Le backend y accède via le réseau Docker interne (http://ollama:11434).
      - "127.0.0.1:11434:11434"
    networks:
      - prof-ia-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Backend FastAPI
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
      args:
        PYTHON_VERSION: "3.13"
        USE_ROCM: "true"
    container_name: prof-ia-backend-v6.0
    restart: unless-stopped
    devices:
      - /dev/kfd:/dev/kfd
      - /dev/dri:/dev/dri
    group_add:
      - video
      - render
    environment:
      DATABASE_URL:             postgresql://user:${POSTGRES_PASSWORD:?"POSTGRES_PASSWORD manquant dans .env"}@postgres:5432/prof_ia_v5
      OLLAMA_HOST:              http://ollama:11434
      OLLAMA_MODEL:             ${OLLAMA_MODEL:-mistral:7b-instruct-q4_K_M}
      HSA_OVERRIDE_GFX_VERSION: "10.1.3"
      ROCR_VISIBLE_DEVICES:     "0"
      PYTORCH_HIP_ALLOC_CONF:   "max_split_size_mb:512"
      RAG_THRESHOLD:            "0.72"
      RAG_TOP_K:                "5"
      CHUNK_SIZE:               "400"
      CHUNK_OVERLAP:            "80"
      ENABLE_LOGGING:           "true"
      AUTO_EVALUATE:            "true"
      GOLDEN_THRESHOLD:         "0.85"
      # FIX : config.py utilise API_TOKEN_SOURCE/API_TOKEN depuis le renommage
      # de JWT_SECRET — l'ancienne variable était ignorée silencieusement
      # (extra="ignore"), ce qui générait un token aléatoire à chaque restart
      # et cassait systématiquement l'auth frontend↔backend. Corrigé ici.
      API_TOKEN:                ${API_TOKEN:?"API_TOKEN manquant dans .env — obligatoire, doit être identique à REACT_APP_API_TOKEN côté frontend"}
      # Restreint par défaut aux origines connues du frontend (LAN). Ajoutez
      # d'autres IP/hosts séparés par des virgules dans .env si besoin.
      CORS_ORIGINS:             ${CORS_ORIGINS:-http://localhost:3000,http://127.0.0.1:3000}
      UPLOAD_DIR:               "/app/data/uploads"
    volumes:
      - ./backend:/app
      - ./data/uploads:/app/data/uploads
      - ./data/logs:/app/data/logs
    ports:
      - "0.0.0.0:8001:8000"
    networks:
      - prof-ia-network
    depends_on:
      postgres:
        condition: service_healthy
      ollama:
        condition: service_started
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    command: >
      uvicorn api.main:app
        --host 0.0.0.0
        --port 8000
        --workers 1
        --loop uvloop
        --http h11

  # Frontend React
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: prof-ia-frontend-v6.0
    restart: unless-stopped
    environment:
      - REACT_APP_API_URL=http://localhost:8001
      - REACT_APP_VERSION=6.0.0
      # Doit être strictement identique à API_TOKEN du service backend, sinon
      # api.js retombe sur le défaut 'dev-token' et toutes les requêtes échouent.
      - REACT_APP_API_TOKEN=${API_TOKEN:?"API_TOKEN manquant dans .env"}
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "0.0.0.0:3000:3000"
    networks:
      - prof-ia-network
    depends_on:
      backend:
        condition: service_healthy

  # Nginx reverse proxy
  nginx:
    image: nginx:alpine
    container_name: prof-ia-nginx-v6.0
    restart: unless-stopped
    ports:
      - "0.0.0.0:8080:80"
    volumes:
      - ./config/nginx.conf:/etc/nginx/nginx.conf:ro
    networks:
      - prof-ia-network
    depends_on:
      - frontend
      - backend

networks:
  prof-ia-network:
    driver: bridge

volumes:
  postgres_data:
    driver: local
  ollama_data:
    driver: local
'@

$envExampleContent = @'
# ── Prof IA — Configuration minimale ─────────────────────────────
# ⚠️ Ce fichier doit être copié en `.env` et complété AVANT `docker compose up`.
# `docker-compose.yml` refuse de démarrer si POSTGRES_PASSWORD ou API_TOKEN
# sont absents (plus de fallback faible type "user" ou "dev-token").

# PostgreSQL — OBLIGATOIRE (utilisé par le service postgres ET par le backend
# pour construire DATABASE_URL — ne pas mettre "user" ou une valeur faible)
# Générer : python -c "import secrets; print(secrets.token_urlsafe(24))"
POSTGRES_PASSWORD=

# Si vous exécutez le backend HORS Docker (dev local), définissez aussi :
# DATABASE_URL=postgresql://user:<même_valeur_que_POSTGRES_PASSWORD>@localhost:5432/prof_ia_v5

# Ollama (défaut : http://localhost:11434)
# OLLAMA_HOST=http://localhost:11434
# OLLAMA_MODEL=qwen3:14b

# Token API — OBLIGATOIRE. Doit être IDENTIQUE côté backend (API_TOKEN) et
# frontend (REACT_APP_API_TOKEN, injecté automatiquement depuis cette même
# variable par docker-compose.yml). Sans cette valeur, le frontend retombe
# sur 'dev-token' et toutes les requêtes API échouent (401).
# Générer : python -c "import secrets; print(secrets.token_urlsafe(32))"
API_TOKEN=

# CORS — origines autorisées, séparées par des virgules.
# Défaut si absent : http://localhost:3000,http://127.0.0.1:3000
# Ajoutez l'IP LAN du frontend si accédé depuis d'autres postes, ex :
# CORS_ORIGINS=http://localhost:3000,http://192.168.1.11:3000
# CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Mode debug (false en production)
# DEBUG=false

# GPU RDNA2 — nombre de CUs réellement actifs
# 24 = stock (défaut). Passer à 40 SEULEMENT après avoir lancé
# scripts/unlock-40cu.sh et vérifié `sudo dmesg | grep active_cu_number`.
# AMD_RDNA2_CUS=40
# AMD_CU_UNLOCK_APPLIED=true

# VRAM/GTT — AMD_GTT_SIZE_MB (config.py, défaut 12288 = 12 Go) est le budget
# LOGIQUE de l'appli. Pour qu'il soit réellement atteignable sans planter,
# GRUB doit avoir les 3 paramètres suivants ENSEMBLE (pas gttsize seul) :
#   amdgpu.gttsize=14750 ttm.pages_limit=3959290 ttm.page_pool_size=3959290
# Voir install.sh étape 3/9, qui peut les ajouter automatiquement.
# AMD_GTT_SIZE_MB=12288'@

Write-Utf8NoBom "$PWD\docker-compose.yml" $dockerComposeContent
Write-Utf8NoBom "$PWD\.env.example" $envExampleContent

$len1 = (Get-Item .\docker-compose.yml).Length
$len2 = (Get-Item .\.env.example).Length
Write-Host "docker-compose.yml : $len1 octets (attendu ~7500)"
Write-Host ".env.example       : $len2 octets (attendu ~2300)"
