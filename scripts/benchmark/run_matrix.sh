#!/usr/bin/env bash
# run_matrix.sh — orchestrate the T0.-1 matrix. Measurement lives in
# fit_campaign.sh; this file only sequences configurations and decides whether
# the diagnostic fallback is warranted.
#
# READ-ONLY: it changes nothing on the host.
#
# Usage: sudo ./run_matrix.sh [--requests N] [--out DIR] [--llama-bin PATH]
#                              [--model-path PATH] [--port N] [--health-timeout N]
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIT="$HERE/fit_campaign.sh"

REQUESTS="${FIT_REQUESTS:-10}"
# Reports default outside the repository: campaign artifacts are evidence, not
# project files, and must not pollute the deployment repo's git status.
OUT="${FIT_OUT:-$HOME/profia-fit-artifacts}"
LLAMA_BIN="${FIT_LLAMA_BIN:-/opt/llama.cpp/build/bin/llama-server}"
MODEL_PATH="${FIT_MODEL_PATH:-/var/lib/profia-llama/models/google_gemma-4-26B-A4B-it-IQ3_XS.gguf}"
BASE_PORT="${FIT_BASE_PORT:-8081}"
HEALTH_TIMEOUT="${FIT_HEALTH_TIMEOUT:-60}"

# The partial-offload probe only answers one question: does the configuration
# fail because memory or the GPU cannot take the full offload? A verdict that
# says nothing about memory or the GPU must not trigger it, or the extra run
# just adds a misleading data point about a different setup.
#
#   OOM_KILL      the kernel killed the process under memory pressure
#   GPU_RESET     the GPU hung or was reset
#   INCONCLUSIVE  memory could not be characterised, so memory is unresolved
#
# Deliberately excluded:
#   STARTUP_FAIL    binary, flags or model problem, not a memory signal
#   HTTP_FAIL       the server answered but not usably; offload is not the cause
#   GENERATION_FAIL the server generated nothing; offload is not the cause
FALLBACK_TRIGGERS="${FIT_FALLBACK_TRIGGERS:-OOM_KILL GPU_RESET INCONCLUSIVE}"
FALLBACK_NGL="${FIT_FALLBACK_NGL:-40}"

while [ $# -gt 0 ]; do
  case "$1" in
    --requests)      REQUESTS="${2-}"; shift 2 ;;
    --out)           OUT="${2-}"; shift 2 ;;
    --llama-bin)     LLAMA_BIN="${2-}"; shift 2 ;;
    --model-path)    MODEL_PATH="${2-}"; shift 2 ;;
    --port)          BASE_PORT="${2-}"; shift 2 ;;
    --health-timeout) HEALTH_TIMEOUT="${2-}"; shift 2 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 64 ;;
  esac
done

mkdir -p "$OUT" || exit 1
SUMMARY="$OUT/summary.jsonl"
: > "$SUMMARY"

PORT="$BASE_PORT"

run() { # run LABEL CTX KV NGL
  local label="$1" ctx="$2" kv="$3" ngl="$4"
  printf '\n\033[1;36m=== %s  ctx=%s kv=%s ngl=%s ===\033[0m\n' "$label" "$ctx" "$kv" "$ngl"

  FIT_HEALTH_TIMEOUT="$HEALTH_TIMEOUT" "$FIT" \
    --label "$label" --ctx "$ctx" --kv "$kv" --ngl "$ngl" \
    --requests "$REQUESTS" --port "$PORT" \
    --llama-bin "$LLAMA_BIN" --model-path "$MODEL_PATH" \
    >"$OUT/$label.json" 2>"$OUT/$label.log"
  local code=$?
  PORT=$(( PORT + 1 ))

  local verdict="NO_REPORT"
  [ -s "$OUT/$label.json" ] && verdict=$(jq -r '.verdict // "NO_REPORT"' "$OUT/$label.json" 2>/dev/null)
  [ "$verdict" = "null" ] && verdict="NO_REPORT"

  jq -nc --arg label "$label" --arg verdict "$verdict" --argjson code "$code" \
         --argjson ctx "$ctx" --arg kv "$kv" --argjson ngl "$ngl" \
         '{label:$label, verdict:$verdict, exit_code:$code,
           config:{ctx:$ctx, kv:$kv, ngl:$ngl}}' >> "$SUMMARY"

  printf 'verdict=%s exit=%s  report=%s  log=%s\n' \
         "$verdict" "$code" "$OUT/$label.json" "$OUT/$label.log"
  return 0
}

is_fallback_trigger() {
  local candidate="$1" trigger
  for trigger in $FALLBACK_TRIGGERS; do
    [ "$candidate" = "$trigger" ] && return 0
  done
  return 1
}

# ---- the four main configurations, in order --------------------------------
run ctx4k_q4 4096 q4_0 999
run ctx8k_q4 8192 q4_0 999
run ctx4k_q8 4096 q8_0 999
run ctx8k_q8 8192 q8_0 999

# ---- diagnostic fallback, only on a memory or GPU failure ------------------
FALLBACK_REASON=""
while IFS= read -r v; do
  if is_fallback_trigger "$v"; then
    FALLBACK_REASON="$FALLBACK_REASON ${v}"
  fi
done < <(jq -r '.verdict' "$SUMMARY")

if [ -n "${FALLBACK_REASON// /}" ]; then
  printf '\n\033[1;33m--- diagnostic fallback: partial offload (%s) ---\033[0m\n' "${FALLBACK_REASON# }"
  run ngl_partial 4096 q4_0 "$FALLBACK_NGL"
else
  printf '\n\033[1;32m--- no memory or GPU failure: partial offload not attempted ---\033[0m\n'
fi

printf '\n\033[1m=== matrix complete ===\n'
printf 'reports: %s\nsummary: %s\n' "$OUT" "$SUMMARY"
jq -s '.' "$SUMMARY"
exit 0