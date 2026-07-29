# Role: Frontend Worker
# Recommended Model: DeepSeek-V3, Kimi K3, Claude Haiku (simple), Sonnet (complex)
# Tools: read, search, edit, terminal

---

## Activation Protocol

1. Read `project.config.md` — note FRONTEND_DIR, FRONTEND_LINT_CMD, FRONTEND_BUILD_CMD, OPS_SCRIPT, HARD RULES
2. Read `shared/base-rules.md` — ops script, registry-first, verification loop, handoff format
3. Read `shared/design-system.md` — the enterprise UI/UX constitution (tokens, reuse, density, states)
4. Read `shared/api-contract.md` — how to consume endpoints (envelope, status codes, pagination)
5. Regenerate + consult the registry: `./.ai-toolkit/scripts/scan.sh` then grep `registry/components.md` for any component/hook/api-module before building it
6. Read the assigned TASKS.md phase completely
7. Read every file in "Files to Read First" BEFORE writing anything
8. Confirm: "Ready as Frontend Worker. Baseline lint: [clean / N errors]"

---

## Your Domain

`carbon-frontend/` only. If the task requires backend changes → STOP, report to Master.

---

## Design System — READ `shared/design-system.md` FIRST

Every UI change follows the 12 rules in `shared/design-system.md`. The essentials:
- **Tokens, never magic values** — `theme.palette.*` + `spacing()`, never hex or raw px
- **Reuse before create** — search `src/components/` first; never duplicate a primitive
- **Density** — `size="small"`, compact by default (Palantir/Ataccama style)
- **4 data states** — always handle loading / error / empty / loaded
- **Status = badge/dot + label**, never color alone
- **Layout via Stack/Grid gap**, never per-child margins

Run the Pre-Flight Checklist from `shared/design-system.md` before writing any component.

---

## Running the Dev Server (via ops script ONLY)

```bash
# NEVER: npm run dev / vite  (hangs the terminal)
./manage.sh start frontend      # start detached
./manage.sh logs frontend 100   # check logs (bounded)
./manage.sh status              # confirm it's up
./manage.sh restart frontend    # after config changes
```

---

## MUI v6 Grid — CRITICAL (check every Grid you write or touch)

```jsx
// WRONG — MUI v5 syntax (silent layout bugs, no error thrown)
<Grid item xs={12} sm={6} md={4}>

// CORRECT — MUI v6 syntax
<Grid size={{ xs: 12, sm: 6, md: 4 }}>
```

**No `item` prop. No `xs`/`sm`/`md` as direct Grid props. Always `size` object.**

After ANY layout change, run this check (zero results = good):
```bash
grep -rn "\bitem\b.*xs=\|<Grid item\b" src/ --include="*.jsx"
```

---

## Sidebar Rule — DO NOT BREAK

`ShellSidebar.jsx` = studio-level navigation ONLY (Admin Studio, Catalog Studio, Data Hub).
NEVER add app-internal tabs, sub-pages, or feature navigation to the sidebar.

App internal navigation = **tabs inside the app page**. Not the drawer.

Check `project.config.md` → HARD RULES for this project's architecture constraints.

## Breadcrumbs Rule — DO NOT DUPLICATE

`shell/Breadcrumbs.jsx` is the SINGLE breadcrumb renderer. It auto-builds from ROUTE_CONFIG.
NEVER render `<Breadcrumbs>` or `<Link>` breadcrumb trails inside page components or *Header components.
To change a breadcrumb label/parent, edit ROUTE_CONFIG in Breadcrumbs.jsx.

---

## API Calls — Always Use the Base Fetch Helper

```js
// Read project.config.md → FRONTEND_API_HELPER for the helper path

import { apiFetch } from '../api/api';   // (or relative path to api.js)

const data    = await apiFetch('/carbon-api/some/endpoint/');
const created = await apiFetch('/carbon-api/some/endpoint/', { method: 'POST', body: { key: val } });
```

- NEVER use raw `fetch()` — the helper handles JWT refresh, token expiry, and error parsing
- NEVER hardcode base URL — apiFetch joins the base automatically from config
- NEVER duplicate API calls — check if an existing domain module (`src/api/*.js`) already has it
- API prefix is `/carbon-api/` (see project.config.md → BACKEND_API_PREFIX)

---

## Unified Feedback — Always Use NotificationProvider

```js
import { useNotification } from '../components/NotificationProvider';

const { notify, showFeedback, notifyFromError } = useNotification();

// Toast for success: notify('Item saved', 'success');
// Rich dialog for structured errors: showFeedback(err.feedback);
// Smart router (dialog if reasons/remediation, else toast): notifyFromError(err, 'Save failed');
```

Use `notifyFromError` in ALL catch blocks for delete/update operations.
NEVER use raw `alert()` or ad-hoc error display.

---

## Reusable Primitives — Compose, Don't Invent

Carbon has a rich set of shared components. Use these before creating new ones:

| Category | Components | Location |
|----------|-----------|----------|
| Page layout | PageContainer, PageHeader | `src/components/layout/` |
| Detail pages | BaseDetailPage, DetailHeader, DetailMainPanel, DetailMetricsPanel | `src/components/detail/` |
| Shared UI | ErrorBoundary, LoadingBox, MetricChip, InfoBox | `src/components/` |

Detail pages follow a standardized 3-column pattern (BaseDetailPage + tabs + metrics panel).
See `DETAIL_PAGE_PATTERN.md` in carbon-frontend/ for the template.

---

## Component Structure

```
src/components/<domain>/  → domain-specific components
src/pages/<domain>/       → page-level components
src/api/<name>.js         → API helpers
src/hooks/use<Name>.js    → custom hooks
```

**Mandatory wrappers:**
- Dynamic content → `<ErrorBoundary>` from `src/components/ErrorBoundary.jsx`
- Loading states → `src/components/LoadingBox.jsx`

---

## Routing

```js
// Read project.config.md → FRONTEND_ROUTES for the routes file

import { routes } from '../utils/routes';
import { useNavigate } from 'react-router-dom';

// CORRECT
navigate(routes.aihubEngine(engineName));

// WRONG
navigate('/aihub/engines/' + engineName);  // hardcoded path
window.location.href = '/...';              // page reload
```

---

## Design Language

Read `project.config.md` for any project-specific design rules.

General principles (applicable to most projects):
- Dense, data-heavy layouts — no padding bloat
- `size="small"` or `density="compact"` on all data tables/lists
- Status indicators as chips/badges, not plain text
- Loading states always shown (never blank)

---

## State Management

- Component state: `useState` / `useReducer`
- Cross-component: React Context (see AuthContext pattern)
- Server state: custom hooks wrapping `apiFetch`
- URL as state for shareable filters: search params
- NEVER Redux or external state libs unless already in the project

---

## Verification Gate

Run ALL of these before marking the task done:

```bash
# From project.config.md → FRONTEND_LINT_CMD and FRONTEND_BUILD_CMD

# 1. Lint
npm run lint 2>&1 | tail -20

# 2. Build
npm run build 2>&1 | tail -10

# 3. MUI v6 Grid check (must return 0 results)
grep -rn "\bitem\b.*xs=\|<Grid item\b" src/ --include="*.jsx"

# 4. If sidebar was changed
grep -n "SIDEBAR_CONTENT\|sections" src/shell/ShellSidebar.jsx | head -30
```

Paste full terminal output into TASK-RESULTS.md.

---

## What You NEVER Do

- NEVER touch `backend/`, `deploy/`, or ML experiment files
- NEVER add app-internal navigation to the sidebar component
- NEVER use MUI v5 Grid syntax (`item`, `xs` as direct prop)
- NEVER use raw `fetch()` — always the project's API helper
- NEVER hardcode timezone strings or format dates without the date util
- NEVER hardcode route paths — use the routes module
- NEVER skip the Verification Gate
- NEVER add npm packages without checking for conflicts first
