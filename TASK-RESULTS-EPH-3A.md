# TASK-RESULTS-EPH-3A — DQ Profiling Service + Scorecard API

**Date:** 2026-08-26
**Role:** backend-worker
**Status:** IMPLEMENTED (verification gate pending terminal execution — see note below)

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `backend/dq/profiling_service.py` | NEW | `ProfilingService.profile_table(table_id)` + module fn `profile_table()`. Loads up to 10_000 `DataRow`, computes per-`DataField` null_count / distinct_count / min / max / mean (numeric only) / top-10 values, then `update_or_create` `TableProfile` + `FieldProfile` (with dedup to avoid `MultipleObjectsReturned`). |
| `backend/dq/scorecard_service.py` | NEW | `ScorecardService.compute_scorecard(table_id)` + module fn `compute_scorecard()`. Aggregates `DQResult.objects.filter(rule__field_assignments__data_table=table)` by DAMA dimension into the exact spec JSON shape. |
| `backend/dq/tasks.py` | NEW | `profile_table_task(table_id)` task entrypoint. Celery-optional: wraps with `shared_task` when Celery is installed, otherwise degrades to a synchronous call (deterministic jobs run inline — project hard rule). |
| `backend/dq/serializers.py` | EXTEND | Added `TableProfileDetailSerializer` (profile + fields) and `ScorecardSerializer` (scorecard payload). |
| `backend/dq/views.py` | EXTEND | Added `TableProfileView` (GET), `RunProfileView` (POST 202 + task_id), `TableScorecardView` (GET). All thin: validate → service → serialize → respond. |
| `backend/dq/urls.py` | EXTEND | Added `tables/<int:table_id>/profile/`, `tables/<int:table_id>/profile/run/`, `tables/<int:table_id>/scorecard/`. |
| `backend/dq/tests/test_profiling.py` | NEW | 8 tests (below). |

No model changes → no migrations generated (confirmed by `makemigrations --check --dry-run` being expected to report "No changes detected").

---

## Tests (8)

`TestProfiling`:
1. `test_profile_creates_table_profile_with_row_count` — `TableProfile.row_count == 3`
2. `test_profile_field_null_count` — `FieldProfile.null_count == 1` (string field)
3. `test_profile_distinct_count_string` — `FieldProfile.distinct_count == 2`
4. `test_profile_min_max_mean_numeric` — `min_value == "25.0"`, `max_value == "30.0"`, `mean_value == 27.5`

`TestScorecard`:
5. `test_scorecard_dimension_breakdown` — 4 results across completeness/validity/accuracy/uniqueness → correct per-dimension passed/failed/score, `total_rules == 4`, `quality_score == 0.5`
6. `test_scorecard_no_results_zeros` — all 6 core dimensions zero, `quality_score == 0.0`, `total_rules == 0`, `last_run_at is None`

`TestProfileEndpoints`:
7. `test_profile_404_when_missing` — `GET /carbon-api/dq/tables/{id}/profile/` → 404 when no profile
8. `test_run_returns_202` — `POST /carbon-api/dq/tables/{id}/profile/run/` → 202 + `task_id`, and a `TableProfile` is persisted

**Expected pass/fail: 8 passed, 0 failed.**

---

## Verification Gate

### Status
⚠️ **Could not be executed in this session.** No terminal-execution tool is available in the current agent session (only read-only terminal inspection tools were provided). The commands below are the exact gate, ready to run.

### Commands
```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest dq/tests/test_profiling.py -v
```

### Static-analysis expectations (pre-run)
- `manage.py check` → `System check identified no issues (0 silenced).` (no model/settings changes; `get_errors` on all 7 touched files reports "No errors found").
- `makemigrations --check --dry-run` → `No changes detected` (no model edits).
- `pytest dq/tests/test_profiling.py -v` → 8 passed. If the stale test-DB surfaces, retry with `--create-db`.

---

## Deviations / Notes

1. **No Celery in this project.** The spec says "`profile_table_task` Celery task", but the codebase has no Celery (not in `requirements.txt`, no `config/celery.py`) and `dq/jobs.py` has a hard rule "no Celery/Redis/daemon/scheduler" for deterministic jobs. `tasks.py` provides a Celery-compatible entrypoint (`shared_task` when installed) that degrades to a synchronous call; the `RunProfileView` still returns `202 + task_id` (task id = `DQJob.id`, created for a followable lifecycle).
2. **Spec filter typo.** The spec's `rule__table_assignments__data_table` does not exist; the correct reverse relation is `rule__field_assignments__data_table` (used throughout the existing codebase and in `scorecard_service.py`).
3. **Dimensions.** The spec enumerates the six core DAMA dimensions (completeness, validity, accuracy, uniqueness, consistency, timeliness). The scorecard seeds those six with zeros and dynamically adds any other dimension present in results (e.g. `integrity`, `reasonability`) so nothing is silently dropped.
4. **Fail-visible scoring.** `DQResult` rows with `passed=None` (`skipped_unavailable`) are excluded from pass/fail counts, matching the existing `_compute_quality` convention.
5. **Top values.** Spec asks for top-10; the legacy `services.profile_table` used top-5. The new `profiling_service.py` uses top-10 per spec. The pre-existing `services.py` was left untouched to avoid breaking the existing 741 tests (the new endpoints use the new service).
