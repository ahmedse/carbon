# Sprint 31 — P4-B: Healthy Domain App (frontend)

**Date:** 2026-08-20
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** READY (BLOCKED until P4-A lands — the endpoints must exist)
**Kind:** Frontend-only. Medium-large.
**Depends on:** P4-A (`backend/healthy/` endpoints under `/carbon-api/healthy/`).
**Source of truth (READ FIRST):** `docs/DESIGN-PLATFORM.md` §8 + §11 (the screen table).

## What this phase builds

The Healthy screens inside the existing `<MainLayout>` shell — the end-to-end proof:
dataset → DQ review → approve → TurnKeyModelLink → prediction → drift → violation, rendered
as operator dashboards.

## Files to Read First

- `docs/DESIGN-PLATFORM.md` §8 + §11
- `carbon-frontend/src/shell/Shell.jsx` — `studioFromPath()` (RULE_15: every new route path must map to a studio)
- `carbon-frontend/src/shell/ShellSidebar.jsx` — where new nav sections go
- `carbon-frontend/src/App.jsx` — route registration (RULE_22: every navigate target must resolve)
- `carbon-frontend/src/api/api.js` — `apiFetch` (RULE_10: use ONLY this)
- `carbon-frontend/src/theme/carbonTheme.js` — tokens (RULE_8)
- `carbon-frontend/src/components/layout/PageContainer.jsx` + `src/components/detail/BaseDetailPage.jsx` (RULE_16)
- Existing DataGrid/table + dashboard patterns (e.g. `src/pages/catalog/`, `src/pages/carbon/`)
- `.ai-toolkit/shared/design-system.md`, `.ai-toolkit/shared/compact-ui.md`

## Files to Change (all under `carbon-frontend/`)

- `src/apps/healthy/` — NEW: dashboard, loadout, reps, collections, inventory screens
- `src/api/healthy.js` — NEW: `apiFetch` helpers for `/carbon-api/healthy/`
- `src/App.jsx` — register routes (absolute, namespace-prefixed per RULE_5)
- `src/shell/Shell.jsx` — add paths to `studioFromPath()` (RULE_15)
- `src/shell/ShellSidebar.jsx` — add "Apps" / Healthy nav section
- `src/__tests__/healthy/` — NEW: Vitest + RTL tests for the screens
- `src/apps/carbon/manifest.js` or app registry surface — Healthy app card (if applicable)

## Screens (from §11)

| Screen | Route | Components |
|--------|-------|-----------|
| Healthy Dashboard | `/apps/healthy` | PipelineStatusRow (5), SummaryKPIs |
| Loadout Sheet | `/apps/healthy/loadout` | WeekPicker, RepTable, ItemRows, ExportXLS |
| Rep Health | `/apps/healthy/reps` | RepCards grid + churn-probability badge |
| AR Queue | `/apps/healthy/collections` | PriorityTable sortable by risk score |
| Slow Movers | `/apps/healthy/inventory` | Heatmap + AlertTable |

## Implementation rules (HARD)

- Theme tokens ONLY (RULE_8) — no hardcoded hex/px/inline font sizes.
- All data calls via `apiFetch` (RULE_10) — never raw `fetch()`.
- Page roots use `PageContainer` / `BaseDetailPage` (RULE_16).
- Tab switching uses MUI `<Tabs>` + `<Tab>` with localStorage persistence (RULE_17) if the
  dashboard is tabbed; otherwise a single scrollable page.
- One breadcrumb source: `src/shell/Breadcrumbs.jsx` (RULE_9) — never inline breadcrumbs.
- Routes absolute + namespace-prefixed (RULE_5); add index route at `/apps` bare root (RULE_22).
- User-facing copy describes OUTCOMES, never internals (RULE_23) — e.g. "Forecast ready",
  never "model served" / "pipeline dispatched".

### DO NOT TOUCH

- `backend/**` — everything backend is P4-A's domain.
- `src/shell/Breadcrumbs.jsx` (read-only, don't restructure).

## Verification Gate (run ALL, paste FULL output)

```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run                     # healthy-screen tests pass
npm run build
cd /home/ahmed/aast/carbon
./.ai-toolkit/scripts/verify.sh frontend
./.ai-toolkit/scripts/audit-routes.py   # no dangling routes (RULE_22)
```

## Output contract

Append to `TASK-RESULTS.md` (Part B handoff format): Summary → Task results → Files Changed →
Verification Output (full paste) → Deviations → Issues Found → verdict.

## Notes for the Master

- Only dispatch after P4-A is ACCEPTED and `/carbon-api/healthy/` endpoints are live.
- If endpoints are missing, STOP and report — do not mock real data shape into the UI.
- Commit with `feat(healthy): P4-B — Healthy frontend screens (dashboard, loadout, reps, AR, slow movers)`.
