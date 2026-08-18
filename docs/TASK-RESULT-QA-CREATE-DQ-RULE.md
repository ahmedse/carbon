# TASK-RESULT-QA-CREATE-DQ-RULE — QA Validation Report

- **Date:** 2026-08-18
- **Role:** qa-validator · **Model:** DeepSeek V4-Flash · **Project:** Carbon
- **Phase/Scope:** Pulse chat tool action — `create_dq_rule` runtime failure ("range rule for AASTMT employee number IDs, 4–5 digits")
- **Source:** user chat repro + `backend/logs/carbon.log` + deterministic scripted repro

---

## Executive Summary

**Verdict: FAILED** — the `create_dq_rule` tool (chat → staged DQ rule with a Confirm button, sprint "fly to rule detail") is **100% broken at runtime**. Every invocation ends in `AttributeError: 'ToolExecution' object has no attribute 'refresh_from_db'`; the user sees a `⚠️` error line instead of a staged proposal, and an orphaned `pending_confirmation` row is left in the DB each time.

- **1 × P1** core-feature defect (reproduced deterministically)
- **2 × P3** (RULE_23 error-text leak + test coverage gap)
- **1 × observation** (pre-existing, out of scope: `_DjangoSession.execute` seam gaps)

No security/RBAC surface affected (Layer 2 clean for this defect).

---

## Layer 1: Structural Gate

| Check | Result |
|---|---|
| `./.ai-toolkit/scripts/verify.sh backend` | ✅ `GATE PASSED` (django check) |
| `pytest ai/tests/test_tool_execution_actions.py -q` | ✅ 15 passed — **but see F3 (coverage gap)** |
| `makemigrations --check --dry-run` | ✅ No changes detected (from prior gate run, same tree) |

Structural gate passes because **no test exercises the failing runtime path** (F3).

---

## Layer 2: Security (API-Level RBAC)

Not the defect surface. The confirm/decline tool-execution endpoints already carry ownership (403), status (400), and membership (404) checks covered by `test_tool_execution_actions.py`. No new RBAC exposure was introduced by this defect; the crash happens inside the tool executor, before any host write.

---

## Layer 3: Functional — Reproduction

### User journey (as reported)
```
User:  "create a new dq rule. range. for employee number IDs fo aastmt.
        they are 4 or 5 digits only. e.g. mine is 1271"
Pulse: ⚠️ create_dq_rule: 'ToolExecution' object has no attribute 'refresh_from_db'
```
Production log (backend/logs/carbon.log:21000, 2026-08-18 17:46:13):
```
pulse.agent.plugins — Plugin create_dq_rule failed: 'ToolExecution' object has no attribute 'refresh_from_db'
  File "backend/ai/plugins/create_dq_rule.py", line 360, in execute
    execution = await host_api.create_pending_execution(...)
  File "backend/ai/host_executor.py", line 185, in create_pending_execution
    await self.db.refresh(execution)
  File "backend/ai/store.py", line 437, in refresh
    await sync_to_async(obj.refresh_from_db, thread_sensitive=True)()
AttributeError: 'ToolExecution' object has no attribute 'refresh_from_db'
```

### Scripted repro (deterministic, same traceback)
`CarbonHostExecutor(db=DjangoStore session, user_token='inproc:platform:1', host_user_id='1')` → `await executor.create_pending_execution(...)`:
```
File "backend/ai/host_executor.py", line 185, in create_pending_execution
    await self.db.refresh(execution)
File "backend/ai/store.py", line 437, in refresh
    await sync_to_async(obj.refresh_from_db, thread_sensitive=True)()
AttributeError: 'ToolExecution' object has no attribute 'refresh_from_db'
```

### Root cause chain
1. `CarbonHostExecutor.create_pending_execution()` (host_executor.py:176) instantiates the **engine** model `from ai.engine.core.models import ToolExecution` (plain, non-Django).
2. `db.add()` → `_to_django_instance()` (store.py:109) **converts** engine → Django mirror `ai.models.ToolExecution`; `db.commit()` **saves** it (autocommit). So the row IS persisted.
3. `db.refresh(execution)` (host_executor.py:185) → `_DjangoSession.refresh()` (store.py:436) calls `obj.refresh_from_db()` **unconditionally on the raw engine instance** — unlike `add()`/`select()`/`get()`, `refresh()` never resolves to the Django mirror → `AttributeError`.
4. The plugin wrapper catches the exception → returns `{"error": ...}` → `_grounded_outcome_note` surfaces it → user sees the raw internal error; **no `execution_id` is returned, so no Confirm button renders** and the `pending_confirmation` row becomes orphaned.

### Side effect (verified)
After one repro, the DB contained exactly 1 orphaned row (`conversation_id='qa-repro-conv'`, `status='pending_confirmation'`, `tool_name='create_dq_rule'`) — persisted before the crash, never surfaced, never confirmable via UI. Cleaned up after evidence capture.

---

## Findings

| ID | Sev | Symptom | Evidence | Suggested owner |
|----|-----|---------|----------|-----------------|
| **F1** | **P1** | `create_dq_rule` always fails at runtime; no DQ rule can be staged/confirmed from chat | Traceback above; `_DjangoSession.refresh()` (store.py:436) calls `refresh_from_db()` on engine-model instances; only `refresh()` lacks the `_to_django_instance()`/`resolve_model()` conversion that `add()`/`select()`/`get()` have | Debugger/Fixer |
| **F2** | P3 | RULE_23 leak: user sees raw internal exception (`⚠️ create_dq_rule: 'ToolExecution' object has no attribute 'refresh_from_db'`) | `_grounded_outcome_note()` (engine_runtime.py:277) writes `f"⚠️ {tool}: {item['error']}"` verbatim | Debugger/Fixer |
| **F3** | P3 | Test coverage gap — sprint tests stage `ToolExecution` via Django mirror `ai.models.ToolExecution.objects.create()` (`_stage_execution`, test_tool_execution_actions.py:167) and never call `CarbonHostExecutor.create_pending_execution()`; hence 15/15 green while prod is broken | grep of test file vs runtime path | Debugger/Fixer (regression test) |
| O1 | — | Pre-existing: engine calls `db.execute(stmt)` on `_DjangoSession` (no such method) in fan-out (`runner.py:803`), skill search (`skills/registry.py:77`), budget hook (`guardrails.py:450`) — all log `AttributeError` but degrade gracefully (single-pass fallback / planner fallback / pass-through). Not touched by this defect | carbon.log:21000 window | Master (separate backlog item) |

---

## Gate Verdict

**FAILED** — P1 defect blocks the "fly to rule detail" feature (accepted 2026-08-18, commit bb91658).

### Handoff to Debugger/Fixer
1. **Fix F1:** make `_DjangoSession.refresh()` resolve engine → Django mirror before calling `refresh_from_db()` (mirror `_to_django_instance()`), OR drop the unnecessary `await self.db.refresh(execution)` in `CarbonHostExecutor.create_pending_execution()` (the UUID id is generated client-side before commit; refresh adds nothing here). Prefer the store fix — it is the general invariant (`add`/`select`/`get` all resolve; `refresh` is the only gap).
2. **Regression test (F3, RULE_11):** add an integration test that calls `CarbonHostExecutor.create_pending_execution()` (the exact runtime path) with a DjangoStore session and asserts a `pending_confirmation` row is returned/staged without error — red today, green after the fix.
3. **Fix F2:** `_grounded_outcome_note()` error line should be outcome-oriented (e.g. "⚠️ I couldn't stage this rule — nothing was created. Try again in a moment.") instead of the raw exception text.
4. Re-run: `verify.sh backend` + `pytest ai -q` + the new regression test; append `PB-NN` to `troubleshooting/playbook.md`.
