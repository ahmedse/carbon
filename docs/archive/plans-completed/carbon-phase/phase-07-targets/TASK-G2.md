# TASK-G2 — Phase 07 Frontend: SBTi Targets Admin UI

## Summary
Build an admin CRUD page for SBTi (Science-Based Targets initiative) targets. The `TargetsDashboard` already exists (read-only progress view) — this adds the management side: create/edit/delete reduction targets per org unit.

---

## D1 — SBTiTargetsPage (`src/pages/carbon/SBTiTargetsPage.jsx`)

**Route**: `/carbon/admin/targets` (AdminRoute)

**Purpose**: Manage emission reduction targets per org unit.

### DataGrid columns:
| Column | Source |
|--------|--------|
| ID | `id` |
| Name | `name` |
| Org Unit | `org_unit_name` (from serializer) |
| Base Year | `base_year` |
| Target Year | `target_year` |
| Type | `target_type` (chip: absolute/intensity) |
| Scope | `scope` (chip: 1/2/3/1+2/1+2+3) |
| Reduction | `reduction_pct`% (LinearProgress bar or colored chip) |
| Status | `status` (chip: draft/warning / committed/info / approved/success) |
| Created | `created_at` (compact date) |

### Actions per row:
- **Edit** — inline drawer or dialog
- **Delete** — confirmation dialog

### Header actions:
- **New Target** button → create dialog
- **Refresh** button

### Create/Edit dialog/drawer fields:
- `name` (text, required)
- `org_unit` (select from org units — fetch from `/accounts/org-units/` or AuthContext)
- `base_year` (number, required, 2020-2050 range)
- `target_year` (number, required, > base_year)
- `target_type` (select: absolute | intensity)
- `scope` (select: 1 | 2 | 3 | 1+2 | 1+2+3)
- `reduction_pct` (number, 0.01-100.00, required)
- `status` (select: draft | committed | approved)
- `description` (textarea, optional)

### Pattern:
Follow `EmissionFactorsPage.jsx` or `GWPReferencePage.jsx` style:
- MUI `Table` (not DataGrid — simpler, matches existing admin pages)
- Inline Drawer for create/edit (same pattern as GWPReferencePage)
- `apiFetch`-based functions from emissions-extended.js
- Delete confirmation via Dialog
- Chip components for status/scope/type with theme colors

---

## D2 — API Client Functions (enhance `src/api/emissions-extended.js`)

Add 4 functions:
```js
fetchSBTiTargets(token)            // GET /emissions/targets/
createSBTiTarget(data, token)      // POST /emissions/targets/
updateSBTiTarget(id, data, token)  // PATCH /emissions/targets/{id}/
deleteSBTiTarget(id, token)        // DELETE /emissions/targets/{id}/
```

All use existing `apiFetch()` from `src/api/api.js`.

---

## D3 — Route + Navigation

### App.jsx — add import + route:
```jsx
import SBTiTargetsPage from "./pages/carbon/SBTiTargetsPage";

// Inside the Carbon section, after admin/rules and admin/gwp:
<Route path="/carbon/admin/targets" element={<AdminRoute><SBTiTargetsPage /></AdminRoute>} />
```

### config.js — add API route (if needed):
```js
targets: `${emissionsPrefix}targets/`,
```
(Check if `emissionsPrefix` is already defined — if not, it's `API_ROUTES.emissionsPrefix`)

### manifest.js — add nav entry under Carbon Admin section:
```js
{ label: 'SBTi Targets', path: '/carbon/admin/targets', role: 'carbon:admin' },
```

### ShellSidebar.jsx — add icon mapping if needed:
Check existing `navIconMap` for pattern. Add:
```js
'SBTi Targets': <TrackChangesIcon />,
```

---

## D4 — Enhance TargetsDashboard (optional, nice-to-have)

If time allows, make the existing `TargetsDashboard.jsx` at `/dashboards/targets` pull real data:

1. Import `fetchSBTiTargets` from emissions-extended.js
2. Replace hardcoded/mock target data with `useEffect` → `fetchSBTiTargets(token)`
3. Map fetched targets into the existing `MainTargetCard` + progress bars
4. Keep existing chart components (Line, Bar from chart.js)

This is **optional** — the core deliverable is the admin CRUD page (D1).

---

## Files to Create/Change

| File | Action |
|------|--------|
| `src/pages/carbon/SBTiTargetsPage.jsx` | **NEW** — D1 |
| `src/api/emissions-extended.js` | **ENHANCE** — D2: add 4 functions |
| `src/App.jsx` | **ENHANCE** — D3: add route |
| `src/config.js` | **ENHANCE** — D3: add targets API route |
| `src/apps/carbon/manifest.js` | **ENHANCE** — D3: add nav entry |
| `src/shell/ShellSidebar.jsx` | **ENHANCE** — D3: add icon mapping |
| `src/pages/dashboards/TargetsDashboard.jsx` | **OPTIONAL** — D4: wire real data |

---

## DO-NOT-TOUCH

- ❌ No backend files
- ❌ No auth changes
- ❌ No theme changes
- ❌ No existing pages (EmissionFactorsPage, GWPReferencePage, etc.)
- ❌ No layout shell components (Sidebar.jsx, Layout.jsx)
- ❌ No package.json
- ❌ No api.js

---

## Verification

```bash
# 1. Build must pass
cd carbon-frontend && npm run build

# 2. No new antipatterns
cd .. && bash .ai-toolkit/scripts/verify.sh antipatterns

# 3. Browser checklist (backend must be running):
#    - /carbon/admin/targets loads SBTiTargetsPage
#    - Create a target: name="Net Zero 2030", org_unit=Facilities, base_year=2023, target_year=2030, type=absolute, scope=1+2, reduction=42, status=draft
#    - Edit the target (change reduction to 50)
#    - Delete the target
#    - Verify entry appears in sidebar under Carbon Admin
#    - Verify TargetsDashboard at /dashboards/targets still loads (with or without real data)
```

## Success Criteria

- [ ] `npm run build` — no errors
- [ ] `verify.sh antipatterns` — no new violations
- [ ] `/carbon/admin/targets` shows SBTi targets grid
- [ ] Create target dialog works, all fields populate correctly
- [ ] Edit/delete operations work
- [ ] Sidebar has "SBTi Targets" entry under Configuration
- [ ] Scope chips use correct theme colors (scope-aware, not hardcoded #hex)
- [ ] Only 6-7 files changed/created
