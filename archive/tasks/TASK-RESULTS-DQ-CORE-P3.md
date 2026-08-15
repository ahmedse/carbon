# TASK-RESULTS-DQ-CORE-P3 — DQ Jobs (Phase 3 of DQ Core)

**Date:** 2026-08-11 · **Status:** ✅ Complete — all 5 deliverables, all 4 gates green
**Spec:** `TASK-DQ-CORE-P3-JOBS.md` · **Playbook:** PB-21 (new entry)

---

## Deliverable 1 — `DQJob` model (`backend/dq/models.py`)

- `DQJob` appended to `dq/models.py` with exactly the specified fields:
  - `job_type` CharField(20) — choices `rule_run | profile | freshness | schema | nl_check | suggest` (module-level `JOB_TYPES`, not class attrs)
  - `status` CharField(10) default `queued` — `queued | running | done | failed | canceled` (module-level `JOB_STATUSES`)
  - `rule` FK → `DQRule` (null, SET_NULL, related_name `jobs`)
  - `data_table` FK → `DataTable` (null, SET_NULL, related_name `dq_jobs`)
  - `payload` / `result` JSONField(default=dict)
  - `pulse_task_id` CharField(64, blank), `progress` PositiveSmallIntegerField(0), `error` TextField(blank)
  - `created_by` FK → User (null, SET_NULL), `created_at` auto_now_add, `updated_at` auto_now
  - Meta: ordering `['-created_at']`, indexes on `(status, job_type)` and `created_at`
- **Migration:** `dq/migrations/0013_dqjob.py` — created and applied (`Applying dq.0013_dqjob... OK`).
- **Single-migration check:** `manage.py makemigrations --check --dry-run` → `No changes detected` (exactly one migration, no drift).

## Deliverable 2 — Runner `backend/dq/jobs.py` (new)

- `create_job(job_type, *, rule=None, table=None, payload=None, user=None) -> DQJob` — validates `job_type` against `JOB_TYPES` (`ValueError` on unknown; API layer returns 400 before this).
- `execute(job)` — dispatch table, **never raises** (tested: `test_runner_never_raises_on_exception`):
  - `rule_run` → `services.run_single_rule` per field assignment; result summary = counts (`{rule_id, rule_name, fields_checked, passed, failed, results}`); writes normal `DQResult` rows.
  - `profile` → `services.profile_table`; `freshness` → shared `services.check_freshness` (also backs `check_freshness` mgmt command); `schema` → shared `services.snapshot_schema` (also backs `schema_snapshot` mgmt command).
  - `nl_check` / `suggest` → submit via `pulse_gateway`, store `pulse_task_id`, status `running`; polling in `refresh(job)`.
- `refresh(job)` — polls `pulse_gateway.get_task_status`; `pending|working` → stays `running`; `completed` → `done` + progress 100 + result (+ `_write_nl_check_results` writes `DQResult` rows for nl_check); `failed` → `failed` with Pulse error; `pulse_unavailable` → increments `payload['unavailable_streak']`, ≥ `PULSE_UNAVAILABLE_LIMIT` (20) consecutive → `failed`; no `pulse_task_id` → `failed`.
- `cancel(job)` — `queued|running` → `canceled`.
- Shared-code refactors in `dq/services.py` (used by both mgmt commands and jobs, zero duplication):
  - `check_freshness(table_id=None, notify=False)` → `{total, stale, results:[...]}` + `FreshnessCheck` row.
  - `snapshot_schema(table_id=None, notify=False)` → `{total, changes_detected, results:[...]}` + `SchemaSnapshot` (+ `SchemaChange` rows for added/dropped/modified).
  - `_get_or_create_table_profile` / `build_suggest_payload` extracted from `suggest_rules_for_table`.

## Deliverable 3 — Pulse task status (`backend/pulse_gateway.py` + contract doc)

- `get_task_status(task_id) -> dict` — `GET {PULSE_URL}/tasks/{task_id}`, same auth envelope pattern as existing methods; graceful degradation → `{"status": "pulse_unavailable", "error": {code, message}}` (codes: `timeout | unreachable | request_failed | unexpected`).
- `submit_dq_validate(rules, rows, context)` and `submit_suggest(table_profile)` added for nl_check / suggest job submission (shared `_post_task` helper, same degradation).
- **Contract flag:** `docs/PULSE_CONTRACT_SPEC.md` §1.8 "Async Task Status — Required for Carbon DQ Jobs (Phase 3)" — documents `GET /tasks/{id}` response `{status: pending|working|completed|failed, result?, error?}`, polling semantics, N=20 unavailable → failed, and best-effort cancel (suggests `POST /tasks/{id}/cancel` as a future contract addition). Docs only — no Pulse-side implementation.

## Deliverable 4 — Endpoints (`dq/views.py`, `dq/urls.py`)

- `POST /carbon-api/dq/jobs/` — validates `job_type` (400 on unknown), resolves `rule`/`data_table` with org-scoped access checks (404), enforces required inputs per type (`rule_run|nl_check` need `rule_id`; `profile|freshness|schema|suggest` need `data_table_id`), then `create_job` + `execute` → 201 with serialized job.
- `GET /carbon-api/dq/jobs/` — filters `status`, `job_type`, `rule`, `table`; ordering `-created_at`; org-scoped queryset (select_related).
- `GET /carbon-api/dq/jobs/{id}/` — calls `refresh()` first (Pulse polling), returns job with `result`.
- `POST /carbon-api/dq/jobs/{id}/cancel/` — `queued|running` → `canceled`; terminal → 400.
- `POST /carbon-api/dq/rules/{id}/run/` — sugar: creates `rule_run` (or `nl_check` per `rule.rule_type`) job and returns it. Old synchronous `execute` action kept for backward compat (removal is Phase 5).
- Router: `router.register(r'jobs', DQJobViewSet, basename='dqjob')` in `dq/urls.py`.
- Permissions: `[IsAuthenticated, ReadAnyWriteGlobalAdmin]` (existing pattern).

## Deliverable 5 — `nl_check` job-only (`dq/services.py`)

- `run_dq()` now skips `nl_check` rules with a logged note (`"Skipping nl_check rule %s (id=%s) in run_dq — run as a job"`) and `continue` before the assignments loop. Deterministic rules behave identically.
- `nl_check` executes only via the `nl_check` job type; on completion `_write_nl_check_results` writes normal `DQResult` rows so history/trends/rollups keep working.

---

## Gates

| Gate | Check | Result |
|------|-------|--------|
| 1. Backend green | `cd backend && ../.venv/bin/python -m pytest -q` | ✅ **990 passed, 11 subtests passed** (41.9s) |
| 2. dq suite green + ≥10 new tests | `../.venv/bin/python -m pytest dq/ -q` | ✅ **227 passed** (13.6s) — **25 new test methods** in `dq/tests/test_phase3_jobs.py` + `test_nl_check.py::test_nl_check_via_run_dq` rewritten for job-only semantics |
| 3. One migration | `makemigrations --check --dry-run` + `ls dq/migrations` | ✅ `0013_dqjob.py` only; `No changes detected` |
| 4. API smoke (live, backend :8009) | POST rule_run job → 201 done; list filter | ✅ see below |

### Gate 4 — live API smoke evidence (JWT `ahmed` admin)

1. `POST /carbon-api/dq/jobs/` `{job_type: "profile", data_table_id: 2}` → **201**, `status: "done"`, `progress: 100`, `result` with `rows_profiled: 62`, `fields_profiled: 5`, per-field `field_profiles`.
2. `POST /carbon-api/dq/jobs/` `{job_type: "rule_run", rule_id: 103}` → **201**, `status: "done"`, `progress: 100`, `result: {rule_id, rule_name, fields_checked: 1, passed: 1, failed: 0, results: [{result_id: 224, checked_count: 62, score: 100, ...}]}` (DQResult history written).
3. `GET /carbon-api/dq/jobs/?status=done&job_type=rule_run` → lists the job.
4. `POST /carbon-api/dq/rules/103/run/` → **201**, `job_type: "rule_run"`, `status: "done"`, `progress: 100` (sugar endpoint works).
5. `POST /carbon-api/dq/jobs/5/cancel/` (done job) → **400** "only queued/running jobs can be canceled" (guard verified live).

### Defect found & fixed by the live smoke (PB-21)

- **Symptom:** profile job failed with `get() returned more than one TableProfile -- it returned 3!` — legacy duplicate `TableProfile` rows for one table broke Django's `update_or_create` (its internal `get()` raises `MultipleObjectsReturned`).
- **Fix:** `profile_table()` now deletes stale duplicate rows (`order_by('-profiled_at')[1:]`) before `update_or_create`.
- **Regression guard:** `test_profile_job_survives_duplicate_table_profiles` (new; dq suite 227 ✅). Live re-run of the same POST now returns `done`.

---

## Test inventory (25 new methods — `dq/tests/test_phase3_jobs.py`)

| Class | Tests |
|-------|-------|
| `DeterministicJobTests` (8) | rule_run lifecycle + counts + DQResult rows; rule_run without rule → failed; profile done; **dup TableProfiles don't break profile job**; freshness creates `FreshnessCheck`; schema creates `SchemaSnapshot`; unknown job_type rejected at creation; runner never raises on exception |
| `PulseJobTests` (6) | nl_check submit→poll→done (mocked `requests.post`/`get`); pending stays running; Pulse failed → job failed; **unavailable streak → failed after N=20**; suggest job submits; deterministic job refresh is a no-op |
| `CancelJobTests` (3) | cancel queued; cancel running via API; cancel done → 400 |
| `JobsApiTests` (6) | create rule_run via API → 201 done + list filter; invalid job_type → 400; rule_run without rule → 400; unauthenticated → 401; `rules/{id}/run/` → rule_run; `rules/{id}/run/` → nl_check for nl_check rules |
| `NLCheckJobOnlyTests` (2) | `run_dq` skips nl_check (rules_run 0); `run_dq` still evaluates deterministic rules |

## Deviations / notes

- **Synchronous Pulse completion:** a submitted Pulse job may come back `completed` on the very first poll (or the POST response) — `_record_pulse_submission` and `refresh()` handle both sync-complete and async-pending uniformly (tested via `test_nl_check_job_submit_then_poll_to_done`).
- **`create_job` validates job_type** (raises `ValueError`); the API rejects unknown types with 400 before the runner is reached. The runner's never-raise guarantee applies to `execute()` (tested).
- No frontend changes (Phase 5), no suggestion persistence (Phase 4), no anomaly type, no scheduler — per explicit exclusions.
- The `rule-assignments` POST endpoint has a **pre-existing** `IntegrityError` on create (unrelated to jobs; reproduced with both field and table-level payloads). Phase 3 smoke created the assignment via ORM to exercise the job path; flagged here for a future fix, out of scope for this task.

---

## Revalidation — 2026-08-12

Current backend state revalidated cleanly without further code changes.

### Dedicated P3 suite

Command:
```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest dq/tests/test_phase3_jobs.py -q
```

Output:
```text
.........................                                                [100%]
25 passed in 3.76s
```

### Full DQ backend suite

Command:
```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest dq/tests -q
```

Output:
```text
........................................................................ [ 87%]
...............................                                          [100%]
247 passed in 12.19s
```

### Backend baseline

Command:
```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
```

Output:
```text
System check identified no issues (0 silenced).
```

### Migration drift check

Command:
```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
```

Output:
```text
No changes detected
```
