#!/bin/bash
# benchmark.sh — Run the Zero-HITL Baseline Benchmark via uv
#
# Usage (from the AP2 repo root):
#   bash scripts/benchmark.sh [--max N] [--output FILE] [--drop-delay N] [--timeout N]
#
# Examples:
#   bash scripts/benchmark.sh --max 5
#   bash scripts/benchmark.sh --max 10 --drop-delay 10 --output results.json
#
# All servers must already be running:
#   bash code/samples/python/scenarios/a2a/human-not-present/cards/run.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_ROOT="$REPO_ROOT/code/samples/python"
BENCHMARK_SCRIPT="$SCRIPT_DIR/run_baseline_benchmark.py"

# Source .env from the AP2 repo root if it exists (picks up OLLAMA_MODEL, FLOW, etc.)
if [ -f "$REPO_ROOT/.env" ]; then
  set -a; source "$REPO_ROOT/.env"; set +a
  echo "  Loaded $REPO_ROOT/.env"
fi

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║       AP2 Zero-HITL Baseline Benchmark            ║"
echo "╚═══════════════════════════════════════════════════╝"
echo "  OLLAMA_MODEL : ${OLLAMA_MODEL:-gemma4:31b-cloud (default)}"
echo "  FLOW         : ${FLOW:-card}"
echo ""

# Run inside the project's uv venv so httpx and all deps are available
cd "$PYTHON_ROOT"
exec uv run python3 "$BENCHMARK_SCRIPT" "$@"
