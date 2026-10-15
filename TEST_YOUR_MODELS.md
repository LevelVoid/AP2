# Testing Your Available Models

## Your Models

You have access to these 6 models:

| Model | Type | Size | Provider |
|-------|------|------|----------|
| **gemma4:31b** | Gemma 4 | 31B | Ollama |
| **gpt-oss:120b** | GPT-OSS | 120B | Ollama |
| **gpt-oss:20b** | GPT-OSS | 20B | Ollama |
| **nemotron-3-nano:30b** | Nemotron 3 | 30B | Ollama |
| **nemotron-3-super** | Nemotron 3 | Super | Ollama/Cloud |
| **nemotron-3-ultra** | Nemotron 3 | Ultra | Ollama/Cloud |

---

## Quick Start: Test All Models

Run comprehensive security tests across all 6 models:

```bash
# 1. Start the AP2 system
cd code/samples/python/scenarios/a2a/human-not-present/cards/
bash run.sh

# 2. In another terminal, test all models
cd /Users/pradeepbiswas/Projects/Research/AP2
bash scripts/test_all_models.sh
```

**This will**:
- ✅ Test all 6 models sequentially
- ✅ Run 61 tests per model (366 total)
- ✅ Generate comprehensive reports for each
- ✅ Create cross-model comparison table
- ✅ Identify most/least secure models
- ⏱️ **Estimated time**: 1-2 hours total (~10-20 min per model)

---

## Alternative: Test Individual Models

Test one model at a time:

```bash
# Test Gemma 4 (31B)
python3 scripts/test_with_model.py --model gemma4:31b

# Test GPT-OSS Large (120B)
python3 scripts/test_with_model.py --model gpt-oss:120b

# Test GPT-OSS Small (20B)
python3 scripts/test_with_model.py --model gpt-oss:20b

# Test Nemotron 3 Nano (30B)
python3 scripts/test_with_model.py --model nemotron-3-nano:30b

# Test Nemotron 3 Super
python3 scripts/test_with_model.py --model nemotron-3-super

# Test Nemotron 3 Ultra
python3 scripts/test_with_model.py --model nemotron-3-ultra
```

---

## Quick Testing (Faster)

Test with fewer samples per cohort:

```bash
# Test with only 3 tests per cohort (~5 min per model)
python3 scripts/test_with_model.py --model gemma4:31b --max-per-cohort 3

# Test only the most interesting cohorts
python3 scripts/test_with_model.py --model gpt-oss:120b \
  --cohorts E_Advanced H_DoS
```

---

## Results Location

Each model's results saved to:

```
model_test_results/
├── gemma4:31b/
│   ├── REPORT_gemma4:31b.md           # ⭐ Read this first
│   ├── metrics_gemma4:31b.json
│   └── ...
├── gpt-oss:120b/
│   ├── REPORT_gpt-oss:120b.md         # ⭐ Read this first
│   └── ...
├── gpt-oss:20b/
├── nemotron-3-nano:30b/
├── nemotron-3-super/
└── nemotron-3-ultra/
```

---

## Comparing Results

After testing multiple models:

### Quick Comparison

```bash
# View all resistance rates
grep "Resistance Rate" model_test_results/*/REPORT_*.md

# View DoS susceptibility
grep "DoS Resistance" model_test_results/*/REPORT_*.md

# View injection resistance
grep "Injection Resistance" model_test_results/*/REPORT_*.md
```

### Detailed Comparison

```bash
# View all reports
ls -la model_test_results/*/REPORT_*.md

# Read specific model
cat model_test_results/gemma4:31b/REPORT_gemma4:31b.md
```

---

## What Gets Tested

For each model, all 61 tests across 3 attack classes:

### 1. Prompt Injection (44 tests)
- Basic injection (HTML, directives)
- Advanced (authority confusion, tool forgery)
- Multi-surface (combined fields)
- Subtle (semantic manipulation)

### 2. Denial of Service (10 tests)
- Logical traps
- Validation errors
- Contradictions
- Timeout attacks

### 3. TOCTOU Race Conditions (7 tests)
- 100ms race window
- 200ms race window
- 500ms race window

---

## Expected Research Questions

After testing all models, you'll be able to answer:

### Security Questions
- **Q**: Which model is most secure overall?
- **A**: Compare resistance rates across models

- **Q**: Which model resists prompt injection best?
- **A**: Compare ASR (Attack Success Rate)

- **Q**: Which model handles DoS attacks best?
- **A**: Compare AFR (Attack Failure Rate)

- **Q**: Are larger models more secure?
- **A**: Compare gpt-oss:120b vs gpt-oss:20b

### Model Comparison
- **Gemma vs GPT-OSS**: Different architectures
- **Model Size Impact**: 20B vs 31B vs 120B
- **Nemotron Variants**: Nano vs Super vs Ultra

---

## Sample Output

After running `bash scripts/test_all_models.sh`, you'll see:

```
╔═══════════════════════════════════════════════════════════════╗
║   AP2 Cross-Model Security Testing                            ║
║   Testing 6 models sequentially                               ║
╚═══════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Testing model: gemma4:31b
  Progress: 1/6
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Testing in progress...]

✅ gemma4:31b completed in 720s

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Testing model: gpt-oss:120b
  Progress: 2/6
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[... continues for all models ...]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ALL TESTING COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total models: 6
Completed: 6
Failed: 0
Total time: 75m 30s

======================================================================
CROSS-MODEL COMPARISON
======================================================================

Model                      Tests    ASR    AFR  Resistance
----------------------------------------------------------------------
✅ nemotron-3-ultra          61    0.0%   5.0%      98.4%
✅ gpt-oss:120b              61    0.0%   8.0%      96.7%
✅ gemma4:31b                61    0.0%  10.0%      95.1%
⚠️  nemotron-3-super         61    2.0%  10.0%      90.2%
⚠️  gpt-oss:20b              61    5.0%  15.0%      83.6%
⚠️  nemotron-3-nano:30b      61    8.0%  12.0%      80.3%

Legend:
  ASR = Attack Success Rate (substitution)
  AFR = Attack Failure Rate (DoS)
  Resistance = Overall defense rate

🏆 Most Secure: nemotron-3-ultra (98.4%)
⚠️  Least Secure: nemotron-3-nano:30b (80.3%)

🛡️  Best DoS Resistance: nemotron-3-ultra (5.0% AFR)
⚠️  Worst DoS Resistance: gpt-oss:20b (15.0% AFR)

======================================================================
```

---

## Troubleshooting

### Servers Not Running
```bash
cd code/samples/python/scenarios/a2a/human-not-present/cards/
bash run.sh
```

### Model Not Available
Verify model is installed in Ollama:
```bash
ollama list
```

Install missing model:
```bash
ollama pull gemma4:31b
```

### Tests Taking Too Long
Run quick test first:
```bash
python3 scripts/test_with_model.py --model gemma4:31b --max-per-cohort 3
```

### Want to Stop Mid-Test
The batch script (`test_all_models.sh`) will ask if you want to continue after each model failure. Press `n` to stop.

---

## Research Value

Testing all 6 models will let you:

1. **Identify Best Model for AP2**
   - Which provides strongest security?
   - Which has best DoS resistance?
   - Which handles edge cases best?

2. **Understand Size vs Security**
   - Does 120B beat 31B?
   - Is Nano (30B) less secure?
   - Size-performance tradeoffs

3. **Compare Architectures**
   - Gemma vs GPT-OSS vs Nemotron
   - Training differences visible in results
   - Model family characteristics

4. **Publication-Ready Data**
   - 6 models × 61 tests = 366 data points
   - Statistical significance
   - Reproducible methodology
   - Comprehensive coverage

---

## Next Steps

1. **Start Testing**:
   ```bash
   bash scripts/test_all_models.sh
   ```

2. **Wait for Completion** (~1-2 hours)

3. **Review Results**:
   ```bash
   ls -la model_test_results/*/REPORT_*.md
   ```

4. **Analyze Findings**:
   - Read ATTACK_METHODOLOGY.md for context
   - Compare resistance rates
   - Identify vulnerability patterns
   - Draw conclusions

---

**Ready to test all 6 models?** 🔬

Run: `bash scripts/test_all_models.sh`
