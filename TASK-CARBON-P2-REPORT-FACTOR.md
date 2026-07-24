# TASK: Carbon Product Apps — P2 Report Generator + Emission Factor Manager

> **Track G — Carbon Product Apps, Priority 2**  
> **Parallel execution:** G1 (Backend) and G2 (Frontend) have zero hard dependencies and can run simultaneously  
> **Prerequisite:** P1 complete (Scoped Data Owner Portal + Dashboard) ✅  
> **Architecture reference:** `plans/CARBON_PRODUCT_APPS_ARCHITECTURE.md` §App 3 + §App 5

---

## Worker Split

| Worker | Track | Scope |
|---|---|---|
| **Worker 1** | G1 — Backend | `ReportConfig` model + enhanced Report API + CSV export |
| **Worker 2** | G2 — Frontend | Emission Factor Manager page + Report Generator wizard |

---

## Pre-Work: What Already Exists (Don't Rebuild)

### Already built — backend
| Feature | Location | Status |
|---|---|---|
| `EmissionFactorViewSet` full CRUD | `backend/emissions/views.py:77` | ✅ Complete |
| `EmissionFactorSerializer` | `backend/emissions/serializers.py:24` | ✅ Complete |
| `/emissions/factors/` registered | `backend/emissions/urls.py:25` | ✅ Registered |
| `/emissions/factors/summary/` dropdown | `views.py:119` | ✅ Exists |
| `/emissions/factors/categories/` | `views.py:126` | ✅ Exists |
| `ReportingPeriodViewSet` | `backend/emissions/views.py:39` | ✅ Complete |
| `ReportAPIView` (basic) | `backend/emissions/views.py:468` | ✅ Exists, needs enhancement |
| `_scope_calcs(user, qs)` | `backend/emissions/views.py:30` | ✅ Org-scoped helper |
| `EmissionFactor` model | `backend/emissions/models.py:96` | ✅ Complete (all fields) |

### Not yet built — what G1 must add
- `ReportConfig` model — saved report configurations
- `ReportConfigViewSet` — CRUD for saved configs
- Enhanced `ReportAPIView` — org_unit filter, grouping, CSV output format
- CSV export endpoint

### Not yet built — what G2 must add
- `EmissionFactorsPage.jsx` — admin CRUD UI for emission factors
- `ReportGeneratorPage.jsx` — multi-step report wizard
- API helper functions for new G1 endpoints
- Routes and sidebar entries

---

---

# TRACK G1 — BACKEND: ReportConfig Model + Enhanced Report API

## Context

`ReportAPIView` (line 468) already does basic scope aggregation but lacks:
1. Persistent saved configurations (`ReportConfig` model)
2. Org-unit-specific filter (currently uses `_scope_calcs` which filters by module access — need to add explicit `org_unit` query param)
3. CSV export format (currently JSON only)
4. Grouping by module (currently groups by scope/category only)
5. CRUD endpoints for saved configs

## Scope — what to build

### G1.1 — `ReportConfig` Model

**File:** `backend/emissions/models.py` (append at end)

```python
class ReportConfig(models.Model):
    """
    Saved report configuration for reusable report generation.
    Captures: which period, which org_unit subtree, which GHG scopes,
    which categories, and output format preferences.
    """
    PERIOD_TYPE_CHOICES = [
        ('existing', 'Existing Reporting Period'),
        ('custom', 'Custom Date Range'),
    ]
    FORMAT_CHOICES = [
        ('json', 'JSON'),
        ('csv', 'CSV'),
    ]
    GROUPING_CHOICES = [
        ('scope', 'By GHG Scope'),
        ('category', 'By Category'),
        ('module', 'By Module'),
        ('month', 'By Month'),
    ]

    name = models.CharField(max_length=200, help_text="e.g., 'FY 2026 Smart Village Annual Report'")
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, related_name='report_configs'
    )

    # Period selection
    reporting_period = models.ForeignKey(
        ReportingPeriod, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="If null, use custom_start / custom_end"
    )
    custom_start = models.DateField(null=True, blank=True)
    custom_end = models.DateField(null=True, blank=True)

    # Scope filters
    org_unit = models.ForeignKey(
        'mdm.OrgUnit', on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Scope to this org_unit subtree (null = all accessible)"
    )
    ghg_scopes = models.JSONField(
        default=list,
        help_text="List of GHG scope numbers to include, e.g., [1, 2, 3]. Empty = all."
    )
    categories = models.JSONField(
        default=list,
        help_text="List of category codes to include. Empty = all."
    )

    # Output preferences
    output_format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='json')
    grouping = models.CharField(max_length=20, choices=GROUPING_CHOICES, default='scope')
    include_dq_status = models.BooleanField(default=True)
    include_unverified = models.BooleanField(default=False)

    # Metadata
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Report Configuration"
        verbose_name_plural = "Report Configurations"

    def __str__(self):
        return self.name
```

**Migration:** Create and apply migration for `ReportConfig`.

**Acceptance:** `python manage.py makemigrations emissions && python manage.py migrate` passes with no errors.

---

### G1.2 — `ReportConfigSerializer`

**File:** `backend/emissions/serializers.py` (append after `EmissionReportSerializer`)

```python
class ReportConfigSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True, allow_null=True
    )
    reporting_period_name = serializers.CharField(
        source='reporting_period.name', read_only=True, allow_null=True
    )
    org_unit_name = serializers.CharField(
        source='org_unit.name', read_only=True, allow_null=True
    )

    class Meta:
        model = ReportConfig
        fields = [
            'id', 'name',
            'created_by', 'created_by_username',
            'reporting_period', 'reporting_period_name',
            'custom_start', 'custom_end',
            'org_unit', 'org_unit_name',
            'ghg_scopes', 'categories',
            'output_format', 'grouping',
            'include_dq_status', 'include_unverified',
            'last_run_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'last_run_at', 'created_at', 'updated_at']
```

---

### G1.3 — `ReportConfigViewSet`

**File:** `backend/emissions/views.py` (append before `OwnerDashboardAPIView`)

```python
class ReportConfigViewSet(viewsets.ModelViewSet):
    """
    CRUD for saved report configurations.

    GET  /emissions/report-configs/           — list user's configs
    POST /emissions/report-configs/           — create new config
    GET  /emissions/report-configs/{id}/      — retrieve
    PATCH /emissions/report-configs/{id}/     — update
    DELETE /emissions/report-configs/{id}/    — delete
    POST /emissions/report-configs/{id}/run/  — execute and return report data
    """
    serializer_class = ReportConfigSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return ReportConfig.objects.select_related(
                'reporting_period', 'org_unit', 'created_by'
            ).all()
        return ReportConfig.objects.select_related(
            'reporting_period', 'org_unit', 'created_by'
        ).filter(created_by=user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        """
        POST /emissions/report-configs/{id}/run/
        Execute the saved configuration and return report data.
        Updates last_run_at timestamp.
        """
        config = self.get_object()
        config.last_run_at = timezone.now()
        config.save(update_fields=['last_run_at'])
        # Delegate to report generation logic
        report_data = _generate_report_from_config(config, request.user)
        return Response(report_data)
```

---

### G1.4 — `_generate_report_from_config()` Service Function

**File:** `backend/emissions/views.py` (add as module-level function before `ReportConfigViewSet`)

This function contains the actual aggregation logic, usable by both the `run` action and the enhanced `ReportAPIView`.

```python
def _generate_report_from_config(config, user):
    """
    Generate report data from a ReportConfig instance.
    Returns a dict with scope_breakdown, category_breakdown, module_breakdown,
    total_co2e_tonnes, and metadata.
    """
    # Base queryset — org scoped
    qs = _scope_calcs(user, Calculation.objects.select_related(
        'module', 'module__org_unit', 'emission_factor', 'data_row'
    ))

    # Filter by org_unit subtree if specified
    if config.org_unit_id:
        from mdm.models import OrgUnit
        ou = OrgUnit.objects.get(pk=config.org_unit_id)
        descendant_ids = ou.get_descendant_ids(include_self=True)
        qs = qs.filter(module__org_unit_id__in=descendant_ids)

    # Filter by reporting period OR custom date range
    if config.reporting_period_id:
        qs = qs.filter(reporting_period_id=config.reporting_period_id)
    elif config.custom_start and config.custom_end:
        qs = qs.filter(
            activity_date__gte=config.custom_start,
            activity_date__lte=config.custom_end
        )

    # Filter by GHG scopes if specified
    if config.ghg_scopes:
        qs = qs.filter(scope__in=config.ghg_scopes)

    # Filter by categories if specified
    if config.categories:
        qs = qs.filter(category__in=config.categories)

    # Aggregations
    scope_names = {1: 'Scope 1 - Direct', 2: 'Scope 2 - Indirect Energy', 3: 'Scope 3 - Value Chain'}
    
    scope_data = qs.values('scope').annotate(
        total_kg=Sum('co2e_kg'), count=Count('id')
    ).order_by('scope')

    grand_total_kg = sum(s['total_kg'] or 0 for s in scope_data)

    scope_breakdown = [
        {
            'scope': s['scope'],
            'scope_name': scope_names.get(s['scope'], f"Scope {s['scope']}"),
            'co2e_tonnes': round((s['total_kg'] or 0) / 1000, 3),
            'percentage': round(((s['total_kg'] or 0) / grand_total_kg * 100) if grand_total_kg else 0, 1),
            'calculation_count': s['count'],
        }
        for s in scope_data
    ]

    category_data = qs.values('category', 'scope').annotate(
        total_kg=Sum('co2e_kg'), count=Count('id')
    ).order_by('scope', 'category')

    category_names = dict(EmissionFactor.CATEGORY_CHOICES)
    category_breakdown = [
        {
            'category': c['category'],
            'category_name': category_names.get(c['category'], c['category']),
            'scope': c['scope'],
            'co2e_tonnes': round((c['total_kg'] or 0) / 1000, 3),
            'calculation_count': c['count'],
        }
        for c in category_data
    ]

    module_breakdown = []
    if config.grouping == 'module':
        module_data = qs.values(
            'module_id', 'module__name', 'module__org_unit__name'
        ).annotate(
            total_kg=Sum('co2e_kg'), count=Count('id')
        ).order_by('module__name')
        module_breakdown = [
            {
                'module_id': m['module_id'],
                'module_name': m['module__name'],
                'org_unit_name': m['module__org_unit__name'],
                'co2e_tonnes': round((m['total_kg'] or 0) / 1000, 3),
                'calculation_count': m['count'],
            }
            for m in module_data
        ]

    reporting_period_data = None
    if config.reporting_period_id:
        try:
            rp = ReportingPeriod.objects.get(pk=config.reporting_period_id)
            reporting_period_data = ReportingPeriodSerializer(rp).data
        except ReportingPeriod.DoesNotExist:
            pass

    return {
        'config_id': config.id,
        'config_name': config.name,
        'reporting_period': reporting_period_data,
        'date_range': {
            'start': str(config.custom_start) if config.custom_start else None,
            'end': str(config.custom_end) if config.custom_end else None,
        },
        'org_unit_id': config.org_unit_id,
        'total_co2e_tonnes': round(grand_total_kg / 1000, 3),
        'calculation_count': qs.count(),
        'scope_breakdown': scope_breakdown,
        'category_breakdown': category_breakdown,
        'module_breakdown': module_breakdown,
        'generated_at': timezone.now().isoformat(),
    }
```

---

### G1.5 — Register `ReportConfig` routes in `urls.py`

**File:** `backend/emissions/urls.py`

Add to imports:
```python
from .views import (
    ...
    ReportConfigViewSet,
)
```

Add to router registrations (after existing `router.register` calls):
```python
router.register(r'report-configs', ReportConfigViewSet, basename='report-config')
```

**New endpoints registered automatically:**
- `GET /carbon-api/emissions/report-configs/`
- `POST /carbon-api/emissions/report-configs/`
- `GET /carbon-api/emissions/report-configs/{id}/`
- `PATCH /carbon-api/emissions/report-configs/{id}/`
- `DELETE /carbon-api/emissions/report-configs/{id}/`
- `POST /carbon-api/emissions/report-configs/{id}/run/`

Also update serializer imports in `emissions/serializers.py` header to include `ReportConfig`.

---

### G1.6 — Enhanced `ReportAPIView` (add org_unit + CSV)

**File:** `backend/emissions/views.py`, `ReportAPIView.get()` (line ~481)

Enhance the existing view to support `?org_unit_id=<id>` and `?format=csv`:

```python
def get(self, request):
    # ... existing period/year logic unchanged ...
    
    # NEW: org_unit subtree filter
    org_unit_id = request.query_params.get('org_unit_id')
    if org_unit_id:
        from mdm.models import OrgUnit
        try:
            ou = OrgUnit.objects.get(pk=org_unit_id)
            descendant_ids = ou.get_descendant_ids(include_self=True)
            queryset = queryset.filter(module__org_unit_id__in=descendant_ids)
        except OrgUnit.DoesNotExist:
            pass
    
    # ... existing scope_totals aggregation unchanged ...
    
    # NEW: CSV format support
    report_format = request.query_params.get('format', 'json')
    if report_format == 'csv':
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Scope', 'Category', 'CO2e (tonnes)', 'Count'])
        rows = queryset.values('scope', 'category').annotate(
            total_kg=Sum('co2e_kg'), count=Count('id')
        ).order_by('scope', 'category')
        category_names = dict(EmissionFactor.CATEGORY_CHOICES)
        scope_names = {1: 'Scope 1', 2: 'Scope 2', 3: 'Scope 3'}
        for r in rows:
            writer.writerow([
                scope_names.get(r['scope'], r['scope']),
                category_names.get(r['category'], r['category']),
                round((r['total_kg'] or 0) / 1000, 3),
                r['count'],
            ])
        from django.http import HttpResponse
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="emissions_report.csv"'
        return response
    
    # ... existing JSON return unchanged ...
```

**Acceptance:** `GET /carbon-api/emissions/report/?format=csv&org_unit_id=5` returns a valid CSV download.

---

### G1.7 — Tests

**File:** `backend/emissions/tests/test_report_config.py` (new file)

Write tests covering:

1. `test_create_report_config` — POST creates config, sets `created_by=request.user`
2. `test_list_own_configs_only` — user A cannot see user B's configs
3. `test_staff_sees_all_configs` — staff user can list all configs
4. `test_run_config_returns_data` — POST to `/run/` returns `total_co2e_tonnes` + `scope_breakdown`
5. `test_run_config_updates_last_run_at` — `last_run_at` is updated after run
6. `test_org_unit_filter` — config with `org_unit=5` only returns calcs from org 5 subtree
7. `test_ghg_scope_filter` — config with `ghg_scopes=[1]` returns only Scope 1 calcs
8. `test_csv_export` — `GET /report/?format=csv` returns `Content-Type: text/csv`
9. `test_unauthenticated_403` — unauthenticated user gets 403 on all config endpoints
10. `test_delete_own_config` — user can DELETE their own config; cannot DELETE others'

**Run:** `cd backend && python -m pytest emissions/tests/test_report_config.py -v`

---

### G1 — Acceptance Criteria

- [ ] `ReportConfig` model created and migrated
- [ ] `ReportConfigViewSet` at `/carbon-api/emissions/report-configs/`
- [ ] `POST /run/` returns structured report with `scope_breakdown` and `total_co2e_tonnes`
- [ ] `org_unit_id` filter on both `ReportAPIView` and `_generate_report_from_config()`
- [ ] CSV export returns `Content-Type: text/csv` with correct rows
- [ ] `created_by` auto-populated, non-owners cannot access others' configs
- [ ] 10 tests pass: `python -m pytest emissions/tests/test_report_config.py -v`
- [ ] `python manage.py check` returns 0 issues

---

---

# TRACK G2 — FRONTEND: Emission Factor Manager + Report Generator Wizard

## Context

The backend `EmissionFactorViewSet` at `/carbon-api/emissions/factors/` is complete with full CRUD. This is purely a **frontend task** — build the management UI that currently only exists in Django admin.

The backend `ReportAPI` exists but G1 is adding `ReportConfig` CRUD + enhanced `/run/` endpoint. G2 can proceed in parallel using the existing `/emissions/report/` endpoint, then wire to the new G1 endpoints when ready.

## Scope — what to build

### G2.1 — Add API functions to `emissions.js`

**File:** `carbon-frontend/src/api/emissions.js`

Add these functions (import `apiFetch` and `API_ROUTES` following existing pattern):

```javascript
// === Emission Factor API ===

export function fetchEmissionFactors(token, filters = {}) {
  const params = new URLSearchParams();
  if (filters.category) params.append('category', filters.category);
  if (filters.scope) params.append('scope', filters.scope);
  if (filters.search) params.append('search', filters.search);
  if (filters.active !== undefined) params.append('active', filters.active);
  const query = params.toString() ? `?${params}` : '';
  return apiFetch(`${API_BASE}/emissions/factors/${query}`, { method: 'GET', token });
}

export function fetchEmissionFactorCategories(token) {
  return apiFetch(`${API_BASE}/emissions/factors/categories/`, { method: 'GET', token });
}

export function createEmissionFactor(token, data) {
  return apiFetch(`${API_BASE}/emissions/factors/`, { method: 'POST', token, body: data });
}

export function updateEmissionFactor(token, id, data) {
  return apiFetch(`${API_BASE}/emissions/factors/${id}/`, { method: 'PATCH', token, body: data });
}

export function deleteEmissionFactor(token, id) {
  return apiFetch(`${API_BASE}/emissions/factors/${id}/`, { method: 'DELETE', token });
}

// === Report Config API ===

export function fetchReportConfigs(token) {
  return apiFetch(`${API_BASE}/emissions/report-configs/`, { method: 'GET', token });
}

export function createReportConfig(token, data) {
  return apiFetch(`${API_BASE}/emissions/report-configs/`, { method: 'POST', token, body: data });
}

export function updateReportConfig(token, id, data) {
  return apiFetch(`${API_BASE}/emissions/report-configs/${id}/`, { method: 'PATCH', token, body: data });
}

export function deleteReportConfig(token, id) {
  return apiFetch(`${API_BASE}/emissions/report-configs/${id}/`, { method: 'DELETE', token });
}

export function runReportConfig(token, id) {
  return apiFetch(`${API_BASE}/emissions/report-configs/${id}/run/`, { method: 'POST', token });
}

export function generateReport(token, params = {}) {
  const query = new URLSearchParams(params).toString();
  return apiFetch(`${API_BASE}/emissions/report/${query ? '?' + query : ''}`, { method: 'GET', token });
}

export function downloadReportCsv(token, params = {}) {
  const p = { ...params, format: 'csv' };
  const query = new URLSearchParams(p).toString();
  return fetch(`${API_BASE}/emissions/report/?${query}`, {
    headers: { Authorization: `Bearer ${token}` }
  }).then(r => r.blob());
}
```

---

### G2.2 — `EmissionFactorsPage.jsx` (App 5 — Factor Manager)

**File:** `carbon-frontend/src/pages/emissions/EmissionFactorsPage.jsx` (new directory `pages/emissions/`)

**Requirements:**

1. **Data grid** using `StandardDataGrid` (or MUI DataGrid pattern from existing pages) with columns:
   - Name, Code, Category (chip), Scope (1/2/3 badge), Factor Value, Activity Unit, Valid From, Valid To, Active (toggle), Source

2. **Filter bar** with:
   - Search input (name/code search → `?search=`)
   - Category select (options from `GET /factors/categories/`)
   - Scope select (1 / 2 / 3 / All)
   - Active toggle (Active / All)

3. **Create/Edit drawer** (reuse existing drawer pattern from `MDMPage.jsx`):
   Fields: name, code, category, subcategory, scope, factor_value, factor_unit, activity_unit, valid_from, valid_to, source, source_url, country, country_code, notes, is_active

4. **Delete** with confirmation dialog

5. **Permissions:** Only render Create/Edit/Delete buttons for `is_staff` or `is_superuser`. Data owners see read-only view.

6. **Empty state:** "No emission factors found" with "Add Factor" button if admin.

**Component structure:**
```jsx
export default function EmissionFactorsPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.is_staff || user?.is_superuser;
  // ... fetchEmissionFactors, categories, etc.
  
  // Column definitions
  const columns = [
    { field: 'name', headerName: 'Name', flex: 2 },
    { field: 'code', headerName: 'Code', width: 120 },
    { field: 'category', headerName: 'Category', width: 160, renderCell: ... },
    { field: 'scope', headerName: 'Scope', width: 80 },
    { field: 'factor_value', headerName: 'Factor', width: 120 },
    { field: 'activity_unit', headerName: 'Activity Unit', width: 120 },
    { field: 'valid_from', headerName: 'Valid From', width: 120 },
    { field: 'is_active', headerName: 'Active', width: 80, renderCell: ... },
    // Actions column (edit/delete) if isAdmin
  ];
  
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5">Emission Factors</Typography>
      {/* Filter bar */}
      {/* DataGrid */}
      {/* Edit drawer */}
    </Box>
  );
}
```

---

### G2.3 — `ReportGeneratorPage.jsx` (App 3 — Report Generator)

**File:** `carbon-frontend/src/pages/emissions/ReportGeneratorPage.jsx`

**Requirements:** Multi-step wizard using MUI `Stepper` component.

**Step 1 — Period (`PeriodStep`)**
```
Select reporting period:
  [Dropdown] Existing period: [FY 2025 ▾] 
  — OR —
  [Date picker] Custom range: Start [____] to End [____]

[Next →]
```

**Step 2 — Scope (`ScopeStep`)**
```
Org Unit: [All accessible ▾ | Select specific org unit]
GHG Scopes: [✓] Scope 1  [✓] Scope 2  [✓] Scope 3
Categories: [All ▾ | Select specific categories...]
Grouping: [By Scope ▾ | By Category | By Module | By Month]

[← Back] [Next →]
```

**Step 3 — Preview (`PreviewStep`)**
```
Fetches GET /emissions/report/ with selected params.
Shows:
  ┌─────────────────────────────────────────┐
  │ Total Emissions: 1,240.5 tCO2e          │
  │ Period: FY 2025 | Org: Smart Village    │
  └─────────────────────────────────────────┘
  Scope breakdown table (scope, tonnes, %)
  [Refresh] 

[← Back] [Export →]
```

**Step 4 — Export (`ExportStep`)**
```
Format: (•) JSON  ( ) CSV
[Save Config for Reuse] → opens name input → calls POST /report-configs/
[Download CSV] → calls downloadReportCsv()
[Copy JSON] → copies response to clipboard

[← Back] [Done]
```

**State management:**
```javascript
const [step, setStep] = useState(0);
const [config, setConfig] = useState({
  reporting_period_id: null,
  custom_start: null,
  custom_end: null,
  org_unit_id: null,
  ghg_scopes: [1, 2, 3],
  categories: [],
  grouping: 'scope',
  output_format: 'json',
});
const [reportData, setReportData] = useState(null);
const [loading, setLoading] = useState(false);
```

**Key behavior:**
- Step 3 auto-fetches preview when user arrives (debounced)
- Step 4 "Save Config" creates a `ReportConfig` via POST, shows success snackbar
- Step 4 "Download CSV" uses `downloadReportCsv()` → triggers browser download
- Back button does NOT re-fetch — preserve state
- All steps show progress in MUI `Stepper` at top

---

### G2.4 — `SavedReportsPage.jsx` (Saved Configs)

**File:** `carbon-frontend/src/pages/emissions/SavedReportsPage.jsx`

Simple list page of saved `ReportConfig` records. Each row shows:
- Config name, created by, last run, reporting period, org unit
- Actions: Run again (POST to `/run/`), Edit, Delete

On "Run again" → shows report results in a drawer or navigates to ReportGeneratorPage with pre-filled config.

---

### G2.5 — Route Registration

**File:** `carbon-frontend/src/App.jsx`

Add imports:
```jsx
import EmissionFactorsPage from "./pages/emissions/EmissionFactorsPage";
import ReportGeneratorPage from "./pages/emissions/ReportGeneratorPage";
import SavedReportsPage from "./pages/emissions/SavedReportsPage";
```

Add routes inside `<RequireAuth>` and `<RequireContext>`:
```jsx
{/* Emission Factor Manager (admin-accessible) */}
<Route path="/admin/emission-factors" element={<EmissionFactorsPage />} />

{/* Report Generator (data owners + admins) */}
<Route path="/data-owner/reports" element={<SavedReportsPage />} />
<Route path="/data-owner/reports/generate" element={<ReportGeneratorPage />} />
```

---

### G2.6 — Sidebar Entries

**File:** `carbon-frontend/src/components/SidebarMenu.jsx`

**Admin sidebar** — add entry under existing admin section:
```jsx
<MenuItem
  to="/admin/emission-factors"
  icon={<ScienceIcon />}
  label="Emission Factors"
  tooltip="Manage emission conversion factors"
  selected={location.pathname === "/admin/emission-factors"}
  collapsed={collapsed}
/>
```

**Data Owner sidebar** — add entries to `DataOwnerSidebar` (existing, line ~549):
```jsx
<MenuItem
  to="/data-owner/reports"
  icon={<AssessmentIcon />}
  label="Reports"
  tooltip="View and generate emissions reports"
  selected={location.pathname.startsWith("/data-owner/reports")}
  collapsed={collapsed}
/>
```

**Import icons:** `ScienceIcon` from `@mui/icons-material/Science`, `AssessmentIcon` from `@mui/icons-material/Assessment`

---

### G2.7 — Empty States

All three pages must handle:

1. **No data:** Display a centered MUI empty state (icon + message + action button)
2. **Loading:** MUI `CircularProgress` while fetching
3. **Error:** MUI `Alert severity="error"` with retry button
4. **No scope (data owner):** `EmissionFactorsPage` — read-only view with info banner
5. **No configs yet:** `SavedReportsPage` — "No saved reports. Generate your first report." + button to `/data-owner/reports/generate`

---

### G2 — Acceptance Criteria

- [ ] `EmissionFactorsPage` renders with real data from `GET /emissions/factors/`
- [ ] Admins can create/edit/delete factors; data owners see read-only
- [ ] Category and scope filters work
- [ ] `ReportGeneratorPage` wizard: all 4 steps work, back/forward navigation preserves state
- [ ] Step 3 preview shows real data from `GET /emissions/report/`
- [ ] Step 4 "Download CSV" triggers browser file download
- [ ] Step 4 "Save Config" creates a `ReportConfig` and shows snackbar
- [ ] `SavedReportsPage` lists configs, "Run again" returns report data
- [ ] Routes `/admin/emission-factors`, `/data-owner/reports`, `/data-owner/reports/generate` all resolve
- [ ] Sidebar entries appear for correct roles
- [ ] `npm run build` passes with no errors

---

## API Contract (G1 → G2 Interface)

### `GET /carbon-api/emissions/report-configs/`
```json
[
  {
    "id": 1,
    "name": "FY 2026 Smart Village Annual",
    "created_by": 5,
    "created_by_username": "ahmed",
    "reporting_period": 2,
    "reporting_period_name": "FY 2026",
    "custom_start": null,
    "custom_end": null,
    "org_unit": 5,
    "org_unit_name": "Smart Village Campus",
    "ghg_scopes": [1, 2, 3],
    "categories": [],
    "output_format": "json",
    "grouping": "scope",
    "include_dq_status": true,
    "include_unverified": false,
    "last_run_at": "2026-07-22T14:30:00Z",
    "created_at": "2026-07-21T10:00:00Z",
    "updated_at": "2026-07-22T14:30:00Z"
  }
]
```

### `POST /carbon-api/emissions/report-configs/{id}/run/`
```json
{
  "config_id": 1,
  "config_name": "FY 2026 Smart Village Annual",
  "reporting_period": { "id": 2, "name": "FY 2026", "status": "open" },
  "date_range": { "start": null, "end": null },
  "org_unit_id": 5,
  "total_co2e_tonnes": 1240.5,
  "calculation_count": 1847,
  "scope_breakdown": [
    { "scope": 1, "scope_name": "Scope 1 - Direct", "co2e_tonnes": 320.1, "percentage": 25.8, "calculation_count": 412 },
    { "scope": 2, "scope_name": "Scope 2 - Indirect Energy", "co2e_tonnes": 850.4, "percentage": 68.6, "calculation_count": 1124 },
    { "scope": 3, "scope_name": "Scope 3 - Value Chain", "co2e_tonnes": 70.0, "percentage": 5.6, "calculation_count": 311 }
  ],
  "category_breakdown": [
    { "category": "electricity", "category_name": "Electricity Grid", "scope": 2, "co2e_tonnes": 850.4, "calculation_count": 1124 }
  ],
  "module_breakdown": [],
  "generated_at": "2026-07-23T09:00:00Z"
}
```

### `GET /carbon-api/emissions/report/?format=csv&org_unit_id=5&reporting_period_id=2`
Returns: `Content-Type: text/csv` attachment with rows:
```
Scope,Category,CO2e (tonnes),Count
Scope 1,Stationary Combustion,320.1,412
Scope 2,Electricity Grid,850.4,1124
Scope 3,Transportation,70.0,311
```

---

## Result File

When both G1 and G2 are done, file `TASK-RESULT-CARBON-P2.md` in the root with:
- Summary of what was implemented
- Test output from G1 (`pytest` result)
- Frontend build confirmation from G2 (`npm run build`)
- List of new files created
- Any deviations from this spec and why
