#!/usr/bin/env bash
# =============================================================================
# BC-250 — Health-check des optimisations (pour systemd / validation manuelle)
# -----------------------------------------------------------------------------
# Sort 0 si 40 CU + 8 cœurs détectés, sinon 1.
#   - CU  : via dmesg (amdgpu « active_cu_number »)
#   - CPU : via nproc (8 cœurs attendus après déblocage SMU)
# =============================================================================
set -uo pipefail

EXPECTED_CU=40
EXPECTED_CORES=8

CU=$(sudo dmesg 2>/dev/null | grep -oP 'active_cu_number[=: ]+\K[0-9]+' | tail -1)
CU=${CU:-0}
CORES=$(nproc)

echo "CU détectés : $CU (attendu $EXPECTED_CU) | cœurs : $CORES (attendu $EXPECTED_CORES)"

if [ "$CU" -ge "$EXPECTED_CU" ] && [ "$CORES" -ge "$EXPECTED_CORES" ]; then
    echo "✅ Health-check OK"
    exit 0
else
    echo "❌ Health-check ÉCHEC (CU=$CU, cores=$CORES)"
    exit 1
fi
