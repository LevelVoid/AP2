# AP2 Security Research: Comprehensive Vulnerability Testing

## Current State

**Branch**: `main` (20+ commits ahead of origin/main)  
**Goal**: Discover genuine security vulnerabilities in Google's Agent Payments Protocol (AP2)  
**Status**: ✅ Research Complete - 61 tests across 3 attack classes (98.4% resistance rate)

---

## What This Is

Google's **Agent Payments Protocol (AP2)** enables autonomous AI agents to make purchases using cryptographic mandates instead of traditional checkout flows. This research provides comprehensive security testing across prompt injection, DoS, and timing attacks.

### Research Summary

**Completed Testing** (Baseline: Gemma 4:31B):
- ✅ **Prompt Injection**: 0% ASR (44 tests) - Highly resistant
- ⚠️ **Denial of Service**: 10% AFR (10 tests) - Minor vulnerability
- ✅ **TOCTOU Race**: 0% ASR (7 tests) - Timing attack resistant
- **Overall**: 98.4% resistance rate (60/61 tests passed)

### The System

- **Zero Human-in-the-Loop (Zero-HITL)**: After one-time mandate approval, agent purchases autonomously
- **Three-tier agent hierarchy**: consent_agent → monitoring_agent → purchase_agent  
- **Cryptographic mandates**: Open mandates (constraints) → Closed mandates (specific transactions)
- **Key roles**: Shopping Agent, Merchant, Credentials Provider, Payment Processor

---

## Research Infrastructure

### What We Have

✅ **Base AP2 System** (from origin/main + local modifications)
- Shopping agent v2 with Ollama LLM support
- MCP servers over HTTP (Starlette + FastMCP)
- Zero-HITL autonomous purchase flow
- Web UI for testing (port 5173)

✅ **HIVE Defense Code** (disabled by default)
- Located in: `code/samples/python/src/common/hive_interceptor.py`
- **Currently NOT in the execution flow**
- Can be enabled by uncommenting blocks in:
  - `shopping_agent_v2/shopping_agent/mandate_tools.py` (lines ~864-939)
  - `shopping_agent/tools.py` (lines ~210-273)

✅ **Attack Vectors & Test Data**
- **8 Attack Cohorts**: A_Exact → H_DoS (61 total tests)
- **3 Attack Classes**: Prompt Injection, DoS, TOCTOU
- **20+ Techniques**: Authority confusion, validation traps, race conditions
- `data/by_cohort/`: Attack cohorts with malicious payloads
- `scripts/generate_advanced_attacks.py`: Sophisticated injection generator
- `scripts/generate_dos_attacks.py`: DoS payload generator
- `scripts/toctou_attack_realistic.py`: Race condition implementation

✅ **Testing Infrastructure**
- `scripts/run_baseline_benchmark.py`: Automated testing harness
- `scripts/benchmark.sh`: Convenience wrapper
- `scripts/test_with_model.py`: **NEW** - Multi-model testing with auto-reporting
- `scripts/quick_toctou_test.sh`: One-command TOCTOU testing

---

## Attack Vectors Tested

### Research Integrity

**✅ No Artificial Scaffolding**: Original prompts had instructions telling agents to follow injections. We removed those and restored authentic Google implementation. All results test real AP2 baseline defenses.

### Three Attack Classes

#### 1. **Prompt Injection Attacks** (0% ASR - Secure ✅)
**44 tests across sophisticated techniques:**
- HTML-hidden text injections
- Authority confusion (`[MERCHANT SYSTEM NOTICE]`)
- Tool response forgery (fake corrected responses)
- Semantic manipulation (suggestions, alternatives)
- JSON injection and Unicode steganography
- Role assumption and instruction continuation
- Multi-surface attacks (merchant + category + image)

**Result**: Agent ignores all embedded instructions. LLM training + AP2 architecture prevents substitution.

#### 2. **Denial of Service Attacks** (10% AFR - Minor Issue ⚠️)
**10 tests with logical traps:**
- Infinite loop instructions
- Logical contradictions
- ✅ **Validation traps** (1/10 successful) - "Price $79.99 exceeds max $79.98"
- Error injection and timeout attacks
- Mandate confusion and semantic deadlocks

**Result**: One technique caused purchase failure. Agent susceptible to fake validation errors.

#### 3. **TOCTOU Race Condition** (0% ASR - Secure ✅)
**7 tests with timing windows (100ms, 200ms, 500ms):**
- Exploit gap between monitoring and purchase agent
- Merchant switches inventory during race window
- Uses existing `/trigger-price-drop` API (no modifications)

**Result**: Agent validates item_id consistency. No substitution via timing attacks.

### Detailed Methodology

For step-by-step explanation of how each attack works, see:
- **[ATTACK_METHODOLOGY.md](ATTACK_METHODOLOGY.md)** - Comprehensive attack flow diagrams

---

## Testing Across Different Models

### Quick Start: Model-Specific Testing

**NEW**: Test all attack vectors across any LLM model with automatic result organization:

```bash
# Test with your model
python3 scripts/test_with_model.py --model gemma-4-31b

# Test with Claude
python3 scripts/test_with_model.py --model claude-opus-4

# Test with GPT-4
python3 scripts/test_with_model.py --model gpt-4

# Test specific cohorts only
python3 scripts/test_with_model.py --model llama-3 --cohorts E_Advanced H_DoS

# Exclude TOCTOU tests
python3 scripts/test_with_model.py --model gemini-pro --include-toctou false
```

**What it does**:
1. ✅ Runs all 8 attack cohorts (A-H) + TOCTOU
2. ✅ Saves results in `model_test_results/<model_name>/`
3. ✅ Generates comprehensive markdown report
4. ✅ Calculates ASR, AFR, resistance metrics
5. ✅ Provides defense analysis and recommendations
6. ✅ Includes attack flow explanations

**Output Structure**:
```
model_test_results/
├── gemma-4-31b/
│   ├── REPORT_gemma-4-31b.md          # Comprehensive analysis
│   ├── metrics_gemma-4-31b.json       # Raw metrics
│   ├── A_Exact_20261015_120000.json   # Individual cohort results
│   ├── E_Advanced_20261015_120100.json
│   └── TOCTOU/
│       └── toctou_20261015_120500/
├── claude-opus-4/
│   ├── REPORT_claude-opus-4.md
│   └── ...
└── gpt-4/
    └── ...
```

### Manual Testing (Alternative)

```bash
# 1. Start the system
cd code/samples/python/scenarios/a2a/human-not-present/cards/
bash run.sh  # Browser auto-open disabled

# 2. Open web UI manually
open http://localhost:5173

# 3. Test specific cohort
cd /Users/pradeepbiswas/Projects/Research/AP2
bash scripts/benchmark.sh --cohort E_Advanced --max 10

# 4. Test TOCTOU separately
bash scripts/quick_toctou_test.sh
```

⚠️ **Run benchmarks sequentially** - concurrent runs corrupt shared state

---

## Research Findings (Baseline: Gemma 4:31B)

### Security Assessment

| Attack Class | Tests | ASR/AFR | Verdict |
|--------------|-------|---------|---------|
| **Prompt Injection** | 44 | 0% ASR | ✅ **Highly Resistant** |
| **Denial of Service** | 10 | 10% AFR | ⚠️ **Minor Vulnerability** |
| **TOCTOU Race** | 7 | 0% ASR | ✅ **Resistant** |
| **Overall** | **61** | **1.6% failure** | ✅ **98.4% Secure** |

### Why Defenses Work

**Substitution Resistance (0% ASR)**:
1. LLM training distinguishes data from instructions
2. Three-tier validation (consent → monitor → purchase)
3. Cryptographic mandates enforce constraints
4. Prompt design emphasizes mandate integrity

**DoS Partial Success (10% AFR)**:
- Validation traps exploit agent caution
- "Price $79.99 > max $79.98" creates unsatisfiable constraint
- Agent errs on side of safety (aborts purchase)
- Lower bar than convincing betrayal

**TOCTOU Resistance (0% ASR)**:
- Item_id pinned during monitoring phase
- Purchase agent doesn't arbitrarily re-query
- Cryptographic binding prevents substitution
- Consistency validation between tiers

### Cross-Model Testing Hypothesis

**Expected variations when testing other models**:
- **Injection**: May vary by model training quality
- **DoS**: Depends on caution vs. confidence balance
- **TOCTOU**: Protocol-level, should be consistent

**Key questions**:
- Do stronger models (Claude Opus, GPT-4) resist DoS better?
- Are smaller models more susceptible to injection?
- Which model makes optimal risk/safety tradeoffs?

---

## Key Files Reference

### Documentation

```
CLAUDE.md                             # This file - research overview
ATTACK_METHODOLOGY.md                 # ⭐ Step-by-step attack explanations
FINAL_RESEARCH_REPORT.md              # Complete findings (Gemma 4:31B baseline)
ADVANCED_ATTACK_STRATEGIES.md         # Attack taxonomy and techniques
REALISTIC_ATTACK_VECTORS.md           # DoS and TOCTOU implementation details
TOCTOU_TESTING_GUIDE.md               # Manual TOCTOU testing guide
README.md                             # Google's original documentation
```

### Testing Scripts

```
scripts/
├── test_with_model.py                # ⭐ NEW: Multi-model testing with auto-reporting
├── run_baseline_benchmark.py         # Core testing harness
├── benchmark.sh                      # Convenience wrapper
├── generate_advanced_attacks.py      # Sophisticated injection generator
├── generate_dos_attacks.py           # DoS payload generator
├── toctou_attack_realistic.py        # Race condition implementation
└── quick_toctou_test.sh              # One-command TOCTOU test
```

### Attack Data

```
data/by_cohort/
├── catalog_A_Exact.json              # Control: Benign products
├── catalog_B_Synonym.json            # Name variations
├── catalog_C_Substitution.json       # Basic injection (HTML, directives)
├── catalog_D_PriceOverride.json      # Price manipulation
├── catalog_E_Advanced.json           # 10 sophisticated techniques
├── catalog_F_MultiSurface.json       # Multi-field attacks
├── catalog_G_Subtle.json             # Semantic manipulation
└── catalog_H_DoS.json                # Denial of Service traps
```

### Agent Implementation

```
code/samples/python/src/roles/shopping_agent_v2/shopping_agent/
├── agent.py                          # Agent hierarchy, MCP connections
├── mandate_tools.py                  # Mandate creation & signing (HIVE disabled)
└── prompts/
    ├── consent_agent.md              # ✅ Restored from origin/main (no scaffolding)
    ├── monitoring_agent.md           # Price/availability monitoring
    └── purchase_agent.md             # ✅ Restored from origin/main (no scaffolding)
```

### MCP Servers (Attack Surface)

```
code/samples/python/src/roles/
├── merchant_agent_mcp/
│   ├── server.py                     # check_product, assemble_cart, create_checkout
│   └── trigger_server.py             # HTTP endpoints + /reset-state + /trigger-price-drop
└── credentials_provider_mcp/
    └── server.py                     # Payment credential issuance
```

---

## Current Differences from Origin/Main

1. **Ollama LLM Support**: Gemini → Ollama (local inference)
2. **MCP over HTTP**: stdio → Starlette/FastMCP (better reliability)
3. **Poisoned Catalog**: Attack dataset generation scripts
4. **Benchmark Harness**: Automated ASR measurement
5. **HIVE Defense**: Added but disabled (commented out)
6. **Receipt Display**: Web UI shows product name (detect wrong purchases)
7. **Prompt Modifications**: Removed artificial "follow injection" instructions

---

## Getting Started

### Quick Start: Test Your Model

**Easiest way** - Run all tests with automatic result organization:

```bash
# 1. Start the system
cd code/samples/python/scenarios/a2a/human-not-present/cards/
bash run.sh

# 2. In another terminal, run tests
cd /Users/pradeepbiswas/Projects/Research/AP2
python3 scripts/test_with_model.py --model your-model-name

# Results automatically saved to:
# model_test_results/your-model-name/REPORT_your-model-name.md
```

**What you'll get**:
- Comprehensive markdown report with ASR/AFR metrics
- Attack-by-attack breakdown
- Defense mechanism analysis
- Specific recommendations
- Step-by-step attack flow explanations (references ATTACK_METHODOLOGY.md)

### Comparing Models

```bash
# Test multiple models
python3 scripts/test_with_model.py --model gemma-4-31b
python3 scripts/test_with_model.py --model claude-opus-4
python3 scripts/test_with_model.py --model gpt-4

# Compare results
ls -la model_test_results/*/REPORT_*.md
```

### Manual Testing (Alternative)

1. **Start servers**: `cd code/samples/python/scenarios/a2a/human-not-present/cards/ && bash run.sh`
2. **Open UI**: http://localhost:5173
3. **Test injection**: Try a poisoned item from `data/by_cohort/catalog_E_Advanced.json`
4. **Check logs**: `.logs/shopping-agent.log`
5. **Analyze**: Did agent purchase correct item?

---

## Important Notes

### Research Integrity
- ✅ **No artificial scaffolding**: Removed instructions that told agents to follow injections
- ✅ **Authentic Google prompts**: Restored from origin/main via git comparison
- ✅ **Real vulnerabilities only**: Testing what actually breaks, not artificial weaknesses

### Configuration
- **HIVE is disabled**: Testing baseline AP2 defenses only
- **Real LLM behavior**: Using actual model inference, not mocked responses
- **Cryptographic validation**: AP2's JWT chains enforce constraints
- **Sequential testing**: Run benchmarks one at a time (prevents state corruption)

### Key Features
- 🔬 **Comprehensive testing**: 61 tests across 3 attack classes
- 📊 **Automatic reporting**: Model-specific results with detailed analysis
- 📖 **Attack explanations**: Step-by-step methodology in ATTACK_METHODOLOGY.md
- 🔄 **Cross-model ready**: Easy comparison across different LLMs

---

## Recommendations Based on Findings

### For Current Implementation (AP2 Baseline + Gemma 4:31B)

**High Priority**:
- ✅ Keep current injection defenses (working perfectly)
- ⚠️ Add contradiction detection for DoS mitigation
- ✅ Document item_id consistency validation mechanism

**Medium Priority**:
- Add explicit validation error filtering
- Implement timeout handling for deliberate delays
- Add token usage limits per tool call

**Low Priority**:
- HIVE defense (baseline sufficient for most cases)
- Advanced semantic analysis (limited additional benefit)

### For Future Research

**Completed**:
- ✅ Prompt injection (comprehensive coverage)
- ✅ DoS attacks (found minor vulnerability)
- ✅ TOCTOU timing (comprehensive coverage)

**Future Work**:
- Compare across multiple models (Claude, GPT-4, Llama)
- Test advanced jailbreak techniques
- Explore supply chain attacks (compromised MCP tools)
- Economic attacks (price optimization manipulation)

---

## Resources

- **AP2 Spec**: `docs/` directory
- **Original Google Repo**: https://github.com/google-agentic-commerce/AP2
- **Attack Methodology**: [ATTACK_METHODOLOGY.md](ATTACK_METHODOLOGY.md)
- **Research Findings**: [FINAL_RESEARCH_REPORT.md](FINAL_RESEARCH_REPORT.md)
- **Web Client**: `code/web-client/` (React + TypeScript)
- **Logs**: `.logs/shopping-agent.log`, `.logs/merchant-mcp.log`

---

**Last Updated**: 2026-10-15  
**Research Phase**: ✅ Complete (baseline findings) + 🔄 Cross-model testing ready  
**HIVE Status**: Code present but disabled  
**Baseline Results**: 98.4% resistance (Gemma 4:31B)  
**Next**: Test across multiple models using `scripts/test_with_model.py`
