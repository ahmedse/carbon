# TASK P12 — Performance Audit & Optimization

**Date:** 2026-08-02  
**Status:** ⬜ SPEC — pending worker assignment  
**Depends on:** P10 (Web Robustness) ✅, P11 (RBAC API) ✅, P13 (Error Handling) ✅  

---

## Context

P10-P13 are complete. Platform works correctly but has NOT been audited for speed. QA plan targets:

| Metric | Target | Current |
|--------|--------|---------|
| API p95 latency | < 200ms | Unknown (no profiling) |
| Page LCP | < 2.5s | Unknown (no Lighthouse) |
| N+1 queries | 0 detected | Unknown (no audit) |
| Frontend bundle | Code-split by route | **2.0 MB single chunk** (zero code-splitting) |
| Backend query optimization | select_related on all FK traversal | Mixed — some done, DQ/MDM gaps |

---

## Architecture Notes (MUST READ)

### What EXISTS (do NOT redo)
- **3 performance tests** in `backend/core/tests/test_performance.py`: N+1 check, reference set speed, DB index check. All pass.
- **3 performance index migrations** already applied: `catalog/0004_add_performance_indices.py`, `dq/0003_add_performance_indices.py`, `mdm/0005_add_performance_indices.py`.
- **select_related already applied** in: emissions/views.py (Calculation, VerificationRecord, CalculationAudit), catalog/views.py (AssetProfile), connections/views.py, dataschema/views.py (TableRelation), importexport/views.py, accounts/views.py (ScopedRole, User), mdm/views.py (ReferenceSet).
- **Suspense wrapper exists** in App.jsx but wraps nothing lazy-loaded — zero effect.
- **apiFetch** handles JWT refresh. useEnabledApps was recently fixed (was raw fetch → 401).

### What's MISSING
1. **DQ app**: FieldProfileViewSet, TableProfileViewSet, DQRuleViewSet, DQResultViewSet — NO select_related/prefetch_related on get_queryset()
2. **MDM app**: OrgUnitViewSet, FieldOptionsView — need auditing
3. **Frontend**: 2.0 MB single JS chunk — ALL 76 page components eagerly imported. No `React.lazy()`, no `manualChunks`.
4. **No profiling baseline**: No django-silk, no middleware timing, no Lighthouse report, no p95 latency measurement.

---

## G1 — Backend: N+1 Query Audit & Fix

### Objective
Eliminate N+1 queries across ALL ViewSets. Every `get_queryset()` that returns model instances with FK relationships must have appropriate `select_related`/`prefetch_related`.

### Scope
- **DQ app** (priority — 4 ViewSets without optimization):
  - `FieldProfileViewSet`: needs `.select_related('data_field__data_table__module')`
  - `TableProfileViewSet`: needs `.select_related('data_table__module')`
  - `DQRuleViewSet`: needs `.select_related('data_field__data_table', 'data_table__module', 'created_by')`
  - `DQResultViewSet`: needs `.select_related('rule__data_table', 'data_field')`
- **MDM app** (2 ViewSets):
  - `OrgUnitViewSet`: audit get_queryset(), add select_related if missing
  - `FieldOptionsView`: audit get_queryset()
- **Catalog app**: `AssetProfileViewSet` already has select_related — verify in code, add `prefetch_related('tags')` if not present
- **Accounts app**: `UserViewSet` uses `User.objects.all()` (Django User model) — check if serializer hits groups/scoped_roles FK in loops
- **dataschema**: `DataTableSerializer`/`DataFieldSerializer` — check if they hit `module` FK in loops

### Gate
- Write `test_n_plus_one_<viewset>.py` tests with `CaptureQueriesContext` that fail if query count exceeds expected (1 base + N for M2M if prefetched)
- `pytest backend/ --no-header | tail -3` — all tests pass
- `python manage.py check` + `makemigrations --check` clean

### DO NOT
- Change serializer logic or add new fields
- Add migration files (this is query optimization, not schema changes)
- Touch emissions app (already optimized in earlier phases)
- Change permission classes or business logic

---

## G2 — Backend: Profiling & Slow Endpoint Identification

### Objective
Install django-silk, profile the top 15 most-used API endpoints, identify any >200ms p95 endpoints, report findings.

### Scope
- Install `django-silk` (add to requirements.txt, wire in settings.py INSTALLED_APPS + MIDDLEWARE)
- Run the seed (`python seed_all.py`) to ensure realistic data volume (237 calculations, 201 rows, 23 tables)
- Hit each endpoint 10x via script or pytest, collect p95 timings
- Endpoints to profile (top 15):
  1. `GET /carbon-api/emissions/dashboard/` (aggregations, most complex)
  2. `GET /carbon-api/emissions/calculations/` (list with select_related)
  3. `GET /carbon-api/catalog/assets/` (list with FK traversal)
  4. `GET /carbon-api/accounts/users/` (user list)
  5. `GET /carbon-api/accounts/scoped-roles/` (RBAC list)
  6. `GET /carbon-api/accounts/me/context/` (auth context — hits on every page load)
  7. `GET /carbon-api/dq/rules/` (DQ rules list)
  8. `GET /carbon-api/dq/results/` (DQ results)
  9. `GET /carbon-api/mdm/org-units/` (org tree)
  10. `GET /carbon-api/mdm/reference-sets/` (reference data)
  11. `GET /carbon-api/dataschema/tables/` (table list)
  12. `GET /carbon-api/dataschema/fields/` (field list)
  13. `GET /carbon-api/emissions/targets/` (SBTi targets)
  14. `GET /carbon-api/catalog/governance-policies/` (policies)
  15. `GET /carbon-api/accounts/audit-log/` (audit trail)

### Gate
- Report file: `TASK-RESULTS-P12-PROFILE.md` with table: endpoint | avg ms | p95 ms | query count | notes
- django-silk UI accessible at `/silk/` (or configured path)
- No permanent code changes beyond adding silk to requirements + settings

### DO NOT
- Keep django-silk enabled in production settings (dev only)
- Optimize anything yet — this is measurement/report only (G3 does optimization)

---

## G3 — Frontend: Code Splitting & Bundle Optimization

### Objective
Reduce initial JS bundle from 2.0 MB single chunk to <500 KB initial load with route-based code splitting.

### Current State
- **App.jsx**: 76 eager `import` statements → everything in one `index-*.js` chunk (2.0 MB)
- **Suspense exists** but wraps zero lazy-loaded components — dead wrapper
- **Zero `React.lazy()` calls** anywhere in codebase
- Vite chunk size warning present every build: "Some chunks are larger than 500 kB"

### Scope

#### 3a: Route-level code splitting (MANDATORY)
Convert all route-level page imports to `React.lazy()`:
```js
// Before
import EmissionsDashboard from "./pages/EmissionsDashboard";
// After
const EmissionsDashboard = React.lazy(() => import("./pages/EmissionsDashboard"));
```

Groups to lazy-load (by route namespace):
- `/carbon/*` — 16 pages (largest group)
- `/catalog/*` — 25+ pages
- `/admin/*` — 11 pages
- `/emissions/*` — 2 pages (legacy)
- `/data-owner/*` — 2 pages
- Misc: Help, Feedback, Settings, DataHubHome, ModuleLandingPage, ScopeInfoPage, NotFound

**Keep as eager** (always needed on first paint): Login, Shell, Layout, PlatformHome, ErrorBoundary, LoadingSpinner, AdminRoute, CatalogRoute, RequireAuth, RequireContext, RoleAwareLanding

#### 3b: MUI path imports
Check that MUI imports use path imports (not barrel), e.g.:
```js
// Good
import Button from "@mui/material/Button";
// Bad
import { Button } from "@mui/material";
```
Do a grep audit — fix any barrel imports found.

#### 3c: Manual chunks config (OPTIONAL — if needed after lazy loading)
If single chunk still >500 KB after lazy loading, configure `vite.config.js`:
```js
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        'mui': ['@mui/material', '@mui/icons-material', '@mui/x-date-pickers'],
        'vendor': ['react', 'react-dom', 'react-router-dom'],
      }
    }
  }
}
```

### Gate
- `npm run build` passes
- Output no longer shows "Some chunks are larger than 500 kB" warning
- At least 5 separate JS chunks in `dist/assets/` (not 1 giant index chunk)
- `npm run lint` — 0 new errors (baseline: 6 pre-existing in api.js)
- `npx vitest run` — all 8 tests pass
- Browser smoke test: login, navigate 3+ routes, confirm no white flash or ChunkLoadError

### DO NOT
- Remove any page or route
- Change the App.jsx route tree structure
- Remove or rewrite the Suspense wrapper (it's correctly positioned already)
- Touch api.js, apiFetch, or any API layer
- Add new dependencies (no @loadable/component — use React.lazy)

---

## G4 — Frontend: Lighthouse Audit

### Objective
Run Lighthouse on the 5 most important pages, report scores and actionable items.

### Pages to audit
1. `/login` — first paint
2. `/` — PlatformHome (app portal)
3. `/carbon/dashboard` — EmissionsDashboard (heaviest data page)
4. `/catalog` — CatalogHome
5. `/admin/users` — Admin CRUD page

### Metrics to report
Per page: Performance score | LCP (s) | TBT (ms) | CLS | SI (s)

### Tool
Use Chrome DevTools Lighthouse tab (or `npx lighthouse http://localhost:5179/login --view` if CLI installed).

### Gate
- Report file: `TASK-RESULTS-P12-LIGHTHOUSE.md` with full table + top 3 recommendations per page

---

## G5 — Verification & Gates

### All Gates (MUST PASS)
```bash
# Backend
cd backend && python manage.py check            # ✅ 0 errors (urls.W005 pre-existing)
cd backend && python manage.py makemigrations --check  # ✅ No changes
cd backend && python -m pytest                  # ✅ all pass (310+ now)

# Frontend
cd carbon-frontend && npm run build             # ✅ no >500KB warning
cd carbon-frontend && npm run lint              # ✅ 0 new errors (6 pre-existing ok)
cd carbon-frontend && npx vitest run            # ✅ 8/8 pass
```

### Timing baseline (record BEFORE and AFTER)
- Backend: `time curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8009/carbon-api/emissions/dashboard/`
- Frontend: Lighthouse Performance score for `/carbon/dashboard`

---

## Files Expected to Change

### Backend (G1 + G2)
- `backend/dq/views.py` — add select_related to 4 ViewSets
- `backend/mdm/views.py` — audit + add select_related (if missing)
- `backend/requirements.txt` — `+django-silk==5.3.2`
- `backend/config/settings.py` — silk INSTALLED_APPS + MIDDLEWARE (dev conditional)
- `backend/core/tests/test_performance.py` — expand with N+1 tests per ViewSet

### Frontend (G3)
- `carbon-frontend/src/App.jsx` — convert ~60 imports to React.lazy
- `carbon-frontend/vite.config.js` — possibly add manualChunks

### Reports (G2 + G4)
- `TASK-RESULTS-P12-PROFILE.md` (new)
- `TASK-RESULTS-P12-LIGHTHOUSE.md` (new)

---

## Worker Split

This task splits naturally into 2 workers:
- **Backend worker**: G1 (N+1 audit) + G2 (silk profiling) + G5 (gates)
- **Frontend worker**: G3 (code splitting) + G4 (Lighthouse) + G5 (gates)

Backend worker has MORE work (4 ViewSets to fix + silk setup + 15-endpoint profile).
Frontend worker's G3 is high-impact (code splitting) but fewer distinct files.

---

## Success Criteria

1. **0 N+1 queries** across all ViewSets (verified by CaptureQueriesContext tests)
2. **Top 15 endpoints profiled** with p95 timings documented
3. **Build < 500 KB initial chunk** (code-split working)
4. **Lighthouse Performance > 70** on all 5 key pages
5. **All gates pass** — backend + frontend
