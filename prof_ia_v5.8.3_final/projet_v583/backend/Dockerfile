# =============================================================================
# Prof IA v5.8.3 — Dockerfile Backend (AMD BC-250 / ROCm 7.2 / Python 3.13)
# =============================================================================
#
# CHANGELOG v5.8.3 :
#   [C1/v5.8.2] PyTorch ROCm 7.2 activé — GPU AMD RDNA2 utilisé pour embeddings
#   [M2] COPY api/ commenté VOLONTAIREMENT — ce n'est pas un oubli.
#        Raison : le volume mount ./backend:/app dans docker-compose.yml
#        permet de modifier le code Python via nano/PuTTY et de faire
#        docker compose restart backend sans rebuild (5min). Adapté au BC-250
#        dédié mono-serveur où on ne distribue pas l'image Docker.
#        Pour un déploiement multi-serveur : décommenter COPY et supprimer le volume.
#   [M4] Version uniformisée à 5.8.3
#
# ARCHITECTURE :
#   Image de base : python:3.13-slim (légère, compatible ROCm via index PyTorch)
#   PyTorch ROCm  : installé depuis https://download.pytorch.org/whl/rocm7.2
#   GPU cible     : AMD Cyan Skillfish gfx1013 (BC-250) — HSA_OVERRIDE requis
# =============================================================================

ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-slim AS base

LABEL maintainer="Prof IA v5.8.3"
LABEL description="Backend FastAPI + ChromaDB + Embeddings ROCm — AMD BC-250"
LABEL version="5.8.3"

# ── Dépendances système ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq-dev \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Dépendances Python ────────────────────────────────────────────────────────
COPY requirements.txt .

# [C1] PyTorch ROCm 7.2 — GPU AMD BC-250 (Cyan Skillfish RDNA2)
# Index officiel PyTorch ROCm — les embeddings all-MiniLM-L6-v2 utilisent le GPU
# VRAM : ~1.5Go en fp16 sur les 16Go GDDR6 unifiée du BC-250
RUN pip install --no-cache-dir torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/rocm7.2

# Dépendances Prof IA (FastAPI, ChromaDB, sentence-transformers, asyncpg, docker...)
RUN pip install --no-cache-dir -r requirements.txt

# ── Code de l'application ─────────────────────────────────────────────────────
# [M2] COPY commenté VOLONTAIREMENT — voir explication en tête de fichier
# En production multi-serveur : décommenter cette ligne + supprimer le volume
# mount './backend:/app' dans docker-compose.yml
# COPY api/ /app/api/

# ── Variables ROCm ────────────────────────────────────────────────────────────
# Cyan Skillfish (gfx1013) absent de la liste officielle ROCm → override obligatoire
ENV HSA_OVERRIDE_GFX_VERSION=10.1.3
ENV ROCR_VISIBLE_DEVICES=0
# PYTORCH_HIP_ALLOC_CONF calculé dynamiquement par config.py (max_split_size_mb)

# ── Répertoires de données ────────────────────────────────────────────────────
RUN mkdir -p /app/data/uploads /app/data/logs /app/models /app/chromadb_data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
