# Carbon DQ Core — Audit

**Date:** 2026-08-10
**Scope:** The data-quality (DQ) core of the Data Trust Platform — backend (`backend/dq/`, `backend/dataschema/`, `backend/pulse_gateway.py`), frontend (`carbon-frontend/src`), docs (`docs/`, `plans/`, root `TASK-DQ-*`), and a benchmark against Ataccama ONE, leading DQ/observability systems, and research literature.

---

## 1. What actually exists

### 1.1 Three mechanisms, not two

**A. Entry-time validation ("Level 1")** — `backend/dataschema/validators.py::validate_row`
Reads `DataField` metadata (`required`, `type`, `validation` JSON with `min`/`max`/`pattern`, `reference_set`, date). Runs in `DataRowSerializer.validate()` and bulk import; failures → HTTP 400, write blocked. Mirrored client-side in `DataRowFormDrawer.jsx` with inline per-field errors. Deterministic, blocking, mechanical.

**B. The DQ rule engine** — `backend/dq/`
- 8 rule types (`dq/models.py:9-19`): `not_null, unique, allowed_values, range, regex, reference_integrity, threshold, nl_check`.
- `RULE_LEVELS = field_validation | business_rule` — **never read by evaluation code**; cosmetic label + API filter only.
- Attachment via `RuleFieldAssignment` (M2M; `data_field=null` ⇒ table-level).
- Execution: manual API only (`POST /dq/run/`, `bulk-execute`, `rules/{id}/execute`) plus one hook after emissions batch calculation (`emissions/models.py:999`, `try/except: pass`). **No Celery, no cron, no scheduler anywhere in the repo.** Management commands exist (`profile_all`, `check_freshness`, `schema_snapshot`) for an external crontab that is not wired.
- Severity (`info/warn/error`) is advisory only — never blocks, quarantines, or drives notification priority (notifications key off `failed_count > 10`, not rule severity).
- Observability pieces: `TableProfile`/`FieldProfile`, `FreshnessCheck`, `SchemaSnapshot`/`SchemaChange`, metrics endpoints, score rollup into `catalog.AssetProfile.quality_score`, `dq_violation` notification on failed runs.

**C. Pulse integration ("Levels 2/3")** — `backend/pulse_gateway.py`
- `dq.validate` backs the `nl_check` rule type (LLM judges rows; explanation + confidence stored in `DQResult.sample_failures`). **Fails open** when Pulse is down (rule auto-passes).
- `dq.suggest` backs `POST /dq/suggest/` — suggestions **never persisted, no UI consumer**.
- Contract (`docs/PULSE_CONTRACT_SPEC.md`) also defines `anomaly.detect`, `classification.infer`, `query.answer`, `report.draft` — **none implemented**.

### 1.2 Frontend

- Consolidated DQ Hub (`pages/catalog/DQHubPage.jsx`) with Dashboard/Rules/Profiles/Freshness&Schema tabs.
- Rule creation via `DQRuleDialog.jsx` (table → level → field → type → params). Dialog offers a third level, `relation_integrity`, that **does not exist in the backend enum**.
- Per-table DQ tabs, per-row DQ metrics panel, module trust gauges.
- **No violations/incidents view** — aggregate failed counts only, no row-level drill-down, no incident workflow.
- Field editors inconsistent: old `FieldForm.jsx` has a raw "Validation (JSON)" textarea; newer `FieldEditorDialog.jsx` has **no validation UI**; neither connects to the DQ rule system.
- Pulse UI = external chat widget only.
- Dead/broken: legacy `DQDashboardPage`/`DQRulesPage` unreachable but still imported; `DQMetricsDrawer` dead code with swapped args; `getFieldProfiles` calls a nonexistent endpoint (`dq/field-profiles/`); `bulkExecuteRules` exported but bypassed.

## 2. User's mental model vs reality

| Belief | Reality |
|---|---|
| "Field CRUD: attach rules, applied when entering data" | Only the raw `validation` JSON on `DataField` is enforced at entry. **DQRule records are never evaluated on write** — rule-violating data is stored and flagged later. The two systems are disconnected. |
| "Field-level validation is mechanical" | Correct. Wart: the no-negatives rule is **hardcoded** into the generic platform validator (`dataschema/validators.py:106`) — a carbon-domain opinion baked into domain-neutral code. |
| "Business-level DQ is outsourced to Pulse" | Half true. `nl_check` exists, but the canonical example (electricity-bill surge in Alamein) is **anomaly detection over aggregates**, which is implemented nowhere. `DQProfileConfig.volume_anomaly_pct` exists in DB/API and is **read by zero lines of engine code**. No baseline, no seasonality, no statistics. |
| "Two levels" | The model declares two levels but behavior has three tiers (entry-time / batch engine / Pulse), and the declared levels do nothing. |

## 3. Philosophy assessment

The documented philosophy — *Trust = Governed + Quality + Cataloged + Observable + Explainable*; metadata-driven; AI stays in Pulse, core stays deterministic; never block on Pulse; rules-as-data via API; quality scores rolled into the catalog as a trust signal — is **aligned with the state of the art**:

- Trust signal in catalog ⇔ Ataccama's Data Trust Index.
- Deterministic core vs AI/semantic split ⇔ market stratification: code-first tools (dbt tests, Great Expectations, SodaCL) own "known unknowns"; ML observability (Monte Carlo, Anomalo, Metaplane) owns "unknown unknowns"; LLMs own rule *authoring* and semantic judgment (Informatica CLAIRE GPT, GX ExpectAI, Ataccama AI Agent).
- Fail-open on Pulse is defensible for UX but silently degrades the trust signal to "everything passes" — must be surfaced in results and scores.

Doc-level drift found: `DESIGN_DATA_TRUST_CORE.md` says "core never calls Pulse; Pulse pulls" while shipped code pushes (contract v2.0 ratified push; design doc never updated); rule-type lists disagree across docs (5/6/7/8; `value_range`/`completeness` examples don't exist); Level 2/3/Phase-4 task headers still say "NOT STARTED" though commits `0da0da5`, `5478368`, `5cff2ff` landed; `PULSE_CONTRACT_SPEC` header still says "not yet implemented".

## 4. Benchmark

### 4.1 Ataccama ONE (Gartner "Augmented DQ" Leader; v17.1, mid-2026)

| Capability | Ataccama | Carbon |
|---|---|---|
| Attribute rules | No-code builder + expression language, dimension-tagged | 7 deterministic types — comparable breadth |
| Record/aggregate rules | GROUP BY aggregation rules (avg, count, composite uniqueness) | **None** — no cross-row/cross-field expressions |
| Cross-table rules | Existence/consistency joins across systems | Only `reference_integrity` against reference sets |
| DQ dimensions | Every rule tagged; scores per dimension (Validity/Completeness/Uniqueness/Timeliness/Accuracy) | **No dimension model** — flat average |
| AI rule generation | NL → full rule (GenAI), AI Agent bulk-creates, profiling-based suggestions | `dq.suggest` server-side only — no persistence, no UI |
| Anomaly detection | Isolation Forest + time-series over profile history, explainable | **None** — config fields inert |
| Observability | Freshness, volume, schema-change, drift + OpenLineage pipeline lineage | Freshness ✓, schema-change ✓, volume/drift ✗, lineage ✗ |
| Write-time enforcement | **DQ Firewall**: central rules exposed as REST/GraphQL at point of entry | **Missing** — exactly the Mechanism A/B split |
| Incidents/remediation | Alerts → escalation → Jira/ServiceNow; remediation plans route bad rows to stewards | Notification only; no incident model, no quarantine, no drill-down |

### 4.2 Wider field and research

- Monte Carlo / Anomalo / Metaplane / AWS Glue DQ: **unsupervised, seasonality-aware anomaly detection over table metrics** — the accepted solution to the "surge" example.
- Deequ (Amazon, PVLDB 2018): profile-driven **constraint suggestion** — statistics first, LLMs second.
- HoloClean (VLDB 2017), denial-constraint & FD discovery: rules can be *discovered* from data, not only hand-written.
- LLM-for-DQ research (Narayan et al. VLDB 2023; Table-GPT 2023; "Quality by Prompt" 2025 — NL → Great Expectations rules): validates LLMs for rule *authoring* and semantic checks, not for statistical detection.
- DAMA DMBOK2 (8 dimensions) and Wang & Strong (1996): canonical dimension frameworks — cheap to adopt as rule tags.
- Data contracts (ODCS v3.1, Linux Foundation): schema + quality + SLA enforced in CI/CD — the write-time enforcement pattern.

**Calibration:** Ataccama is hundreds of engineers over a decade. The goal is their *shape* — dimensions, one rule world enforced everywhere, statistical monitors, an incident loop — not feature parity.

## 5. Bugs found (fix regardless of strategy)

1. `GET /dq/metrics/table/<id>/` and `/field/<id>/` filter on FKs removed in migration 0009 → **HTTP 500** (`dq/views.py:772,838`).
2. `bulk-execute` double-counts every rule as failure — list-vs-dict bug (`dq/views.py:305`).
3. `DQRuleExecutor` (`dq/executor.py`) is a hollow duplicate: `execute()` with no sample validates 0 rows and always passes; `POST /dq/rules/{id}/execute/` hits this path. Also accepts a `'custom'` type not in `RULE_TYPES`.
4. Inert config: `DQProfileConfig.auto_profile_enabled`, `volume_anomaly_pct`, `sample_size` unread by engine; `check_freshness` ignores per-table `expected_max_age_hours`.
5. `DQRule` docstring promises entry-time validation and a "Pulse scheduler" — both false.
6. Stale doc/task headers as listed in §3; dead frontend code as listed in §1.2.

## 6. Recommendations (ranked)

1. **Close the A/B split** — one rule world: field-level DQRules enforced at write time (DQ Firewall pattern) or compiled into `DataField.validation`.
2. **Real anomaly detection** — scheduled profiling + z-score/IQR over stored metrics, honoring `volume_anomaly_pct`; Pulse explains anomalies, doesn't compute them.
3. **Make severity act** — error blocks/quarantines on import, warn flags; minimal incident model.
4. **Persist Pulse suggestions** — accept → creates DQRule; reject with reason.
5. **Tag rules with DQ dimensions** — per-dimension score rollup.
6. Fix §5 bugs; delete dead frontend code.

The detailed execution design lives in `plans/CARBON_DQ_CORE_PLAN.md`.
