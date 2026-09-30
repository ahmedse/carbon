# O1 readiness audit

**Target:** O1 — Smart Village electricity and diesel.  
**Product:** Carbon on AASTMT.  
**Date:** 2026-09-29.  
**Owner:** carbon-inventory-lead.  
**Question:** What does ready require for jobs, observability, health, data quality, and coverage?  
**Answer:** The leaf is not ready to publish. Process health can be green while the inventory is not.  
**Limit:** This audit does not change code, does not lock a period, and does not score `carbon.clearturn.tech`.

Ready, by P-12, names the target, the product, the evidence, the date, and the limit. A green `/carbon-api/health/` is not that sentence.

---

## Jobs

There is no scheduled job for the footprint.

| Mechanism | What it does | O1 |
|-----------|----------------|----|
| `EMISSIONS_AUTO_CALC` | Default `False` in `config/settings.py`. Not set in `backend/.env`. | Stays off. `calculate` is a person confirming the run. |
| `emissions/signals.py` `auto_calculate_on_row_save` | On `DataRow` save, if the flag is on and a `CalculationRule` has `auto_calculate=True`, creates calculations. | Not the O1 path while the flag is off. |
| Same file, factor `pre_save` | When `factor_value` changes, marks non-superseded calculations `is_stale=True`. | Sync side effect. Not a queue. |
| `setup_carbon_app` | Manual command. Seeds an Egypt grid kWh factor and a water m3 factor at scope 3. | Water is outside O1. Not the rollout. |
| `seed_emission_factors` | Manual library. Includes `FUEL_DIESEL_STAT` unit `liter`, source DEFRA 2024, and many scope 3 rows. `--clear` deletes factors. | This audit did not query whether that row is loaded on `carbon_dev`. Do not run `--clear`. |
| Platform DQ jobs | `nl_check` and `anomaly_detect` are job-only inside `dq/services.py`. | They are not CR-DQ-01. |

No Celery beat entry for emissions was found.

---

## Observability

| Signal | Where | What it measures | What it does not measure |
|--------|-------|------------------|--------------------------|
| `GET /carbon-api/health/` | `config/health_views.py` | Database `SELECT 1`, Redis cache round-trip, disk free percent, last backup, admin log count | Open periods, O1, factors, coverage |
| `GET /carbon-api/health/metrics/` | Same file | `carbon_database_up`, `carbon_disk_free_pct`, `carbon_last_backup_age_seconds` | Inventory |
| `GET /carbon-api/health/prometheus/` | `core/telemetry.py` | `carbon_api_requests_total`, `carbon_api_duration_seconds`, `carbon_dq_runs_total`, `carbon_ai_conversations_active`, freshness gauges | No `open_period_count` series |
| Excellence observed | `CARBON-ONB-OBS-04` / `OBS-05` | Pytest shape on HEAD. Rank 5 file absent | A 14-day live series |
| Factor stale log | `emissions/signals.py` | Count of calculations marked stale | A kilogram |

The `carbon_` prefix on those metrics is the platform process. It is not the Smart Village inventory.

The O1 signal that exists is still `GET /carbon-api/carbon/onboarding/o1/`. On 29 Sep 2026, `carbon_dev` returned count 2 and no kilograms.

---

## Health

`/carbon-api/health/` returns 200 when the database answers and Redis and disk are acceptable. It returns 503 when status is `degraded`.

A 200 does not mean one open period. It does not mean a factor exists. It does not mean a calculation exists.

Footprint health, for this leaf, is the onboarding checklist:

| Check | Ready when |
|-------|------------|
| CR-PER-01 | Exactly one status open. Today: FY 2023-24 id 15 Open. FY 2025-26 id 16 Locked. |
| CR-BND-01 | That period has a boundary and one of the three approaches. |
| CR-SRC-01 | Both Smart Village source names exist. Diesel description is generators or fleet, one word. |
| CR-FAC-01 | Active kWh scope 2 and litre scope 1, country EGY or blank, source text non-empty. |
| CR-DQ-01 | Quantity > 0 on a linked table. A missing month is a gap. The checklist emits no DQ code until that table exists. |
| CR-COV-01 | Goal is draft, scope 1+2, materiality_bounded, tier 4, and only after the sources exist. |
| CR-PULSE-01 | A quoted kilogram is in this turn's tool payload. |

---

## Data quality

Three different numbers exist. Only one is the O1 tier.

| Number | Source | Meaning | Use for O1 |
|--------|--------|---------|------------|
| `data_quality_tier` 1–5 | `InventorySourceStatus` | 1 Audited … 5 Proxy. Smaller is better. Onboarding minimum is 4. A figure that leaves the organisation needs 3 or better. | Yes. P-05. |
| AssetProfile percent | `OwnerService._build_dq_summary` | Passing assets / total assets × 100. | No. That is catalog asset health. |
| Chairman `data_quality` | `ChairmanService` | `min(100, int((months_with_data / 36) * 100 * 3))`. | No. That is a month-count heuristic. |
| `carbon_dq_runs_total` | `dq/services.py` `run_dq` | Platform rule runs by status passed / failed / skipped. | No, until a table is linked and a rule is bound on purpose. |

CR-DQ-01 does not appear in `evaluate_o1`. Catalogue stays planned. A zero must not be inserted for a missing month.

---

## Coverage

Two calculators. They do not answer the same question.

| | Onboarding checklist `evaluate_o1` | `InventoryCoverageService.compute_coverage` | `ChairmanService` coverage |
|--|-------------------------------------|-----------------------------------------------|----------------------------|
| Covered | Linked tables on this period, and a Calculation for this period | Any status `covered` on that period id | Any status `covered` on the source, any period |
| Goal | Scope `1+2`, status `draft`, `materiality_bounded`, tier 4. Omits `target_coverage_pct` | First goal with status `active`. If none, completeness becomes `absolute` | Does not read the goal |
| Percent | Not copied onto the checklist | `covered / denominator × 100`. Denominator drops exclusions only when the active goal is materiality-bounded | `covered / total × 100`. Excluded sources stay in the gap count |
| Tonnes | Only `summary_kg` from the calculation summary for the single open period | None | All calculations in the user's org scope, not limited to the open period. Code comment: figures are platform-wide |

`CoverageGoal.target_coverage_pct` is a required decimal on the model. A goal row cannot be saved without a percent. O1 says do not store that percent before the two sources exist, and do not default it to 100.

Chat may repeat a number that is inside `get_chairman_overview`, because CR-PULSE-01 allows that payload. That number is not the O1 period total. Staff do not call it the Smart Village footprint.

---

## What ready still requires

1. Exactly one period Open. Done on `carbon_dev` 30 Sep 2026: FY 2023-24 id 15 Open, FY 2025-26 id 16 Locked.
2. One boundary on that period, approach one of the three. Done: `Smart Village Operational Control`, `operational_control`.
3. Both O1 sources, or an explicit gap. Done on `carbon_dev`: both names covered. South Valley, Abu Qir, and Alamein excluded `insufficient_data`.
4. Factor rows that pass CR-FAC-01. The checklist must not show `factor_value`.
5. Activity with quantity > 0. Missing months stay gaps.
6. A person confirms the calculation.
7. Coverage status uses the checklist rule, not the chairman percent.
8. A quoted kilogram is `summary_kg` from the two linked tables. Period-wide `get_calculation_summary` is not that number.
9. Rank 5 observed is the served GET (`CARBON-ONB-OBS-05`). The evidence JSON path stays absent. Overall stays 4 until every dimension has a passing rank-5 cell.
10. `carbon.clearturn.tech` is still unscored.

P1 and P2 stay closed. Catalogue stays planned. `blocks_release` stays empty.
