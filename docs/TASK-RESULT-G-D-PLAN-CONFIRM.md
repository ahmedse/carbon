# TASK RESULT — G-D: plan_task Confirm Workflow End-to-End + Provenance Surface

**Date:** 2026-08-25
**Gate:** G-D — "Planner → Coworker": the chat-native plan lifecycle
(`plan_task` → `edit_plan` → `approve_plan` → run) settles and executes with an
audit ledger, and every claim carries its source (provenance).
**Status:** ✅ GATE MET

---

## 1. Objective

Prove the F6 (Agentic Workflow) exit gate end-to-end, *inside the chat*, without
bouncing to the Tasks panel for the planning half:

```
discuss → decompose → propose → (edit_plan) → "settled?" → (approve_plan) → run
```

Two sub-goals:

1. **Confirm workflow end-to-end** — `plan_task` drafts a `pending_approval`
   plan (never executes inline), `edit_plan` revises without auto-approving
   (RULE_21), `approve_plan` is the explicit settle gate, and `run` is a
   separate, explicit action whose steps complete under an audit ledger.
2. **Provenance surface** — every claim/outcome carries its source (retrieved
   fact / tool result / model inference), never a bare assertion. Provenance is
   surfaced in three layers already present in the platform: message-level
   (`_build_message_provenance`), knowledge-graph (`KgProvenance` rows, exposed
   in the `graph` observability panel), and tool-grounded outcome copy
   (`_grounded_outcome_note` / `_grounded_access_table`).

## 2. What already existed (survey)

The W3-A/W3-C plans layer (`ai/plans_service.PlansService`) already owned every
state transition, with full owner-scoping (CBAC) and service-level tests:

- `create_plan` — brief → `pending_approval` `Run` + `RunStep` rows (planning
  only, RULE_21).
- `approve_plan` / `decline_plan` — plan-level consent transitions.
- `edit_plan` — re-plan + `{added, removed, changed}` diff; non-pending plans
  drop back to `pending_approval` (`replan_gate`).
- `run_plan_stream` — SSE frames (`plan_start → step_start → step_result →
  step_end → done`) with per-step consent.

The chat-native bridges (`ai/plugins/plan_task.py`, `ai/plugins/plan_lifecycle.py`
with `edit_plan` / `approve_plan`) were present but **untested directly** — the
gap G-D closes.

## 3. Changes

### 3.1 `ai/tests/test_plan_lifecycle.py` — NEW (the gap)

12 tests covering the chat-native confirm workflow, mirroring `test_plans.py`'s
engine-seam fakes (`_FakePlanner`, `_FakeReActLoop`, `_FakeFactory`):

| Test | Proves |
|------|--------|
| `test_plan_lifecycle_plugins_registered` | `plan_task`, `edit_plan`, `approve_plan` all registered |
| `test_edit_plan_metadata` / `test_approve_plan_metadata` | non-mutating (`requires_confirmation=False`), correct input schema |
| `test_edit_plan_requires_authenticated_session` | auth gate |
| `test_approve_plan_requires_authenticated_session` | auth gate |
| `test_edit_plan_requires_brief_or_deltas` | validation gate |
| `test_approve_plan_unknown_user_is_graceful` | fail-visible, no crash |
| `test_edit_plan_revises_and_never_auto_approves` | F6: editing never auto-approves |
| `test_approve_plan_settles_plan` | F6-03: settle gate + audit-ledger copy (provenance, RULE_23) |
| `test_approve_plan_rejects_non_pending` | double-approve is a graceful error |
| `test_plan_task_does_not_fabricate_completion` | F6-06: steps are `pending`, not done |
| `test_full_chat_confirm_workflow_end_to_end` | F6-01/03/05: plan → approve → run → `completed` with ledger |

No production code changed — the bridges were already correct; the task was to
**prove** them with deterministic, order-independent tests (the F6 gate is a
verification gate, not a build gate).

## 4. Verification Evidence

```
$ pytest ai/tests/test_plan_lifecycle.py -q
12 passed in 5.20s

$ pytest ai/tests/test_plan_task.py ai/tests/test_plan_lifecycle.py \
    ai/tests/test_plans.py ai/tests/test_observability_api.py \
    ai/tests/test_chat_wiring.py ai/tests/test_tool_execution_actions.py -q
116 passed in 28.49s

$ pytest ai -q
1096 passed, 1 failed in 158.71s
   └─ failed = test_observability_api.py::test_rollups_totals_and_per_run_shape
      (KNOWN order-dependent flake — passes in isolation: 1 passed in 1.48s)
```

## 5. Verdict

**✅ GATE MET.** F6 is green:

- F6-01 — `plan_task` produces a `pending_approval` plan, never inline execution.
- F6-02 — RULE_21 holds: `edit_plan`/`approve_plan` are non-mutating or the
  consent gate itself; no write happens without approval.
- F6-03 — confirm/settle gate transitions correctly.
- F6-05 — multi-step DAG visible with `awaiting_approval`/`pending` tokens.
- F6-06 — no fabricated completion: statuses reflect reality at each gate.

Provenance is surfaced at message, KG, and tool-outcome layers; the plan
lifecycle outcome copy names the audit ledger in product terms (RULE_23, no
engine leakage).

### Residuals

None introduced. The pre-existing `test_rollups_totals_and_per_run_shape`
order-dependent flake (unrelated to G-D) remains as documented in G-C.
