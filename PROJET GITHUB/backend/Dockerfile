# =============================================================================
# Prof IA v6.0 — Dockerfile Backend (AMD BC-250 / ROCm 7.2 / Python 3.13)
# =============================================================================
# FIX BUG#2 : Ce fichier était absent — docker compose build échouait
#
# NOTE ROCm : PyTorch ROCm ne peut pas être installé depuis le PyPI standard.
# En production sur BC-250, utiliser l'image de base ROCm officielle :
#   FROM rocm/pytorch:rocm7.2_ubuntu22.04_py3.13_pytorch_release
# En développement / CI sans GPU, l'image python:3.13-slim est suffisante.
#
# Pour basculer en image ROCm complète, remplacer la ligne FROM ci-dessous
# et retirer le bloc "PyTorch CPU (CI/dev)" pour activer le bloc ROCm.
# =============================================================================

ARG PYTHON_VERSION=3.13
ARG USE_ROCM=false
FROM python:${PYTHON_VERSION}-slim AS base

# ── Dépendances système ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq-dev \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ── Répertoire de travail ─────────────────────────────────────────────────────
WORKDIR /app

# ── Dépendances Python ────────────────────────────────────────────────────────
# Copie séparée pour profiter du cache Docker (ne rebuild que si requirements changent)
COPY requirements.txt .

# PyTorch — sélection ROCm ou CPU via --build-arg USE_ROCM=true
RUN if [ "$USE_ROCM" = "true" ]; then \
        pip install --no-cache-dir torch torchvision torchaudio \
            --index-url https://download.pytorch.org/whl/rocm7.2; \
    else \
        pip install --no-cache-dir torch torchvision torchaudio \
            --index-url https://download.pytorch.org/whl/cpu; \
    fi

# Reste des dépendances Prof IA
RUN pip install --no-cache-dir -r requirements.txt

# ── Code de l'application ─────────────────────────────────────────────────────
# En PRODUCTION : décommenter ce COPY et commenter les volumes dans docker-compose.yml
# COPY api/ /app/api/

# ── Variables ROCm — injectées avant tout import torch ────────────────────────
# Cyan Skillfish (gfx1013) absent de la liste officielle ROCm
ENV HSA_OVERRIDE_GFX_VERSION=10.1.3
ENV ROCR_VISIBLE_DEVICES=0
# PYTORCH_HIP_ALLOC_CONF est calculé dynamiquement par config.py — ne pas fixer ici

# ── Répertoires de données ────────────────────────────────────────────────────
RUN mkdir -p /app/data/uploads /app/data/logs /app/models

# ── Utilisateur non-root ─────────────────────────────────────────────────────
# Note : les groupes video et render sont ajoutés via group_add dans docker-compose
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser && \
    chown -R appuser:appgroup /app

USER appuser

# ── Port ─────────────────────────────────────────────────────────────────────
EXPOSE 8000

# ── Healthcheck ───────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ── Commande par défaut ───────────────────────────────────────────────────────
# Surchargée par docker-compose.yml (uvicorn avec --loop uvloop --http h11)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
