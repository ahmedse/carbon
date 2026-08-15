# Platform RBAC + Admin Architecture — Holistic Rethink

**Date:** 2026-07-24  
**Context:** User feedback: "with RBAC, let's do user/roles/privileges/assignments and accounts mgt too. i think this should be under admin, right? rethink deep"  
**Status:** Architectural planning

---

## Core Insight: Admin is Platform-Level, Not App-Level

**Current State Problem:**
- Admin pages (`/admin/users`, `/admin/access`, `/admin/org-units`) live in **platform routes**, not in any app
- Admin studio exists in activity bar as a **platform studio** (alongside home, help, settings)
- BUT: Access Control is the **foundation** for all RBAC across **all apps**
- **Contradiction:** Carbon manifest declares `role: 'carbon:admin'` but there's no Carbon-specific admin interface—only platform-wide admin

**The Fundamental Question:**
> Is "Admin" a platform studio (manages users/roles/org units for ALL apps), or is it per-app (Carbon has its own admin, Catalog has its own admin)?

**Answer (following Platform App Model):**
> **Admin is Layer 2 (Platform Service)**—it's the control plane for RBAC, users, and org units that ALL apps consume.

---

## The Current Architecture (What Exists)

### Frontend: Admin as Platform Studio

**File:** `carbon-frontend/src/shell/useShellState.js` (lines 18-25)

```javascript
const PLATFORM_STUDIOS = [
  { id: 'home',     label: 'Dashboard',      icon: DashboardIcon, path: '/dashboard' },
  { id: 'catalog',  label: 'Catalog',        icon: LayersIcon,    path: '/catalog' },
  { id: 'admin',    label: 'Administration', icon: SecurityIcon,  path: '/admin' },
  { id: 'settings', label: 'Settings',       icon: SettingsIcon,  path: '/settings' },
  { id: 'help',     label: 'Help',           icon: HelpIcon,      path: '/help' },
];
```

**Current Admin Studio Pages:**

1. **Users Page** ([`UsersPage.jsx`](carbon-frontend/src/pages/admin/UsersPage.jsx))
   - CRUD for user accounts (username, email, password, is_active)
   - Protected by `<AdminRoute>` (requires admin permission)
   - Backend: `UserViewSet` in `backend/accounts/views.py`

2. **Access Control Page** ([`AccessControlPage.jsx`](carbon-frontend/src/pages/admin/AccessControlPage.jsx))
   - Assign `ScopedRole` (user → group/role → org unit)
   - Shows all role assignments across system
   - Backend: `ScopedRoleViewSet` in `backend/accounts/views.py`

3. **Org Units Page** ([`OrgUnitsPage.jsx`](carbon-frontend/src/pages/admin/OrgUnitsPage.jsx))
   - Manage organizational hierarchy (create, edit, delete org units)
   - Backend: `OrgUnitViewSet` in `backend/mdm/views.py`

4. **Governance Policies Page** ([`GovernancePolicyPage.jsx`](carbon-frontend/src/pages/admin/GovernancePolicyPage.jsx))
   - Manage platform-wide governance policies (redirects to `/catalog/policies`)

**Routes:** All under `/admin/*` namespace

```javascript
<Route path="/admin/users" element={<AdminRoute><UsersPage /></AdminRoute>} />
<Route path="/admin/access" element={<AdminRoute><AccessControlPage /></AdminRoute>} />
<Route path="/admin/org-units" element={<AdminRoute><OrgUnitsPage /></AdminRoute>} />
<Route path="/admin/org-units/:orgUnitId" element={<AdminRoute><OrgUnitDetailPage /></AdminRoute>} />
```

### Backend: Accounts App (Platform RBAC Core)

**File:** `backend/accounts/views.py`

**ViewSets:**

1. **`UserViewSet`** (lines 133-140)
   - CRUD for User model
   - Permission: `HasScopedRole` with `required_role = "admin"`
   - Endpoint: `/api/v1/accounts/users/`

2. **`GroupViewSet`** (lines 142-149)
   - Read-only list of Django Groups (roles)
   - Permission: `HasScopedRole` with `required_role = "admin"`
   - Endpoint: `/api/v1/accounts/groups/`

3. **`ScopedRoleViewSet`** (lines 151-212)
   - CRUD for ScopedRole assignments
   - Permission: `CanManageScopedRoles` (superuser or org-scoped steward)
   - Endpoint: `/api/v1/accounts/scoped-roles/`
   - **Anti-escalation guard:** Org-scoped admins can only assign roles within their org subtree

4. **`RoleAssignmentAuditLogViewSet`** (lines 213-220)
   - Read-only audit trail of role changes
   - Endpoint: `/api/v1/accounts/role-audit/`

**Key Model:** `ScopedRole`
```python
class ScopedRole(models.Model):
    user = ForeignKey(User)
    group = ForeignKey(Group)          # Role name (e.g., 'admin', 'data_owners_group')
    org_unit = ForeignKey(OrgUnit)      # Scope (null = global)
    module = ForeignKey(Module)         # Optional module-specific scope
    is_active = BooleanField()
```

**How Apps Consume RBAC:**
- Apps declare roles in their manifest (e.g., `carbon:data_owner`, `carbon:analyst`)
- Backend uses `get_visible_org_units(user)` utility to scope data queries
- Frontend uses `availablePerspectives` (from `/accounts/me/context/`) to filter navigation

---

## The Problem: Confusion Between Platform Admin and App Admin

**Scenario 1: Carbon Admin**
- Carbon manifest declares `role: 'carbon:admin'` for Emission Factors and Reporting Periods pages
- BUT there's no "Carbon Admin Settings" page in the Carbon app itself
- Carbon admins manage **emission factors** and **reporting periods** (domain-specific config)
- They do NOT manage users or role assignments (that's platform-wide)

**Scenario 2: Platform Admin**
- Platform admin manages users, roles, org units (cross-app concerns)
- Should have visibility into ALL apps' roles (Carbon roles, Catalog roles, future Research roles)
- Currently lives in `/admin/*` studio

**The Confusion:**
- Is `carbon:admin` the same as platform `admin`?
- Should Carbon have its own "Admin" section separate from platform Admin?
- Should platform Admin show app-specific role management (e.g., "Assign Carbon Analyst role")?

---

## The Correct Architecture (Aligned with Platform App Model)

### Principle: Separation of Concerns

**Platform Admin (Layer 2 — Platform Service):**
- **Purpose:** Manage the platform RBAC system itself (users, groups, org units, global role assignments)
- **Scope:** Cross-app, system-wide
- **Users:** Platform administrators (IT staff, superusers)
- **Location:** `/admin/*` studio in activity bar
- **Pages:**
  1. Users — CRUD user accounts
  2. Groups/Roles — Define role names (admin, data_owners_group, analysts_group, etc.)
  3. Org Units — Manage organizational hierarchy
  4. Access Control — Assign users to roles + org units (with anti-escalation guards)
  5. Audit Log — View role assignment history

**App Admin (Layer 3 — App-Specific Configuration):**
- **Purpose:** Manage app-specific configuration and reference data
- **Scope:** Single app (e.g., Carbon)
- **Users:** App admins (Carbon admin, Catalog admin)
- **Location:** Within each app's navigation (e.g., Carbon sidebar → "Administration" group)
- **Carbon Example:**
  - Emission Factors — Reference data for calculations
  - Reporting Periods — Workflow and timeline management
  - Calculation Rules — Business logic configuration
  - **NOT user/role management** (that's platform-level)

---

## The Solution: Two-Tier Admin Model

### Tier 1: Platform Admin Studio (System-Wide RBAC)

**Activity Bar Studio:**
- ID: `admin`
- Label: "Administration"
- Icon: `SecurityIcon`
- Path: `/admin`
- **Role Required:** Platform `admin` (global superuser or steward)

**Sidebar Navigation:**
```javascript
{
  section: 'Platform Administration',
  items: [
    { label: 'Users',          path: '/admin/users',       icon: PeopleIcon,         role: 'admin' },
    { label: 'Groups & Roles', path: '/admin/groups',      icon: GroupIcon,          role: 'admin' },
    { label: 'Org Units',      path: '/admin/org-units',   icon: AccountTreeIcon,    role: 'admin' },
    { label: 'Access Control', path: '/admin/access',      icon: SecurityIcon,       role: 'admin' },
    { label: 'Audit Log',      path: '/admin/audit',       icon: HistoryIcon,        role: 'admin' },
    { type: 'divider' },
    { type: 'group', label: 'App Management' },
    { label: 'Registered Apps', path: '/admin/apps',       icon: AppsIcon,           role: 'admin' },
    { label: 'Role Registry',   path: '/admin/role-matrix', icon: GridViewIcon,     role: 'admin' },
  ]
}
```

**New Pages Needed:**
1. **Groups & Roles Page** — Manage Django Groups (create `carbon_admins_group`, `catalog_stewards_group`, etc.)
2. **Role Registry Page** — Show all roles from all app manifests in a matrix view
3. **Registered Apps Page** — Show all apps from APP_REGISTRY with their manifests

### Tier 2: App-Specific Admin (Domain Configuration)

**Carbon App Example:**

**Manifest Navigation:**
```javascript
{
  section: 'Carbon Footprint',
  items: [
    { label: 'Dashboard',          path: '/carbon/dashboard',          role: '*' },
    { type: 'divider' },
    { type: 'group', label: 'Data Owner' },
    { label: 'My Portal',          path: '/carbon/owner/portal',       role: 'carbon:data_owner' },
    // ...
    { type: 'divider' },
    { type: 'group', label: 'Administration' },
    { label: 'Emission Factors',   path: '/carbon/admin/factors',      role: 'carbon:admin' },
    { label: 'Reporting Periods',  path: '/carbon/reporting/periods',  role: 'carbon:admin' },
    { label: 'Calculation Rules',  path: '/carbon/admin/rules',        role: 'carbon:admin' },
    // NO user management here!
  ]
}
```

**Clarification:** `carbon:admin` role means "can configure Carbon app settings" NOT "can assign users to roles"

---

## RBAC Flow: How It All Connects

### 1. Platform Admin Creates User
- Go to Platform Admin Studio → Users
- Create user account (username, email, password)
- User exists but has NO roles yet (cannot access any app)

### 2. Platform Admin Assigns Role
- Go to Platform Admin Studio → Access Control
- Select user, select group (e.g., `carbon_data_owners_group`), select org unit (e.g., "Faculty of Engineering")
- Backend creates `ScopedRole` entry
- **Effect:** User can now access Carbon app with `carbon:data_owner` perspective

### 3. Frontend Perspective Resolution
- User logs in → AuthContext calls `/accounts/me/context/`
- Backend returns: `{ perspectives: ['data-owner'], org_units: [3, 5, 7] }`
- Frontend sets `availablePerspectives = ['data-owner']`
- ShellSidebar filters Carbon navigation:
  - Shows: Dashboard, My Portal, My Dashboard, My Assets, Data Entry Hub
  - Hides: Generate Report, Emission Factors, Reporting Periods (analyst/admin only)

### 4. App Admin Configures Domain
- A different user with `carbon:admin` role logs in
- They see Administration group in Carbon sidebar
- They manage Emission Factors, Reporting Periods (app config)
- They do NOT see Platform Admin studio in activity bar (not a platform admin)

### 5. Platform Admin Views All Roles
- Platform admin can see role matrix:
  ```
  User       | Role              | Scope                  | Status
  -----------|-------------------|------------------------|--------
  ahmed      | admin (global)    | (all org units)        | active
  john.doe   | carbon:data_owner | Engineering            | active
  jane.smith | carbon:analyst    | (global)               | active
  bob.jones  | catalog:steward   | Academic Affairs       | active
  ```

---

## Implementation Plan

### Phase 1: Clarify Existing Admin Studio (Platform-Level)

**Goal:** Make it crystal clear that `/admin/*` is platform RBAC management, NOT app configuration

**Tasks:**

1. **Rename Admin Studio Label**
   - Change from "Administration" to "**Platform Admin**" or "**System Admin**"
   - Makes scope obvious

2. **Add Groups & Roles Page**
   - List all Django Groups
   - Show which groups map to which app roles (from manifests)
   - Allow creating new groups for future apps

3. **Add Role Registry Page**
   - Read all app manifests from `APP_REGISTRY`
   - Display role matrix showing all declared roles:
     ```
     App     | Role Key          | Label        | Scoped | Description
     --------|-------------------|--------------|--------|------------------
     carbon  | carbon:data_owner | Data Owner   | Yes    | CRUD on assigned org data
     carbon  | carbon:analyst    | Analyst      | No     | Read-only, cross-org visibility
     carbon  | carbon:admin      | Carbon Admin | No     | Manage factors, rules, periods
     catalog | catalog:steward   | Steward      | Yes    | Curate assets in assigned domain
     ```

4. **Update Access Control Page**
   - Show app context when assigning roles
   - E.g., "Assign **Carbon Data Owner** role to user John on org unit **Engineering**"

### Phase 2: Document App Admin vs Platform Admin

**Goal:** Clear guidelines for app developers on what belongs where

**Document:** `docs/RBAC_APP_ADMIN_GUIDELINES.md`

**Rules:**

| Concern | Where It Lives | Who Manages It |
|---------|----------------|----------------|
| User accounts (create/delete users) | Platform Admin | Platform admins |
| Role assignments (who has what role) | Platform Admin | Platform admins + org stewards |
| Org unit hierarchy | Platform Admin | Platform admins |
| App-specific reference data | App Admin (in app sidebar) | App admins |
| App-specific workflows | App Admin | App admins |
| Cross-app concerns (audit, governance) | Platform Services (Catalog) | Platform admins |

### Phase 3: Update Carbon Manifest Roles

**Goal:** Align Carbon manifest with this two-tier model

**Changes:**

1. **Keep Carbon roles focused on app functions:**
   - `carbon:data_owner` — Can submit data for assigned org units
   - `carbon:analyst` — Can generate reports, view analytics (read-only, cross-org)
   - `carbon:admin` — Can configure emission factors, reporting periods, calculation rules

2. **Remove any confusion with platform admin:**
   - Carbon admins do NOT manage users
   - Carbon admins do NOT assign roles
   - Carbon admins configure **domain-specific settings**

### Phase 4: Fix Role Provisioning (Backend)

**Goal:** Ensure `/accounts/me/context/` returns user's app roles correctly

**Backend Changes:**

Update `/accounts/me/context/` endpoint to map ScopedRole groups to app perspectives:

```python
@api_view(['GET'])
def user_context(request):
    user = request.user
    scoped_roles = ScopedRole.objects.filter(user=user, is_active=True)
    
    perspectives = []
    for role in scoped_roles:
        group_name = role.group.name
        # Map Django group names to app perspectives
        if 'admin' in group_name.lower():
            perspectives.append('admin')
        if 'data_owner' in group_name or 'dataowner' in group_name:
            perspectives.append('data-owner')
        if 'analyst' in group_name:
            perspectives.append('analyst')
        if 'steward' in group_name:
            perspectives.append('steward')
    
    org_units = get_visible_org_units(user)
    
    return Response({
        'perspectives': list(set(perspectives)),
        'org_units': [u.id for u in org_units],
        'scoped_roles': [
            {'role': r.group.name, 'org_unit': r.org_unit.name if r.org_unit else 'Global'}
            for r in scoped_roles
        ]
    })
```

### Phase 5: Fix Frontend Role Filtering

**Goal:** Make ShellSidebar role filtering work with both platform and app roles

**Changes:**

1. **Update ShellSidebar.jsx** (covered in RBAC-HARDENING-PLAN.md)
2. **Test with multiple user types:**
   - Platform admin → sees Platform Admin studio + all app items
   - Carbon admin → sees Carbon Administration group, NOT Platform Admin studio
   - Data owner → sees Carbon Data Owner group, NOT admin sections

---

## Decision Matrix: What Goes Where?

| Feature | Platform Admin Studio | Carbon App Admin Section | Reasoning |
|---------|----------------------|--------------------------|-----------|
| Create user account | ✅ YES | ❌ NO | Cross-app concern |
| Assign user to Carbon data owner role | ✅ YES | ❌ NO | Role assignment is platform RBAC |
| Manage org unit hierarchy | ✅ YES | ❌ NO | Org units used by ALL apps |
| Configure emission factors | ❌ NO | ✅ YES | Carbon-specific reference data |
| Configure reporting periods | ❌ NO | ✅ YES | Carbon-specific workflow config |
| View role assignment audit log | ✅ YES | ❌ NO | Cross-app security concern |
| Create calculation rules | ❌ NO | ✅ YES | Carbon-specific business logic |
| Manage data product lineage | ❌ NO | ✅ YES (Catalog) | Catalog-specific feature |
| Manage DQ rule templates | ❌ NO | ✅ YES (Catalog) | Catalog-specific feature |

---

## Success Criteria

✅ Clear mental model: "Platform Admin = RBAC control plane; App Admin = domain configuration"  
✅ Platform Admin studio shows cross-app user/role/org management  
✅ Carbon app shows domain-specific admin pages (factors, periods, rules)  
✅ No overlap: user management never appears in app sidebars  
✅ Role provisioning works: users with `carbon:data_owner` role see correct Carbon navigation  
✅ Documentation exists: guidelines for future app developers  
✅ Role Registry page shows all app roles from manifests  

---

## Files to Create/Modify

**New Pages:**
1. `carbon-frontend/src/pages/admin/GroupsPage.jsx` — Manage Django Groups
2. `carbon-frontend/src/pages/admin/RoleRegistryPage.jsx` — Show app role matrix
3. `carbon-frontend/src/pages/admin/RegisteredAppsPage.jsx` — Show APP_REGISTRY

**Modify:**
1. `carbon-frontend/src/shell/useShellState.js` — Update Admin studio label to "Platform Admin"
2. `carbon-frontend/src/shell/ShellSidebar.jsx` — Add admin sidebar items (Groups, Role Registry, etc.)
3. `carbon-frontend/src/App.jsx` — Add routes for new admin pages
4. `backend/accounts/views.py` — Fix `/accounts/me/context/` role mapping
5. `docs/RBAC_APP_ADMIN_GUIDELINES.md` — New documentation

**Reference:**
- [`plans/RBAC-HARDENING-PLAN.md`](plans/RBAC-HARDENING-PLAN.md) — Frontend role filtering fixes
- [`docs/PLATFORM_APP_MODEL.md`](docs/PLATFORM_APP_MODEL.md) — Layer separation principles

---

## Next Steps

1. **Review this architecture** with user for approval
2. **Phase 1:** Enhance Platform Admin studio (Groups, Role Registry pages)
3. **Phase 2:** Document guidelines
4. **Phase 3:** Fix role provisioning backend
5. **Phase 4:** Implement frontend role filtering (from RBAC-HARDENING-PLAN.md)
6. **Phase 5:** Test with multiple user personas (platform admin, app admin, data owner, analyst)
