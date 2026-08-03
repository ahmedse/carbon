# TASK P12 — Frontend: Code Splitting + Lighthouse Audit

**Role:** `frontend-worker`
**Date:** 2026-08-02
**Depends on:** P12 spec (`TASK-CARBON-P12-PERFORMANCE.md`)
**Covers:** G3 (code splitting) + G4 (Lighthouse audit) + G5 (verification gates)

---

## Activation Protocol

1. Read `.ai-toolkit/project.config.md` — FRONTEND_DIR, FRONTEND_LINT_CMD, FRONTEND_BUILD_CMD, OPS_SCRIPT, HARD RULES
2. Read `.ai-toolkit/shared/base-rules.md` — ops script, verification loop, handoff format
3. Read `.ai-toolkit/shared/design-system.md` — the enterprise UI/UX constitution
4. Read `.ai-toolkit/shared/api-contract.md` — apiFetch usage
5. Run `./.ai-toolkit/scripts/scan.sh` to refresh registry
6. Read "Files to Read First" below
7. Run `npm run build` to confirm current state (expect 2.0 MB single chunk)
8. Confirm: "Ready as Frontend Worker. Baseline build: [size], lint: [N errors]"

---

## Files to Read First

- `carbon-frontend/src/App.jsx` — ALL 76 imports, route tree, Suspense wrapper
- `carbon-frontend/vite.config.js` — current build config (check for existing manualChunks)
- `carbon-frontend/package.json` — deps (React 18, MUI 7.1.0, react-router-dom v6)
- `carbon-frontend/src/components/` — grep for any existing `React.lazy` usage
- `carbon-frontend/eslint.config.js` — lint rules

---

## G3 — Code Splitting & Bundle Optimization

### Current State
- **App.jsx**: 76 eager `import` statements at top of file → ALL pages in one `index-*.js` chunk
- **Bundle**: ~2.0 MB single chunk. Vite warns every build: "Some chunks are larger than 500 kB"
- **Suspense**: Wraps the route tree but wraps zero lazy-loaded components — dead wrapper
- **Zero `React.lazy()` calls** anywhere in codebase

### Target
- Initial JS chunk < 500 KB
- At least 5 separate chunks in `dist/assets/`
- No "chunks are larger than 500 kB" warning

### Step 1: Route-level code splitting (PRIMARY)

Convert ALL route-level page imports to `React.lazy()`. Pattern:

```jsx
// BEFORE (eager — blocks initial load)
import EmissionsDashboard from "./pages/EmissionsDashboard";
import CatalogHome from "./pages/CatalogHome";

// AFTER (lazy — loaded on demand, Suspense handles loading state)
const EmissionsDashboard = React.lazy(() => import("./pages/EmissionsDashboard"));
const CatalogHome = React.lazy(() => import("./pages/CatalogHome"));
```

**Pages to lazy-load** (grouped by route namespace):

| Route namespace | Pages | Count |
|-----------------|-------|-------|
| `/carbon/*` | All pages under `/carbon/` routes | ~16 |
| `/catalog/*` | All pages under catalog routes | ~25 |
| `/admin/*` | All admin pages (users, scoped-roles, etc.) | ~11 |
| `/emissions/*` | Legacy emissions pages | ~2 |
| `/data-owner/*` | Data owner pages | ~2 |
| Misc | Help, Feedback, Settings, DataHubHome, ModuleLandingPage, ScopeInfoPage, NotFound | ~7 |

**Keep as EAGER imports** (needed on first paint — do NOT lazy-load):
- `Login`
- `Shell` / `ShellSidebar` / `ShellBreadcrumb`
- `Layout` components
- `PlatformHome`
- `ErrorBoundary`
- `LoadingSpinner`
- `AdminRoute` / `CatalogRoute` / `RequireAuth` / `RequireContext`
- `RoleAwareLanding`
- `apiFetch` / `api.js` / `config.js`

### Step 2: MUI path import audit

Run this audit:
```bash
grep -rn "from '@mui/material'" carbon-frontend/src/ --include="*.jsx" --include="*.js" | grep -v "/\*"
```

If any files use barrel imports like `import { Button, TextField } from "@mui/material"`, convert to path imports:
```jsx
// BAD — pulls entire MUI into bundle
import { Button, TextField } from "@mui/material";

// GOOD — tree-shakeable
import Button from "@mui/material/Button";
import TextField from "@mui/material/TextField";
```

### Step 3: manualChunks in vite.config.js (IF NEEDED)

Only add if build still shows >500 KB chunks after lazy loading:

```js
// vite.config.js
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        mui: ['@mui/material', '@mui/icons-material', '@mui/x-date-pickers'],
        vendor: ['react', 'react-dom', 'react-router-dom'],
      },
    },
  },
},
```

### Gates (G3)
- [ ] `npm run build` — PASS (no >500 KB warnings)
- [ ] At least 5 separate JS chunks in `dist/assets/`
- [ ] `ls -lh carbon-frontend/dist/assets/*.js | wc -l` ≥ 5
- [ ] `du -sh carbon-frontend/dist/assets/` — total still reasonable (< 3 MB total is fine)
- [ ] `npm run lint` — 0 NEW errors (6 pre-existing in api.js are ok)
- [ ] `npx vitest run` — 8/8 pass
- [ ] Browser smoke test: login, navigate 3+ routes, confirm no white flash

---

## G4 — Lighthouse Audit

### Objective
Run Lighthouse on 5 key pages, produce report with scores + actionable recommendations.

### Pages to audit
1. `http://localhost:5179/login` — first paint
2. `http://localhost:5179/` — PlatformHome (app portal)
3. `http://localhost:5179/carbon/dashboard` — EmissionsDashboard (heaviest page)
4. `http://localhost:5179/catalog` — CatalogHome
5. `http://localhost:5179/admin/users` — Admin CRUD

### How to run Lighthouse
```bash
# Option A: Chrome DevTools → Lighthouse tab (manual)
# Option B: CLI (if installed)
npx lighthouse http://localhost:5179/login --view --chrome-flags="--no-sandbox"
```

### Metrics to report per page
| Metric | Target |
|--------|--------|
| Performance score | > 70 |
| LCP (Largest Contentful Paint) | < 2.5s |
| TBT (Total Blocking Time) | < 300ms |
| CLS (Cumulative Layout Shift) | < 0.1 |
| SI (Speed Index) | < 3.0s |

### Gate (G4)
- [ ] `TASK-RESULTS-P12-LIGHTHOUSE.md` created with full table for 5 pages
- [ ] Top 3 actionable recommendations per page
- [ ] Before/after comparison if G3 code splitting improved scores

---

## G5 — Final Verification

```bash
cd carbon-frontend
npm run build        # MUST pass, no >500KB warning
npm run lint         # 0 new errors (6 pre-existing ok)
npx vitest run       # 8/8 pass
```

Also verify via `./manage.sh`:
```bash
./manage.sh status   # frontend should be running on port 5179
```

---

## DO NOT
- ❌ Remove any page or route — every existing page must remain accessible
- ❌ Change the App.jsx route tree structure — only change import style
- ❌ Remove or rewrite the Suspense wrapper — it's correctly positioned, just needs lazy children
- ❌ Touch `api.js`, `apiFetch`, or any API layer
- ❌ Add new dependencies (no `@loadable/component` — use `React.lazy` only)
- ❌ Change any component's behavior, props, or rendering logic
- ❌ Touch any backend files

---

## Success Criteria
1. **Build < 500 KB initial chunk** — no Vite chunk size warnings
2. **At least 5 JS chunks** in dist — proven code splitting
3. **All 8 Vitest tests pass** — nothing broken
4. **Lighthouse Performance > 70** on all 5 key pages
5. **`TASK-RESULTS-P12-LIGHTHOUSE.md`** populated with scores + recommendations
6. **0 new lint errors** beyond pre-existing 6 in api.js

---

## Handoff

When done, write `TASK-RESULTS-P12-FRONTEND.md` with:
- Files changed (with line ranges)
- Build output (show chunk list: `ls -lh dist/assets/*.js`)
- Lighthouse table (5 pages × 5 metrics)
- Terminal output from gates (build, lint, vitest)
- Any issues or blockers
