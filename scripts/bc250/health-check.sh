#!/usr/bin/env bash
# =============================================================================
# BC-250 — Health-check des optimisations (systemd / validation manuelle)
# -----------------------------------------------------------------------------
# Sort 0 si 40 CU + 8 cœurs détectés, sinon 1 (déclenche Restart=on-failure).
# Ajouts (2026-08-26) : détection VRAM BIOS, état des services, garde-fou
# tension CPU (warning). Le code de sortie reste basé sur CU + cœurs uniquement
# pour ne pas faire bootloop sur une lecture capteur temporairement indisponible.
# =============================================================================
set -uo pipefail

EXPECTED_CU=40
EXPECTED_CORES=8
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CU=$(sudo dmesg 2>/dev/null | grep -oP 'active_cu_number[=: ]+\K[0-9]+' | tail -1)
CU=${CU:-0}
CORES=$(nproc)

echo "CU détectés : $CU (attendu $EXPECTED_CU) | cœurs : $CORES (attendu $EXPECTED_CORES)"

# VRAM BIOS (warn only) — 512 Mo attendu pour le split dynamique RAM/VRAM
if lspci -v 2>/dev/null | grep -qiE 'memory.*(512m|524288k)'; then
    echo "✓ VRAM BIOS : 512 Mo détectée"
else
    echo "⚠ VRAM BIOS : 512 Mo NON détectée (régler dans le menu BIOS / module 02 si besoin)"
fi

# État des services systemd (info)
for svc in bc250-optimizations.service cyan-skillfish-governor-smu; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo "✓ service $svc : actif"
    elif systemctl is-enabled --quiet "$svc" 2>/dev/null; then
        echo "⚠ service $svc : activé mais inactif"
    else
        echo "⚠ service $svc : absent/inactif"
    fi
done

# Garde-fou tension CPU (warn) — seuil dur 1300 mV (brick). Lecture via sensors Vcore.
if command -v sensors >/dev/null 2>&1; then
    VCORE=$(sensors 2>/dev/null | grep -iE '(vcore|in0|cpu voltage)' | grep -oE '[0-9]+\.[0-9]+' | head -1)
    if [ -n "$VCORE" ]; then
        VCORE_MV=$(awk "BEGIN{printf \"%d\", $VCORE*1000+0.5}")
        if [ "$VCORE_MV" -gt 1300 ]; then
            echo "❌ TENSION CPU > 1300 mV ($VCORE_MV mV) — RISQUE BRICK !"
        else
            echo "✓ Tension CPU Vcore : $VCORE_MV mV (seuil dur 1300 mV)"
        fi
    fi
fi

if [ "$CU" -ge "$EXPECTED_CU" ] && [ "$CORES" -ge "$EXPECTED_CORES" ]; then
    echo "✅ Health-check OK"
    exit 0
else
    echo "❌ Health-check ÉCHEC (CU=$CU, cores=$CORES)"
    exit 1
fi
