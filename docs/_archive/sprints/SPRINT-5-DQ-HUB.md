# TASK — Unified DQ Management Hub

**Status:** ⬜ READY · **Created:** 2026-08-09 · **Planned effort:** 2 workers (backend + frontend)

## Why

The DQ system is currently scattered across **6 different frontend surfaces** and **2 separate pages**:

| Current location | Type | Purpose |
|---|---|---|
| `pages/catalog/DQDashboardPage.jsx` | Full page | Org-level metrics + recent results table |
| `pages/catalog/DQRulesPage.jsx` | Full page | Rule CRUD DataGrid + history dialog |
| `pages/catalog/tabs/DQRulesTab.jsx` | Inline tab | Per-table rules (inside SchemaDetailPage) |
| `components/dq/DQMetricsDrawer.jsx` | Slide-out drawer | Per-table metrics + rules (from dataschema view) |
| `components/dq/DQRulesList.jsx` | Shared component | Simple rules list (used in AssetQualityTab) |
| `pages/catalog/tabs/DQRuleDialog.jsx` | Dialog component | Create/edit rule form |

This fragmentation means:
- Users navigate between 2 separate routes (`/catalog/dq-dashboard` and `/catalog/dq-rules`) for one system
- Two DIFFERENT rule-editing dialogs exist (`DQRuleDialog.jsx` in tabs/ and the inline form in DQRulesPage's dialog)
- No single view shows rules + metrics + execution history + profiles together
- Inline tabs (`DQRulesTab`, `DQMetricsDrawer`) partially duplicate the full pages

## Target Architecture

```
┌──────────────────────────────────────────────────┐
│  /catalog/dq-hub  (single route)                 │
│                                                  │
│  ┌─ Metric Cards Row ───────────────────────────┐│
│  │ Quality Score │ Rules Active │ Tables │ Fail ││
│  └──────────────────────────────────────────────┘│
│                                                  │
│  ┌─ Tabs ───────────────────────────────────────┐│
│  │ [Rules] [Results] [Profiles] [Freshness]     ││
│  └──────────────────────────────────────────────┘│
│                                                  │
│  Rules tab:                                      │
│  ┌─ Toolbar: [+New Rule] [Run All] [Suggest AI] ┐│
│  │ ─────────────────────────────────────────── ││
│  │ DataGrid: name, type, table, field, sev,    ││
│  │ active, last score, last run, actions        ││
│  │ Actions: [▶Run] [✎Edit] [📋History] [🗑Del] ││
│  └──────────────────────────────────────────────┘│
│                                                  │
│  Results tab:                                    │
│  ┌─ Filters: [table▾] [rule▾] [passed▾]        ┐│
│  │ ─────────────────────────────────────────── ││
│  │ DataGrid: rule, table, status, failed rows,  ││
│  │ score, run_at, [📋Failures]                  ││
│  └──────────────────────────────────────────────┘│
│                                                  │
│  Profiles tab:                                   │
│  ┌─ DataGrid: table name, rows, completeness,   ││
│  │ profiled_at, [Profile Now]                   ││
│  └──────────────────────────────────────────────┘│
│                                                  │
│  Freshness tab (Phase 1.8):                      │
│  ┌─ DataGrid: table, last_data, max_age, fresh?,││
│  │ checked_at                                    ││
│  └──────────────────────────────────────────────┘│
└──────────────────────────────────────────────────┘
```

## Backend gap (1 item)

The backend is **95% complete**. Only one endpoint missing:

1. **POST `/dq/rules/bulk-execute/`** — Accept `{rule_ids: [1,2,3]}` or `{data_table_id: 5}`, execute all matching rules, return summary `{total, passed, failed, results: [...]}`. Currently there's `POST /dq/run/` (single rule or all-table) but no bulk-by-rule-ids endpoint.

## Frontend work (all items)

### 1. BUILD `pages/catalog/DQHubPage.jsx` — The unified page

**Route:** `/carbon/catalog/dq-hub`

**Tabs:**
1. **Rules** (default) — Full CRUD DataGrid:
   - Columns: Name, Type, Table, Field, Severity, Active, Last Score, Last Run, Actions
   - Actions: Run Now, Edit, History, Deactivate
   - Toolbar: "+ New Rule" button, "Run All Active" button, "AI Suggest" button
   - Edit/Create: Reuse the existing `tabs/DQRuleDialog.jsx` (it's the better one)
2. **Results** — Read-only DataGrid:
   - Columns: Rule, Table, Status (Passed/Failed chip), Failed Rows, Score, Executed At, Failures
   - Filters: table dropdown, passed/failed toggle, search
   - "View Failures" action opens a dialog with the sample_failures detail
3. **Profiles** — Read-only DataGrid:
   - Columns: Table, Row Count, Completeness %, Profiled At, Actions
   - Actions: "Profile Now" (triggers POST /dq/profile/)
   - Clicking a row expands field-level breakdown (null_counts, distinct_counts)
4. **Freshness/Schema** (Phase 1.8) — Read-only:
   - Freshness checks table: table, last data timestamp, max age, is_fresh bool, checked_at
   - Schema changes table: table, change_type (added/dropped/modified), field_name, detected_at
   - Optional: "Take Snapshot" button if admin

**Summary cards** (above tabs, always visible):
- Quality Score (gauge-style, from org metrics)
- Active Rules count (passing / total)
- Tables Profiled count
- Failing Rules count

### 2. UPDATE routing in `App.jsx`

- Add: `<Route path="/catalog/dq-hub" element={<DQHubPage />} />`
- Keep old routes as redirects for bookmark compatibility:
  - `/catalog/dq-dashboard` → redirect to `/catalog/dq-hub`
  - `/catalog/dq-rules` → redirect to `/catalog/dq-hub?tab=rules`
- Update nav/sidebar links: replace both entries with single "DQ Hub" link

### 3. CLEANUP — remove or deprecate old files

- **DELETE:** `pages/catalog/DQDashboardPage.jsx` (replaced by hub)
- **DELETE:** `pages/catalog/DQRulesPage.jsx` (replaced by hub)
- **DELETE:** `components/dq/DQMetricsDrawer.jsx` (replaced by hub's profile tab)
- **DELETE:** `components/dq/DQRulesList.jsx` (replaced by hub; AssetQualityTab can use a minimal inline version or link to hub)
- **KEEP:** `tabs/DQRuleDialog.jsx` (reused by hub)
- **KEEP:** `tabs/DQRulesTab.jsx` (still used inside SchemaDetailPage as inline view — or optionally replace with a link to hub filtered by table)
- **UPDATE:** `tabs/AssetQualityTab.jsx` — replace `DQRulesList` import with link to `/catalog/dq-hub?tab=rules&table=X`

### 4. ADD missing API wrappers in `api/dq.js`

- `bulkExecuteRules(token, { rule_ids?, data_table_id? })` → `POST dq/run/`
- `getFreshnessChecks(token, filters)` → `GET dq/freshness/`
- `getSchemaChanges(token, filters)` → `GET dq/schema-changes/`
- `profileTable(token, tableId)` → `POST dq/profile/`
- `profileTablesBulk(token, tableIds)` → `POST dq/profile/bulk/`
- `getDQSuggestions(token, tableId)` → `POST dq/suggest/`

## Worker Prompts

Below are copy-paste-ready prompts. Dispatch workers in order: Backend first, then Frontend.

---

### WORKER 1 — BACKEND (Django)

```
TASK: DQ Unified Hub — Backend endpoint additions

You are working on /home/ahmed/aast/carbon/backend. The DQ system backend is 95% complete. Add the following:

1. POST /dq/rules/bulk-execute/ — new action on DQRuleViewSet
   - Accept {rule_ids: [1,2,3]} or {data_table_id: 5}
   - Execute all matching active rules via run_single_rule (already in dq/services.py)
   - Return {total, passed, failed, results: [DQResultSerializer...]}
   - AdminOrSuperuserOnly permission
   - Use @action(detail=False, methods=['post'], url_path='bulk-execute')
   - Import run_single_rule from .services

2. VERIFY (don't create if exists) these endpoints are accessible:
   - POST /dq/profile/ — ProfileTriggerView (exists)
   - POST /dq/profile/bulk/ — BulkProfileView (exists)
   - POST /dq/suggest/ — DQSuggestView (exists)
   - GET /dq/freshness/ — check if FreshnessCheck has a ViewSet; if not, create a ReadOnlyModelViewSet
   - GET /dq/schema-changes/ — check if SchemaChange has a ViewSet; if not, create a ReadOnlyModelViewSet

3. For FreshnessCheck and SchemaChange:
   - Create serializers in dq/serializers.py if missing
   - Create ReadOnlyModelViewSets in dq/views.py if missing
   - Register in dq/urls.py
   - Follow existing patterns (RBAC scoping, select_related, permission_classes=[IsAuthenticated])

4. Tests:
   - Add test for bulk-execute endpoint in dq/tests/test_dq.py
   - Add tests for FreshnessCheck/SchemaChange endpoints if created
   - Run: pytest dq/tests/ --reuse-db -q -v
   - All must pass

OUTPUT: List every file you touch and what you changed.
```

---

### WORKER 2 — FRONTEND (React)

```
TASK: DQ Unified Hub — Frontend consolidation

You are working on /home/ahmed/aast/carbon/carbon-frontend. 

GOAL: Replace 6 scattered DQ components/pages with ONE unified page: /catalog/dq-hub

## Step 1 — Create src/pages/catalog/DQHubPage.jsx

This is the main deliverable. Single-page app with:

### Header with summary cards (always visible above tabs):
- Quality Score card: Large number with color (green ≥80, yellow ≥60, red <60)
- Active Rules card: "12 / 15 passing" with mini sparkline
- Tables Profiled card: Count with completeness avg
- Failed Checks card: Count with red highlight if >0

### Tabs: [Rules] [Results] [Profiles] [Freshness & Schema]

#### Rules Tab (default):
- Toolbar: [+ New Rule] [Run All Active] [AI Suggest Rules] buttons
- DataGrid columns: Name, Type (chip), Table, Field, Severity (chip), Active (chip), Last Score, Last Run, Actions
- Actions column: ▶Run, ✎Edit, 📋History, ⊘Deactivate
- Click "Edit" or "+ New Rule" → opens DQRuleDialog (reuse from tabs/DQRuleDialog.jsx)
- "Run All Active": calls POST /dq/run/ with {data_table_id: selectedTable}
- "AI Suggest": calls POST /dq/suggest/ — show suggestions in a dialog
- Table filter dropdown at top
- Search bar for rule name

#### Results Tab:
- Filter row: Table dropdown, Rule dropdown, Status toggle (All/Passed/Failed)
- DataGrid: Rule, Table, Status (Passed/Failed chip), Failed Rows, Score, Executed At, [View Failures]
- "View Failures" opens dialog showing sample_failures array

#### Profiles Tab:
- DataGrid: Table, Row Count, Completeness %, Profiled At, [Profile Now]
- "Profile Now" calls POST /dq/profile/ with {data_table_id}
- Click row to expand: shows field-level null_counts, distinct_counts, min/max/mean
- Bulk Profile button (admin only): select multiple tables → POST /dq/profile/bulk/

#### Freshness & Schema Tab:
- Sub-tabs: [Freshness] [Schema Changes]
- Freshness: DataGrid — Table, Last Data Timestamp, Max Age (hrs), Fresh? (chip), Checked At
- Schema: DataGrid — Table, Change Type (added/dropped/modified chip), Field Name, Detected At, Old Def, New Def

### Data fetching:
- Use api/dq.js wrappers. Add any missing ones (see Step 3).
- All DataGrids use MUI X DataGrid with pagination, sorting, density="compact"
- All tabs lazy-load (fetch only when tab is active)
- Loading states: CircularProgress centered. Error states: Alert severity="error".

## Step 2 — Update App.jsx routing

- Add lazy import for DQHubPage
- Add route: <Route path="/catalog/dq-hub" element={<DQHubPage />} />
- Add redirects:
  <Route path="/catalog/dq-dashboard" element={<Navigate to="/carbon/catalog/dq-hub" replace />} />
  <Route path="/catalog/dq-rules" element={<Navigate to="/carbon/catalog/dq-hub?tab=rules" replace />} />
- Update any nav/sidebar that links to dq-dashboard or dq-rules → link to dq-hub instead

## Step 3 — Add missing API wrappers in src/api/dq.js

Add these functions following the existing pattern (use apiFetch, relative paths):
- bulkExecuteRules(token, { rule_ids, data_table_id }) → POST dq/run/
- profileTable(token, tableId) → POST dq/profile/ {data_table_id}
- profileTablesBulk(token, tableIds) → POST dq/profile/bulk/ {data_table_ids}
- getDQSuggestions(token, tableId) → POST dq/suggest/ {data_table_id}
- getFreshnessChecks(token, filters) → GET dq/freshness/
- getSchemaChanges(token, filters) → GET dq/schema-changes/

## Step 4 — Cleanup old files

DELETE these files (they are fully replaced by DQHubPage):
- src/pages/catalog/DQDashboardPage.jsx
- src/pages/catalog/DQRulesPage.jsx
- src/components/dq/DQMetricsDrawer.jsx
- src/components/dq/DQRulesList.jsx

UPDATE src/pages/catalog/tabs/AssetQualityTab.jsx:
- Remove DQRulesList import
- Replace the DQRulesList usage with a "View in DQ Hub" link button that navigates to /catalog/dq-hub?tab=rules&table={tableId}

KEEP (these are reused):
- src/pages/catalog/tabs/DQRuleDialog.jsx (used by hub and DQRulesTab)
- src/pages/catalog/tabs/DQRulesTab.jsx (used inline in SchemaDetailPage)

## Step 5 — Build verification

Run: cd carbon-frontend && npm run build
- Must compile with 0 errors, 0 warnings
- Fix any import errors from deleted files

OUTPUT: List every file you touch and what you changed.
```

---

## Verification Gate

1. Backend: `pytest dq/tests/ --reuse-db -q -v` — all pass
2. Backend: `pytest --reuse-db -q` — 873+ pass, same 3 pre-existing failures
3. Frontend: `npm run build` — 0 errors
4. Browser: Navigate to `/carbon/catalog/dq-hub` — all 4 tabs load, CRUD works, execute works, history works
