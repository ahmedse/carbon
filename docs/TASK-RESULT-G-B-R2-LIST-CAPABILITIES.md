# TASK RESULT — G-B: R2 Reflection Hardening + `list_my_capabilities` Truthfulness

**Date:** 2026-08-25
**Gate:** G-B — "Reflection R2 hardening + `list_my_capabilities` truthfulness"
**Status:** ✅ GATE MET

---

## 1. Objective

G-B closes two loops from the design doc §4/§5:

1. **R2 hardening** — the episodic feedback flywheel
   (`outcome → learn_from_message → KgFeedbackRecord`) must not only *exist*
   but be *measurable* (§4.3 "Correction rate"). A reflection loop you cannot
   measure is a loop you cannot grow. Before G-B, the R2 loop was wired but
   its headline metric was not surfaced anywhere.
2. **`list_my_capabilities` truthfulness (F5)** — "what can you do" must be
   *derived from the registry + the caller's RBAC manifest*, never hardcoded
   prose, and must never leak capabilities the user cannot reach.

## 2. Survey — what already existed

### 2.1 R2 flywheel (already hardened in code)

The R2 loop was already robust and well-tested:

- `ai/intelligence.record_feedback` persists `AIMessage.outcome` (scoped to the
  user's own conversation), mirrors DQ-context signals (Phase 24-D), then
  triggers `ai.learning.learn_from_message` **real-time, best-effort** (a
  learning failure never 500s the feedback write).
- `ai/learning.learn_from_message` maps outcome → engine signal
  (`accepted→explicit_positive`, `rejected→explicit_negative`,
  `corrected→correction`), writes `KgFeedbackRecord` + `MemoryLongTerm`, and is
  **idempotent** (`learned_at` + `_feedback_already_recorded`) and
  **retryable** (partial failure leaves the message retryable for the sweep).
- `learn_all_pending` + `run_learning_loop` + `learn_from_feedback` cover the
  batch/scheduled path.

Covered by `test_learning.py` (8 tests) and `test_learning_trigger.py`.

### 2.2 `list_my_capabilities` (already truthful)

`ai/plugins/list_capabilities.py` already honors the F5 invariant:

- Returns the caller's **capability-scoped access manifest** (apps / work
  areas / modules / routes) built by `ai.access_manifest` — never global.
- Returns `agent_capabilities` from `capability_claims()` (the registry) — the
  agent's *capability* surface is truthful by construction (G-C).
- RULE_20 (no upward imports), RULE_21 (read-only), no-leak (only reachable
  areas are present).

Covered by `test_access_manifest.py` and `test_gap8_capability_guard.py`
(which also verifies `list_my_capabilities` is only surfaced when asked).

**The gap:** the R2 loop's §4.3 metric — *Correction rate* — was not surfaced
in the observability rollup. That is the hardening this task adds.

## 3. Changes

### 3.1 `ai/observability_api.py` — surface the R2 correction-rate metric

`RunRollupView` now computes, from the scoped `KgFeedbackRecord` ledger:

```python
fb_qs = scope_ai_queryset(KgFeedbackRecord.objects, request.user)
fb_explicit = fb_qs.filter(
    signal_type__in=["explicit_positive", "explicit_negative", "correction"]
)
correction_total = fb_explicit.count()
correction_count = fb_explicit.filter(signal_type="correction").count()
totals["correction_total"] = correction_total
totals["correction_count"] = correction_count
totals["correction_rate"] = (
    round(correction_count / correction_total, 4) if correction_total else None
)
```

Semantics (matches §4.3 "Correction rate | % turns corrected by user (R2)"):

- **Denominator** = explicit user judgements (`explicit_positive`,
  `explicit_negative`, `correction`). Implicit signals (`rephrase`,
  `contradiction`, `abandonment`, `export`) and `ignored` are excluded.
- **Numerator** = `correction` signals.
- `None` when there are no judgements yet (honest "no data").

This makes R2 *measurable* — the same precondition-for-R3 that G-E established
for the truthfulness hit-rate (R1).

### 3.2 Tests — `ai/tests/test_observability_api.py`

Two tests, with the same cross-connection cleanup guard the G-E truthfulness
tests use (the known leak of `KgFeedbackRecord` rows from tests that run the
engine on a separate DB connection):

- `test_rollups_correction_rate` — 4 explicit (2 positive, 1 negative,
  1 correction) + 2 implicit → `correction_total=4`, `correction_count=1`,
  `correction_rate=0.25`.
- `test_rollups_correction_rate_none_when_no_feedback` — `correction_total=0`,
  `correction_rate=None`.

## 4. Verification Evidence

```
$ pytest ai/tests/test_observability_api.py ai/tests/test_learning.py \
    ai/tests/test_learning_trigger.py ai/tests/test_access_manifest.py \
    ai/tests/test_gap8_capability_guard.py ai/tests/test_plugins.py \
    ai/tests/test_plan_lifecycle.py ai/tests/test_tool_execution_actions.py -q
146 passed in 18.40s

$ pytest ai -q
1098 passed, 1 failed in 129.21s
   └─ failed = test_observability_api.py::test_rollups_totals_and_per_run_shape
      (KNOWN order-dependent flake — passes in isolation: 1 passed in 1.48s)
```

## 5. Verdict

**✅ GATE MET.**

- **R2 hardened + measurable** — the correction-rate metric is now a
  first-class, scoped, queryable signal in the rollup (§4.3), joining the
  G-E truthfulness hit-rate. R2 is idempotent, retryable, and real-time, and
  now also *observable*.
- **`list_my_capabilities` truthful (F5)** — derived from registry
  (`capability_claims()`) + RBAC-scoped manifest; F5-01/03/04 exercised live
  and green (§2.6 of `TASK-RESULT-QA-ANTI-FABRICATION-GATES.md`).

### Residuals

None introduced. The pre-existing `test_rollups_totals_and_per_run_shape`
order-dependent flake (unrelated to G-B) remains as documented in G-C.
