# TASK.md — RUN A6: Data Hub End-to-End Completion

## MASTER CONTEXT

**RUN ID:** A6  
**RUN Type:** Frontend + UX  
**Dependencies:** A0 ✅ → A1 ✅ → A2 ✅ → A3 ✅ → A4 ✅ → A5 ✅ → **A6** (this)  
**Status:** ACTIVE  
**Worker:** Raptor (Code Mode)  
**Plan:** [`plans/DATA_HUB_COMPLETION_PLAN.md`](plans/DATA_HUB_COMPLETION_PLAN.md)

---

## 1. HEADER

**Title:** Data Hub End-to-End Completion  
**Goal:** Fix Data Hub navigation, create complete user journey for data entry  
**Priority:** HIGH  
**Estimated Complexity:** Medium-High (7 phases, multiple files)

---

## 2. OBJECTIVE

Complete the Data Hub (DataSchema studio) with:
1. Working navigation (no 404 errors)
2. Module browser landing page
3. Role-based studio visibility
4. Context-aware sidebar navigation
5. Full user journey for data-owners and admins

**Current Pain Points:**
- `/dataschema/entry` leads to 404 (dead route in sidebar)
- Shell layout disabled by feature flag
- Admin studio icon visible to non-admins (poor UX)
- No landing page for Data Hub studio
- Module-scoped users need module picker

**Success Criteria:**
- Zero 404 errors in Data Hub navigation
- Shell layout enabled by default
- Admin studio hidden for non-admin users
- Module browser works for multi-module users
- All user journeys (4 scenarios) pass testing

---

## 3. SCOPE — IN

**Files to Create:**
1. `carbon-frontend/src/pages/DataHubHome.jsx` — Module browser landing page

**Files to Modify:**
1. `carbon-frontend/src/App.jsx` — Remove feature flag, add `/dataschema` route
2. `carbon-frontend/src/shell/useShellState.js` — Filter studios by role, fix dataschema path
3. `carbon-frontend/src/shell/ShellSidebar.jsx` — Fix Data Entry link, add module context
4. `docs/RUN_LOG.md` — Document RUN A6 completion

**Backend:** No changes (backend is complete)

---

## 4. SCOPE — OUT (DO NOT TOUCH)

- ❌ Backend API changes (all endpoints exist and work)
- ❌ Permissions/RBAC (already complete from A2/A3)
- ❌ Table/field CRUD (already works in TableManagerPage)
- ❌ Data entry grid (already works in TableDataPage)
- ❌ Bulk import backend (may do frontend UI, but backend out of scope)
- ❌ Dashboard scoping (already fixed in A5)
- ❌ Other studios (Emissions, Admin, etc. — out of scope)

---

## 5. PRECONDITIONS / SETUP

**Required State:**
- ✅ A5 complete (perspective architecture implemented)
- ✅ Backend scoping works (verified in A5)
- ✅ AuthContext has `availablePerspectives`, `context.modules`, `tablesByModule`
- ✅ ModuleLandingPage works (shows tables for a module)
- ✅ TableManagerPage works (admin table CRUD)
- ✅ DataEntryPage works (data entry grid)

**Development Environment:**
```bash
# Verify backend running
curl http://localhost:8009/carbon-api/health/
# Expected: {"status":"ok"}

# Verify frontend builds
cd carbon-frontend && npm run build
# Expected: Build success

# Verify you're on feature branch
git branch --show-current
# Expected: feature/ai-copilot-mvp or similar
```

---

## 6. IMPLEMENTATION STEPS

### Step 1: Read Current Code (Required First)

**Purpose:** Understand current state before making changes

```bash
# 1.1 Read App.jsx to see current routes and feature flag
cat carbon-frontend/src/App.jsx | grep -A 5 "useShellLayout"
cat carbon-frontend/src/App.jsx | grep -A 20 "Route path="

# 1.2 Read useShellState.js to see studio definitions
cat carbon-frontend/src/shell/useShellState.js | grep -A 20 "DEFAULT_STUDIOS"

# 1.3 Read ShellSidebar.jsx to see current sidebar items
cat carbon-frontend/src/shell/ShellSidebar.jsx | grep -A 30 "getSidebarItems"

# 1.4 Read ModuleLandingPage.jsx to understand module landing UX
head -60 carbon-frontend/src/pages/ModuleLandingPage.jsx
```

**Checkpoint:** Confirm you understand:
- Where feature flag check is ([`App.jsx:93`](carbon-frontend/src/App.jsx:93))
- How studios are defined ([`useShellState.js:13`](carbon-frontend/src/shell/useShellState.js:13))
- Current sidebar items per studio ([`ShellSidebar.jsx:19`](carbon-frontend/src/shell/ShellSidebar.jsx:19))
- How ModuleLandingPage shows table grid

---

### Step 2: Enable Shell Layout by Default

**Objective:** Make Shell the default layout (remove feature flag)

**File:** `carbon-frontend/src/App.jsx`

**Change 1: Remove feature flag check**
```javascript
// BEFORE (around line 93)
const useShellLayout = import.meta.env.VITE_USE_SHELL_LAYOUT === 'true';
const RootLayout = useShellLayout ? Shell : Layout;

// AFTER
const useShellLayout = true; // Shell is now the default
const RootLayout = useShellLayout ? Shell : Layout;

// OR simplify to:
const RootLayout = Shell; // Shell is now the only layout
```

**Rationale:** The Shell layout is now stable (A5 completed). No need for feature flag.

**Test:**
```bash
cd carbon-frontend
npm run dev
# Navigate to http://localhost:5173
# Expected: Shell layout (ActivityBar on left, HeaderNew with perspective tabs)
```

**Checkpoint:** ✅ Shell layout renders without setting `VITE_USE_SHELL_LAYOUT=true`

---

### Step 3: Fix Studio Default Path

**Objective:** Change dataschema studio default path from invalid `/dataschema/entry` to `/dataschema`

**File:** `carbon-frontend/src/shell/useShellState.js`

**Change: Update dataschema studio path**
```javascript
// BEFORE (around line 27)
{ 
  id: 'dataschema', 
  label: 'Data Hub', 
  icon: StorageIcon, 
  path: '/dataschema/entry'  // ❌ Invalid (missing moduleId/tableId)
},

// AFTER
{ 
  id: 'dataschema', 
  label: 'Data Hub', 
  icon: StorageIcon, 
  path: '/dataschema'  // ✅ Valid (will create this route)
},
```

**Rationale:** `/dataschema/entry` requires `:moduleId/:tableId` params. The studio icon should navigate to a landing page, not directly to data entry.

**Checkpoint:** ✅ Studio definition updated (don't test yet, route doesn't exist)

---

### Step 4: Hide Admin Studio for Non-Admins

**Objective:** Filter studios based on user's available perspectives

**File:** `carbon-frontend/src/shell/useShellState.js`

**Change: Filter studios by role**
```javascript
// ADD IMPORT at top
import { useAuth } from '../auth/AuthContext';

// MODIFY useShellState function (around line 71)
export function useShellState() {
  const { availablePerspectives } = useAuth(); // ADD THIS
  
  // CHANGE: Filter studios based on user perspective
  const studios = useMemo(() => {
    let filtered = DEFAULT_STUDIOS;
    
    // Hide admin studio if user doesn't have admin perspective
    if (!availablePerspectives?.includes('admin')) {
      filtered = filtered.filter(s => s.id !== 'admin');
    }
    
    return filtered;
  }, [availablePerspectives]); // CHANGE from useState to useMemo
  
  const [activeStudio, setActiveStudio] = useState('home');
  // ... rest of state unchanged
```

**Rationale:** Non-admin users clicking admin icon get redirected with "Access Denied". Better UX: don't show the icon at all.

**Test After Frontend Restart:**
1. Login as `fac_officer` (non-admin)
2. Check ActivityBar — admin icon should NOT appear
3. Login as `global_admin` (admin)
4. Check ActivityBar — admin icon SHOULD appear

**Checkpoint:** ✅ Admin studio conditionally rendered

---

### Step 5: Fix Data Entry Sidebar Link

**Objective:** Change "Data Entry" link from `/dataschema/entry` to `/dataschema`

**File:** `carbon-frontend/src/shell/ShellSidebar.jsx`

**Change: Update dataschema sidebar items**
```javascript
// FIND (around line 34)
case 'dataschema':
  return [
    { label: 'Data Entry', path: '/dataschema/entry', icon: AddCircleOutlineIcon },
    { label: 'Table Manager', path: '/schema-admin/table-manager', icon: TableChartIcon },
    { label: 'Data Quality', path: '/dashboards/data-quality', icon: RuleIcon },
  ];

// REPLACE WITH
case 'dataschema':
  return [
    { label: 'Data Entry', path: '/dataschema', icon: AddCircleOutlineIcon },
    { label: 'Table Manager', path: '/schema-admin/table-manager', icon: TableChartIcon },
    { label: 'Data Quality', path: '/dashboards/data-quality', icon: RuleIcon },
  ];
```

**Rationale:** Same reason as Step 3 — `/dataschema/entry` is invalid.

**Checkpoint:** ✅ Sidebar link updated (don't test yet, route doesn't exist)

---

### Step 6: Create Data Hub Home Page

**Objective:** Build module browser landing page with auto-redirect logic

**File:** `carbon-frontend/src/pages/DataHubHome.jsx` (NEW FILE)

**Implementation:**
```javascript
// File: carbon-frontend/src/pages/DataHubHome.jsx
import React, { useEffect } from 'react';
import { Box, Typography, Card, CardContent, Grid, Button, Chip } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import StorageIcon from '@mui/icons-material/Storage';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';

const SCOPE_COLORS = {
  1: { bg: '#e8f5e9', color: '#2e7d32', label: 'Scope 1' },
  2: { bg: '#e3f2fd', color: '#1565c0', label: 'Scope 2' },
  3: { bg: '#fff3e0', color: '#e65100', label: 'Scope 3' },
};

export default function DataHubHome() {
  const navigate = useNavigate();
  const { context, availablePerspectives, tablesByModule } = useAuth();
  
  const modules = context?.modules || [];
  const isAdmin = availablePerspectives?.includes('admin');
  
  // Auto-redirect: single-module users go straight to their module
  useEffect(() => {
    if (modules.length === 1 && !isAdmin) {
      navigate(`/modules/${modules[0].id}`, { replace: true });
    }
  }, [modules, isAdmin, navigate]);
  
  // Don't render module browser if auto-redirecting
  if (modules.length === 1 && !isAdmin) {
    return (
      <Box p={3} textAlign="center">
        <Typography>Loading your module...</Typography>
      </Box>
    );
  }
  
  return (
    <Box p={3}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={3}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Data Hub
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Select a module to enter or view data
          </Typography>
        </Box>
        
        {isAdmin && (
          <Button
            variant="contained"
            startIcon={<AdminPanelSettingsIcon />}
            onClick={() => navigate('/schema-admin/table-manager')}
          >
            Manage All Tables
          </Button>
        )}
      </Box>
      
      {modules.length === 0 && (
        <Box textAlign="center" py={8}>
          <StorageIcon sx={{ fontSize: 80, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            No Data Modules Assigned
          </Typography>
          <Typography variant="body2" color="text.disabled" mt={1}>
            Contact your administrator to get access to data entry modules.
          </Typography>
        </Box>
      )}
      
      <Grid container spacing={2}>
        {modules.map(module => {
          const scope = module.scope || 1;
          const scopeStyle = SCOPE_COLORS[scope] || SCOPE_COLORS[1];
          const tableCount = (tablesByModule?.[String(module.id)] || []).length;
          
          return (
            <Grid item xs={12} sm={6} md={4} key={module.id}>
              <Card
                variant="outlined"
                sx={{
                  cursor: 'pointer',
                  height: '100%',
                  transition: 'all 0.2s',
                  '&:hover': {
                    boxShadow: 3,
                    borderColor: 'primary.main',
                    transform: 'translateY(-2px)',
                  },
                }}
                onClick={() => navigate(`/modules/${module.id}`)}
              >
                <CardContent>
                  <Box display="flex" alignItems="center" gap={1} mb={2}>
                    <StorageIcon color="primary" />
                    <Typography variant="h6" fontWeight={600}>
                      {module.name}
                    </Typography>
                  </Box>
                  
                  <Typography variant="body2" color="text.secondary" mb={2} minHeight={40}>
                    {module.description || 'No description'}
                  </Typography>
                  
                  <Box display="flex" alignItems="center" gap={1}>
                    <Chip
                      label={scopeStyle.label}
                      size="small"
                      sx={{
                        bgcolor: scopeStyle.bg,
                        color: scopeStyle.color,
                        fontWeight: 600,
                      }}
                    />
                    <Typography variant="caption" color="text.secondary">
                      {tableCount} {tableCount === 1 ? 'table' : 'tables'}
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
}
```

**Rationale:**
- Multi-module users see grid of modules
- Single-module users auto-redirect to their module
- Admin users see "Manage All Tables" button
- Shows table count per module
- Scope badges for visual hierarchy
- Empty state for users with no modules

**Checkpoint:** ✅ DataHubHome.jsx created

---

### Step 7: Add Data Hub Home Route

**Objective:** Wire up `/dataschema` route to render DataHubHome

**File:** `carbon-frontend/src/App.jsx`

**Change: Add route**
```javascript
// FIND the imports section (around line 1-23)
import DataEntryPage from "./pages/DataEntryPage";
// ADD AFTER DataEntryPage import:
import DataHubHome from "./pages/DataHubHome";

// FIND the routes section (around line 100-165)
// ADD AFTER the dashboards routes (around line 115):
                
                {/* Data Hub */}
                <Route path="/dataschema" element={<DataHubHome />} />
                
                {/* Emissions Calculator Routes */}
                <Route path="/emissions" element={<EmissionsDashboard />} />
```

**Rationale:** Users clicking "Data Entry" or Data Hub studio icon now have a valid destination.

**Test:**
```bash
# Frontend should already be running from earlier steps
# Navigate to http://localhost:5173/dataschema
# Expected: Module browser (if multi-module) or redirect (if single-module)
```

**Checkpoint:** ✅ Route added, DataHubHome renders

---

### Step 8: Build & Integration Test

**Objective:** Verify all navigation works, no 404s, role gates work

**Test Scenario 1: Data-Owner (Single Module)**
```bash
# 1. Login as fac_officer (Facilities module only)
# Username: fac_officer
# Password: DataOwner_2026!

# 2. Check landing
# Expected: Auto-redirect to /modules/{facilities_id} (shows table grid)

# 3. Click Data Hub studio icon (3rd icon in ActivityBar)
# Expected: Navigate to /dataschema, then auto-redirect to /modules/{facilities_id}

# 4. Click "Data Entry" in sidebar
# Expected: Navigate to /dataschema, then auto-redirect to /modules/{facilities_id}

# 5. Check admin studio NOT visible
# Expected: Admin icon does NOT appear in ActivityBar

# 6. Click a table card
# Expected: Navigate to /dataschema/entry/{moduleId}/{tableId} (data entry grid)
```

**Test Scenario 2: Admin (Multi-Module)**
```bash
# 1. Login as global_admin
# Username: global_admin
# Password: GlobalAdmin_2026!

# 2. Check landing
# Expected: /dashboard (executive summary)

# 3. Click Data Hub studio icon
# Expected: Navigate to /dataschema (module browser shows all modules)

# 4. Verify "Manage All Tables" button visible
# Expected: Button appears in top-right

# 5. Click "Manage All Tables"
# Expected: Navigate to /schema-admin/table-manager

# 6. Check admin studio IS visible
# Expected: Admin icon appears in ActivityBar (4th icon)

# 7. Click a module card
# Expected: Navigate to /modules/{moduleId} (table grid)
```

**Test Scenario 3: Data-Owner (No Modules)**
```bash
# 1. Create test user with no module assignments
# OR use existing user with no roles

# 2. Login
# Expected: Login succeeds

# 3. Navigate to /dataschema
# Expected: See "No Data Modules Assigned" empty state

# 4. Check admin studio NOT visible
# Expected: Admin icon does NOT appear
```

**Test Scenario 4: Navigation Sanity**
```bash
# As any logged-in user:

# 1. Click Data Entry in sidebar
# Expected: No 404, valid page loads

# 2. Click Data Hub studio icon
# Expected: No 404, valid page loads

# 3. Click Table Manager in sidebar (admin only)
# Expected: Admin sees it, navigates successfully
# Expected: Non-admin does NOT see it in sidebar

# 4. Check browser console
# Expected: No errors (warnings about Pulse are OK)
```

**Acceptance Criteria (ALL must pass):**
- ✅ Zero 404 errors in Data Hub navigation
- ✅ Single-module users auto-redirect to their module
- ✅ Multi-module users see module browser
- ✅ Admin users see "Manage All Tables" button
- ✅ Non-admin users do NOT see admin studio icon
- ✅ All sidebar links work (Data Entry, Data Quality, Table Manager for admins)
- ✅ Module cards navigate to `/modules/{moduleId}`
- ✅ Table cards navigate to `/dataschema/entry/{moduleId}/{tableId}`
- ✅ No console errors (Pulse warnings OK)

**If any test fails:** Debug, fix, re-test before proceeding.

---

### Step 9: Git Commit

**Objective:** Commit all changes with clear message

```bash
# Stage all modified files
git add carbon-frontend/src/App.jsx
git add carbon-frontend/src/shell/useShellState.js
git add carbon-frontend/src/shell/ShellSidebar.jsx
git add carbon-frontend/src/pages/DataHubHome.jsx

# Commit
git commit -m "feat(A6): complete Data Hub navigation and module browser

- Enable Shell layout by default (remove feature flag)
- Fix Data Entry dead route: /dataschema/entry → /dataschema
- Hide admin studio icon for non-admin users
- Create DataHubHome module browser with auto-redirect
- Update sidebar Data Entry link to /dataschema
- Add /dataschema route to App.jsx

All user journeys tested:
- Single-module data-owners: auto-redirect ✅
- Multi-module users: module browser ✅
- Admin: module browser + Manage All Tables ✅
- Role-based studio visibility ✅

Resolves: #A6 Data Hub Completion"

# Verify commit
git log -1 --stat
```

**Checkpoint:** ✅ Changes committed

---

### Step 10: Update RUN_LOG and Create TASK-RESULT

**Objective:** Document completion of RUN A6

**File 1:** `docs/RUN_LOG.md`

**Change: Update A6 status**
```markdown
// FIND (around line 15)
| A6 | Deployment-readiness gate | ops | ⏳ PENDING | — | — |

// REPLACE WITH
| A6 | Data Hub Completion | frontend+UX | ✅ COMPLETE | 2026-07-18 | See `TASK-RESULT-A6.md` (root) |
```

**Then ADD new section before "## Archive":**
```markdown
### A6: Data Hub End-to-End Completion (2026-07-18) ✅
**Objective:** Fix Data Hub navigation and create complete user journey  
**Actions:**
- Enabled Shell layout by default (removed VITE_USE_SHELL_LAYOUT feature flag)
- Fixed Data Entry dead route: /dataschema/entry → /dataschema
- Created DataHubHome module browser with auto-redirect for single-module users
- Hidden admin studio icon for non-admin users (role-based filtering)
- Updated sidebar Data Entry link to /dataschema

**Key Metrics:**
- 1 file created: DataHubHome.jsx
- 3 files modified: App.jsx, useShellState.js, ShellSidebar.jsx
- Zero 404 errors in Data Hub navigation
- 4/4 user journey test scenarios PASSED

**Key Findings:**
- ✅ Shell layout now enabled by default (stable, no feature flag needed)
- ✅ Module browser works for multi-module users
- ✅ Single-module users auto-redirect to their module (cleaner UX)
- ✅ Admin studio hidden for non-admins (no more "Access Denied" clicks)
- ✅ All Data Hub routes valid (no dead links)

**Result:** See `TASK-RESULT-A6.md` (root) for full report
```

**File 2:** `TASK-RESULT-A6.md` (NEW FILE in root)

Create detailed result document following A5 format:
- Summary of what was built
- What changed vs what was already complete
- Step-by-step execution log
- Test results (all 4 scenarios)
- Acceptance criteria checklist (all PASS)
- Known gaps (if any)
- Commit hash and file changes
- Screenshots or curl outputs if helpful

**Template Structure:**
```markdown
# TASK-RESULT-A6.md — RUN A6: Data Hub End-to-End Completion

**Date:** 2026-07-18
**Worker:** Raptor (Code Mode)
**Master:** Planner
**Task:** [`TASK.md`](TASK.md) RUN A6

---

## Summary

**What was built:** Complete Data Hub navigation with module browser landing page...

**What changed:**
- Created DataHubHome.jsx module browser
- Enabled Shell layout by default
- ...

**What was already complete:**
- Backend DataTable/DataField/DataRow APIs
- ModuleLandingPage (table grid per module)
- ...

---

## Step 1: Read Current Code
[Execution log...]

## Step 2: Enable Shell Layout by Default
[What was changed, why, test result...]

[Continue for all steps...]

---

## Test Results

### Test Scenario 1: Data-Owner (Single Module)
✅ PASS - Auto-redirect works...

[Continue for all scenarios...]

---

## Acceptance Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Zero 404 errors in Data Hub | ✅ PASS | All routes tested |
| ... | ... | ... |

---

## Files Changed

**Created:**
- carbon-frontend/src/pages/DataHubHome.jsx (+123 lines)

**Modified:**
- carbon-frontend/src/App.jsx (+4/-2 lines)
- carbon-frontend/src/shell/useShellState.js (+12/-3 lines)
- carbon-frontend/src/shell/ShellSidebar.jsx (+1/-1 lines)

**Total:** 1 file created, 3 files modified, +140/-6 lines

---

## Git Commit

Commit: [hash]
Message: feat(A6): complete Data Hub navigation and module browser
Files: 4 changed

---

## Gaps / Future Work

1. **Bulk Import UI** - Backend may support, frontend not built (marked optional)
2. **Recent Tables Widget** - Could add localStorage tracking for "Continue where you left off"
3. **Module Search** - If users have 10+ modules, add search bar
4. **Favorites** - Allow users to star frequently used modules/tables

---

## Definition of Done Status

✅ All implementation steps completed
✅ All test scenarios passed
✅ Git commit created
✅ RUN_LOG updated
✅ TASK-RESULT created
✅ No regressions (existing features still work)
✅ Documentation complete
```

**Checkpoint:** ✅ Documentation complete

---

## 7. ACCEPTANCE CRITERIA

Must ALL be ✅ PASS to consider RUN A6 complete:

1. ✅ Shell layout enabled by default (no feature flag check)
2. ✅ `/dataschema` route exists and renders DataHubHome
3. ✅ Single-module users auto-redirect to `/modules/{moduleId}`
4. ✅ Multi-module users see module browser grid
5. ✅ Admin users see "Manage All Tables" button on DataHubHome
6. ✅ Admin studio icon hidden for non-admin users
7. ✅ Admin studio icon visible for admin users
8. ✅ "Data Entry" sidebar link navigates to `/dataschema` (no 404)
9. ✅ Data Hub studio icon navigates to `/dataschema` (no 404)
10. ✅ Module cards navigate to `/modules/{moduleId}`
11. ✅ All 4 test scenarios PASS (see Step 8)
12. ✅ No console errors (Pulse warnings OK)
13. ✅ Git commit created with all changes
14. ✅ RUN_LOG updated with A6 completion
15. ✅ TASK-RESULT-A6.md created with full report

---

## 8. DELIVERABLE FORMAT

**Primary Deliverable:** `TASK-RESULT-A6.md` in project root

**Required Sections:**
1. Summary (what was built, what changed)
2. Execution log (all 10 steps with results)
3. Test results (4 scenarios, all PASS)
4. Acceptance criteria checklist (15 items, all PASS)
5. Files changed (list + line counts)
6. Git commit hash
7. Known gaps / future work
8. Definition of Done status

**Success Signal:** All acceptance criteria ✅ PASS, zero 404 errors in Data Hub

---

## 9. DEFINITION OF DONE

**RUN A6 is complete when:**

- [x] All 10 implementation steps executed successfully
- [x] DataHubHome.jsx created (module browser with auto-redirect)
- [x] Shell layout enabled by default (feature flag removed)
- [x] Admin studio hidden for non-admins (role-based filtering)
- [x] All Data Hub routes valid (no dead links)
- [x] All 4 test scenarios PASS (logged in TASK-RESULT)
- [x] All 15 acceptance criteria PASS
- [x] Git commit created with clear message
- [x] RUN_LOG updated with A6 completion
- [x] TASK-RESULT-A6.md created with full report
- [x] No regressions (existing features still work)
- [x] Frontend builds successfully (`npm run build`)
- [x] No console errors in browser (Pulse warnings OK)

---

## 10. ESCALATION

**If you encounter:**

1. **Routing issues** (404s persist after adding route)
   - Check React Router nested route structure
   - Verify `<Outlet />` in parent layouts
   - Check if `basename` in BrowserRouter affects paths

2. **Auth context undefined** (useAuth returns null/undefined)
   - Verify AuthProvider wraps all routes in App.jsx
   - Check if context is loaded before rendering DataHubHome
   - Add loading state if needed

3. **Module auto-redirect not working**
   - Check `useEffect` dependency array in DataHubHome
   - Verify `modules` array is populated from AuthContext
   - Check if `navigate` is called correctly with `replace: true`

4. **Admin studio still visible for non-admins**
   - Verify `useAuth` import in useShellState.js
   - Check `availablePerspectives` is populated correctly
   - Verify `useMemo` dependency array includes `availablePerspectives`

5. **Build fails**
   - Check syntax errors in new files
   - Verify all imports are correct
   - Run `npm run build` and check error message

**Stop work and report if:**
- Backend API returns unexpected errors (should not happen, backend is complete)
- AuthContext structure changed (unlikely, just finished A5)
- Critical blocker prevents testing (environment issue, not code)

---

## 11. REFERENCE

**Design Doc:** [`plans/DATA_HUB_COMPLETION_PLAN.md`](plans/DATA_HUB_COMPLETION_PLAN.md)  
**Protocol:** `.clinerules/master-worker-protocol.md`  
**Previous RUN:** [`TASK-RESULT-A5.md`](TASK-RESULT-A5.md) (perspective architecture)  
**Backend RBAC:** [`TASK-RESULT-A3.md`](TASK-RESULT-A3.md) (data-owner scoping)

**Related Files:**
- [`App.jsx`](carbon-frontend/src/App.jsx) - React Router routes
- [`useShellState.js`](carbon-frontend/src/shell/useShellState.js) - Studio definitions
- [`ShellSidebar.jsx`](carbon-frontend/src/shell/ShellSidebar.jsx) - Sidebar navigation
- [`ModuleLandingPage.jsx`](carbon-frontend/src/pages/ModuleLandingPage.jsx) - Existing module landing
- [`AuthContext.jsx`](carbon-frontend/src/auth/AuthContext.jsx) - User context + modules

**Test Users:**
- `fac_officer` / `DataOwner_2026!` - Single module (Facilities)
- `global_admin` / `GlobalAdmin_2026!` - Admin (all modules)

---

**Status:** READY FOR EXECUTION  
**Next:** Worker (Raptor) executes steps 1-10, creates TASK-RESULT-A6.md
