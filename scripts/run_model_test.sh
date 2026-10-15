#!/bin/bash
# ---------------------------------------------------------------------------
# run_model_test.sh — Test a specific cohort with the correct poisoned catalog
#
# Restarts the merchant trigger server with CATALOG_COHORT set so the
# cohort-specific injection payloads are served. The agent and other
# servers keep running.
#
# Usage:
#   bash scripts/run_model_test.sh --model gpt-oss:20b --cohort E_Advanced --max 10
#   bash scripts/run_model_test.sh --model gemma4:31b --cohort E_Advanced
#
# Prerequisites: run.sh must have been started first (agent on 8080).
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_ROOT="$REPO_ROOT/code/samples/python"
CARDS_DIR="$REPO_ROOT/code/samples/python/scenarios/a2a/human-not-present/cards"
MERCHANT_DIR="$REPO_ROOT/code/samples/python/src/roles/merchant_agent_mcp"
MERCHANT_TRIGGER_PORT=8081
LOG_DIR="$CARDS_DIR/.logs"

# Source .env
if [ -f "$REPO_ROOT/.env" ]; then
  set -a; source "$REPO_ROOT/.env"; set +a
fi

# Parse args
MODEL=""
COHORT=""
MAX_TESTS=""
EXTRA_ARGS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)  MODEL="$2"; shift 2 ;;
    --cohort) COHORT="$2"; shift 2 ;;
    --max)    MAX_TESTS="$2"; shift 2 ;;
    *)        EXTRA_ARGS="$EXTRA_ARGS $1"; shift ;;
  esac
done

if [ -z "$MODEL" ]; then
  echo "Usage: $0 --model <model-name> --cohort <cohort> [--max N]"
  exit 1
fi

if [ -z "$COHORT" ]; then
  COHORT="E_Advanced"
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OBSERVATIONS_DIR="$REPO_ROOT/observations/${MODEL//[:\/]/_}"
mkdir -p "$OBSERVATIONS_DIR"

OUTPUT_FILE="$OBSERVATIONS_DIR/${COHORT}_${TIMESTAMP}.json"

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  AP2 Attack Vector Test                               ║"
echo "╠═══════════════════════════════════════════════════════╣"
echo "║  Model  : $MODEL"
echo "║  Cohort : $COHORT"
echo "║  Output : $OUTPUT_FILE"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# --- Step 1: Restart merchant trigger server with correct catalog ---
echo "Restarting merchant trigger with CATALOG_COHORT=$COHORT ..."

# Kill existing merchant trigger
MERCHANT_PID=$(lsof -ti tcp:$MERCHANT_TRIGGER_PORT 2>/dev/null || true)
if [ -n "$MERCHANT_PID" ]; then
  echo "  Stopping merchant trigger (PID=$MERCHANT_PID) ..."
  kill -TERM $MERCHANT_PID 2>/dev/null || true
  sleep 2
  kill -9 $MERCHANT_PID 2>/dev/null || true
  sleep 1
fi

# Export env vars for the merchant
export CATALOG_COHORT="$COHORT"
export TEMP_DB_DIR="$CARDS_DIR/.temp-db"
export MERCHANT_TRIGGER_STATE_PATH="$TEMP_DB_DIR/merchant_trigger_state.json"
export MERCHANT_INVENTORY_PATH="$TEMP_DB_DIR/merchant_inventory.json"
export FLOW=card

# Clear inventory so the new catalog takes effect
rm -f "$TEMP_DB_DIR/merchant_inventory.json"
rm -f "$TEMP_DB_DIR/merchant_trigger_state.json"

# Start merchant trigger with the cohort catalog
mkdir -p "$LOG_DIR"
(cd "$MERCHANT_DIR" && CATALOG_COHORT="$COHORT" uv run python trigger_server.py) \
  >"$LOG_DIR/merchant-trigger.log" 2>&1 &
NEW_PID=$!
echo "  Started merchant trigger PID=$NEW_PID with CATALOG_COHORT=$COHORT"

# Wait for merchant to be ready
echo "  Waiting for merchant trigger on port $MERCHANT_TRIGGER_PORT ..."
for i in $(seq 1 30); do
  if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$MERCHANT_TRIGGER_PORT/health" 2>/dev/null | grep -q 200; then
    echo "  Merchant trigger ready."
    break
  fi
  sleep 0.5
done

# --- Step 2: Set OLLAMA_MODEL if needed ---
if [ -n "$MODEL" ]; then
  export OLLAMA_MODEL="$MODEL"
fi

# --- Step 3: Run the benchmark ---
echo ""
echo "Running benchmark for cohort $COHORT ..."
echo ""

BENCH_ARGS="--cohort $COHORT --output $OUTPUT_FILE"
if [ -n "$MAX_TESTS" ]; then
  BENCH_ARGS="$BENCH_ARGS --max $MAX_TESTS"
fi

cd "$PYTHON_ROOT"
uv run python3 "$REPO_ROOT/scripts/run_baseline_benchmark.py" $BENCH_ARGS $EXTRA_ARGS

echo ""
echo "Results saved to: $OUTPUT_FILE"
echo ""
