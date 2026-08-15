# TASK-DQ-CORE-P4-PULSE

**Status:** NOT STARTED
**Phase:** 4 of 5 — DQ Core next-gen plan (`plans/CARBON_DQ_CORE_PLAN.md` §3-Phase-4)
**Depends on:** TASK-DQ-CORE-P3-JOBS
**Executing agent:** read this file cold; everything needed is below.

## Goal

All AI capability lands as Pulse plugins behind the existing task contract: persisted rule suggestions with accept/reject, statistical anomaly detection, and **fail-visible** behavior (a down Pulse is shown as "unknown", never a silent pass). Carbon stays deterministic; Pulse-side work is flagged via contract updates only.

## Design decisions (do NOT debate)

1. **Fail-visible, not fail-open.** When Pulse is unreachable, `nl_check`/`suggest`/`anomaly` produce status `pulse_unavailable` — results say "skipped/unknown" and scores reflect the gap. This intentionally reverses today's silent auto-pass. Call it out in the commit message.
2. **Anomaly detection is statistical-first.** The `anomaly.detect` payload asks Pulse for z-score/IQR/seasonal-baseline detection over profile metrics and grouped aggregates; the LLM's job is only the human-readable `explanation`. Do NOT build LLM-row-judging for anomalies.
3. **Suggestions are data.** Persisted, reviewed, accepted into real rules. Nothing auto-creates rules.
4. Carbon-side only. Pulse-side plugin implementation is out of repo — contract doc updates flag it.

## Deliverables

### 1. `DQSuggestion` model — `backend/dq/models.py`

Fields: `data_table` FK, `payload` JSON (a complete v1 rule definition from `rule_schema`), `rationale` TextField, `confidence` FloatField nullable, `status` (`pending | accepted | rejected`), `reject_reason` TextField blank, `job` FK→DQJob nullable, `created_by`, timestamps.

### 2. Suggest flow

- `suggest` job (from P3) → on Pulse `done`, validate each suggested definition with `rule_schema.validate_definition`; valid ones become `DQSuggestion(status=pending)`; invalid ones logged into job `result.invalid`.
- `POST /carbon-api/dq/suggestions/{id}/accept/` → creates the `DQRule` (via the v1 definition; bindings resolve table/field slugs → `RuleFieldAssignment`), marks suggestion `accepted`, returns the rule. `POST .../reject/` `{reason?}` → `rejected`.
- `GET /carbon-api/dq/suggestions/` — filter by `status`, `data_table`.
- Keep `POST /dq/suggest/` (legacy inline endpoint) as a thin alias creating a `suggest` job; deprecate in its response header/docstring.

### 3. `DQAnomaly` model + anomaly job

- Fields: `data_table` FK, `metric` (e.g. `row_count`, `null_pct:<field>`, `sum(kwh)`), `group_key` JSON nullable (e.g. `{"building": "alamein"}`), `expected_range` JSON `{low, high}`, `observed` FloatField, `score` FloatField (deviation magnitude), `explanation` TextField (Pulse-written), `severity`, `job` FK, `detected_at`.
- Gateway: add `detect_anomalies(payload)` → task type `anomaly.detect` per contract §(already defined, async 120s).
- `anomaly` job type: builds payload from `TableProfile`/`FieldProfile` history + `DQProfileConfig.volume_anomaly_pct` (**wire this field now** — it is currently inert) + rule definitions of `type: anomaly_detect` bound to the table; stores returned anomalies as `DQAnomaly` rows; insufficient history (<6 profiles) → job `done` with `result.state = "insufficient_history"`.
- `GET /carbon-api/dq/anomalies/` — filter by table, severity, date. Anomalies also emit `notify_event(event_type='dq_anomaly', ...)` following the existing `dq/signals.py` pattern.

### 4. Fail-visible results

- `DQResult.passed` → allow null; add `status` (`passed | failed | skipped_unavailable`). Data migration maps existing rows.
- `engine.evaluate` / `services` nl_check branch: Pulse unavailable/error → `DQResult(status='skipped_unavailable', passed=null)`, and the rule is excluded from score denominators. `GET /dq/metrics/` gains `skipped_rules` count so the gap is visible.
- Same treatment for suggest/anomaly job failures: job `failed` with `error`, never fabricated output.

### 5. Contract doc — `docs/PULSE_CONTRACT_SPEC.md`

- Mark `anomaly.detect` as "consumed by Carbon (Phase 4) — Pulse-side implementation pending"; specify the exact payload Carbon sends (metrics history, sensitivity, volume_anomaly_pct) and expects (anomalies[] with expected/observed/score/explanation).
- Note the suggestion-feedback path (`reject_reason`) as a future `dq.suggest.feedback` task type — doc only.

## Explicit exclusions

- No frontend (Phase 5). No scheduler. No Pulse-side code. No `classification.infer`/`query.answer`/`report.draft`.

## Gates

1. Backend green: `cd backend && python -m pytest -q` (or `./manage.sh test` from repo root). Note: there is **no `verify.sh`** in this repo — `manage.sh test` wraps pytest.
2. `python -m pytest dq/ -q` — green; new tests ≥ 12: suggestion accept→rule-created (with `RuleFieldAssignment`), reject flow, invalid-suggestion quarantine, anomaly job with mocked gateway (anomalies stored, insufficient-history state), fail-visible paths (gateway raising → `skipped_unavailable`, excluded from score), `volume_anomaly_pct` actually read.
3. Migrations: `DQSuggestion`, `DQAnomaly`, `DQResult.status` — apply cleanly.
4. API smoke: create suggest job with mocked Pulse → suggestion appears in `GET /dq/suggestions/`; accept → rule exists and runs.

## Done criteria

From the API alone: request suggestions → accept one into a working rule; run an anomaly job → stored anomalies with expected-vs-observed numbers and explanations; take Pulse down → scores honestly show "unknown", nothing silently passes.
