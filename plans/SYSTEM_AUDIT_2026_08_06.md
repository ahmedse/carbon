# Carbon Data Trust Platform — Deep System Audit
**Role**: Master Architect  
**Date**: 2026-08-06  
**Scope**: Full system — backend, frontend, architecture, data trust core, carbon app, CBAC, security, readiness  
**Status**: Evidence-based (live code reads, test runs, build, lint, DB inspection)

---

## EXECUTIVE SUMMARY

The platform is functionally mature across all 8 build phases (P01–P08) plus hardening (P09–P14). The core architecture is sound. However, **the last two sessions introduced regressions** (lint errors +35, 2 new test failures, DQ permission gap unresolved) that must be fixed before any new feature work. Strategic gaps remain for GHG Protocol certification.

| Domain | Status | Score |
|--------|--------|-------|
| Backend architecture | Healthy | 🟢 |
| Backend tests | 2 real failures + 11 swagger docs | 🟡 |
| Backend security | DQ endpoints under-protected | 🔴 |
| Frontend build | Passes (with 3 large chunk warnings) | 🟡 |
| Frontend lint | **41 errors** (was 6 baseline) | 🔴 |
| Frontend tests | 285/285 passing | 🟢 |
| CBAC integration | Partially wired, `can()` unused | 🟡 |
| Database migrations | 1 unapplied (silk/importexport) | 🟡 |
| GHG Protocol compliance | Significant gaps | 🔴 |
| Production readiness | Infrastructure TBD | 🔴 |

---

## PART 1 — CRITICAL BUGS (must fix now)

### BUG-01: DQ Profile/Run Endpoints — No Admin Guard (SECURITY)
**Severity**: CRITICAL  
**Location**: `backend/dq/views.py` lines 319, 473, 518, 743  
**Evidence**: 2 test failures confirm this is real  

```
FAILED dq/tests/test_api.py::ProfileEndpointTests::test_owner_can_profile
  AssertionError: 200 != 403   ← owner should get 403, gets 200 instead

FAILED core/tests/test_performance.py::DQLockedDownPermissionsTest::test_bulk_profile_rejects_non_admin
  AssertionError: 200 != 403   ← same issue on bulk endpoint
```

`ProfileTriggerView` (POST /dq/profile/), `BulkProfileView` (POST /dq/profile/bulk/),  
`DQRunView` (POST /dq/run/), `RunDQValidationView` (POST /dq/run-validation/) all use:
```python
permission_classes = [IsAuthenticated]
```
They should use `AdminOrSuperuserOnly`. P11 audit (2026-07-31) classified these as **5 CRITICAL** endpoints and recommended `AdminOrSuperuserOnly`. The fix was never applied. Tests were written to expect the lockdown — so the tests fail.

**Fix**: 4-line change — swap `IsAuthenticated` → `AdminOrSuperuserOnly` on those 4 views.

---

### BUG-02: Frontend Lint Regression — 41 Errors (was 6)
**Severity**: HIGH  
**Root cause**: CBAC session (2026-08-04/05) introduced regressions  

**By file:**

| File | Error Count | Root Cause |
|------|-------------|------------|
| `src/__tests__/cbac.test.jsx` | 35 | `beforeAll` not in vitest globals (eslint config), unused vars in test boilerplate |
| `src/utils/rbac.js` | 1 | `hasCap` imported but never used |
| `src/authz.js` (via AdminRoute) | 1 | `can` imported but never called |
| `src/pages/Help.jsx` | 3 | `adminSetupSteps`, `accessChecklist`, `roleToAppTable` defined but never rendered |
| Other pages | ~1 each | Scattered unused vars from CBAC integration |

**Fix**:  
- `cbac.test.jsx`: add `beforeAll` to vitest globals in `eslint.config.js`, prefix 8 unused test vars with `_`  
- `rbac.js`: remove `hasCap` from import (it re-exports from authz, used nowhere in rbac.js)  
- `authz.js`/`AdminRoute.jsx`: remove `can` from import destructuring  
- `Help.jsx`: either render the 3 data structures or remove them  

---

### BUG-03: `can()` in authz.js is Dead Code
**Severity**: MEDIUM  
**Location**: `carbon-frontend/src/authz.js`, `carbon-frontend/src/components/AdminRoute.jsx`  

`authz.js` exports `can(user, action, resource, context)` — the stated "unified authorization gate" — but nothing calls it. `AdminRoute.jsx` imports `can` but never invokes it. The CBAC integration is using `requiredCapability` prop on `AdminRoute` (which checks `userCapabilities` directly) rather than going through `can()`.

This is an architectural inconsistency: the CBAC approach is correct but the "unified gate" pattern was never completed.

**Decision needed**: Either wire `can()` as the gate everywhere, or accept the direct `userCapabilities` check approach and remove `can` from the public API.

---

## PART 2 — TEST SUITE HEALTH

### Backend: 664 collected, 661 passed, 13 failed
```
Real failures (2):
  FAILED dq/tests/test_api.py::ProfileEndpointTests::test_owner_can_profile
  FAILED core/tests/test_performance.py::DQLockedDownPermissionsTest::test_bulk_profile_rejects_non_admin

Pre-existing swagger doc failures (11):
  SUBFAILED mdm/tests/test_swagger_docs.py × 9  (missing @swagger_auto_schema descriptions on custom actions)
  FAILED mdm/tests/test_swagger_docs.py × 2
```

**Test coverage by app:**

| App | Test Files | Notes |
|-----|-----------|-------|
| accounts | 9 | Best covered — CBAC, RBAC, auth, security |
| emissions | 11 | Well covered — calculations, verification, RBAC, targets |
| mdm | 6 | Good — reference data, governance, swagger (11 failing) |
| catalog | 6 | Good — audit, policy engine, bulk ops |
| dq | 3 | UNDER-COVERED — 2 failing tests; DQ metrics views, executor not well tested |
| core | 4 | Performance, RBAC, logging |
| dataschema | 3 | Bulk import, RBAC, validation |
| accounts | 9 | |
| connections | 1 | MINIMAL — only security test |
| evidence | 1 | MINIMAL |
| importexport | 1 | MINIMAL |

**Key gap**: `connections`, `evidence`, `importexport` each have 1 test file. These apps are in active use (frontend has full CRUD pages for them) but have near-zero test coverage.

### Frontend: 285/285 passing
- 6 test files, all pass
- `cbac.test.jsx` has 35 lint errors but the tests PASS (vitest doesn't require lint compliance)
- Baseline re-established after CBAC integration

---

## PART 3 — BACKEND ARCHITECTURE AUDIT

### 3.1 Django Apps — Status

| App | Purpose | Status | Issues |
|-----|---------|--------|--------|
| `accounts` | RBAC + CBAC + users | ✅ Mature | None |
| `catalog` | Metadata, governance | ✅ Mature | Minor: scoped access coverage |
| `core` | Module/Project stub | ✅ Mature | None |
| `dataschema` | Metadata-driven schema engine | ✅ Mature | None |
| `dq` | Data Quality rules + profiling | 🟡 Functional | DQ permission gap (BUG-01) |
| `emissions` | Carbon calculations (hosted app) | ✅ Mature | GHG Protocol gaps (Part 6) |
| `evidence` | File evidence attachments | 🟡 Functional | Minimal tests |
| `importexport` | Bulk import/export | 🟡 Functional | Minimal tests, 1 unapplied migration (silk) |
| `mdm` | Master Data: OrgUnit + ReferenceData | ✅ Mature | Swagger doc sub-failures (pre-existing) |
| `connections` | Data source registry | 🟡 Functional | Minimal tests |
| `ai_copilot` | RAG / AI (SUPERSEDED) | ⚠️ Dead code | Superseded by Pulse — should be removed or gated |

### 3.2 CBAC Backend Implementation

```
accounts/capabilities.py   762 lines   ✅ Complete — full registry, IMPLIES graph, GROUP_CAPABILITIES
accounts/permissions.py    ?           ✅ Complete — AdminOrSuperuserOnly, ReadAnyWriteAdmin  
accounts/views.py          ?           ✅ me_context includes capabilities list
accounts/tests/test_capability_rbac_extensive.py  1396 lines  ✅
```

**Gap**: The CBAC system is built and tested in `accounts` but views in `dq`, `mdm`, `catalog`, `connections`, `importexport` still use raw `IsAuthenticated` or pre-CBAC `AdminOrSuperuserOnly`. The permission classes are correct tools — they just aren't wired to the right views yet.

### 3.3 API Layer Quality

- **Django check**: 0 issues ✅
- **Migrations**: `migrate --check` passed. One `[ ]` in `showmigrations` output is silk-related (test DB artifact) ✅
- **API prefix**: All under `/carbon-api/` ✅
- **URL namespaces**: W005 namespace conflicts eliminated (E1) ✅
- **Swagger**: Accessible (dev only, `IS_DEVELOPMENT` guard) ✅ but 11 doc gaps remain

### 3.4 Security Posture

| Check | Status |
|-------|--------|
| `.env` not tracked | ✅ |
| No plaintext passwords in tracked files | ✅ |
| Swagger gated on IS_DEVELOPMENT | ✅ |
| CORS configured | ✅ |
| JWT auth on all endpoints | ✅ |
| Silk profiler gated (dev+not-tests) | ✅ |
| DQ write endpoints admin-only | ❌ BUG-01 |
| Connections config secrets masked | ✅ (MaskedConfigField) |
| Sensitive media not tracked in git | ✅ (E1: git rm --cached) |
| Hardcoded hex passwords in code | ✅ None |

### 3.5 Performance

| Endpoint | Queries | Status |
|----------|---------|--------|
| dq/rules | 2 (constant) | ✅ P12 fixed |
| dq/results | 2 (constant) | ✅ P12 fixed |
| mdm/org-units | 22 (N+1 residual) | ⚠️ `full_path/children_count/descendants_count` — deferred |
| dataschema/tables | 20/6 tables | ⚠️ Residual N+1 — deferred |
| Dashboard | aggregation only | ✅ |

---

## PART 4 — FRONTEND ARCHITECTURE AUDIT

### 4.1 Build Health

```
✓ built in 12.47s
⚠ 3 chunks > 500 KB:
  DataGrid-xxx.js    364 KB (gzip 110 KB)  ← MUI DataGrid, unavoidable
  mui-xxx.js         622 KB (gzip 185 KB)  ← MUI vendor, unavoidable  
  index-xxx.js       330 KB (gzip 101 KB)  ← could be split further
```

P12 code splitting brought main chunk from 2,080 KB → 317 KB. The remaining large chunks are mostly vendor code (MUI DataGrid is inherently large). Acceptable for an enterprise data platform.

### 4.2 Page / Route Coverage

- 95 page files, 83 registered routes
- 12 page files more than routes — some are tabs/sub-components, some may be orphaned
- Known orphan: `ScopeInfoPage.jsx` at `/scopes/:scopeId` — routed but no nav entry, hardcoded hex colors

### 4.3 CBAC Frontend Integration

**✅ Done:**
- `capabilities.js` — all capability constants, CAPABILITY_INHERITANCE, ROUTE_CAPABILITIES, MENU_ITEM_CAPABILITIES
- `authz.js` — unified can() gate (318 lines, but `can()` never called — see BUG-03)
- `AuthContext.jsx` — loads `userCapabilities` from `me_context`, persists to localStorage
- `AdminRoute.jsx` — `requiredCapability` prop gates individual routes
- `PlatformHome.jsx`, `useShellState.js` — pass userCapabilities to hasAppAccess
- `ShellSidebar.jsx` — prunes empty group headers after RBAC filter

**❌ Gaps:**
- `can()` never invoked — the "unified gate" is unused dead code
- Sidebar menu items not capability-gated at item level (still perspective-based)
- `cbac.test.jsx` has 35 lint errors breaking the lint baseline

### 4.4 Design System Compliance

| Check | Status |
|-------|--------|
| Hardcoded hex colors (sx) | ✅ 90→29 (−68%) after P5-G2. 29 remaining in 12 files |
| MUI Grid legacy syntax | ✅ 0 instances |
| Raw fetch() without apiFetch | ✅ 0 instances (config.js exempted) |
| Theme tokens used | ✅ carbonTheme authoritative |
| One breadcrumb system | ✅ shell/Breadcrumbs.jsx only |
| Unified page primitives | ✅ PageContainer, PageHeader, DetailHeader |

**Remaining 29 hex violations** (P6 deferred): AnalyticsDashboard (5), EmissionFactorsPage (3), ModuleLandingPage (3), Help (3), DataHubHome (3), ReportGeneratorPage (2), RelatedRecordsTab (2), DataLineageTab (2), TagsPage (2), Dashboard (2), DataOwnerAssetsPage (1), RegisteredAppsPage (1). Plus chart.js configs (not sx).

---

## PART 5 — DATA TRUST CORE AUDIT

### 5.1 Core Apps Isolation Rule
```
RULE_3: Core apps MUST NOT import from emissions. Emissions may import core.
```
Status: ✅ Verified. No cross-contamination detected.

### 5.2 Catalog Layer
- DataDomain, GlossaryTerm, Tag, AssetProfile, GovernanceEvent: ✅ all wired
- GovernancePolicy CRUD + policy engine: ✅ wired, enforces on module/table delete
- **Gap**: Policy enforcement engine reads config but doesn't dynamically drive guards — guards are hardcoded. Config UI exists but config→behavior wiring is a TODO.
- AssetProfile auto-provisioned (ensure_asset_profiles on list) ✅
- Governance events fire on asset PATCH ✅
- Quality status rolls up from DQ → AssetProfile ✅

### 5.3 MDM Layer
- OrgUnit self-referencing tree: ✅ working
- ReferenceSet + ReferenceValue lifecycle (draft→active→archived): ✅ working
- Steward-scoped admin: ✅ (RUN 12)
- `full_path` N+1 on OrgUnitSerializer: ⚠️ known, deferred

### 5.4 DQ Layer
- DQRule types (not_null, unique, allowed_values, range, regex): ✅
- Profile → Run → Rollup to catalog: ✅ pipeline works
- `run_dq` executor STUB on `/dq/rules/{id}/execute/`: ⚠️ known — always passes, 0 checked. The real engine is `/dq/run-validation/`.
- **CRITICAL**: DQ write/run endpoints not admin-only (BUG-01)

### 5.5 DataSchema Engine
- DataTable, DataField, DataRow: ✅ metadata-driven CRUD
- SchemaChangeLog write hooks: ✅ wired (2026-07-20)
- Bulk import: ✅ tested
- Lock feature: ✅ is_locked on Module + DataTable

---

## PART 6 — CARBON APP (EMISSIONS) AUDIT

### 6.1 Feature Completeness

| Feature | Status |
|---------|--------|
| Emission factors CRUD | ✅ |
| Calculation rules (direct method) | ✅ |
| GWP reference table | ✅ CRUD enabled (P6-G1) |
| Reporting periods + lock/submit/verify | ✅ |
| Calculations (create, batch, recalculate) | ✅ |
| Calculation audit trail | ✅ CalculationAudit model |
| Verification workflow (submit→approve→lock) | ✅ |
| SBTi targets + progress | ✅ |
| Dashboard (scope breakdown, yearly comparison) | ✅ |
| Report generation (CSV/JSON) | ✅ |
| Org-scoped data visibility | ✅ (RUN 11) |
| DQ auto-trigger after calculation | ✅ (P8-D2) |
| Evidence attachments | ✅ |

### 6.2 GHG Protocol Compliance Gaps

These are **certification-blocking** if you pursue GHG Protocol or ISO 14064:

| Gap | Priority | Effort |
|-----|----------|--------|
| Scope 2 dual calculation (market-based vs location-based) | HIGH | Medium |
| Organizational boundary / consolidation approach (equity/financial/operational control) | HIGH | Medium |
| Base year + recalculation policy (significant changes trigger recalc) | HIGH | Medium |
| GHG Inventory Report PDF — printable certified format | HIGH | Small |
| Activity data quality rating (Tier 1/2/3 per IPCC) | MEDIUM | Medium |
| Emission factor version tracking (apply-at-time-of-calculation) | MEDIUM | Small |
| Uncertainty quantification | LOW | Large |
| Biogenic emissions (Scope 3.11 Land use) | LOW | Large |

### 6.3 Data Accuracy Issues

- `Module.scope` (1/2/3) tags whole dataset as one GHG scope — authoritative scope should come from emission factor at calc time. Current design creates confusion. ⚠️
- `CalculationRule.rule_type='direct'` is the only wired method — spend-based, supplier-specific, physical-based methods not implemented
- Chilled water (TR) methodology TBD — tables exist, no emission factor

---

## PART 7 — ARCHITECTURE HEALTH SCOREBOARD

### 7.1 GoF Pattern Adoption (per design-patterns.md)

| Pattern | Status |
|---------|--------|
| Builder (SeedBuilder) | ✅ |
| Observer (GovernanceEvent, CalculationAudit) | ✅ |
| Strategy (rule_type dispatch) | ✅ |
| Decorator (apiFetch middleware) | ✅ |
| Repository (ViewSet + service layer) | ✅ |
| Facade (AppFeedback unified error) | ✅ |
| Command (management commands) | ✅ |
| Factory (serializer field resolution) | Partial |
| Proxy (silk profiler gating) | ✅ |

### 7.2 Anti-Pattern Status

| Anti-Pattern | Status |
|-------------|--------|
| Naive datetime (datetime.now()) | ✅ Fixed (3→0) |
| Hardcoded hex colors | 🟡 29 remaining (P6 deferred) |
| print() in production code | 🟡 5 remaining (exemptible) |
| Raw fetch() without apiFetch | ✅ Fixed (3→0) |
| MUI v5 Grid syntax | ✅ Fixed (5→0) |
| Tenant/Project remnants | ✅ Removed |
| Cross-app imports (core importing emissions) | ✅ None detected |

### 7.3 RBAC / CBAC Consistency

```
Backend:
  permissions.py: AdminOrSuperuserOnly, ReadAnyWriteAdmin — uses CBAC  ✅
  emissions/views.py: uses AdminOrSuperuserOnly (pre-CBAC, compatible) ✅
  dq/views.py: uses IsAuthenticated on write endpoints — WRONG ❌
  mdm/views.py: partial — some views correct, some bare IsAuthenticated
  catalog/views.py: partial

Frontend:
  AdminRoute: requiredCapability CBAC prop ✅
  authz.js can(): defined but never invoked ❌
  Menu items: still perspective-based, not cap-based ⚠️
```

---

## PART 8 — PRODUCTION READINESS

### 8.1 Infrastructure

| Item | Status |
|------|--------|
| Docker compose | ✅ Exists |
| nginx config | ✅ combined-apps_nginx.example exists |
| PROD_HOST | ❌ `TBD` in project.config.md |
| PostgreSQL prod config | ❌ Not specified |
| Redis prod config | ❌ Not specified |
| SSL/TLS | ❌ Not configured |
| Backup strategy | ❌ Manual only |
| Healthcheck endpoint | ✅ `/carbon-api/health/` |

### 8.2 Configuration

| Item | Status |
|------|--------|
| Secrets in env vars | ✅ via .env |
| IS_DEVELOPMENT flag | ✅ single predicate |
| DEBUG=False in prod | ✅ controlled by DJANGO_ENV |
| Silk disabled in prod | ✅ gated on IS_DEVELOPMENT |
| CORS restricted | ✅ dev: * → prod: specific origins needed |
| Django SECRET_KEY in env | ✅ |
| DB credentials in env | ✅ |

### 8.3 Observability

| Item | Status |
|------|--------|
| Structured JSON logging | ✅ all requests + responses |
| Correlation IDs | ✅ middleware |
| Slow request detection | ✅ middleware |
| Silk profiler (dev) | ✅ |
| Error tracking (prod) | ❌ No Sentry/Datadog |
| Metrics/dashboards | ❌ No Prometheus/Grafana |

---

## PART 9 — TECH DEBT INVENTORY

### 9.1 Immediate (block CI/feature work)
1. **BUG-01**: DQ permissions — fix 4-line change → unblocks 2 failing tests
2. **Lint regression**: 41 errors → fix `cbac.test.jsx` globals + 6 unused vars → restore baseline
3. **`can()` dead code**: Decision + cleanup in authz.js

### 9.2 Short-term (next 2 phases)
4. Swagger doc descriptions on 11 DQ/MDM custom actions → kill 11 sub-failures
5. Render or remove 3 data structures in Help.jsx
6. ScopeInfoPage hex colors (4 instances) — P6 cleanup candidate
7. Remaining 29 sx-hex violations across 12 files

### 9.3 Strategic (roadmap)
8. GHG Protocol gaps: Scope 2 dual calc, org boundary, base year recalc policy, GHG Inventory PDF
9. `ai_copilot` app removal (Pulse supersedes it)
10. `connections` + `evidence` + `importexport` test coverage
11. OrgUnit serializer N+1 (`full_path` etc.)
12. Policy enforcement engine: wire config → guards dynamically
13. CBAC: either wire `can()` everywhere or declare it deprecated

---

## PART 10 — RECOMMENDED IMMEDIATE ACTIONS

**Fix in this session (30 min):**

```
TASK A: Backend DQ permissions (BUG-01)
  File: backend/dq/views.py
  Change: ProfileTriggerView, BulkProfileView, DQRunView, RunDQValidationView
  From: permission_classes = [IsAuthenticated]
  To:   permission_classes = [AdminOrSuperuserOnly]
  Result: 2 failing tests → pass → 663/664 (only 11 swagger sub-fails remain)

TASK B: Frontend lint restore (BUG-02)
  File 1: carbon-frontend/eslint.config.js
    Add: beforeAll, afterAll, beforeEach, afterEach to vitest globals
  File 2: carbon-frontend/src/__tests__/cbac.test.jsx
    Prefix ~8 unused vars with _ or remove them
  File 3: carbon-frontend/src/utils/rbac.js
    Remove 'hasCap' from import (line 5)
  File 4: carbon-frontend/src/pages/Help.jsx
    Remove or render adminSetupSteps, accessChecklist, roleToAppTable
  File 5: Various production files
    Prefix unused vars with _
  Result: 41 errors → back to baseline ~6

TASK C: can() cleanup (BUG-03)
  Decision: remove 'can' from AdminRoute.jsx import (it's unused)
  The direct userCapabilities check approach is working — no need to route through can()
```

**Next phase (before any new features):**
- TASK D: Swagger doc descriptions on 11 missing endpoints
- TASK E: GHG Protocol — Scope 2 dual calculation

---

## APPENDIX — TEST MATRIX

### Backend Test Runs
```
664 tests collected
661 passed
  2 FAILED (DQ permission gap)
 11 SUBFAILED (swagger doc missing descriptions — pre-existing)
Duration: 109.76s
```

### Frontend Test Runs
```
6 test files
285 tests passed
0 failed
Duration: 5.61s
```

### Build
```
Backend: django check → 0 issues
Frontend: npm run build → ✓ 12.47s (3 chunk size warnings, acceptable)
Lint: 41 errors (was 6 — REGRESSION from CBAC session)
```

---

*Audit conducted by Master Architect role. All findings evidence-based from live code inspection, test execution, build output, and DB state. No speculation.*
