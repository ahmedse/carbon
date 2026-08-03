# TASKS-P3.md — Phase 3: Test Coverage for Service-Heavy Apps
# Master Architect → Backend Worker | Date: 2026-07-31
# Role: Backend Worker | Model: DeepSeek | Budget: ~35K tokens

---

## Audit Reality Check

| App | Service lines | Existing test | Actual coverage |
|-----|--------------|--------------|-----------------|
| emissions | 1,101 | test_services.py (129 lines) | 4/9 classes, 9 shallow tests |
| dq | 535 | test_executor.py (476 lines) | All rule types + run_dq + profile_table + bulk — good |
| catalog | 17 | None for services | 1 function untested |

**Strategy:** Extend emissions tests (the big gap). dq adds missing direct tests for `_compute_quality`. catalog adds idempotency test.

---

## G1 — emissions/services.py: Untested Classes

### What EXISTS (test_services.py, 129 lines):
- CalculationEngineService.validate_calculation_request (5 tests)
- TargetService.get_progress (1 test)
- DashboardService.get_dashboard_data (2 tests)
- OwnerService.get_org_units (2 tests)

### What to ADD:

#### A. YearlyComparisonService (3 tests)
- test_comparison_returns_structure: call get_comparison(superuser, [2024,2025]), verify keys
- test_empty_years: call with empty list, verify structure exists
- test_baseline_year_set_from_period: create baseline period, verify baseline_year matches

#### B. ReportService (4 tests)
- test_report_returns_structure: generate_report(superuser), verify title/scope_details/format
- test_report_with_org_unit: filter by org_unit_id
- test_report_with_period: filter by period_id
- test_empty_report: no calculations exist, structure still valid

#### C. CalculationEngineService — extend (2 tests)
- test_batch_calculate_active_rules: create rules, call batch_calculate, verify counts
- test_batch_calculate_empty_tables: call with empty table IDs

#### D. OwnerService — extend (3 tests)
- test_get_owner_dashboard: returns stats, performance_summary
- test_get_owner_summary: returns structure
- test_get_owner_assets: returns list, search filter

#### E. MyDataService (3 tests)
- test_get_my_data_returns_none_for_unscoped_user: user with no org units
- test_get_my_data_returns_structure: user with org_unit, verify keys
- test_get_my_data_quality_status: create asset profile, verify quality fields

#### F. ConsoleService (3 tests)
- test_console_returns_structure: superuser, verify active_period/stats/alerts
- test_console_no_active_period: no reporting periods, doesn't crash
- test_console_dq_alerts: create low-quality asset, verify alerts

#### G. ReportConfigService (2 tests)
- test_generate_from_config_returns_structure: create config, verify keys
- test_generate_from_config_filters: verify scope/category filtering

#### H. TargetService (1 additional)
- test_get_progress_zero_data: no calculations match, actual_tco2e is 0.0

**Total: ~21 new tests across 8 classes**

---

## G2 — dq/services.py: Missing Direct Tests

test_executor.py already covers all rule types, run_dq, profile_table, run_single_rule, bulk_profile.
Add direct unit tests for the remaining:

- test_compute_quality_no_rules: _compute_quality returns 'unknown', None
- test_compute_quality_all_passing: creates 3 passing results → 'passing', 100
- test_compute_quality_mixed: 1 pass, 1 fail → 'warning', 50

---

## G3 — catalog/services.py

- test_ensure_asset_profiles_creates_profiles
- test_ensure_asset_profiles_idempotent: run twice, count same
- test_ensure_asset_profiles_returns_count

---

## Verification Gate

```bash
./manage.sh manage check --deploy 2>&1 | grep -i error || echo "No errors"
./manage.sh test emissions dq catalog --keepdb 2>&1 | tail -10
./manage.sh test --keepdb 2>&1 | tail -5
./.ai-toolkit/scripts/verify.sh backend 2>&1 | tail -10
```
