# Task Results — Pulse Vendoring Phase 2b-3a: Wire `dq.validate` + `dq.suggest` In-Process

Status: **COMPLETE — worker implementation, awaiting Master Architect commit**
Spec: `plans/TASKS-PULSE-VENDOR-PHASE-2B-3A-DQ.md`

## Summary

Wired the final two DQ task types (`dq.validate`, `dq.suggest`) in-process in
`backend/ai/engine_runtime.py`, completing the task-type matrix. Both are
LLM-only (fail-visible by construction — no deterministic fallback). The dead
`not_wired` fallthrough in `dispatch_task` was removed; every task in `MODULES`
is now covered by `_TASK_HANDLERS` ∪ `chat`.

## Files changed

| Path | Change |
|------|--------|
| `backend/ai/engine_runtime.py` | Added `_run_dq_validate`, `_run_dq_suggest`, prompt builders (`_dq_validate_prompt`, `_dq_suggest_prompt`), `_coerce_confidence`, `_llm_unavailable`; extended `_llm_text` with `response_format` pass-through; registered both handlers in `_TASK_HANDLERS`; removed the `not_wired` fallthrough in `dispatch_task` (missing handler now surfaces fail-visible as `engine_error`). |
| `backend/ai/tests/test_dq_wiring.py` | **NEW** — 10 tests: validate completed (fail + pass + missing-index fail-open), validate LLM-outage → `pulse_unavailable`/`llm_unavailable`, validate unparseable → per-rule `skipped_unavailable`, validate empty inputs → no-op, suggest completed, suggest confidence coercion/clamp, suggest LLM-outage → `pulse_unavailable`, suggest unparseable → `pulse_unavailable`. |
| `backend/ai/tests/test_chat_wiring.py` | Replaced `test_other_tasks_still_not_wired` with `test_all_module_tasks_are_wired` asserting no task in `MODULES` returns `not_wired`; added local `cfg` fixture. |
| `backend/smoke_dq_wiring.py` | **NEW** — in-memory Store + stubbed LLM; calls `dq.validate` and `dq.suggest`, prints `status=completed`. |

## Result contract (verbatim return statements)

`_run_dq_validate` (completed path):

```python
    return {
        "status": "completed",
        "task_id": task_id,
        "result": {"results": results},
    }
```

with each element of `results` being
`{"rule_id": str, "status": "pass"|"fail"|"skipped_unavailable", "details": [{"passed": bool, "explanation": str}, ...]}`,
`details` positionally indexed by row (missing verdict indices → `passed=False`).

`_run_dq_suggest` (completed path):

```python
    return {
        "status": "completed",
        "task_id": task_id,
        "result": {"suggestions": suggestions},
    }
```

with each element of `suggestions` being
`{"prompt": str, "rule_type": "nl_check", "rationale": str, "suggested_severity": "info"|"warn"|"error", "confidence": float}`,
confidence coerced to float and clamped to [0.0, 1.0].

Fail-visible paths (both handlers) return:

```python
    return {
        "status": "pulse_unavailable",
        "task_id": task_id,
        "error": {
            "code": "llm_unavailable",
            "message": message,
        },
    }
```

## Gate results

| Gate | Result |
|------|--------|
| `python -c "import ast; ast.parse(...)"` (engine_runtime.py) | `PARSE OK` |
| `python manage.py check` | `System check identified no issues (0 silenced).` |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `python -m pytest ai/tests dq/tests -q` | **354 passed** (baseline 344 + 10 new `test_dq_wiring.py` tests) |
| `python smoke_dq_wiring.py` | `dq.validate -> completed` / `dq.suggest -> completed` / `SMOKE PASSED` |
| `bash .ai-toolkit/scripts/verify.sh backend` | `GATE PASSED` |

## Deviations / decisions

1. **`verify.sh` location** — the spec said "run `verify.sh backend` from the
   repo root if available". There is no repo-root `verify.sh`; it lives at
   `.ai-toolkit/scripts/verify.sh` and was invoked as
   `bash .ai-toolkit/scripts/verify.sh backend`.
2. **`_llm_text` extended, not bypassed** — to honor `route_chat(task="eval" /
   "cognition", ..., response_format={"type":"json_object"})` while keeping the
   established `_llm_text`-style try/except, the helper gained an optional
   `response_format` kwarg passed through to `route_chat`. Existing callers are
   unaffected (keyword-only, default `None`).
3. **`not_wired` fallthrough removed, not kept defensive** — per spec, the dead
   fallthrough was removed. A missing handler (impossible for `MODULES` entries
   today) now surfaces as `pulse_unavailable`/`engine_error` via a `LookupError`
   inside the existing try/except, keeping the fail-visible contract.
4. **Severity/confidence sanitization in `dq.suggest`** — invalid
   `suggested_severity` values are coerced to `"warn"`; uncoercible/missing
   `confidence` defaults to neutral `0.5` then clamps to [0.0, 1.0]. This is
   field-level sanitization of an otherwise-valid LLM payload, not fabrication.
5. **Conversation history** — the optional `conversation_history` payload key is
   accepted but not injected into the prompt (spec's message guidance lists
   rule/fields/rows/context for validate and table metadata for suggest only).
6. **Validate: first LLM outage aborts the task** — per spec ("LLM
   exception/None → return `pulse_unavailable`/`llm_unavailable`"), the whole
   `dq.validate` dispatch returns `pulse_unavailable` on any rule's LLM failure
   rather than per-rule skipping; the consumer (`dq/engine.py::_evaluate_nl_check`)
   maps a non-completed response to `SKIPPED_UNAVAILABLE`.

## Notes

- No new models, no migrations, no new database state. LLM-call budget logging
  continues via `route_chat` → Store (`app_identifier="carbon"`).
- `ai/` imports nothing from `dq/`, `accounts/`, `catalog/`, `mdm/`, `emissions/`,
  or `core/` (the DQ consumer is the caller, not a dependency).
- Pre-existing `not_wired` strings in `test_intelligence.py` and
  `test_provider_pulse.py` are mocked return values, not real dispatch
  expectations — left untouched.
