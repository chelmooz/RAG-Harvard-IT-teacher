#!/usr/bin/env bash
# =============================================================================
# Prof IA v5.4 — Script d'installation AMD BC-250 (Cyan Skillfish / RDNA2)
# OS : Debian 13.3 (Trixie) | Kernel 6.18.10 | Mesa 26.0 | ROCm 7.2
# =============================================================================
set -euo pipefail

# ── Couleurs ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Variables BC-250 ──────────────────────────────────────────────────────────
export HSA_OVERRIDE_GFX_VERSION="10.1.3"   # Cyan Skillfish = gfx1013
export ROCR_VISIBLE_DEVICES="0"
export PYTORCH_HIP_ALLOC_CONF="max_split_size_mb:512"

info "========================================"
info " Prof IA v5.4 — Setup AMD BC-250"
info " Architecture : Cyan Skillfish (RDNA2)"
info " GFX override : $HSA_OVERRIDE_GFX_VERSION"
info "========================================"

# ── 1. Vérification du matériel ──────────────────────────────────────────────
info "1/8 Vérification du matériel AMD..."
if ! lspci | grep -qi "Navi"; then
    warn "GPU AMD non détecté via lspci — continuer quand même ? (Ctrl+C pour annuler)"
    sleep 3
fi

if [[ ! -e /dev/kfd ]]; then
    error "/dev/kfd absent. Vérifiez que amdgpu est chargé : sudo modprobe amdgpu"
fi

info "✅ /dev/kfd présent"

# ── 2. Variables système permanentes ─────────────────────────────────────────
info "2/8 Configuration variables ROCm permanentes..."
ROCM_ENV="/etc/environment.d/99-rocm-bc250.conf"
sudo tee "$ROCM_ENV" > /dev/null <<EOF
HSA_OVERRIDE_GFX_VERSION=10.1.3
ROCR_VISIBLE_DEVICES=0
PYTORCH_HIP_ALLOC_CONF=max_split_size_mb:512
EOF
info "✅ Variables écrites dans $ROCM_ENV"

# ── 3. Paramètre kernel amdgpu.gttsize ────────────────────────────────────────
info "3/8 Vérification gttsize (VRAM unifiée)..."
GRUB_FILE="/etc/default/grub"
CURRENT_CMD=$(grep "^GRUB_CMDLINE_LINUX_DEFAULT" "$GRUB_FILE" || echo "")
if echo "$CURRENT_CMD" | grep -q "gttsize"; then
    info "✅ amdgpu.gttsize déjà configuré"
else
    warn "amdgpu.gttsize=12288 absent du GRUB — ajoutez manuellement à GRUB_CMDLINE_LINUX_DEFAULT"
    warn "Puis lancez : sudo update-grub && sudo reboot"
fi

# ── 4. Python 3.13 et dépendances système ────────────────────────────────────
info "4/8 Dépendances système..."
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    python3.13 python3.13-venv python3.13-dev \
    ffmpeg libpq-dev \
    curl git build-essential \
    postgresql-client-18 2>/dev/null || \
    sudo apt-get install -y postgresql-client

# ── 5. Environnement virtuel Python 3.13 ─────────────────────────────────────
info "5/8 Création du venv Python 3.13..."
VENV_DIR="./venv"
if [[ ! -d "$VENV_DIR" ]]; then
    python3.13 -m venv "$VENV_DIR"
    info "✅ Venv créé dans $VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

pip install --upgrade pip setuptools wheel -q

# ── 6. PyTorch ROCm 7.2 ──────────────────────────────────────────────────────
info "6/8 Installation PyTorch ROCm 7.2..."
ROCM_INDEX="https://download.pytorch.org/whl/rocm7.2"

# Vérifie si PyTorch ROCm est déjà installé
if python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    info "✅ PyTorch ROCm déjà installé"
else
    pip install torch torchvision torchaudio \
        --index-url "$ROCM_INDEX" -q
    info "✅ PyTorch ROCm 7.2 installé"
fi

# Vérification ROCm
python -c "
import torch
print(f'PyTorch : {torch.__version__}')
print(f'ROCm disponible : {torch.cuda.is_available()}')
if torch.cuda.is_available():
    props = torch.cuda.get_device_properties(0)
    print(f'GPU : {props.name} | {props.total_memory // 1024**2} Mo')
" || warn "Vérification PyTorch échouée (normal si GPU non accessible dans ce shell)"

# ── 7. Dépendances Prof IA v5 ─────────────────────────────────────────────────
info "7/8 Installation dépendances Prof IA v5..."
pip install -r backend/requirements.txt \
    --index-url "$ROCM_INDEX" -q
info "✅ Dépendances Python installées"

# ── 8. Ollama ROCm ───────────────────────────────────────────────────────────
info "8/8 Configuration Ollama ROCm..."
if ! command -v ollama &>/dev/null; then
    info "Installation Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh
fi

# Créer le service systemd avec les variables ROCm
sudo tee /etc/systemd/system/ollama.service > /dev/null <<'EOF'
[Unit]
Description=Ollama Service (AMD BC-250)
After=network-online.target

[Service]
ExecStart=/usr/local/bin/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment="HOME=/usr/share/ollama"
Environment="HSA_OVERRIDE_GFX_VERSION=10.1.3"
Environment="ROCR_VISIBLE_DEVICES=0"
Environment="OLLAMA_KEEP_ALIVE=24h"
Environment="OLLAMA_NUM_PARALLEL=1"

[Install]
WantedBy=default.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ollama
sudo systemctl start ollama
sleep 3

info "Téléchargement du modèle Mistral 7B Q4_K_M (4,5 Go)..."
HSA_OVERRIDE_GFX_VERSION=10.1.3 ollama pull mistral:7b-instruct-q4_K_M || \
    warn "Pull Ollama échoué — lancez manuellement : ollama pull mistral:7b-instruct-q4_K_M"

# ── Résumé ───────────────────────────────────────────────────────────────────
echo ""
info "========================================"
info " ✅ Installation Prof IA v5 terminée!"
info "========================================"
echo ""
info "Pour démarrer : docker compose up -d"
info "Ou sans Docker : source venv/bin/activate && uvicorn backend.api.main:app"
echo ""
info "Variables ROCm actives dans ce shell :"
info "  HSA_OVERRIDE_GFX_VERSION=$HSA_OVERRIDE_GFX_VERSION"
info "  PYTORCH_HIP_ALLOC_CONF=$PYTORCH_HIP_ALLOC_CONF"
echo ""
warn "Si le GPU n'est pas détecté, vérifiez :"
warn "  1. sudo usermod -aG video,render \$USER && newgrp render"
warn "  2. Reboot avec amdgpu.gttsize=12288 dans GRUB"
