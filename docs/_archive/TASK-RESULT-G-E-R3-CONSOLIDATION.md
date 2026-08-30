# TASK RESULT — G-E: R3 Consolidation Observability (Truthfulness Hit-Rate)

**Date:** 2026-08-25
**Gate:** G-E — "Reflective system": R3 consolidation is *measurable* (§4.3
metrics). This task makes the first metric — **truthfulness hit-rate** — a
first-class, queryable signal, recorded per-turn and aggregated in the Pulse
observability rollup.
**Status:** ✅ GATE MET (metrics surface live; R3 distill itself is host-side
and human/agent-reviewed — see §5)

---

## 1. Objective

The design doc §4.3 defines five growth metrics; the first row is:

> **Truthfulness hit-rate** — % turns with zero gate flags — `ledger flags`

Before this task, the F1–F3 anti-fabrication gate flags (`apply_anti_hallucination_gate`)
were computed per turn but **discarded** (`_anti_flags` was never persisted or
surfaced). The metric was therefore unmeasurable — the gate ran, but there was
no evidence layer. G-E closes that loop:

1. **Persist** the gate flags as a `turn_ledger` stage (`truthfulness_gate`,
   `stage_index=7`) every turn.
2. **Surface** `truthfulness_flags` + `truthful` on the chat result so the
   workspace layer can reflect it and QA can assert on it.
3. **Aggregate** the hit-rate in the observability rollup so it trends over time.

## 2. Changes

### 2.1 `ai/engine_runtime.py` — persist + surface the gate signal

In `_run_chat`, the previously-discarded `_anti_flags` is now `anti_flags` and:

```python
content, anti_flags = apply_anti_hallucination_gate(response.text, completed_tools)
...
await _record_truthfulness_gate(db=db, ledger=ledger, anti_flags=anti_flags)
```

The result dict gains:

```python
"truthfulness_flags": list(anti_flags),   # F1–F3 flags, verbatim
"truthful": not anti_flags,               # bool gate signal
```

New helper (best-effort, never-raising — observability must never fail a turn):

```python
async def _record_truthfulness_gate(db, ledger, anti_flags: list[str]) -> None:
    await LedgerWitness().record_stage(
        db=db, turn_id=ledger.turn_id, instance_id=ledger.instance_id,
        conversation_id=ledger.conversation_id, host_user_id=ledger.host_user_id,
        stage="truthfulness_gate", stage_index=7,
        verdict="pass" if not anti_flags else "flag",
        flags=list(anti_flags),
    )
```

A clean turn records `flags_json=None` (the ledger witness's "no flags"
convention); a flagged turn records the F1–F3 flag list.

### 2.2 `ai/observability_api.py` — aggregate the hit-rate

`RunRollupView` now computes, scoped to the requesting user:

```python
truth_qs = scope_ai_queryset(TurnLedgerRow.objects, request.user).filter(
    stage="truthfulness_gate"
)
truth_total = truth_qs.count()
truth_flagged = truth_qs.exclude(flags_json__isnull=True).exclude(flags_json=[]).count()
totals["truthfulness_total"] = truth_total
totals["truthfulness_flagged"] = truth_flagged
totals["truthfulness_hit_rate"] = round(1 - truth_flagged / truth_total, 4) if truth_total else None
```

### 2.3 Tests

- `ai/tests/test_tool_execution_actions.py` — 2 unit tests for
  `_record_truthfulness_gate` (writes the correct stage/verdict/flags; never
  raises on a broken db).
- `ai/tests/test_observability_api.py` — 2 rollup tests (hit-rate = 0.75 for
  3 clean + 1 flagged; `None` when no turns), with a cleanup guard against the
  suite's known cross-connection ledger-row leak.

## 3. Verification Evidence

```
$ pytest ai/tests/test_tool_execution_actions.py ai/tests/test_observability_api.py -q
53 passed in 7.18s

$ pytest ai/tests/test_observability_api.py -q
12 passed in 5.60s

$ pytest ai -q
1096 passed, 1 failed in 158.71s
   └─ failed = test_observability_api.py::test_rollups_totals_and_per_run_shape
      (KNOWN order-dependent flake — passes in isolation: 1 passed in 1.48s;
       the 3 truthfulness-gate regressions from the pre-guard run are GONE)
```

## 4. Metrics now measurable

| Metric | Signal | Where |
|--------|--------|-------|
| Truthfulness hit-rate | `truthfulness_total` / `truthfulness_flagged` / `truthfulness_hit_rate` | `GET /carbon-api/ai/pulse/rollups/` |
| Per-turn gate flags | `truthfulness_flags` / `truthful` | chat result (workspace layer) |
| Raw gate evidence | `turn_ledger` rows `stage="truthfulness_gate"` | `logs` observability panel |

## 5. Verdict

**✅ GATE MET** (metrics surface live). §4.3's first metric is now recorded
per-turn and aggregated per-user in the rollup, so growth is *measurable* — the
precondition for R3 consolidation.

The R3 distill job itself is, by design (§4.2), **host-side and human/agent-
reviewed** — it consumes the feedback flywheel (`KgFeedbackRecord`) and the
successful-turn evidence surfaced here, but never lets the engine mutate its
own memory/rules/config. That boundary is the sustainability guardrail and is
unchanged by this task.

### Residuals

None introduced. The pre-existing `test_rollups_totals_and_per_run_shape`
order-dependent flake (unrelated to G-E) remains as documented in G-C.
