# TASK: Move 1 — Carbon App Seam (Route Namespace Migration + DQ Wiring)

> **Track G — Platform/App Separation, Move 1**
> **Architecture reference:** `docs/PLATFORM_APP_MODEL.md` § 8 (Move 1)
> **Manifest already created:** `carbon-frontend/src/apps/carbon/manifest.js` ✅
> **Parallel execution:** G1 (Frontend) and G2 (Backend) have zero dependencies — start simultaneously.

---

## Background (read before starting)

The platform model declares Carbon's frontend route namespace as `/carbon/*`.  
The current implementation uses `/data-owner/*` — a pre-namespace leftover.  
Move 1 migrates this to `/carbon/owner/*` with backwards-compatible redirects so no links break.

The backend `OwnerDashboardAPIView` returns a **hardcoded stub** for the `data_quality_summary` block.  
Move 1 wires it to real DQ data from the database.

**Do NOT:**
- Move any JSX files to a different folder
- Change any `catalog/`, `mdm/`, `dq/`, `dataschema/` backend files
- Add new models or migrations
- Touch the Emissions Calculator routes (`/emissions/*`)
- Touch the admin routes (`/admin/*`, `/catalog/*`)

---

---

# TRACK G1 — FRONTEND: Route Namespace Migration

## Scope: 3 files, surgical edits only

### G1.1 — `carbon-frontend/src/App.jsx`

**Currently (lines 161–164):**
```jsx
{/* Data Owner Portal Routes */}
<Route path="/data-owner" element={<DataOwnerPortalPage />} />
<Route path="/data-owner/dashboard" element={<DataOwnerDashboardPage />} />
<Route path="/data-owner/assets" element={<DataOwnerAssetsPage />} />
```

**Replace with:**
```jsx
{/* Carbon App — Data Owner Routes (namespace: /carbon/owner/*) */}
<Route path="/carbon/owner/portal" element={<DataOwnerPortalPage />} />
<Route path="/carbon/owner/dashboard" element={<DataOwnerDashboardPage />} />
<Route path="/carbon/owner/assets" element={<DataOwnerAssetsPage />} />
{/* Legacy redirects — remove in Move 2 */}
<Route path="/data-owner" element={<Navigate to="/carbon/owner/portal" replace />} />
<Route path="/data-owner/dashboard" element={<Navigate to="/carbon/owner/dashboard" replace />} />
<Route path="/data-owner/assets" element={<Navigate to="/carbon/owner/assets" replace />} />
```

**Note:** `Navigate` is already imported at line 3 of `App.jsx`.  
`DataOwnerPortalPage`, `DataOwnerDashboardPage`, `DataOwnerAssetsPage` are already imported at lines 54–56.

---

### G1.2 — `carbon-frontend/src/components/SidebarMenu.jsx`

**Currently (lines 571–597):**
```jsx
<MenuItem
  to="/data-owner"
  icon={<DashboardIcon />}
  label="My Portal"
  tooltip="Overview of your domain assets"
  selected={location.pathname === "/data-owner"}
  collapsed={collapsed}
  sx={{ mb: 0.5 }}
/>
<MenuItem
  to="/data-owner/dashboard"
  icon={<AnalyticsIcon />}
  label="My Dashboard"
  tooltip="Emissions KPIs and data quality"
  selected={location.pathname === "/data-owner/dashboard"}
  collapsed={collapsed}
  sx={{ mb: 0.5 }}
/>
<MenuItem
  to="/data-owner/assets"
  icon={<TableIcon />}
  label="My Assets"
  tooltip="Scoped asset browser"
  selected={location.pathname === "/data-owner/assets"}
  collapsed={collapsed}
  sx={{ mb: 0.5 }}
/>
```

**Replace with:**
```jsx
<MenuItem
  to="/carbon/owner/portal"
  icon={<DashboardIcon />}
  label="My Portal"
  tooltip="Overview of your domain assets"
  selected={location.pathname === "/carbon/owner/portal"}
  collapsed={collapsed}
  sx={{ mb: 0.5 }}
/>
<MenuItem
  to="/carbon/owner/dashboard"
  icon={<AnalyticsIcon />}
  label="My Dashboard"
  tooltip="Emissions KPIs and data quality"
  selected={location.pathname === "/carbon/owner/dashboard"}
  collapsed={collapsed}
  sx={{ mb: 0.5 }}
/>
<MenuItem
  to="/carbon/owner/assets"
  icon={<TableIcon />}
  label="My Assets"
  tooltip="Scoped asset browser"
  selected={location.pathname === "/carbon/owner/assets"}
  collapsed={collapsed}
  sx={{ mb: 0.5 }}
/>
```

---

### G1.3 — `carbon-frontend/src/pages/data-owner/DataOwnerPortalPage.jsx`

Three `navigate()` calls in this file use old paths. Replace all three:

| Line (approx) | Current value | Replace with |
|---|---|---|
| ~184 | `navigate(\`/data-owner/assets?domain=${domain.id}\`)` | `navigate(\`/carbon/owner/assets?domain=${domain.id}\`)` |
| ~406 | `navigate('/data-owner/dashboard')` | `navigate('/carbon/owner/dashboard')` |
| ~421 | `navigate('/data-owner/assets')` | `navigate('/carbon/owner/assets')` |

Use search-and-replace on the string `/data-owner/` → `/carbon/owner/` **within this file only**.  
Do NOT globally replace across all files.

---

## Definition of Done (G1)

- [ ] `GET /carbon/owner/portal` renders `DataOwnerPortalPage`
- [ ] `GET /carbon/owner/dashboard` renders `DataOwnerDashboardPage`
- [ ] `GET /carbon/owner/assets` renders `DataOwnerAssetsPage`
- [ ] `GET /data-owner` redirects to `/carbon/owner/portal` (no 404)
- [ ] `GET /data-owner/dashboard` redirects to `/carbon/owner/dashboard`
- [ ] `GET /data-owner/assets` redirects to `/carbon/owner/assets`
- [ ] Sidebar "My Portal", "My Dashboard", "My Assets" links resolve to new paths
- [ ] "View Assets →" button inside domain cards navigates to `/carbon/owner/assets?domain=<id>`
- [ ] No console errors
- [ ] Write `TASK-RESULT-MOVE1-G1.md` confirming each DoD item

---

---

# TRACK G2 — BACKEND: Wire Real DQ Data into OwnerDashboardAPIView

## Scope: 1 file, 1 function, replace stub block only

**File:** `backend/emissions/views.py`

**Location:** Inside `OwnerDashboardAPIView.get()` — the stub block at approximately lines 731–737:

```python
# DQ metrics (stub for now - integration with DQ app later)
dq_summary = {
    'quality_score': 85,
    'rules_passing': 42,
    'rules_total': 50,
    'tables_profiled': 156,
}
```

**Replace with real DQ data:**

```python
# DQ metrics — real data from AssetProfile quality_status
from catalog.models import AssetProfile
from django.db.models import Q as Q_import

# Scope asset profiles to user's org units (same scoping as calc_qs above)
if org_units is not None:
    asset_qs = AssetProfile.objects.filter(
        Q_import(data_table__module__org_unit_id__in=org_units) |
        Q_import(data_field__data_table__module__org_unit_id__in=org_units)
    )
else:
    asset_qs = AssetProfile.objects.all()

total_assets = asset_qs.count()
passing_count = asset_qs.filter(quality_status='passing').count()
warning_count = asset_qs.filter(quality_status='warning').count()
failing_count = asset_qs.filter(quality_status='failing').count()
unknown_count = asset_qs.filter(quality_status='unknown').count()

# Quality score = (passing / total * 100) if any assets exist
quality_score = round((passing_count / total_assets * 100), 1) if total_assets > 0 else 0.0

dq_summary = {
    'quality_score': quality_score,
    'passing_count': passing_count,
    'warning_count': warning_count,
    'failing_count': failing_count,
    'unknown_count': unknown_count,
    'total_assets': total_assets,
}
```

**Note:** `Q` is already imported at the top of `backend/emissions/views.py` as `Q`. Use `Q_import` alias inside the local scope to avoid shadowing. Or check the import and use `Q` directly if there is no naming conflict in this local block.

**Important:** The import `from catalog.models import AssetProfile` must go **inside the method body** (local import), NOT at the top of the file. This prevents a circular import between `emissions` and `catalog`.

---

## Definition of Done (G2)

- [ ] `GET /api/v1/emissions/owner-dashboard/` returns `data_quality_summary` with real counts (not hardcoded 85/42/50/156)
- [ ] A user scoped to org_unit=5 gets only asset profiles belonging to that org_unit subtree
- [ ] Staff/superuser gets aggregate across all org_units
- [ ] Zero new migrations (no model changes)
- [ ] Existing tests still pass (`python manage.py test emissions` from `backend/`)
- [ ] Write `TASK-RESULT-MOVE1-G2.md` with the actual JSON response proving real data

---

## Context for implementing workers

### Key files to read before starting

| File | Why |
|---|---|
| [`carbon-frontend/src/App.jsx`](carbon-frontend/src/App.jsx) | Route registration — lines 161–164 are your target |
| [`carbon-frontend/src/components/SidebarMenu.jsx`](carbon-frontend/src/components/SidebarMenu.jsx) | Sidebar links — lines 571–597 are your target |
| [`carbon-frontend/src/pages/data-owner/DataOwnerPortalPage.jsx`](carbon-frontend/src/pages/data-owner/DataOwnerPortalPage.jsx) | Lines ~184, ~406, ~421 have old paths |
| [`backend/emissions/views.py`](backend/emissions/views.py) | `OwnerDashboardAPIView.get()` lines ~731–737 is your target |
| [`backend/catalog/models.py`](backend/catalog/models.py) | `AssetProfile.quality_status` field choices |
| [`carbon-frontend/src/apps/carbon/manifest.js`](carbon-frontend/src/apps/carbon/manifest.js) | The manifest that defines the route namespace — read for context |

### How `AssetProfile.quality_status` works (for G2 worker)

`AssetProfile` has a `quality_status` CharField with choices: `passing`, `warning`, `failing`, `unknown`.  
It is linked to `DataTable` via `AssetProfile.data_table` (OneToOne) and to `DataField` via `AssetProfile.data_field` (OneToOne).  
Both `data_table` and `data_field` link to modules → org_units.

### Architecture constraint (both workers)

These changes are **Move 1 of the strangler-fig migration** described in `docs/PLATFORM_APP_MODEL.md`.  
The constraint: **no breaking changes**. Old URLs redirect. New URLs are additive. No data moves.
