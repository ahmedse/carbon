# TASK-DQ-CORE-P5-WORKSPACE

**Status:** NOT STARTED
**Phase:** 5 of 5 — DQ Core next-gen plan (`plans/CARBON_DQ_CORE_PLAN.md` §3-Phase-5)
**Depends on:** TASK-DQ-CORE-P4-PULSE
**Executing agent:** read this file cold; everything needed is below.

## Goal

One sidebar entry → one **DQ Workspace** (`/dq`) with five tabs. Rules are authored as JSON (Pulse drafts, human approves — no form builder). System components are reused, above all `components/DataGrid/CarbonDataGrid.jsx` for every grid.

## Design decisions (do NOT debate)

1. **JSON-first authoring.** Rule create/edit = a plain JSON textarea + client syntax check + server `rule_schema` errors echoed verbatim. "Draft with Pulse" button (NL prompt → `suggest` job → prefilled JSON for approval). No rule-builder form.
2. **Reuse, don't rebuild.** `CarbonDataGrid` for all grids; metric-card and tab patterns copied from `pages/catalog/DQHubPage.jsx`; then `DQHubPage` is deleted.
3. **One menu.** Sidebar gets a single "DQ Workspace" entry; all legacy DQ routes redirect to `/dq`.
4. React 19 + Vite + MUI + react-router v6; data layer via `src/api/dq.js` (extend it — no ad-hoc `apiFetch` strings in components; fix the Phase-0-noted inline import in `DQHubPage.handleBulkExecute` pattern by not copying it).

## Deliverables

### 1. Route & menu

- Route `/dq` → `pages/dq/DQWorkspacePage.jsx`; redirects: `/catalog/dq`, `/catalog/dq-dashboard`, `/catalog/dq-rules`, `/dashboards/data-quality` → `/dq`.
- `shell/ShellSidebar.jsx`: one entry "DQ Workspace" (replace both legacy entries). Command palette + breadcrumbs updated to `/dq`.

### 2. Workspace tabs (`DQWorkspacePage`)

1. **Overview** — overall score + per-dimension scores (from `dq/metrics/` `scores_by_dimension`), `skipped_rules` indicator ("Pulse unavailable" honesty), recent failed results, running jobs strip, trend sparkline (from `rules/{id}/history/` aggregation or metrics).
2. **Rules** — `CarbonDataGrid` over `GET /dq/rules/` with server-side filters: search (name), level, type, dimension, severity, active, tag, `include_archived`. Row actions: **view icon** → `/dq/rules/:id`; run (creates job → toast links to Jobs tab); activate/deactivate toggle. "New rule" button → JSON editor dialog (item 4).
3. **Jobs** — `CarbonDataGrid` over `GET /dq/jobs/` (type, target, status chip, progress bar, created, duration); polls every 5s while any `running`; row → detail drawer: payload, `pulse_task_id`, result summary, error, cancel button.
4. **Suggestions** — pending `DQSuggestion` cards/rows: proposed JSON (collapsible, syntax-highlighted if a highlighter already exists in the repo, else plain `<pre>`), rationale, confidence; **Accept** (creates rule, navigate to its detail) / **Reject** (optional reason dialog).
5. **Monitoring** — move (not rewrite) the Profiles / Freshness / Schema-change components from `DQHubPage` into this tab.

### 3. Rule detail — `pages/dq/RuleDetailPage.jsx` at `/dq/rules/:id`, five tabs

1. **Definition** — JSON editor (save → `PATCH`, creates new `version`; server validation errors listed), name/description/tags editing, bindings (tables/fields chips).
2. **Operations** — activate/deactivate, run now (job link), duplicate, archive (when results exist) / delete (when none).
3. **Usage & Data Products** — bound tables/fields; related catalog assets resolved via table → module → catalog `AssetProfile` (quality rollup); "used by N data products" header; coverage note when a bound field has no other rules.
4. **Stats** — pass-rate trend chart (existing `history/` endpoint + `improving/stable/degrading`), checked/failed over time, last-run summary card.
5. **Results** — `CarbonDataGrid` of `DQResult` for the rule; row expand → `sample_failures` drill-down (row ids + `explanation`/`confidence` when AI-produced); `skipped_unavailable` rows shown distinctly.

### 4. Rule JSON editor dialog — `components/dq/RuleJsonEditor.jsx`

- Textarea (monospace), client JSON.parse check, "Validate" button hitting rule create in dry-run fashion if the backend supports it (else rely on submit errors), "Draft with Pulse" input (NL → creates `suggest` job → on `done`, prefills textarea from the first pending suggestion).
- Used by both "New rule" and the Definition tab.

### 5. Cleanup

- Delete `pages/catalog/DQHubPage.jsx` and any leftovers from P0. Per-table DQ tabs (`SchemaDetailPage` DQ Rules tab, `AssetQualityTab`) stay but their "manage" actions deep-link to `/dq/rules/:id` (or `/dq/rules?table=<id>`).
- Remove the legacy synchronous `rules/{id}/execute/` action from the backend now that the UI uses jobs (kept in P3 only for compat).

## Explicit exclusions

- No charting-library upgrade — use what the repo already has. No JSON-schema form generators. No new backend endpoints beyond what P1–P4 delivered.

## Gates

1. `cd carbon-frontend && npm run build && npm run lint` — clean.
2. Frontend tests (vitest/jest if configured, else add minimal render tests): workspace renders 5 tabs; rules grid fires filter params; rule detail renders 5 tabs; suggestion accept navigates to the new rule.
3. E2E smoke (Playwright, `e2e/`): login → sidebar "DQ Workspace" → create rule via JSON editor → run → see job reach `done` → open rule detail Stats tab. Mock Pulse where needed.
4. `grep -rn "DQHubPage\|dq-dashboard\|dq-rules" carbon-frontend/src/` → only redirect entries remain.
5. Backend still green after removing the legacy execute action: `cd backend && python -m pytest dq/ -q` (or `./manage.sh test` from repo root — there is **no `verify.sh`** in this repo).

## Done criteria

A rule's full lifecycle — Pulse-draft → approve JSON → enforce at gate → run as job → monitor stats → archive — happens without leaving `/dq`. One sidebar menu. No dead DQ code anywhere in `src/`.
