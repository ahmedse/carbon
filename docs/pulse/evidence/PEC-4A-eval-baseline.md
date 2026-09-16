# PEC-4A — Eval harness baseline (Nibras)

**Date:** 2026-09-16  
**Instance:** `nibras`  
**Entrypoint:** `python -m ai.eval.run_harness`  
**Pytest:** `pytest ai/eval ai/tests/redteam -q --maxfail=8 --disable-warnings`  
**Marker:** `eval_golden`

## What was measured

Offline / deterministic golden suite (no LLM). Scenarios cover:

| Category | Scenario IDs | Count |
|----------|--------------|-------|
| Net-pay grounding | NIB-NP-001 … NIB-NP-006 | 6 |
| Cross-employee deny | NIB-DENY-001 … NIB-DENY-003 | 3 |
| Payroll lifecycle consent | NIB-PAY-001 … NIB-PAY-005 | 5 |
| Ambiguous → clarify | NIB-CLAR-001 … NIB-CLAR-004 | 4 |
| Topic guard (out-of-scope) | NIB-TG-001 … NIB-TG-005 | 5 |
| Compound Q-1 | NIB-Q1-001 … NIB-Q1-002 | 2 |
| **Total** | | **25** (≥20) |

## Baseline metrics (measured 2026-09-16)

```json
{
  "instance": "nibras",
  "scenario_count": 25,
  "passed": 25,
  "failed": 0,
  "pass_rate": 1.0,
  "grounding_pass": 1.0,
  "deny_correctness": 1.0,
  "fabrication_rate": 0.0,
  "clarify_pass": 1.0,
  "lifecycle_pass": 1.0,
  "topic_guard_pass": 1.0,
  "compound_pass": 1.0,
  "latency_ms_total": 90.81,
  "tokens": 0,
  "failed_ids": []
}
```

**Gate:** `fabrication_rate` must be exactly `0`. Harness exits non-zero otherwise.

## Negative proofs (regression would fail)

1. Fabricated amount `9999.999` → `assert_no_pay_figures_beyond_db` raises.  
2. Leaked deny row → `assert_scoped_empty_for_denied` raises.  
3. Metadata-only compound answer (Q-1) → `assert_compound_net_pay_answer` raises (scenario NIB-Q1-002).

## CI wiring

`.github/workflows/ci.yml` job `backend` step **Eval harness golden (PEC-4A — nibras)**:

```bash
python -m ai.eval.run_harness
python -m pytest ai/eval ai/tests/redteam -q --maxfail=8 -m "not live" --disable-warnings
```

## Files

| File | Role |
|------|------|
| `backend/ai/eval/scenarios_nibras.py` | ≥20 golden scenario defs |
| `backend/ai/eval/run_harness.py` | CI entry + metrics JSON |
| `backend/ai/eval/test_harness_golden.py` | pytest `eval_golden` |
| `backend/ai/eval/checks.py` | compound + topic_guard asserts |
| `backend/pytest.ini` | `eval_golden` marker |
