# Carbon Domain — Shared Context v1.0

> **Read this first.** Both BE and FE workers must understand this context before any task.

---

## 1. Directory Structure

```
backend/
  emissions/           ← Carbon domain app (THIS IS YOUR SCOPE)
    models.py          ← EmissionFactor, GWP, Calculation, CalculationRule, ReportingPeriod, ReportConfig
    views.py           ← ViewSets + APIViews
    serializers.py     ← DRF serializers
    urls.py            ← URL routing
    admin.py
    api.py             ← Frontend API client functions (used by FE)
  core/models.py       ← Module, Feedback
  catalog/models.py    ← DataDomain, GlossaryTerm, Tag, AssetProfile, GovernanceEvent, GovernancePolicy
  dataschema/models.py ← DataTable, DataField, DataRow, SchemaChangeLog, TableRelation
  mdm/models.py        ← ReferenceSet, ReferenceValue, OrgUnit
  dq/                  ← Data quality engine
  config/urls.py       ← Root URL config: /api/v1/emissions/ → emissions.urls

carbon-frontend/
  src/
    api/
      client.js        ← apiFetch() helper (use this for ALL API calls)
      emissions.js     ← Frontend API functions for emissions endpoints
    auth/
      AuthContext.jsx  ← useAuth() → { user, context, login, logout }
    components/        ← Shared components (Breadcrumbs, NotificationProvider, etc.)
    pages/carbon/      ← Carbon pages
    apps/carbon/
      manifest.js      ← App manifest (roles, nav, ontology)
    utils/
      rbac.js          ← hasRole(), filterMenuItems(), canAccess()
    config.js          ← API_BASE, route definitions
    shell/             ← Shell layout (sidebar, header)
```

---

## 2. Key Models (Emissions App)

### EmissionFactor
```python
class EmissionFactor(models.Model):
    name = CharField
    code = CharField(unique=True)
    category = CharField(choices=[
        'electricity', 'stationary_combustion', 'mobile_combustion',
        'fugitive', 'process', 'transport', 'waste', 'water', 'materials'
    ])
    scope = IntegerField(choices=[(1,'Scope 1'),(2,'Scope 2'),(3,'Scope 3')])
    factor_value = FloatField
    factor_unit = CharField        # e.g., "kg CO2e/kWh"
    activity_unit = CharField      # e.g., "kWh"
    co2_factor = FloatField(null=True)
    ch4_factor = FloatField(null=True)
    n2o_factor = FloatField(null=True)
    country = CharField(null=True)
    country_code = CharField(null=True)
    region = CharField(null=True)
    source = CharField(null=True)
    source_url = URLField(null=True)
    valid_from = DateField(null=True)
    valid_to = DateField(null=True)
    is_active = BooleanField(default=True)
    tags = JSONField(default=list)  # e.g., ["grid", "renewable"]

    def calculate_emissions(self, activity_value):
        return self.factor_value * activity_value
```

### Calculation
```python
class Calculation(models.Model):
    data_row = ForeignKey('dataschema.DataRow', on_delete=SET_NULL, null=True)
    module = ForeignKey('core.Module', on_delete=SET_NULL, null=True)
    emission_factor = ForeignKey(EmissionFactor, on_delete=SET_NULL, null=True)
    activity_value = FloatField
    activity_unit = CharField
    co2e_kg = FloatField
    co2_kg = FloatField(null=True)
    ch4_kg = FloatField(null=True)
    n2o_kg = FloatField(null=True)
    scope = IntegerField
    category = CharField
    reporting_period = ForeignKey(ReportingPeriod, null=True)
    reporting_year = IntegerField(null=True)   # legacy
    reporting_month = IntegerField(null=True)  # legacy
    activity_date = DateField(null=True)
    calculated_by = ForeignKey(settings.AUTH_USER_MODEL, null=True)
    calculation_method = CharField(default='factor')
    calculated_at = DateTimeField(auto_now_add=True)

    @classmethod
    def create_from_data_row(cls, data_row, emission_factor, reporting_period=None):
        # Factory method — use this when creating calculations
```

### ReportingPeriod
```python
class ReportingPeriod(models.Model):
    name = CharField
    start_date = DateField
    end_date = DateField
    period_type = CharField(choices=['annual','quarterly','monthly','custom'])
    status = CharField(choices=['draft','open','locked','submitted','verified','closed'])
    is_baseline = BooleanField(default=False)
    created_by = ForeignKey(settings.AUTH_USER_MODEL, null=True)

    @property
    def duration_days(self): ...
    @property
    def is_active(self):
        return self.status in ['open', 'locked', 'submitted']
```

### CalculationRule
```python
class CalculationRule(models.Model):
    data_table = ForeignKey('dataschema.DataTable')
    activity_field = ForeignKey('dataschema.DataField', related_name='activity_rules')
    date_field = ForeignKey('dataschema.DataField', related_name='date_rules', null=True)
    emission_factor = ForeignKey(EmissionFactor)
    output_field = ForeignKey('dataschema.DataField', related_name='output_rules', null=True)
    rule_type = CharField(choices=['direct','unit_convert','formula'])
    unit_conversion_factor = FloatField(null=True)
    custom_formula = TextField(null=True)
    name = CharField
    is_active = BooleanField(default=True)
    auto_calculate = BooleanField(default=False)

    def calculate_for_row(self, data_row): ...
    def calculate_for_table(self): ...
```

### ReportConfig
```python
class ReportConfig(models.Model):
    name = CharField
    created_by = ForeignKey(settings.AUTH_USER_MODEL)
    reporting_period = ForeignKey(ReportingPeriod, null=True)
    custom_start = DateField(null=True)
    custom_end = DateField(null=True)
    org_unit = ForeignKey('mdm.OrgUnit', null=True)
    ghg_scopes = JSONField(default=list)     # [1, 2, 3]
    categories = JSONField(default=list)     # ['electricity', 'water']
    output_format = CharField(default='json')
    grouping = CharField(default='scope')
    include_dq_status = BooleanField(default=True)
    include_unverified = BooleanField(default=False)
    last_run_at = DateTimeField(null=True)
```

---

## 3. Frontend Unified Component Library

> **CRITICAL RULE**: Never create ad-hoc tables, forms, empty states, or stat cards. Always use these shared components. If a component doesn't exist yet, create it in the library first, then use it.

### Component Map

```
src/
  components/
    DataGrid/
      CarbonDataGrid.jsx          ← THE standard table (EVERY page uses this)
    Cards/
      StatCard.jsx                ← Stat metric display
      WorkflowCard.jsx            ← Navigation/workflow card
    Page/
      PageHeader.jsx              ← Page title + subtitle + breadcrumb + action buttons
      EmptyState.jsx              ← Icon + title + description + CTA
      LoadingSkeleton.jsx         ← Skeleton matching layout
      ErrorAlert.jsx              ← Alert with retry button
    Layout/
      TabPanel.jsx                ← Tab container with consistent styling
      RightPanel.jsx              ← Collapsible/resizable entity metadata panel
    Feedback/
      PeriodBanner.jsx            ← Active period status bar
      ActivityFeed.jsx            ← Compact timeline
    Form/
      SaveBar.jsx                 ← Bottom-pinned Cancel + Save
      FormField.jsx               ← Standard field wrapper (label above, size=small)
```

### 3.1 CarbonDataGrid — THE Standard Table

**Every table in Carbon uses this component.** No exceptions.

```jsx
import CarbonDataGrid from '../../components/DataGrid/CarbonDataGrid';

<CarbonDataGrid
  columns={columns}           // Array of column defs (see below)
  rows={rows}                 // Array of data objects
  loading={loading}           // Boolean — shows skeleton rows
  error={error}               // String — shows error state
  emptyMessage="No data found"
  searchPlaceholder="Search..."
  onRowClick={(row) => ...}   // Opens right panel
  filterControls={<>{/* Optional filter chips/dropdowns above table */}</>}
  totalCount={total}          // For server-side pagination
  page={page}
  pageSize={20}
  onPageChange={setPage}
  onPageSizeChange={setPageSize}
  sortField="name"
  sortDirection="asc"
  onSortChange={(field, dir) => ...}
  selectable={false}          // Enable row selection
  onSelectionChange={(selectedIds) => ...}
/>
```

**Column definition:**
```javascript
const columns = [
  {
    field: 'name',            // data key
    headerName: 'Module Name',// display header
    width: 200,               // default width in px
    minWidth: 120,
    maxWidth: 400,
    sortable: true,           // shows sort arrow on click
    resizable: true,          // user can drag to resize
    hideable: true,           // can be hidden via column menu
    render: (value, row) => ...,  // custom cell render
    // Actions column (always last):
    actions: [
      { icon: <EditIcon fontSize="small" />, tooltip: 'Edit', onClick: (row) => ... },
      { icon: <DeleteIcon fontSize="small" />, tooltip: 'Delete', onClick: (row) => ... },
    ]
  }
];
```

**Features provided automatically:**
- ✅ Pagination (bottom, MUI TablePagination)
- ✅ Sortable headers (click to toggle asc/desc/none)
- ✅ Resizable columns (drag right border)
- ✅ Show/hide columns (gear icon menu at top-right)
- ✅ Hover row highlight (light blue background)
- ✅ Selected row highlight (blue background)
- ✅ Search bar (top-left, filters rows client-side or triggers onSearch)
- ✅ Filter chips row (top, between search and table)
- ✅ Loading skeleton (5 rows of pulsing cells)
- ✅ Error state (Alert inside table area)
- ✅ Empty state (icon + message)
- ✅ Sticky header
- ✅ Compact density (size="small", 24px rows)
- ✅ Striped rows (alternating light gray)
- ✅ Last column reserved for action icons (16px, subtle)

### 3.2 StatCard

```jsx
import StatCard from '../../components/Cards/StatCard';

<StatCard
  label="Total Emissions"
  value="2,670"
  unit="tCO₂e"
  color="primary"             // primary | success | info | warning | error | secondary
  icon={<TrendingUpIcon />}
  sparkline={[12, 15, 13, 18, 14]}  // Optional tiny trend line
  trend="+12%"                // Optional trend indicator
  trendDirection="up"         // up | down | neutral
  onClick={() => ...}         // Optional — makes card clickable
/>
```

### 3.3 WorkflowCard

```jsx
import WorkflowCard from '../../components/Cards/WorkflowCard';

<WorkflowCard
  title="Emissions Dashboard"
  description="View trends, scope breakdowns, and comparisons"
  icon={<DashboardIcon />}
  color="primary"
  onClick={() => navigate('/carbon/dashboard')}
  disabled={false}
  badge="New"                 // Optional chip
  adminOnly={false}           // Shows "Admin" chip if true
/>
```

### 3.4 PageHeader

```jsx
import PageHeader from '../../components/Page/PageHeader';

<PageHeader
  title="Carbon Console"
  subtitle="Manage organizational carbon emissions"
  breadcrumbs={[{ label: 'Home', path: '/' }, { label: 'Carbon' }]}
  actions={<Button size="small">New Report</Button>}
  badge={<Chip label="Admin" size="small" color="error" />}
/>
```

### 3.5 EmptyState

```jsx
import EmptyState from '../../components/Page/EmptyState';

<EmptyState
  icon={<InboxIcon />}
  title="No modules configured"
  description="Contact your administrator to set up emission source modules."
  action={<Button size="small">Learn More</Button>}
/>
```

### 3.6 LoadingSkeleton

```jsx
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';

// Auto-detects layout: card-grid | table | detail
<LoadingSkeleton variant="card-grid" count={6} columns={3} />
<LoadingSkeleton variant="table" rows={5} />
<LoadingSkeleton variant="detail" />
```

### 3.7 ErrorAlert

```jsx
import ErrorAlert from '../../components/Page/ErrorAlert';

<ErrorAlert
  message="Failed to load dashboard data"
  onRetry={() => loadData()}
/>
```

### 3.8 PeriodBanner

```jsx
import PeriodBanner from '../../components/Feedback/PeriodBanner';

<PeriodBanner
  period={activePeriod}       // { id, name, start_date, end_date, status, days_remaining }
  // Auto-handles: active (info), no period (warning), locked (error)
/>
```

### 3.9 ActivityFeed

```jsx
import ActivityFeed from '../../components/Feedback/ActivityFeed';

<ActivityFeed
  items={recentActivity}      // [{ id, action, module_name, timestamp, detail }]
  maxItems={5}
  emptyMessage="No recent activity"
/>
```

### 3.10 TabPanel

```jsx
import TabPanel from '../../components/Layout/TabPanel';

const [tab, setTab] = useState(0);

<Tabs value={tab} onChange={(e, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
  <Tab label="My Modules" />
  <Tab label="Emission Sources" />
</Tabs>
<TabPanel value={tab} index={0}>
  <ModuleContent />
</TabPanel>
<TabPanel value={tab} index={1}>
  <SourcesContent />
</TabPanel>
```

### 3.11 RightPanel — Entity Metadata Sidebar

```jsx
import RightPanel from '../../components/Layout/RightPanel';

<RightPanel
  open={selectedRow !== null}
  onClose={() => setSelectedRow(null)}
  width={360}                 // Default, user-resizable
  minWidth={280}
  maxWidth={600}
  title="Module Details"
  sections={[
    { label: 'Overview', content: <OverviewTab /> },
    { label: 'Lineage', content: <LineageTab /> },
    { label: 'DQ Score', content: <DQTab /> },
    { label: 'Audit Trail', content: <AuditTab /> },
  ]}
/>
```

### 3.12 SaveBar

```jsx
import SaveBar from '../../components/Form/SaveBar';

<SaveBar
  onSave={handleSave}
  onCancel={handleCancel}
  loading={saving}
  dirty={isDirty}
  saveLabel="Save Changes"
/>
```

---

## 4. Frontend API Patterns

// GET
const data = await apiFetch('/api/v1/emissions/dashboard/');

// POST
const result = await apiFetch('/api/v1/emissions/calculate/', {
  method: 'POST',
  body: JSON.stringify({ module_id: 1, period_id: 2 })
});
```

### Auth/RBAC (ALWAYS use this pattern)
```javascript
import { useAuth } from '../../auth/AuthContext';

const { user, context } = useAuth();
const isAdmin = user?.is_superuser || context?.available_perspectives?.includes('admin');
const orgUnits = context?.org_units || [];
```

### Component Structure (follow this)
```javascript
// src/pages/carbon/NewPage.jsx
import React, { useState, useEffect } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { apiFetch } from '../../api/client';
import { Box, Typography, ... } from '@mui/material';

export default function NewPage() {
  const { context, user } = useAuth();
  const { showNotification } = useNotification();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await apiFetch('/api/v1/emissions/...');
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <CircularProgress />;
  if (error) return <Alert severity="error">{error}</Alert>;

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      {/* Page content */}
    </Container>
  );
}
```

### MUI Density (ALWAYS compact)
```jsx
<Table size="small" />
<TextField size="small" />
<Button size="small" />
<Chip size="small" />
<Card sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 2 }} />
```

---

## 5. Existing APIs (Emissions)

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/emissions/dashboard/` | Dashboard aggregations |
| GET | `/api/v1/emissions/owner-dashboard/` | Data owner dashboard |
| GET | `/api/v1/emissions/owner/summary/` | Owner summary stats |
| GET | `/api/v1/emissions/owner/assets/` | Owner emission sources |
| GET | `/api/v1/emissions/owner/activity/` | Owner activity data |
| GET | `/api/v1/emissions/yearly-comparison/` | YoY comparison |
| GET | `/api/v1/emissions/report/` | Generate report |
| POST | `/api/v1/emissions/calculate/` | Trigger calculation |
| CRUD | `/api/v1/emissions/periods/` | Reporting periods |
| CRUD | `/api/v1/emissions/factors/` | Emission factors |
| CRUD | `/api/v1/emissions/gwp/` | GWP values |
| CRUD | `/api/v1/emissions/calculations/` | Calculations |
| CRUD | `/api/v1/emissions/rules/` | Calculation rules |
| CRUD | `/api/v1/emissions/report-configs/` | Report configs |

---

## 6. Auth Context Shape

```javascript
// user object
{
  id, username, email, is_superuser, is_staff
}

// context object (from /accounts/me/context/)
{
  available_perspectives: ['carbon-admin', 'carbon:data_owner'],  // or ['carbon:analyst']
  org_units: [{ id, name, code, org_type }],
  default_perspective: 'carbon-admin'
}
```

---

## 7. Key Conventions

- **File naming**: PascalCase for components, camelCase for utilities, snake_case for Python
- **Imports order**: React → MUI → icons → local components → api → utils
- **CSS**: MUI `sx` prop only; never create .css files
- **Icons**: @mui/icons-material only
- **Colors**: `theme.palette.primary.main` etc.; never hardcode colors
- **Dates**: Use `new Date().toLocaleDateString()` or moment if already imported
- **Numbers**: `new Intl.NumberFormat().format()` for display
- **Fetch state**: loading | error | empty | data — always handle all 4

---

## 8. Quick Commands

```bash
# Backend
cd /home/ahmed/aast/carbon/backend
python manage.py test emissions        # Run emissions tests
python manage.py test --verbosity=2    # Detailed output

# Frontend
cd /home/ahmed/aast/carbon/carbon-frontend
npm run build                          # Production build
npm run dev                            # Dev server

# Full system
cd /home/ahmed/aast/carbon
./manage.sh start                      # Start both BE+FE
./manage.sh status                     # Check status
```
