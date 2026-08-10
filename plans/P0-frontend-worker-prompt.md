# P0 — Frontend Worker Prompt

**Role:** Frontend Worker (React 19 + Vite + MUI v7)
**Phase:** DQ Core P0 Fixes
**Spec:** `TASK-DQ-CORE-P0-FIXES.md` (read it now if you haven't)
**Companion docs:** `plans/CARBON_DQ_CORE_PLAN.md`, `docs/CARBON_DQ_CORE_AUDIT.md`

## Your 1 deliverable (frontend dead code cleanup)

Delete dead code only. **Zero new features, zero redesign, zero refactoring.**

### Item 1: Delete `carbon-frontend/src/components/dq/DQMetricsDrawer.jsx`

- This file is **not imported anywhere** in `carbon-frontend/src/` (verified with grep).
- Delete the entire file.

### Item 2: Remove dead lazy imports in `App.jsx`

- `App.jsx` lines 57-58 import `DQDashboardPage` and `DQRulesPage` but **no Route element uses them**. Their routes (`/catalog/dq-dashboard`, `/catalog/dq-rules`) already redirect to `/catalog/dq`.
- Remove lines 57-58 (the two `React.lazy(() => import(...))` lines).
- Do NOT touch the Route redirects (`/catalog/dq-dashboard` → `/catalog/dq`, `/catalog/dq-rules` → `/catalog/dq`). Keep those.
- Delete the two page files: `pages/catalog/DQDashboardPage.jsx` and `pages/catalog/DQRulesPage.jsx`.

### Item 3: Delete dead API functions in `api/dq.js`

- **`getFieldProfiles()`** (line 78): calls nonexistent endpoint `dq/field-profiles/`. Not imported anywhere in `carbon-frontend/src/` (verified). Delete the function.
- **`bulkExecuteRules()`** (line 159): not imported anywhere (verified). Delete the function.

### Item 4: Remove stale breadcrumb in `shell/StatusBar.jsx`

- Line 61: `if (pathname === '/dataschema/quality' || pathname === '/carbon/data-entry/quality')` — these paths no longer exist.
- Delete the whole if block (lines 60-63 or wherever the block ends, typically closing brace + its `return` statement).

## Gates (run in order, all must pass)

1. `grep -ri "DQMetricsDrawer" carbon-frontend/src/` → zero hits
2. `grep -ri "getFieldProfiles\|field-profiles" carbon-frontend/src/` → zero hits
3. `grep -ri "bulkExecuteRules" carbon-frontend/src/` → zero hits
4. `grep -ri "DQDashboardPage\|DQRulesPage" carbon-frontend/src/` → zero hits
5. `grep "dataschema/quality\|data-entry/quality" carbon-frontend/src/shell/StatusBar.jsx` → zero hits
6. `cd carbon-frontend && npm run build` → clean (no errors)
7. `cd carbon-frontend && npm run lint` → clean (no new warnings; pre-existing warnings in unchanged files are fine)

## Explicit exclusions (HARD BOUNDARIES)

- Do NOT touch any other file.
- Do NOT add new components, routes, or features.
- Do NOT refactor or restructure.
- Do NOT touch `DQHubPage.jsx`, `DQRuleDialog.jsx`, or any active component.
- Do NOT run git commit.

## Handoff

Report in this exact format when done:
```
PHASE 0 FRONTEND: <DONE | BLOCKED>
- Deliverables: <1/1 or note deviations>
- Gates: <pass/fail per gate, with command output summary>
- Files changed: <list>
- Decisions needed: <list, or "none">
```
