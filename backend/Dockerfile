# =============================================================================
# Prof IA v1.4 — Dockerfile Backend (BC-250 / CPU / Python 3.13)
# =============================================================================
# FIX BUG#2 : Ce fichier était absent — docker compose build échouait
#
# GPU — v1.4 (G2-T00) :
#   Le chemin GPU de v1.4 est Vulkan/RADV, et il est exécuté par llama.cpp SUR
#   L'HÔTE (ADR-002). Le conteneur backend n'a PAS de chemin GPU : BGE-M3 et le
#   reranker tournent sur CPU.
#   ROCm n'est pas le chemin cible (ADR-002 « Conséquences et risques » : « optionnel et non décidé »).
#   `USE_ROCM` reste lisible pour une demande explicite, mais il est désactivé
#   par défaut et ne masque PLUS aucun échec.
#
# Image de base : python slim (jamais rocm/pytorch).
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

# PyTorch — sélection CPU (défaut v1.4) ou ROCm (demande explicite).
#
# G2-T00 : le repli `|| pip install .../whl/cpu` a été SUPPRIMÉ. Il rendait une
# installation ROCm échouée indiscernable d'une installation réussie : `USE_ROCM=true`
# pouvait ne rien signifier du tout. v1.4 exige que l'échec soit BRUYANT —
# demander ROCm et le rater doit casser le build, pas installer du torch CPU en silence.
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

# ── Variables ROCm — VOLONTAIREMENT ABSENTES (G2-T00) ────────────────────────
# HSA_OVERRIDE_GFX_VERSION et ROCR_VISIBLE_DEVICES ne sont plus définies ici :
# elles n'ont de sens qu'avec un torch ROCm, qui n'est pas le chemin v1.4
# (embeddings BGE-M3 CPU + reranker CPU, LLM externalisé sur l'hôte).
# PYTORCH_HIP_ALLOC_CONF était également injecté ici ; il ne l'est plus.
# Historique conservé : voir ADR-002 « Conséquences et risques » — « ROCm reste optionnel et non décidé ».

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
