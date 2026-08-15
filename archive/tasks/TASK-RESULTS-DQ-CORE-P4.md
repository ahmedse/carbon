# TASK-RESULTS-DQ-CORE-P4 — Pulse Suggestion + Anomaly + Fail-Visible

**Task spec**: `TASK-DQ-CORE-P4-PULSE.md`
**Branch**: `main` (working tree, uncommitted) · **Date**: 2026-08-11
**Design decision #1 (shipped): fail-visible, not fail-open** — Pulse unreachable now
yields honest `skipped_unavailable` results and `failed` jobs, reversing the previous
silent auto-pass behavior.

---

## 1. Deliverables

### D1 — `DQSuggestion` model (suggestion inbox)
- `DQSuggestion`: `data_table` FK, `payload` JSON (v1 rule definition), `rationale`,
  `confidence` (nullable), `status` (`pending|accepted|rejected`), `reject_reason`,
  `job` FK → `DQJob` (nullable, `SET_NULL`), `created_by`, `created_at/updated_at`.
- Migration `dq.0014` (CreateModel + DQAnomaly + DQResult.status + job_type/rule_type
  choice extensions); model + API verified by 22 new tests in
  `backend/dq/tests/test_phase4_pulse.py`.

### D2 — Suggest flow (thin alias + accept/reject + quarantine)
- `POST /dq/suggest/` is now a **thin alias** over the `suggest` job:
  validates `data_table_id` (400/404), checks table access, creates + executes a
  `DQJob(job_type='suggest')`, returns **201 + job object + `X-Deprecated: true`**.
- `dq/jobs.py` `_persist_suggestions`: each Pulse suggestion validated with
  `rule_schema.validate_definition`; **valid → `DQSuggestion(status='pending')`**,
  **invalid → quarantined to `job.result.invalid`** (counters
  `suggestions_stored`/`suggestions_invalid`); nothing is ever fabricated.
- `DQSuggestionViewSet`: `GET /dq/suggestions/` (filter by `status`, `data_table`,
  org-scoped), `POST .../accept/` (re-validates payload → auto-reject 400 if invalid;
  creates `DQRule` + `RuleFieldAssignment` via direct ORM; marks `accepted`),
  `POST .../reject/` (with optional `reason`).

### D3 — `DQAnomaly` + anomaly job
- `DQAnomaly`: `metric`, `group_key` (JSON), `expected_range` (JSON), `observed`
  (Float), `score`, `explanation`, `severity` (`info|warn|error`), `detected_at`,
  `data_table` FK, `job` FK.
- `job_type='anomaly'` → `jobs._submit_anomaly_job` → `services.build_anomaly_payload`:
  TableProfile history + per-field FieldProfile history + active `anomaly_detect`
  rules. **`DQProfileConfig.volume_anomaly_pct` is now actually read** (was inert) and
  feeds both `payload['sensitivity']` and `payload['volume_anomaly_pct']`.
- **`< 6` profile snapshots → job `done` with `result.state='insufficient_history'`**
  (Pulse never called — Carbon-side guard, fail-visible).
- Pulse returns → `_write_anomaly_results` stores `DQAnomaly` rows (entries missing
  `observed` are **dropped, never fabricated**) and emits
  `notify_event(event_type='dq_anomaly', ...)` per stored anomaly.
- `DQAnomalyViewSet`: `GET /dq/anomalies/` filtered by `severity`, `data_table`,
  `date` / `from` / `to`, org-scoped.
- `pulse_gateway.detect_anomalies(payload)` submits envelope
  `{task: {type: 'anomaly.detect', payload: {profile: payload}}}` (async, 120s).

### D4 — Fail-visible results (behavior reversal)
- `DQResult.passed` → nullable (default `None`); new `status`
  (`passed|failed|skipped_unavailable`); **data migration `dq.0015`** backfills
  existing rows (`passed=True→'passed'`, `False→'failed'`, `null→'skipped_unavailable'`).
- Pulse unavailable → `DQResult(status='skipped_unavailable', passed=None, score=0,
  checked_count=0)`; `run_dq`/`run_single_rule` map `passed=None` → `skipped_unavailable`.
- `_compute_quality`: skipped rules **excluded from the score denominator**;
  all-skipped → `('unknown', None)`.
- `GET /dq/metrics/` gains `skipped_rules` + `scored_rules`; `overall_score =
  passing / (passing + failing)`; all-skipped → `0.0` with honest counts.
- `engine.evaluate`: `anomaly_detect` rules → `SKIPPED_UNAVAILABLE` sentinel
  (never a fabricated verdict); `run_dq` skips `nl_check` + `anomaly_detect`
  (job-only).
- Suggest/anomaly job failures → job `failed` with honest `error`, **never** a
  fabricated result payload.
- Signal fix (`dq/signals.py`): guard `if instance.passed:` → `if instance.passed is
  not False:` so `passed=None` (skipped) no longer fires a spurious `dq_violation`
  alert — only real failures do.

### D5 — `docs/PULSE_CONTRACT_SPEC.md` §3.5
- `anomaly.detect` marked **"consumed by Carbon (Phase 4) — Pulse-side implementation
  pending"** with the exact payload (`table`, `sensitivity`/`volume_anomaly_pct` from
  `DQProfileConfig`, `history` TableProfile snapshots, per-field `fields` history,
  `rules`) and response spec (`anomalies[]` with `metric/group_key/expected_range/
  observed/score/severity/explanation`; `severity` coerced to `info|warn|error`).
- Noted future `dq.suggest.feedback` task type for accept/reject feedback.

---

## 2. Gates

| Gate | Requirement | Result |
|------|-------------|--------|
| 1 | Full backend suite green | ✅ **1012 passed + 11 subtests** (baseline 990 + 11) |
| 2 | `dq/` suite green, ≥12 new tests | ✅ **249 passed** (baseline 227; **+22 new** — all in `test_phase4_pulse.py`; 5 legacy suggest tests rewritten to thin-alias; 6 nl_check degradation tests updated to fail-visible) |
| 3 | Migrations: exactly `DQSuggestion`, `DQAnomaly`, `DQResult.status` | ✅ `dq.0014` + `dq.0015`; applied cleanly to dev DB; `makemigrations --check --dry-run` → **No changes detected** |
| 4 | API smoke (live :8009, admin JWT) | ✅ see §3 |

---

## 3. Live API smoke (:8009, JWT `ahmed`/`AdminPa_132`)

| Scenario | Observed |
|----------|----------|
| `POST /dq/suggest/` (Pulse down) | **201** + `X-Deprecated: true`; job `status: failed`, honest error (`404 Client Error ... :9100/.../tasks`); **zero** fabricated suggestions |
| `GET /dq/suggestions/?status=pending&data_table=1` | Seeded pending suggestion returned with payload/rationale/confidence |
| `POST /dq/suggestions/1/accept/` | **Rule 104 created** (`nl_check`, `rule_level=field_validation` — level mapping verified); suggestion → `status: accepted` |
| `POST /dq/jobs/` `{job_type: 'anomaly'}` | Job `done` with `result.state='insufficient_history'` (3 snapshots < 6; Pulse never called); `DQAnomaly` count 0 — nothing fabricated |
| `POST /dq/jobs/` `{job_type: 'nl_check'}` (Pulse down) | Job `status: failed` + honest error; **`DQResult(status='skipped_unavailable', passed=None, score=0, checked_count=0)`** persisted |

Smoke left realistic artifacts in dev DB (suggestion #1 accepted → rule #104, jobs 8/9).

---

## 4. Files changed (P4 scope)

**Backend** (modified): `dq/models.py`, `dq/views.py`, `dq/urls.py`, `dq/serializers.py`,
`dq/services.py`, `dq/engine.py`, `dq/signals.py`, `dq/rule_schema.py`,
`dq/management/commands/{check_freshness,schema_snapshot}.py`, `pulse_gateway.py`
**Backend** (new/untracked): `dq/jobs.py`, `dq/migrations/0013_dqjob.py` (P3),
`dq/migrations/0014_*.py`, `dq/migrations/0015_map_existing_dqresult_status.py`,
`dq/tests/test_phase3_jobs.py` (P3), `dq/tests/test_phase4_pulse.py` (22 tests)
**Tests updated**: `dq/tests/test_nl_check.py` (6 → fail-visible),
`dq/tests/test_phase3_suggest.py` (5 → thin-alias semantics)
**Docs**: `docs/PULSE_CONTRACT_SPEC.md` (§3.5 + `dq.suggest.feedback` note),
`.ai-toolkit/troubleshooting/playbook.md` (**PB-22** appended after PB-21)

---

## 5. Constraints respected

- No frontend changes; no scheduler; no Pulse-side implementation.
- No new dependencies. `gate.py` untouched.
- Pre-existing rule-assignments POST IntegrityError out of scope — accept flow uses
  direct ORM `RuleFieldAssignment.objects.create`.
- Tests run with `--create-db` (pytest.ini `--reuse-db --nomigrations` requires a
  fresh test DB after schema changes).

## 6. Notes / follow-ups

- `dq/jobs.py` + `test_phase3_jobs.py` + `0013_dqjob.py` were already untracked
  (P3 work in progress) — included here as part of the suite.
- When Pulse implements `anomaly.detect`, remove the `insufficient_history`
  local-only completion only after ≥6 snapshots accumulate, or lower
  `MIN_ANOMALY_PROFILES` deliberately.
