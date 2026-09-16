# Sprint 26 — R3: NL query execution on JSONB dataschema data (F-05)

**Owner:** Master Architect · **Worker Role:** backend-worker · **Model:** DeepSeek V4-Flash
**Status:** 🚀 READY for dispatch (investigation-led — see "Current state" before coding)
**Source:** `docs/TASK-RESULT-QA-AI-PULSE-SIMULATION.md` finding F-05
**Priority:** P1 — `query.nl` is broken against seeded data.

## Goal
Make `query.nl` (natural-language query) execute against the platform's actual data source
instead of failing with `relation 'emissions' does not exist`.

## Current state (verified facts — investigate the data layer before coding)
- `query.nl` routes through `backend/ai/engine/knowledge_graph/engine.py` (`ExecutionEngine`)
  which builds SQL against **physical tables/views** (e.g. `SELECT ... FROM emissions`).
- The real data lives in **`dataschema_datarow`** as JSONB (logical schema → rows), NOT in
  physical per-table relations. There is currently no logical→physical mapping, so the SQL
  engine targets tables that don't exist.
- `backend/ai/engine/knowledge_graph/data_profiler.py` already profiles the host DB via
  read-only psycopg2; `schema_analyzer.py` / `migration.py` build KG nodes from table metadata.

## Files to Change
- `backend/ai/engine/knowledge_graph/engine.py` — MODIFY: add a dataschema-backed execution
  path (or a logical→physical resolver) so `query.nl` reads from `dataschema_datarow`.
- `backend/ai/engine_runtime.py` — MODIFY only if the `T_NL_QUERY` handler needs to pass a
  dataschema-scoped flag.
- `backend/ai/tests/test_nl_query_dataschema.py` — ADD.

## Tasks
1. **Investigate first** (read before editing): `engine.py` `ExecutionEngine`, `engine_runtime.py`
   `T_NL_QUERY` handler (~line 855 area), and the `dataschema` app's model for `datarow`
   (JSONB shape). Determine the minimal way to serve `nl_query` over `dataschema_datarow`:
   - Option A (preferred if simple): add a **read-only dataschema data source** — when the
     resolved entity is a dataschema-backed "table", execute the filter/aggregate over the
     JSONB rows in Python (or via SQL `jsonb` operators) instead of `FROM <physical_table>`.
   - Option B: build/materialize a logical→physical view mapping. Only if A is not feasible.
2. Preserve the read-only guarantee (no writes on `query.nl`).
3. Map the "first N rows" and simple filter/aggregate cases; a clean, honest "table not found"
   fallback must remain for genuinely unknown tables (don't fabricate data).

## DO NOT TOUCH
- Frontend files.
- `query.nl` classification/routing in `turn_classifier.py` (keep the route, fix the execution).
- DQ/other task handlers.

## Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_nl_query_dataschema.py -q
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q
```
Acceptance repro: "show me the first 5 rows of the emissions table" returns actual rows from
`dataschema_datarow`, not `relation 'emissions' does not exist`.

## Hard rules
- `python -m pytest`, never `manage.py test`. Venv `/home/ahmed/aast/carbon/.venv`.
- Read-only execution for `query.nl` (RULE_21: AI suggests, Carbon executes — but reads may run).

## Output contract
Append an `R3` section to `TASK-RESULTS.md`.

## Notes for the Master
- This is the most under-specified of the P1s. If the dataschema JSONB shape makes a general
  solution large, implement the **first-N-rows + basic filter** slice and report what a full
  mapping would take. Flag any architectural decision in Deviations.
