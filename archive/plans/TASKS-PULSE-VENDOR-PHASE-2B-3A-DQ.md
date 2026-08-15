# Pulse Vendoring — Phase 2b-3a: Wire `dq.validate` + `dq.suggest` In-Process

Status: **FINAL SPEC — for worker dispatch**
Parent: `plans/TASKS-PULSE-VENDOR-PHASE-2B-2-KG-ANALYTICS.md` (2b-2 COMMITTED `e3d9486`)
Commit baseline: `e3d9486` (7 KG/analytics tasks wired, `chat` wired in 2b-1)

## Objective

Wire the final two **DQ task types** — `dq.validate` and `dq.suggest` — in-process
in `backend/ai/engine_runtime.py`, completing the task-type matrix. These two are
distinct from the 7 KG/analytics tasks: they are **LLM-only** (no deterministic
fallback is possible for arbitrary natural-language rules), so they are fail-visible
by construction — an LLM outage returns `pulse_unavailable`, never a fabricated verdict.

`dq.validate` / `dq.suggest` are the *only* remaining `not_wired` task types after
this phase. The SQLAlchemy `knowledge_graph/` cluster migration is **2b-3b** (out of
scope here) — do NOT touch `knowledge_graph/store.py`, `data_profiler.py`, etc.

## The consumer relationship (critical context)

Carbon's DQ runner already consumes these two tasks *today* via
`PulseProvider.validate_dq()` / `suggest_dq()` → `dispatch_task(...)`:

- `backend/dq/engine.py::_evaluate_nl_check` (the `nl_check` rule evaluator) calls
  `PulseProvider().validate_dq(request)`. It treats a non-`completed` response as
  `SKIPPED_UNAVAILABLE` (the honest "I could not evaluate this" verdict — NOT a pass).
  So returning `pulse_unavailable` on LLM outage is the correct fail-visible path;
  the consumer maps it to a skipped DQ result and excludes the rule from score
  denominators.
- The result shape you return is consumed by `PulseProvider.validate_dq()` and
  `suggest_dq()` in `backend/ai/providers/pulse.py`. Return the exact keys below or
  the typed response will silently drop fields.

## Task-type → result contract (exact keys, do NOT change providers/pulse.py)

### `dq.validate`

**Payload keys** (what `PulseProvider.validate_dq` sends):
```json
{
  "rules": [{"id": str, "prompt": str, "fields": [str], "severity": str}],
  "rows": [ {field: value, ...}, ... ],
  "context": {"table_name": str, "row_count_hint": int, ...},
  "conversation_history": {"conversation_id": str, "messages": [...]}   // optional
}
```

**Result keys** (what `validate_dq` reads back — return these EXACTLY):
```json
{
  "results": [
    {
      "rule_id": str,
      "status": "pass" | "fail" | "skipped_unavailable",
      "details": [
        {"passed": bool, "explanation": str},
        ...
      ]
    }
  ]
}
```
- `details` is **positionally indexed by row** (index `i` = `rows[i]`). The provider's
  `_extract_failing_rows` enumerates `details` and returns the indices where
  `passed` is False. `explanation` for the overall rule is taken from `details[0].explanation`.
- `status` = `"pass"` iff all `details[].passed` are True; `"fail"` iff any False;
  `"skipped_unavailable"` iff the LLM returned an unparseable/empty verdict for that
  rule (so the consumer maps it to `SKIPPED_UNAVAILABLE`, not a pass).

### `dq.suggest`

**Payload keys**:
```json
{
  "table": {"name": str, "description": str, "columns": [...], "row_count": int},
  "conversation_history": {...}   // optional
}
```

**Result keys** (read back by `suggest_dq`):
```json
{
  "suggestions": [
    {
      "prompt": str,
      "rule_type": "nl_check",
      "rationale": str,
      "suggested_severity": "info" | "warn" | "error",
      "confidence": float
    }
  ]
}
```
- `rule_type` MUST be `"nl_check"` (these are natural-language business rules; the
  provider defaults to `"nl_check"` anyway, but set it explicitly).
- `suggested_severity` ∈ `info`/`warn`/`error`. `confidence` ∈ [0.0, 1.0].

## Implementation guidance

Add two handlers and register them in `_TASK_HANDLERS`:

```python
_TASK_HANDLERS = {
    "dq.validate": _run_dq_validate,     # NEW
    "dq.suggest": _run_dq_suggest,       # NEW
    "carbon.query.nl": _run_query_nl,
    # ... existing 7 unchanged
}
```

`dispatch_task` already routes any task in `MODULES` to `_TASK_HANDLERS` (with
`try/except` → `pulse_unavailable`/`engine_error`); the `not_wired` fallthrough only
fires for tasks absent from the registry. After adding both handlers, **no task type
should return `not_wired`** — remove the now-dead `not_wired` comment/fallthrough if
it becomes unreachable (verify `MODULES` is fully covered by `_TASK_HANDLERS` ∪ `chat`).

### `_run_dq_validate(instance_id, payload, task_id)`

1. Extract `rules`, `rows`, `context`. Guard empty inputs (no rules or no rows →
   return `completed` with `results=[]` — the consumer treats "no prompt/no rows" as
   a local no-op).
2. For **each rule**, evaluate it against **all rows in one LLM call** (not per-row,
   to bound cost). Build a message instructing the model to act as a data-quality
   rule evaluator: rule `prompt`, field names `fields`, the row payloads, and the
   `context` (table name, row count). Require a JSON response:
   `{"results": [{"index": int, "passed": bool, "explanation": str}, ...]}` — one
   entry per row, `index` matching row position.
3. Call the engine LLM via `route_chat(task="eval", ...)` with
   `response_format={"type": "json_object"}` (the `eval` model is configured for
   evaluation). Use the existing `_llm_text`-style try/except: **an LLM exception
   (no API key, provider error) returns `None` and you must NOT fabricate** — return
   `pulse_unavailable` with `error.code="llm_unavailable"`.
4. Parse the JSON verdict. If parsing fails or the LLM returns `None`/empty content,
   set that rule's `status="skipped_unavailable"` with `details=[]` (fail-visible,
   not fabricated). Do NOT raise for a parse failure — degrade to skipped.
5. Map the parsed per-row verdicts into `details` (list of `{passed, explanation}`,
   ordered by `index`, length == len(rows); missing indices → `passed=False`). Derive
   `status` from `details`. Return `{"results": [...]}`.

Do **NOT** import anything from `dq/` — this handler uses the engine LLM only.
`dq/engine.py` is the *caller*, not a dependency.

### `_run_dq_suggest(instance_id, payload, task_id)`

1. Extract `table` (`name`, `description`, `columns`, `row_count`).
2. Build a message instructing the model to propose natural-language DQ business
   rules for the table (completeness, cross-field consistency, temporal plausibility,
   range/outlier plausibility) from the column metadata. Require JSON:
   `{"suggestions": [{"prompt": str, "rule_type": "nl_check", "rationale": str, "suggested_severity": "info|warn|error", "confidence": float}, ...]}`.
3. Call `route_chat(task="cognition", ...)` with `response_format={"type":"json_object"}`.
4. On LLM exception / `None` / unparseable JSON → return `pulse_unavailable`
   (`error.code="llm_unavailable"`). **No deterministic fallback** — fabricating rules
   is worse than saying "cannot suggest". On success, return `{"suggestions": [...]}`
   with each `confidence` coerced to `float` and clamped to [0.0, 1.0].

### Fail-visible rules (unchanged)

- Any *unexpected* exception inside a handler propagates to `dispatch_task`'s
  `except` → `pulse_unavailable`/`engine_error` (already wired).
- LLM outage → `pulse_unavailable` (never a fake pass or a fake suggestion).
- Unparseable LLM verdict → per-rule `skipped_unavailable` (validate) or
  `pulse_unavailable` (suggest).

## Non-negotiables (unchanged from 2b)

- **Fail-visible, never fabricate.**
- **No new database.** No new durable state (these tasks are stateless LLM calls;
  the existing `LLMCallLog`/budget logging inside `route_chat` already persists via
  the Store). Do NOT add models or migrations.
- **CBAC on every read/write** — `route_chat`'s internal budget/log writes already
  go through the Store (`app_identifier="carbon"`).
- **No HTTP transport** — in-process only.
- **`ai` imports nothing from `accounts`/`catalog`/`mdm`/`dq`/`emissions`/`core`.**
- **TZ-aware datetimes** — no `datetime.now()`/`utcnow()`.

## Acceptance gates (worker runs, master re-runs)

- `cd backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check` — 0 issues.
- `cd backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run` — no drift.
- `cd backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests dq/tests -q` — all green (baseline **344 passed**; add `ai/tests/test_dq_wiring.py`):
  - `dq.validate` completed path (stub `get_llm_client` → JSON verdict) returns
    `status="completed"` with correct `results` shape (pass + fail + details).
  - `dq.validate` LLM-outage path → `pulse_unavailable`/`llm_unavailable`.
  - `dq.validate` unparseable-verdict path → per-rule `skipped_unavailable`.
  - `dq.suggest` completed path (stub LLM → JSON) returns `status="completed"` with
    `suggestions` shape (prompt/rule_type/rationale/suggested_severity/confidence).
  - `dq.suggest` LLM-outage path → `pulse_unavailable`/`llm_unavailable`.
  - `not_wired` is fully gone: assert no task in `MODULES` returns `not_wired`
    (update `test_chat_wiring.py::test_other_tasks_still_not_wired` — rename/repurpose
    it to assert all tasks are wired, or delete it).
- `cd backend && /home/ahmed/aast/carbon/.venv/bin/python -c "import ast, pathlib; m=ast.parse(pathlib.Path('ai/engine_runtime.py').read_text())"` — file parses (sanity).
- `verify.sh backend` — GATE PASSED.
- Smoke: extend or add `smoke_dq_wiring.py` (in-memory Store + stubbed LLM) that
  calls `dq.validate` and `dq.suggest` and prints `status=completed`.

## Result doc

Write `plans/TASK-RESULTS-PULSE-VENDOR-PHASE-2B-3A-DQ.md` listing files changed,
gate results, and any deviations.

## Rollback / safety

- `git checkout e3d9486 -- backend/ai/` restores the 2b-2 baseline.
- Never `git add -A`. Stage only `backend/ai/engine_runtime.py` + `backend/ai/tests/*`
  + the smoke file + this results doc.
