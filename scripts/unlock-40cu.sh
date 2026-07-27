#!/usr/bin/env bash
# =============================================================================
# Prof IA — Déblocage 40 CU pour AMD BC-250 (Cyan Skillfish)
# =============================================================================
# Ce script NE réécrit PAS les registres GPU lui-même. Il clone et invoque
# l'outil communautaire maintenu par duggasco (patch noyau amdgpu + scripts
# de build), qui est la référence documentée sur :
#   https://elektricm.github.io/amd-bc250-docs/system/40cu-unlock/
#   https://github.com/duggasco/bc250-40cu-unlock
#
# AVANT DE LANCER CE SCRIPT, LISEZ CECI :
#   - Le module amdgpu est reconstruit hors-arbre. CHAQUE mise à jour du
#     noyau annule le patch (il faudra relancer ce script après un
#     `apt upgrade` qui touche le kernel).
#   - Tous les BC-250 ne se débloquent pas proprement : les cartes avec un
#     "harvest pattern" dispersé peuvent avoir des CUs réellement
#     défectueux. Ce script exécute cu_map.sh AVANT toute action pour vous
#     montrer votre pattern — lisez la sortie avant de continuer.
#   - Sustained load à 40 CU / 2 GHz fait throttle sur le radiateur stock.
#     Un plafond gouverneur à 1500 MHz est recommandé (voir la doc GPU
#     Governor du projet BC-250).
#   - Secure Boot doit être désactivé, ou vous devez signer le module vous-
#     même.
#   - C'est réversible : sauvegarde automatique du module d'origine, et
#     `disable`/`restore` pour revenir en arrière.
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

REPO_URL="https://github.com/duggasco/bc250-40cu-unlock.git"
WORK_DIR="${HOME}/.cache/bc250-40cu-unlock"
ENV_FILE="$(dirname "$0")/../.env"

# ── 0. Garde-fous ─────────────────────────────────────────────────────────────
if [[ "$(id -u)" -eq 0 ]]; then
    error "Ne lancez pas ce script en root direct — il utilise sudo lui-même quand nécessaire."
fi

if ! lspci -d 1002: 2>/dev/null | grep -qi "13fe\|Cyan Skillfish"; then
    warn "PCI device 0x13FE (BC-250) non détecté via lspci — le patch est gated sur cet ID."
    warn "Continuer quand même ? (Ctrl+C pour annuler, sinon 5s)"
    sleep 5
fi

for bin in gcc make zstd curl git; do
    command -v "$bin" &>/dev/null || error "$bin manquant. Installez-le avant de continuer."
done

if [[ ! -e /usr/lib/modules/$(uname -r)/build ]] && ! dpkg -l 2>/dev/null | grep -q "linux-headers-$(uname -r)"; then
    warn "linux-headers-$(uname -r) introuvable — installation..."
    sudo apt-get update -qq
    sudo apt-get install -y "linux-headers-$(uname -r)" build-essential
fi

# ── 1. Cloner / mettre à jour le repo duggasco ────────────────────────────────
info "1/5 Récupération de bc250-40cu-unlock..."
if [[ -d "$WORK_DIR" ]]; then
    git -C "$WORK_DIR" pull --ff-only
else
    git clone "$REPO_URL" "$WORK_DIR"
fi

# ── 2. Harvest pattern — À LIRE avant de continuer ────────────────────────────
info "2/5 Vérification du harvest pattern de votre carte..."
if [[ -x "$WORK_DIR/scripts/cu_map.sh" ]]; then
    "$WORK_DIR/scripts/cu_map.sh" || warn "cu_map.sh a échoué — vérifiez manuellement avant de continuer."
    echo ""
    warn "Pattern CONTIGU (CU 0-5 actifs, 6-9 fusionnés, identique sur les 4 shader arrays)"
    warn "  → déblocage 40 CU généralement propre."
    warn "Pattern DISPERSÉ → risque de CUs réellement défectueux, prévoir un test de"
    warn "  santé par WGP après coup (bc250-cu-health-test.sh + bc250-cu-mask.sh)."
    echo ""
    read -rp "Continuer avec le déblocage complet des 40 CU ? [o/N] " CONFIRM
    [[ "$CONFIRM" =~ ^[oOyY]$ ]] || { info "Annulé — aucune modification appliquée."; exit 0; }
else
    warn "cu_map.sh introuvable dans le repo — poursuite sans vérification du harvest pattern."
fi

# ── 3. Build + installation via le script officiel Debian/Ubuntu ─────────────
info "3/5 Build et installation du module amdgpu patché (Debian/Ubuntu)..."
cd "$WORK_DIR"
sudo ./scripts/bc250-enable-40cu.sh build
sudo ./scripts/bc250-enable-40cu.sh enable

warn "Un REBOOT est nécessaire pour charger le module patché."
read -rp "Redémarrer maintenant ? [o/N] " DO_REBOOT
if [[ "$DO_REBOOT" =~ ^[oOyY]$ ]]; then
    sudo reboot
    exit 0
else
    warn "N'oubliez pas de redémarrer, puis relancez ce script avec 'verify' :"
    warn "  $0 verify"
fi

# ── 4. Vérification post-reboot ───────────────────────────────────────────────
verify_unlock() {
    info "4/5 Vérification post-reboot..."
    local cu_count
    cu_count=$(sudo dmesg | grep -oP 'active_cu_number \K[0-9]+' | tail -1 || echo "")

    if [[ "$cu_count" == "40" ]]; then
        info "✅ 40 CUs actifs confirmés (dmesg: active_cu_number 40)."
        if command -v vulkaninfo &>/dev/null; then
            RADV_DEBUG=info vulkaninfo --summary 2>&1 | grep -i num_cu || true
        fi
        return 0
    elif [[ "$cu_count" == "24" ]]; then
        error "active_cu_number=24 — le module patché n'a pas chargé. Vérifiez /etc/modprobe.d/bc250-40cu.conf et Secure Boot."
    else
        error "Impossible de lire active_cu_number dans dmesg. Le patch n'a probablement pas chargé."
    fi
}

# ── 5. Mise à jour du .env du projet ──────────────────────────────────────────
update_env() {
    info "5/5 Mise à jour de $ENV_FILE..."
    if [[ -f "$ENV_FILE" ]]; then
        sed -i '/^AMD_RDNA2_CUS=/d;/^AMD_CU_UNLOCK_APPLIED=/d' "$ENV_FILE"
    fi
    {
        echo "AMD_RDNA2_CUS=40"
        echo "AMD_CU_UNLOCK_APPLIED=true"
    } >> "$ENV_FILE"
    info "✅ .env mis à jour (AMD_RDNA2_CUS=40, AMD_CU_UNLOCK_APPLIED=true)."
    warn "Pensez à plafonner le gouverneur GPU à 1500 MHz pour du sustained (voir"
    warn "docs/system/governor sur elektricm.github.io/amd-bc250-docs) — 2 GHz"
    warn "en continu fait throttle sur radiateur stock."
}

case "${1:-}" in
    verify)
        verify_unlock && update_env
        ;;
    disable|restore)
        sudo "$WORK_DIR/scripts/bc250-enable-40cu.sh" "$1"
        sed -i '/^AMD_RDNA2_CUS=/d;/^AMD_CU_UNLOCK_APPLIED=/d' "$ENV_FILE" 2>/dev/null || true
        echo "AMD_RDNA2_CUS=24" >> "$ENV_FILE"
        echo "AMD_CU_UNLOCK_APPLIED=false" >> "$ENV_FILE"
        info "Reverti au stock 24 CU. Redémarrez pour appliquer."
        ;;
    *)
        # Cas où le script n'a pas rebooté immédiatement plus haut
        ;;
esac
