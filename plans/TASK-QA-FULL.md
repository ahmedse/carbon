# TASK-QA-FULL — Comprehensive Platform Validation
**Assigned to:** QA/Validator (DeepSeek-V3)
**Date:** 2026-08-06
**Based on:** `plans/PHASED_EXECUTION_PLAN.md` (Phases 0-2 complete, 3-6 pending)
**Goal:** Validate every endpoint, model, and functionality in the Carbon Data Trust Platform
**Duration:** 2-3 days

---

## Activation

1. Read `.ai-toolkit/project.config.md` → project identity, HARD RULES (especially RULE_1–RULE_8)
2. Read `.ai-toolkit/shared/qa-framework.md` → 4-layer validation model, evidence standards
3. Read `.ai-toolkit/roles/qa-validator.md` → your role constraints (no code, evidence only)
4. Run `./manage.sh start` to bring up backend + DB
5. Acquire a JWT token: `curl -X POST http://localhost:8009/carbon-api/token/ -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}'`
6. Confirm: "Ready as QA/Validator for Carbon. Checklist items: 200+"

---

## Prerequisite: Backend Server

```bash
./manage.sh start backend
# Verify: curl http://localhost:8009/carbon-api/health/
```

---

## SECTION A — Swagger / API Schema (3 checks)

| # | Check | Method | Expected |
|---|-------|--------|----------|
| A1 | Swagger UI reachable | Browser: `http://localhost:8009/carbon-api/swagger/` | Swagger UI renders, lists all endpoints grouped by tag |
| A2 | Schema JSON valid | `curl http://localhost:8009/carbon-api/swagger/?format=openapi` | Valid JSON, status 200 |
| A3 | Swagger in prod gated | Check `config/urls.py` — swagger only on DEBUG/IS_DEVELOPMENT | Confirm gated |

---

## SECTION B — Emissions App (GHG Protocol) — 35+ endpoints

### B1 — Reporting Periods (`/carbon-api/carbon/periods/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| B1.1 | `periods/` | GET | Any | Returns list with `organizational_boundary`, `total_emissions`, status fields |
| B1.2 | `periods/` | POST | Admin | Creates period with name, start_date, end_date, organizational_boundary |
| B1.3 | `periods/{id}/` | GET | Any | Detail includes all fields |
| B1.4 | `periods/{id}/` | PATCH | Admin | Update name, dates, boundary |
| B1.5 | `periods/{id}/` | DELETE | Admin | Soft delete or 204 |
| B1.6 | `periods/{id}/submit/` | POST | Admin/analyst | Transitions to submitted, creates pending VerificationRecord |
| B1.7 | `periods/{id}/verify/` | POST | Admin | Transitions to verified, updates VerificationRecord |
| B1.8 | `periods/{id}/reject/` | POST | Admin | Transitions back, requires reason |
| B1.9 | `periods/{id}/lock/` | POST | Admin | Locks period, blocks calculations |
| B1.10 | `periods/{id}/inventory_report/` | GET | Any | JSON report with scope totals, Scope 2 dual breakdown, boundary, base year, quality, verification |
| B1.11 | `periods/{id}/inventory_report/?format=pdf` | GET | Any | PDF download (WeasyPrint required) |

### B2 — Emission Factors (`/carbon-api/carbon/factors/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| B2.1 | `factors/` | GET | Any | List with filters: category, scope, country_code, search, active |
| B2.2 | `factors/` | POST | Admin | Creates factor with name, code, category, scope, value, unit, valid_from, valid_to |
| B2.3 | `factors/{id}/` | GET | Any | Detail includes all fields |
| B2.4 | `factors/{id}/` | PATCH | Admin | Update factor — confirm `is_active` filter for active factors |
| B2.5 | `factors/{id}/` | DELETE | Admin | 204 |
| B2.6 | `factors/summary/` | GET | Any | Minimal list for dropdowns (id, name, code) |
| B2.7 | `factors/categories/` | GET | Any | Returns category choices |

### B3 — GWP (`/carbon-api/carbon/gwp/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| B3.1 | `gwp/` | GET | Any | List of GWP values |
| B3.2 | `gwp/` | POST | Admin | Creates GWP (gas, value, source, effective_date) |
| B3.3 | `gwp/{id}/` | GET | Any | Detail |
| B3.4 | `gwp/{id}/` | PATCH | Admin | Update |
| B3.5 | `gwp/{id}/` | DELETE | Admin | 204 |

### B4 — Calculations (`/carbon-api/carbon/calculations/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| B4.1 | `calculations/` | GET | Any | List includes `scope2_method`, `emission_factor_snapshot`, `factor_applied_at`, `quality_score`, `data_quality_tier` |
| B4.2 | `calculations/` | POST | Analyst | Creates calculation; verify `emission_factor_snapshot` populated |
| B4.3 | `calculations/{id}/` | GET | Any | Detail with all Phase 2 fields |
| B4.4 | `calculations/{id}/` | DELETE | Admin | 204 |
| B4.5 | `calculations/summary/` | GET | Any | Aggregated summary by scope |
| B4.6 | `calculations/{id}/recalculate/` | POST | Admin | Recalculates, preserves superseded row |
| B4.7 | `calculations/batch-recalculate/` | POST | Admin | Batch recalculation |

### B5 — Calculation Rules (`/carbon-api/carbon/rules/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| B5.1 | `rules/` | GET | Any | List includes `scope2_calculation_method`, `data_quality_tier` |
| B5.2 | `rules/` | POST | Admin | Creates rule with scope2_calculation_method, data_quality_tier |
| B5.3 | `rules/{id}/` | GET | Any | Detail |
| B5.4 | `rules/{id}/` | PATCH | Admin | Update scope2 method, quality tier |
| B5.5 | `rules/{id}/` | DELETE | Admin | 204 |

### B6 — Verification Records (`/carbon-api/carbon/verifications/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| B6.1 | `verifications/` | GET | Any | List with status, verifier, notes |
| B6.2 | `verifications/{id}/` | GET | Any | Detail |
| B6.3 | `verifications/{id}/verify/` | POST | Admin | Sets status to verified |
| B6.4 | `verifications/{id}/reject/` | POST | Admin | Sets status to rejected, requires reason |

### B7 — Calculation Audits (`/carbon-api/carbon/calculation-audits/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| B7.1 | `calculation-audits/` | GET | Any | List with before/after values, triggered_by |
| B7.2 | `calculation-audits/{id}/` | GET | Any | Detail |

### B8 — SBTi Targets (`/carbon-api/carbon/targets/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| B8.1 | `targets/` | GET | Any | List with baseline year, target year, reduction % |
| B8.2 | `targets/` | POST | Admin | Create SBTi target |
| B8.3 | `targets/{id}/` | GET | Any | Detail |
| B8.4 | `targets/{id}/` | PATCH | Admin | Update |
| B8.5 | `targets/{id}/` | DELETE | Admin | 204 |

### B9 — Report Configs (`/carbon-api/carbon/report-configs/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| B9.1 | `report-configs/` | GET | Any | List saved report configs |
| B9.2 | `report-configs/` | POST | Admin | Create config (name, period, scope_filter, format) |
| B9.3 | `report-configs/{id}/` | GET | Any | Detail |
| B9.4 | `report-configs/{id}/` | PATCH | Admin | Update |
| B9.5 | `report-configs/{id}/` | DELETE | Admin | 204 |

### B10 — Export Audits (`/carbon-api/carbon/export-audits/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| B10.1 | `export-audits/` | GET | Any | List with who/when/format/config_hash |
| B10.2 | `export-audits/{id}/` | GET | Any | Detail |

### B11 — Organizational Boundaries (Phase 2 — NEW) (`/carbon-api/carbon/boundaries/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| B11.1 | `boundaries/` | GET | Any | List with name, consolidation_approach, is_active, included_org_units |
| B11.2 | `boundaries/` | POST | Admin | Create boundary (name, approach, description, org_units) |
| B11.3 | `boundaries/{id}/` | GET | Any | Detail includes org_units_names |
| B11.4 | `boundaries/{id}/` | PATCH | Admin | Update approach, description, org_units |
| B11.5 | `boundaries/{id}/` | DELETE | Admin | 204 (or deactivate) |

### B12 — Base Years (Phase 2 — NEW) (`/carbon-api/carbon/base-years/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| B12.1 | `base-years/` | GET | Any | List with year, reporting_period, recalculation_policy, open_triggers_count |
| B12.2 | `base-years/` | POST | Admin | Create base year (year, period, policy, threshold) |
| B12.3 | `base-years/{id}/` | GET | Any | Detail |
| B12.4 | `base-years/{id}/` | PATCH | Admin | Update policy, threshold |
| B12.5 | `base-years/{id}/` | DELETE | Admin | 204 |
| B12.6 | `base-years/{id}/recalculate/` | POST | Admin | Creates RecalculationTrigger, processes recalculation |

### B13 — Recalculation Triggers (Phase 2 — NEW) (`/carbon-api/carbon/recalculation-triggers/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| B13.1 | `recalculation-triggers/` | GET | Any | List with trigger_type, description, variance_pct, resolution_status |
| B13.2 | `recalculation-triggers/` | POST | Admin | Create trigger linked to base_year, with type/description/variance |
| B13.3 | `recalculation-triggers/{id}/` | GET | Any | Detail includes display fields |
| B13.4 | `recalculation-triggers/{id}/` | PATCH | Admin | Update resolution_status, notes |
| B13.5 | `recalculation-triggers/{id}/resolve/` | POST | Admin | Sets resolved_at, marks recalculation complete |

### B14 — Dashboard & Analytics (`/carbon-api/carbon/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| B14.1 | `dashboard/` | GET | Any | Returns aggregated emission data, scope breakdown |
| B14.2 | `owner-dashboard/` | GET | Data Owner | Org-scoped dashboard |
| B14.3 | `owner/summary/` | GET | Data Owner | Summary stats for org unit |
| B14.4 | `owner/assets/` | GET | Data Owner | Asset list for org unit |
| B14.5 | `owner/activity/` | GET | Data Owner | Recent activity for org unit |
| B14.6 | `my-data/` | GET | Data Owner | Consolidated owner data |
| B14.7 | `yearly-comparison/` | GET | Any | Year-over-year emission comparison |
| B14.8 | `report/` | GET | Any | Report with org_unit_id, format, scope filter params |
| B14.9 | `calculate/` | POST | Analyst | Single calculation trigger |
| B14.10 | `batch-calculate/` | POST | Admin | Batch calculation trigger |
| B14.11 | `console/` | GET | Any | Console landing page data |

---

## SECTION C — Data Schema (`/carbon-api/dataschema/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| C1 | `tables/` | GET | Any | List DataTables with fields count, row count |
| C2 | `tables/` | POST | Admin | Create table with name, description, org_unit |
| C3 | `tables/{id}/` | GET | Any | Detail with fields list |
| C4 | `tables/{id}/` | PATCH | Admin | Update, check `is_locked` blocks edits |
| C5 | `tables/{id}/` | DELETE | Admin | 204 |
| C6 | `fields/` | GET | Any | List DataFields |
| C7 | `fields/` | POST | Admin | Create field (name, data_type, table FK) |
| C8 | `fields/{id}/` | GET | Any | Detail |
| C9 | `fields/{id}/` | PATCH | Admin | Update field type, name |
| C10 | `fields/{id}/` | DELETE | Admin | 204 |
| C11 | `rows/` | GET | Any | List DataRows with data JSON, table context |
| C12 | `rows/` | POST | Analyst | Create row with field values JSON |
| C13 | `rows/{id}/` | GET | Any | Detail with parsed values |
| C14 | `rows/{id}/` | PATCH | Analyst | Update row data |
| C15 | `rows/{id}/` | DELETE | Admin | 204 |
| C16 | `schema-logs/` | GET | Any | Schema change log entries |
| C17 | `relations/` | GET | Any | Table relations list |
| C18 | `relations/` | POST | Admin | Create table relation |

---

## SECTION D — Data Quality (`/carbon-api/dq/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| D1 | `profiles/` | GET | Any | List field profiles |
| D2 | `table-profiles/` | GET | Any | List table profiles |
| D3 | `rules/` | GET | Any | List DQ rules with type, threshold, severity |
| D4 | `rules/` | POST | Admin | Create rule (6 types: completeness, uniqueness, range, pattern, freshness, custom) |
| D5 | `rules/{id}/` | GET | Any | Detail |
| D6 | `rules/{id}/` | PATCH | Admin | Update rule params |
| D7 | `rules/{id}/` | DELETE | Admin | 204 |
| D8 | `rules/{id}/execute/` | POST | Admin | Execute single rule, returns DQResult |
| D9 | `results/` | GET | Any | List DQ results with pass/fail, score |
| D10 | `profile/` | POST | Admin | Trigger profiling |
| D11 | `profile/bulk/` | POST | Admin | Bulk profile trigger |
| D12 | `run/` | POST | Admin | Run all DQ rules |
| D13 | `metrics/` | GET | Any | Overall DQ metrics |
| D14 | `metrics/table/{table_id}/` | GET | Any | Table-level DQ metrics |
| D15 | `metrics/field/{field_id}/` | GET | Any | Field-level DQ metrics |
| D16 | `run-validation/` | POST | Admin | Run DQ validation |

---

## SECTION E — MDM / Reference Data (`/carbon-api/mdm/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| E1 | `reference-sets/` | GET | Any | List reference sets |
| E2 | `reference-sets/` | POST | Admin | Create reference set |
| E3 | `reference-sets/{id}/` | GET | Any | Detail |
| E4 | `reference-sets/{id}/` | PATCH | Admin | Update |
| E5 | `reference-sets/{id}/` | DELETE | Admin | 204 |
| E6 | `reference-values/` | GET | Any | List values with set filter |
| E7 | `reference-values/` | POST | Admin | Create value in set |
| E8 | `reference-values/{id}/` | GET | Any | Detail |
| E9 | `reference-values/{id}/` | PATCH | Admin | Update value |
| E10 | `reference-values/{id}/` | DELETE | Admin | 204 |
| E11 | `org-units/` | GET | Any | List org units (tree-aware) |
| E12 | `org-units/` | POST | Admin | Create org unit with parent |
| E13 | `org-units/{id}/` | GET | Any | Detail with children_count, descendants_count |
| E14 | `org-units/{id}/` | PATCH | Admin | Update, move parent |
| E15 | `org-units/{id}/` | DELETE | Admin | 204 (blocks if has children) |
| E16 | `org-units/tree/` | GET | Any | Full tree structure |
| E17 | `org-units/{id}/children/` | GET | Any | Direct children |
| E18 | `org-units/{id}/ancestors/` | GET | Any | Ancestor chain |
| E19 | `org-units/{id}/descendants/` | GET | Any | All descendants flat |
| E20 | `org-units/by_type/` | GET | Any | Filter by org unit type |
| E21 | `org-units/search/` | GET | Any | Search by name |
| E22 | `org-units/stats/` | GET | Any | Org unit statistics |
| E23 | `org-units/{id}/move/` | POST | Admin | Move to new parent |
| E24 | `org-units/reorder/` | POST | Admin | Reorder siblings |
| E25 | `bind-field/` | POST | Admin | Bind field to reference set |
| E26 | `field-options/` | GET | Any | Get field options from bound set |

---

## SECTION F — Catalog (`/carbon-api/catalog/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| F1 | `domains/` | GET | Any | List data domains |
| F2 | `domains/` | POST | Admin | Create domain |
| F3 | `domains/{id}/` | GET | Any | Detail |
| F4 | `domains/{id}/` | PATCH | Admin | Update |
| F5 | `domains/{id}/` | DELETE | Admin | 204 |
| F6 | `glossary/` | GET | Any | List glossary terms |
| F7 | `glossary/` | POST | Admin | Create term |
| F8 | `glossary/{id}/` | GET | Any | Detail |
| F9 | `glossary/{id}/` | PATCH | Admin | Update |
| F10 | `glossary/{id}/` | DELETE | Admin | 204 |
| F11 | `tags/` | GET | Any | List tags |
| F12 | `tags/` | POST | Admin | Create tag |
| F13 | `tags/{id}/` | GET | Any | Detail |
| F14 | `tags/{id}/` | PATCH | Admin | Update |
| F15 | `tags/{id}/` | DELETE | Admin | 204 |
| F16 | `assets/` | GET | Any | List asset profiles |
| F17 | `assets/` | POST | Admin | Create asset profile |
| F18 | `assets/{id}/` | GET | Any | Detail |
| F19 | `assets/{id}/` | PATCH | Admin | Update |
| F20 | `assets/{id}/` | DELETE | Admin | 204 |
| F21 | `governance-events/` | GET | Any | List governance events |
| F22 | `governance-events/` | POST | Admin | Create event |
| F23 | `governance-policies/` | GET | Any | List governance policies |
| F24 | `governance-policies/` | POST | Admin | Create policy |
| F25 | `search/` | GET | Any | Catalog search across domains/glossary/assets |
| F26 | `governance/compliance/` | GET | Any | Compliance summary |

---

## SECTION G — Accounts & RBAC (`/carbon-api/accounts/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| G1 | `users/` | GET | Admin | List users (non-admin sees own only) |
| G2 | `users/` | POST | Admin | Create user with groups |
| G3 | `users/{id}/` | GET | Any | Detail (own or admin) |
| G4 | `users/{id}/` | PATCH | Admin | Update user, assign groups |
| G5 | `users/{id}/` | DELETE | Admin | 204 |
| G6 | `groups/` | GET | Admin | List groups with member count |
| G7 | `groups/` | POST | Admin | Create group |
| G8 | `groups/{id}/` | GET | Admin | Detail with members |
| G9 | `groups/{id}/` | PATCH | Admin | Update group, add/remove members |
| G10 | `groups/{id}/` | DELETE | Admin | 204 |
| G11 | `scoped-roles/` | GET | Admin | List scoped roles |
| G12 | `scoped-roles/` | POST | Admin | Create scoped role (user, group, org_unit, module) |
| G13 | `scoped-roles/{id}/` | GET | Admin | Detail |
| G14 | `scoped-roles/{id}/` | PATCH | Admin | Update scope |
| G15 | `scoped-roles/{id}/` | DELETE | Admin | 204 |
| G16 | `role-audit-logs/` | GET | Admin | List role assignment audit logs |
| G17 | `my-roles/` | GET | Any | Current user's roles |
| G18 | `me/context/` | GET | Any | Current user context (org_units, modules, capabilities) |
| G19 | `role-registry/` | GET | Admin | Full role registry |
| G20 | `change-password/` | POST | Any | Change own password |
| G21 | `logout/` | POST | Any | Logout / token blacklist |
| G22 | `platform-apps/` | GET | Any | List platform apps |
| G23 | `platform-apps/{app_id}/` | GET | Any | App detail |
| G24 | `pulse-auth/` | POST | Admin | Pulse AI authentication |
| G25 | `pulse-provision/` | POST | Admin | Pulse AI provisioning |
| G26 | `audit-log/` | GET | Admin | Legacy audit log list |
| G27 | `audit-log/{id}/` | GET | Admin | Legacy audit log detail |
| G28 | `access-control/` | GET/POST | Admin | Access control list / create |
| G29 | `access-control/{id}/` | GET/PATCH/DELETE | Admin | Access control detail / update / delete |
| G30 | `capability-matrix/` | GET | Admin | Full capability matrix |

---

## SECTION H — Evidence (`/carbon-api/evidence/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| H1 | `evidence/` | GET | Any | List evidence records with file URLs |
| H2 | `evidence/` | POST | Analyst | Upload evidence file (PDF/JPEG/PNG) |
| H3 | `evidence/{id}/` | GET | Any | Detail with file URL, attached objects |
| H4 | `evidence/{id}/` | PATCH | Analyst | Update metadata |
| H5 | `evidence/{id}/` | DELETE | Admin | 204, file deleted from disk |
| H6 | Evidence attach/detach | POST | Analyst | Attach evidence to DataRow, verify link appears in detail |

---

## SECTION I — Connections (`/carbon-api/connections/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| I1 | `sources/` | GET | Any | List data sources |
| I2 | `sources/` | POST | Admin | Create source with connection_config |
| I3 | `sources/{id}/` | GET | Any | Detail — **CRITICAL: secrets must be masked (***)** |
| I4 | `sources/{id}/` | PATCH | Admin | Update, secrets write-only |
| I5 | `sources/{id}/` | DELETE | Admin | 204 |
| I6 | `consuming/` | GET | Any | List consuming connections |
| I7 | `consuming/` | POST | Admin | Create consuming connection |
| I8 | `consuming/{id}/` | GET | Any | Detail |
| I9 | `consuming/{id}/` | PATCH | Admin | Update |
| I10 | `consuming/{id}/` | DELETE | Admin | 204 |

---

## SECTION J — Import/Export (`/carbon-api/importexport/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| J1 | `export-projects/` | GET | Any | List export projects |
| J2 | `export-projects/` | POST | Admin | Create export project |
| J3 | `export-projects/{id}/` | GET | Any | Detail |
| J4 | `export-projects/{id}/` | PATCH | Admin | Update |
| J5 | `export-projects/{id}/` | DELETE | Admin | 204 |
| J6 | `import/` | GET | Any | List import jobs |
| J7 | `import/` | POST | Admin | Create import job (upload CSV) |
| J8 | `import/{id}/` | GET | Any | Detail with status (pending/running/done/failed) |
| J9 | `export/` | GET | Any | List export jobs |
| J10 | `export/` | POST | Admin | Create export job |
| J11 | `export/{id}/` | GET | Any | Detail with download URL if ready |

---

## SECTION K — Auth Endpoints (`/carbon-api/`)

| # | Endpoint | Method | Auth | What to Validate |
|---|----------|--------|------|------------------|
| K1 | `token/` | POST | None | Obtain JWT pair (access + refresh) |
| K2 | `token/refresh/` | POST | None | Refresh access token |
| K3 | `health/` | GET | None | Health check — 200, `{"status":"ok"}` |
| K4 | Token throttle | POST x6 (rapid) | None | 429 after 5 attempts/minute |

---

## SECTION L — RBAC Matrix Validation

Test each role against critical endpoints:

| # | Role | Endpoint | Method | Expected |
|---|------|----------|--------|----------|
| L1 | Anonymous | `carbon/periods/` | GET | 401 |
| L2 | Anonymous | `token/` | POST | 200 (with valid creds) |
| L3 | Viewer | `carbon/calculations/` | POST | 403 |
| L4 | Viewer | `carbon/periods/` | GET | 200 |
| L5 | Analyst | `carbon/calculations/` | POST | 201 |
| L6 | Analyst | `carbon/periods/{id}/verify/` | POST | 403 (admin only) |
| L7 | Analyst | `dataschema/rows/` | POST | 201 |
| L8 | Admin | `carbon/periods/{id}/verify/` | POST | 200 |
| L9 | Admin | `accounts/users/` | GET | 200 |
| L10 | Data Owner (scoped) | `carbon/owner-dashboard/` | GET | 200 (scoped to org) |
| L11 | Data Owner (scoped) | `carbon/dashboard/` | GET | 200 (but scoped data) |
| L12 | Data Owner (scoped) | `mdm/org-units/` | GET | 200 (filtered to visible) |

---

## SECTION M — Phase 2 Model Validation (GHG Protocol)

| # | Check | How |
|---|-------|-----|
| M1 | `Calculation.scope2_method` exists | GET any calculation, check field present |
| M2 | `Calculation.emission_factor_snapshot` populated | Create calculation, verify snapshot JSON present |
| M3 | `Calculation.factor_applied_at` timestamped | Check it's within 1 second of creation |
| M4 | `Calculation.quality_score` is 0-100 | Check property returns number in range |
| M5 | `Calculation.data_quality_tier` matches rule | Tier 1 rule → score > 66, Tier 3 → score < 33 |
| M6 | `CalculationRule.scope2_calculation_method` | Create rule with location_based, market_based, dual |
| M7 | Dual Scope 2 creates 2 Calculations | Rule with dual → Scope 2 activity → 2 Calculation rows |
| M8 | `OrganizationalBoundary` CRUD | Create, read, update boundary with org_units |
| M9 | `BaseYear` unique constraint | Create 2 active base years → second should fail |
| M10 | `RecalculationTrigger` workflow | Create trigger, resolve it |
| M11 | `ReportingPeriod.organizational_boundary` FK | Assign boundary to period, GET shows boundary name |
| M12 | Inventory report JSON | GET `periods/{id}/inventory_report/` → valid JSON with all sections |
| M13 | Inventory report PDF | GET `periods/{id}/inventory_report/?format=pdf` → PDF bytes if WeasyPrint |

---

## SECTION N — Anti-Pattern Scan

| # | Check | Command | Expected |
|---|-------|---------|----------|
| N1 | No `print()` in views | `grep -rn "print(" backend/*/views.py` | 0 (or documented exceptions) |
| N2 | No hardcoded secrets | `grep -rPn "(password|secret|key)\s*=\s*['\"]\w{4,}" backend/ --include="*.py"` | 0 in non-test files |
| N3 | No `datetime.now()` | `grep -rn "datetime.now()" backend/ --include="*.py"` | 0 (use timezone.now()) |
| N4 | Core apps don't import emissions | `grep -rn "from emissions\|import emissions" backend/{accounts,core,catalog,mdm,dq,dataschema,connections,evidence,importexport}/` | 0 |
| N5 | `.gitignore` covers raw/, *.sql, *.dump | `cat .gitignore \| grep -E "raw/|\*.sql|\*.dump"` | All 3 present |
| N6 | No __pycache__ tracked | `git ls-files \| grep __pycache__` | 0 |
| N7 | No .pyc tracked | `git ls-files \| grep "\.pyc$"` | 0 |

---

## SECTION O — Frontend Smoke Tests (Browser)

| # | Page | URL | What to Check |
|---|------|-----|---------------|
| O1 | Login | `/carbon/login` | Login form renders, JWT obtained, redirects to console |
| O2 | Console | `/carbon/console` | Dashboard cards render, data loads |
| O3 | Emissions Dashboard | `/carbon/emissions` | Charts render, scope breakdown visible |
| O4 | Calculations | `/carbon/calculations` | Table renders, calculations listed |
| O5 | Verification | `/carbon/verifications` | Pending tab shows records |
| O6 | Reporting Periods | `/carbon/periods` | List renders, status badges |
| O7 | Assets | `/carbon/assets` | Asset list renders |
| O8 | Reference Data | `/carbon/reference-data` | Reference sets + values |
| O9 | Data Schema | `/carbon/dataschema` | Tables list renders |
| O10 | DQ Dashboard | `/carbon/dq` | Metrics display |
| O11 | Admin: Users | `/carbon/admin/users` | User CRUD |
| O12 | Admin: Groups | `/carbon/admin/groups` | Group management |
| O13 | Admin: Rules | `/carbon/admin/rules` | Calculation rules |
| O14 | Admin: Factors | `/carbon/admin/factors` | Emission factors |
| O15 | Admin: GWP | `/carbon/admin/gwp` | GWP management |
| O16 | Admin: Targets | `/carbon/admin/targets` | SBTi targets |
| O17 | Dark mode toggle | Any page | Switch to dark, verify all elements readable |
| O18 | Breadcrumbs | Deep page | Breadcrumb trail correct |
| O19 | Sidebar collapse | Any page | Toggle collapse, navigation still works |
| O20 | 404 page | `/carbon/nonexistent` | Friendly 404, not white screen |

---

## SECTION P — Test Suite Gate

| # | Check | Command | Expected |
|---|-------|---------|----------|
| P1 | Backend tests pass | `python -m pytest backend/ -x --tb=short` | 664 passed (or more) |
| P2 | Verify no test regressions | Check that Phase 2 additions didn't break existing | All original tests pass |
| P3 | Frontend lint | `cd carbon-frontend && npm run lint` | 0 errors |
| P4 | Frontend build | `cd carbon-frontend && npm run build` | Build succeeds |

---

## Deliverable

Create `TASK-RESULT-QA-FULL.md` with:

1. **Summary table**: Total endpoints tested, passed, failed, blocked
2. **Per-section results**: Each check with ✅/❌/⚠️/🚫 (blocked) + evidence
3. **RBAC matrix**: Table of L1-L12 results
4. **Anti-pattern findings**: Any N1-N7 violations with file:line
5. **Bug list**: Each bug with severity (CRITICAL/HIGH/MEDIUM/LOW), reproduction steps, evidence (curl output, screenshot)
6. **Recommendations**: What to fix before Phase 3

**Evidence standard**: Every ❌ must include curl command + actual response or screenshot. No evidence = not a valid finding.
