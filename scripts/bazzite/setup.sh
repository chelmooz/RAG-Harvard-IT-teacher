#!/usr/bin/env bash
# =============================================================================
# Prof IA v6.0 — Setup BC-250 sur BAZZITE (Fedora immuable, rpm-ostree)
# -----------------------------------------------------------------------------
# OS « first-class » recommandé (README §8.1). Pour Debian/ROCm, voir install.sh.
#
# Phase 1 (userspace, AUCUN rebuild noyau) :
#   - Split RAM/VRAM serveur (12 Go GPU / 4 Go CPU)
#   - Governor SMU Cyan Skillfish (COPR)
#   - Dépendances : umr (40 CU) + python3 (SMU)
#   - Service systemd durci (40 CU / 8c / UV-OC) + health-check
#   - Bascule mode JEU / RAG (libération VRAM Ollama)
#
# ⚠️  Reboot requis après les kargs rpm-ostree (et après install de paquets).
# =============================================================================
set -uo pipefail

export HSA_OVERRIDE_GFX_VERSION="10.1.3"   # Cyan Skillfish = gfx1013
export RADV_DEBUG="nohiz"

info()  { echo -e "\033[0;32m[INFO]\033[0m $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m $*"; }

# Racine du repo (parent de scripts/bazzite)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BC250_SRC="$REPO_ROOT/scripts/bc250"
INSTALL_DIR="/opt/bc250"

# ── 1. Split RAM/VRAM : ttm.pages_limit (~12 Go GPU / 4 Go CPU) ────────────────
# UMA_SIZE=512 Mo se règle dans le CMOS (bc250memcfg / menu BIOS), pas en kargs.
info "Karg ttm.pages_limit=3014656 (split serveur 12/4 Go)..."
rpm-ostree kargs --append-if-missing="ttm.pages_limit=3014656"

# ── 2. Governor SMU (pilote 40 CU / limites) via COPR filippor/bazzite ─────────
info "Governor cyan-skillfish-governor-smu (COPR filippor/bazzite)..."
if ! rpm -q cyan-skillfish-governor-smu >/dev/null 2>&1; then
    sudo rpm-ostree install \
        "https://download.copr.fedorainfracloud.org/results/filippor/bazzite/fedora-$(rpm -E %fedora)/x86_64/cyan-skillfish-governor-smu-*-1.x86_64.rpm" \
        || warn "COPR filippor/bazzite indisponible — installez le governor manuellement."
fi

# ── 3. Dépendances userspace : umr (40 CU) + python3 (SMU) ────────────────────
info "Dépendances : umr + python3..."
if ! command -v umr >/dev/null 2>&1; then
    sudo rpm-ostree install umr \
        || warn "Paquet 'umr' indispo via rpm-ostree — installez via distrobox/brew, ou build depuis https://gitlab.freedesktop.org/tomstdenis/umr"
fi
if ! command -v python3 >/dev/null 2>&1; then
    sudo rpm-ostree install python3 \
        || warn "python3 requis pour les scripts SMU (core-unlock / smu-oc)."
fi

# ── 4. Variables d'environnement ROCm pour la session ─────────────────────────
info "Export des variables ROCm (gfx1013)..."
grep -qxF 'export HSA_OVERRIDE_GFX_VERSION="10.1.3"' ~/.bashrc 2>/dev/null \
    || echo 'export HSA_OVERRIDE_GFX_VERSION="10.1.3"' >> ~/.bashrc
grep -qxF 'export RADV_DEBUG="nohiz"' ~/.bashrc 2>/dev/null \
    || echo 'export RADV_DEBUG="nohiz"' >> ~/.bashrc

# ── 5. Installation des scripts BC-250 sous /opt/bc250 + service systemd ───────
info "Installation de $BC250_SRC → $INSTALL_DIR ..."
sudo mkdir -p "$INSTALL_DIR"
sudo cp -r "$BC250_SRC/." "$INSTALL_DIR/"
sudo chmod +x "$INSTALL_DIR"/*.sh "$INSTALL_DIR"/mem-oc/*.sh

info "Installation du service systemd durci (Restart=on-failure + health-check)..."
sudo cp "$INSTALL_DIR/bc250-optimizations.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bc250-optimizations.service
info "Service activé. Il s'exécute au boot (40 CU / 8c / UV-OC) et retente si échec."

# ── 6. Bascule mode JEU / RAG ─────────────────────────────────────────────────
info "Installation du swapper bc250-game-mode..."
sudo cp "$INSTALL_DIR/bc250-game-mode.sh" /usr/local/bin/bc250-game-mode
sudo chmod +x /usr/local/bin/bc250-game-mode

# ── 7. Monitoring (btop / amdgpu_top / MangoHUD + fix util GPU 655%) ──────────
info "Monitoring : btop, htop, amdgpu_top, mangohud (rpm-ostree)..."
sudo rpm-ostree install btop htop amdgpu_top mangohud \
    || warn "Monitoring : certains paquets indispo via rpm-ostree — distrobox/brew/COPR."
BC250_GPUFIX="/opt/bc250-gpu-fix"
if [ ! -d "$BC250_GPUFIX" ]; then
    git clone --depth 1 https://github.com/ossini/bc250-gpu-fix "$BC250_GPUFIX" 2>/dev/null \
        || warn "Clone bc250-gpu-fix impossible (réseau) — à faire manuellement."
fi
if [ -d "$BC250_GPUFIX" ]; then
    if command -v cargo >/dev/null 2>&1; then
        ( cd "$BC250_GPUFIX" && cargo build --release \
          && sudo cp target/release/bc250-gpu-fix /usr/local/bin/ \
          && sudo cp bc250-gpu-fix.service /etc/systemd/system/ 2>/dev/null \
          && sudo systemctl daemon-reload \
          && sudo systemctl enable --now bc250-gpu-fix.service ) \
            || warn "bc250-gpu-fix : build/install a échoué — voir $BC250_GPUFIX/README."
    else
        warn "rust/cargo absent — build manuel de bc250-gpu-fix requis (binaire précompilé)."
    fi
fi

# ── 7b. System tuning : zswap + swapfile + mitigations (anti-crash RAM/VRAM) ───
# Sur 16 Go unifiés avec 4 Go CPU pour le serveur RAG, l'absence de swap/zswap
# fait planter Ollama/Postgres sur un pic mémoire. Important pour notre usage
# hybride (module 07 de bc250-beast). Nécessite reboot (rpm-ostree kargs).
info "System tuning : zswap + swapfile Btrfs + mitigations=off..."
sudo rpm-ostree kargs --append-if-missing="zswap.enabled=1" 2>/dev/null || warn "karg zswap.enabled non appliqué (reboot/ostree ?)"
sudo rpm-ostree kargs --append-if-missing="zswap.max_pool_percent=25" 2>/dev/null || true
sudo rpm-ostree kargs --append-if-missing="zswap.compressor=lz4" 2>/dev/null || true
sudo rpm-ostree kargs --append-if-missing="systemd.zram=0" 2>/dev/null || true
sudo rpm-ostree kargs --append-if-missing="mitigations=off" 2>/dev/null || warn "karg mitigations=off non appliqué"
sudo rpm-ostree initramfs --enable --arg=--add-drivers --arg=lz4 2>/dev/null || warn "initramfs lz4 : ignoré (peut déjà être présent)"

# Swapfile Btrfs 32G sur /var (procédure Bazzite officielle)
if findmnt -no FSTYPE /var 2>/dev/null | grep -qi btrfs; then
    info "Création swapfile Btrfs 32G sur /var/swap..."
    sudo btrfs subvolume create /var/swap 2>/dev/null || true
    sudo btrfs filesystem mkswapfile --size 32G /var/swap/swapfile 2>/dev/null \
        || warn "mkswapfile a échoué (espace ?) — swap non créé."
    if [ -f /var/swap/swapfile ]; then
        grep -q '/var/swap/swapfile' /etc/fstab 2>/dev/null || \
            echo '/var/swap/swapfile none swap defaults,nofail 0 0' | sudo tee -a /etc/fstab >/dev/null
        sudo swapon -a 2>/dev/null || true
        echo 'vm.swappiness=120' | sudo tee /etc/sysctl.d/99-swappiness.conf >/dev/null
        sudo sysctl -p /etc/sysctl.d/99-swappiness.conf 2>/dev/null || true
    fi
else
    warn "/var n'est pas Btrfs ici — créez un swapfile classique manuellement (zswap seul actif)."
fi

# lm_sensors (températures/voltage pour validate.sh)
sudo rpm-ostree install lm_sensors 2>/dev/null || warn "lm_sensors indispo (validate.sh perdra les températures)."

# ── 7c. Config du governor GPU cyan-skillfish (safe-points) ─────────────────────
info "Génération /etc/cyan-skillfish-governor/config.toml (safe-points 350->2000 MHz)..."
GPU_FREQ_MHZ="${GPU_FREQ_MHZ:-2000}"
sudo mkdir -p /etc/cyan-skillfish-governor
sudo tee /etc/cyan-skillfish-governor/config.toml >/dev/null <<EOF
# Généré par scripts/bazzite/setup.sh — tester la config manuellement avant boot auto.
target-temperature = 85

[[safe-points]]
frequency = 350
voltage = 700

[[safe-points]]
frequency = ${GPU_FREQ_MHZ}
EOF
info "Governor : editez config.toml et activez le service (systemctl enable --now cyan-skillfish-governor-smu)."

# ── 8. Memory OC (GDDR6) — optionnel, garde-fous stricts ──────────────────────
warn "Memory OC (GDDR6) NON automatisé par défaut. Sur Cyan Skillfish l'OD sysfs"
warn "est souvent absent : utilisez bc250-game-mode + le réglage BIOS/CMOS, ou"
warn "scripts/bc250/mem-oc/mem_oc.sh (teste l'OD sysfs, revert auto si instable)."

warn "REBOOT requis pour appliquer kargs + paquets rpm-ostree."
warn "Garde-fous : Vid CPU ≤ 1325 mV (brick) ; GPU ≤ 2,2-2,4 GHz air ; PSU ≥ 460 W."
warn "Stresser 40 CU + 8 cœurs AVANT prod. Tout est non testé sur machine réelle."
