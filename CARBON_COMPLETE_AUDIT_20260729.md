# CARBON DATA TRUST PLATFORM — COMPLETE END-TO-END AUDIT

**Generated**: 2026-07-29 | **Scope**: Backend + Frontend + AI Toolkit Compliance  
**Context**: Post 3-phase cleanup (venv, 27 TASK files, ai_copilot, duplicates, deprecated apps)

---

## EXECUTIVE SUMMARY

| Dimension | Score | Trend |
|-----------|-------|-------|
| Backend completeness | 70% | ⚠️ |
| Frontend completeness | 65% | ⚠️ |
| Carbon domain app | 60% | 🔴 |
| AI Toolkit compliance | 50% | 🔴 |
| Test coverage | 25% | 🔴 |
| Service pattern compliance | 20% | 🔴 |

**VERDICT**: The platform has strong bones (11 backend apps, 70+ frontend pages, solid RBAC, 41 migrations) but suffers from **fat views**, **missing services**, **stale tooling config**, **insufficient tests**, and **incomplete carbon domain features**. The user's question — "until I have a complete end-to-end domain app" — requires ~40 fixes across 6 workstreams.

---

## SECTION 1: PLATFORM ARCHITECTURE (BACKEND)

### 1.1 App Inventory (11 apps)

| App | Views (lines) | Has services.py? | Tests | Status |
|-----|--------------|-------------------|-------|--------|
| `accounts` | 474 | ❌ | 7 test files | ✅ Core RBAC complete |
| `catalog` | 356 | ✅ (17 lines) | 4 test files | ✅ Governance hub |
| `connections` | 81 | ❌ | 0 | ⚠️ Minimal |
| `core` | 92 | ❌ | 3 test files | ✅ Module+Feedback |
| `dataschema` | 625 | ❌ | 3 test files | ✅ Dynamic schema |
| `dq` | 709 | ✅ (535 lines) | 3 test files | ✅ Best service pattern |
| `emissions` | **1,418** | ❌ **CRITICAL** | 4 test files | 🔴 **Fat views** |
| `evidence` | 137 | ❌ | 0 | ⚠️ Minimal, untested |
| `importexport` | 116 | ❌ | 0 | ⚠️ Minimal, untested |
| `mdm` | 646 | ❌ | 6 test files | ✅ Org hierarchy |
| `config` | — | — | — | ✅ Settings/URLs |

### 1.2 FAT VIEWS ANTI-PATTERN (CRITICAL)

Only **2 of 11 apps** have a `services.py`. The `emissions` app (1,418 lines) has **195 lines of business logic directly in views.py** — filter chains, aggregation, Decimal arithmetic, data-quality hacks.

```python
# emissions/views.py — THIS SHOULD BE IN services.py
scope_data = queryset.values('scope').annotate(total_kg=Sum('co2e_kg'), count=Count('id'))
monthly_data = queryset.values('reporting_month', 'scope').annotate(total_kg=Sum('co2e_kg'))
grand_total_kg = sum(s['total_kg'] or 0 for s in scope_data)
# ... 1200 more lines of business logic ...
```

**FIX**: Create `emissions/services.py` with:
- `DashboardService` (scope breakdown, category breakdown, monthly trends, DQ score)
- `YearlyComparisonService` (YoY comparison, baseline calculation, SBTi trajectory)
- `ReportService` (GHG Protocol report generation, scope details)
- `CalculationEngineService` (bulk calculation, rule execution)
- `OwnerService` (owner dashboard, summary, assets, activity)

### 1.3 RBAC ENFORCEMENT GAPS (HIGH)

**Emissions endpoints lack view-level RBAC**:

| Endpoint | Current Permission | Should Be |
|----------|-------------------|-----------|
| `DashboardAPIView` | `IsAuthenticated` | `IsAuthenticated` + scoped data ✅ |
| `YearlyComparisonAPIView` | `IsAuthenticated` | + cross-org check |
| `ReportAPIView` | `IsAuthenticated` | + org-unit filter |
| `CalculateAPIView` | `IsAuthenticated` | `AdminOrSuperuserOnly` |
| `OwnerDashboardAPIView` | `IsAuthenticated` | + owner role check |
| `MyDataAPIView` | `IsAuthenticated` | + data_owner role check |
| `ConsoleAPIView` | `IsAuthenticated` | + scoped to org |
| `ReportingPeriodViewSet` | `AdminOrSuperuserOnly` ✅ | Already correct |
| `EmissionFactorViewSet` | `AdminOrSuperuserOnly` ✅ | Already correct |
| `CalculationViewSet` | `IsAuthenticated` | needs AdminOrSuperuserOnly for write |

### 1.4 MISSING CARBON DOMAIN FEATURES

| Feature | Priority | Status |
|---------|----------|--------|
| SBTi target model | P1 | ❌ Missing — calculated on the fly in views |
| Verification workflow | P1 | ❌ Missing — Period has status field but no verify endpoints |
| Calculation audit trail | P1 | ⚠️ Partial — has calculated_by/at but no change log |
| Emission allocation (shared sources) | P2 | ❌ Missing |
| Auto DQ on calculations | P2 | ❌ Missing — no DQ integration |
| Batch calculation API | P2 | ❌ Missing |
| Calculation status/progress | P2 | ❌ Missing |
| GHG Protocol report export (PDF) | P2 | ❌ Missing — API only JSON |
| Scope 3 Category 1-15 detail | P3 | ⚠️ Category exists but no sub-categorization |
| Carbon offset credits | P3 | ❌ Missing |
| Supplier-specific factors | P3 | ❌ Missing |

### 1.5 API URL PREFIX CONFUSION (MEDIUM)

Two prefixes for the same emissions app:
```python
# backend/config/urls.py:59 and :60
path('api/v1/carbon/', include(('emissions.urls', 'carbon'), namespace='carbon')),
path(f'{api_prefix}/carbon/', include(('emissions.urls', 'carbon'), namespace='carbon')),
# api_prefix = 'carbon-api' — so second is /carbon-api/carbon/
```

**FIX**: Consolidate to single prefix. The frontend config.js already uses `emissionsAPI: "carbon/"` which works via `API_BASE_URL`. Pick one.

---

## SECTION 2: FRONTEND ARCHITECTURE

### 2.1 Page Inventory (~75 pages)

| Directory | Count | Status |
|-----------|-------|--------|
| `pages/carbon/` | 3 | 🔴 Too few for a domain app |
| `pages/emissions/` | 4 | ⚠️ Legacy pages |
| `pages/data-owner/` | 3 | ⚠️ Legacy (redirected to /carbon) |
| `pages/dashboards/` | 6 | ✅ Platform dashboards |
| `pages/catalog/` | ~25 | ✅ Rich catalog |
| `pages/admin/` | ~12 | ✅ Full admin |
| `pages/dataschema/` | ~5 | ✅ Data entry |
| Root pages | ~10 | ✅ Mixed |

### 2.2 CARBON APP FRONTEND GAPS (HIGH)

The Carbon domain app has only **3 pages**:
1. **CarbonConsolePage** — overview/landing
2. **ModuleWorkspacePage** — single module drill-down
3. **MyDataPage** — data owner workspace

**Missing pages for a complete domain app**:

| Page | Priority | Backend API exists? |
|------|----------|---------------------|
| CarbonAnalyticsPage (trends, YoY comparison) | P1 | ✅ yearly-comparison/ |
| CarbonReportViewerPage (interactive report) | P1 | ✅ report/ |
| CarbonVerificationPage (verify periods) | P1 | ❌ No verify API |
| CarbonFactorManagerPage (admin CRUD) | P2 | ✅ factors/ ViewSet |
| CarbonRuleManagerPage (admin CRUD) | P2 | ✅ rules/ ViewSet |
| CarbonTargetsPage (SBTi targets) | P2 | ❌ No target model |
| CarbonPeriodsPage (period management) | P2 | ✅ periods/ ViewSet |
| CarbonDataEntryPage (specialized entry) | P3 | ✅ via dataschema |

### 2.3 AI TOOLKIT RULE COMPLIANCE MATRIX

| Rule | Description | Compliance | Evidence |
|------|-------------|------------|----------|
| RULE_1 | Core never imports emissions | ✅ PASS | catalog/dq have "MUST NOT import" comments; 0 violations |
| RULE_2 | API through apiFetch | ✅ 90% | All carbon pages use api/emissions modules |
| RULE_3 | ShellSidebar only studio nav | ✅ PASS | Sidebar reads APP_REGISTRY manifest |
| RULE_4 | carbon-api/ prefix | ⚠️ FIX | Dual prefix `/api/v1/carbon/` + `/carbon-api/carbon/` |
| RULE_5 | design tokens, no hardcoded colors | 🔴 FAIL | **20 files** have hardcoded hex colors |
| RULE_6 | No in-repo AI | ✅ PASS | ai_copilot removed from codebase |
| RULE_7 | Thin views, fat services | 🔴 FAIL | **8/11 apps** have no services.py |
| RULE_8 | MUI v6 Grid (no `item` prop) | 🔴 FAIL | **10 files** still use `item` prop |
| RULE_9 | Single breadcrumb | ✅ PASS | Breadcrumbs.jsx exists, used in EditorArea |
| RULE_10 | All date formatting via systemTime.js | ⚠️ UNKNOWN | systemTime.js exists but not verified across all pages |
| RULE_11 | NotificationProvider for feedback | ✅ PASS | NotificationProvider.jsx exists |
| RULE_12 | RBAC: global vs org-scoped | ✅ PASS | ScopedRole with org_unit/module scope |

### 2.4 HARDCODED COLOR VIOLATIONS (RULE_5)

These 20 files have `#xxxxxx` hex codes (must use `theme.palette`):
- `pages/EmissionsDashboard.jsx`, `EmissionsReport.jsx`
- `pages/DataHubHome.jsx`, `ScopeInfoPage.jsx`, `Login.jsx`
- `pages/dashboards/*` (5 files)
- `pages/data-owner/*` (1 file: DataOwnerAssetsPage)
- `pages/Help.jsx`, `SettingsPage.jsx`, `TableManagerPage.jsx`
- `pages/dataschema/*` (4 files)

**FIX**: Replace all `#xxxxxx` with `theme.palette.*` references or `carbonDesign` tokens.

### 2.5 MUI V6 GRID MIGRATION (RULE_8)

10 files still use `<Grid item>` (must use Grid2 or no `item` prop):
- `components/Layout/ResponsiveGrid.jsx`
- `components/entity/EntityDetailShell.jsx`
- `components/dq/DQMetricsPanel.jsx`
- `components/FilteredDataGrid.jsx`
- `pages/carbon/CarbonConsolePage.jsx`
- `pages/ScopeInfoPage.jsx`, `Help.jsx`
- `pages/data-owner/DataOwnerPortalPage.jsx`, `DataOwnerDashboardPage.jsx`
- `pages/DataHubHome.jsx`

### 2.6 STALE AI REFERENCES (MEDIUM)

| File | Issue | Fix |
|------|-------|-----|
| `src/config.js:121-129` | AI routes (aiChat, aiInsights, aiPreferences, aiQa) | Remove lines 119-130 |
| `src/api/aiCopilot.js` | Stale API module for deleted app | Delete file |

---

## SECTION 3: AI TOOLKIT CONFIGURATION ISSUES

### 3.1 project.config.md STALENESS (CRITICAL)

The config has a **second set of RULE_3-10** that are **gigacast forecaster rules** from a previous project:

```
RULE_5=Forecaster data sources MUST be Prediction instances (id=0 reserved for manual entry)
RULE_6=Forecaster inference_service runs via ML feature service (ai_engines/powergen7)
RULE_7=Actuals reset requires BOTH: delete from ds1 AND clear actual_value/error/error_pct...
RULE_8=Forecaster must implement set_inference_config()...
RULE_9=ORM list endpoints: select_related(None) + defer all JSONFields...
RULE_10=All date formatting in frontend through src/utils/systemTime.js...
```

**KEY_ARCHITECTURE_FILES** all point to nonexistent gigacast paths:
```
AI_INFERENCE=backend/aihub/services/inference_service.py  ← DOES NOT EXIST
AI_FEATURES=backend/datahub_v2/services/ml_feature_service.py  ← DOES NOT EXIST
AI_ENGINE_PG7=backend/ai_engines/powergen7/forecaster.py  ← DOES NOT EXIST
FRONTEND_APP=frontend/src/App.jsx  ← WRONG: carbon-frontend/src/App.jsx
FRONTEND_DATETIME=frontend/src/utils/systemTime.js  ← WRONG
FRONTEND_ROUTES=frontend/src/utils/routes.js  ← WRONG
```

**FIX**: Remove lines ~90-121 (entire second RULE section + stale KEY_ARCHITECTURE_FILES), rewrite with Carbon-appropriate paths.

### 3.2 REGISTRY STATUS

✅ Freshly scanned (2026-07-29). All 4 registry files now reflect post-cleanup state.
⚠️ No CI hook to prevent staleness — registry can drift again.

---

## SECTION 4: TEST COVERAGE

### 4.1 Backend Test Summary

| App | Test Files | Test Lines | Coverage Estimate |
|-----|-----------|------------|-------------------|
| accounts | 7 | ~800 | 60% |
| catalog | 4 | ~500 | 40% |
| core | 3 | ~300 | 40% |
| dataschema | 3 | ~400 | 35% |
| dq | 3 | ~500 | 50% |
| emissions | 4 | ~600 | **15%** 🔴 |
| mdm | 6 | ~700 | 50% |
| connections | 0 | 0 | **0%** 🔴 |
| evidence | 0 | 0 | **0%** 🔴 |
| importexport | 0 | 0 | **0%** 🔴 |
| **TOTAL** | **31** | **~3,877** | **~30%** |

### 4.2 Missing Critical Tests

- [ ] `emissions/views.py` DashboardAPIView integration test
- [ ] `emissions/views.py` YearlyComparisonAPIView integration test
- [ ] `emissions/views.py` ReportAPIView integration test
- [ ] `emissions/views.py` CalculateAPIView integration test
- [ ] CalculationRule.execute() end-to-end test
- [ ] Calculation.create_from_data_row() unit test
- [ ] _scope_calcs() RBAC boundary tests
- [ ] ConsoleAPIView integration test
- [ ] connections app — all views
- [ ] evidence app — all views
- [ ] importexport app — all views
- [ ] Migration up/down validation
- [ ] Frontend component tests (0 tests in entire carbon-frontend/)

---

## SECTION 5: PRIORITIZED FIX PLAN

### WORKSTREAM A: ARCHITECTURE (P0 — 2-3 days)

| # | Fix | Files |
|---|-----|-------|
| A1 | Fix `project.config.md` — remove gigacast rules, fix paths | `.ai-toolkit/project.config.md` |
| A2 | Create `emissions/services.py` — extract ALL business logic from views | `backend/emissions/services.py` |
| A3 | Create services for accounts, catalog, mdm, dataschema | `backend/*/services.py` |
| A4 | Consolidate dual API prefix | `backend/config/urls.py` |

### WORKSTREAM B: FRONTEND COMPLIANCE (P0 — 1-2 days)

| # | Fix | Files |
|---|-----|-------|
| B1 | Remove AI routes from config.js | `frontend/src/config.js` |
| B2 | Delete `src/api/aiCopilot.js` | `frontend/src/api/aiCopilot.js` |
| B3 | Fix all 20 hardcoded hex colors → theme.palette | 20 .jsx files |
| B4 | Fix all 10 MUI v6 Grid `item` prop → Grid2 | 10 .jsx files |

### WORKSTREAM C: CARBON DOMAIN APP (P1 — 3-5 days)

| # | Fix | Description |
|---|-----|-------------|
| C1 | Build SBTi Target model | New model: `ReductionTarget` with baseline, target_year, reduction_pct |
| C2 | Build verification endpoints | `POST /emissions/periods/{id}/verify/`, `POST .../submit/` |
| C3 | Build CarbonAnalyticsPage | YoY comparison, trends, scope breakdown frontend page |
| C4 | Build CarbonReportViewerPage | Interactive report viewer frontend page |
| C5 | Build CarbonTargetsPage | SBTi target tracking frontend page |
| C6 | Add calculation audit trail | `CalculationAudit` model or extend `Calculation` with change tracking |
| C7 | Integrate DQ checks on calculations | Auto-run DQ validation after each calculation |

### WORKSTREAM D: TESTS (P1 — 2-3 days)

| # | Fix | Description |
|---|-----|-------------|
| D1 | Test emissions views (Dashboard, Yearly, Report, Calculate, Console) | 5 new test classes |
| D2 | Test CalculationRule.execute() end-to-end | Integration test |
| D3 | Test _scope_calcs() RBAC boundary | Unit tests |
| D4 | Test connections, evidence, importexport views | 6 new test modules |
| D5 | Add migration validation test | Verify all migrations apply + rollback |

### WORKSTREAM E: INFRASTRUCTURE (P2 — 1 day)

| # | Fix | Description |
|---|-----|-------------|
| E1 | Add GitHub Actions CI | `.github/workflows/ci.yml` |
| E2 | Add pre-commit hook for scan.sh | Auto-regenerate registry |
| E3 | Add frontend test setup (vitest) | `carbon-frontend/vitest.config.js` |

### WORKSTREAM F: DOCUMENTATION (P2 — 1 day)

| # | Fix | Description |
|---|-----|-------------|
| F1 | Rewrite `.ai-toolkit/project.config.md` | Carbon-specific, no stale rules |
| F2 | Create `.ai-toolkit/decisions/ADR-001-carbon-architecture.md` | Document the split |
| F3 | Update `.ai-toolkit/ONBOARDING.md` | Post-cleanup state |

---

## SECTION 6: CARBON DOMAIN APP COMPLETENESS CHECKLIST

This is the user's direct question: "what do we need for a complete end-to-end domain app carbon?"

### Backend (emissions app)

| Capability | Status | Notes |
|------------|--------|-------|
| Emission factor library | ✅ Complete | CRUD + categories + search + tags + GHG breakdown |
| Global Warming Potentials | ✅ Complete | Read-only, AR5+AR6, 20yr+100yr |
| Reporting periods | ✅ Complete | Status workflow, date validation, baseline flag |
| Calculation storage | ✅ Complete | Links to DataRow, Module, EmissionFactor |
| Calculation rules engine | ✅ Complete | Direct/unit-convert/formula, factor selector mapping |
| Dashboard API | ✅ Complete | Scope/category/monthly breakdown + DQ score |
| Yearly comparison API | ✅ Complete | YoY + baseline + SBTi trajectory |
| Report generation API | ✅ Complete | GHG Protocol structure, scope details |
| Calculate API | ✅ Complete | Trigger calculations |
| Console API | ✅ Complete | Aggregated landing data |
| Owner dashboard/summary/assets/activity | ✅ Complete | Org-unit scoped |
| My Data API | ✅ Complete | Owner workspace |
| SBTi target model | ❌ **MISSING** | Calculated on the fly — no persistence |
| Verification workflow | ❌ **MISSING** | Period has status but no verify/submit endpoints |
| Calculation audit trail | ⚠️ **PARTIAL** | Has calculated_by/at but no change history |
| Emission allocation | ❌ **MISSING** | No shared-source allocation |
| Batch calculation | ❌ **MISSING** | Calculate runs serially |
| DQ integration | ❌ **MISSING** | No auto-DQ on calculations |
| Report export (PDF/CSV) | ⚠️ **PARTIAL** | CSV download exists, no PDF |
| Services pattern | 🔴 **MISSING** | All logic in views.py |

### Frontend (Carbon app)

| Capability | Status | Notes |
|------------|--------|-------|
| Console/overview page | ✅ Complete | CarbonConsolePage |
| My Data entry page | ✅ Complete | MyDataPage with EntityDetailShell |
| Module workspace page | ✅ Complete | ModuleWorkspacePage |
| Analytics/trends page | ❌ **MISSING** | API exists, page doesn't |
| Report viewer page | ❌ **MISSING** | API exists, page doesn't |
| Targets page | ❌ **MISSING** | No model, no page |
| Factor management page | ❌ **MISSING** | API exists (ViewSet), page doesn't |
| Rule management page | ❌ **MISSING** | API exists (ViewSet), page doesn't |
| Period management page | ❌ **MISSING** | API exists (ViewSet), page doesn't |
| Verification page | ❌ **MISSING** | No API, no page |
| App manifest | ✅ Complete | apps/carbon/manifest.js |
| Sidebar navigation | ✅ Complete | ShellSidebar reads manifest |
| API client modules | ✅ Complete | emissions.js + emissions-extended.js |

---

## SECTION 7: SUMMARY — WHAT YOU NEED

### Immediate (this week)
1. **Extract emissions business logic into services.py** — this is the #1 architectural debt
2. **Fix project.config.md** — remove all gigacast rules, fix all stale paths
3. **Remove stale AI references** — config.js routes + aiCopilot.js
4. **Fix 20 hardcoded hex colors + 10 MUI v6 Grid violations**

### Short-term (next 2 weeks)
5. **Build 5 missing frontend pages** (Analytics, Report Viewer, Targets, Factors, Periods)
6. **Build SBTi Target model + API**
7. **Build verification workflow**
8. **Add tests for emissions views** (15% coverage is dangerous)

### Medium-term (next month)
9. **Add services to remaining 8 apps** that lack them
10. **Add CI/CD pipeline**
11. **Add frontend test suite (vitest)**
12. **Build emission allocation + batch calculation**

### Architecture Decision Required
> **Should the Carbon domain app continue as a `frontend app` (manifest + pages) using the shared `emissions` Django app, or should it become a fully separate `carbon_app` with its own models/views?**
>
> Current architecture: ✅ Frontend app pattern (manifest.js declares the app, pages live in `pages/carbon/`, API is shared `emissions` app)
>
> Recommendation: Keep current pattern. The `emissions` Django app IS the carbon backend. The `carbon` frontend app IS the carbon UI. They're two halves of one domain app. Don't split further — consolidate.

---

**Audit completed by**: Master Architect (DeepSeek V4 Pro)  
**Next step**: Begin Workstream A1: Fix `project.config.md`
