# TASK: Carbon App Architecture Fixes

**Status:** Ready for Implementation  
**Priority:** P0 (Blocking Production)  
**Estimated Effort:** Backend 4-6 hours, Frontend 6-8 hours  
**Context:** Based on audit findings in [`plans/CARBON_APP_CRITICAL_AUDIT.md`](plans/CARBON_APP_CRITICAL_AUDIT.md)

---

## Objective

Fix critical architectural issues in the Carbon Footprint app identified during audit:
1. ReportingPeriod UI/model mismatch
2. Data Owner pages violating domain isolation (depend on Catalog APIs)
3. Data Entry Hub namespace confusion

**Note on RBAC:** Keep `role: '*'` for all items during development. Ahmed needs unrestricted access. RBAC will be hardened post-MVP.

---

## Worker Split

- **Worker 1 (Backend):** Create emissions-specific APIs for Data Owner pages
- **Worker 2 (Frontend):** Fix ReportingPeriod UI, refactor Data Owner pages, resolve Data Entry Hub namespace

---

# WORKER 1: Backend — Data Owner API Isolation

## Context

Data Owner pages currently call Catalog APIs (`fetchDataDomains`, `fetchAssetProfiles`, `fetchGovernanceEvents`). This violates domain isolation. Need to create **emissions-specific endpoints** that return org-unit-scoped emissions data.

## Acceptance Criteria

- [ ] Data Owner backend endpoints return emissions-relevant data only
- [ ] All endpoints respect org unit scoping (use `get_visible_org_units()`)
- [ ] Endpoints are optimized (no N+1 queries)
- [ ] Proper error handling and permission checks
- [ ] Swagger docs updated

---

## G1: Create Data Owner Summary Endpoint

**File:** `backend/emissions/views.py`

### G1.1 — Add `OwnerSummaryAPIView`

Create new view class after `OwnerDashboardAPIView` (around line 820):

```python
class OwnerSummaryAPIView(APIView):
    """
    GET /api/v1/emissions/owner/summary/
    
    Returns high-level summary for data owner portal landing page.
    
    Response:
    {
        "org_unit": {
            "id": 1,
            "name": "Faculty of Engineering",
            "code": "ENG"
        },
        "modules": [
            {
                "id": 5,
                "name": "Electricity - Main Campus",
                "scope": 2,
                "table_name": "electricity_consumption"
            }
        ],
        "summary": {
            "total_modules": 3,
            "modules_with_data": 2,
            "latest_submission": "2025-01-15T10:30:00Z",
            "data_quality": {
                "passing": 5,
                "warning": 2,
                "failing": 1
            }
        }
    }
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Get user's org units
        org_units = get_visible_org_units(user)
        if not org_units:
            return Response({
                'org_unit': None,
                'modules': [],
                'summary': {
                    'total_modules': 0,
                    'modules_with_data': 0,
                    'latest_submission': None,
                    'data_quality': {'passing': 0, 'warning': 0, 'failing': 0}
                }
            })
        
        # For now, use first org unit (future: support multi-org)
        org_unit = org_units[0]
        
        # Get modules for this org unit
        from core.models import Module
        modules = Module.objects.filter(
            org_unit=org_unit
        ).select_related('org_unit').order_by('name')
        
        # Count modules with data
        modules_with_data = 0
        for module in modules:
            # Check if module's table has any rows
            table = module.get_table()
            if table and table.rows.exists():
                modules_with_data += 1
        
        # Get latest submission timestamp
        from dataschema.models import DataRow
        latest_row = DataRow.objects.filter(
            table__module__org_unit=org_unit
        ).order_by('-created_at').first()
        
        latest_submission = latest_row.created_at if latest_row else None
        
        # Get data quality summary (stub for now, will connect to DQ system later)
        dq_summary = {
            'passing': 0,
            'warning': 0,
            'failing': 0
        }
        
        # Serialize response
        module_data = [{
            'id': m.id,
            'name': m.name,
            'scope': m.scope,
            'table_name': m.table_name
        } for m in modules]
        
        return Response({
            'org_unit': {
                'id': org_unit.id,
                'name': org_unit.name,
                'code': getattr(org_unit, 'code', '')
            },
            'modules': module_data,
            'summary': {
                'total_modules': modules.count(),
                'modules_with_data': modules_with_data,
                'latest_submission': latest_submission,
                'data_quality': dq_summary
            }
        })
```

### G1.2 — Register URL

**File:** `backend/emissions/urls.py`

Add after `OwnerDashboardAPIView` route (around line 45):

```python
path('owner/summary/', OwnerSummaryAPIView.as_view(), name='owner-summary'),
```

---

## G2: Create Data Owner Assets Endpoint

**File:** `backend/emissions/views.py`

### G2.1 — Add `OwnerAssetsAPIView`

Create after `OwnerSummaryAPIView`:

```python
class OwnerAssetsAPIView(APIView):
    """
    GET /api/v1/emissions/owner/assets/
    
    Returns emission-generating assets scoped to user's org unit.
    This is emissions-specific (not catalog generic assets).
    
    Query params:
    - search: Filter by name
    - scope: Filter by scope (1, 2, 3)
    
    Response:
    [
        {
            "id": 5,
            "name": "Electricity - Main Campus",
            "scope": 2,
            "category": "electricity",
            "table_name": "electricity_consumption",
            "row_count": 120,
            "last_entry": "2025-01-15T10:30:00Z",
            "data_quality_status": "passing"
        }
    ]
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Get user's org units
        org_units = get_visible_org_units(user)
        if not org_units:
            return Response([])
        
        # Get modules (emission sources) for user's org units
        from core.models import Module
        modules = Module.objects.filter(
            org_unit__in=org_units
        ).select_related('org_unit').order_by('name')
        
        # Apply filters
        search = request.query_params.get('search')
        if search:
            modules = modules.filter(name__icontains=search)
        
        scope = request.query_params.get('scope')
        if scope:
            modules = modules.filter(scope=scope)
        
        # Build response
        assets = []
        for module in modules:
            table = module.get_table()
            row_count = table.rows.count() if table else 0
            
            # Get last entry timestamp
            last_row = table.rows.order_by('-created_at').first() if table and table.rows.exists() else None
            last_entry = last_row.created_at if last_row else None
            
            assets.append({
                'id': module.id,
                'name': module.name,
                'scope': module.scope,
                'category': module.category or 'unknown',
                'table_name': module.table_name,
                'row_count': row_count,
                'last_entry': last_entry,
                'data_quality_status': 'passing'  # Stub, connect to DQ later
            })
        
        return Response(assets)
```

### G2.2 — Register URL

**File:** `backend/emissions/urls.py`

Add after `owner/summary/`:

```python
path('owner/assets/', OwnerAssetsAPIView.as_view(), name='owner-assets'),
```

---

## G3: Create Data Owner Activity Feed Endpoint

**File:** `backend/emissions/views.py`

### G3.1 — Add `OwnerActivityAPIView`

Create after `OwnerAssetsAPIView`:

```python
class OwnerActivityAPIView(APIView):
    """
    GET /api/v1/emissions/owner/activity/
    
    Returns recent activity (data submissions, calculations) for user's org unit.
    
    Query params:
    - limit: Max events to return (default 20)
    
    Response:
    [
        {
            "id": 123,
            "type": "data_entry",
            "description": "Added 5 rows to Electricity - Main Campus",
            "user": "Ahmed Hassan",
            "timestamp": "2025-01-15T10:30:00Z",
            "module": "Electricity - Main Campus"
        }
    ]
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        limit = int(request.query_params.get('limit', 20))
        
        # Get user's org units
        org_units = get_visible_org_units(user)
        if not org_units:
            return Response([])
        
        # Get recent data rows created for user's org unit modules
        from dataschema.models import DataRow
        from core.models import Module
        
        recent_rows = DataRow.objects.filter(
            table__module__org_unit__in=org_units
        ).select_related(
            'table__module',
            'created_by'
        ).order_by('-created_at')[:limit]
        
        events = []
        for row in recent_rows:
            module = row.table.module
            user_name = row.created_by.get_full_name() if row.created_by else 'System'
            
            events.append({
                'id': row.id,
                'type': 'data_entry',
                'description': f"Updated data in {module.name}",
                'user': user_name,
                'timestamp': row.created_at,
                'module': module.name
            })
        
        return Response(events)
```

### G3.2 — Register URL

**File:** `backend/emissions/urls.py`

Add after `owner/assets/`:

```python
path('owner/activity/', OwnerActivityAPIView.as_view(), name='owner-activity'),
```

---

## Definition of Done (Worker 1)

- [ ] `OwnerSummaryAPIView` created and returns org unit + modules + summary
- [ ] `OwnerAssetsAPIView` created and returns emission sources scoped to user
- [ ] `OwnerActivityAPIView` created and returns recent activity events
- [ ] All 3 endpoints registered in `urls.py`
- [ ] Endpoints respect org unit scoping via `get_visible_org_units()`
- [ ] Manual test: `curl` each endpoint as Ahmed user
- [ ] Swagger docs accessible at `/api/schema/swagger/`

---

# WORKER 2: Frontend — UI Fixes and Refactoring

## Context

1. ReportingPeriodPage form doesn't expose `status`, `period_type`, `is_baseline` fields
2. Data Owner pages use Catalog APIs — need to switch to new emissions endpoints
3. Data Entry Hub path `/dataschema` should be under Carbon namespace

---

## G1: Fix ReportingPeriod Form (Model Alignment)

**File:** `carbon-frontend/src/pages/emissions/ReportingPeriodsPage.jsx`

### G1.1 — Update form state

**Lines 42-48:** Change from:
```javascript
const [form, setForm] = useState({
  name: '',
  start_date: '',
  end_date: '',
  is_active: false,  // ❌ This is a computed property, not a field!
  description: '',
});
```

To:
```javascript
const [form, setForm] = useState({
  name: '',
  start_date: '',
  end_date: '',
  period_type: 'annual',  // ✅ New: annual/quarterly/monthly/custom
  status: 'draft',        // ✅ New: draft/open/locked/submitted/verified/closed
  is_baseline: false,     // ✅ New: baseline period flag
  description: '',
});
```

### G1.2 — Update handleOpenDialog

**Lines 68-89:** Update to populate new fields:

```javascript
const handleOpenDialog = (period = null) => {
  if (period) {
    setEditingPeriod(period);
    setForm({
      name: period.name,
      start_date: period.start_date,
      end_date: period.end_date,
      period_type: period.period_type || 'annual',
      status: period.status || 'draft',
      is_baseline: period.is_baseline || false,
      description: period.description || '',
    });
  } else {
    setEditingPeriod(null);
    setForm({
      name: '',
      start_date: '',
      end_date: '',
      period_type: 'annual',
      status: 'draft',
      is_baseline: false,
      description: '',
    });
  }
  setOpenDialog(true);
};
```

### G1.3 — Add form fields to dialog

**After line 256 (end_date TextField)**, add:

```javascript
<TextField
  select
  label="Period Type"
  name="period_type"
  value={form.period_type}
  onChange={handleChange}
  fullWidth
  margin="normal"
  required
>
  <MenuItem value="annual">Annual</MenuItem>
  <MenuItem value="quarterly">Quarterly</MenuItem>
  <MenuItem value="monthly">Monthly</MenuItem>
  <MenuItem value="custom">Custom</MenuItem>
</TextField>

<TextField
  select
  label="Status"
  name="status"
  value={form.status}
  onChange={handleChange}
  fullWidth
  margin="normal"
  required
>
  <MenuItem value="draft">Draft</MenuItem>
  <MenuItem value="open">Open for Data Entry</MenuItem>
  <MenuItem value="locked">Locked for Review</MenuItem>
  <MenuItem value="submitted">Submitted</MenuItem>
  <MenuItem value="verified">Verified</MenuItem>
  <MenuItem value="closed">Closed</MenuItem>
</TextField>

<FormControlLabel
  control={
    <Switch
      checked={form.is_baseline}
      onChange={handleChange}
      name="is_baseline"
    />
  }
  label="Baseline Period (used for year-over-year comparisons)"
/>
```

### G1.4 — Update table columns

**Lines 172-179:** Add period_type and status columns:

```javascript
<TableHead sx={{ backgroundColor: 'action.hover' }}>
  <TableRow>
    <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
    <TableCell sx={{ fontWeight: 600 }}>Type</TableCell>
    <TableCell sx={{ fontWeight: 600 }}>Start Date</TableCell>
    <TableCell sx={{ fontWeight: 600 }}>End Date</TableCell>
    <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
    <TableCell sx={{ fontWeight: 600 }} align="right">Actions</TableCell>
  </TableRow>
</TableHead>
```

**Lines 196-201:** Display period_type and status:

```javascript
<TableRow key={period.id} hover>
  <TableCell>{period.name}</TableCell>
  <TableCell>
    <Chip 
      label={period.period_type || 'annual'} 
      size="small" 
      variant="outlined"
    />
  </TableCell>
  <TableCell>{new Date(period.start_date).toLocaleDateString()}</TableCell>
  <TableCell>{new Date(period.end_date).toLocaleDateString()}</TableCell>
  <TableCell>
    <Chip 
      label={period.status || 'draft'} 
      size="small"
      color={
        period.status === 'verified' ? 'success' :
        period.status === 'open' ? 'primary' :
        period.status === 'closed' ? 'default' :
        'warning'
      }
    />
  </TableCell>
  <TableCell align="right">
    {/* Actions... */}
  </TableCell>
</TableRow>
```

---

## G2: Refactor Data Owner Pages to Use Emissions APIs

### G2.1 — Create new API functions

**File:** `carbon-frontend/src/api/emissions.js`

**Add after `fetchOwnerDashboard` function (around line 183):**

```javascript
/**
 * Fetch data owner summary (org unit, modules, stats)
 */
export async function fetchOwnerSummary(token) {
  return apiFetch(`${API_ROUTES.emissionsAPI}owner/summary/`, { token });
}

/**
 * Fetch emission-generating assets scoped to user's org unit
 */
export async function fetchOwnerAssets({ search, scope } = {}, token) {
  const params = new URLSearchParams();
  if (search) params.append('search', search);
  if (scope) params.append('scope', scope);
  
  const endpoint = params.toString()
    ? `${API_ROUTES.emissionsAPI}owner/assets/?${params.toString()}`
    : `${API_ROUTES.emissionsAPI}owner/assets/`;
  
  return apiFetch(endpoint, { token });
}

/**
 * Fetch recent activity for data owner
 */
export async function fetchOwnerActivity({ limit = 20 } = {}, token) {
  return apiFetch(`${API_ROUTES.emissionsAPI}owner/activity/?limit=${limit}`, { token });
}
```

### G2.2 — Refactor DataOwnerPortalPage

**File:** `carbon-frontend/src/pages/data-owner/DataOwnerPortalPage.jsx`

**Lines 1-12:** Change imports from:
```javascript
import {
  fetchDataDomains,
  fetchAssetProfiles,
  fetchGovernanceEvents,
} from '../../api/catalog';
```

To:
```javascript
import {
  fetchOwnerSummary,
  fetchOwnerAssets,
  fetchOwnerActivity,
} from '../../api/emissions';
```

**Lines 250-295:** Refactor loadData function:

```javascript
useEffect(() => {
  const loadData = async () => {
    try {
      setLoading(true);

      // Fetch summary (replaces domains + manual asset grouping)
      const summaryRes = await fetchOwnerSummary(token);
      
      if (!summaryRes.org_unit) {
        setError('no-scope');
        setLoading(false);
        return;
      }
      
      // Fetch assets (emission sources)
      const assetsRes = await fetchOwnerAssets({}, token);
      setAssets(assetsRes || []);
      
      // Fetch activity feed
      const activityRes = await fetchOwnerActivity({ limit: 10 }, token);
      setEvents(activityRes || []);
      
      // Store summary for display
      setDomains([{
        id: summaryRes.org_unit.id,
        name: summaryRes.org_unit.name,
        assets: summaryRes.summary.total_modules,
        avgQuality: summaryRes.summary.data_quality.passing > 0 ? 85 : 50
      }]);

      setError(null);
    } catch (err) {
      console.error('Error loading portal data:', err);
      setError('load-failed');
      showNotification({
        message: 'Failed to load portal data',
        type: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  if (token) {
    loadData();
  }
}, [token, showNotification]);
```

### G2.3 — Refactor DataOwnerDashboardPage

**File:** `carbon-frontend/src/pages/data-owner/DataOwnerDashboardPage.jsx`

**Lines 1-7:** Change imports to use `fetchOwnerSummary` alongside `fetchOwnerDashboard`:

```javascript
import { fetchOwnerDashboard, fetchReportingPeriodsFiltered, fetchOwnerSummary } from '../../api/emissions';
```

### G2.4 — Refactor DataOwnerAssetsPage

**File:** `carbon-frontend/src/pages/data-owner/DataOwnerAssetsPage.jsx`

**Lines 1-8:** Change imports:
```javascript
import { fetchOwnerAssets } from '../../api/emissions';
// Remove: fetchAssetProfiles, fetchDataDomains from catalog
```

**Lines 120-140:** Update loadAssets function:

```javascript
const loadAssets = async () => {
  try {
    setLoading(true);
    const data = await fetchOwnerAssets({ search: searchTerm, scope: filters.scope }, token);
    setAssets(data || []);
  } catch (err) {
    console.error('Error loading assets:', err);
    showNotification({
      message: 'Failed to load assets',
      type: 'error',
    });
  } finally {
    setLoading(false);
  }
};
```

---

## G3: Resolve Data Entry Hub Namespace

**File:** `carbon-frontend/src/apps/carbon/manifest.js`

### G3.1 — Update manifest navigation

**Line 59:** Change from:
```javascript
{ label: 'Data Entry Hub', path: '/dataschema', role: '*' },
```

To:
```javascript
{ label: 'Data Entry Hub', path: '/carbon/data-entry', role: '*' },
```

### G3.2 — Add comment explaining legacy path

Add comment above the item:
```javascript
// Data Entry Hub — Carbon-owned table-driven data entry interface
// Note: Previously at /dataschema, moved under Carbon namespace
{ label: 'Data Entry Hub', path: '/carbon/data-entry', role: '*' },
```

### G3.3 — Update route registration

**File:** `carbon-frontend/src/App.jsx`

**Around line 140:** Find existing dataschema routes and add Carbon alias:

```javascript
{/* Data Entry Hub - Carbon namespace */}
<Route path="/carbon/data-entry" element={<Navigate to="/dataschema" replace />} />

{/* Legacy dataschema routes (keep for now, will migrate fully later) */}
<Route path="/dataschema" element={<DataSchemaPage />} />
<Route path="/dataschema/table/:tableName" element={<TableDetailPage />} />
<Route path="/dataschema/table/:tableName/row/:rowId" element={<RowDetailPage />} />
```

**Reasoning:** Keeps `/dataschema` working (no breaking changes) but provides new Carbon-namespaced path.

---

## G4: Remove useNotification() Dependency (Optional P2)

**Skip for now** — Noted in audit as P2 priority. Keep current implementation with `useNotification()` to avoid breaking changes. Will refactor to Material-UI Snackbar in future sprint.

---

## Definition of Done (Worker 2)

- [ ] ReportingPeriodPage form includes `period_type`, `status`, `is_baseline` fields
- [ ] ReportingPeriodPage table displays period type and status columns
- [ ] New API functions `fetchOwnerSummary`, `fetchOwnerAssets`, `fetchOwnerActivity` created
- [ ] DataOwnerPortalPage refactored to use emissions APIs (no catalog imports)
- [ ] DataOwnerDashboardPage updated to use `fetchOwnerSummary`
- [ ] DataOwnerAssetsPage refactored to use `fetchOwnerAssets`
- [ ] Manifest navigation updated: Data Entry Hub → `/carbon/data-entry`
- [ ] Route added: `/carbon/data-entry` redirects to `/dataschema` (legacy path maintained)
- [ ] `npm run build` succeeds
- [ ] Manual test: All pages load without errors

---

## Parallel Execution Notes

- Workers can proceed **independently** (no file conflicts)
- Worker 2 should wait for Worker 1 to complete G1-G3 before testing Data Owner pages
- Worker 2 can complete G1 (ReportingPeriod) and G3 (Data Entry Hub) immediately

---

## Files to Create

**Worker 1:**
- None (all changes in existing files)

**Worker 2:**
- None (all changes in existing files)

---

## Files to Modify

**Worker 1:**
- `backend/emissions/views.py` — Add 3 new view classes
- `backend/emissions/urls.py` — Register 3 new endpoints

**Worker 2:**
- `carbon-frontend/src/pages/emissions/ReportingPeriodsPage.jsx` — Add fields to form
- `carbon-frontend/src/api/emissions.js` — Add 3 new API functions
- `carbon-frontend/src/pages/data-owner/DataOwnerPortalPage.jsx` — Refactor API calls
- `carbon-frontend/src/pages/data-owner/DataOwnerDashboardPage.jsx` — Update imports
- `carbon-frontend/src/pages/data-owner/DataOwnerAssetsPage.jsx` — Refactor API calls
- `carbon-frontend/src/apps/carbon/manifest.js` — Update Data Entry Hub path
- `carbon-frontend/src/App.jsx` — Add `/carbon/data-entry` route

---

## Do NOT Change

- RBAC settings (keep `role: '*'` for Ahmed during dev)
- Existing `/dataschema` routes (maintain backward compatibility)
- Any Catalog domain files
- Shell navigation logic
- Core platform files

---

## Testing Checklist

**Worker 1:**
- [ ] `GET /api/v1/emissions/owner/summary/` returns org unit + modules for Ahmed
- [ ] `GET /api/v1/emissions/owner/assets/` returns emission sources scoped to Ahmed's org unit
- [ ] `GET /api/v1/emissions/owner/activity/` returns recent data entries
- [ ] Swagger docs updated and accessible

**Worker 2:**
- [ ] ReportingPeriodsPage: Create new period with status="open", period_type="quarterly"
- [ ] ReportingPeriodsPage: Edit existing period, verify all fields populate
- [ ] DataOwnerPortalPage loads without Catalog API errors
- [ ] DataOwnerAssetsPage loads emission sources from new endpoint
- [ ] Navigate to "Data Entry Hub" → URL shows `/carbon/data-entry` → redirects to `/dataschema`
- [ ] Build succeeds: `npm run build`

---

## Reference Documents

- Audit findings: [`plans/CARBON_APP_CRITICAL_AUDIT.md`](plans/CARBON_APP_CRITICAL_AUDIT.md)
- Platform model: [`docs/PLATFORM_APP_MODEL.md`](docs/PLATFORM_APP_MODEL.md)
- Carbon P1 task: [`TASK-CARBON-P1-SCOPED-OWNER-APPS.md`](TASK-CARBON-P1-SCOPED-OWNER-APPS.md)
- Original P2 task: [`TASK-CARBON-P2-REPORT-FACTOR.md`](TASK-CARBON-P2-REPORT-FACTOR.md)
