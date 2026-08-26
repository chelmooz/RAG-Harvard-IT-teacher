#!/usr/bin/env bash
# =============================================================================
# BC-250 — Orchestrateur Phase 1 (userspace, sans rebuild noyau)
# -----------------------------------------------------------------------------
# Applique dans l'ordre : 40 CU (UMR) → 8 cœurs (SMU) → UV/OC CPU (SMU).
# Idempotent. Chaque étape échoue « soft » (WARN) sans brick : les garde-fous
# sont dans chaque script vendored. En fin, lance le health-check ; si celui-ci
# échoue, le script sort en erreur → systemd (Restart=on-failure) retente.
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0

echo "=== BC-250 Phase 1 : 40 CU (UMR) ==="
sudo bash "$SCRIPT_DIR/40cu-unlock/bc250-cu-live-manager.sh" \
    || { echo "WARN : 40 CU non appliqué"; fail=1; }

echo "=== BC-250 Phase 1 : 8 cœurs Zen2 (SMU) ==="
sudo python3 "$SCRIPT_DIR/core-unlock/bc250-unlock-cores.py" \
    || { echo "WARN : 8 cœurs non appliqués"; fail=1; }

echo "=== BC-250 Phase 1 : UV/OC CPU (SMU) ==="
sudo python3 "$SCRIPT_DIR/smu-oc/bc250_apply.py" \
    || { echo "WARN : UV/OC CPU non appliqué"; fail=1; }

echo "=== Vérification (health-check) ==="
"$SCRIPT_DIR/health-check.sh" \
    || { echo "HEALTHCHECK ÉCHEC — optimisations non effectives"; exit 1; }

echo "✅ Phase 1 appliquée (fail=$fail). Stresser avant mise en prod."
exit 0
