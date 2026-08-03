# TASKS-P7.md — Bug Fixes & Seed Data Remediation

**Date:** 2026-07-31
**Owner:** debugger-fixer (Backend Worker)
**Priority:** HIGH
**Source:** Browser simulation by Master Architect (admin, dataowner1, transport_officer, viewer1)

---

## BUG 1: RoleBadge TypeError in HeaderEnhanced [CRITICAL]

**Symptom:** Console `TypeError: role.replace is not a function`

**Root cause:** `carbon-frontend/src/components/HeaderEnhanced.jsx:81`
```js
const primaryRole = user?.roles?.[0];  // ← returns OBJECT {role, active, org_unit_id, module_id}
```
The `RoleBadge` component at line 57 calls `role.replace("_group", "").replace("_", " ")` on the string it receives. But `user.roles[i]` is an **object**, not a string (populated from `accounts/my-roles/`).

**Fix:** Change line 81 to extract the role string:
```js
const primaryRole = user?.roles?.[0]?.role;
```

**File:** `carbon-frontend/src/components/HeaderEnhanced.jsx`
**Lines:** 81
**Estimated effort:** 1 line change, 2 min

---

## BUG 2: Groups Page "Failed to load groups" [LOW]

**Symptom:** GroupsPage shows "Failed to load groups" alert

**Investigation result:** The API endpoint `GET /carbon-api/accounts/groups/` works correctly for admin — returns 4 groups (admins_group, dataowners_group, analysts_group, viewers_group). Admin is both superuser AND has global admins_group ScopedRole, so `HasScopedRole.has_permission()` returns True immediately.

**Possible causes:**
- Transient network/fetch error during simulation
- Token expired mid-session (simplejwt 5-min default)
- Frontend render race condition (loading → error before data arrives)

**Action:** Re-test in browser as admin → Admin → Groups. If it works now, mark as no-fix. If it fails, check Network tab for HTTP status code.

**Estimated effort:** 5 min verification, possibly no code changes needed

---

## BUG 3: Emissions Dashboard Shows 0t CO₂e [HIGH] ✅ CONFIRMED

**Symptom:** Dashboard shows 0t CO₂e, 0% DQ score, but "189 data points"

**Root cause:** Frontend defaults to year **2025**, but ALL 189 seeded calculations have `reporting_year=2026`.

**Proof (API test):**
```
GET /carbon-api/carbon/dashboard/?year=2025 → total_co2e_tonnes=0.0  (calc_count=189*)
GET /carbon-api/carbon/dashboard/?year=2026 → total_co2e_tonnes=7926.73 (calc_count=189)
```
*`calculation_count` is a secondary bug — it uses unfiltered `base_qs.count()` instead of year-filtered `qs.count()` in `DashboardService.get_dashboard_data()`.

**Fix 1 (Frontend):** `carbon-frontend/src/pages/EmissionsDashboard.jsx:182`
```js
// Change:
const [selectedYear, setSelectedYear] = useState(2025);
// To:
const [selectedYear, setSelectedYear] = useState(2026);
```

**Fix 2 (Secondary — service):** `backend/emissions/services.py` line ~86
```python
# Change:
'calculation_count': base_qs.count(),
# To:
'calculation_count': qs.count(),
```

**Files:**
- `carbon-frontend/src/pages/EmissionsDashboard.jsx` line 182
- `backend/emissions/services.py` line ~86

**Estimated effort:** 2 line changes, 2 min

---

## BUG 4: MUI Grid Deprecation Warnings [LOW]

**Symptom:** Console warnings about `item`, `xs`, `sm`, `md` props removed in MUI Grid v2

**Action:** Sweep all Grid components and migrate to Grid2 `size` prop API.

```jsx
// OLD (deprecated):
<Grid item xs={12} sm={6} md={4}>

// NEW (Grid2):
<Grid size={{ xs: 12, sm: 6, md: 4 }}>
```

**Migration approach:**
1. `grep -rn "Grid" carbon-frontend/src/ --include="*.jsx"` to find all Grid usages
2. Change `import Grid from '@mui/material/Grid'` → `import Grid from '@mui/material/Grid2'`
3. Replace `<Grid item>` with `<Grid>`, `xs/sm/md/lg/xl` props → `size={{ xs, sm, md, lg, xl }}`
4. Run FE tests to verify: `cd carbon-frontend && npm test`

**Estimated effort:** 20-30 min sweep across ~30 Grid usages

---

## RBAC GAP: transport_officer and viewer1 Land on "No Applications Available"

**Symptom:** After login, these users see empty app dashboard. Only `dataowner1` lands on Carbon Footprint (redirects to `/carbon/modules/30`).

**Root cause:** Platform apps are not assigned to role groups in seed data. `seed_all.py` has no `with_app_assignments` step.

**Action:** Add a `with_app_assignments()` method to the `SeedBuilder` class in `backend/seed_all.py` that assigns platform apps to role groups so each role sees relevant apps on login.

**Platform apps** (from `accounts/platform-apps/` API):
- Carbon Footprint → dataowners_group, analysts_group
- Data Quality → admins_group, analysts_group
- MDM → admins_group
- Catalog → admins_group, viewers_group
- Data Schema → admins_group, dataowners_group
- etc.

**Estimated effort:** ~30 min for seed method + re-seed with `--reset`

---

## Seed Data Assessment

### ✅ What EXISTS (sufficient):
| Area | Count | Notes |
|------|-------|-------|
| Users | 5 | admin, dataowner1, analyst1, viewer1, transport_officer |
| OrgUnits | 5 | Smart Village, Transport, Facilities, IT, Academics |
| Modules | 4 | Carbon Footprint, Data Quality, MDM, Catalog |
| DataTables | ~6 | Electricity, Water, Transport, etc. |
| DataRows | ~189 | Sufficient for demo dashboards |
| CalculationRules | 7 | Electricity×2, Water, Chilled Water, Diesel, Gasoline, Commute |
| Calculations | 189 | 7,926 t CO₂e across all rules |
| Groups | 4 | admins, dataowners, analysts, viewers |
| ReportingPeriods | — | At least 1 (2026) |
| EmissionFactors | — | Grid 2024/2025, water, fuels |
| DQ Rules | — | Profile scores |

### ⚠️ What NEEDS MORE:
| Area | Gap | Priority |
|------|-----|----------|
| Platform App Assignments | No apps assigned to role groups (RBAC gap) | **HIGH** |
| 2025 seed data | All calculations are 2026-only, dashboard defaults to 2025 | **HIGH** |
| ReportingPeriod diversity | Only 2026 year present | MEDIUM |
| DQ scores > 0 | `data_quality_score` formula returns 0 for year-2025 filter | MEDIUM (fixed with BUG 3) |
| Scope 3 data | Only Scope 1 & 2 emissions in seed | LOW |
| More diverse fuel types | Current seed covers electricity, water, diesel, gasoline | LOW |

---

## Execution Order

1. **BUG 1** (RoleBadge) — 1 line, immediate
2. **BUG 3** (Dashboard year) — 2 lines, immediate
3. **BUG 4** (MUI Grid) — sweep, ~30 min
4. **BUG 2** (Groups page) — verify, likely no code change
5. **RBAC GAP** (app assignments) — seed method, ~30 min + re-seed

**Total estimated effort:** ~1 hour
