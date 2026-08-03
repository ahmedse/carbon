# Phase 4 — Frontend Health
# Master Architect → Frontend Worker (Kimi K3) | 2026-07-31
# Domain: frontend | Budget: ~25K tokens | 3 task groups (7 tasks)

---

## FRONTEND WORKER — Execute Phase 4: Frontend Health

Read this file completely before starting. 7 tasks across 3 groups. Domain: frontend only.

## FILES TO READ FIRST

- `src/hooks/useEnabledApps.js` — the ONLY existing hook; copy its caching + cancellation pattern
- `src/api/api.js` — apiFetch, token refresh, buildQuery patterns
- `src/api/emissions.js` — fetchEmissionsDashboard, fetchConsoleData API signatures
- `src/config.js` — API_ROUTES, API_BASE_URL
- `.ai-toolkit/shared/design-system.md` — token rules (Rule 1), data states (Rule 4)
- `.ai-toolkit/project.config.md` — HARD RULES, frontend stack specifics
- `src/pages/dashboards/AnalyticsDashboard.jsx` — study inline fetching pattern (799 lines)
- `src/pages/carbon/CarbonConsolePage.jsx` — study inline fetching (164 lines)
- `src/pages/carbon/MyDataPage.jsx` — study inline fetching (602 lines)
- `src/pages/data-owner/DataOwnerDashboardPage.jsx` — study inline fetching (370 lines)

---

## REALITY CHECK

- 83 page files with inline useState/useEffect/fetch patterns (~26K lines total)
- 1 existing hook: `useEnabledApps.js` (well-designed: module-level cachedPromise, cancellation flag)
- All pages are routed in App.jsx — no obviously dead pages
- Top 5 heaviest: AnalyticsDashboard (799), MDMPage (750), CalculationsPage (718), EmissionsDashboard (701), MyDataPage (602)

**Strategy**: Don't extract 83 hooks. Create 5 composable hooks pages can adopt incrementally.

---

## TASKS

### GROUP 1 — Extract Data-Fetching Hooks (5 new files)

---

**TASK 1.1 — Create `useApi.js` (generic GET hook)**

- CREATE `src/hooks/useApi.js`
- Signature: `useApi(fetchFn, deps)` where `fetchFn` returns a Promise
- Returns: `{ data, loading, error, refetch }`
- Pattern from `useEnabledApps.js`: `useRef` for cancellation, `useEffect` with cleanup
- Token: from `localStorage.getItem("access")`
- Auto-triggers on dependency change; `refetch()` forces re-fetch
- Verify: Node imports OK

---

**TASK 1.2 — Create `useEmissionsDashboard.js`**

- CREATE `src/hooks/useEmissionsDashboard.js`
- Wraps `fetchEmissionsDashboard` from `../api/emissions`
- Manages filter state: year, reporting_period_id, org_unit_id
- Signature: `useEmissionsDashboard(initialFilters?)`
- Returns: `{ data, loading, error, filters, setFilters, refetch }`
- Study AnalyticsDashboard.jsx for filter→fetch→data pipeline
- Verify: Node imports OK

---

**TASK 1.3 — Create `useCarbonConsole.js`**

- CREATE `src/hooks/useCarbonConsole.js`
- Wraps `fetchConsoleData` from `../api/emissions`
- Signature: `useCarbonConsole()`
- Returns: `{ data, loading, error, refetch }`
- Study CarbonConsolePage.jsx for exact API call and response shape
- Verify: Node imports OK

---

**TASK 1.4 — Create `useMyData.js`**

- CREATE `src/hooks/useMyData.js`
- Study MyDataPage.jsx (602 lines) for API functions called
- Wraps my-data API calls with filter state
- Returns: `{ data, loading, error, filters, setFilters, refetch }`
- Verify: Node imports OK

---

**TASK 1.5 — Create `useOwnerDashboard.js`**

- CREATE `src/hooks/useOwnerDashboard.js`
- Study DataOwnerDashboardPage.jsx (370 lines) for API functions called
- Wraps owner dashboard API calls
- Returns: `{ data, loading, error, refetch }`
- Verify: Node imports OK

---

### GROUP 2 — Audit Page Status (1 task)

---

**TASK 2.1 — Audit ScopeInfoPage.jsx routing**

- READ `src/pages/ScopeInfoPage.jsx`
- grep App.jsx for "ScopeInfoPage" — is it imported AND routed?
- Report findings: routed path or "NOT ROUTED — candidate for deletion"
- DO NOT DELETE — report only

---

### GROUP 3 — Count inline sx for P5 Planning (1 task)

---

**TASK 3.1 — Count raw sx usages**

- Run: `grep -rn "sx={{" src/ --include="*.jsx" | wc -l`
- Report the count for P5-G2 scoping

---

## DO NOT TOUCH

- **DO NOT edit any existing page file** — only create new hook files
- **DO NOT delete any pages** — audit only
- **DO NOT change API function signatures** — wrap, don't modify
- **DO NOT touch backend files**
- **DO NOT run `npm install`**

---

## GATES (run in order before reporting done)

```bash
# Gate 1 — Build must pass
cd carbon-frontend && npm run build 2>&1 | tail -5

# Gate 2 — All 5 hooks import cleanly
cd carbon-frontend && node --input-type=module -e "
  import { useApi } from './src/hooks/useApi.js';
  import { useEmissionsDashboard } from './src/hooks/useEmissionsDashboard.js';
  import { useCarbonConsole } from './src/hooks/useCarbonConsole.js';
  import { useMyData } from './src/hooks/useMyData.js';
  import { useOwnerDashboard } from './src/hooks/useOwnerDashboard.js';
  console.log('All 5 hooks import OK');
" 2>&1

# Gate 3 — Hook count: 1 existing + 5 new = 6
ls src/hooks/*.js | wc -l

# Gate 4 — Lint (if configured)
npm run lint 2>&1 | tail -5
```

---

## HARD RULES (from project.config.md)

1. **Tokens only** — `theme.palette.*`, `spacing()`. NEVER raw px/hex.
2. **4 data states** — every hook returns loading + error + data (design-system.md §4).
3. **Hooks return data, not JSX** — they're data hooks, not component hooks.
4. **NEVER run raw npm/vite** — use `./manage.sh start frontend` if you need dev server.

---

## REPORT BACK

Write `TASK-RESULTS-P4.md`:

```markdown
## [2026-07-31] Frontend Worker — Phase 4: Frontend Health

### Summary
N/N gates passed. X files created.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.1 | useApi.js | ✅/❌ | |
| 1.2 | useEmissionsDashboard.js | ✅/❌ | |
| 1.3 | useCarbonConsole.js | ✅/❌ | |
| 1.4 | useMyData.js | ✅/❌ | |
| 1.5 | useOwnerDashboard.js | ✅/❌ | |
| 2.1 | ScopeInfoPage audit | ✅/❌ | [routed/not routed] |
| 3.1 | Inline sx count | ✅/❌ | N occurrences |

### Files Created
| File | Lines | What |
|------|-------|------|

### Verification Output
[paste terminal output from all gates]

### Deviations / Issues
[...or NONE]
```
