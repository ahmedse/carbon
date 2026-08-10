# Carbon DQ Core — Next-Generation Phased Plan

**Date:** 2026-08-10
**Status:** Approved direction, pending phase sign-off
**Companion:** `docs/CARBON_DQ_CORE_AUDIT.md` (as-is findings this plan fixes)
**North star:** `docs/STRATEGY_DATA_TRUST_PLATFORM.md` — Trust = Governed + Quality + Cataloged + Observable + Explainable

---

**Execution task specs (one per phase, self-contained for an executing agent):**
`TASK-DQ-CORE-P0-FIXES.md` · `TASK-DQ-CORE-P1-RULE-CORE.md` · `TASK-DQ-CORE-P2-GATE.md` · `TASK-DQ-CORE-P3-JOBS.md` · `TASK-DQ-CORE-P4-PULSE.md` · `TASK-DQ-CORE-P5-WORKSPACE.md` — execute strictly in order; each carries its own gates.

## 0. Design principles (what makes this "next-gen")

Built to avoid the known flaws of existing DQ systems (see audit §4):

1. **One rule world.** A rule is a versioned JSON document. The same definition is enforced at write time (gate), at import, and in batch runs. No split-brain between "entry validation" and "DQ rules" (today's Mechanism A/B split — the most common flaw in the field).
2. **Deterministic core, AI at the edge.** The core engine is pure, testable, provider-free. Everything AI (NL checks, suggestions, anomaly detection, explanations) is a **Pulse plugin** behind the existing task contract. No SDK imports, no model names, fail-visible.
3. **JSON-first authoring, Pulse-assisted.** No sophisticated rule-builder form. A validated JSON editor in the UI; Pulse drafts the JSON from natural language; a human approves. Rules are data: diffable, exportable, API-creatable.
4. **Severity acts.** `error` blocks/quarantines, `warn` stores-and-flags, `info` records. No advisory-only severities, no alert noise from meaningless failures.
5. **Jobs, not hidden automation.** Anything beyond the field-level gate is an explicit, user-started **Job** with a status you follow to completion. No silent schedulers, no magic.
6. **Zero dead config.** Every config field is wired or deleted (today: `volume_anomaly_pct`, `auto_profile_enabled`, `sample_size` are inert).
7. **Dimensions everywhere.** Every rule carries a DAMA dimension; scores roll up per dimension so the trust signal is legible to auditors.
8. **Fail-visible AI.** When Pulse is down, results say `skipped: pulse_unavailable` and the score reflects the gap — never a silent auto-pass.

## 1. Target architecture

```
                ┌────────────────────────────────────────────┐
                │            DQ Workspace (React)            │
                │  /dq — one sidebar entry, 5 tabs           │
                └───────────────┬────────────────────────────┘
                                │ REST /carbon-api/dq/
        ┌───────────────────────┼─────────────────────────────┐
        │                       │                             │
┌───────▼────────┐    ┌─────────▼─────────┐         ┌────────▼────────┐
│  Gate (sync)   │    │  Jobs (async)     │         │  Rule store     │
│  dq/gate.py    │    │  DQJob + runner   │         │  DQRule v2      │
│  pure evaluate │    │  dq/jobs.py       │         │  JSON def, dim, │
│  + /gate/check │    │  submit → poll    │         │  versioned      │
└───────┬────────┘    └─────────┬─────────┘         └─────────────────┘
        │ write-path hook       │ pulse tasks
        │ (dataschema)          ▼
        │               ┌─────────────────┐
        │               │  Pulse plugins  │  dq.validate · dq.suggest
        │               │  (AI lives here)│  anomaly.detect · explain
        │               └─────────────────┘
        ▼
 DataRow writes / bulk import  →  gate verdict: pass | warn | block | quarantine
```

- **Gate** = standalone, stateless checker. Only deterministic, field-level types (`not_null, unique, allowed_values, range, regex, reference_integrity, threshold`) plus the existing Level-1 metadata checks. Milliseconds, in-request.
- **Jobs** = everything else: batch rule runs, profiling, freshness/schema sweeps, `nl_check`, `suggest`, `anomaly_detect`. User opens a job, watches it finish.
- **Pulse plugins** = AI implementations behind `pulse_gateway.py`. Contract additions needed: task status polling, `anomaly.detect` payload, suggestion feedback.

## 2. Rule JSON schema (v1) — the single authoring format

```json
{
  "schema_version": 1,
  "name": "electricity_kwh_non_negative",
  "description": "kWh can never be negative",
  "level": "field",
  "dimension": "validity",
  "type": "range",
  "severity": "error",
  "active": true,
  "bindings": [{"table": "utility_bills", "field": "kwh"}],
  "params": {"min": 0},
  "enforcement": {"on_write": true, "on_import": "block"}
}
```

```json
{
  "schema_version": 1,
  "name": "alamein_electricity_surge_watch",
  "level": "business",
  "dimension": "accuracy",
  "type": "anomaly_detect",
  "severity": "warn",
  "bindings": [{"table": "utility_bills", "field": null}],
  "params": {"metric": "sum(kwh)", "grain": "monthly", "group_by": ["building"], "sensitivity": "medium"}
}
```

- `level`: `field | business`. `field` rules with deterministic types run in the **gate**; everything else runs as a **job**. Engine dispatch is derived from type, not stored.
- `dimension`: `completeness | validity | accuracy | consistency | timeliness | uniqueness | integrity | reasonability` (DAMA DMBOK2 set).
- `type`: existing 7 + `nl_check` + `anomaly_detect` (+ later: `expression` for cross-field, `cross_table`).
- `enforcement.on_write`: only honored for gate-eligible types; ignored otherwise (validated).
- Server-side validation per type (`dq/rule_schema.py` — hand-rolled validators, no new dependency). Pulse generates this JSON from NL ("fill-in" flow); humans edit raw JSON only.

## 3. Phases

Each phase ends green: `verify.sh backend` + DQ test suite + a manual UI pass. Estimates assume one developer.

---

### Phase 0 — Stop the bleeding (≈1 day)

Fix the audit's §5 bugs; zero new features.

- [ ] `dq/views.py:772,838` — metrics endpoints query removed FKs → rewrite via `RuleFieldAssignment` (fixes HTTP 500).
- [ ] `dq/views.py:305` — `bulk_execute` list-vs-dict double count.
- [ ] Delete `dq/executor.py`; route `rules/{id}/execute/` to `run_single_rule()`. (Kills the always-passes stub path and the duplicate if/elif chain.)
- [ ] Remove or wire inert `DQProfileConfig` fields (decision: **delete** `auto_profile_enabled`, `sample_size`; `volume_anomaly_pct` deferred to Phase 4 — mark deprecated in serializer help_text). Note: per-table freshness thresholds don't exist — `FreshnessCheck.expected_max_age_hours` is only a snapshot of the global default; document it, per-table override is a Phase 6 candidate.
- [ ] Fix `DQRule` docstring; update stale TASK-DQ Level 2/3/Phase-4 headers to DONE with commit refs; fix `PULSE_CONTRACT_SPEC` header; align rule-type lists in `DESIGN_DATA_TRUST_CORE.md` and `plans/CARBON_DATA_TRUST_ARCHITECTURE.md`.
- [ ] Frontend: delete `DQMetricsDrawer.jsx`, legacy `DQDashboardPage`/`DQRulesPage` imports, dead `getFieldProfiles`/`bulkExecuteRules`, stale `StatusBar` paths.
- **Done when:** the 6 bug classes are gone, 153+ DQ tests pass, no dead imports.

---

### Phase 1 — Unified rule core (≈3–4 days)

Make rules versioned JSON with dimensions; single evaluator.

- [ ] `dq/rule_schema.py` — per-type param validators + dimension enum + `validate_definition(dict)`.
- [ ] `DQRule` v2 (`dq/models.py`): add `dimension`, `definition` JSON (full v1 doc), `version` int, `archived` bool. Keep existing columns as derived/indexed (name/type/severity denormalized from `definition` for querying). Migration: wrap existing rules into v1 JSON.
- [ ] `dq/engine.py` — **one** evaluator (from `services.py::_evaluate_rule`, the only survivor after Phase 0), signature `evaluate(rule_def, rows) -> verdict`.
- [ ] Replace 409-on-delete with **archive** (rules with results are archived, not deleted; grid filter "show archived").
- [ ] Emit per-dimension rollups in `GET /dq/metrics/` (`scores_by_dimension`).
- [ ] Move the hardcoded no-negatives check out of `dataschema/validators.py` into seeded field-level rules (carbon seed), making the platform domain-neutral again.
- [ ] Tests: schema validation per type; migration fidelity; dimension rollup; archive semantics.
- **Done when:** any rule is fully described by its JSON doc; old UI dialog still works against denormalized fields (temporary compatibility).

---

### Phase 2 — The Gate (≈3 days)

Standalone write-time enforcement — the Ataccama "DQ Firewall" pattern, minus the enterprise weight.

- [ ] `dq/gate.py` — `check_rows(table, rows, mode) -> {row_verdicts, summary}`; pure function over gate-eligible rules bound to the table. Severity mapping: `error → block`, `warn → store + flag`, `info → record`.
- [ ] `POST /carbon-api/dq/gate/check/` — stateless endpoint (also serves external producers later; auth = existing scoped permissions).
- [ ] Write-path hook: `DataRowSerializer.validate()` + `BulkImportService` call the gate after Level-1 `validate_row`. Import modes: `block` (reject row) vs `quarantine` (store with `dq_flagged=True`, reported in import summary). Row-level flag field on `DataRow` (JSON: failed rule ids + severity).
- [ ] `enforcement.on_write=true` field rules now **actually enforced at entry** — closes the A/B split.
- [ ] Frontend `DataRowFormDrawer`: surface gate `warn` as non-blocking helper text, `block` as error (backend 400 mapping already exists — fix `err.response.data` reading to match `apiFetch` behavior).
- [ ] Tests: gate purity (no DB writes), severity mapping, import quarantine, write-path 400/flag flows.
- **Done when:** a `range` rule with `severity=error, on_write=true` rejects a bad row via API and import; `warn` stores-and-flags; the flag is visible on the row.

---

### Phase 3 — Jobs (≈3–4 days)

Explicit, followable execution for everything non-gate.

- [ ] `DQJob` model: `job_type` (`rule_run | profile | freshness | schema | nl_check | suggest | anomaly`), `status` (`queued | running | done | failed | canceled`), `target` (rule/table nullable), `payload` JSON, `result` JSON, `pulse_task_id`, `progress` 0–100, `created_by`, timestamps, `error`.
- [ ] Runner (`dq/jobs.py`): **no Celery**. Deterministic jobs (`rule_run`, `profile`, …) execute inline at creation (their data volumes are small) with status transitions persisted; Pulse jobs submit via gateway and are **polled**: `GET /dq/jobs/{id}/` re-checks Pulse task status until terminal. Contract addition: `GET {PULSE_URL}/tasks/{id}` (Pulse-side work, flagged to Pulse team).
- [ ] Endpoints: `POST /dq/jobs/` (create+run), `GET /dq/jobs/` (filter by status/type), `GET /dq/jobs/{id}/`, `POST /dq/jobs/{id}/cancel`.
- [ ] `POST /dq/rules/{id}/run/` becomes sugar for creating a `rule_run` job.
- [ ] `nl_check` moves from inline-in-run to job-only (it's LLM latency; never synchronous).
- [ ] Every job writes `DQResult`s as today, so history/trends/rollups keep working.
- [ ] Tests: lifecycle transitions, Pulse poll (mocked: pending→done, timeout→failed), cancel, result linkage.
- **Done when:** "Run this rule" from anywhere creates a job you can poll to a terminal state; Pulse jobs show real progress; nothing AI runs synchronously in a request.

---

### Phase 4 — Pulse DQ plugins (≈4–5 days; mostly Pulse-side, Carbon side is thin)

All AI lives here. Carbon stays deterministic.

- [ ] **Suggestions, persisted:** `DQSuggestion` model (payload JSON, rationale, confidence, status `pending|accepted|rejected`, reject_reason). `POST /dq/jobs/` type `suggest` → Pulse drafts v1-rule JSON → stored. `POST /dq/suggestions/{id}/accept` → creates the `DQRule`; `/reject` stores reason (feedback payload to Pulse later).
- [ ] **Anomaly detection:** implement contract `anomaly.detect` (Pulse-side: statistical first — z-score/IQR/seasonal baseline over `TableProfile` metrics and grouped aggregates; LLM only writes the human explanation). Carbon: `anomaly` job type + results stored as `DQAnomaly` (metric, group, expected range, observed, score, explanation, severity). Honors `volume_anomaly_pct` (finally wired).
- [ ] **Fail-visible:** `nl_check`/`suggest`/`anomaly` Pulse outages produce `DQResult(passed=None, status='pulse_unavailable')` surfaced in score as "unknown", never silent pass. (Breaking change to today's fail-open — call out in release notes.)
- [ ] **Explanations persisted:** nl_check/anomaly results always store `explanation` + `confidence` (already partially done in `sample_failures`).
- [ ] Tests: mocked gateway for all three plugins; unavailable-path assertions; accept→rule-created flow.
- **Done when:** from the UI you can request suggestions and accept one into a real rule; an anomaly job on `utility_bills` flags the Alamein-surge-style case with expected-vs-observed numbers and a Pulse-written explanation.

---

### Phase 5 — DQ Workspace frontend (≈5–7 days)

One menu, one workspace, system components reused.

**Route & menu**
- [ ] Single sidebar entry **"DQ Workspace"** → `/dq` (replaces the two legacy entries; `/catalog/dq*` redirects → `/dq`). Workspace page `pages/dq/DQWorkspacePage.jsx` with top-level tabs.

**Tab 1 — Overview**
- Score cards (overall + per-dimension from Phase 1), recent failures, jobs running now, trend sparkline. Reuse existing metric card patterns from `DQHubPage`.

**Tab 2 — Rules** (the grid)
- [ ] `pages/dq/RulesTab.jsx` — `components/DataGrid/CarbonDataGrid.jsx` with server-side filters (level, type, dimension, severity, active, tag, search-by-name) and row actions: **view icon** → `/dq/rules/:id`, run, activate/deactivate.
- [ ] "New rule" → JSON editor (plain textarea + client JSON-syntax check + server schema errors echoed) with a **"Draft with Pulse"** button (NL prompt → suggest job → JSON prefilled for approval). No form builder, per direction.

**Rule detail — `/dq/rules/:id`, multi-tab**
1. **Definition** — the JSON doc (edit → saves as new `version`), name/description, bindings (tables/fields), tags.
2. **Operations** — activate/deactivate, edit, run now (creates job → links to it), archive/delete (archive when results exist), duplicate.
3. **Usage & Data Products** — bound tables/fields; related catalog assets (via table → module → `AssetProfile`, which carries the quality rollup); coverage stats; "used by N data products".
4. **Stats** — pass-rate trend (existing `rules/{id}/history/` + `improving/degrading`), checked/failed over time, last-run summary.
5. **Results** — grid of `DQResult` with sample-failures drill-down (row ids + explanation/confidence for AI checks).

**Tab 3 — Jobs**
- `CarbonDataGrid` of jobs (type, target, status chip, progress, created, duration); auto-refresh while any `running`; row → job detail drawer (payload, Pulse task id, result summary, error, cancel).

**Tab 4 — Suggestions**
- Pending Pulse suggestions: rationale + confidence + proposed JSON (collapsible); **Accept** (→ new rule, prefilled editor) / **Reject** (reason optional).

**Tab 5 — Monitoring**
- Reuse existing Profiles / Freshness / Schema-change components from `DQHubPage` (moved, not rewritten).

**Cleanup:** delete `DQHubPage` after migration; keep per-table DQ tabs (they deep-link into `/dq/rules?table=<id>`).
- [ ] Tests: route smoke, rules grid filter wiring, rule-detail tabs render, accept-suggestion flow (msw-mocked).
- **Done when:** everything DQ is reachable from one menu; a rule's full lifecycle (draft→approve→enforce→monitor→archive) happens without leaving the workspace.

---

### Phase 6 — Hardening & next-gen extras (ongoing, prioritized)

- [ ] **Incident-lite:** from a failed result, one click creates a tracked item (owner, status, note) — no Jira integration needed yet.
- [ ] **Expression rules** (`type: expression`, e.g. `scope1 + scope2 ≈ total`): safe evaluator (AST whitelist, no `eval`) — covers the cross-field gap vs Ataccama aggregation rules.
- [ ] **Rule coverage report:** tables/fields with no rules — the "unknown unknowns" prompt for Pulse suggestions.
- [ ] Optional external cron for `profile_all`/`check_freshness` as *system jobs* (still visible in the Jobs tab — principle 5 holds).
- [ ] Perf: push rule evaluation into SQL where trivially translatable (not_null/range/unique) once row counts demand it; pure-Python is fine until then.
- [ ] Docs: update `DESIGN_DATA_TRUST_CORE.md` (Pulse push direction), strategy doc stage markers, `AGENTS.md` if conventions change.

## 4. Out of scope (explicit)

- No Celery/Redis, no scheduler daemon (jobs are user-started; optional cron is Phase 6).
- No no-code rule builder form (JSON + Pulse drafting is the authoring UX).
- No Jira/ServiceNow, no lineage/OpenLineage, no SQL pushdown, no multi-env promotion — enterprise weight we don't need yet.
- No Pulse-side implementation in this repo (contract work flagged to the Pulse platform).

## 5. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Fail-visible (Phase 4) makes scores dip when Pulse is down | Intended honesty; Overview shows "N rules skipped" separately from failures |
| Inline job execution blocks requests on big tables | Row-count guard → auto-switch to "queued" + management-command worker (`run_dq_jobs`) if a deployment needs it |
| JSON authoring errors | Server schema validation with precise errors; Pulse drafting as the primary path |
| `anomaly.detect` needs history (≥6 profiles) | Gate the job with a clear "insufficient history" state; Phase 6 cron builds history |
| Scope creep toward Ataccama parity | Principles 1–8 are the contract; Phase 6 items require explicit sign-off |

## 6. Effort summary

| Phase | Scope | Estimate |
|---|---|---|
| 0 | Bug fixes, dead code, doc drift | 1 day |
| 1 | Rule JSON v2, dimensions, one engine | 3–4 days |
| 2 | Gate + write-path enforcement | 3 days |
| 3 | Jobs + Pulse polling | 3–4 days |
| 4 | Pulse plugins (suggest/anomaly/fail-visible) | 4–5 days |
| 5 | DQ Workspace frontend | 5–7 days |
| 6 | Hardening (rolling) | as prioritized |

**~3–4 weeks of focused work to a robust core** (Phases 0–5), Phase 6 rolling.
