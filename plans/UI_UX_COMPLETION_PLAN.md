# UI/UX End-to-End Completion Plan — Context & Information Architecture

**Date:** 2026-07-18  
**Status:** Planning  
**Priority:** HIGH  
**Dependencies:** A6 complete (Data Hub navigation fixed)

---

## Executive Summary

Based on screenshot review and codebase audit, the Carbon platform has **excellent visual design** but **missing contextual information** that users need:

1. **Scope visibility gap:** Scope 1/2/3 exists in code but not visible in current UI view
2. **Org unit context missing:** User's org unit shows in scope banner but not prominently in navigation
3. **Data Quality navigation inconsistent:** Flies to separate dashboard, breaks Data Hub context
4. **Breadcrumbs incomplete:** Missing module/table context
5. **Header lacks user context:** No org unit indicator, minimal role visibility

---

## Audit Findings

### ✅ What Works Well

**Visual Design:**
- Clean, modern interface with good color scheme
- Consistent typography and spacing
- Clear iconography (Scope 1/2/3 icons defined)
- Professional card-based layouts

**Data Integrity:**
- Scopes ARE tracked in backend (Module.scope field)
- Org units ARE in context ([`Layout.jsx:34`](carbon-frontend/src/components/Layout.jsx:34))
- Breadcrumbs system exists ([`Breadcrumbs.jsx`](carbon-frontend/src/shell/Breadcrumbs.jsx))
- Multiple pages show scope badges ([`ModuleLandingPage`](carbon-frontend/src/pages/ModuleLandingPage.jsx:14), [`DataHubHome`](carbon-frontend/src/pages/DataHubHome.jsx:8))

### ❌ What's Missing (Screenshot Evidence)

**From User Screenshot:**
```
URL: localhost:5179/carbon/dataschema

Carbon logo
[Grid icon] [CO2 icon] [Data icon]

DATA HUB                     [<]

    [+] Data Entry
    [≡] Data Quality
```

**Issues:**
1. **No scope indicator** - User doesn't know which scopes they're viewing
2. **No org unit display** - User doesn't know their organizational context
3. **No module count** - User doesn't know how many modules they have access to
4. **Breadcrumbs not visible** - No navigation trail
5. **User context minimal** - Header doesn't show user's org/role prominently

---

## Gap Analysis by Component

### 1. HeaderNew.jsx — Missing Context Display

**Current State:**
- Shows username + avatar
- Shows role badge (small, in dropdown)
- Shows perspective tabs (if multiple)
- **Missing:** Org unit name, module count, user's scope access

**Proposed Enhancement:**
```
[Logo] Carbon  |  [Org Unit: Medicine Faculty] [3 Modules]  |  [Perspectives]  [User ▼]
```

**Where to add:**
```javascript
// HeaderNew.jsx - add between logo and perspective tabs
<Box display="flex" alignItems="center" gap={2} ml={3}>
  {userOrgUnit && (
    <Box display="flex" alignItems="center" gap={0.5}>
      <LocationOnIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
      <Typography variant="caption" color="text.secondary">
        {userOrgUnit}
      </Typography>
    </Box>
  )}
  {moduleCount > 0 && (
    <Chip 
      label={`${moduleCount} Modules`}
      size="small"
      variant="outlined"
    />
  )}
</Box>
```

---

### 2. DataHubHome.jsx — Missing Scope Filter

**Current State:**
- Shows modules in grid
- Each card shows scope badge
- **Missing:** Scope filter/tabs to view modules by scope

**Proposed Enhancement:**
```
Data Hub
[Tabs: All | Scope 1 | Scope 2 | Scope 3]

[Module cards filtered by selected scope]
```

**Implementation:**
```javascript
const [scopeFilter, setScopeFilter] = useState('all');

const filteredModules = useMemo(() => {
  if (scopeFilter === 'all') return modules;
  return modules.filter(m => m.scope === parseInt(scopeFilter));
}, [modules, scopeFilter]);

// Add Tabs above module grid
<Tabs value={scopeFilter} onChange={(_, val) => setScopeFilter(val)}>
  <Tab value="all" label="All Modules" />
  <Tab value="1" label="Scope 1" icon={<NatureIcon />} />
  <Tab value="2" label="Scope 2" icon={<BoltIcon />} />
  <Tab value="3" label="Scope 3" icon={<LocalShippingIcon />} />
</Tabs>
```

---

### 3. ShellSidebar.jsx — Missing Context Indicators

**Current State:**
- Shows "DATA HUB" title
- Shows menu items (Data Entry, Data Quality)
- **Missing:** 
  - User's org unit
  - Module count
  - Scope summary (e.g., "2 Scope 1, 1 Scope 2")

**Proposed Enhancement:**
```
DATA HUB                     [<]

Medicine Faculty             <-- org unit
3 Modules (2×S1, 1×S2)      <-- scope summary

    [+] Data Entry
    [≡] Data Quality
```

**Implementation:**
```javascript
// ShellSidebar.jsx - add context header
<Box px={2} py={1.5} borderBottom="1px solid" borderColor="divider">
  <Typography variant="h6">{title}</Typography>
  
  {activeStudio === 'dataschema' && userOrgUnit && (
    <>
      <Typography variant="caption" color="text.secondary" display="block">
        {userOrgUnit}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        {modules.length} modules • {scopeSummary}
      </Typography>
    </>
  )}
</Box>
```

---

### 4. ModuleLandingPage.jsx — Missing Scope Context

**Current State:**
- Shows module name as h4
- Shows module description
- Shows table cards with scope badges
- **Missing:** 
  - Scope indicator in page header
  - "Back to Data Hub" navigation
  - Scope icon next to module name

**Proposed Enhancement:**
```
[<- Back to Data Hub]

[Scope1 Icon] Stationary Combustion (Scope 1)
Direct emissions from fuel combustion

[Table cards...]
```

**Implementation:**
```javascript
<Box display="flex" alignItems="center" gap={1} mb={1}>
  <IconButton onClick={() => navigate('/dataschema')}>
    <ArrowBackIcon />
  </IconButton>
  <Typography variant="caption">Back to Data Hub</Typography>
</Box>

<Box display="flex" alignItems="center" gap={1.5} mb={1}>
  {scopeIcons[module.scope]}
  <Typography variant="h4">
    {module.name}
  </Typography>
  <Chip 
    label={scopeLabels[module.scope]}
    size="small"
    sx={{ bgcolor: getScopeColor(module.scope) }}
  />
</Box>
```

---

### 5. Data Quality Navigation Fix

**Current Issue:**
- Clicking "Data Quality" → `/dashboards/data-quality`
- Breaks Data Hub context (user loses sidebar, breadcrumbs)
- User doesn't know how to get back

**Two Solutions:**

**Option A: Keep separate DQ dashboard, add breadcrumbs**
```javascript
// Breadcrumbs.jsx
'/dashboards/data-quality': {
  label: 'Data Quality',
  icon: RuleIcon,
  parent: '/dataschema',  // <-- links back to Data Hub
},
```

**Option B: Embed DQ view in Data Hub (recommended)**
```javascript
// Create /dataschema/quality route
<Route path="/dataschema/quality" element={<DataQualityView />} />

// ShellSidebar.jsx
case 'dataschema':
  return [
    { label: 'Data Entry', path: '/dataschema', icon: AddCircleOutlineIcon },
    { label: 'Data Quality', path: '/dataschema/quality', icon: RuleIcon }, // <-- stays in Data Hub
  ];
```

Benefits: User stays in Data Hub context, sidebar visible, breadcrumbs work

---

### 6. Breadcrumbs Enhancement

**Current State:**
- Breadcrumbs defined in [`Breadcrumbs.jsx`](carbon-frontend/src/shell/Breadcrumbs.jsx:17)
- `/dataschema` entry exists (line 53)
- **Missing:** Module and table breadcrumbs

**Proposed Enhancement:**
```
Home > Data Hub > Stationary Combustion > Fuel Consumption
```

**Implementation:**
```javascript
// Breadcrumbs.jsx - add dynamic module/table resolution
function buildBreadcrumbs(pathname, context) {
  // Handle /modules/:moduleId
  const moduleMatch = pathname.match(/\/modules\/(\d+)/);
  if (moduleMatch) {
    const moduleId = moduleMatch[1];
    const module = context?.modules?.find(m => String(m.id) === moduleId);
    
    return [
      { label: 'Home', path: '/', icon: HomeIcon },
      { label: 'Data Hub', path: '/dataschema', icon: StorageIcon },
      { label: module?.name || `Module ${moduleId}`, path: pathname, icon: null },
    ];
  }
  
  // Handle /dataschema/entry/:moduleId/:tableId
  const entryMatch = pathname.match(/\/dataschema\/entry\/(\d+)\/(\d+)/);
  if (entryMatch) {
    const [, moduleId, tableId] = entryMatch;
    const module = context?.modules?.find(m => String(m.id) === moduleId);
    const table = context?.tablesByModule?.[moduleId]?.find(t => String(t.id) === tableId);
    
    return [
      { label: 'Home', path: '/', icon: HomeIcon },
      { label: 'Data Hub', path: '/dataschema', icon: StorageIcon },
      { label: module?.name || `Module ${moduleId}`, path: `/modules/${moduleId}`, icon: null },
      { label: table?.title || `Table ${tableId}`, path: pathname, icon: null },
    ];
  }
  
  // ... rest of breadcrumb logic
}
```

---

## Implementation Phases

### Phase 1: Header Context Enhancement
**Objective:** Show user's org unit + module count in header

**Files to modify:**
- `carbon-frontend/src/components/HeaderNew.jsx`

**Changes:**
- Add org unit display between logo and perspective tabs
- Add module count chip
- Get data from `useAuth()` context

**Visual:**
```
Before: [Logo] Carbon  |  [Perspectives] [User]
After:  [Logo] Carbon  |  Medicine Faculty • 3 Modules  |  [Perspectives] [User]
```

**Acceptance:**
- ✅ Org unit name visible in header
- ✅ Module count visible in header
- ✅ Updates when user switches perspective

---

### Phase 2: Data Hub Scope Filtering
**Objective:** Add scope tabs to Data Hub home to filter modules by scope

**Files to modify:**
- `carbon-frontend/src/pages/DataHubHome.jsx`

**Changes:**
- Add `scopeFilter` state
- Add Tabs component above module grid
- Filter `modules` by selected scope
- Add scope icons to tabs

**Visual:**
```
Data Hub

[All | Scope 1 | Scope 2 | Scope 3]  <-- New scope filter tabs

[Module cards for selected scope]
```

**Acceptance:**
- ✅ Scope tabs render above modules
- ✅ Clicking scope tab filters modules
- ✅ "All" shows all modules
- ✅ Tab shows count (e.g., "Scope 1 (2)")

---

### Phase 3: Sidebar Context Display
**Objective:** Show org unit + scope summary in Data Hub sidebar

**Files to modify:**
- `carbon-frontend/src/shell/ShellSidebar.jsx`

**Changes:**
- Add context header below title
- Show org unit name
- Show module count + scope breakdown
- Only show for Data Hub studio

**Visual:**
```
DATA HUB

Medicine Faculty
3 modules: 2×S1, 1×S2

[+] Data Entry
[≡] Data Quality
```

**Acceptance:**
- ✅ Org unit displays in sidebar
- ✅ Module count + scope summary displays
- ✅ Only shows in dataschema studio
- ✅ Updates when context changes

---

### Phase 4: Module Page Enhancement
**Objective:** Add scope context + back navigation to module landing page

**Files to modify:**
- `carbon-frontend/src/pages/ModuleLandingPage.jsx`

**Changes:**
- Add "Back to Data Hub" button
- Add scope icon + chip next to module name
- Show scope in subtitle

**Visual:**
```
[← Back to Data Hub]

[Scope1 Icon] Stationary Combustion (Scope 1)
Direct emissions from owned or controlled sources

[Table cards...]
```

**Acceptance:**
- ✅ Back button navigates to `/dataschema`
- ✅ Scope icon displays next to module name
- ✅ Scope chip displays with correct color
- ✅ Visual hierarchy clear

---

### Phase 5: Data Quality Navigation Fix
**Objective:** Keep Data Quality within Data Hub context

**Option:** Create `/dataschema/quality` route

**Files to modify:**
1. `carbon-frontend/src/App.jsx` - Add route
2. `carbon-frontend/src/shell/ShellSidebar.jsx` - Update link
3. `carbon-frontend/src/pages/dataschema/DataQualityView.jsx` - Create new component (reuse DQ dashboard content)

**Changes:**
```javascript
// App.jsx
<Route path="/dataschema/quality" element={<DataQualityView />} />

// ShellSidebar.jsx
{ label: 'Data Quality', path: '/dataschema/quality', icon: RuleIcon },

// DataQualityView.jsx
// Copy content from DataQualityDashboard but:
// - Remove header/footer (Shell provides)
// - Filter by user's modules only
// - Show module-specific DQ metrics
```

**Acceptance:**
- ✅ Data Quality link stays within Data Hub
- ✅ Sidebar remains visible
- ✅ Breadcrumbs show: Home > Data Hub > Data Quality
- ✅ DQ metrics filtered to user's modules

---

### Phase 6: Breadcrumbs Enhancement
**Objective:** Show complete navigation trail for modules + tables

**Files to modify:**
- `carbon-frontend/src/shell/Breadcrumbs.jsx`

**Changes:**
- Add dynamic module resolution from URL params
- Add dynamic table resolution from URL params
- Use AuthContext to get module/table names
- Build 4-level trail: Home > Data Hub > Module > Table

**Visual:**
```
Home > Data Hub > Stationary Combustion > Fuel Consumption
```

**Acceptance:**
- ✅ Module breadcrumb shows module name (not just ID)
- ✅ Table breadcrumb shows table title (not just ID)
- ✅ Clicking breadcrumb navigates correctly
- ✅ Breadcrumbs update on route change

---

### Phase 7: Shell Layout Small Fixes
**Objective:** Polish existing Shell components

**Files to modify:**
- `carbon-frontend/src/shell/Shell.jsx` - Any final adjustments
- `carbon-frontend/src/shell/StatusBar.jsx` - Show current module/table
- `carbon-frontend/src/shell/EditorArea.jsx` - Ensure proper spacing

**Changes:**
- StatusBar shows current context (e.g., "Module: Stationary Combustion")
- EditorArea padding consistent
- Any visual polish needed

**Acceptance:**
- ✅ StatusBar shows meaningful context
- ✅ No visual bugs in Shell
- ✅ Consistent spacing throughout

---

## Summary of Changes

### New Components
- `carbon-frontend/src/pages/dataschema/DataQualityView.jsx` (reuse existing DQ dashboard)

### Modified Components
1. **HeaderNew.jsx** - Add org unit + module count
2. **DataHubHome.jsx** - Add scope filter tabs
3. **ShellSidebar.jsx** - Add context header (org + scope summary)
4. **ModuleLandingPage.jsx** - Add back button + scope context
5. **Breadcrumbs.jsx** - Add dynamic module/table resolution
6. **App.jsx** - Add `/dataschema/quality` route
7. **StatusBar.jsx** - Show current module/table context

### Visual Improvements
- Org unit visible in 3 places (header, sidebar, scope banner)
- Scope visible in 4 places (header context, tabs, module cards, breadcrumbs)
- Module count visible in 2 places (header, sidebar)
- Breadcrumbs show full context trail
- Data Quality integrated into Data Hub

---

## Acceptance Criteria (All Phases)

1. ✅ User can see their org unit in header
2. ✅ User can see module count in header
3. ✅ User can filter modules by scope in Data Hub
4. ✅ Sidebar shows org unit + scope summary
5. ✅ Module page shows scope context clearly
6. ✅ Back button on module page works
7. ✅ Data Quality stays within Data Hub context
8. ✅ Breadcrumbs show full navigation trail (Home > Data Hub > Module > Table)
9. ✅ StatusBar shows current module/table
10. ✅ All scope badges use consistent colors
11. ✅ No navigation dead ends
12. ✅ Context clear at all times

---

## Future Enhancements (Out of Scope)

**Org Unit Switcher:**
- If user has multiple org units, add dropdown in header to switch context
- Would require backend support for "active org unit" session state

**Scope Analytics:**
- Add "Scope Overview" page showing emissions by scope
- Link from scope tabs in Data Hub

**Recent Activity:**
- Track last 5 visited modules/tables
- Show in Data Hub sidebar for quick access

**Favorites:**
- Allow users to "star" frequently used modules/tables
- Show starred items at top of lists

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Header gets crowded with context | Medium | Use compact chips, hide on small screens |
| Scope tabs confuse users | Low | Clear labels + icons, defaults to "All" |
| Data Quality duplication | Low | Reuse existing component, just change route |
| Breadcrumbs performance (context lookup) | Low | Data already in AuthContext (cached) |

---

## Next Steps

1. Review this plan with stakeholders
2. Get approval on visual mockups (if needed)
3. Create TASK.md for RUN A7: UI/UX Context Completion
4. Execute phases 1-7 sequentially
5. Test all user scenarios
6. Create TASK-RESULT-A7.md

---

**Status:** Ready for implementation  
**Estimated Complexity:** Medium (7 phases, mostly frontend, no backend changes)  
**Dependencies:** A6 complete (Data Hub navigation works)