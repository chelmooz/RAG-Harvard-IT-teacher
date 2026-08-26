#!/usr/bin/env bash
# =============================================================================
# BC-250 — Memory (GDDR6) Overclock — MÉTHODE SYSFS AMDGPU OD (si disponible)
# -----------------------------------------------------------------------------
# ⚠️  OC MÉMOIRE = risque d'instabilité système / crash (pas de brick MCU, mais
#     possible corruption). Incréments MINCES + test de stabilité + revert auto.
#
# Sur Cyan Skillfish (gfx1013), l'OD sysfs est souvent ABSENT. Dans ce cas,
# l'OC mémoire se fait via le réglage « memory clock » du BIOS/CMOS (manuel)
# ou via un message SMU mémoire VÉRIFIÉ (non automatisé ici).
# =============================================================================
set -uo pipefail

CARD_PATH=$(ls -d /sys/class/drm/card*/device 2>/dev/null | head -1)
OD="${CARD_PATH:+${CARD_PATH}/pp_od_clk_voltage}"
STEP="${1:-50}"   # MHz par incrément (défaut +50)

if [ -z "$OD" ] || [ ! -w "$OD" ]; then
    echo "OD sysfs ($OD) indisponible sur Cyan Skillfish."
    echo "→ Memory OC sysfs NON supporté ici."
    echo "  Options :"
    echo "    1) BIOS/CMOS : régler 'memory clock' manuellement (recommandé)."
    echo "    2) Message SMU mémoire VÉRIFIÉ sur TA silicon — à coder dans smu-oc."
    exit 2
fi

CUR=$(awk '/MCLK|mclk/{print $2; exit}' "$OD" 2>/dev/null | grep -oP '\d+')
CUR=${CUR:-?}
echo "MCLK actuel : ${CUR} MHz — tentative +${STEP} MHz"

# Commandes OD AMDGPU standard (peuvent varier selon le driver) :
echo "s ${STEP}" > "$OD"     # set memory OD delta
echo "c"        > "$OD"     # commit
echo "m 1"      > "$OD"     # apply profile 1

# Test de stabilité léger (échoue vite si mémoire instable)
if command -v stress-ng >/dev/null 2>&1; then
    if ! stress-ng --vm 1 --vm-bytes 1G --timeout 10s >/dev/null 2>&1; then
        echo "Instabilité détectée → REVERT"
        echo "r" > "$OD"; echo "c" > "$OD"
        exit 1
    fi
else
    echo "stress-ng absent — validation manuelle requise (jeu/benchmark)."
fi

echo "✅ OC mémoire posé (+${STEP} MHz). Valide AVANT prod (jeu 10 min + benchmark)."
echo "    Revert manuel : echo 'r' > $OD ; echo 'c' > $OD"
