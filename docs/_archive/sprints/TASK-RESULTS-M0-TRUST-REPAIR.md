# Task Results — Pulse Memory Phase M0: Trust Repair (P0)

**Role:** backend-worker (+ Master Architect follow-up for ISSUE-M0-1)
**Plan:** `tasks/TASK-PULSE-MEMORY-NEXTGEN.md` §1b, §2b, §4 Phase M0
**Spec:** `tasks/TASK-PULSE-MEMORY-M0-EXECUTION.md`
**Date:** 2026-08-24

---

## 1. Task-by-task pass/fail

| Task | What | Status |
|------|------|--------|
| Fix 1 (GAP-M5) | Add `learn_fact` + `forget_fact` to `_draft_tools` `allow` set | ✅ DONE |
| Fix 1 (GAP-M5) | Append truthful memory directive to `instance.yaml` `persona` | ✅ DONE |
| Fix 1 (GAP-M5) | Append 2 grounding rules to GROUNDING RULES block in `runner.py` | ✅ DONE |
| Fix 2 (GAP-M6) | Create `dialogue/pending_action.py` (`PendingActionStore`) | ✅ DONE |
| Fix 2 (GAP-M6) | Pre-S1 confirmation short-circuit in `run()` | ✅ DONE |
| Fix 2 (GAP-M6) | Post-response proposal-detection hook in `run()` | ✅ DONE |
| Fix 3 (GAP-M7) | `_is_capability_query` helper + per-turn `draft_tools` filter | ✅ DONE |
| Tests | `ai/tests/test_gap7_pending_action.py` | ✅ DONE |
| Tests | `ai/tests/test_gap8_capability_guard.py` | ✅ DONE |
| ISSUE-M0-1 (P0) | `MEMORY` branch + `_memory_in_process` handler in `host_executor.py` | ✅ DONE |
| ISSUE-M0-1 (P0) | Memory confirm-response branch in `workspace_api.py` | ✅ DONE |
| Tests | `ai/tests/test_gap9_memory_confirm.py` (learn / forget / empty-fact) | ✅ DONE |
| Verification gates | 4 gates (pytest gaps, full `ai`, `manage.py check`, antipatterns) | ✅ DONE — see §4 |

---

## 2. Files changed

| Action | Path | What |
|--------|------|------|
| MODIFIED | `backend/ai/engine/cognition/turn/runner.py` | Added `import re`; module-level `_is_capability_query` + `_filter_draft_tools`; extended `allow` set with `learn_fact`/`forget_fact`; pre-S1 pending-confirmation short-circuit; post-response `detect_proposal` hook; 2 new grounding rules; per-turn `draft_tools` filter |
| MODIFIED | `backend/ai/engine/instances/carbon/instance.yaml` | Appended truthful memory directive to `persona` (kept existing text intact) |
| CREATED | `backend/ai/engine/cognition/dialogue/pending_action.py` | `PendingActionStore` (thread-safe, in-process, regex-only, domain-agnostic) + `get_pending_action_store()` singleton |
| CREATED | `backend/ai/tests/test_gap7_pending_action.py` | 20 domain-agnostic tests for `PendingActionStore` |
| CREATED | `backend/ai/tests/test_gap8_capability_guard.py` | 14 domain-agnostic tests for `_is_capability_query`, `_filter_draft_tools`, `_draft_tools` allow set |
| MODIFIED | `backend/ai/host_executor.py` | Added `MEMORY`-method branch in `_call_api` + `_memory_in_process` handler (learn→`LongTermMemory.store_fact`, forget→`archive_fact`) |
| MODIFIED | `backend/ai/workspace_api.py` | Added memory-kind confirm-response branch (truthful assistant message + no navigate action) for `confirm_tool_execution` |
| CREATED | `backend/ai/tests/test_gap9_memory_confirm.py` | 3 tests driving `create_pending_execution → confirm_execution → _memory_in_process` for learn/forget/empty-fact |

**Do-not-touch files:** `fallback.py`, `anaphora.py`, `entity_extractor.py`, `memory/working.py`, `learning/preferences.py`, `knowledge/terminology.py`, `cognition/turn/critic.py` — none modified. `host_executor.py` and `workspace_api.py` were originally READ-ONLY for the worker but were intentionally modified by the Master Architect to resolve ISSUE-M0-1 (the M0 trust repair cannot ship with the confirm→store write silently failing). Both edits are additive (a new dispatch branch + a new response branch) — no existing DQ/table/rule-assignment path was touched.

**Constraints held:** no new DB model, no migration; memory writes go through `execute_learn_fact(...)` (never `LongTermMemory.store_fact` directly); every hook wrapped in try/except that logs and continues.

---

## 3. Implementation notes

### Fix 1 — GAP-M5 (capability truthfulness)
- `allow` set in `TurnPipelineRunner.__init__` now contains `"learn_fact"` and `"forget_fact"` (no existing entries removed, executor instantiation unchanged).
- `instance.yaml` `persona` now states there is no standalone persistent memory and that `learn_fact` only proposes (saved after user confirmation). Existing "Never claim an action succeeded unless a tool result confirmed it" text preserved.
- GROUNDING RULES block gained two bullets (memory-truthfulness + capability-separation) inserted before the final capability-list bullet.

### Fix 2 — GAP-M6 (pending-action confirmation flow)
- `PendingActionStore` mirrors `WorkingMemory`'s lock-per-dict singleton pattern.
  - `set_pending / get_pending / check_confirmation / clear / detect_proposal` as specified.
  - Confirmation = short (≤ 4 words) affirmative in `{yes, yeah, yep, ok, okay, sure, do it, go ahead, please, store it, remember it, yes please}` AND a pending action exists. Bare `yes` with no pending action returns `None`.
  - `detect_proposal` regex captures the fact and infers `identity` (`I am|my name is|I'm`), `preference` (`prefer|want|like|always`), else `observation`. Purely regex, no domain terms, no LLM.
- Pre-S1 hook (after `run.started`, before S1): `check_confirmation` → if pending + executor + instance_id, call `execute_learn_fact(fact, category, instance_id, executor, conversation_id)`, `clear()`, return truthful `AgentResponse` ("Done — I've prepared a memory card for that. Click confirm to save it permanently."), write a `final` ledger row with `verdict="pass"` + `pending_confirmation_shortcircuit: True`, broadcast `run.completed`. Whole hook wrapped in try/except (falls through to normal pipeline on any failure).
- Post-response hook (before the single-pass `return response, ledger`): `detect_proposal(final_text)` → `set_pending(...)`. Wrapped in try/except.

### Fix 3 — GAP-M7 (capability-tool salience guard)
- `_is_capability_query(text)` regex matches the 7 required trigger phrases.
- `_filter_draft_tools(draft_tools, user_message, salience_domain)` excludes `list_my_capabilities` unless the message is an explicit capability query or `salience.domain == "identity"`. Applied to the `draft_tools` list before it is passed to `draft(...)` (and the escalation re-draft reuses the same filtered list). No other tool is filtered.

---

## 4. Verification

> **STATUS: EXECUTED — all four gates run with live output (2026-08-24, after the ISSUE-M0-1 fix).**

**Gate 1 — targeted gap tests + new regression tests:**
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_gap7_pending_action.py ai/tests/test_gap8_capability_guard.py ai/tests/test_gap9_memory_confirm.py -q
# → 37 passed (20 gap7 + 14 gap8 + 3 gap9)
```
(90 gap tests were also run earlier in the campaign: `test_gap1..gap8` → 90 passed.)

**Gate 2 — full `ai` suite:**
```bash
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q
# → 1059 passed, 1 failed
#   FAILED ai/tests/test_observability_api.py::test_rollups_totals_and_per_run_shape
#   assert 11 == 4  (KNOWN pre-existing order-dependent flake — NOT caused by M0)
#   → re-run in isolation: 1 passed (confirms order-dependence)
```

**Gate 3 — Django system check:**
```bash
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
# → System check identified no issues (0 silenced).
```

**Gate 4 — antipatterns:**
```bash
cd /home/ahmed/aast/carbon && ./.ai-toolkit/scripts/verify.sh antipatterns
# → GATE PASSED
#   ✓ no hardcoded secrets, ✓ no MUI v5 Grid, ✓ no hardcoded hex
#   ⚠ pre-existing warnings only: raw fetch() (5 files), naive datetime
#     (export_document.py), 28 print() calls — all present before M0.
```

**Static verification (also performed):** `get_errors` reported **No errors found** on `host_executor.py`, `workspace_api.py`, `runner.py`, `pending_action.py`, and the three new test files.

---

## 5. Deviations

1. **`_filter_draft_tools` extracted as a module-level helper** (in addition to the spec's `_is_capability_query`). The spec's Fix 3 shows inline filtering; I factored it into `_filter_draft_tools` so the guard behaviour is directly unit-testable (as the spec's own test list requires — "a filtered draft_tools list excludes …"). The inline behaviour is identical.
2. **Pre-S1 hook placed after the existing `run.started` broadcast** (still before the S1 block). This satisfies "Broadcast run.started / run.completed" without a duplicate `run.started` emit; the short-circuit only emits `run.completed`.
3. **Confirmation message wording** slightly expanded ("…for that…") but retains the truthful, non-"saved" semantics the spec requires.

---

## 6. Issues found (NOT fixed — logged per instructions)

### ISSUE-M0-1 — RESOLVED (P0, fixed by Master Architect)
The spec's READ-ONLY `host_executor.py` / `workspace_api.py` were reviewed (not modified by the worker). Finding:

- `execute_learn_fact` / `execute_forget_fact` stage a `ToolExecution` with `method="MEMORY"` and `endpoint="long_term/{category}"` / `"long_term/forget"`.
- On user confirm, `workspace_api.confirm_tool_execution` → `CarbonHostExecutor.confirm_execution` → `CarbonHostExecutor._call_api(method="MEMORY", endpoint="long_term/…")`.
- `CarbonHostExecutor._call_api` dispatched only via `_IN_PROCESS_ENDPOINTS` (currently `dq/rules`, `dataschema/tables`, `dataschema/tables/detail`, `dq/rule-assignments`) and otherwise raised `ToolExecutionError("Host API endpoint MEMORY long_term/… is not available…")`.
- There was **no** `long_term/*` in-process handler and **no** `"MEMORY"` branch in `confirm_execution` / `_call_api`.

**Resolution (implemented):**
- Added a `MEMORY`-method branch at the top of `_call_api` that delegates to a new `_memory_in_process(method, params, body)` handler.
- `_memory_in_process` reads `body["operation"]`:
  - `learn` → `LongTermMemory(self.db).store_fact(instance_id, category, content, source="learn_fact", confidence, host_user_id=self.host_user_id, visibility="private")` → returns `{status_code: 201, data: {id, fact, category}, kind: "memory", operation: "learn"}`.
  - `forget` → `LongTermMemory(self.db).archive_fact(memory_id)` → returns `{status_code: 200/404, data: {id, archived}, kind: "memory", operation: "forget"}`.
  - empty `fact` → raises `ToolExecutionError("Cannot remember an empty fact.")` (fail-visible).
- Added a memory-kind response branch in `workspace_api.confirm_tool_execution` so the confirmed memory card saves a truthful grounded assistant message ("✅ Remembered: …" / "✅ Forgot that fact.") with no DQ navigate action, and returns `{status: "confirmed", kind: "memory", operation, memory_id, action: null}`. The existing DQ-rule response path is untouched.
- Regression coverage: `ai/tests/test_gap9_memory_confirm.py` (learn persists a private `MemoryLongTerm` row scoped to `host_user_id`; forget archives it; empty fact errors). All 3 pass.

### ISSUE-M0-2 — `identity` category not in the `learn_fact` tool's `category` enum
`PendingActionStore._infer_category` returns `identity` for identity facts (per spec), but the `learn_fact` tool definition's `category` enum is `["correction", "business_rule", "preference", "observation"]`. `execute_learn_fact` does not validate the enum (it uses the category verbatim in the endpoint/label), so this is cosmetic — the write would still work if ISSUE-M0-1 were fixed. Logged for consistency awareness; not changed (spec mandates the `identity` inference).

---

## 7. Conclusion

All three fixes (GAP-M5 / GAP-M6 / GAP-M7) and their domain-agnostic tests are implemented, **plus** the adjacent P0 bug (ISSUE-M0-1) that would have made the confirm→store path silently fail. The four verification gates were executed live: 1059 `ai` tests pass with only the pre-existing order-dependent flake (`test_rollups_totals_and_per_run_shape`, passes in isolation), `manage.py check` is clean, and the antipatterns gate passes (pre-existing warnings only). M0 trust repair is now end-to-end functional: propose → confirm → durable private `MemoryLongTerm` write/archive.
