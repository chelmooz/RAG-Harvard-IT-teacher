#!/usr/bin/env bash
# =============================================================================
# BC-250 — Orchestrateur Phase 1 (userspace, sans rebuild noyau)
# -----------------------------------------------------------------------------
# Applique dans l'ordre : 40 CU (UMR) -> 8 coeurs (SMU) -> UV/OC CPU (SMU).
# CORRECTION (2026-08-26) : les outils vendored REQUIERENT une sous-commande
# explicite. Sans elle : le CU manager ouvrait un menu interactif (plantage en
# systemd), core-unlock levait une RuntimeError, et bc250_apply.py ne faisait
# rien. On appelle désormais les sous-commandes documentées + persistance.
#
# Idempotent. Chaque étape échoue « soft » (WARN) sans brick : les garde-fous
# sont dans chaque script vendored. En fin, lance le health-check ; si celui-ci
# échoue, le script sort en erreur -> systemd (Restart=on-failure) retente.
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0

# Sweet spots génériques (Old Lamer). Overridables via env pour le réglage fin.
BC250_CPU_FREQ_MHZ="${BC250_CPU_FREQ_MHZ:-3850}"
BC250_CPU_VID_MV="${BC250_CPU_VID_MV:-1150}"
BC250_CPU_TEMP_C="${BC250_CPU_TEMP_C:-90}"
BC250_OC_CONF="${BC250_OC_CONF:-/etc/bc250-smu-oc.conf}"

CU_TOOL="$SCRIPT_DIR/40cu-unlock/bc250-cu-live-manager.sh"
CORE_TOOL="$SCRIPT_DIR/core-unlock/bc250-unlock-cores.py"
OC_DETECT="$SCRIPT_DIR/smu-oc/bc250_detect.py"
OC_APPLY="$SCRIPT_DIR/smu-oc/bc250_apply.py"

step() { echo "=== $* ==="; }

# ── 40 CU (UMR) ────────────────────────────────────────────────────────────────
step "BC-250 Phase 1 : 40 CU (UMR)"
if ! command -v umr >/dev/null 2>&1; then
    warn() { echo "[WARN] $*"; }
    warn "umr absent — tentative d'install via l'outil intégré..."
    sudo bash "$CU_TOOL" install-umr \
        || warn "install-umr a échoué (réseau ?) — 40 CU non appliqué cette fois."
fi
sudo bash "$CU_TOOL" enable all \
    || { echo "WARN : 40 CU non appliqué"; fail=1; }
# Sauvegarde la table WGP courante comme profil de boot (ré-appliquée par notre
# service systemd à chaque démarrage). On ne crée PAS le service propre à l'outil
# pour éviter un double service systemd.
sudo bash "$CU_TOOL" write-service-table || true

# ── 8 coeurs Zen2 (SMU) ─────────────────────────────────────────────────────────
step "BC-250 Phase 1 : 8 coeurs Zen2 (SMU)"
sudo python3 "$CORE_TOOL" apply \
    || { echo "WARN : 8 coeurs non appliqués"; fail=1; }

# ── UV/OC CPU (SMU) ─────────────────────────────────────────────────────────────
step "BC-250 Phase 1 : UV/OC CPU (SMU)"
# bc250_detect génère le fichier de conf (frequency/scale/max_temperature) en
# appliquant live ; bc250_apply --apply le ré-applique depuis la conf sauvegardée.
if [ ! -f "$BC250_OC_CONF" ]; then
    sudo python3 "$OC_DETECT" \
        --frequency "$BC250_CPU_FREQ_MHZ" \
        --vid "$BC250_CPU_VID_MV" \
        --temp "$BC250_CPU_TEMP_C" \
        --keep -c "$BC250_OC_CONF" \
        || { echo "WARN : génération conf OC échouée"; fail=1; }
fi
if [ -f "$BC250_OC_CONF" ]; then
    sudo python3 "$OC_APPLY" --apply "$BC250_OC_CONF" \
        || { echo "WARN : UV/OC CPU non appliqué"; fail=1; }
else
    echo "WARN : pas de conf OC -> UV/OC CPU ignoré"
    fail=1
fi

# ── Vérification ────────────────────────────────────────────────────────────────
step "Vérification (health-check)"
"$SCRIPT_DIR/health-check.sh" \
    || { echo "HEALTHCHECK ÉCHEC — optimisations non effectives"; exit 1; }

echo "✅ Phase 1 appliquée (fail=$fail). Stresser avant mise en prod."
exit 0
