# TASK-G2 — Phase 06 Admin Configuration: Calculation Rules + GWP UI

## Summary
Build two admin pages (Calculation Rules CRUD + GWP Reference CRUD) and fix a broken route. These pages let admins configure the emissions calculation engine.

---

## Existing Context

**Working**:
- `EmissionFactorsPage.jsx` at `/carbon/admin/factors` — CRUD for emission factors ✅
- `ReportingPeriodsPage.jsx` at `/carbon/admin/periods` — CRUD for periods ✅
- Backend: CalculationRuleViewSet is full ModelViewSet at `/emissions/rules/`
- Backend: GWPViewSet will be upgraded to ModelViewSet by G1 worker

**Broken**:
- `/carbon/admin/rules` → points to `EmissionFactorsPage` (copy-paste bug in App.jsx line 199)

**Missing**:
- No Calculation Rules admin page
- No GWP reference admin page

---

## D1 — Fix Broken Route (App.jsx)

In `App.jsx` line 199:
```jsx
// BROKEN:
<Route path="/carbon/admin/rules" element={<AdminRoute><EmissionFactorsPage /></AdminRoute>} />
```
Change to:
```jsx
<Route path="/carbon/admin/rules" element={<AdminRoute><CalculationRulesPage /></AdminRoute>} />
```

---

## D2 — CalculationRulesPage (`src/pages/emissions/CalculationRulesPage.jsx`)

**Route**: `/carbon/admin/rules` (AdminRoute)

**Purpose**: Manage calculation rules — which DataField × EmissionFactor bindings auto-calculate emissions.

### DataGrid columns:
| Column | Source |
|--------|--------|
| ID | `id` |
| Name | `name` |
| Data Table | `data_table_name` (from D5 enriched serializer) |
| Activity Field | `activity_field_name` |
| Emission Factor | `emission_factor_name` |
| Factor Code | `emission_factor_code` |
| Rule Type | `rule_type` (chip: direct/unit_convert/formula) |
| Active | `is_active` (Switch or Chip) |
| Auto-Calc | `auto_calculate` (Chip) |
| Last Executed | `last_executed_at` (from D5) |

### Actions per row:
- **Edit** — inline dialog or drawer (name, description, factor_selector, unit_conversion_factor, is_active, auto_calculate)
- **Delete** — confirmation dialog
- **Execute Now** — POST `/rules/{id}/execute/` with optional reporting_period_id + recalculate

### Header actions:
- **New Rule** button → create dialog
- **Refresh**

### Create/Edit dialog fields:
- `name` (text, required)
- `description` (textarea)
- `data_table` (select from existing tables — fetch from `/dataschema/tables/` or context)
- `activity_field` (select, filtered by selected table's fields)
- `emission_factor` (select from `/emissions/factors/`)
- `rule_type` (select: direct/unit_convert/formula)
- `unit_conversion_factor` (number, shown when rule_type=unit_convert)
- `is_active` (switch)
- `auto_calculate` (switch)

### API calls:
```js
fetchCalculationRules(token);         // already in emissions-extended.js
createCalculationRule(data, token);   // add to emissions-extended.js
updateCalculationRule(id, data, token); // add
deleteCalculationRule(id, token);     // add
executeCalculationRule(id, data, token); // add: POST /rules/{id}/execute/
```

### Pattern: Follow `EmissionFactorsPage.jsx` style — Table with edit/delete icons, dialog for create/edit. Use `apiFetch`-based functions from emissions-extended.js.

---

## D3 — GWPReferencePage (`src/pages/emissions/GWPReferencePage.jsx`)

**Route**: `/carbon/admin/gwp` (NEW route, AdminRoute)

**Purpose**: Manage IPCC Global Warming Potential reference values.

### DataGrid columns:
| Column | Source |
|--------|--------|
| ID | `id` |
| Gas Name | `gas_name` |
| Formula | `gas_formula` |
| AR5 100yr | `gwp_ar5_100yr` |
| AR6 100yr | `gwp_ar6_100yr` |
| AR5 20yr | `gwp_ar5_20yr` |
| AR6 20yr | `gwp_ar6_20yr` |
| CAS # | `cas_number` |
| Notes | `notes` (truncated) |

### Actions per row:
- **Edit** — dialog (gas_name, gas_formula, 4 GWP values, cas_number, notes)
- **Delete** — confirmation dialog

### Header actions:
- **New GWP** button → create dialog

### API calls (add to emissions-extended.js):
```js
fetchGWPValues(token);         // GET /emissions/gwp/
createGWPValue(data, token);   // POST /emissions/gwp/
updateGWPValue(id, data, token); // PATCH /emissions/gwp/{id}/
deleteGWPValue(id, token);     // DELETE /emissions/gwp/{id}/
```

### Pattern: Same as EmissionFactorsPage — table + dialogs.

---

## D4 — Route Registration + Navigation

### App.jsx — add route:
```jsx
<Route path="/carbon/admin/gwp" element={<AdminRoute><GWPReferencePage /></AdminRoute>} />
```

### manifest.js — verify sidebar entries exist:
```js
{ label: 'Emission Factors',     path: '/carbon/admin/factors',      role: 'carbon:admin' },  // exists
{ label: 'Calculation Rules',    path: '/carbon/admin/rules',        role: 'carbon:admin' },  // exists
{ label: 'GWP Reference',        path: '/carbon/admin/gwp',          role: 'carbon:admin' },  // ADD
```

### config.js — add route:
```js
gwp: `${emissionsPrefix}gwp/`,
```

---

## D5 — API Client Functions (enhance `src/api/emissions-extended.js`)

Add:
```js
fetchGWPValues(token)
createGWPValue(data, token)
updateGWPValue(id, data, token)
deleteGWPValue(id, token)
createCalculationRule(data, token)
updateCalculationRule(id, data, token)
deleteCalculationRule(id, token)
executeCalculationRule(id, data, token)
```

All use existing `apiFetch()` from `src/api/api.js`.

---

## Files to Create/Change

| File | Action |
|------|--------|
| `src/pages/emissions/CalculationRulesPage.jsx` | **NEW** — D2 |
| `src/pages/emissions/GWPReferencePage.jsx` | **NEW** — D3 |
| `src/api/emissions-extended.js` | **ENHANCE** — D5: add 8 functions |
| `src/App.jsx` | **FIX** — D1 (line 199) + D4 (add gwp route) |
| `src/config.js` | **ENHANCE** — D4: add gwp route |
| `src/apps/carbon/manifest.js` | **ENHANCE** — D4: add GWP nav entry |

---

## DO-NOT-TOUCH

- ❌ No backend files
- ❌ No auth changes
- ❌ No theme changes
- ❌ No existing pages (EmissionFactorsPage, ReportingPeriodsPage)
- ❌ No layout shell components
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
#    - /carbon/admin/rules loads CalculationRulesPage (NOT EmissionFactorsPage)
#    - /carbon/admin/gwp loads GWPReferencePage
#    - Create/Edit/Delete a Calculation Rule works
#    - Create/Edit/Delete a GWP value works
#    - Execute rule action triggers calculation
#    - Sidebar has GWP Reference entry
```

## Success Criteria

- [ ] `npm run build` — no errors
- [ ] `verify.sh antipatterns` — no new violations
- [ ] `/carbon/admin/rules` shows Calculation Rules grid (not factors)
- [ ] `/carbon/admin/gwp` shows GWP reference values grid
- [ ] CRUD operations work for both pages
- [ ] Execute rule shows response
- [ ] Sidebar has all 3 Carbon Admin entries (Factors, Rules, GWP)
- [ ] Only 6 files changed/created
