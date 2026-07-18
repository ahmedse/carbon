# Data Hub End-to-End Completion Plan

**Date:** 2026-07-18  
**Status:** Planning  
**Priority:** HIGH  
**Goal:** Complete Data Hub (DataSchema studio) with full user journey for data entry, table management, and quality checks

---

## Executive Summary

The Data Hub is the core data entry interface for org-scoped users. Currently it has backend functionality but incomplete frontend UX. This plan addresses:
1. **Dead route:** `/dataschema/entry` leads to 404
2. **Missing landing page:** No home for Data Hub studio
3. **Shell layout disabled:** Feature flag prevents new UI from activating
4. **Admin studio visible to all:** Non-admin users see admin icon but get redirected
5. **Incomplete navigation:** Data Hub sidebar needs module-aware navigation

---

## Current State Analysis

### ✅ What Works (Backend Complete)
- [`DataTableViewSet`](backend/dataschema/views.py:46) - Full CRUD with RBAC
- [`DataFieldViewSet`](backend/dataschema/views.py:78) - Schema field management
- [`DataRowViewSet`](backend/dataschema/views.py:100) - Data entry with org-scoping
- [`HasScopedRole`](backend/accounts/permissions.py:11) - Module auto-resolution works
- [`ReadScopedWriteAdmin`](backend/accounts/permissions.py:89) - Schema protection works
- [`TableManagerPage`](carbon-frontend/src/pages/TableManagerPage.jsx) - Admin table CRUD works
- [`ModuleLandingPage`](carbon-frontend/src/pages/ModuleLandingPage.jsx) - Shows tables per module
- [`DataEntryPage`](carbon-frontend/src/pages/DataEntryPage.jsx) - Grid-based data entry works

### ❌ What's Broken
1. **Dead Route:** [`ShellSidebar:36`](carbon-frontend/src/shell/ShellSidebar.jsx:36) → `/dataschema/entry` (missing `:moduleName/:tableId`)
2. **No Home:** Data Hub studio has no landing page when user clicks icon
3. **Shell Disabled:** [`App.jsx:93`](carbon-frontend/src/App.jsx:93) uses `VITE_USE_SHELL_LAYOUT=true` flag (not set by default)
4. **Admin Icon Leak:** [`ActivityBar`](carbon-frontend/src/shell/ActivityBar.jsx) shows admin to all users
5. **Path Mismatch:** [`useShellState.js:30`](carbon-frontend/src/shell/useShellState.js:30) default path `/dataschema/entry` is invalid

### ⚠️ What's Incomplete
- No "Module Browser" page for users with multiple modules
- No "Recent Tables" or "Favorites" UX
- No bulk data import UI (backend might support via API)
- No data quality dashboard integration in Data Hub

---

## User Journeys (Target Experience)

### Journey 1: Data-Owner (Single Module)
1. Login → auto-redirect to `/modules/{moduleId}` ([`App.jsx:74`](carbon-frontend/src/App.jsx:74))
2. See grid of tables for their module ([`ModuleLandingPage`](carbon-frontend/src/pages/ModuleLandingPage.jsx))
3. Click table → `/dataschema/entry/{moduleId}/{tableId}` (data entry grid)
4. Add/edit rows with validation
5. Upload evidence files
6. Submit for review

### Journey 2: Data-Owner (Multiple Modules)
1. Login → auto-redirect to `/dataschema` (module browser)
2. See list of assigned modules (Scope 1, Scope 2, Scope 3)
3. Click module → same as Journey 1 step 2

### Journey 3: Admin (Schema Management)
1. Login → dashboard (admin has admin perspective)
2. Click Data Hub studio icon → `/dataschema` (module browser)
3. Sidebar shows "Table Manager" option (admin-only)
4. Click Table Manager → `/schema-admin/table-manager` (full schema CRUD)

### Journey 4: Data Hub Navigation (All Users)
1. User in Data Hub studio (dataschema)
2. Sidebar shows:
   - **Data Entry** → module browser or last visited module
   - **Data Quality** → `/dashboards/data-quality`
   - **Table Manager** → admin-only, hidden for non-admins ✅ (already implemented)

---

## Architecture Decisions

### Decision 1: Data Hub Landing Page
**Problem:** `/dataschema/entry` is invalid (needs moduleId + tableId)  
**Solution:** Create `/dataschema` as Data Hub home:
- **Single module user:** Auto-redirect to `/modules/{firstModuleId}`
- **Multi-module user:** Show module browser (grid of modules)
- **Admin:** Show module browser + "Manage All Tables" CTA

**Route:**
```javascript
<Route path="/dataschema" element={<DataHubHome />} />
```

### Decision 2: Enable Shell Layout by Default
**Problem:** Shell layout only activates if `VITE_USE_SHELL_LAYOUT=true`  
**Solution:** Remove feature flag, make Shell the default layout  
**File:** [`App.jsx:93`](carbon-frontend/src/App.jsx:93)

```javascript
// BEFORE
const useShellLayout = import.meta.env.VITE_USE_SHELL_LAYOUT === 'true';

// AFTER
const useShellLayout = true; // Shell is now default
```

### Decision 3: Hide Admin Studio for Non-Admins
**Problem:** [`ActivityBar`](carbon-frontend/src/shell/ActivityBar.jsx) shows admin icon to all users  
**Solution:** Filter studios based on `availablePerspectives` from AuthContext

**Implementation:**
```javascript
// useShellState.js
import { useAuth } from '../auth/AuthContext';

export function useShellState() {
  const { availablePerspectives } = useAuth();
  
  const studios = useMemo(() => {
    let filtered = DEFAULT_STUDIOS;
    
    // Hide admin studio if user doesn't have admin perspective
    if (!availablePerspectives?.includes('admin')) {
      filtered = filtered.filter(s => s.id !== 'admin');
    }
    
    return filtered;
  }, [availablePerspectives]);
  
  // rest of state...
}
```

### Decision 4: Fix Data Entry Sidebar Link
**Problem:** Sidebar "Data Entry" → `/dataschema/entry` (404)  
**Solution:** Link to `/dataschema` (Data Hub home)

**File:** [`ShellSidebar.jsx:36`](carbon-frontend/src/shell/ShellSidebar.jsx:36)
```javascript
// BEFORE
{ label: 'Data Entry', path: '/dataschema/entry', icon: AddCircleOutlineIcon }

// AFTER
{ label: 'Data Entry', path: '/dataschema', icon: AddCircleOutlineIcon }
```

### Decision 5: Module Browser Page
**New component:** `carbon-frontend/src/pages/DataHubHome.jsx`

Features:
- Show modules grid (with scope badges)
- Search/filter modules
- Recent tables quick access
- Admin: "Manage All Tables" button → Table Manager
- Single-module users: auto-redirect to that module

---

## Implementation Plan

### Phase 1: Fix Critical Navigation Issues
**Objective:** Make Data Hub accessible without 404 errors

1. **Enable Shell Layout** ([`App.jsx`](carbon-frontend/src/App.jsx))
   - Remove `VITE_USE_SHELL_LAYOUT` feature flag
   - Make Shell default layout
   
2. **Fix Data Entry Route** ([`ShellSidebar.jsx`](carbon-frontend/src/shell/ShellSidebar.jsx))
   - Change path from `/dataschema/entry` → `/dataschema`
   
3. **Fix Studio Default Path** ([`useShellState.js`](carbon-frontend/src/shell/useShellState.js))
   - Change dataschema studio path from `/dataschema/entry` → `/dataschema`
   
4. **Add Data Hub Home Route** ([`App.jsx`](carbon-frontend/src/App.jsx))
   ```javascript
   <Route path="/dataschema" element={<DataHubHome />} />
   ```

**Acceptance Criteria:**
- ✅ Clicking "Data Entry" in sidebar loads a page (no 404)
- ✅ Clicking Data Hub studio icon loads a page (no 404)
- ✅ Shell layout is active by default

---

### Phase 2: Build Data Hub Home Page
**Objective:** Create proper landing experience for Data Hub studio

1. **Create DataHubHome Component** (`carbon-frontend/src/pages/DataHubHome.jsx`)
   - Detect single vs multi-module user
   - Show module browser for multi-module users
   - Auto-redirect single-module users to their module
   - Show admin CTA for Table Manager
   
2. **Module Browser UI**
   - Grid of module cards (similar to [`ModuleLandingPage`](carbon-frontend/src/pages/ModuleLandingPage.jsx) table grid)
   - Scope badges (Scope 1/2/3)
   - Module name, description, table count
   - Click module → `/modules/{moduleId}`
   
3. **Recent Tables Widget** (optional enhancement)
   - Store last 5 visited tables in localStorage
   - Quick access cards above module grid
   - "Continue where you left off" UX

**Acceptance Criteria:**
- ✅ Multi-module users see module browser
- ✅ Single-module users auto-redirect to their module
- ✅ Admin users see "Manage All Tables" button
- ✅ Module cards show scope, name, table count
- ✅ Clicking module card navigates to `/modules/{moduleId}`

---

### Phase 3: Role-Aware Studio Visibility
**Objective:** Hide admin studio icon for non-admin users

1. **Enhance useShellState** ([`useShellState.js`](carbon-frontend/src/shell/useShellState.js))
   - Import `useAuth` to access `availablePerspectives`
   - Filter `DEFAULT_STUDIOS` based on user's perspectives
   - Admin studio only shown if `availablePerspectives.includes('admin')`
   
2. **Update ActivityBar** (no changes needed, consumes filtered studios)

**Acceptance Criteria:**
- ✅ Admin users see admin studio icon
- ✅ Non-admin users do NOT see admin studio icon
- ✅ No 404 or "Access Denied" from trying to access hidden studio

---

### Phase 4: Enhanced Data Hub Sidebar
**Objective:** Context-aware navigation within Data Hub studio

**Current Sidebar (dataschema studio):**
```javascript
{ label: 'Data Entry', path: '/dataschema/entry', icon: AddCircleOutlineIcon },
{ label: 'Table Manager', path: '/schema-admin/table-manager', icon: TableChartIcon },
{ label: 'Data Quality', path: '/dashboards/data-quality', icon: RuleIcon },
```

**Proposed Changes:**

1. **Data Entry link** → `/dataschema` (fixed in Phase 1)

2. **Add Module-Specific Links** (when user is in a module)
   - Detect current module from URL (`/modules/:moduleId` or `/dataschema/entry/:moduleId/:tableId`)
   - Show "← Back to {ModuleName}" at top of sidebar
   - Show table list for current module (collapsible)
   
3. **Recent Tables Section** (optional)
   - Show last 3 visited tables with quick links
   - Persist in localStorage

**Implementation:**
```javascript
// ShellSidebar.jsx
const { pathname } = useLocation();
const moduleIdMatch = pathname.match(/\/(?:modules|dataschema\/entry)\/(\d+)/);
const currentModuleId = moduleIdMatch?.[1];

if (activeStudio === 'dataschema') {
  if (currentModuleId) {
    // Show module-specific navigation
    const module = context?.modules?.find(m => String(m.id) === currentModuleId);
    const tables = tablesByModule?.[currentModuleId] || [];
    
    items = [
      { label: `← ${module?.name || 'Modules'}`, path: '/dataschema', icon: ArrowBackIcon },
      ...tables.map(t => ({
        label: t.title,
        path: `/dataschema/entry/${currentModuleId}/${t.id}`,
        icon: TableChartIcon,
      })),
    ];
  } else {
    // Show top-level Data Hub navigation
    items = [
      { label: 'Data Entry', path: '/dataschema', icon: AddCircleOutlineIcon },
      { label: 'Data Quality', path: '/dashboards/data-quality', icon: RuleIcon },
    ];
  }
  
  // Admin-only: Table Manager
  if (availablePerspectives.includes('admin')) {
    items.push({ label: 'Table Manager', path: '/schema-admin/table-manager', icon: TableChartIcon });
  }
}
```

**Acceptance Criteria:**
- ✅ Top-level: Shows "Data Entry", "Data Quality"
- ✅ Module context: Shows "← Back to Modules" + table list
- ✅ Admin-only: "Table Manager" appears for admins
- ✅ Non-admin: "Table Manager" hidden (already implemented)

---

### Phase 5: Bulk Operations UI (Optional Enhancement)
**Objective:** Enable bulk data import/export for data-owners

**Backend Status:** Check if bulk upsert endpoint exists  
**Frontend:** Add "Import" button on table data page

1. **Import CSV/Excel Dialog**
   - Upload file
   - Map columns to fields
   - Preview + validation
   - Bulk upsert via API
   
2. **Export Data Button**
   - Export current table to CSV/Excel
   - Filtered data export

**Acceptance Criteria:**
- ✅ "Import Data" button on [`TableDataPage`](carbon-frontend/src/components/TableDataPage.jsx)
- ✅ Upload CSV → map columns → preview → submit
- ✅ "Export Data" button → download CSV

---

### Phase 6: Integration & Testing
**Objective:** Verify all user journeys work end-to-end

**Test Scenarios:**

1. **Data-Owner (Single Module)**
   - Login as `fac_officer` (Facilities module only)
   - Should auto-redirect to `/modules/{facilities_id}`
   - Should see table grid
   - Click table → data entry works
   - Sidebar "Data Entry" → returns to module page
   - Sidebar "Data Quality" → loads DQ dashboard

2. **Data-Owner (Multi-Module)**
   - Login as user with Facilities + Transport modules
   - Should redirect to `/dataschema` (module browser)
   - Should see both modules in grid
   - Click Facilities → see Facilities tables
   - Click Transport → see Transport tables

3. **Admin**
   - Login as `global_admin`
   - Click Data Hub studio icon → `/dataschema` (module browser)
   - Should see "Manage All Tables" button
   - Click button → `/schema-admin/table-manager`
   - Sidebar shows "Table Manager" link
   - Can create/edit tables across all modules

4. **Non-Admin UX**
   - Login as `fac_officer`
   - Admin studio icon should NOT appear in ActivityBar
   - Sidebar "Table Manager" should NOT appear
   - Direct navigation to `/admin/users` → 403 redirect

**Acceptance Criteria:**
- ✅ All 4 test scenarios pass
- ✅ No 404 errors in Data Hub navigation
- ✅ No console errors
- ✅ Role gates work (admin vs non-admin)

---

### Phase 7: Documentation & User Guide
**Objective:** Document Data Hub workflows for users and developers

1. **User Guide** (`docs/DATA_HUB_USER_GUIDE.md`)
   - How to navigate Data Hub
   - How to enter data
   - How to upload evidence
   - How to export data
   - Admin: How to manage tables/fields
   
2. **Developer Guide** (update `docs/DESIGN_UI_ARCHITECTURE_A5.md`)
   - Data Hub architecture
   - Shell layout overview
   - Sidebar navigation logic
   - Role-based studio filtering
   
3. **Update RUN_LOG** ([`docs/RUN_LOG.md`](docs/RUN_LOG.md))
   - Add RUN A6: Data Hub Completion

**Acceptance Criteria:**
- ✅ User guide created with screenshots
- ✅ Developer guide updated
- ✅ RUN_LOG updated

---

## Files to Create

### New Files
1. `carbon-frontend/src/pages/DataHubHome.jsx` - Data Hub landing page
2. `docs/DATA_HUB_USER_GUIDE.md` - User documentation
3. `plans/DATA_HUB_COMPLETION_PLAN.md` - This file

### Files to Modify
1. [`carbon-frontend/src/App.jsx`](carbon-frontend/src/App.jsx) - Remove feature flag, add route
2. [`carbon-frontend/src/shell/useShellState.js`](carbon-frontend/src/shell/useShellState.js) - Filter studios by role, fix path
3. [`carbon-frontend/src/shell/ShellSidebar.jsx`](carbon-frontend/src/shell/ShellSidebar.jsx) - Fix link, enhance with module context
4. [`docs/RUN_LOG.md`](docs/RUN_LOG.md) - Add RUN A6

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Users confused by module browser | Medium | Single-module users auto-redirect, clear UX |
| Breaking existing data entry workflows | High | Keep all existing routes, only add `/dataschema` |
| Performance: loading all modules on home | Low | Modules already cached in AuthContext |
| Admin studio hiding breaks links | Low | AdminRoute already handles 403, just cleaner UX |

---

## Success Metrics

1. **Zero 404 errors** in Data Hub navigation
2. **Admin studio hidden** for non-admin users (UX improvement)
3. **Data Hub home loads** in < 500ms
4. **All user journeys** (4 scenarios) pass manual testing
5. **Documentation complete** (user guide + developer guide)

---

## Next Steps

1. Review this plan with stakeholders
2. Create TODO list with sequenced tasks
3. Switch to Code mode for implementation
4. Execute Phase 1 → Phase 7 sequentially
5. Create TASK-RESULT-A6.md upon completion

---

## Appendix: Current Route Map

### Working Routes
- `/login` → Login page ✅
- `/dashboard` → Executive dashboard ✅
- `/dashboards/*` → Dashboard suite ✅
- `/emissions/*` → Emissions calculator ✅
- `/modules/:moduleId` → Module landing (table grid) ✅
- `/dataschema/entry/:moduleId/:tableId` → Data entry ✅
- `/schema-admin/table-manager` → Admin table CRUD ✅
- `/admin/*` → Admin pages (role-gated) ✅

### Broken Routes
- `/dataschema/entry` → 404 ❌ (missing moduleId/tableId)
- `/dataschema` → 404 ❌ (no route defined)

### Proposed Routes
- `/dataschema` → Data Hub home (module browser or redirect) 🆕
- Keep all existing routes unchanged ✅

---

**Status:** Ready for implementation  
**Next:** Create sequenced TODO list and switch to Code mode