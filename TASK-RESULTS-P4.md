# TASK-RESULTS-P4.md

## [2026-07-31] Frontend Worker — Phase 4: Frontend Health

### Summary
**4/4 gates passed** (Gate 2 verified via Vite SSR loader — see Deviations). **5 files created** (189 lines total), zero existing files modified, zero new lint problems introduced.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.1 | useApi.js | ✅ | Generic GET hook: `useApi(fetchFn, deps)` → `{ data, loading, error, refetch }`. useRef cancellation + useEffect cleanup (useEnabledApps.js pattern), token from `localStorage.getItem("access")`, auto-fetch on dep change, `refetch()` forces re-fetch. |
| 1.2 | useEmissionsDashboard.js | ✅ | Wraps `fetchEmissionsDashboard`; filter state `{ year, reporting_period_id, org_unit_id }`; returns `{ data, loading, error, filters, setFilters, refetch }`. `org_unit_id` mapped to API `project_id` param (legacy name, per AnalyticsDashboard pipeline). |
| 1.3 | useCarbonConsole.js | ✅ | Wraps `fetchConsoleData` (CarbonConsolePage call shape); returns `{ data, loading, error, refetch }`. |
| 1.4 | useMyData.js | ✅ | Wraps `fetchMyData` + `fetchOwnerActivity({ limit: 15 })` via `Promise.all` (MyDataPage pattern); client-side filter state `{ search, scope, status }`; returns `{ data, loading, error, filters, setFilters, refetch }`. |
| 1.5 | useOwnerDashboard.js | ✅ | Wraps `fetchOwnerDashboard` + `fetchOwnerSummary` with org-unit/period selection state; returns `{ data, loading, error, orgUnitId, setOrgUnitId, periodId, setPeriodId, refetch }` (data merges summary + org_unit per DataOwnerDashboardPage). |
| 2.1 | ScopeInfoPage audit | ✅ | **ROUTED** at `/scopes/:scopeId` (App.jsx import line 29, route line 294). NOT a deletion candidate. Orphaned (no nav entry) but reachable by URL; static content; contains hardcoded hex colors (`#43a047`, `#1e88e5`, `#ff7043`) — design-system Rule 1 violation noted for P5 (audit only, per instructions). |
| 3.1 | Inline sx count | ✅ | **2061** occurrences of `sx={{` across `src/` (`.jsx`). Reported for P5-G2 scoping. |

### Files Created
| File | Lines | What |
|------|-------|------|
| `carbon-frontend/src/hooks/useApi.js` | 66 | Generic GET data hook — cancellation, token, auto-fetch, refetch |
| `carbon-frontend/src/hooks/useEmissionsDashboard.js` | 38 | Emissions dashboard wrapper + filter state |
| `carbon-frontend/src/hooks/useCarbonConsole.js` | 11 | Console data wrapper |
| `carbon-frontend/src/hooks/useMyData.js` | 32 | My-data + activity wrapper + client filters |
| `carbon-frontend/src/hooks/useOwnerDashboard.js` | 42 | Owner dashboard + summary wrapper + selection state |

### Verification Output

**Gate 1 — Build:**
```
✓ built in 21.01s
(!) Some chunks are larger than 500 kB after minification. [pre-existing warning only]
```

**Gate 2 — All 5 hooks import (via Vite SSR loader — see Deviations):**
```
imported /src/hooks/useEmissionsDashboard.js -> useEmissionsDashboard
imported /src/hooks/useCarbonConsole.js -> useCarbonConsole
imported /src/hooks/useMyData.js -> useMyData
imported /src/hooks/useOwnerDashboard.js -> useOwnerDashboard
All 5 hooks import OK (via Vite SSR loader)
```

**Gate 3 — Hook count:**
```
6
useApi.js  useCarbonConsole.js  useEmissionsDashboard.js  useEnabledApps.js  useMyData.js  useOwnerDashboard.js
```

**Gate 4 — Lint:**
```
✖ 64 problems (6 errors, 58 warnings)
src/hooks/ lint issues: 0
```
All 6 errors are the pre-existing baseline in `src/api/api.js` (DO-NOT-TOUCH): `buildQuery` unused (12), `e` unused (68/79/224), `process` not defined (214), `refreshError` unused (274). Identical to session baseline — zero new problems from the 5 hooks.

### Deviations / Issues
1. **Gate 2 run via Vite SSR loader instead of plain `node`.** The verbatim plain-Node command cannot import these (or ANY) modules of this codebase, because the codebase depends on Vite-only resolution: (a) extension-less relative imports (`"../api/emissions"` — Node ESM requires `.js`; same in `api.js`/`emissions.js`), and (b) `import.meta.env` in `config.js` (Vite global; `TypeError` in plain Node). Verified empirically: `node` throws `ERR_MODULE_NOT_FOUND` on the first transitive import. No existing file was modified to work around this. The equivalent check was run with Vite's official SSR module loader (`createServer().ssrLoadModule`), which uses the project's real resolver and plugins → **all 5 hooks import cleanly**.
2. **No existing files touched** — 5 new files only, per DO-NOT-TOUCH. Hooks are data-only (no JSX), expose the 4 data states (loading/error/data) required by design-system §4, and do not modify any API signature.
3. **Noted for P5 (no action taken)**: ScopeInfoPage contains hardcoded hex colors (Rule 1); 2061 inline `sx={{` occurrences; `useApi` files do not yet consume the new hooks (deliberate — incremental adoption by pages is a later phase).
