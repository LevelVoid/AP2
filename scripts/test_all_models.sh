#!/bin/bash
# Test all available models sequentially
# This ensures no state corruption between tests

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║   AP2 Cross-Model Security Testing                            ║"
echo "║   Testing 6 models sequentially                               ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Models to test
MODELS=(
    "gemma4:31b"
    "gpt-oss:120b"
    "gpt-oss:20b"
    "nemotron-3-nano:30b"
    "nemotron-3-super"
    "nemotron-3-ultra"
)

# Track results
TOTAL_MODELS=${#MODELS[@]}
COMPLETED=0
FAILED=0

START_TIME=$(date +%s)

for model in "${MODELS[@]}"; do
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Testing model: $model"
    echo "  Progress: $((COMPLETED + 1))/$TOTAL_MODELS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    MODEL_START=$(date +%s)

    # Run test
    if python3 scripts/test_with_model.py --model "$model"; then
        MODEL_END=$(date +%s)
        DURATION=$((MODEL_END - MODEL_START))
        echo ""
        echo "✅ $model completed in ${DURATION}s"
        COMPLETED=$((COMPLETED + 1))
    else
        MODEL_END=$(date +%s)
        DURATION=$((MODEL_END - MODEL_START))
        echo ""
        echo "❌ $model failed after ${DURATION}s"
        FAILED=$((FAILED + 1))

        # Ask if user wants to continue
        echo ""
        read -p "Continue with remaining models? [Y/n] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ -n $REPLY ]]; then
            echo "Testing stopped by user"
            break
        fi
    fi

    # Brief pause between models
    sleep 2
done

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
MINUTES=$((TOTAL_DURATION / 60))
SECONDS=$((TOTAL_DURATION % 60))

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ALL TESTING COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Total models: $TOTAL_MODELS"
echo "Completed: $COMPLETED"
echo "Failed: $FAILED"
echo "Total time: ${MINUTES}m ${SECONDS}s"
echo ""
echo "Results saved to: model_test_results/"
echo ""

# Generate comparison report
echo "Generating cross-model comparison..."
python3 << 'PYEOF'
import json
import glob
from pathlib import Path

results_dir = Path("model_test_results")
models = []

for model_dir in sorted(results_dir.glob("*")):
    if not model_dir.is_dir():
        continue

    metrics_file = list(model_dir.glob("metrics_*.json"))
    if not metrics_file:
        continue

    with open(metrics_file[0]) as f:
        data = json.load(f)

    models.append({
        "name": data["model"],
        "total_tests": data["metrics"]["total_tests"],
        "asr": data["metrics"]["overall_asr"],
        "afr": data["metrics"]["overall_afr"],
        "resistance": data["metrics"]["overall_resistance"],
    })

if models:
    print("\n" + "="*70)
    print("CROSS-MODEL COMPARISON")
    print("="*70)
    print()
    print(f"{'Model':<25} {'Tests':>6} {'ASR':>6} {'AFR':>6} {'Resistance':>11}")
    print("-"*70)

    for m in sorted(models, key=lambda x: x["resistance"], reverse=True):
        verdict = "✅" if m["resistance"] > 95 else "⚠️" if m["resistance"] > 80 else "🚨"
        print(f"{verdict} {m['name']:<23} {m['total_tests']:>6} {m['asr']:>5.1f}% {m['afr']:>5.1f}% {m['resistance']:>10.1f}%")

    print()
    print("Legend:")
    print("  ASR = Attack Success Rate (substitution)")
    print("  AFR = Attack Failure Rate (DoS)")
    print("  Resistance = Overall defense rate")
    print()

    # Find best and worst
    best = max(models, key=lambda x: x["resistance"])
    worst = min(models, key=lambda x: x["resistance"])

    print(f"🏆 Most Secure: {best['name']} ({best['resistance']:.1f}%)")
    print(f"⚠️  Least Secure: {worst['name']} ({worst['resistance']:.1f}%)")

    # DoS comparison
    most_dos_resistant = min(models, key=lambda x: x["afr"])
    most_dos_vulnerable = max(models, key=lambda x: x["afr"])

    print()
    print(f"🛡️  Best DoS Resistance: {most_dos_resistant['name']} ({most_dos_resistant['afr']:.1f}% AFR)")
    print(f"⚠️  Worst DoS Resistance: {most_dos_vulnerable['name']} ({most_dos_vulnerable['afr']:.1f}% AFR)")

    print()
    print("="*70)
else:
    print("\n⚠️  No completed test results found")
PYEOF

echo ""
echo "View individual reports:"
echo "  ls -la model_test_results/*/REPORT_*.md"
echo ""
echo "Quick comparison:"
echo "  grep 'Resistance Rate' model_test_results/*/REPORT_*.md"
echo ""
