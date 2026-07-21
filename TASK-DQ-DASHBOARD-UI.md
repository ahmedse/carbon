# TASK: Data Quality Dashboard UI (Frontend Integration)

**Status:** Ready for frontend worker execution  
**Track:** Frontend Integration (Parallel with Track E)  
**Dependencies:** Track A (DQ Execution) backend APIs complete  
**Estimated Scope:** Medium-High complexity, 4 UI components

---

## Context

The Data Trust Core backend has **complete Data Quality (DQ) functionality** from Track A:
- ✅ **11 API endpoints** for profiling, rule execution, metrics, history
- ✅ **6 rule types**: not_null, unique, allowed_values, range, regex, reference_integrity
- ✅ **Swagger documentation** at `/api/swagger/`
- ✅ **Catalog integration**: AssetProfile quality_status/quality_score auto-updated

**Current Frontend State:**
- ✅ Basic DQ API client exists: [`carbon-frontend/src/api/dq.js`](carbon-frontend/src/api/dq.js:1-220)
- ✅ Unified UI patterns established: MUI DataGrid + BaseDetailPage
- ⚠️ **No user-facing DQ dashboard** — APIs not accessible via UI
- ⚠️ **Quality metrics hidden** — Users can't see quality scores or trigger profiling

**User's Strategic Request:**
> "go Recommendation: DQ Dashboard UI (Option 1)"

**Parallel Execution:** Backend worker executes Track E (Operational Excellence) simultaneously

---

## Objectives

1. **DQ Dashboard:** Create overview page showing org-level quality metrics and recent results
2. **DQ Rule Management:** UI for CRUD operations on DQ rules with execution triggers
3. **Quality Integration:** Enhance existing Asset pages with quality indicators and history
4. **User Actions:** Enable users to trigger profiling and view results without API knowledge

---

## Deliverables

### **UI1: DQ Dashboard Page (`/catalog/dq-dashboard`)**

**Goal:** Provide executives and data stewards with org-level data quality visibility.

#### Page Layout

**Header Section:**
- Title: "Data Quality Dashboard"
- Subtitle: Organization name + date range selector
- Refresh button (manual reload)

**Metrics Cards (Top Row):**
```
┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐
│ Quality Score    │ Rules Passing    │ Tables Profiled  │ Failed Checks    │
│                  │                  │                  │                  │
│   85/100         │   42/50 (84%)   │   156 tables    │   8 critical    │
│   [Green Gauge]  │   [Progress Bar] │   [Count]       │   [Red Badge]   │
└──────────────────┴──────────────────┴──────────────────┴──────────────────┘
```

**Recent DQ Results Table (Main Content):**
- MUI DataGrid showing last 50 DQ results
- Columns: Rule Name, Table, Executed At, Status (Pass/Fail), Failed Rows, Actions
- Filters: Status (all/pass/fail), Date range, Table
- Sort: Default to `-executed_at` (newest first)
- Row click: Navigate to result detail

**Quick Actions Panel (Sidebar or Bottom):**
- Button: "Profile All Tables" → Triggers `POST /dq/profile/bulk/`
- Button: "Run All Rules" → Triggers `POST /dq/run/` for org
- Status: Show loading spinner when operations in progress

#### API Integration

**Data Sources:**
- `GET /dq/metrics/` → Metrics cards data
- `GET /dq/results/?limit=50&ordering=-executed_at` → Recent results table

**Actions:**
- `POST /dq/profile/bulk/` → Profile multiple tables
- `POST /dq/run/` → Run rules across org

#### Implementation Pattern

**File:** `carbon-frontend/src/pages/catalog/DQDashboardPage.jsx`

```jsx
import React, { useState, useEffect } from 'react';
import { Box, Grid, Card, CardContent, Typography, CircularProgress, Button } from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import { useAuth } from '../../contexts/AuthContext';
import { getOrgDQMetrics, getDQResults, profileTables, runDQValidation } from '../../api/dq';
import { carbonTheme } from '../../styles/carbonTheme';

export default function DQDashboardPage() {
  const { token } = useAuth();
  const [metrics, setMetrics] = useState(null);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    loadData();
  }, []);
  
  const loadData = async () => {
    setLoading(true);
    try {
      const [metricsData, resultsData] = await Promise.all([
        getOrgDQMetrics(token),
        getDQResults(token, { limit: 50, ordering: '-executed_at' })
      ]);
      setMetrics(metricsData);
      setResults(resultsData.results || resultsData);
    } catch (error) {
      console.error('Failed to load DQ data:', error);
    }
    setLoading(false);
  };
  
  const handleProfileAll = async () => {
    // Trigger bulk profiling
  };
  
  const columns = [
    { field: 'rule_name', headerName: 'Rule', width: 200 },
    { field: 'table_name', headerName: 'Table', width: 200 },
    {
      field: 'passed',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => (
        <Chip
          label={params.value ? 'PASS' : 'FAIL'}
          color={params.value ? 'success' : 'error'}
          size="small"
        />
      )
    },
    { field: 'failed_rows', headerName: 'Failed Rows', width: 130 },
    { field: 'executed_at', headerName: 'Executed', width: 180 },
  ];
  
  return (
    <Box sx={{ p: 3 }}>
      {/* Metrics Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard title="Quality Score" value={metrics?.quality_score || 0} />
        </Grid>
        {/* ... more metric cards */}
      </Grid>
      
      {/* Results Table */}
      <Card>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2 }}>Recent DQ Results</Typography>
          <DataGrid
            rows={results}
            columns={columns}
            pageSize={25}
            autoHeight
            loading={loading}
          />
        </CardContent>
      </Card>
    </Box>
  );
}
```

**Acceptance Criteria:**
- [ ] Metrics cards load from `GET /dq/metrics/` within 2s
- [ ] Results table shows last 50 DQ runs with pass/fail status
- [ ] Clicking row navigates to result detail page
- [ ] "Profile All Tables" button triggers bulk profiling with loading indicator
- [ ] Page refreshes data when bulk operation completes
- [ ] Responsive layout (cards stack on mobile)

---

### **UI2: DQ Rules Management Page (`/catalog/dq-rules`)**

**Goal:** Enable data stewards to create, edit, and execute DQ rules.

#### Page Layout

**Rules List (Main Content):**
- MUI DataGrid showing all DQ rules
- Columns: Rule Name, Type, Target Table/Field, Severity, Active, Last Run, Actions
- Filters: Rule type, Severity, Active status
- Search: Rule name
- Row actions: Edit, Execute, View History, Delete

**Create Rule Button (Top Right):**
- Opens modal/drawer for rule creation
- Form fields:
  - Name (text input)
  - Description (textarea)
  - Rule Type (dropdown: not_null, unique, allowed_values, range, regex, reference_integrity)
  - Target Table (dropdown from `/dataschema/tables/`)
  - Target Field (dropdown from table fields)
  - Severity (dropdown: info, warning, error, critical)
  - Parameters (dynamic based on rule type)
  - Active (checkbox)

**Rule Detail Drawer:**
- Opens when clicking row or "View History"
- Tabs:
  - Overview: Rule config, created by, updated at
  - Execution History: Chart + table from `GET /dq/rules/{id}/history/`
  - Failed Samples: If last run failed, show sample rows

#### API Integration

**Data Sources:**
- `GET /dq/rules/` → Rules list
- `GET /dq/rules/{id}/history/` → Execution trend
- `GET /dq/results/{id}/failures/` → Sample failed rows

**Actions:**
- `POST /dq/rules/` → Create rule
- `PATCH /dq/rules/{id}/` → Update rule
- `DELETE /dq/rules/{id}/` → Delete rule
- `POST /dq/rules/{id}/execute/` → Run single rule

#### Dynamic Rule Parameters Form

**Example: allowed_values rule:**
```jsx
{ruleType === 'allowed_values' && (
  <TextField
    label="Allowed Values (comma-separated)"
    helperText="e.g., red,green,blue"
    value={params.allowed_values}
    onChange={(e) => setParams({
      ...params,
      allowed_values: e.target.value.split(',').map(v => v.trim())
    })}
  />
)}

{ruleType === 'range' && (
  <>
    <TextField label="Min Value" type="number" value={params.min} />
    <TextField label="Max Value" type="number" value={params.max} />
  </>
)}

{ruleType === 'regex' && (
  <TextField
    label="Pattern"
    helperText="e.g., ^[A-Z]{3}-\\d{4}$ for ABC-1234"
    value={params.pattern}
  />
)}
```

**Acceptance Criteria:**
- [ ] Rules list loads all rules from `GET /dq/rules/`
- [ ] Create rule form validates required fields before submit
- [ ] Rule type dropdown dynamically shows params form
- [ ] Execute button triggers `POST /dq/rules/{id}/execute/` with loading state
- [ ] Execution history chart shows pass/fail trend (last 10 runs)
- [ ] Failed samples table shows max 10 example rows with field values
- [ ] Delete rule shows confirmation dialog

---

### **UI3: Asset Quality Tab (Extend AssetDetailPage)**

**Goal:** Integrate quality metrics into existing asset detail pages.

#### Enhancement to [`AssetDetailPage.jsx`](carbon-frontend/src/pages/catalog/AssetDetailPage.jsx:28-147)

**Add "Quality" Tab:**
```jsx
mainTabs={[
  { label: 'Overview', value: 'overview' },
  { label: 'Edit', value: 'edit' },
  { label: 'Quality', value: 'quality' },  // NEW
  { label: 'Audit', value: 'audit' },
]}
```

**Quality Tab Content (`tabs/AssetQualityTab.jsx`):**

**Quality Score Badge (Top):**
```
┌─────────────────────────────────────────────────┐
│ Quality Score: 85/100                           │
│ [████████░░] Green                             │
│ Status: GOOD | Last Profiled: 2026-07-20      │
└─────────────────────────────────────────────────┘
```

**Rules Applied to This Asset:**
- Table showing rules targeting this table
- Columns: Rule Name, Type, Last Run, Status, Failed Rows
- Click row to see failures

**Profiling Metrics (if profiled):**
- Table of field-level metrics from `GET /dq/table-profiles/?data_table={id}`
- Metrics: completeness, uniqueness, validity
- Chart showing quality trend over time

**Quick Actions:**
- Button: "Profile Now" → Triggers `POST /dq/profile/` for this table
- Button: "Run Rules" → Triggers `POST /dq/run/?table_id={id}`

#### API Integration

**Data Sources:**
- `GET /dq/metrics/table/{tableId}/` → Quality score, status
- `GET /dq/results/?data_table={tableId}&limit=20` → Recent rule runs
- `GET /dq/table-profiles/?data_table={tableId}` → Profiling metrics

**Actions:**
- `POST /dq/profile/` with `{data_table_id: tableId}` → Profile this table
- `POST /dq/run/` with `{data_table_id: tableId}` → Run rules for table

**Acceptance Criteria:**
- [ ] Quality tab appears when asset has associated data_table
- [ ] Quality score badge shows current score from catalog AssetProfile
- [ ] Rules table lists only rules targeting this table
- [ ] Profiling metrics show field-level completeness/uniqueness
- [ ] "Profile Now" button triggers profiling with loading state
- [ ] After profiling, metrics refresh automatically
- [ ] Failed rows link navigates to failures detail

---

### **UI4: Quality Indicators (Integrate into Existing Pages)**

**Goal:** Surface quality scores throughout the catalog UI without dedicated pages.

#### Enhancement to [`AssetsPage.jsx`](carbon-frontend/src/pages/catalog/AssetsPage.jsx:110-414)

**Add Quality Column to DataGrid:**
```jsx
{
  field: 'quality_status',
  headerName: 'Quality',
  width: 150,
  renderCell: (params) => (
    <QualityStatusBadge
      value={params.row.quality_status}
      score={params.row.quality_score}
    />
  )
}
```

**QualityStatusBadge Component:**
```jsx
// carbon-frontend/src/components/QualityStatusBadge.jsx
import { Chip, Tooltip } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningIcon from '@mui/icons-material/Warning';
import ErrorIcon from '@mui/icons-material/Error';

export default function QualityStatusBadge({ value, score }) {
  const config = {
    excellent: { color: 'success', icon: <CheckCircleIcon />, label: 'Excellent' },
    good: { color: 'success', icon: <CheckCircleIcon />, label: 'Good' },
    fair: { color: 'warning', icon: <WarningIcon />, label: 'Fair' },
    poor: { color: 'error', icon: <ErrorIcon />, label: 'Poor' },
    unknown: { color: 'default', icon: null, label: 'Not Profiled' },
  };
  
  const { color, icon, label } = config[value] || config.unknown;
  
  return (
    <Tooltip title={`Quality Score: ${score || 'N/A'}/100`}>
      <Chip
        icon={icon}
        label={label}
        color={color}
        size="small"
        sx={{ fontWeight: 'medium' }}
      />
    </Tooltip>
  );
}
```

**Add Quality Filter:**
```jsx
filterDefs={[
  // ... existing filters
  {
    field: 'quality_status',
    label: 'Quality Status',
    type: 'select',
    options: [
      { value: 'excellent', label: 'Excellent' },
      { value: 'good', label: 'Good' },
      { value: 'fair', label: 'Fair' },
      { value: 'poor', label: 'Poor' },
      { value: 'unknown', label: 'Not Profiled' },
    ]
  }
]}
```

**Acceptance Criteria:**
- [ ] Quality badge appears in Assets list grid
- [ ] Badge color reflects status: green (excellent/good), yellow (fair), red (poor), gray (unknown)
- [ ] Tooltip shows numeric score on hover
- [ ] Quality filter works in Assets page
- [ ] Badge component reusable across pages

---

## Implementation Guidelines

### Technology Stack (Existing)
- React 18
- Material-UI (MUI) v5
- React Router v6
- MUI X DataGrid
- dayjs (date formatting)
- Existing API client: [`carbon-frontend/src/api/dq.js`](carbon-frontend/src/api/dq.js)

### Component Reuse Patterns

**From [`AssetsPage.jsx`](carbon-frontend/src/pages/catalog/AssetsPage.jsx:110-414):**
- MUI DataGrid configuration
- Filter bar pattern
- Loading states with CircularProgress
- Notification system (toast/snackbar)

**From [`AssetDetailPage.jsx`](carbon-frontend/src/pages/catalog/AssetDetailPage.jsx:28-147):**
- BaseDetailPage wrapper with tabs
- Tab panel switching logic
- Breadcrumb navigation

**From [`MDMPage.jsx`](carbon-frontend/src/pages/catalog/MDMPage.jsx:62-758):**
- TabPanel component
- Modal form pattern (for create rule)
- Data refresh after mutations

### Routing Configuration

**Add to [`CatalogRoutes.jsx`](carbon-frontend/src/pages/catalog/CatalogRoutes.jsx:18-49):**
```jsx
export const catalogRoutes = [
  // ... existing routes
  {
    path: 'dq-dashboard',
    element: <DQDashboardPage />,
    label: 'Data Quality',
  },
  {
    path: 'dq-rules',
    element: <DQRulesPage />,
    label: 'DQ Rules',
  },
];
```

### API Client Extensions

**Existing functions in [`carbon-frontend/src/api/dq.js`](carbon-frontend/src/api/dq.js:1-220):**
- ✅ `getOrgDQMetrics(token)` — Dashboard metrics
- ✅ `getTableDQMetrics(tableId, token)` — Table quality score
- ✅ `getDQResults(token, filters)` — Results list
- ✅ `getDQRules(token, filters)` — Rules list
- ✅ `createDQRule(token, data)` — Create rule
- ✅ `executeDQRule(token, id)` — Run rule
- ✅ `runTableValidation(token, tableId)` — Profile + run rules

**New functions needed:**
```javascript
// carbon-frontend/src/api/dq.js

export async function getRuleHistory(ruleId, token) {
  return apiFetch(`${API_BASE_URL}dq/rules/${ruleId}/history/`, {
    method: 'GET',
    token,
  });
}

export async function getResultFailures(resultId, token) {
  return apiFetch(`${API_BASE_URL}dq/results/${resultId}/failures/`, {
    method: 'GET',
    token,
  });
}

export async function profileTable(tableId, token) {
  return apiFetch(`${API_BASE_URL}dq/profile/`, {
    method: 'POST',
    token,
    body: { data_table_id: tableId },
  });
}

export async function bulkProfileTables(tableIds, token) {
  return apiFetch(`${API_BASE_URL}dq/profile/bulk/`, {
    method: 'POST',
    token,
    body: { table_ids: tableIds },
  });
}
```

### Styling Guidelines

**Use carbonTheme.js palette:**
```javascript
import { carbonTheme } from '../../styles/carbonTheme';

// Quality status colors
const qualityColors = {
  excellent: carbonTheme.palette.success.main,
  good: carbonTheme.palette.success.light,
  fair: carbonTheme.palette.warning.main,
  poor: carbonTheme.palette.error.main,
  unknown: carbonTheme.palette.grey[400],
};
```

**Consistent spacing:**
- Page padding: `sx={{ p: 3 }}`
- Card spacing: `spacing={3}` in Grid containers
- Section margins: `sx={{ mb: 4 }}`

### Testing Protocol

**Manual Browser Testing:**
1. **Dashboard Load:**
   - Navigate to `/catalog/dq-dashboard`
   - Verify metrics cards display numeric values
   - Verify results table loads without errors
   - Check responsive layout on mobile (cards stack vertically)

2. **Rule Creation:**
   - Click "Create Rule" button
   - Select rule type "not_null"
   - Select target table + field
   - Submit form
   - Verify rule appears in list
   - Click "Execute" → verify loading state → verify result appears

3. **Rule History:**
   - Click rule row to open detail drawer
   - Verify "Execution History" tab shows chart
   - Chart should plot pass/fail trend over last 10 runs
   - Verify table below chart matches API response

4. **Asset Quality Tab:**
   - Navigate to existing asset detail (`/catalog/assets/{id}`)
   - Click "Quality" tab
   - Verify quality score badge matches catalog value
   - Click "Profile Now" → verify loading → verify metrics update

5. **Quality Badge Integration:**
   - Go to `/catalog/assets`
   - Verify "Quality" column appears in grid
   - Badges should show colors: green (excellent/good), yellow (fair), red (poor)
   - Hover badge → verify tooltip shows numeric score

**Integration Testing:**
- Test with empty state (no DQ results) → should show "No data" message
- Test error handling (API 500) → should show error toast
- Test with 1000+ results → DataGrid pagination works
- Test concurrent operations (profile + run rules) → loading states independent

### File Modification Checklist

**Files to Create:**
- [ ] `carbon-frontend/src/pages/catalog/DQDashboardPage.jsx`
- [ ] `carbon-frontend/src/pages/catalog/DQRulesPage.jsx`
- [ ] `carbon-frontend/src/pages/catalog/tabs/AssetQualityTab.jsx`
- [ ] `carbon-frontend/src/components/QualityStatusBadge.jsx`
- [ ] `carbon-frontend/src/components/DQRuleForm.jsx` (modal for create/edit)
- [ ] `carbon-frontend/src/components/ExecutionHistoryChart.jsx`

**Files to Modify:**
- [ ] `carbon-frontend/src/api/dq.js` — Add new API functions (4 total)
- [ ] `carbon-frontend/src/pages/catalog/CatalogRoutes.jsx` — Add DQ routes
- [ ] `carbon-frontend/src/pages/catalog/AssetDetailPage.jsx` — Add Quality tab
- [ ] `carbon-frontend/src/pages/catalog/AssetsPage.jsx` — Add Quality column + filter

**No Changes Required:**
- Existing API client structure ([`carbon-frontend/src/api/dq.js`](carbon-frontend/src/api/dq.js) already has base functions)
- Backend APIs (all complete from Track A)
- Routing infrastructure (React Router already configured)

---

## Out of Scope (Deferred to Future)

**Explicitly NOT part of this task:**
- ❌ Real-time DQ monitoring (WebSocket/SSE) — Phase 2
- ❌ Custom rule builder (drag-and-drop logic) — Phase 3
- ❌ Automated remediation actions — Phase 3
- ❌ ML-based anomaly detection — Phase 3
- ❌ DQ reports export (PDF/Excel) — Future enhancement
- ❌ Email notifications on quality degradation — Phase 2
- ❌ SLA/SLO tracking for quality — Phase 3

---

## Success Criteria

**Frontend Integration complete when:**
- [ ] DQ Dashboard loads metrics from `GET /dq/metrics/` within 2s
- [ ] Users can create DQ rules via UI (all 6 rule types supported)
- [ ] Users can execute rules and see results immediately
- [ ] Asset detail pages show quality tab with profiling metrics
- [ ] Quality badges appear in Assets list with color coding
- [ ] All 4 UI components responsive on desktop + mobile
- [ ] Error handling: API failures show user-friendly toast messages
- [ ] Loading states: All async operations show spinner/skeleton
- [ ] Browser testing: Works in Chrome, Firefox, Safari (latest versions)

---

## Deliverable Artifacts

Upon completion, provide:

1. **TASK-RESULT-DQ-DASHBOARD-UI.md** — Completion report with:
   - Summary of implemented components
   - Files created/modified (line counts)
   - Screenshots of all 4 UI components
   - Browser testing results (compatibility matrix)
   - Known limitations or browser-specific issues

2. **Code Changes:**
   - React components (pages + shared)
   - API client extensions
   - Route configuration
   - CSS/styling additions

3. **Testing Evidence:**
   - Screenshots: Dashboard, Rules page, Asset Quality tab, Quality badges
   - Video walkthrough: Create rule → Execute → View results (optional)
   - Browser compatibility test results

---

## References

- [`carbon-frontend/src/api/dq.js`](carbon-frontend/src/api/dq.js:1-220) — Existing DQ API client
- [`carbon-frontend/src/pages/catalog/AssetsPage.jsx`](carbon-frontend/src/pages/catalog/AssetsPage.jsx:110-414) — MUI DataGrid pattern
- [`carbon-frontend/src/pages/catalog/AssetDetailPage.jsx`](carbon-frontend/src/pages/catalog/AssetDetailPage.jsx:28-147) — BaseDetailPage + tabs pattern
- [`carbon-frontend/src/pages/catalog/MDMPage.jsx`](carbon-frontend/src/pages/catalog/MDMPage.jsx:62-758) — Modal form pattern
- Swagger API docs: `http://localhost:8000/api/v1/swagger/` (DQ section)
- MUI DataGrid docs: https://mui.com/x/react-data-grid/
- MUI X Charts: https://mui.com/x/react-charts/

---

**END OF TASK SPECIFICATION**
