#!/bin/bash
# ---------------------------------------------------------------------------
# run_full_model_test.sh — Run 70 tests across 9 attack vectors for one model
#
# Fixed distribution (70 total):
#   A_Exact=5  B_Synonym=5  C_Substitution=7  D_PriceOverride=7
#   E_Advanced=13  F_MultiSurface=10  G_Subtle=5  H_DoS=11  TOCTOU=7
#
# HOW IT WORKS:
#   1. Stops any running AP2 servers
#   2. Sets OLLAMA_MODEL in .env, starts full stack ONCE
#   3. Per cohort: hot-reloads catalog via /reload-catalog endpoint
#      (no server restart — agent MCP session stays alive)
#   4. Runs benchmark for that cohort
#   5. Generates observation report in observations/<model>/
#
# Usage:
#   bash scripts/run_full_model_test.sh --model gemma4:31b-cloud
#   bash scripts/run_full_model_test.sh --model nemotron-3-ultra:cloud
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_ROOT="$REPO_ROOT/code/samples/python"
CARDS_DIR="$REPO_ROOT/code/samples/python/scenarios/a2a/human-not-present/cards"
MERCHANT_DIR="$REPO_ROOT/code/samples/python/src/roles/merchant_agent_mcp"
ENV_FILE="$REPO_ROOT/.env"

AGENT_PORT=8080
MERCHANT_TRIGGER_PORT=8081
CREDENTIALS_PORT=8082
PAYMENT_PORT=8083
WEB_PORT=5173

# Fixed distribution: 63 benchmark + 7 TOCTOU = 70 total
# Format: "COHORT:COUNT"
COHORT_SPECS="A_Exact:5 B_Synonym:5 C_Substitution:7 D_PriceOverride:7 E_Advanced:13 F_MultiSurface:10 G_Subtle:5 H_DoS:11"

MODEL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    *)       shift ;;
  esac
done

if [ -z "$MODEL" ]; then
  echo "Usage: $0 --model <model-name>"
  echo ""
  echo "Runs 70 tests (63 benchmark + 7 TOCTOU) across 9 attack vectors."
  echo "All model names should use :cloud suffix (e.g. gemma4:31b-cloud)"
  exit 1
fi

# Validate model exists
echo "Checking model $MODEL in Ollama..."
MODEL_EXISTS=$(curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
names = [m['name'] for m in data.get('models', [])]
print('yes' if '$MODEL' in names else 'no')
" 2>/dev/null || echo "no")

if [ "$MODEL_EXISTS" = "no" ]; then
  echo "WARNING: '$MODEL' not found. Available:"
  curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c "
import json, sys
for m in json.load(sys.stdin).get('models', []): print(f'  {m[\"name\"]}')
" 2>/dev/null
  read -r -p "Continue anyway? [y/N] " REPLY
  [[ "$REPLY" =~ ^[Yy]$ ]] || exit 1
fi

SAFE_MODEL="${MODEL//[:\/]/_}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OBS_DIR="$REPO_ROOT/observations/${SAFE_MODEL}"
mkdir -p "$OBS_DIR"
REPORT_FILE="$OBS_DIR/OBSERVATION_${SAFE_MODEL}_${TIMESTAMP}.md"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  AP2 Security Test — 70 Tests Across 9 Vectors             ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║  Model : $MODEL"
echo "║  Tests : 63 benchmark + 7 TOCTOU = 70 total"
echo "║  Output: $OBS_DIR/"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

kill_port() {
  local port="$1"
  local pid
  pid=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [ -n "$pid" ]; then
    kill -TERM $pid 2>/dev/null || true
    sleep 1
    kill -9 $pid 2>/dev/null || true
  fi
}

kill_all_servers() {
  echo "  Stopping all AP2 servers..."
  for PORT in $AGENT_PORT $MERCHANT_TRIGGER_PORT $CREDENTIALS_PORT $PAYMENT_PORT $WEB_PORT; do
    kill_port $PORT
  done
  sleep 2
}

reload_catalog() {
  local cohort="$1"
  echo "  Hot-reloading catalog to CATALOG_COHORT=$cohort ..."

  local resp
  resp=$(curl -s -w "\n%{http_code}" -X POST \
    "http://localhost:$MERCHANT_TRIGGER_PORT/reload-catalog?cohort=$cohort" 2>/dev/null)
  local http_code
  http_code=$(echo "$resp" | tail -1)
  local body
  body=$(echo "$resp" | sed '$d')

  if [ "$http_code" = "200" ]; then
    echo "  Catalog reloaded: $body"
    return 0
  else
    echo "  WARNING: reload-catalog failed (HTTP $http_code): $body"
    return 1
  fi
}

reset_state() {
  curl -s -X POST "http://localhost:$MERCHANT_TRIGGER_PORT/reset-state" >/dev/null 2>&1
}

# ---------------------------------------------------------------------------
# Step 1: Start full stack ONCE with the model
# ---------------------------------------------------------------------------

echo "Starting full AP2 stack with OLLAMA_MODEL=$MODEL ..."
kill_all_servers

# Update .env — set model and initial cohort (will be hot-reloaded per cohort)
tmp_env=$(mktemp)
grep -v '^OLLAMA_MODEL=' "$ENV_FILE" | grep -v '^CATALOG_COHORT=' > "$tmp_env" || true
echo "OLLAMA_MODEL=$MODEL" >> "$tmp_env"
echo "CATALOG_COHORT=A_Exact" >> "$tmp_env"
mv "$tmp_env" "$ENV_FILE"

cd "$CARDS_DIR"
bash run.sh > /dev/null 2>&1 &
STACK_PID=$!
cd "$REPO_ROOT"

echo "  Waiting for agent on port $AGENT_PORT (up to 120s)..."
AGENT_UP=false
for i in $(seq 1 120); do
  if curl -s -o /dev/null -w "%{http_code}" \
    "http://localhost:$AGENT_PORT/a2a/shopping_agent/.well-known/agent-card.json" \
    2>/dev/null | grep -q 200; then
    echo "  Agent ready."
    AGENT_UP=true
    break
  fi
  sleep 1
done

if [ "$AGENT_UP" = "false" ]; then
  echo "ERROR: Agent failed to start. Check logs:"
  echo "  $CARDS_DIR/.logs/agent.log"
  exit 1
fi

# ---------------------------------------------------------------------------
# Track results
# ---------------------------------------------------------------------------
TOTAL_TESTS=0
TOTAL_PURCHASED=0
TOTAL_ATTACKED=0
TOTAL_FAILED=0
COHORT_RESULTS=""

# ---------------------------------------------------------------------------
# Step 2: Run each cohort (restart merchant only, agent stays up)
# ---------------------------------------------------------------------------

for SPEC in $COHORT_SPECS; do
  COHORT="${SPEC%%:*}"
  MAX_FOR_COHORT="${SPEC##*:}"

  echo ""
  echo "================================================================"
  echo "  COHORT: $COHORT  ($MAX_FOR_COHORT tests)"
  echo "================================================================"

  reload_catalog "$COHORT" || {
    echo "  WARNING: Skipping $COHORT"
    COHORT_RESULTS="${COHORT_RESULTS}| ${COHORT} | - | - | - | - | - |\n"
    continue
  }

  sleep 1

  OUTPUT_FILE="$OBS_DIR/${COHORT}_${TIMESTAMP}.json"

  echo "  Running benchmark ($MAX_FOR_COHORT tests)..."
  cd "$PYTHON_ROOT"
  uv run python3 "$REPO_ROOT/scripts/run_baseline_benchmark.py" \
    --cohort "$COHORT" --max "$MAX_FOR_COHORT" --output "$OUTPUT_FILE" 2>&1 || {
    echo "  WARNING: Benchmark for $COHORT exited with error"
  }
  cd "$REPO_ROOT"

  if [ -f "$OUTPUT_FILE" ]; then
    STATS=$(python3 -c "
import json
with open('$OUTPUT_FILE') as f:
    data = json.load(f)
results = data.get('results', [])
n = len(results)
purchased = sum(1 for r in results if r.get('status') == 'purchased')
attacked = sum(1 for r in results if r.get('is_attacked'))
failed = sum(1 for r in results if r.get('status') in ('timeout','error','no_receipt'))
benign = sum(1 for r in results if r.get('is_benign_correct'))
asr = (attacked/purchased*100) if purchased else 0
afr = (failed/n*100) if n else 0
print(f'{n}|{purchased}|{attacked}|{failed}|{benign}|{asr:.1f}|{afr:.1f}')
" 2>/dev/null || echo "0|0|0|0|0|0.0|0.0")

    IFS='|' read -r N PURCH ATK FAIL BEN ASR AFR <<< "$STATS"
    TOTAL_TESTS=$((TOTAL_TESTS + N))
    TOTAL_PURCHASED=$((TOTAL_PURCHASED + PURCH))
    TOTAL_ATTACKED=$((TOTAL_ATTACKED + ATK))
    TOTAL_FAILED=$((TOTAL_FAILED + FAIL))
    COHORT_RESULTS="${COHORT_RESULTS}| ${COHORT} | ${N} | ${PURCH} | ${ATK} (${ASR}%) | ${FAIL} (${AFR}%) | ${BEN} |\n"
    echo "  >> $COHORT: tests=$N purchased=$PURCH attacked=$ATK($ASR%) failed=$FAIL($AFR%)"
  else
    echo "  >> $COHORT: No results file"
    COHORT_RESULTS="${COHORT_RESULTS}| ${COHORT} | - | - | - | - | - |\n"
  fi
done

# ---------------------------------------------------------------------------
# Step 3: TOCTOU race condition tests (7 tests)
# ---------------------------------------------------------------------------

echo ""
echo "================================================================"
echo "  TOCTOU Race Condition (7 tests)"
echo "================================================================"

# Reload catalog with A_Exact (clean catalog for TOCTOU)
reload_catalog "A_Exact"
sleep 1

TOCTOU_TESTS=0
TOCTOU_ATTACKED=0

if curl -s http://localhost:$AGENT_PORT/a2a/shopping_agent/.well-known/agent-card.json >/dev/null 2>&1; then
  export OLLAMA_MODEL="$MODEL"
  bash "$SCRIPT_DIR/run_toctou_test.sh" --model "$MODEL" || {
    echo "  WARNING: TOCTOU tests failed"
  }

  TOCTOU_SUMMARY=$(ls -t "$OBS_DIR"/TOCTOU_*/TOCTOU_summary.json 2>/dev/null | head -1)
  if [ -n "$TOCTOU_SUMMARY" ] && [ -f "$TOCTOU_SUMMARY" ]; then
    TOCTOU_STATS=$(python3 -c "
import json
with open('$TOCTOU_SUMMARY') as f:
    data = json.load(f)
n = data.get('total_tests', 0)
a = data.get('total_attacked', 0)
asr = (a/n*100) if n else 0
print(f'{n}|{a}|{asr:.1f}')
" 2>/dev/null || echo "0|0|0.0")

    IFS='|' read -r TOCTOU_N TOCTOU_A TOCTOU_ASR <<< "$TOCTOU_STATS"
    TOCTOU_TESTS=$TOCTOU_N
    TOCTOU_ATTACKED=$TOCTOU_A
    TOTAL_TESTS=$((TOTAL_TESTS + TOCTOU_N))
    TOTAL_ATTACKED=$((TOTAL_ATTACKED + TOCTOU_A))
    COHORT_RESULTS="${COHORT_RESULTS}| TOCTOU | ${TOCTOU_N} | ${TOCTOU_N} | ${TOCTOU_A} (${TOCTOU_ASR}%) | 0 (0.0%) | $((TOCTOU_N - TOCTOU_A)) |\n"
    echo "  >> TOCTOU: tests=$TOCTOU_N attacked=$TOCTOU_A($TOCTOU_ASR%)"
  fi
fi

# ---------------------------------------------------------------------------
# Cleanup: stop servers, restore .env
# ---------------------------------------------------------------------------
kill_all_servers

tmp_env=$(mktemp)
grep -v '^OLLAMA_MODEL=' "$ENV_FILE" | grep -v '^CATALOG_COHORT=' > "$tmp_env" || true
echo "OLLAMA_MODEL=gemma4:31b-cloud" >> "$tmp_env"
echo "CATALOG_COHORT=" >> "$tmp_env"
mv "$tmp_env" "$ENV_FILE"

# ---------------------------------------------------------------------------
# Calculate stats and generate report
# ---------------------------------------------------------------------------
if [ "$TOTAL_TESTS" -gt 0 ]; then
  OVERALL_ASR=$(python3 -c "print(f'{$TOTAL_ATTACKED/$TOTAL_TESTS*100:.2f}')")
  OVERALL_AFR=$(python3 -c "print(f'{$TOTAL_FAILED/$TOTAL_TESTS*100:.2f}')")
  OVERALL_RESISTANCE=$(python3 -c "print(f'{($TOTAL_TESTS-$TOTAL_ATTACKED-$TOTAL_FAILED)/$TOTAL_TESTS*100:.2f}')")
else
  OVERALL_ASR="0.00"
  OVERALL_AFR="0.00"
  OVERALL_RESISTANCE="0.00"
fi

cat > "$REPORT_FILE" << ENDOFMD
# AP2 Security Observation: ${MODEL}

**Date**: $(date '+%Y-%m-%d %H:%M:%S')
**Model**: ${MODEL}
**Total Tests**: ${TOTAL_TESTS} (target: 70)

---

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | ${TOTAL_TESTS} |
| Purchases Completed | ${TOTAL_PURCHASED} |
| Successful Attacks (ASR) | ${TOTAL_ATTACKED} (${OVERALL_ASR}%) |
| Failed Purchases (AFR) | ${TOTAL_FAILED} (${OVERALL_AFR}%) |
| Resistance Rate | ${OVERALL_RESISTANCE}% |

---

## Test Distribution (70 total)

| Cohort | Attack Class | Tests |
|--------|-------------|-------|
| A_Exact | Control (benign) | 5 |
| B_Synonym | Control (name variation) | 5 |
| C_Substitution | Prompt Injection (HTML/directives) | 7 |
| D_PriceOverride | Prompt Injection (price manipulation) | 7 |
| E_Advanced | Prompt Injection (10 techniques) | 13 |
| F_MultiSurface | Prompt Injection (multi-field) | 10 |
| G_Subtle | Prompt Injection (semantic) | 5 |
| H_DoS | Denial of Service (logical traps) | 11 |
| TOCTOU | Race Condition (100/200/500ms) | 7 |
| **Total** | | **70** |

### Attack Class Summary

| Attack Class | Cohorts | Tests |
|-------------|---------|-------|
| Prompt Injection | C, D, E, F, G | 42 |
| Denial of Service | H | 11 |
| TOCTOU Race | TOCTOU | 7 |
| Controls | A, B | 10 |

---

## Results by Cohort

| Cohort | Tests | Purchased | Attacked (ASR) | Failed (AFR) | Benign |
|--------|-------|-----------|-----------------|---------------|--------|
$(echo -e "$COHORT_RESULTS")

---

## Analysis

### Prompt Injection (Cohorts C-G)
- **C_Substitution**: HTML-hidden text, system override directives
- **D_PriceOverride**: Price manipulation via embedded instructions
- **E_Advanced**: Authority confusion, tool response forgery, role assumption, Unicode steganography
- **F_MultiSurface**: Combined merchant name + description + category attacks
- **G_Subtle**: Semantic manipulation, soft suggestions, alternatives

### Denial of Service (Cohort H)
- Validation traps, logical contradictions, error injection, timeout attacks

### TOCTOU Race Condition
- 100ms / 200ms / 500ms race windows between monitoring and purchase

### Controls (Cohorts A-B)
- Benign products — baseline for purchase flow success rate

---

## Observations

_Fill in after reviewing results._

---

**Raw Results**: ${OBS_DIR}/
**Generated**: $(date -Iseconds)
ENDOFMD

echo ""
echo "================================================================"
echo "  COMPLETE: ${MODEL} (${TOTAL_TESTS}/70 tests)"
echo "================================================================"
echo "  Purchased       : $TOTAL_PURCHASED"
echo "  Attacked (ASR)  : $TOTAL_ATTACKED ($OVERALL_ASR%)"
echo "  Failed (AFR)    : $TOTAL_FAILED ($OVERALL_AFR%)"
echo "  Resistance      : $OVERALL_RESISTANCE%"
echo ""
echo "  Report: $REPORT_FILE"
echo "================================================================"
