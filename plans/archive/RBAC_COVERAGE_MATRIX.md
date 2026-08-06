# RBAC Coverage Matrix — Carbon Data Trust Platform
# Generated: 2026-08-04
# Covers: All permissions, routes, menu items, action buttons

## ── USER ROLES ────────────────────────────────────────────────────

### Role Definitions
| # | Role Group | Perspective | Scope | Read | Write | Admin |
|---|-----------|-------------|-------|------|-------|-------|
| R1 | `admins_group` (global org=None) | `admin` | Platform | ✅ | ✅ | ✅ |
| R2 | `carbon_lead` | `carbon-admin` | Org | ✅ | ✅ | Carbon only |
| R3 | `dataowners_group` | `data-owner` | Org | ✅ | Org-data only | ❌ |
| R4 | `analysts_group` | `analyst` | Any | ✅ | ❌ | ❌ |
| R5 | `viewers_group` | `viewer` | Org | ✅ | ❌ | ❌ |
| R6 | `auditors_group` | `None` ⚠️ | Org | ✅ | ❌ | ❌ |

### Test Users
| User | Roles | Expected Perspectives |
|------|-------|----------------------|
| ahmed | superuser | admin |
| alamein.admin (now) | dataowners_group@Alamein | data-owner |
| test.admin | admins_group@global | admin |
| test.carbon_lead | carbon_lead@Alamein | carbon-admin |
| test.analyst | analysts_group@global | analyst |
| test.viewer | viewers_group@Alamein | viewer |
| test.auditor | auditors_group@Alamein | (none) ⚠️ |
| test.multi | dataowners_group + analysts_group | data-owner, analyst |

## ── FRONTEND ROUTE MATRIX ─────────────────────────────────────────

| # | Route | Required Perspective | R1 admin | R2 carbon-lead | R3 data-owner | R4 analyst | R5 viewer | R6 auditor |
|---|-------|---------------------|----------|----------------|---------------|------------|-----------|------------|
| F1 | `/` (PlatformHome) | any | ✅ card | ✅ card | ✅ card | ✅ card | ✅ card | ✅ card |
| F2 | `/carbon/console` | `*` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| F3 | `/carbon/dashboard` | `*` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| F4 | `/carbon/analytics` | `carbon:analyst` | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| F5 | `/carbon/my-data` | `carbon:data_owner` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| F6 | `/carbon/my-data/:id` | `carbon:data_owner` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| F7 | `/carbon/my-data/:id/:tid` | `carbon:data_owner` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| F8 | `/carbon/calculations` | `carbon:data_owner` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| F9 | `/carbon/verification` | `carbon:data_owner` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| F10 | `/carbon/admin/factors` | `carbon:admin` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| F11 | `/carbon/admin/rules` | `carbon:admin` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| F12 | `/carbon/admin/gwp` | `carbon:admin` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| F13 | `/carbon/admin/targets` | `carbon:admin` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| F14 | `/carbon/reporting/generate` | `carbon:analyst` | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| F15 | `/carbon/reporting/saved` | `carbon:analyst` | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| F16 | `/carbon/reporting/periods` | `carbon:analyst` | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| F17 | `/carbon/owner/assets` | data-owner | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| F18 | `/admin/users` | `admin` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| F19 | `/admin/groups` | `admin` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| F20 | `/admin/org-units` | `admin` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| F21 | `/admin/access` | `admin` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| F22 | `/admin/audit` | `admin` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| F23 | `/catalog/products` | catalog-admin | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

## ── SIDEBAR ITEM MATRIX ───────────────────────────────────────────

| # | Label | manifest role | R1 | R2 | R3 | R4 | R5 | R6 |
|---|-------|--------------|----|----|----|----|----|-----|
| S1 | Overview | `*` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| S2 | Emissions Dashboard | `*` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| S3 | Analytics & Trends | `carbon:analyst` | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| S4 | Data Entry | `carbon:data_owner` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| S5 | Calculations | `carbon:data_owner` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| S6 | Verification | `carbon:data_owner` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| S7 | Generate Report | `carbon:analyst` | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| S8 | Saved Reports | `carbon:analyst` | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| S9 | Reporting Periods | `carbon:analyst` | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| S10 | Emission Factors | `carbon:admin` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| S11 | Calculation Rules | `carbon:admin` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| S12 | GWP Reference | `carbon:admin` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| S13 | SBTi Targets | `carbon:admin` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |

## ── BACKEND API PERMISSION MATRIX ──────────────────────────────────

| # | Endpoint | Method | Permission Class | R1 | R2 | R3 | R4 | R5 | R6 |
|---|----------|--------|-----------------|----|----|----|----|----|-----|
| B1 | `/emissions/factors/` | GET | AdminOrSuperuserOnly | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| B2 | `/emissions/factors/` | POST | AdminOrSuperuserOnly | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| B3 | `/emissions/gwp/` | GET | AdminOrSuperuserOnly | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| B4 | `/emissions/gwp/` | POST | AdminOrSuperuserOnly | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| B5 | `/emissions/rules/` | GET | AdminOrSuperuserOnly | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| B6 | `/emissions/rules/` | POST | AdminOrSuperuserOnly | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| B7 | `/emissions/calculate/` | POST | AdminOrSuperuserOnly | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| B8 | `/emissions/batch-calculate/` | POST | AdminOrSuperuserOnly | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| B9 | `/emissions/sbti-targets/` | GET | AdminOrSuperuserOnly | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| B10 | `/emissions/sbti-targets/` | POST | AdminOrSuperuserOnly | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| B11 | `/emissions/periods/` | GET | ReadAnyWriteAdmin | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| B12 | `/emissions/periods/` | POST | ReadAnyWriteAdmin | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| B13 | `/emissions/calculations/` | GET | CalculationWritePermission | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| B14 | `/emissions/calculations/` | POST | CalculationWritePermission | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| B15 | `/emissions/console/` | GET | IsAuthenticated | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| B16 | `/emissions/verification/` | GET | IsAuthenticated | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| B17 | `/core/modules/` | GET | IsAuthenticated | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| B18 | `/core/modules/` | POST | HasScopedRole(admin) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| B19 | `/accounts/users/` | GET | HasScopedRole(admin) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| B20 | `/accounts/groups/` | GET | HasScopedRole(admin) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

## ── GAPS FOUND ─────────────────────────────────────────────────────

### GAP-01: `auditors_group` has no perspective mapping
- Backend: `RoleResolutionService.perspective_from_group_name('auditors_group')` → `None`
- Impact: Auditors get zero UI perspectives, zero menu items, fall to "No Data Products" dead-end
- Fix: Add `if "auditor" in normalized: return "auditor"` in perspective_from_group_name

### GAP-02: Manifest `carbon:admin` role doesn't match backend `carbon-admin`
- Frontend manifest: `role: 'carbon:admin'`
- Backend perspective: `carbon-admin`
- `filterMenuItems` correctly normalizes: `carbon:admin` → checks `admin` and `carbon-admin`
- This gap is COVERED — filterMenuItems handles the transformation ✅

### GAP-03: `dataowners_group` can SEE calculations/verification menu but can't WRITE
- Menu shows Data Entry, Calculations, Verification for data-owner
- Backend: CalculationWritePermission allows READ but not WRITE
- Pages need write-button visibility gating based on actual capabilities
- Severity: Medium — user sees buttons that 403

### GAP-04: `ReportingPeriodViewSet` GET is open to ALL authenticated users
- Uses `ReadAnyWriteAdmin` — anyone can read
- But the menu item `Reporting Periods` requires `carbon:analyst`
- Data owners can't see the menu item but CAN access the API directly
- Severity: Low — data leak through direct API access by data owners

### GAP-05: `ModuleViewSet` GET shows modules filtered by `get_visible_module_ids`
- For org-scoped users, returns ONLY modules with matching org_unit
- But 0 modules have org_unit assigned → always returns empty
- Data owners see zero modules → "No Data Products" dead-end
- Severity: CRITICAL for data owner UX

### GAP-06: AdminRoute uses `isDomainLead('carbon', ...)` but no `isDataOwner` check
- Routes like `/carbon/my-data` are NOT wrapped in AdminRoute
- They rely on the backend to 403, which is correct for security
- But the UI shows them even though the backend may deny writes
- Severity: Low (security is fine, UX needs polish)

### GAP-07: filterMenuItems doesn't handle `carbon:admin` → `carbon-admin`
- `filterMenuItems` splits on `:`: appPrefix='carbon', roleSuffix='admin'
- Checks `admin` in perspectives → NO (data owners get 'data-owner', not 'admin')
- Checks `carbon-admin` in perspectives → NO for data owners ✅
- CORRECT behavior but confusing code — the `carbon:admin` manifest role means "Carbon App Admin", not "Platform Admin"

### GAP-08: `canAccessRoute` doesn't check `isDataOwner` for `/carbon/my-data`
- `/carbon/my-data` → falls through to `hasAppAccess('carbon', ...)`
- `hasAppAccess` checks modules, domain lead, and roles
- `dataowners_group` → `dataowners_group` includes `carbon` → TRUE
- This correctly allows access ✅

### GAP-09: Verification pages — verify/reject requires admin
- `VerificationService.verify()` checks `user_is_global_admin(user) or user_is_domain_lead(user, 'carbon')`
- Data owners can SEE the verification list but can't verify/reject
- Correct behavior but UX needs to disable buttons

### GAP-10: `importexport`, `catalog`, `connections`, `dq` views use AdminOrSuperuserOnly
- No `domain_lead_groups` declared on these views
- catalog_lead, dq_lead, mdm_lead would get 403 on their own domain views
- Fix: Same pattern as carbon — declare `domain_lead_groups` on views
