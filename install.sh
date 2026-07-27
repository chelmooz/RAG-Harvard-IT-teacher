#!/usr/bin/env bash
# =============================================================================
# Prof IA v6.0 — Script d'installation AMD BC-250 (Cyan Skillfish / RDNA2)
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
info " Prof IA v6.0 — Setup AMD BC-250"
info " Architecture : Cyan Skillfish (RDNA2)"
info " GFX override : $HSA_OVERRIDE_GFX_VERSION"
info "========================================"

# ── 1. Vérification du matériel ──────────────────────────────────────────────
info "1/9 Vérification du matériel AMD..."
if ! lspci | grep -qi "Navi"; then
    warn "GPU AMD non détecté via lspci — continuer quand même ? (Ctrl+C pour annuler)"
    sleep 3
fi

if [[ ! -e /dev/kfd ]]; then
    error "/dev/kfd absent. Vérifiez que amdgpu est chargé : sudo modprobe amdgpu"
fi

info "✅ /dev/kfd présent"

# ── 2. Variables système permanentes ─────────────────────────────────────────
info "2/9 Configuration variables ROCm permanentes..."
ROCM_ENV="/etc/environment.d/99-rocm-bc250.conf"
sudo tee "$ROCM_ENV" > /dev/null <<EOF
HSA_OVERRIDE_GFX_VERSION=10.1.3
ROCR_VISIBLE_DEVICES=0
PYTORCH_HIP_ALLOC_CONF=max_split_size_mb:512
EOF
info "✅ Variables écrites dans $ROCM_ENV"

# ── 3. Paramètres kernel VRAM (gttsize + ttm.pages_limit + ttm.page_pool_size) ─
info "3/9 Vérification des paramètres VRAM (GTT unifiée)..."
GRUB_FILE="/etc/default/grub"
CURRENT_CMD=$(grep "^GRUB_CMDLINE_LINUX_DEFAULT" "$GRUB_FILE" || echo "")

# Valeurs documentées (elektricm.github.io/amd-bc250-docs/linux/kernel/) —
# triplet testé par la communauté pour un accès GPU max (~14.5-14.75 Go).
# AMD_GTT_SIZE_MB=12288 (app, config.py) reste le budget LOGIQUE utilisé par
# PYTORCH_HIP_ALLOC_CONF ; ce plafond kernel plus large laisse de la marge
# pour éviter que le driver ne plante pile à la limite.
GTT_KERNEL_PARAMS="amdgpu.gttsize=14750 ttm.pages_limit=3959290 ttm.page_pool_size=3959290"

MISSING_PARAMS=()
echo "$CURRENT_CMD" | grep -q "gttsize"          || MISSING_PARAMS+=("amdgpu.gttsize")
echo "$CURRENT_CMD" | grep -q "ttm.pages_limit"   || MISSING_PARAMS+=("ttm.pages_limit")
echo "$CURRENT_CMD" | grep -q "ttm.page_pool_size" || MISSING_PARAMS+=("ttm.page_pool_size")

if echo "$CURRENT_CMD" | grep -q "amd_iommu=on"; then
    error "amd_iommu=on détecté dans GRUB — IOMMU est CASSÉ sur BC-250 (crashs, écran noir). Retirez-le avant de continuer."
fi

if [[ ${#MISSING_PARAMS[@]} -eq 0 ]]; then
    info "✅ gttsize + ttm.pages_limit + ttm.page_pool_size déjà tous configurés"
else
    warn "Paramètre(s) manquant(s) dans GRUB : ${MISSING_PARAMS[*]}"
    warn "Sans ttm.pages_limit/ttm.page_pool_size en plus de gttsize, le plafond VRAM"
    warn "par défaut peut être dépassé et faire planter le driver avant les 12 Go visés."
    echo ""
    read -rp "Ajouter automatiquement '$GTT_KERNEL_PARAMS' à GRUB maintenant ? [o/N] " ADD_GTT
    if [[ "$ADD_GTT" =~ ^[oOyY]$ ]]; then
        sudo cp "$GRUB_FILE" "${GRUB_FILE}.bak.$(date +%s)"
        if grep -q "^GRUB_CMDLINE_LINUX_DEFAULT=" "$GRUB_FILE"; then
            sudo sed -i -E "s|^(GRUB_CMDLINE_LINUX_DEFAULT=\")([^\"]*)(\")|\1\2 ${GTT_KERNEL_PARAMS}\3|" "$GRUB_FILE"
        else
            echo "GRUB_CMDLINE_LINUX_DEFAULT=\"quiet ${GTT_KERNEL_PARAMS}\"" | sudo tee -a "$GRUB_FILE" > /dev/null
        fi
        sudo update-grub
        info "✅ GRUB mis à jour (sauvegarde : ${GRUB_FILE}.bak.*). Un REBOOT est nécessaire pour appliquer."
    else
        warn "Ajoutez manuellement à GRUB_CMDLINE_LINUX_DEFAULT : $GTT_KERNEL_PARAMS"
        warn "Puis lancez : sudo update-grub && sudo reboot"
    fi
fi

# ── 4. Python 3.13 et dépendances système ────────────────────────────────────
info "4/9 Dépendances système..."
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    python3.13 python3.13-venv python3.13-dev \
    ffmpeg libpq-dev \
    curl git build-essential \
    postgresql-client-18 2>/dev/null || \
    sudo apt-get install -y postgresql-client

# ── 5. Environnement virtuel Python 3.13 ─────────────────────────────────────
info "5/9 Création du venv Python 3.13..."
VENV_DIR="./venv"
if [[ ! -d "$VENV_DIR" ]]; then
    python3.13 -m venv "$VENV_DIR"
    info "✅ Venv créé dans $VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

pip install --upgrade pip setuptools wheel -q

# ── 6. PyTorch ROCm 7.2 ──────────────────────────────────────────────────────
info "6/9 Installation PyTorch ROCm 7.2..."
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
info "7/9 Installation dépendances Prof IA v5..."
pip install -r backend/requirements.txt \
    --index-url "$ROCM_INDEX" -q
info "✅ Dépendances Python installées"

# ── 8. Ollama Vulkan ──────────────────────────────────────────────────────────
info "8/9 Configuration Ollama (Vulkan — ROCm non fonctionnel sur gfx1013)..."
if ! command -v ollama &>/dev/null; then
    info "Installation Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh
fi

# Service systemd — Vulkan (pas de variables ROCm : HSA_OVERRIDE_GFX_VERSION
# et ROCR_VISIBLE_DEVICES sont sans effet sur le chemin Vulkan, et Ollama
# bascule automatiquement sur Vulkan après un échec ROCm sur gfx1013).
sudo tee /etc/systemd/system/ollama.service > /dev/null <<'EOF'
[Unit]
Description=Ollama Service (AMD BC-250 — Vulkan/RADV)
After=network-online.target

[Service]
ExecStart=/usr/local/bin/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment="HOME=/usr/share/ollama"
Environment="OLLAMA_KEEP_ALIVE=24h"
Environment="OLLAMA_NUM_PARALLEL=1"

[Install]
WantedBy=default.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ollama
sudo systemctl start ollama
sleep 3

info "Vérification du backend GPU détecté par Ollama..."
journalctl -u ollama -n 30 --no-pager | grep -i "vulkan\|gfx1013\|rocm" || \
    warn "Aucune mention Vulkan/ROCm dans les logs — vérifiez : sudo journalctl -u ollama -f"

info "Téléchargement du modèle Qwen3-14B Q4_K_M (9,3 Go)..."
ollama pull qwen3:14b || \
    warn "Pull Ollama échoué — lancez manuellement : ollama pull qwen3:14b"

# ── 9. Déblocage 40 CU (optionnel) ───────────────────────────────────────────
info "9/9 Déblocage 40 CU RDNA2 (optionnel)..."
echo ""
warn "Le BC-250 sort d'usine avec 24 des 40 CUs actifs (16 fusionnés en firmware,"
warn "pas endommagés). Un déblocage communautaire existe (crédit : duggasco,"
warn "voir https://elektricm.github.io/amd-bc250-docs/system/40cu-unlock/) :"
warn "  - Gain mesuré : ~1.61x en calcul (Vulkan pp512), effet quasi nul en 3D."
warn "  - Reconstruit le module amdgpu hors-arbre : à refaire à chaque MAJ kernel."
warn "  - Toutes les cartes ne se débloquent pas proprement (harvest pattern)."
warn "  - Sustained load nécessite un plafond gouverneur à 1500 MHz + un bon refroidissement."
warn "  - Réversible (sauvegarde du module d'origine)."
echo ""
read -rp "Lancer scripts/unlock-40cu.sh maintenant ? [o/N] " RUN_40CU
if [[ "$RUN_40CU" =~ ^[oOyY]$ ]]; then
    bash "$(dirname "$0")/scripts/unlock-40cu.sh"
else
    info "Ignoré. Vous pourrez le lancer plus tard avec : ./scripts/unlock-40cu.sh"
fi

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
warn "  2. Reboot avec amdgpu.gttsize=14750 ttm.pages_limit=3959290 ttm.page_pool_size=3959290 dans GRUB"
