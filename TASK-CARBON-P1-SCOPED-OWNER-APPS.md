# TASK: Carbon Product Apps — P1 Scoped Data Owner Portal + Dashboard

> **Track F — Carbon Product Apps, Priority 1**  
> **Parallel execution:** F1 (Backend) and F2 (Frontend) have zero dependencies and can run simultaneously  
> **Prerequisite:** Data Trust Core Phase 1 complete (326 tests passing) ✅  
> **Architecture reference:** `plans/CARBON_PRODUCT_APPS_ARCHITECTURE.md`

---

## Worker Split

| Worker | Track | Scope |
|---|---|---|
| **Worker 1** | F1 — Backend | RBAC hardening + `OwnerDashboardView` API |
| **Worker 2** | F2 — Frontend | Scoped Portal UI + Owner Dashboard page |

---

---

# TRACK F1 — BACKEND: RBAC Hardening + Owner Dashboard API

## Context

The Data Trust Core backend has org-unit RBAC in all DQ ViewSets (already restrictive). However:
1. `AssetProfileViewSet.get_queryset()` in `backend/catalog/views.py` has **no org_unit scoping** — a user with no org_unit assignments currently sees all assets from all campuses. This must be fixed.
2. `DQRuleViewSet.get_queryset()` needs verification that it's correctly restrictive.
3. A new `OwnerDashboardView` must be added to `backend/emissions/views.py` to power the data owner KPI dashboard.

## Scope — what to build

### F1.1 — Harden `AssetProfileViewSet.get_queryset()`

**File:** `backend/catalog/views.py`

Current code at line 190:
```python
def get_queryset(self):
    ensure_asset_profiles()
    qs = AssetProfile.objects.select_related(...)...
    p = self.request.query_params
    # ... only query param filters, NO org_unit scoping
```

**Required change:** After `ensure_asset_profiles()`, add org_unit scoping:

```python
def get_queryset(self):
    if getattr(self, 'swagger_fake_view', False):
        return AssetProfile.objects.none()
    ensure_asset_profiles()
    qs = AssetProfile.objects.select_related(
        'data_table', 'data_field', 'data_field__data_table',
        'domain', 'owner', 'steward', 'glossary_term',
    ).prefetch_related('tags')

    # Org-unit scoping — staff/superuser see all; others scoped to their org_unit subtree
    user = self.request.user
    if not (user.is_superuser or user.is_staff):
        from accounts.models import ScopedRole
        org_unit_ids = ScopedRole.objects.filter(
            user=user, is_active=True
        ).values_list('org_unit_id', flat=True).distinct()
        if not org_unit_ids:
            return AssetProfile.objects.none()
        qs = qs.filter(
            Q(data_table__module__org_unit_id__in=org_unit_ids) |
            Q(data_field__data_table__module__org_unit_id__in=org_unit_ids)
        )
    
    # ... rest of existing query param filters unchanged
```

**Acceptance:** A user with `ScopedRole` for org_unit=5 (Smart Village) gets ONLY assets belonging to modules in org_unit=5 or its subtree; users with no ScopedRoles get HTTP 200 with empty results (not all assets).

### F1.2 — Verify `DQRuleViewSet` scoping

**File:** `backend/dq/views.py`, line ~123

Check `DQRuleViewSet.get_queryset()`. If it does NOT return `.none()` when user has no org_units, apply the same pattern as `FieldProfileViewSet`. If already correct, leave unchanged and note in result file.

### F1.3 — `OwnerDashboardView` in emissions

**File:** `backend/emissions/views.py` (new view added at end of file)

New endpoint: `GET /carbon-api/emissions/owner-dashboard/`

Query parameters:
- `org_unit` (optional int) — specific org_unit to scope to; defaults to user's primary org_unit
- `period` (optional int) — `ReportingPeriod.id`; defaults to latest non-closed period

**Response contract:**
```json
{
  "org_unit": {
    "id": 5,
    "name": "Smart Village Campus",
    "org_type": "campus"
  },
  "reporting_period": {
    "id": 2,
    "name": "FY 2025",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "status": "open"
  },
  "emissions": {
    "total_co2e_tonne": 1240.5,
    "scope1_co2e_tonne": 320.1,
    "scope2_co2e_tonne": 850.4,
    "scope3_co2e_tonne": 70.0,
    "calculation_count": 1847,
    "previous_period_co2e_tonne": 1280.0,
    "change_pct": -3.1
  },
  "data_quality": {
    "avg_quality_score": 87.3,
    "passing_count": 12,
    "warning_count": 3,
    "failing_count": 1,
    "unknown_count": 2
  },
  "modules": {
    "total": 5,
    "with_data": 4,
    "without_data": 1,
    "without_data_names": ["Chilled Water S2"]
  },
  "recent_events": [
    {
      "id": 101,
      "action": "update",
      "entity_type": "AssetProfile",
      "timestamp": "2026-07-18T10:32:00Z",
      "user": "john.doe"
    }
  ]
}
```

**Implementation logic:**
```python
class OwnerDashboardView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Determine org_unit scope
        # 1. If org_unit param provided, verify user has access to it
        # 2. Otherwise, use user's first ScopedRole org_unit
        # 3. Expand to subtree using OrgUnit.get_descendant_ids()
        
        # Determine reporting period
        # 1. If period param provided, use it
        # 2. Otherwise, latest non-closed ReportingPeriod
        
        # Emissions aggregation
        # Filter Calculation.objects by module__org_unit_id__in=descendant_ids
        # AND reporting_year = period.start_date.year (if period is annual)
        # OR reporting_period = period (if period FK used)
        # Aggregate: Sum(co2e_kg), grouped by scope → convert kg to tonnes (/1000)
        
        # Previous period: same logic for the period before selected
        
        # Data quality: query AssetProfile where data_table__module__org_unit_id__in=...
        # Count by quality_status
        
        # Modules: count modules in org_unit subtree; check which have Calculations
        
        # Recent events: GovernanceEvent filtered by assets in scope, last 5
```

**RBAC guards:**
- If user is not staff/superuser, verify user has a `ScopedRole` for the requested org_unit (or an ancestor). Raise `PermissionDenied` if not.
- Staff/superuser: can pass any org_unit.

### F1.4 — Register URL

**File:** `backend/emissions/urls.py`

Add:
```python
from .views import OwnerDashboardView
# ...
path('owner-dashboard/', OwnerDashboardView.as_view(), name='owner-dashboard'),
```

### F1.5 — Tests

**File:** `backend/emissions/tests.py` OR new `backend/emissions/tests/test_owner_dashboard.py`

Test cases:
1. `test_owner_dashboard_returns_scoped_data` — user with ScopedRole for org_unit=A gets emissions only for org_unit=A
2. `test_owner_dashboard_excludes_other_org_units` — user A cannot see org_unit=B emissions
3. `test_owner_dashboard_no_scope_returns_empty` — user with no ScopedRoles gets 200 with zeroed metrics
4. `test_owner_dashboard_staff_sees_all` — staff user without ScopedRoles sees all data when org_unit param provided
5. `test_asset_profile_viewset_org_scoping` — user with org_unit=A gets only org_unit=A assets

## Definition of Done (F1)

- [ ] `AssetProfileViewSet.get_queryset()` scopes by org_unit; staff bypass
- [ ] `DQRuleViewSet.get_queryset()` verified/fixed to be restrictive
- [ ] `GET /carbon-api/emissions/owner-dashboard/` returns correct JSON contract
- [ ] URL registered in `emissions/urls.py`
- [ ] All new tests pass; existing 326 tests still pass
- [ ] No migrations needed (no new models)
- [ ] Write `TASK-RESULT-CARBON-P1-F1.md` with test output evidence

---

---

# TRACK F2 — FRONTEND: Scoped Data Owner Portal + Dashboard

## Context

AASTMT campus data owners (e.g., Smart Village Facilities manager) need a dedicated, scoped UI experience. They should NOT see the full admin catalog — only data relevant to their org_unit:
- Their modules and assets
- Their data quality scores
- Their emissions KPIs
- Their submission status

**Key principle:** The backend already filters data by org_unit — the frontend just needs to present it cleanly for a data owner persona.

## Architecture decisions

- New route namespace: `/data-owner/` (separate from `/catalog/` admin routes)
- Role gate: any authenticated user with at least one `ScopedRole` can access `/data-owner/`
- Reuse existing components: `FilteredDataGrid`, `MetricCard`, `BaseDetailPage`, `carbonTheme`
- New API functions go in `carbon-frontend/src/api/emissions.js`

## Scope — what to build

### F2.1 — New API functions

**File:** `carbon-frontend/src/api/emissions.js` (add to existing file)

```js
// Owner Dashboard API
export async function fetchOwnerDashboard(token, orgUnitId = null, periodId = null) {
  const params = new URLSearchParams();
  if (orgUnitId) params.set('org_unit', orgUnitId);
  if (periodId) params.set('period', periodId);
  const url = `${API_BASE}/emissions/owner-dashboard/${params.toString() ? '?' + params : ''}`;
  return apiFetch(url, { method: 'GET', token });
}

// Fetch reporting periods for selector
export async function fetchReportingPeriods(token, status = null) {
  const url = status
    ? `${API_BASE}/emissions/reporting-periods/?status=${status}`
    : `${API_BASE}/emissions/reporting-periods/`;
  return apiFetch(url, { method: 'GET', token });
}
```

Also check if `fetchOwnerDashboard` already exists; if so, extend it or reuse.

### F2.2 — `DataOwnerPortalPage.jsx`

**File:** `carbon-frontend/src/pages/data-owner/DataOwnerPortalPage.jsx` (new)

**Route:** `/data-owner/`

This is the landing page for a data owner. It shows:
1. **Header:** "Welcome, [name] — [Org Unit Name]" with org unit switcher if user has multiple
2. **Domain cards grid:** Each domain the user has assets in, with:
   - Asset count
   - Quality badge (passing/warning/failing)
   - "View Assets" link
3. **Quick stats row:** Total assets | Assets needing attention | Modules with missing data
4. **Recent activity feed:** Last 5 governance events for their scope

**Implementation notes:**
- On mount: fetch `GET /catalog/domains/` (already scoped) + `GET /catalog/assets/` (now scoped) + `GET /dq/metrics/`
- Use `context.org_unit` from `useAuth()` as default scope
- Domain cards use MUI `Card` with quality color accent (green/amber/red)
- "View Assets" navigates to `/data-owner/assets?domain=<id>`

```jsx
export default function DataOwnerPortalPage() {
  const { user, context } = useAuth();
  const [domains, setDomains] = useState([]);
  const [dqMetrics, setDqMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Load on mount
  // Display domain cards + quick stats
  // Recent activity list
}
```

### F2.3 — `DataOwnerDashboardPage.jsx`

**File:** `carbon-frontend/src/pages/data-owner/DataOwnerDashboardPage.jsx` (new)

**Route:** `/data-owner/dashboard`

The KPI emissions + data quality dashboard for a campus data owner.

**Layout:** 
```
┌─────────────────────────────────────────────────────────────┐
│  Period: [FY 2025 ▼]   Org Unit: [Smart Village ▼]          │
├──────────┬──────────┬──────────┬──────────────────────────  │
│ Total    │ Scope 1  │ Scope 2  │ Scope 3                    │
│ 1,240t   │ 320t     │ 850t     │ 70t                        │
│ ▼3.1% vs │ CO2e     │ CO2e     │ CO2e                       │
│ prev     │          │          │                            │
├──────────┴──────────┴──────────┴────────────────────────────│
│  Data Quality           │  Submission Status                │
│  Score: 87%             │  4/5 modules with data            │
│  ✅ 12 passing          │  ⚠️  Chilled Water S2 missing     │
│  ⚠️   3 warning          │                                   │
│  ❌  1 failing           │                                   │
├─────────────────────────┴───────────────────────────────────│
│  Recent Activity (last 5 events)                             │
│  Jul 18 • AssetProfile updated • john.doe                   │
│  Jul 17 • DQ rule run • system                              │
└─────────────────────────────────────────────────────────────┘
```

**Components to use/create:**
- `MetricCard` (existing in `src/components/dashboard/MetricCard.jsx`) for the 4 scope cards
- `DataQualityCard` (existing in `src/components/dq/DataQualityCard.jsx`) for DQ summary
- New `SubmissionStatusCard.jsx` (small component, inline is fine)
- `PeriodSelector` — a `<Select>` populated from `fetchReportingPeriods()`
- `OrgUnitSelector` — a `<Select>` if user has multiple org_unit assignments

**API call:** `fetchOwnerDashboard(token, orgUnitId, periodId)`

### F2.4 — `DataOwnerAssetsPage.jsx`

**File:** `carbon-frontend/src/pages/data-owner/DataOwnerAssetsPage.jsx` (new)

**Route:** `/data-owner/assets`

A simplified version of `AssetsPage.jsx` that:
- Is always pre-filtered to the user's org_unit scope (no org_unit filter needed — backend handles it)
- Hides admin-only columns (owner assignment, classification editor)
- Shows quality badge prominently
- Links to the existing `/catalog/assets/:assetId` detail page (no change to detail page)
- Supports filtering by domain (from URL query param `?domain=<id>`)

**Implementation:** Can copy ~80% from `AssetsPage.jsx`, remove admin controls, add domain filter from URL.

### F2.5 — Route registration

**File:** `carbon-frontend/src/App.jsx`

Add inside `<Route element={<RequireContext />}>`:
```jsx
{/* Data Owner Portal — scoped experience */}
<Route path="/data-owner" element={<DataOwnerPortalPage />} />
<Route path="/data-owner/dashboard" element={<DataOwnerDashboardPage />} />
<Route path="/data-owner/assets" element={<DataOwnerAssetsPage />} />
```

No role gate needed initially — all authenticated users can access; the backend scoping handles the data filtering. Users with no org_units see empty state.

### F2.6 — Sidebar entry

**File:** `carbon-frontend/src/components/SidebarMenu.jsx`

Add a new sidebar section "Data Owner" (or integrate into existing sidebar logic that shows items based on `availablePerspectives`):

```jsx
// In the sidebar menu items, add a section that appears for users with scoped roles
{
  label: 'My Data',
  icon: <AssignmentIndIcon />,  // or similar
  items: [
    { label: 'My Portal', path: '/data-owner', icon: <DashboardIcon /> },
    { label: 'My Dashboard', path: '/data-owner/dashboard', icon: <BarChartIcon /> },
    { label: 'My Assets', path: '/data-owner/assets', icon: <StorageIcon /> },
  ]
}
```

Show this section only when `context?.org_units?.length > 0` (i.e., user has scoped role assignments). Check how the existing sidebar conditions work and follow the same pattern.

### F2.7 — Empty state handling

In all three new pages, if the API returns empty data (user has no org_unit scope), show a clear empty state:
```jsx
<Box sx={{ textAlign: 'center', py: 8 }}>
  <Typography variant="h6">No data scope assigned</Typography>
  <Typography color="text.secondary">
    Contact your administrator to assign you to an organizational unit.
  </Typography>
</Box>
```

## Component hierarchy

```
/data-owner/                    → DataOwnerPortalPage.jsx
  └── DomainCard (inline)
  └── QuickStats (inline)
  └── RecentActivityFeed (inline)

/data-owner/dashboard           → DataOwnerDashboardPage.jsx
  ├── PeriodSelector (inline)
  ├── MetricCard (existing)
  ├── DataQualityCard (existing)
  └── SubmissionStatusCard (inline)

/data-owner/assets              → DataOwnerAssetsPage.jsx
  └── FilteredDataGrid (existing)
```

## Files to create

| File | Notes |
|---|---|
| `carbon-frontend/src/pages/data-owner/DataOwnerPortalPage.jsx` | New |
| `carbon-frontend/src/pages/data-owner/DataOwnerDashboardPage.jsx` | New |
| `carbon-frontend/src/pages/data-owner/DataOwnerAssetsPage.jsx` | New |

## Files to modify

| File | Change |
|---|---|
| `carbon-frontend/src/api/emissions.js` | Add `fetchOwnerDashboard`, `fetchReportingPeriods` |
| `carbon-frontend/src/App.jsx` | Add 3 new routes under `/data-owner/` |
| `carbon-frontend/src/components/SidebarMenu.jsx` | Add "My Data" sidebar section |

## Definition of Done (F2)

- [ ] `/data-owner/` renders domain cards with quality badges, scoped to user's org_unit
- [ ] `/data-owner/dashboard` renders KPI tiles (total CO2e, scope breakdown, DQ score, submission status)
- [ ] `/data-owner/assets` renders filtered asset list, respects `?domain=<id>` query param
- [ ] Empty state shown when user has no org_unit scope
- [ ] Sidebar shows "My Data" section for scoped users
- [ ] All routes registered in `App.jsx`
- [ ] No new MUI theme — uses `carbonTheme` throughout
- [ ] No TypeScript errors / console errors
- [ ] Write `TASK-RESULT-CARBON-P1-F2.md` with screenshot evidence or DOM inspection

---

## Parallel Execution Notes

```
Worker 1 (F1 backend)            Worker 2 (F2 frontend)
========================          ==========================
F1.1: Harden AssetProfile         F2.1: Add API functions
      get_queryset()               F2.2: DataOwnerPortalPage
F1.2: Verify DQRule scoping       F2.3: DataOwnerDashboardPage
F1.3: OwnerDashboardView          F2.4: DataOwnerAssetsPage
F1.4: Register URL                F2.5: Register routes
F1.5: Tests                       F2.6: Sidebar entry
                                   F2.7: Empty states
```

Both workers can start immediately. F2 Worker should mock the `/owner-dashboard/` API response during development if F1 is not yet complete — the contract is fixed in F1.3 above.

---

## Context for the implementing worker

### Key existing patterns to follow

- **Org-unit scoping:** See how `FieldProfileViewSet.get_queryset()` does it in `backend/dq/views.py:68` — exact same pattern for F1.1
- **Frontend API calls:** See `carbon-frontend/src/api/dq.js` for the `apiFetch` pattern
- **MetricCard:** `carbon-frontend/src/components/dashboard/MetricCard.jsx`
- **DataQualityCard:** `carbon-frontend/src/components/dq/DataQualityCard.jsx`
- **FilteredDataGrid:** `carbon-frontend/src/components/FilteredDataGrid.jsx`
- **Auth context:** `useAuth()` from `carbon-frontend/src/auth/AuthContext.jsx` — provides `user`, `context`, `token`
- **Correlation IDs:** Every API response has `X-Correlation-ID` — already handled by the `apiFetch` wrapper

### AASTMT org unit structure (seed data context)

- AASTMT (root campus)
  - Abu Qir Campus
    - Facilities & Utilities (has real electricity/water data)
  - Smart Village Campus
    - (currently empty — use this for scoped user test)

### Do NOT change

- Existing admin catalog pages (`/catalog/assets`, `/catalog/dq-dashboard`, etc.)
- Any `catalog`, `mdm`, `dq` app code beyond F1.1 and F1.2
- Frontend routing for existing catalog pages
- Any existing test files
