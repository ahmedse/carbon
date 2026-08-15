# TASK-DQ-CORE-P3-JOBS

**Status:** NOT STARTED
**Phase:** 3 of 5 — DQ Core next-gen plan (`plans/CARBON_DQ_CORE_PLAN.md` §3-Phase-3)
**Depends on:** TASK-DQ-CORE-P1-RULE-CORE (P2 recommended, not required)
**Executing agent:** read this file cold; everything needed is below.

## Goal

Everything beyond the write-time gate becomes an explicit, user-started **Job** with a followable lifecycle. No hidden automation, no schedulers, no Celery. The user opens a job and watches it reach a terminal state.

## Design decisions (do NOT debate)

1. **No Celery/Redis/daemon.** Deterministic jobs (`rule_run`, `profile`, `freshness`, `schema`) execute **inline** during `POST /dq/jobs/` (data volumes are small; if a deployment outgrows this, the escape hatch is a `run_dq_jobs` management command — add a `queued` path but do NOT build the worker now).
2. **Pulse jobs are polled.** `nl_check`, `suggest` submit to Pulse via `pulse_gateway.py`; `GET /dq/jobs/{id}/` re-checks Pulse task status and advances the job until terminal.
3. **Nothing AI runs synchronously in a request.** `nl_check` moves from inline-in-`run_dq` to job-only.
4. Every completed job still writes normal `DQResult` rows — history, trends, and catalog rollups keep working unchanged.

## Deliverables

### 1. `DQJob` model — `backend/dq/models.py`

Fields: `job_type` (`rule_run | profile | freshness | schema | nl_check | suggest`), `status` (`queued | running | done | failed | canceled`), `rule` FK nullable, `data_table` FK nullable, `payload` JSON (inputs), `result` JSON (summary), `pulse_task_id` CharField blank, `progress` 0–100, `error` TextField blank, `created_by` FK, `created_at/updated_at`. Indexes on `(status, job_type)` and `created_at`.

### 2. Runner — `backend/dq/jobs.py` (new)

- `create_job(job_type, *, rule=None, table=None, payload, user) -> DQJob`
- `execute(job)` dispatch table:
  - `rule_run` → `services.run_single_rule()` (or `run_dq` filtered); result summary = counts.
  - `profile` → existing `profile_table()`; `freshness`/`schema` → the same callables the management commands use (extract shared functions if the logic is trapped in command classes).
  - `nl_check`/`suggest` → submit via `pulse_gateway`, store `pulse_task_id`, status `running`; **polling** happens in `refresh(job)` called from `GET /dq/jobs/{id}/`.
- All exceptions → `status=failed`, `error=str(e)`. Never raise out of the runner.

### 3. Pulse task status — `backend/pulse_gateway.py`

- Add `get_task_status(task_id) -> dict` → `GET {PULSE_URL}/tasks/{task_id}` with the same auth envelope pattern as existing methods; on unreachable/timeout return `{"status": "pulse_unavailable"}` (job stays `running`, retried on next poll; after N=20 consecutive unavailable polls → `failed`).
- **Flag to Pulse team (docs only, do not implement Pulse-side):** `docs/PULSE_CONTRACT_SPEC.md` — add `GET /tasks/{id}` to the contract as required for async tasks, response `{status: pending|running|done|failed, result?, error?}`.

### 4. Endpoints — `dq/views.py`, `dq/urls.py`

- `POST /carbon-api/dq/jobs/` `{job_type, rule_id?, data_table_id?, payload?}` → creates + executes (deterministic) or submits (Pulse); returns the job.
- `GET /carbon-api/dq/jobs/` — filters `status`, `job_type`, `rule`, `table`; ordering `-created_at`.
- `GET /carbon-api/dq/jobs/{id}/` — calls `refresh()` first for Pulse jobs; returns job with `result`.
- `POST /carbon-api/dq/jobs/{id}/cancel/` — `queued/running` → `canceled` (Pulse-side cancel: best effort, note in contract doc).
- `POST /carbon-api/dq/rules/{id}/run/` — sugar: creates a `rule_run` (or `nl_check`, per rule type) job, returns it. The old synchronous `execute` action stays for backward compat until Phase 5 switches the UI, then remove it in Phase 5.

### 5. `nl_check` job-only

- `services.run_dq()`: skip `nl_check` rules with a logged note ("run as job"); they execute only via the `nl_check` job type. Keep behavior identical otherwise.

## Explicit exclusions

- No frontend (Phase 5). No suggestion persistence (Phase 4 — `suggest` job here may return suggestions inline in `result` without storing them). No anomaly type (Phase 4). No scheduler/cron.

## Gates

1. Backend green: `cd backend && python -m pytest -q` (or `./manage.sh test` from repo root). Note: there is **no `verify.sh`** in this repo — `manage.sh test` wraps pytest.
2. `python -m pytest dq/ -q` — green; new tests ≥ 10: lifecycle transitions for a deterministic job; Pulse job with mocked gateway (pending→done, timeout→failed after N polls, unavailable streak→failed); cancel; `rules/{id}/run/` creates the right job type per rule type; `nl_check` absent from `run_dq` results.
3. One migration (`DQJob`).
4. API smoke: create `rule_run` job → 201, status `done`, `result` non-empty; `GET /dq/jobs/?status=done` lists it.

## Done criteria

"Run this rule" anywhere in the API creates a job pollable to a terminal state; Pulse work never blocks a request; results/history/rollups unaffected.
