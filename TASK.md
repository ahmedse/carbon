# TASK.md — RUN A5: Role-Adaptive UI (Perspectives Architecture)

---

## MASTER CONTEXT

**Protocol:** Master/Worker handoff (see `.clinerules/master-worker-protocol.md`)  
**Master:** Planner (this file's author)  
**Worker:** Raptor/Copilot (executor)  
**Active RUN sequence:** A0 ✅ → A1 ✅ → A2 ✅ → A3 ✅ → A4 ✅ → **A5** → A6

**Previous RUN findings:**
- **A0:** Baseline audit — deployment blockers identified, permission model sound
- **A1:** Repository cleaned — 48,667 lines removed, docs organized
- **A2:** Governance RBAC fixed — global admins only can write catalog/mdm/dq
- **A3:** Data-owner experience fixed — DataSchema 403 resolved, schema write protection enforced
- **A4:** Admin experience verified — global admin full CRUD confirmed, org-scoped admin limits verified

**Current state:**
- ✅ Backend fully functional — all roles/permissions working correctly
- ✅ Org scoping enforced server-side (modules, tables, data rows)
- ✅ Frontend exists: single React app, AdminRoute, sidebar, dashboards, data entry grid
- ⚠️ **Dashboard numbers NOT org-scoped** — data leakage: a data-owner sees ALL AASTMT totals (critical bug)
- ⚠️ **Sidebar is one-size-fits-all** — data-owners see admin menu items; admin sidebar is cluttered
- ⚠️ **No perspective switcher** — admin must manually navigate to schema/admin pages
- ⚠️ **No role-aware landing** — all users land at same Executive Summary page

**Design decision:** See `docs/DESIGN_UI_ARCHITECTURE_A5.md` — ONE unified app with role-adaptive perspectives (Ataccama ONE pattern). Three perspectives: Data Entry, Dashboards, Admin.

**Roadmap:**
- **A0–A4** ✅: Backend foundation solid
- **A5** (this RUN): Role-adaptive UI — perspectives architecture
- **A6**: Deployment-readiness gate (security hardening)

---

## 1. HEADER

**RUN ID:** A5  
**Title:** Role-Adaptive UI — Perspectives Architecture  
**Type:** FRONTEND + BACKEND  
**Worker:** Raptor  
**Master:** Planner  
**Date Issued:** 2026-07-18

---

## 2. OBJECTIVE

**Problem:** The frontend is a single flat experience — every user sees the same sidebar regardless of role. Dashboard numbers are not org-scoped (a Transport data-owner sees the full AASTMT total — a data leak). There is no perspective switching.

**Goal:** Implement the Ataccama-inspired role-adaptive perspectives model (documented in `docs/DESIGN_UI_ARCHITECTURE_A5.md`):

1. **Fix dashboard data scoping leak** — emissions aggregates must filter by user's allowed modules (critical backend fix)
2. **Perspective switcher in header** — Data Entry / Dashboards / Admin tabs; Admin tab only for `admins_group` users
3. **Refactor sidebar per perspective** — Data Entry sidebar (lean: scopes → modules → tables) vs Admin sidebar (Org / Schema / Platform sections)
4. **Role-aware landing page** — data-only users land on their first module; admins land on Executive Summary
5. **Scope banner** — tell data-owners clearly "You are viewing: [Their OrgUnit]"

**Success:** After this RUN:
- ✅ Data-owner's dashboard shows ONLY their org's numbers (not all AASTMT)
- ✅ Data-owner's sidebar is lean — only their modules/tables, no admin noise
- ✅ Admin user sees perspective tabs in header — can switch between Data Entry and Admin
- ✅ Admin sidebar shows organized sections (Org / Schema / Platform) when in Admin mode
- ✅ User with only data-owner role has NO admin tab visible
- ✅ Role-aware redirect on first load

---

## 3. SCOPE — IN

- **Backend:** Apply org scoping to all emissions aggregate endpoints (`DashboardAPIView`, `YearlyComparisonAPIView`, `ReportAPIView`, `CalculationViewSet`)
- **Backend:** Add `/api/accounts/me/context/` endpoint returning user's effective scope
- **Frontend AuthContext:** Add `currentPerspective` state and `setPerspective` function
- **Frontend Header:** Add perspective switcher tabs (Data Entry | Dashboards | Admin)
- **Frontend SidebarMenu:** Refactor into perspective-driven sections
- **Frontend App.jsx:** Add role-aware redirect on login
- **Frontend Layout:** Add "You are viewing: [OrgUnit]" scope banner for non-admin users
- **Tests:** Verify data-owner dashboard ≠ global admin dashboard (different numbers)

---

## 4. SCOPE — OUT (DO NOT TOUCH)

- **No permission model changes** — A2/A3 fixes are working correctly, do not touch
- **No new backend apps** — no new Django apps, no new migrations beyond what's needed
- **No AI/Pulse/LLM work** — `ai_copilot` remains frozen
- **No reports backend** — missing feature, explicitly deferred
- **No separate admin console** — the design decision is ONE unified app
- **No Ataccama catalog/MDM/DQ UI screens** — those are future RUNs
- **No deployment config** — that's A6

---

## 5. PRECONDITIONS / SETUP

1. **A0–A4 complete** — backend working, all roles verified
2. **Backend running** on `http://localhost:8009`
3. **Frontend running** on `http://localhost:5173` (or check `vite.config.js`)
4. **Test users available:**
   - `global_admin` / `GlobalAdmin_2026!` — global admin
   - `fac.steward` / `FacSteward_2025` — org-scoped admin (org_unit=5)
   - `facilities.officer` / `FacOfficer_2025` — data-owner (org_unit=5)
   - `transport.owner` / `TransOwner_2025` — data-owner (org_unit=4, if exists)
5. **Read before coding:**
   - `docs/DESIGN_UI_ARCHITECTURE_A5.md` — the full design decision
   - `carbon-frontend/src/auth/AuthContext.jsx` — current auth/context state
   - `carbon-frontend/src/components/SidebarMenu.jsx` — current sidebar implementation
   - `carbon-frontend/src/components/Header.jsx` — current header
   - `backend/emissions/views.py` — the endpoints to patch

---

## 6. CONSTRAINTS (MUST / MUST NOT)

### MUST:
- **Read `docs/DESIGN_UI_ARCHITECTURE_A5.md` first** — the architectural decision is documented there
- **Fix the dashboard scoping leak before any frontend work** — this is a data integrity issue
- Test backend boots after each backend change (`python manage.py check`)
- Test frontend builds after each major change (`npm run build` in `carbon-frontend/`)
- Document every curl test for backend changes
- Commit in logical groups (backend scope fix, perspective context, sidebar refactor, header switcher, landing fix)
- Keep the single React app — do NOT create separate apps or routes for admin vs user

### MUST NOT:
- Break existing data-owner access (A3 fixes must remain intact)
- Break existing admin routes (`/admin/org-units`, `/admin/access`, `/admin/users`)
- Remove the `AdminRoute` component — keep it, just enhance it
- Create separate login pages or URLs for different roles
- Duplicate components (one for admin, one for user) — use props/context to adapt
- Change the backend permission model

---

## 7. STEPS

### Step 1: Read Current Code (Required First)

**Objective:** Understand current state before modifying anything.

```bash
cd /home/ahmed/aast/carbon

# 1.1 Read the design decision
cat docs/DESIGN_UI_ARCHITECTURE_A5.md

# 1.2 Check current emissions views
cat backend/emissions/views.py

# 1.3 Check current rbac_utils for get_visible_module_ids
cat backend/accounts/rbac_utils.py

# 1.4 Read AuthContext
cat carbon-frontend/src/auth/AuthContext.jsx

# 1.5 Read current Header
cat carbon-frontend/src/components/Header.jsx

# 1.6 Read current Layout
cat carbon-frontend/src/components/Layout.jsx

# 1.7 Verify backend is running
curl -s http://localhost:8009/carbon-api/ | head -20 || echo "Backend not running — start it first"
```

**Record:**
- Does `get_visible_module_ids` exist in `rbac_utils.py`? (If not, it needs to be created)
- What are the exact view class names in `emissions/views.py`?
- Does `AuthContext` already have a `currentPerspective` state?
- Is the Header a functional or class component?

---

### Step 2: Backend — Fix Dashboard Data Scoping Leak (CRITICAL)

**Objective:** Every emissions aggregate endpoint must filter by user's allowed module set.

**Context:** Per `DESIGN_ORG_ACCESS_MODEL.md §4.6`, dashboard aggregates currently return ALL data regardless of user's org scope. A Transport data-owner sees AASTMT-wide totals. This must be fixed.

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend

# 2.1 Check if get_visible_module_ids exists
grep -n "get_visible_module_ids\|get_allowed_module_ids" accounts/rbac_utils.py

# 2.2 Read the current rbac_utils to understand what helpers exist
cat accounts/rbac_utils.py
```

**If `get_visible_module_ids` does NOT exist, add it to `accounts/rbac_utils.py`:**
```python
def get_visible_module_ids(user):
    """
    Returns None if user has unrestricted access (global admin/superuser).
    Returns a list of allowed module IDs for scoped users.
    Used to scope dashboard aggregates — do NOT use for reference data.
    """
    if user_is_global_admin(user):
        return None  # unrestricted
    return list(get_allowed_module_ids(user, VISIBILITY_ROLES))
```

**Then patch `emissions/views.py`:**
```python
# Add this helper near the top of emissions/views.py
from accounts.rbac_utils import get_visible_module_ids

def _scope_qs(user, qs, module_field='module_id'):
    """Filter queryset to user's allowed modules. Pass-through for global admins."""
    allowed = get_visible_module_ids(user)
    if allowed is None:
        return qs
    return qs.filter(**{f'{module_field}__in': allowed})
```

**Apply `_scope_qs` to each view — find the exact view names first:**
```bash
grep -n "class.*View\|def get\|def list\|queryset" emissions/views.py | head -60
```

Apply to:
- `DashboardAPIView` — the main dashboard summary
- `YearlyComparisonAPIView` — year-over-year chart
- `ReportAPIView` — the GHG report endpoint
- `CalculationViewSet` — the calculations list

**Verification test:**
```bash
# Get tokens
GLOBAL_TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"global_admin","password":"GlobalAdmin_2026!"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access'])")

FAC_TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"facilities.officer","password":"FacOfficer_2025"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access'])")

# Compare dashboard totals — they MUST be different (or fac must be <= global)
echo "=== GLOBAL ADMIN DASHBOARD ==="
curl -s 'http://localhost:8009/carbon-api/emissions/dashboard/' \
  -H "Authorization: Bearer $GLOBAL_TOKEN" | python3 -m json.tool | grep -i total

echo "=== FACILITIES OFFICER DASHBOARD ==="
curl -s 'http://localhost:8009/carbon-api/emissions/dashboard/' \
  -H "Authorization: Bearer $FAC_TOKEN" | python3 -m json.tool | grep -i total
```

**Expected result:** The facilities officer sees ONLY their facility's numbers. If both return identical totals, the scoping is not applied.

**Commit:**
```bash
git add backend/accounts/rbac_utils.py backend/emissions/views.py
git commit -m "fix(emissions): apply org-scoped filtering to all dashboard aggregates

- Add _scope_qs() helper applying get_visible_module_ids() to querysets
- Patch DashboardAPIView, YearlyComparisonAPIView, ReportAPIView, CalculationViewSet
- Global admins bypass filter (allowed=None)
- Data-owners/stewards see only their org subtree's numbers
- Fixes data leakage noted in DESIGN_ORG_ACCESS_MODEL.md §4.6"
```

**Record:**
- Full output of both dashboard curl calls
- Are the totals different? (Expected: YES)
- Which views were patched?
- Any errors?

---

### Step 3: Backend — Add `/api/accounts/me/context/` Endpoint

**Objective:** Give the frontend a single "context card" endpoint — who I am, what I can see, what my effective scope is.

**Response shape:**
```json
{
  "user": {
    "id": 7,
    "username": "facilities.officer",
    "email": "fac@carbon.local",
    "full_name": "Facilities Officer"
  },
  "roles": ["dataowners_group"],
  "is_global_admin": false,
  "perspectives": ["data_entry", "dashboards"],
  "org_units": [
    {"id": 5, "name": "Operations & Facilities", "type": "division"}
  ],
  "module_count": 3
}
```

**Add to `accounts/views.py`:**
```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from accounts.rbac_utils import (
    user_is_global_admin, get_allowed_org_unit_ids, get_allowed_module_ids, VISIBILITY_ROLES
)
from mdm.models import OrgUnit
from core.models import Module

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_context(request):
    user = request.user
    roles_qs = user.scoped_roles.filter(is_active=True).select_related('group', 'org_unit')
    role_names = list(set(r.group.name for r in roles_qs))
    is_global = user_is_global_admin(user)

    # Determine which perspectives this user can see
    perspectives = ['dashboards']
    has_data_role = any(r in role_names for r in ['dataowners_group', 'auditors_group'])
    has_admin_role = 'admins_group' in role_names
    if has_data_role or has_admin_role:
        perspectives.append('data_entry')
    if has_admin_role:
        perspectives.append('admin')

    # Org units the user can see
    if is_global:
        org_units = list(OrgUnit.objects.values('id', 'name', 'org_type')[:20])
    else:
        allowed_ids = get_allowed_org_unit_ids(user, VISIBILITY_ROLES)
        org_units = list(OrgUnit.objects.filter(id__in=allowed_ids).values('id', 'name', 'org_type'))

    module_count = Module.objects.all().count() if is_global else \
        len(get_allowed_module_ids(user, VISIBILITY_ROLES))

    return Response({
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': f"{user.first_name} {user.last_name}".strip() or user.username,
        },
        'roles': role_names,
        'is_global_admin': is_global,
        'perspectives': perspectives,
        'org_units': org_units,
        'module_count': module_count,
    })
```

**Add URL in `accounts/urls.py`:**
```python
path('me/context/', views.me_context, name='me-context'),
```

**Verify:**
```bash
FAC_TOKEN=<from step 2>
curl -s 'http://localhost:8009/carbon-api/accounts/me/context/' \
  -H "Authorization: Bearer $FAC_TOKEN" | python3 -m json.tool

GLOBAL_TOKEN=<from step 2>
curl -s 'http://localhost:8009/carbon-api/accounts/me/context/' \
  -H "Authorization: Bearer $GLOBAL_TOKEN" | python3 -m json.tool
```

**Expected:**
- Fac officer: `perspectives: ["dashboards", "data_entry"]`, `is_global_admin: false`
- Global admin: `perspectives: ["dashboards", "data_entry", "admin"]`, `is_global_admin: true`

**Commit:**
```bash
git add backend/accounts/views.py backend/accounts/urls.py
git commit -m "feat(accounts): add /me/context/ endpoint for frontend perspective resolution"
```

**Record:**
- Full curl output for both users
- Are perspectives correct for each role?

---

### Step 4: Frontend — Perspective Context in AuthContext

**Objective:** Add `currentPerspective` state to `AuthContext` so all components can read it.

**Read first:**
```bash
cat carbon-frontend/src/auth/AuthContext.jsx
```

**Add to `AuthContext.jsx`:**
```javascript
// Inside AuthContext, add:
const [currentPerspective, setCurrentPerspective] = useState(() => {
  return localStorage.getItem('carbon_perspective') || 'data_entry';
});

const setPerspective = (perspective) => {
  setCurrentPerspective(perspective);
  localStorage.setItem('carbon_perspective', perspective);
};

// Add to context value:
// currentPerspective, setPerspective, availablePerspectives (from /me/context/ response)
```

**Also add `availablePerspectives` from the `/me/context/` API call (if not already fetching that endpoint).**

**Add to the context API file (`api/api.js` or similar):**
```javascript
export const fetchMeContext = () =>
  api.get('/accounts/me/context/').then(r => r.data);
```

**Commit:**
```bash
git add carbon-frontend/src/auth/AuthContext.jsx carbon-frontend/src/api/
git commit -m "feat(frontend): add perspective state to AuthContext"
```

**Record:**
- What was already in AuthContext? (paste the key parts)
- Did you need to add `availablePerspectives` or was it already there?

---

### Step 5: Frontend — Perspective Switcher in Header

**Objective:** Add perspective tabs to the Header — visible only to users who have multiple perspectives.

**Read first:**
```bash
cat carbon-frontend/src/components/Header.jsx
```

**Target UI (simplified — adapt to the existing MUI theme in the project):**
```
┌──────────────────────────────────────────────────────────────────┐
│ 🌿 AASTMT Carbon │  [Data Entry]  [Dashboards]  [Admin ▾]        │  👤 Ahmed ▼
└──────────────────────────────────────────────────────────────────┘
```

**Implementation approach in Header.jsx:**
```jsx
import { useAuth } from '../auth/AuthContext';
import { Tabs, Tab } from '@mui/material';

// Inside Header component:
const { currentPerspective, setPerspective, availablePerspectives } = useAuth();

// Only show switcher if user has more than one perspective
const showSwitcher = availablePerspectives?.length > 1;

// Tab labels
const PERSPECTIVE_LABELS = {
  data_entry: 'Data Entry',
  dashboards: 'Dashboards',
  admin: 'Admin',
};

// Render tabs:
{showSwitcher && (
  <Tabs
    value={currentPerspective}
    onChange={(_, val) => setPerspective(val)}
    sx={{ /* match existing header style */ }}
  >
    {availablePerspectives.map(p => (
      <Tab key={p} value={p} label={PERSPECTIVE_LABELS[p]} />
    ))}
  </Tabs>
)}
```

**Commit:**
```bash
git add carbon-frontend/src/components/Header.jsx
git commit -m "feat(frontend): add perspective switcher to Header

- Tabs visible only for users with multiple perspectives
- Data Entry | Dashboards | Admin (Admin tab gated to admins_group)
- Persisted in localStorage via AuthContext"
```

**Record:**
- Before/after screenshot description (or text description of what changed)
- Is the Admin tab correctly hidden for data-only users?

---

### Step 6: Frontend — Refactor SidebarMenu by Perspective

**Objective:** The sidebar renders completely different content based on `currentPerspective`.

**Read first:**
```bash
cat carbon-frontend/src/components/SidebarMenu.jsx
```

**Refactor approach — split into perspective-driven rendering:**

```jsx
// SidebarMenu.jsx — simplified structure
export default function SidebarMenu({ collapsed }) {
  const { currentPerspective, canSchemaAdmin } = useAuth();

  if (currentPerspective === 'admin') {
    return <AdminSidebar collapsed={collapsed} />;
  }
  if (currentPerspective === 'dashboards') {
    return <DashboardSidebar collapsed={collapsed} />;
  }
  // Default: data_entry
  return <DataEntrySidebar collapsed={collapsed} />;
}
```

**`DataEntrySidebar` — lean operator view:**
```
📊 My Dashboard (→ /dashboard)
─────────
🌿 Scope 1 — Direct Emissions
   └── [Module: Fleet Fuel]
       └── Gas Bills
🔵 Scope 2 — Energy
   └── [Module: Electricity]
       └── Monthly Bills
🚛 Scope 3 — Value Chain
   (empty for this user → show empty state)
─────────
❓ Help
💬 Feedback
```
- NO Schema Manager section
- NO Admin section  
- Modules come from the server (already org-scoped via `context.modules`)

**`AdminSidebar` — organized admin view:**
```
🏛️ Organization
   └── Org Units (→ /admin/org-units)
   └── Users (→ /admin/users)
   └── Access Control (→ /admin/access)
─────────
🗄️ Schema Management
   └── Table Manager (→ /schema-admin/table-manager)
─────────
📊 Dashboards
   └── Executive Summary
   └── Analytics
   └── Targets
   └── Data Quality
   └── Reporting
─────────
⚙️ Help / Feedback
```

**`DashboardSidebar` — all 5 dashboard views:**
```
📊 Executive Summary (→ /dashboards/executive)
📈 Analytics (→ /dashboards/analytics)
🎯 Targets & Progress (→ /dashboards/targets)
✅ Data Quality (→ /dashboards/data-quality)
📄 Reporting (→ /dashboards/reporting)
─────────
❓ Help
💬 Feedback
```

**IMPORTANT:** Keep the `AdminRoute` protection on admin pages — the sidebar change is purely visual. Server-side and `AdminRoute` still enforce access.

**Commit:**
```bash
git add carbon-frontend/src/components/SidebarMenu.jsx
git commit -m "refactor(frontend): perspective-driven sidebar (data-entry / admin / dashboards)

- DataEntrySidebar: lean view with only user's scoped modules/tables
- AdminSidebar: organized sections (Org / Schema / Dashboards / Help)
- DashboardSidebar: all 5 dashboard views
- No admin UI visible in data-entry perspective
- AdminRoute protection unchanged (server still enforces)"
```

**Record:**
- Did the sidebar correctly hide admin links for the data-entry perspective?
- Did admin sidebar show organized sections?
- Any errors in the console?

---

### Step 7: Frontend — Role-Aware Landing Page

**Objective:** On login/first load, redirect users to the right place for their role.

**Current behavior:** Everyone lands at `/` → `ExecutiveSummary`.

**Target behavior:**
- Data-only users (no admin role) → redirect to their first module (`/modules/:id`) or data entry page
- Admin users → stay at `/` (Executive Summary is fine for admins)
- Users with no modules assigned → show a helpful empty state

**In `App.jsx` or `AuthContext`, add redirect logic:**
```jsx
// After login / on first load:
function RoleAwareRedirect() {
  const { user, availablePerspectives, context } = useAuth();
  
  const isAdminOnly = availablePerspectives?.includes('admin') && 
                      !availablePerspectives?.includes('data_entry');
  const isDataOnly = !availablePerspectives?.includes('admin');
  
  if (isDataOnly) {
    // Redirect to first module
    const firstModule = context?.modules?.[0];
    if (firstModule) {
      return <Navigate to={`/modules/${firstModule.id}`} replace />;
    }
    // No modules — show empty state
    return <NoModulesAssigned />;
  }
  
  // Admin or mixed: go to dashboard
  return <Navigate to="/dashboard" replace />;
}
```

**Also add a simple `NoModulesAssigned` component:**
```jsx
function NoModulesAssigned() {
  return (
    <Box sx={{ p: 4, textAlign: 'center' }}>
      <Typography variant="h6" gutterBottom>No data modules assigned</Typography>
      <Typography color="text.secondary">
        Contact your administrator to get access to data entry modules.
      </Typography>
    </Box>
  );
}
```

**Commit:**
```bash
git add carbon-frontend/src/App.jsx
git commit -m "feat(frontend): role-aware landing page redirect on login

- Data-only users → first assigned module (or NoModulesAssigned empty state)
- Admin users → Executive Summary dashboard
- NoModulesAssigned component for users with no module access"
```

**Record:**
- Did data-owner user land on their module page?
- Did admin user land on the dashboard?
- What happens for a user with no modules?

---

### Step 8: Frontend — Scope Banner in Layout

**Objective:** Show data-owners clearly which org unit scope they are operating in.

**Read first:**
```bash
cat carbon-frontend/src/components/Layout.jsx
```

**Add to Layout.jsx (inside the main content area, at the top, only for non-admin users):**
```jsx
const { user, availablePerspectives, currentPerspective } = useAuth();
const isAdmin = availablePerspectives?.includes('admin');
const userOrgUnit = user?.roles?.find(r => r.org_unit)?.org_unit_name;

// In the render, above the <Outlet />:
{!isAdmin && userOrgUnit && currentPerspective === 'data_entry' && (
  <Alert
    severity="info"
    icon={<LocationOnIcon />}
    sx={{ mb: 2, borderRadius: 1 }}
  >
    You are viewing: <strong>{userOrgUnit}</strong>
  </Alert>
)}
```

If the org unit name is not in the user roles, use the `/me/context/` response's `org_units[0].name`.

**Commit:**
```bash
git add carbon-frontend/src/components/Layout.jsx
git commit -m "feat(frontend): scope banner showing user's org unit in data-entry perspective"
```

**Record:**
- Does the banner appear for data-owner users?
- Is it correctly hidden for admin users?
- What text does it show?

---

### Step 9: Build & Integration Test

**Objective:** Verify the full flow works end-to-end.

```bash
cd /home/ahmed/aast/carbon/carbon-frontend

# 9.1 Build the frontend
npm run build

# 9.2 Check for build errors
echo $?  # Should be 0

# 9.3 Start dev server (keep running in background if needed)
npm run dev &
sleep 3

# 9.4 Check backend still boots
cd /home/ahmed/aast/carbon/backend
python manage.py check
```

**Manual test checklist (paste results):**

**Test A — Data Owner Flow:**
1. Login as `facilities.officer`
2. ✅/❌ Perspective tabs visible? (should show: Data Entry | Dashboards)
3. ✅/❌ Admin tab visible? (should NOT appear)
4. ✅/❌ Sidebar shows only their modules (no Schema Manager, no Admin section)?
5. ✅/❌ Dashboard numbers are scoped (lower than global admin's total)?
6. ✅/❌ Scope banner shows "You are viewing: Operations & Facilities"?
7. ✅/❌ Can enter data in their tables?
8. ✅/❌ Cannot navigate to `/admin/org-units` (redirect away)?

**Test B — Global Admin Flow:**
1. Login as `global_admin`
2. ✅/❌ Perspective tabs visible? (should show: Data Entry | Dashboards | Admin)
3. ✅/❌ Can switch to Admin perspective?
4. ✅/❌ Admin sidebar shows: Org / Schema / Dashboards sections?
5. ✅/❌ Dashboard numbers show full AASTMT total?
6. ✅/❌ No scope banner (admins see all)?
7. ✅/❌ Can access `/admin/org-units`, `/admin/users`, `/admin/access`?
8. ✅/❌ Can access `/schema-admin/table-manager`?

**Test C — Cross-scope protection (backend):**
```bash
# Facilities officer cannot see transport data (server enforces)
FAC_TOKEN=<token>
curl -s 'http://localhost:8009/carbon-api/dataschema/rows/?data_table=<transport_table_id>' \
  -H "Authorization: Bearer $FAC_TOKEN" | python3 -m json.tool
# Expected: empty results or 403
```

**Commit:**
```bash
git add -A
git commit -m "chore(A5): final integration test — perspectives architecture complete"
```

---

### Step 10: Final Checks

```bash
cd /home/ahmed/aast/carbon

# 10.1 Backend check
cd backend && python manage.py check

# 10.2 Frontend build
cd ../carbon-frontend && npm run build && echo "BUILD OK"

# 10.3 Git status
cd .. && git status

# 10.4 Git log
git log --oneline -15
```

**Record:**
- `manage.py check` output
- Build result
- `git status`
- Full commit list for A5

---

## 8. ACCEPTANCE CRITERIA

| # | Criterion | Pass Threshold | Status | Evidence Ref |
|---|-----------|----------------|--------|--------------|
| AC1 | Dashboard data scoping fixed | Data-owner's dashboard total ≠ global admin's total (or is a strict subset) | | Step 2 |
| AC2 | `/me/context/` endpoint works | Returns correct perspectives array per role | | Step 3 |
| AC3 | Perspective context in AuthContext | `currentPerspective` state exists, persists in localStorage | | Step 4 |
| AC4 | Perspective switcher visible for admin users | Admin tab appears when user has `admins_group` role | | Step 5 |
| AC5 | Perspective switcher hidden for data-only users | No Admin tab for users with only `dataowners_group` | | Step 5, 9 |
| AC6 | Data Entry sidebar is lean | No Schema Manager or Admin links visible in data-entry perspective | | Step 6, 9 |
| AC7 | Admin sidebar has organized sections | Org / Schema / Dashboards sections visible in admin perspective | | Step 6, 9 |
| AC8 | Role-aware landing page | Data-owner lands on their first module; admin lands on dashboard | | Step 7 |
| AC9 | Scope banner shows org unit | "You are viewing: [OrgUnit]" banner for data-owners in data-entry mode | | Step 8 |
| AC10 | Admin routes still protected | `/admin/*` and `/schema-admin/*` still redirect non-admins | | Step 9 |
| AC11 | Frontend builds clean | `npm run build` exits 0 with no errors | | Step 9 |
| AC12 | Backend boots clean | `python manage.py check` exits 0 | | Step 10 |

**Worker: fill the "Status" column with PASS/FAIL and reference the step where evidence is found.**

---

## 9. DELIVERABLE FORMAT

**File:** `TASK-RESULT-A5.md`

**Required structure:**

```markdown
# TASK-RESULT-A5.md — RUN A5: Role-Adaptive UI (Perspectives Architecture)

## Summary
[One paragraph: what was built, what changed, what was fixed]

## Critical Fix: Dashboard Data Scoping
[What was the leak? How was it fixed? Proof (curl output showing different totals)]

## Step 1: Code Review
[What did you find in the existing code?]

## Step 2: Backend — Dashboard Scoping Fix
[Commands + full output + verification curl showing different numbers]

## Step 3: Backend — /me/context/ Endpoint
[Commands + curl output for both user types]

## Step 4: Frontend — Perspective Context
[What was added to AuthContext]

## Step 5: Frontend — Perspective Switcher in Header
[What changed in Header.jsx]

## Step 6: Frontend — Sidebar Refactor
[What changed in SidebarMenu.jsx + description of each perspective's sidebar]

## Step 7: Frontend — Role-Aware Landing
[What was added to App.jsx]

## Step 8: Frontend — Scope Banner
[What was added to Layout.jsx]

## Step 9: Build & Integration Test
[Build result + manual test checklist with ✅/❌ for each item]

## Step 10: Final Checks
[manage.py check output, build result, git status]

## Acceptance Criteria Table
[Copy AC table from TASK.md, fill Status column]

## Git Commit Summary
[All commits with hashes and messages]

## Gaps / Known Issues
[List anything that was not implemented and why, or "None"]

## Definition of Done Status
[Explicit: "DoD met" or "DoD not met because..."]
```

---

## 10. DEFINITION OF DONE

- All 12 acceptance criteria filled with PASS (or documented N/A with reason)
- Dashboard data scoping fixed — verified by curl showing different numbers per role (AC1 PASS)
- `/me/context/` endpoint works for both data-owner and global admin (AC2 PASS)
- Perspective switcher works in header — Admin tab gated to `admins_group` (AC4/AC5 PASS)
- Sidebar shows correct content per perspective (AC6/AC7 PASS)
- Role-aware landing page works (AC8 PASS)
- Frontend builds clean — `npm run build` exits 0 (AC11 PASS)
- Backend boots clean — `manage.py check` exits 0 (AC12 PASS)
- `TASK-RESULT-A5.md` returned with all required sections
- **Gate:** A5 completion unblocks A6 (Deployment-readiness gate)

---

## 11. ESCALATION

**If blocked:**
1. Stop the blocked step immediately
2. Mark it `BLOCKED: <specific reason>` in the result
3. Continue with remaining independent steps
4. Summarize all blockers at the top of `TASK-RESULT-A5.md`
5. Never guess, assume, or fabricate test results

**Priority order if time-constrained:** Step 2 (data leak fix) > Step 6 (sidebar refactor) > Step 5 (perspective switcher) > Steps 7–8 (landing/banner)

**If `get_visible_module_ids` doesn't exist:** Create it in `rbac_utils.py` using the existing `get_allowed_module_ids` helper. Do NOT create a separate implementation — use what's already there.

**If `availablePerspectives` is not in AuthContext:** Fetch it from `/me/context/` on login and store in context state.

**If the build fails:** Paste the full error output. Do NOT force-push or skip build verification.

---

## 12. REFERENCE

- **Design decision:** `docs/DESIGN_UI_ARCHITECTURE_A5.md`
- **Org access model:** `docs/DESIGN_ORG_ACCESS_MODEL.md` (§4.6 = dashboard scoping, §5 = portal strategy)
- **Strategy:** `docs/STRATEGY_DATA_TRUST_PLATFORM.md`
- **Auth context:** `carbon-frontend/src/auth/AuthContext.jsx`
- **Current sidebar:** `carbon-frontend/src/components/SidebarMenu.jsx`
- **Emissions views:** `backend/emissions/views.py`
- **RBAC utils:** `backend/accounts/rbac_utils.py`

---

**END OF TASK.md — RUN A5**

**Worker (Raptor):** This is a combined backend + frontend RUN. Start with Step 2 (the data scoping fix) — that's the most important change and it's pure backend. Then work through the frontend perspectives. Read `docs/DESIGN_UI_ARCHITECTURE_A5.md` before writing any code — the architectural decision is fully documented there. Good luck.
