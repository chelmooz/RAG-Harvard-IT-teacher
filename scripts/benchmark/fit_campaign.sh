#!/usr/bin/env bash
# fit_campaign.sh — Measure ONE llama.cpp configuration on BC-250 (READ-ONLY).
#
# Measures; never reconfigures. No writes to /sys or /proc, no kernel args, no
# voltage or CU changes, no privilege escalation. A JSON report goes to stdout;
# human diagnostics go to stderr.
#
# One trial = ONE streaming request. Token counts come from the usage block;
# throughput prefers llama.cpp native timings when the server exposes them and
# falls back to chunk arrival timestamps otherwise.
#
# Exit code encodes the verdict:
#   0  GREEN           every trial generated tokens, no OOM, no GPU reset,
#                     every mandatory metric was readable
#   1  GENERATION_FAIL server answered but produced no tokens
#   2  STARTUP_FAIL    llama-server never became healthy
#   3  HTTP_FAIL       no trial obtained a usable HTTP response
#   4  OOM_KILL        kernel logged an OOM inside the measurement window
#   5  GPU_RESET       kernel logged a GPU reset inside the measurement window
#   6  INCONCLUSIVE    a mandatory metric was unreadable, so memory could not
#                     be characterised (advisory metrics never cause this)
#  64  bad arguments
#  65  missing binary, model, or tool
set -euo pipefail

LABEL=""; CTX=""; KV=""; NGL=""; REQUESTS=10
HOST="127.0.0.1"; PORT=8081
# Candidate model for the pre-deployment qualification campaign.
# Not a production validation: see docs/architecture/PROF-IA-v1.4-master.md.
MODEL_PATH="${FIT_MODEL_PATH:-/var/lib/profia-llama/models/Qwen2.5-7B-Instruct-Q6_K.gguf}"
MODEL_NAME=""
LLAMA_BIN="${FIT_LLAMA_BIN:-/opt/llama.cpp/build/bin/llama-server}"
SYS_ROOT="${FIT_SYS_ROOT:-}"
DMESG_FILE="${FIT_DMESG_FILE:-}"
HEALTH_TIMEOUT="${FIT_HEALTH_TIMEOUT:-60}"
MAX_TOKENS=128
PROMPT='Count from 1 to 100.'

while [ $# -gt 0 ]; do
  case "$1" in
    --label)      LABEL="${2-}"; shift 2 ;;
    --ctx)        CTX="${2-}"; shift 2 ;;
    --kv)         KV="${2-}"; shift 2 ;;
    --ngl)        NGL="${2-}"; shift 2 ;;
    --requests)   REQUESTS="${2-}"; shift 2 ;;
    --host)       HOST="${2-}"; shift 2 ;;
    --port)       PORT="${2-}"; shift 2 ;;
    --model-path) MODEL_PATH="${2-}"; shift 2 ;;
    --model-name) MODEL_NAME="${2-}"; shift 2 ;;
    --llama-bin)  LLAMA_BIN="${2-}"; shift 2 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 64 ;;
  esac
done

die()  { printf '%s\n' "$1" >&2; exit "${2:-1}"; }
note() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$1" >&2; }

# ---- argument validation ---------------------------------------------------
[ -n "$LABEL" ] && [ -n "$CTX" ] && [ -n "$KV" ] && [ -n "$NGL" ] \
  || die "missing required --label/--ctx/--kv/--ngl" 64
case "$KV" in q4_0|q8_0) ;; *) die "invalid --kv: $KV (expected q4_0 or q8_0)" 64 ;; esac
case "$CTX" in ''|*[!0-9]*) die "invalid --ctx: $CTX (expected integer)" 64 ;; esac
case "$NGL" in ''|*[!0-9]*) die "invalid --ngl: $NGL (expected integer)" 64 ;; esac
case "$REQUESTS" in ''|*[!0-9]*|0) die "invalid --requests: $REQUESTS (expected >= 1)" 64 ;; esac

[ -x "$LLAMA_BIN" ] || die "llama-server not executable: $LLAMA_BIN" 65
[ -f "$MODEL_PATH" ] || die "model not found: $MODEL_PATH" 65
command -v jq    >/dev/null || die "jq is required" 65
command -v curl  >/dev/null || die "curl is required" 65
command -v awk   >/dev/null || die "awk is required" 65

# The OpenAI-compatible "model" field identifies the candidate in the request
# and in the report. Derive it from the real file so it cannot drift from what
# is actually loaded.
[ -n "$MODEL_NAME" ] || MODEL_NAME=$(basename "$MODEL_PATH" .gguf)
MODEL_SIZE_BYTES=$(stat -c%s "$MODEL_PATH" 2>/dev/null || echo null)

WORK="${TMPDIR:-/tmp}/fit_$$"
mkdir -p "$WORK"
RAW="$WORK/stream.tsv"
HDRS="$WORK/headers.txt"
LLAMA_LOG="$WORK/llama.log"

# ---- helpers ---------------------------------------------------------------
ms()      { date +%s%3N; }
uptime()  { awk '{printf "%d", $1 * 1000}' "${SYS_ROOT}/proc/uptime" 2>/dev/null || echo null; }
read_metric() { [ -f "$1" ] && cat "$1" || echo null; }
kernel_log() { if [ -n "$DMESG_FILE" ]; then cat "$DMESG_FILE"; else dmesg -T -k 2>/dev/null || true; fi; }
meminfo_kib() {
  # FIT_NO_MEMINFO simulates a kernel that does not expose /proc/meminfo, so
  # the mandatory-metric-missing path is reachable without patching the host.
  [ "${FIT_NO_MEMINFO:-0}" = "1" ] && { echo null; return; }
  # /proc/meminfo keys carry a trailing colon: "MemAvailable:".
  awk -v k="$1:" '$1==k{print $2}' "${SYS_ROOT}/proc/meminfo" 2>/dev/null || echo null
}

# Unit conversions. The three sources are in different units and mixing them is
# a silent-corruption bug, so each gets its own converter.
kib_to_mib()   { local v="${1:-}"; if [ -z "$v" ] || [ "$v" = null ]; then echo null; else echo $(( v / 1024 )); fi; }
bytes_to_mib() { local v="${1:-}"; if [ -z "$v" ] || [ "$v" = null ]; then echo null; else echo $(( v / 1024 / 1024 )); fi; }
millideg()     { local v="${1:-}"; if [ -z "$v" ] || [ "$v" = null ]; then echo null; else echo $(( v / 1000 )); fi; }

# Kernel-log signatures. These must cover what the kernel actually prints:
# "Out of memory: Killed process N", "oom_reaper: ...", "oom_kill: Restricting
# process to...". Matching only one of them silently under-counts.
OOM_RE='out of memory|oom_kill|oom_reaper'
RST_RE='gpu reset|ring .*timeout|amdgpu.*reset'

# Only kernel lines produced after the baseline snapshot belong to this run.
kernel_new_lines() { kernel_log | tail -n "+$(( KERNEL_LINES_BASE + 1 ))"; }
count_new() { kernel_new_lines | grep -Eic "$1" || true; }

# ---- report ----------------------------------------------------------------
REQ_JSON='[]'; SUMMARY_JSON='{}'; FLAGS='[]'
GPU_LAYERS=0; HEALTH_LATENCY_MS=null; STARTUP_OK=false
OOM_COUNT=0; RESET_COUNT=0
MEM_AVAIL_BASE=null; SWAP_FREE_BASE=null
VRAM_BASE=null; GTT_BASE=null; TEMP_BASE=null
WALL_LAUNCH=null; UPTIME_LAUNCH=null; UPTIME_END=null
KERNEL_LINES_BASE=0
KERNEL_OOM_BASE=0; KERNEL_RST_BASE=0

report() { # report VERDICT EXIT [flags]
  jq -n \
    --arg label "$LABEL" \
    --arg verdict "${1}" \
    --argjson exit_code "${2}" \
    --argjson flags "${3:-$FLAGS}" \
    --arg llama_version "${LLAMA_VERSION:-unknown}" \
    --arg llama_help_hash "${LLAMA_HELP_HASH:-}" \
    --arg model_sha256 "${MODEL_SHA:-}" \
    --arg model_name "${MODEL_NAME:-unknown}" \
    --arg model_file "$(basename "$MODEL_PATH")" \
    --argjson model_size_bytes "${MODEL_SIZE_BYTES:-null}" \
    --argjson cfg_ctx "$CTX" --arg cfg_kv "$KV" \
    --argjson cfg_ngl "$NGL" --argjson cfg_n "$REQUESTS" \
    --argjson mem_base "$MEM_AVAIL_BASE" \
    --argjson swap_base "$SWAP_FREE_BASE" \
    --argjson vram_base "$VRAM_BASE" \
    --argjson gtt_base "$GTT_BASE" \
    --argjson temp_base "$TEMP_BASE" \
    --argjson health_ms "$HEALTH_LATENCY_MS" \
    --argjson gpu_layers "$GPU_LAYERS" \
    --argjson startup_ok "$STARTUP_OK" \
    --argjson reqs "$REQ_JSON" \
    --argjson sum "$SUMMARY_JSON" \
    --argjson oom "$OOM_COUNT" \
    --argjson rst "$RESET_COUNT" \
    --argjson wall_launch "$WALL_LAUNCH" \
    --argjson uptime_launch "$UPTIME_LAUNCH" \
    --argjson uptime_end "$UPTIME_END" \
    --argjson kbase "$KERNEL_LINES_BASE" \
    '{
       label: $label,
       verdict: $verdict,
       exit_code: $exit_code,
       flags: $flags,
       env: {
         llama_version: $llama_version,
         llama_help_hash: $llama_help_hash,
         model_name: $model_name,
         model_file: $model_file,
         model_sha256: $model_sha256,
         model_size_bytes: $model_size_bytes
       },
       config: {ctx: $cfg_ctx, kv: $cfg_kv, ngl: $cfg_ngl, requests: $cfg_n},
       baseline: {
         mem_avail_mib: $mem_base,
         swap_free_mib: $swap_base,
         vram_mib: $vram_base,
         gtt_mib: $gtt_base,
         temp_c: $temp_base
       },
       startup: {
         startup_ok: $startup_ok,
         health_latency_ms: $health_ms,
         gpu_layers: $gpu_layers
       },
       window: {
         wall_clock_launch_ms: $wall_launch,
         uptime_launch_ms: $uptime_launch,
         uptime_end_ms: $uptime_end,
         kernel_baseline_line_count: $kbase
       },
       requests: $reqs,
       summary: $sum,
       kernel: {oom_count: $oom, gpu_reset_count: $rst}
     }'
}

cleanup() {
  if [ -n "${PID:-}" ] && kill -0 "$PID" 2>/dev/null; then
    kill -INT "$PID" 2>/dev/null || true
    sleep 1
    kill -KILL "$PID" 2>/dev/null || true
  fi
  rm -rf "$WORK" 2>/dev/null || true
}
trap cleanup EXIT

# ---- environment fingerprint ----------------------------------------------
note "fingerprinting binary and model"
LLAMA_VERSION=$("$LLAMA_BIN" --version 2>&1 | head -1)
LLAMA_HELP=$("$LLAMA_BIN" --help 2>&1)
LLAMA_HELP_HASH=$(printf '%s' "$LLAMA_HELP" | sha256sum | cut -d' ' -f1)

# help_has_flag HELP FLAG
#
# Bash pattern matching rather than a grep pipeline, for two reasons found the
# hard way against a real llama-server:
#   1. `printf ... | grep -q` returns failure under `pipefail` when grep exits
#      early on a match, because the writer takes SIGPIPE. On a ~59 KB --help
#      every short flag matched early enough to trigger it, so -ngl, -c, -ctk,
#      -ctv, -np, -fa, -b and -ub all read as "missing" while --jinja (matched
#      late, after the writer had finished) did not.
#   2. llama.cpp renders short flags as "-fa,   --flash-attn", so a bare
#      " -fa" substring test also fails.
# The token boundary keeps -b from matching inside -ub and -c inside -ctk.
help_has_flag() {
  local help="$1" flag="$2"
  [[ "$help" =~ (^|[[:space:]])"$flag"([,[:space:]]|$) ]]
}

for flag in -ngl -c -ctk -ctv -np -fa -b -ub --jinja; do
  help_has_flag "$LLAMA_HELP" "$flag" || die "llama-server lacks required flag $flag" 65
done
MODEL_SHA=$(sha256sum "$MODEL_PATH" | cut -d' ' -f1)

# ---- baseline --------------------------------------------------------------
MEM_AVAIL_BASE=$(kib_to_mib "$(meminfo_kib MemAvailable)")
SWAP_FREE_BASE=$(kib_to_mib "$(meminfo_kib SwapFree)")
VRAM_BASE=$(bytes_to_mib "$(read_metric "${SYS_ROOT}/sys/class/drm/card0/device/mem_info_vram_used")")
GTT_BASE=$(bytes_to_mib "$(read_metric "${SYS_ROOT}/sys/class/drm/card0/device/mem_info_gtt_used")")
TEMP_BASE=$(millideg "$(read_metric "${SYS_ROOT}/sys/class/drm/card0/device/hwmon/hwmon0/temp1_input")")
KERNEL_LINES_BASE=$(kernel_log | wc -l | tr -d ' ')
KERNEL_OOM_BASE=$(kernel_log | grep -Eic "$OOM_RE" || true)
KERNEL_RST_BASE=$(kernel_log | grep -Eic "$RST_RE" || true)

# ---- launch ----------------------------------------------------------------
note "launching llama-server ctx=$CTX kv=$KV ngl=$NGL"
T0=$(ms); WALL_LAUNCH=$T0; UPTIME_LAUNCH=$(uptime)
"$LLAMA_BIN" -m "$MODEL_PATH" --host 0.0.0.0 --port "$PORT" \
  -c "$CTX" -ctk "$KV" -ctv "$KV" -ngl "$NGL" -np 1 -fa on -b 512 -ub 512 --jinja \
  >"$LLAMA_LOG" 2>&1 &
PID=$!

STARTUP_OK=false
for _ in $(seq 1 "$HEALTH_TIMEOUT"); do
  if curl -sf -m 2 "http://$HOST:$PORT/health" >/dev/null 2>&1; then STARTUP_OK=true; break; fi
  kill -0 "$PID" 2>/dev/null || break
  sleep 1
done
HEALTH_LATENCY_MS=$(( $(ms) - T0 ))

GPU_LAYERS=$(grep -aoE 'offloaded [0-9]+/[0-9]+' "$LLAMA_LOG" 2>/dev/null | tail -1 | cut -d' ' -f2 | cut -d/ -f1 || true)
[ -z "$GPU_LAYERS" ] && GPU_LAYERS=0

if [ "$STARTUP_OK" != true ]; then
  note "STARTUP_FAIL — server never became healthy"
  UPTIME_END=$(uptime)
  FLAGS='["STARTUP_FAIL"]'
  report STARTUP_FAIL 2 '["STARTUP_FAIL"]'
  exit 2
fi
note "healthy in ${HEALTH_LATENCY_MS}ms, gpu_layers=$GPU_LAYERS"

# ---- one streaming request per trial ---------------------------------------
REQUEST_BODY=$(jq -nc --arg m "$MODEL_NAME" --arg p "$PROMPT" --argjson mt "$MAX_TOKENS" \
  '{model:$m,messages:[{role:"user",content:$p}],max_tokens:$mt,
    temperature:0,stream:true,stream_options:{include_usage:true}}')

SUCCESS=0; HTTP_OK=0; GEN_TOKENS_TOTAL=0
MAX_RSS=0; MIN_MEM_AVAIL="$MEM_AVAIL_BASE"; MAX_TEMP=0; MEM_UNREADABLE=0

for i in $(seq 1 "$REQUESTS"); do
  : > "$RAW"; : > "$HDRS"
  R_START=$(ms)
  # ONE streaming request. Response headers go to a file so the HTTP status is
  # observable without corrupting the SSE body we need to timestamp.
  curl -sN -m 300 -D "$HDRS" \
    -X POST "http://$HOST:$PORT/v1/chat/completions" \
    -H 'Content-Type: application/json' -d "$REQUEST_BODY" 2>/dev/null \
    | while IFS= read -r line; do
        case "$line" in
          data:*)         printf '%s\t%s\n' "$(ms)" "$line" >> "$RAW" ;;
          *"[DONE]"*)     printf '%s\t%s\n' "$(ms)" "$line" >> "$RAW"; break ;;
        esac
      done
  R_END=$(ms)
  LATENCY=$(( R_END - R_START ))
  HTTP_CODE=$(awk '/^HTTP\//{c=$2} END{print (c==""?"000":c)}' "$HDRS")
  [ "$HTTP_CODE" = "200" ] && HTTP_OK=$(( HTTP_OK + 1 ))

  USAGE=$(grep -F '"usage"' "$RAW" | tail -1 | sed 's/^[0-9]*\tdata: //' || true)
  GEN_TOK=$(printf '%s' "$USAGE" | jq -r '.usage.completion_tokens // 0' 2>/dev/null || echo 0)
  PRM_TOK=$(printf '%s' "$USAGE" | jq -r '.usage.prompt_tokens // 0' 2>/dev/null || echo 0)
  [ -z "$GEN_TOK" ] && GEN_TOK=0
  [ -z "$PRM_TOK" ] && PRM_TOK=0

  # Prefer server-native timings when present on any chunk.
  TIMINGS=$(grep -F '"timings"' "$RAW" | tail -1 | sed 's/^[0-9]*\tdata: //' || true)
  NAT_RATE=$(printf '%s' "$TIMINGS" | jq -r '.timings.predicted_per_second // empty' 2>/dev/null || true)
  if [ -n "$NAT_RATE" ] && [ "$NAT_RATE" != "null" ]; then
    TOK_SRC='"native"'
    GEN_TOK_S=$(printf '%s' "$NAT_RATE" | awk '{printf "%.2f", $1}')
    GEN_MS=$(printf '%s' "$TIMINGS" | jq -r '.timings.predicted_ms // null' 2>/dev/null || echo null)
    TTFT_MS=null
    PROMPT_RATE=$(printf '%s' "$TIMINGS" | jq -r 'if (.timings.prompt_ms // 0) > 0 then (.timings.prompt_per_second // null) else null end' 2>/dev/null || echo null)
  else
    TOK_SRC='"chunk_arrival"'
    TTFT_ABS=$(awk -F'\t' '/content/{print $1; exit}' "$RAW" || true)
    LAST_ABS=$(awk -F'\t' '/content/{l=$1} END{print l}' "$RAW" || true)
    if [ -n "$TTFT_ABS" ] && [ -n "$LAST_ABS" ] && [ "$LAST_ABS" -gt "$TTFT_ABS" ]; then
      TTFT_MS=$(( TTFT_ABS - R_START ))
      GEN_MS=$(( LAST_ABS - TTFT_ABS ))
      GEN_TOK_S=$(awk -v g="$GEN_TOK" -v d="$GEN_MS" 'BEGIN{printf "%.2f", (d>0? g*1000/d : 0)}')
      PROMPT_RATE=$(awk -v p="$PRM_TOK" -v t="$TTFT_MS" 'BEGIN{printf "%.2f", (t>0? p*1000/t : 0)}')
    else
      TTFT_MS=null; GEN_MS=null; GEN_TOK_S=null; PROMPT_RATE=null
    fi
  fi

  OK=false
  if [ "$GEN_TOK" -gt 0 ]; then OK=true; SUCCESS=$((SUCCESS+1)); GEN_TOKENS_TOTAL=$((GEN_TOKENS_TOTAL+GEN_TOK)); fi

  RSS=$(ps -o rss= -p "$PID" 2>/dev/null | awk '{print int($1/1024)}' || echo 0); RSS=${RSS:-0}
  MEM=$(kib_to_mib "$(meminfo_kib MemAvailable)")
  SWAPF=$(kib_to_mib "$(meminfo_kib SwapFree)")
  VRAM=$(bytes_to_mib "$(read_metric "${SYS_ROOT}/sys/class/drm/card0/device/mem_info_vram_used")")
  GTT=$(bytes_to_mib "$(read_metric "${SYS_ROOT}/sys/class/drm/card0/device/mem_info_gtt_used")")
  TEMP=$(millideg "$(read_metric "${SYS_ROOT}/sys/class/drm/card0/device/hwmon/hwmon0/temp1_input")")

  [ "$MEM" = null ] && MEM_UNREADABLE=$((MEM_UNREADABLE+1))
  [ "$RSS" -gt "$MAX_RSS" ] && MAX_RSS=$RSS
  [ "$MEM" != null ] && [ "$MEM" -lt "$MIN_MEM_AVAIL" ] && MIN_MEM_AVAIL="$MEM"
  [ "$TEMP" != null ] && [ "$TEMP" -gt "$MAX_TEMP" ] && MAX_TEMP=$TEMP

  REQ_JSON=$(printf '%s' "$REQ_JSON" | jq \
    --argjson i "$i" --argjson code "$HTTP_CODE" \
    --argjson lat "$LATENCY" --argjson ttft "$TTFT_MS" --argjson gms "$GEN_MS" \
    --argjson gts "$GEN_TOK_S" --argjson pr "$PROMPT_RATE" --argjson src "$TOK_SRC" \
    --argjson ok "$OK" --argjson gt "$GEN_TOK" --argjson pt "$PRM_TOK" \
    --argjson rss "$RSS" --argjson mem "$MEM" --argjson sw "$SWAPF" \
    --argjson vram "$VRAM" --argjson gtt "$GTT" --argjson temp "$TEMP" \
    '. + [{i:$i, http_status:$code, latency_total_ms:$lat, ttft_ms:$ttft,
           generation_time_ms:$gms, generation_tok_s:$gts,
           prompt_rate_estimate:$pr, token_source:$src,
           success:$ok, generated_tokens:$gt, prompt_tokens:$pt,
           rss_mib:$rss, mem_avail_mib:$mem, swap_free_mib:$sw,
           vram_mib:$vram, gtt_mib:$gtt, temp_c:$temp}]')
  sleep 0.2
done

# ---- kernel attribution (window between baseline and end) -------------------
UPTIME_END=$(uptime)
OOM_COUNT=$(count_new "$OOM_RE")
RESET_COUNT=$(count_new "$RST_RE")

# ---- advisory vs mandatory metrics -----------------------------------------
[ "$VRAM_BASE" = null ] && FLAGS=$(printf '%s' "$FLAGS" | jq '. + ["METRIC_MISSING_VRAM"]')
[ "$GTT_BASE"  = null ] && FLAGS=$(printf '%s' "$FLAGS" | jq '. + ["METRIC_MISSING_GTT"]')
[ "$TEMP_BASE" = null ] && FLAGS=$(printf '%s' "$FLAGS" | jq '. + ["METRIC_MISSING_TEMP"]')

MEM_AVAIL_FINAL=$(kib_to_mib "$(meminfo_kib MemAvailable)")
SUMMARY_JSON=$(jq -n \
  --argjson s "$SUCCESS" --argjson h "$HTTP_OK" --argjson n "$REQUESTS" \
  --argjson g "$GEN_TOKENS_TOTAL" --argjson r "$MAX_RSS" \
  --argjson mm "$MIN_MEM_AVAIL" --argjson mf "$MEM_AVAIL_FINAL" \
  --argjson t "$MAX_TEMP" --argjson mu "$MEM_UNREADABLE" \
  '{successful_requests:$s, http_ok_requests:$h, requested_requests:$n,
    total_generated_tokens:$g, rss_peak_mib:$r,
    mem_avail_min_mib:$mm, mem_avail_final_mib:$mf, temp_peak_c:$t,
    unreadable_mem_samples:$mu}')

# ---- verdict ---------------------------------------------------------------
verdict() {
  if [ "$STARTUP_OK" != true ];      then echo STARTUP_FAIL;    return 2; fi
  if [ "$HTTP_OK" -eq 0 ];           then echo HTTP_FAIL;       return 3; fi
  if [ "$OOM_COUNT" -gt 0 ];         then echo OOM_KILL;       return 4; fi
  if [ "$RESET_COUNT" -gt 0 ];       then echo GPU_RESET;      return 5; fi
  if [ "$SUCCESS" -eq 0 ];           then echo GENERATION_FAIL; return 1; fi
  if [ "$MEM_AVAIL_FINAL" = null ] || [ "$MEM_UNREADABLE" -gt 0 ]; then
    echo INCONCLUSIVE; return 6
  fi
  echo GREEN; return 0
}

set +e
VERDICT=$(verdict); CODE=$?
set -e
FLAGS=$(printf '%s' "$FLAGS" | jq --arg v "$VERDICT" '. + [$v]')
report "$VERDICT" "$CODE" "$FLAGS"
note "verdict=$VERDICT code=$CODE tokens=$SUCCESS/$REQUESTS http_ok=$HTTP_OK oom=$OOM_COUNT reset=$RESET_COUNT"
exit "$CODE"