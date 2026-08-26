#!/usr/bin/env bash
# =============================================================================
# BC-250 — Validation & Benchmark (équivalent module 09 de bc250-beast)
# -----------------------------------------------------------------------------
# Batterie de tests non-bloquants + tests de stabilité optionnels (stress-ng /
# FurMark). Le garde-fou TENSION CPU est DUR : > 1300 mV => FAIL (risque brick).
# Ne pas lancer depuis systemd (les stress tests bloqueraient le boot) : à jouer
# manuellement après apply_phase1, ou via `bc250-game-mode validate`.
#
# Usage : sudo ./validate.sh [--yes]   (--yes = non-interactif sur valeurs par défaut)
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CU_TOOL="$SCRIPT_DIR/40cu-unlock/bc250-cu-live-manager.sh"

# Valeurs cibles (surchargeables via env, cf bc250-beast.conf.example)
CPU_FREQ_MHZ="${CPU_FREQ_MHZ:-3850}"
CPU_VID_MV="${CPU_VID_MV:-1150}"
GPU_FREQ_MHZ="${GPU_FREQ_MHZ:-2000}"
BIOS_TARGET_VRAM_MB="${BIOS_TARGET_VRAM_MB:-512}"

BC250_YES="${BC250_YES:-0}"
DRY_RUN="${DRY_RUN:-0}"

PASS=0; FAIL=0; WARN=0

C_GREEN='\033[0;32m'; C_RED='\033[0;31m'; C_YELLOW='\033[1;33m'; C_NC='\033[0m'
pass() { PASS=$((PASS+1)); printf "  ${C_GREEN}✓${C_NC} %-42s %s\n" "$1" "${2:-}"; }
fail() { FAIL=$((FAIL+1)); printf "  ${C_RED}✗${C_NC} %-42s %s\n" "$1" "${2:-}"; }
warn() { WARN=$((WARN+1)); printf "  ${C_YELLOW}⚠${C_NC} %-42s %s\n" "$1" "${2:-}"; }

confirm() {
    local p="${1:-Continuer ?}"
    [[ "$BC250_YES" == "1" || "$DRY_RUN" == "1" ]] && return 0
    read -rp "$(printf "${C_YELLOW}%s [y/N] : ${C_NC}" "$p")" a
    [[ "$a" =~ ^[Yy]$ ]]
}

echo
printf "${C_GREEN}=== VALIDATION BC-250 ===${C_NC}\n"

# 1) CPU cores
threads=$(nproc)
if [[ "$threads" -eq 16 ]]; then pass "CPU : 16 threads / 8 cœurs" "$threads";
elif [[ "$threads" -eq 8 ]]; then warn "CPU : 8 threads (déblocage 8c non appliqué)" "$threads";
else fail "CPU : threads inattendus" "$threads"; fi

# 2) CPU freq
cf=$(awk -F: '/^cpu MHz/ {print int($2+0.5); exit}' /proc/cpuinfo 2>/dev/null)
if [[ -n "$cf" && "$cf" -gt 0 ]]; then
    d=$(( cf > CPU_FREQ_MHZ ? cf - CPU_FREQ_MHZ : CPU_FREQ_MHZ - cf ))
    if [[ $d -le 100 ]]; then pass "CPU fréq (~${CPU_FREQ_MHZ} MHz)" "${cf} MHz";
    elif [[ $d -le 200 ]]; then warn "CPU fréq (écart ${d} MHz)" "${cf} MHz";
    else warn "CPU fréq (écart ${d} MHz)" "${cf} MHz"; fi
else warn "CPU fréq" "illisible (/proc/cpuinfo)"; fi

# 3) GPU CU actives
if [[ -x "$CU_TOOL" ]]; then
    out=$(bash "$CU_TOOL" status 2>/dev/null || true)
    acu=$(echo "$out" | grep -oE '[0-9]+[[:space:]]*CU' | head -1 | grep -oE '[0-9]+' || echo "?")
    if [[ "$acu" == "40" ]]; then pass "GPU CU actives" "40 CU";
    elif [[ "$acu" == "24" ]]; then warn "GPU CU : 24 (usine, mode factory)" "$acu CU";
    elif [[ "$acu" != "?" ]]; then warn "GPU CU actives" "$acu CU (attendu 40)";
    else warn "GPU CU actives" "imparsable"; fi
else warn "GPU CU actives" "bc250-cu-live-manager absent"; fi

# 4) Services
for svc in bc250-optimizations.service cyan-skillfish-governor-smu; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then pass "service $svc" "actif";
    elif systemctl is-enabled --quiet "$svc" 2>/dev/null; then warn "service $svc" "activé/inactif";
    else warn "service $svc" "inactif/absent"; fi
done

# 5) VRAM BIOS
vram=0
lo=$(lspci -v 2>/dev/null | grep -iE 'memory.*(512m|524288k)' | head -1)
hi=$(lspci -v 2>/dev/null | grep -iE 'memory.*(8g|8192m|8388608k)' | head -1)
[[ -n "$lo" ]] && vram=512; [[ -n "$hi" ]] && vram=8192
if [[ "$vram" -eq "$BIOS_TARGET_VRAM_MB" ]]; then pass "VRAM BIOS (${BIOS_TARGET_VRAM_MB} Mo)" "${vram} Mo";
elif [[ "$vram" -eq 8192 ]]; then warn "VRAM BIOS : 8 Go (défaut usine)" "basculer 512 Mo (module 02)";
elif [[ "$vram" -gt 0 ]]; then warn "VRAM BIOS" "${vram} Mo (attendu ${BIOS_TARGET_VRAM_MB})";
else warn "VRAM BIOS" "indéterminée"; fi

# 6) Températures
if command -v sensors >/dev/null 2>&1; then
    so=$(sensors 2>/dev/null || true)
    ct=$(echo "$so" | grep -iE '^(k10temp|cpu|package).*[0-9]+\.[0-9]+°c' | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1 | awk '{print int($1+0.5)}')
    gt=$(echo "$so" | grep -iE '^(amdgpu|edge|junction).*[0-9]+\.[0-9]+°c' | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1 | awk '{print int($1+0.5)}')
    if [[ -n "$ct" ]]; then
        if [[ "$ct" -le 85 ]]; then pass "Temp CPU (≤85°C)" "${ct}°C"; else warn "Temp CPU (>85°C)" "${ct}°C"; fi
    else warn "Temp CPU" "non détectée (sensors)"; fi
    if [[ -n "$gt" ]]; then
        if [[ "$gt" -le 80 ]]; then pass "Temp GPU (≤80°C)" "${gt}°C"; else warn "Temp GPU (>80°C)" "${gt}°C"; fi
    else warn "Temp GPU" "non détectée (sensors)"; fi
else warn "Températures" "sensors indispo (lm_sensors)"; fi

# 7) TENSION CPU — GARDE-FOU DUR (>1300 mV = brick)
vcore_mv=0
if command -v sensors >/dev/null 2>&1; then
    vc=$(sensors 2>/dev/null | grep -iE '(vcore|in0|cpu voltage)' | grep -oE '[0-9]+\.[0-9]+' | head -1)
    [[ -n "$vc" ]] && vcore_mv=$(awk "BEGIN{printf \"%d\", $vc*1000+0.5}")
fi
if [[ "$vcore_mv" -gt 0 ]]; then
    if [[ "$vcore_mv" -gt 1300 ]]; then fail "TENSION CPU > 1300 mV (BRICK!)" "${vcore_mv} mV";
    else pass "Tension CPU (≤1300 mV)" "${vcore_mv} mV"; fi
else warn "Tension CPU" "non lisible (sensors Vcore) — vérifier manuellement"; fi

# 8) Fréquence GPU
gf=0
dpm="/sys/class/drm/card0/device/pp_dpm_sclk"
if [[ -r "$dpm" ]]; then gf=$(grep '\*' "$dpm" | grep -oE '[0-9]+' | head -1); fi
if [[ "$gf" -gt 0 ]]; then
    d=$(( gf > GPU_FREQ_MHZ ? gf - GPU_FREQ_MHZ : GPU_FREQ_MHZ - gf ))
    if [[ $d -le 100 ]]; then pass "GPU fréq (~${GPU_FREQ_MHZ} MHz)" "${gf} MHz";
    else warn "GPU fréq (écart ${d} MHz)" "${gf} MHz"; fi
else warn "GPU fréq" "illisible (pp_dpm_sclk)"; fi

# ── Tests de stabilité (optionnels) ──────────────────────────────────────────────
echo
printf "${C_GREEN}=== STABILITÉ (optionnel) ===${C_NC}\n"
if confirm "Lancer stress-ng CPU (300s) + FurMark GPU ?"; then
    if command -v stress-ng >/dev/null 2>&1; then
        if stress-ng --cpu "$(nproc)" --timeout 300s --metrics-brief 2>/dev/null; then
            pass "Stabilité CPU (stress-ng 300s)" "OK"; else fail "Stabilité CPU" "échec"; fi
    else warn "Stabilité CPU" "stress-ng absent (pkg_install stress-ng)"; fi
    if command -v FurMark >/dev/null 2>&1; then
        if FurMark -t 300 2>/dev/null; then pass "Stabilité GPU (FurMark 300s)" "OK"; else fail "Stabilité GPU" "échec"; fi
    else warn "Stabilité GPU" "FurMark absent (ignoré)"; fi
else
    warn "Stabilité" "ignorée (choix utilisateur)"
fi

# ── Rapport ──────────────────────────────────────────────────────────────────────
total=$((PASS+FAIL+WARN))
score=$(( total > 0 ? PASS*100/total : 0 ))
echo
printf "╔══════════════════════════════════════╗\n"
printf "║  Rapport BC-250 : %2d✓  %2d⚠  %2d✗  (score %d%%)  ║\n" "$PASS" "$WARN" "$FAIL" "$score"
printf "╚══════════════════════════════════════╝\n"
if [[ $FAIL -gt 0 ]]; then
    echo "Recommandations :"
    echo "  • 8c/40CU non appliqués   -> relancer apply_phase1 (sudo /opt/bc250/apply_phase1.sh)"
    echo "  • services inactifs       -> journalctl -u <svc>"
    echo "  • VRAM ≠ 512 Mo           -> module 02 (BIOS) / menu BIOS"
    echo "  • TENSION > 1300 mV       -> DANGER : baisser le UV/OC CPU immédiatement"
fi
[[ $FAIL -gt 0 ]] && exit 1
exit 0
