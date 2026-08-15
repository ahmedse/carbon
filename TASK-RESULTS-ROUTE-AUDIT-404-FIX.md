# TASK-RESULTS-ROUTE-AUDIT-404-FIX — Frontend Worker Handoff

- **Date:** 2026-08
- **Role:** Frontend Worker
- **Source:** User bug report — *"when i first open it this happens: Page Not Found / The page `/carbon/` doesn't exist."* + *"audit all routes and urls … prevent such from ever happening again! and update ai-toolkit accordingly"*
- **Scope:** Frontend-only (React Router / Vite / nginx deploy configs) + `.ai-toolkit/` hardening
- **Verdict per gate:** `verify.sh frontend` ✅ GATE PASSED · `npm run lint` ✅ 0 errors / 53 warnings (pre-existing debt) · `npm run build` ✅ `built in 10.74s` · `npm test` ✅ 336/336 · `audit-routes.py` ✅ `69 referenced path(s) resolve, 16 namespace root(s) covered`

---

## Summary

| # | Deliverable | Status | Evidence |
|---|-------------|--------|----------|
| 1 | Fix `/carbon/` first-open 404 | ✅ | bare-root index redirects in `App.jsx` |
| 2 | Full route/URL audit (all nav targets resolve) | ✅ | `audit-routes.py` → clean |
| 3 | Deterministic prevention wired into the gate | ✅ | `audit-routes.py` added to `verify.sh` `frontend`/`all`/`full` |
| 4 | Toolkit rule + worker role + playbook | ✅ | RULE_22, frontend-worker Routing section, PB-25 |
| 5 | Regression test (red → green) | ✅ | `routes.test.jsx` 6 assertions → 336/336 |

---

## Root cause (1 line)

Routes are **absolute + namespace-prefixed** (`/carbon/*`, `/admin/*`, …) but the **bare namespace roots had no `<Route>`**, so `/carbon/` fell through to `<Route path="*">` → `NotFound` — and `VITE_BASE=/` does not strip the `/carbon/` mount path that combined nginx serves the SPA under.

## Why it only bit on first open

`studioFromPath()` still highlighted the `carbon` studio (it reads the URL prefix), but React Router had no matching `<Route path="/carbon">` — only the deeper `/carbon/console`, `/carbon/dashboard`, etc. A fresh session lands on `/carbon/` (the deploy mount), which has no route → 404. Deep links worked; the bare root didn't.

---

## Fix applied

### 1. `carbon-frontend/src/App.jsx` — bare-root index redirects (RULE_22)
Added idempotent `<Navigate replace />` index routes at every top-level namespace root (no layout duplication, since the redirect just forwards into the existing tree):

- `/carbon` → `/carbon/console`
- `/emissions/dashboard` → `/carbon/dashboard`
- `/data-owner/reports/generate` → `/carbon/reporting/generate`
- `/admin` → `/admin/users`
- `/settings/profile` + `/settings/preferences` → `/settings`
- `/dashboards` → `/carbon/dashboard`
- `/modules` → `/carbon/my-data`
- `/scopes` → `/carbon/console`
- `/schema-admin` → `/schema-admin/table-manager`

Each carries a `RULE_22` comment. Redirects are chosen over duplicated layouts so future renames don't fork the tree.

### 2. `carbon-frontend/src/shell/CommandPalette.jsx` — dead nav target
`path: '/emissions/dashboard'` → `path: '/carbon/dashboard'`.

### 3. `carbon-frontend/src/pages/emissions/SavedReportsPage.jsx` — dead href
`href="/data-owner/reports/generate"` → `href="/carbon/reporting/generate"`.

### 4. `.ai-toolkit/scripts/audit-routes.py` (NEW) — deterministic prevention
Two hard-failure checks:
1. Every literal nav target (`navigate("…")`, `<Navigate to>`, `<Link to>`, `to=`, `href=`, `path:` config) resolves to a `<Route>` — dynamic `:param` segments are normalized; template-literal `${}` and capability-route maps (`authz.js`/`rbac.js`) are excluded as mirrors; `src/apps/stub` (unregistered scaffolding) excluded.
2. Every top-level route namespace declares a bare-root index route.
- Output: `✓ route audit clean: 69 referenced path(s) resolve, 16 namespace root(s) covered`.

### 5. `.ai-toolkit/scripts/verify.sh` — gate wiring
New `verify_routes()` runs `audit-routes.py` (via resolved python); wired into `frontend)`, `all)`, `full)`.

### 6. `.ai-toolkit/project.config.md` — rules
- **RULE_5 corrected:** routes are absolute/namespace-prefixed; `VITE_BASE` (router basename) MUST stay `/` (App.jsx already carries prefixes — any non-`/` basename would double-prefix and 404).
- **RULE_22 added:** NO DANGLING ROUTES — every top-level namespace must register a bare-root index route; enforce with `audit-routes.py`.

### 7. `.ai-toolkit/roles/frontend-worker.md` — Routing section rewritten
Removed the incorrect "NEVER hardcode route paths — use `../utils/routes`" guidance (module never existed); added RULE_22-aware routing rules + `audit-routes.py` step to the Verification Gate.

### 8. `.ai-toolkit/troubleshooting/playbook.md` — PB-25
"Page Not Found: /carbon/ on first open (bare namespace root)" with Symptom / Layer / Root cause / Fix / Best practice / Regression guard / First seen 2026-08. (Also restored PB-05 body accidentally dropped mid-edit.)

### 9. `carbon-frontend/src/__tests__/routes.test.jsx` (NEW) — regression guard
Reads `App.jsx` via `readFileSync(resolve(process.cwd(), 'src/App.jsx'))`, extracts `<Route path → <Navigate to replace/>` pairs, asserts all 9 namespace-root redirects. Red→green: first failed on `fileURLToPath(new URL(import.meta.url))` (`import.meta.url` is not `file:` under Vitest) → fixed to `process.cwd()`.

### 10. `carbon-frontend/eslint.config.js` — test-file Node globals
Added `...globals.node` to the `src/__tests__/**` scope so the filesystem-reading test can use `process`.

---

## Verification (definition of done)

```
$ npm run lint
✖ 53 problems (0 errors, 53 warnings)     # warnings are pre-existing react-hooks/exhaustive-deps debt

$ npm run build
✓ built in 10.74s

$ npm test
Test Files  9 passed (9)
     Tests  336 passed (336)

$ ./.ai-toolkit/scripts/verify.sh frontend
── Frontend ────────────────────────────
✓ lint
✓ build
── Routes ──────────────────────────────
✓ route audit clean: 69 referenced path(s) resolve, 16 namespace root(s) covered
✓ route/URL audit
════════════════════════════════════════
GATE PASSED
```

---

## Issues found (out of scope / noted debt)

- **53 pre-existing lint warnings** — all `react-hooks/exhaustive-deps` in existing pages; untouched (frontend-only scope, no behavior change).
- **`src/apps/stub`** — unregistered scaffolding template excluded from the audit (`EXCLUDE_DIRS`); flagged for future removal, not part of this fix.

## Deviations

- **None.** Frontend-only scope respected; no backend/API/DB changes. Backend tests intentionally not re-run (unchanged).

## Lessons encoded

1. Every top-level route namespace needs a bare-root index redirect — enforced by RULE_22 + `audit-routes.py` + regression test.
2. `import.meta.url` is **not** a `file:` URL under Vitest — use `process.cwd()` for filesystem paths in tests.
3. Template-literal `${}` nav targets and capability→route mirror maps are false positives in literal route audits — excluded by design.
