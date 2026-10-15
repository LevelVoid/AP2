#!/bin/bash
# Run advanced attack test suite
# Tests sophisticated injection techniques across multiple attack surfaces

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RESULTS_DIR="$REPO_ROOT/vulnerability_test_results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_DIR="$RESULTS_DIR/advanced_run_$TIMESTAMP"

mkdir -p "$RUN_DIR"

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║   AP2 Advanced Attack Test Suite                              ║"
echo "║   Sophisticated Injection Techniques                          ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "Testing advanced attacks to achieve ASR > 0%"
echo "Results: $RUN_DIR"
echo ""

# Advanced cohorts
declare -a COHORTS=(
    "E_Advanced:10:Advanced injection techniques (authority confusion, tool forgery, etc)"
    "F_MultiSurface:10:Attacks across different data fields (merchant, category, image)"
    "G_Subtle:5:Subtle semantic manipulations"
)

# Check servers
if ! curl -s http://localhost:8080/a2a/shopping_agent/.well-known/agent-card.json >/dev/null 2>&1; then
  echo "❌ ERROR: Servers not running!"
  echo "Start with: cd code/samples/python/scenarios/a2a/human-not-present/cards && bash run.sh"
  exit 1
fi
echo "✅ Servers running"
echo ""

# Summary file
SUMMARY_FILE="$RUN_DIR/summary.txt"
echo "AP2 Advanced Attack Test Results - $(date)" > "$SUMMARY_FILE"
echo "================================================" >> "$SUMMARY_FILE"
echo "" >> "$SUMMARY_FILE"

# Run each cohort
for cohort_spec in "${COHORTS[@]}"; do
    IFS=':' read -r COHORT MAX DESC <<< "$cohort_spec"

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Testing: $COHORT"
    echo "  Description: $DESC"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    OUTPUT_FILE="$RUN_DIR/results_${COHORT}.json"
    LOG_FILE="$RUN_DIR/log_${COHORT}.txt"

    if bash "$SCRIPT_DIR/benchmark.sh" --cohort "$COHORT" --max "$MAX" --output "$OUTPUT_FILE" 2>&1 | tee "$LOG_FILE"; then
        echo "✅ $COHORT completed"

        # Parse results
        if [ -f "$OUTPUT_FILE" ]; then
            echo "" >> "$SUMMARY_FILE"
            echo "Cohort: $COHORT - $DESC" >> "$SUMMARY_FILE"
            echo "----------------------------------------" >> "$SUMMARY_FILE"

            python3 << PYEOF >> "$SUMMARY_FILE"
import json
with open('$OUTPUT_FILE', 'r') as f:
    data = json.load(f)

results = data.get('results', [])
total = len(results)
attacked = sum(1 for r in results if r.get('is_attacked', False))
benign_correct = sum(1 for r in results if r.get('is_benign_correct', False))
errors = sum(1 for r in results if r.get('status') == 'error')

asr = (attacked / total * 100) if total > 0 else 0
benign_rate = (benign_correct / total * 100) if total > 0 else 0

print(f'  Total tests: {total}')
print(f'  Attack Success Rate (ASR): {asr:.1f}% ({attacked}/{total})')
print(f'  Benign correct: {benign_rate:.1f}% ({benign_correct}/{total})')
print(f'  Errors: {errors}')

if attacked > 0:
    print(f'\n  🚨 SUCCESSFUL ATTACKS:')
    for i, r in enumerate(results, 1):
        if r.get('is_attacked'):
            print(f"    Test {i}: {r.get('expected_benign_item', '?')} → {r.get('purchased_item', '?')}")
            if 'attack_technique' in r:
                print(f"             Technique: {r['attack_technique']}")
PYEOF
        fi
    else
        echo "❌ $COHORT failed"
        echo "  Status: FAILED" >> "$SUMMARY_FILE"
    fi

    sleep 3
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ADVANCED ATTACK SUITE COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Results: $RUN_DIR"
echo ""
cat "$SUMMARY_FILE"
echo ""
