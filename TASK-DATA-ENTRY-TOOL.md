# TASK: Data Entry Tool — End-to-End Implementation

**Assignee**: Worker  
**Priority**: High  
**Scope**: Frontend only — no backend changes required  
**Persona**: Data Owner (not admin, not analyst)

---

## Goal

Build a coherent 3-level data entry workspace for data owners to find their emission sources, see which tables need data, and enter/manage activity data rows. Everything navigates within the app normally (standard page navigation with breadcrumbs). No nested sidebar-within-sidebar patterns.

---

## User Journey

```
Level 1: /carbon/my-data
  └─ Click source row
     Level 2: /carbon/my-data/:moduleId
       └─ Click table row
          Level 3: /carbon/my-data/:moduleId/:tableId
            └─ Click "View" on a data row
               Level 4: /carbon/data-entry/row/:tableId/:rowId  ← already exists, do not touch
```

---

## File Locations

### Files to CREATE (new):
- `carbon-frontend/src/pages/carbon/MyDataPage.jsx`           ← Level 1 (rewrite)
- `carbon-frontend/src/pages/carbon/ModuleWorkspacePage.jsx`  ← Level 2 (new)

### Files to MODIFY:
- `carbon-frontend/src/App.jsx`                               ← add 2 new routes
- `carbon-frontend/src/pages/DataEntryPage.jsx`               ← add breadcrumb context

### Files to NOT TOUCH:
- `carbon-frontend/src/components/TableDataPage.jsx`          ← Level 3, used as-is
- `carbon-frontend/src/components/DataTableGrid.jsx`          ← used as-is
- `carbon-frontend/src/components/DataRowFormDrawer.jsx`      ← used as-is
- `carbon-frontend/src/components/entity/EntityDetailShell.jsx` ← used as-is
- `carbon-frontend/src/components/detail/BaseDetailPage.jsx`  ← used as-is

---

## Available Components (import from `../../components`)

```js
// Page components
import { PageHeader, EmptyState, ErrorAlert, LoadingSkeleton } from '../../components';
import { StatCard } from '../../components';
import { CarbonDataGrid } from '../../components';
import { ActivityFeed } from '../../components';
import { RightPanel } from '../../components';

// Entity detail shell (three-column layout with resizable right panel)
import EntityDetailShell from '../../components/entity/EntityDetailShell';

// TableDataPage (complete data entry component — Level 3)
import TableDataPage from '../../components/TableDataPage';
```

---

## Available APIs

```js
// Auth context
import { useAuth } from '../../auth/AuthContext';
// provides: { token, user, context }
// context.project_id  — required for all dataschema calls
// context.modules     — list of all modules user has access to

// My Data (Level 1 data)
import { fetchMyData, fetchOwnerActivity } from '../../api/emissions';
// fetchMyData(token) returns:
// {
//   org_unit: { id, name, code },
//   stats: { total_modules, total_rows, modules_with_data, data_quality: { total_assets, passing } },
//   modules: [
//     { id, name, scope, row_count, table_count, quality_score, last_entry }
//   ]
// }
// fetchOwnerActivity({ limit: 10 }, token) returns array of activity events

// Module CRUD
import { createModule, updateModule, deleteModule } from '../../api/modules';
// createModule(token, { name, scope, org_unit }) → created module
// updateModule(token, id, { name, scope })        → updated module
// deleteModule(token, id)                          → 204

// Tables for a module (Level 2 data)
import { fetchDataSchemaTables } from '../../api/dataschema';
// fetchDataSchemaTables(token, project_id, module_id) returns:
// [ { id, title, description, row_count, field_count, module } ]
```

---

## Route Changes in `App.jsx`

Find the existing route:
```jsx
<Route path="/carbon/my-data" element={<MyDataPage />} />
```

Replace with:
```jsx
import ModuleWorkspacePage from './pages/carbon/ModuleWorkspacePage';

<Route path="/carbon/my-data" element={<MyDataPage />} />
<Route path="/carbon/my-data/:moduleId" element={<ModuleWorkspacePage />} />
<Route path="/carbon/my-data/:moduleId/:tableId" element={<DataEntryPage />} />
```

`DataEntryPage` is already imported in App.jsx. No new import needed for it.

---

## Level 1 — `MyDataPage.jsx`

### Layout

```
PageHeader (title="My Data", subtitle=org unit name, breadcrumbs)
4× StatCard row
FilterBar (search + scope + status dropdowns)
CarbonDataGrid (sources list)
ModuleDialog (add/edit drawer)
DeleteConfirmDialog
Snackbar
```

### Breadcrumbs
```js
[{ label: 'Home', path: '/dashboard' }, { label: 'My Data' }]
```

### StatCards (4 across)
| Title | Value | Color |
|-------|-------|-------|
| Sources | `stats.total_modules` | primary |
| With Data | `stats.modules_with_data` | success |
| Total Rows | `stats.total_rows` | info |
| DQ Score | computed: `Math.round((stats.data_quality.passing / stats.data_quality.total_assets) * 100) + '%'` or `'N/A'` | warning |

### Filter Controls (above grid, in a Paper)
- `TextField` search: filters `module.name` (client-side)
- `Select` Scope: `All / Scope 1 / Scope 2 / Scope 3` — filters `module.scope`
- `Select` Status: `All / Active / No Data / Low DQ` — see status logic below
- `Tooltip` + `IconButton` refresh button

### Status Logic (computed, not from API)
```js
function getStatus(mod) {
  if (!mod.row_count || mod.row_count === 0) return 'no_data';
  if (mod.quality_score != null && mod.quality_score < 60) return 'low_dq';
  return 'active';
}
```

### Grid Columns (use `CarbonDataGrid`)
```
| Scope       | Source Name       | Rows | Status    | DQ%  | Last Entry | Actions |
```

Column specs:
- **Scope**: width 110, render `<Chip>` using scope meta:
  ```js
  const SCOPE_META = {
    1: { label: 'Scope 1', color: 'error' },
    2: { label: 'Scope 2', color: 'warning' },
    3: { label: 'Scope 3', color: 'info' },
  };
  ```
- **Source Name**: `flex: 2`, `minWidth: 200`, fontWeight 600
- **Rows**: `width: 90`, `type: 'number'`
- **Status**: `width: 120`, render `<Chip>`:
  ```js
  const STATUS_META = {
    active:  { label: 'Active',   color: 'success' },
    no_data: { label: 'No Data',  color: 'default' },
    low_dq:  { label: 'Low DQ',   color: 'warning' },
  };
  ```
  Note: `valueGetter: (params) => getStatus(params.row)`
- **DQ%**: `width: 90`, render score or `—`
- **Last Entry**: `width: 150`, render formatted date or `Never`
- **Actions**: `width: 100`, sortable false — two `IconButton`s: Edit (pencil), Delete (trash). Use `e.stopPropagation()` to prevent row click.

### Row Click
```js
onRowClick={(params) => navigate(`/carbon/my-data/${params.row.id}`)}
```

### Add Source Button
In PageHeader `actions` prop:
```jsx
<Button variant="contained" size="small" startIcon={<AddIcon />} onClick={() => setAddOpen(true)}>
  Add Source
</Button>
```

### ModuleDialog (inline sub-component in same file)
```jsx
function ModuleDialog({ open, onClose, onSave, initial, loading }) { ... }
```
Fields:
- `TextField` — Source Name (required, min 2 chars)
- `Select` — Scope (1=Direct, 2=Indirect Energy, 3=Value Chain)

### DeleteConfirmDialog (inline sub-component in same file)
Standard MUI `Dialog` with `DialogContentText` warning, Cancel + Delete (red) buttons.

### CRUD handlers
```js
handleCreate(payload) → createModule(token, { ...payload, org_unit: orgUnit.id }) → reload
handleEdit(payload)   → updateModule(token, editTarget.id, payload) → reload
handleDelete()        → deleteModule(token, moduleToDelete.id) → reload
```

After each CRUD operation: call `load()` to refresh, show `Snackbar`.

---

## Level 2 — `ModuleWorkspacePage.jsx`

### Layout: Three-Column via `EntityDetailShell`

Use `EntityDetailShell` component with `useThreeColumnLayout` pattern (pass `header` + `metricsPanel` props).

```jsx
<EntityDetailShell
  header={<PageHeader ... />}
  mainTabs={[{ label: 'Tables', render: () => <TablesGrid /> }]}
  metricsPanel={<SourceStatusPanel ... />}
  panelWidthKey="moduleWorkspace:panelWidth"
/>
```

### Data Loading
```js
const { moduleId } = useParams();
const { token, context } = useAuth();
const projectId = context?.project_id || context?.projectId;

// Find module from context.modules (already loaded globally — no extra fetch needed)
const module = useMemo(
  () => (context?.modules || []).find(m => String(m.id) === moduleId),
  [context?.modules, moduleId]
);

// Fetch tables for this module
useEffect(() => {
  fetchDataSchemaTables(token, projectId, moduleId).then(setTables);
}, [moduleId, token, projectId]);

// Fetch recent activity
useEffect(() => {
  fetchOwnerActivity({ limit: 8 }, token).then(setActivity);
}, [token]);
```

### Breadcrumbs
```js
[
  { label: 'Home', path: '/dashboard' },
  { label: 'My Data', path: '/carbon/my-data' },
  { label: module?.name || '...' },
]
```

### PageHeader props
```jsx
<PageHeader
  title={module?.name || 'Loading...'}
  subtitle={`${SCOPE_META[module?.scope]?.label} — ${tables.length} tables, ${module?.row_count || 0} rows`}
  breadcrumbs={breadcrumbs}
  badge={SCOPE_META[module?.scope]?.label}
/>
```

### Main Area — Tables Grid

Columns:
```
| Table Name  | Rows | DQ%  | Status   |  (arrow → )
```

Column specs:
- **Table Name**: `flex: 2`, fontWeight 600
- **Rows**: `width: 80`, type number
- **Status**: `width: 120`, computed:
  ```js
  // no rows → 'No Data', else → 'Has Data'
  tbl.row_count === 0 ? <Chip label="No Data" color="default" /> : <Chip label="Has Data" color="success" />
  ```
- **Arrow**: `width: 50`, render `<ChevronRightIcon />` — decorative

Row click:
```js
onRowClick={(params) => navigate(`/carbon/my-data/${moduleId}/${params.row.id}`)}
```

No add/edit/delete actions on tables — that is catalog admin scope. Read-only list only.

If `tables.length === 0` after loading: show `<EmptyState>` with message:
```
"No tables defined for this source yet.
 Contact your administrator to set up data tables."
```

### Right Panel — `SourceStatusPanel` (inline sub-component)

This is ~80 lines. Sections (use MUI `Box`, `Typography`, `Divider`, `Stack`):

**Section 1: Completion Status**
```
Data Completeness
─────────────────
● 2 of 3 tables have data    ← computed from tables array

Tables needing data:
  ⚠ Equipment List (0 rows)  ← tables where row_count === 0
```

**Section 2: DQ Score**
```
Quality Score
─────────────
[linear progress bar]  94%
```
Use MUI `LinearProgress` with `value={module.quality_score || 0}`.
Color: `success` if ≥80, `warning` if ≥60, `error` if <60.

**Section 3: Recent Activity**
```
Recent Activity
───────────────
· 5 rows added — Monthly Invoices    (relative date)
· 2 rows updated — Tariff Records    (relative date)
```
Use `ActivityFeed` component if activity items match its expected shape, otherwise render manually as a simple `Stack` of `Typography` items.

Panel should have `p: 2`, `overflow: 'auto'`, sections separated by `<Divider sx={{ my: 2 }} />`.

---

## Level 3 — `DataEntryPage.jsx` (modify existing)

File: `carbon-frontend/src/pages/DataEntryPage.jsx`

Current code reads `moduleId` and `tableId` from `useParams()` and passes to `TableDataPage`.

**Change**: Also read `moduleId` to construct proper breadcrumbs, and pass them to `TableDataPage` (or wrap it with a `PageHeader`).

```jsx
export default function DataEntryPage() {
  const { moduleId, tableId } = useParams();
  const { user, context } = useAuth();
  const navigate = useNavigate();

  const projectId = context?.project_id || context?.projectId;
  const module = (context?.modules || []).find(m => String(m.id) === String(moduleId));

  if (!user || !context) {
    return <LoadingSkeleton />;
  }

  return (
    <Box>
      <PageHeader
        title="Data Entry"
        subtitle={module?.name || `Module ${moduleId}`}
        breadcrumbs={[
          { label: 'Home', path: '/dashboard' },
          { label: 'My Data', path: '/carbon/my-data' },
          { label: module?.name || '...', path: `/carbon/my-data/${moduleId}` },
          { label: 'Data Entry' },
        ]}
      />
      <TableDataPage
        project_id={projectId}
        module_id={moduleId}
        moduleId={moduleId}
        tableId={tableId}
        lang={context.language || 'en'}
        token={user.token}
      />
    </Box>
  );
}
```

Import `PageHeader`, `LoadingSkeleton` from `../components` and `useNavigate` from `react-router-dom`.

---

## Acceptance Criteria

### Level 1
- [ ] Page loads at `/carbon/my-data`
- [ ] 4 StatCards display correct values from `fetchMyData`
- [ ] Grid shows all modules with correct Scope/Status/DQ chips
- [ ] Search filters by source name (client-side, no API call)
- [ ] Scope dropdown filters the grid
- [ ] Status dropdown filters correctly (active/no_data/low_dq)
- [ ] Clicking a row navigates to `/carbon/my-data/:moduleId`
- [ ] Add Source opens dialog, creates module via API, refreshes grid
- [ ] Edit opens dialog pre-populated, saves via PATCH, refreshes grid
- [ ] Delete shows confirmation dialog, calls deleteModule API, refreshes grid
- [ ] Snackbar shows success/error after each CRUD operation
- [ ] Page shows `EmptyState` when user has 0 modules
- [ ] Page shows `ErrorAlert` when API fails
- [ ] `LoadingSkeleton` shown during initial load

### Level 2
- [ ] Page loads at `/carbon/my-data/:moduleId`
- [ ] Module name and scope shown in PageHeader
- [ ] Breadcrumbs show: Home > My Data > {Source Name}
- [ ] Tables grid lists all tables for the module
- [ ] "No Data" / "Has Data" chips correct
- [ ] Clicking a table row navigates to `/carbon/my-data/:moduleId/:tableId`
- [ ] Right panel shows correct completeness (N of M tables have data)
- [ ] Right panel highlights tables with 0 rows
- [ ] Right panel shows DQ score with LinearProgress
- [ ] Right panel shows recent activity list
- [ ] Right panel is collapsible (toggle button, state persisted to localStorage)
- [ ] `EmptyState` shown when module has no tables
- [ ] `ErrorAlert` or graceful message when module not found

### Level 3
- [ ] Page loads at `/carbon/my-data/:moduleId/:tableId`
- [ ] Breadcrumbs: Home > My Data > {Source} > Data Entry
- [ ] `TableDataPage` renders fully with rows grid
- [ ] Add Row opens `DataRowFormDrawer`
- [ ] Edit, Delete, Import, Export, DQ all work (these come from `TableDataPage` — just verify they still work)
- [ ] View button navigates to `/carbon/data-entry/row/:tableId/:rowId` (already exists)

---

## Code Quality Rules

- No `console.log` left in final code
- No `window.confirm()` — use `Dialog` components instead
- All API errors shown via `Snackbar` with `severity="error"`
- All loading states use existing `LoadingSkeleton` or MUI `CircularProgress`
- No inline style objects — use MUI `sx` prop
- ESLint must pass with 0 errors (warnings acceptable for known issues in other files)
- No unused imports
- `useCallback` on all handlers defined inside components that are passed as props
- `useMemo` for filtered/computed arrays

---

## Patterns to Follow

### Standard grid page pattern (follow exactly)
```jsx
export default function SomePage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setData(await fetchSomething(token)); }
    catch (err) { setError(err.message || 'Failed to load'); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <LoadingSkeleton />;
  if (error) return <ErrorAlert message={error} onRetry={load} />;
  if (!data || data.length === 0) return <EmptyState ... />;

  return ( ... );
}
```

### Snackbar pattern
```js
const [snackbar, setSnackbar] = useState(null);
// show: setSnackbar({ severity: 'success', message: '...' })
// clear: setSnackbar(null)

<Snackbar open={Boolean(snackbar)} autoHideDuration={4000} onClose={() => setSnackbar(null)}
  anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
  <Alert severity={snackbar?.severity || 'info'} variant="filled" onClose={() => setSnackbar(null)}>
    {snackbar?.message}
  </Alert>
</Snackbar>
```

### CarbonDataGrid usage
```jsx
<CarbonDataGrid
  rows={filteredItems}
  columns={columns}
  loading={loading}
  density="compact"
  emptyMessage="No sources found."
  onRowClick={(params) => navigate(`.../${params.row.id}`)}
  pageSize={25}
/>
```

---

## Scope Metadata Constant (use in both Level 1 and Level 2)

Define once at top of each file (not shared — to avoid coupling):

```js
const SCOPE_META = {
  1: { label: 'Scope 1', color: 'error',   shortLabel: 'S1' },
  2: { label: 'Scope 2', color: 'warning', shortLabel: 'S2' },
  3: { label: 'Scope 3', color: 'info',    shortLabel: 'S3' },
};
```

---

## What NOT to Build

- ❌ Do not add table creation/editing (that is Catalog scope)
- ❌ Do not add field management (that is Catalog scope)  
- ❌ Do not show field counts or schema details to the user
- ❌ Do not add a "Go to Catalog" link anywhere in these pages
- ❌ Do not build a split-sidebar-within-sidebar layout
- ❌ Do not duplicate `DataRowFormDrawer` or `TableDataPage` logic
- ❌ Do not use `window.confirm()` or `window.alert()`
- ❌ Do not add navigation away from the app shell (no full-page takeovers)
