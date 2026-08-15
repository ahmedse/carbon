# TASK-CBAC-A4 — Swagger doc test cleanup (pre-existing failures)

> **Status**: ⏸️ OPEN
> **Type**: Test hygiene / legacy removal
> **Depends on**: TASK-CBAC-TRUST-CORE-SWAP (committed `cc196da`) — failures pre-date the swap
> **Owner**: Backend dev
> **Opened**: 2026-08-11 (QA verification, deviation #8)

## Problem Statement

2 pre-existing test failures, both in `backend/mdm/tests/test_swagger_docs.py`,
reference the **removed** legacy endpoint `/dq/rules/{id}/execute/`:

```
FAILED mdm/tests/test_swagger_docs.py::SwaggerDocumentationTests::test_swagger_schema_contains_documented_operations
SUBFAILED(path="'/dq/rules/{id}/execute/'", method="'post'") mdm/tests/test_swagger_docs.py::SwaggerDocumentationTests::test_key_operations_have_descriptions
```

Root cause: the synchronous rule-execute endpoint was removed in the Phase 5
jobs/pulse refactor (rule execution now creates an async `DQJob` via the run endpoint).
The swagger tests were not updated.

## Affected Assertions (exact lines)

```python
# backend/mdm/tests/test_swagger_docs.py
35:  self.assertIn('/dq/rules/{id}/execute/', paths)
36:  self.assertIn('/dq/rules/{id}/history/', paths)
72:  ('/dq/rules/{id}/execute/', 'post'),
```

## Work Items

- [ ] Confirm the current (jobs-era) run endpoint path & method:
      e.g. `/dq/rules/{id}/run/` POST (verify against `backend/dq/urls.py` / views)
- [ ] Update line 35: assert the new run path is present instead of `/execute/`
- [ ] Update line 36: verify `/dq/rules/{id}/history/` still exists — keep or replace
      based on current URLs
- [ ] Update line 72: swap `('/dq/rules/{id}/execute/', 'post')` for the correct
      (path, method) tuple that exists in the schema
- [ ] Run `pytest backend/mdm/tests/test_swagger_docs.py -q` — must be green
- [ ] Full suite: `python -m pytest -q --reuse-db` — expect **0 failures** (this closes
      the last 2 known pre-existing failures)

## Constraints

- RULE_11: any behavioral change must ship with regression coverage — here the fix IS
  test maintenance, so the updated assertions are the regression net.
- Do NOT re-add the `/execute/` endpoint; it was deliberately removed (async jobs).
- Verify against the committed + working tree URLs (jobs refactor is uncommitted at
  the time of this card — re-check after DQ jobs commit lands).

## DoD

- [ ] Swagger tests green in isolation
- [ ] Full backend suite green (0 failed)
- [ ] No production code changed unless a genuine schema gap is found (flag if so)
