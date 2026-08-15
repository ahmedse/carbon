# Carbon Footprint App — Critical Architecture Audit

**Date:** 2026-07-23  
**Auditor:** Zoo (Architect Mode)  
**Scope:** Complete Carbon Footprint domain app after consolidation

---

## Executive Summary

The Carbon Footprint app is **functionally complete** but has **4 critical architectural issues** and **7 quality concerns** that need addressing before production deployment.

### Critical Issues (Must Fix)

1. **ReportingPeriod Model/UI Mismatch** — Backend has rich status workflow (draft→open→locked→submitted→verified→closed), but frontend only exposes `is_active` boolean
2. **Missing RBAC Bypass** — All navigation items set to `role: '*'` defeats the purpose of the manifest role system
3. **Data Owner Pages Depend on Catalog APIs** — Violates domain isolation (fetching from catalog instead of emissions)
4. **Data Entry Hub External Dependency** — Points to `/dataschema` which is outside Carbon namespace

### Quality Concerns (Should Fix)

5. Missing empty state handling in ReportingPeriodsPage
6. No pagination support for reporting periods list
7. Inconsistent error handling patterns across pages
8. useNotification() dependency creates fragility
9. No loading states for delete operations
10. Missing form validation feedback
11. No success notifications after CRUD operations

---

## Detailed Findings

### 🔴 Critical Issue #1: ReportingPeriod Model/UI Mismatch

**Location:** [`backend/emissions/models.py:8-94`](backend/emissions/models.py:8) vs [`carbon-frontend/src/pages/emissions/ReportingPeriodsPage.jsx`](carbon-frontend/src/pages/emissions/ReportingPeriodsPage.jsx)

**Problem:**  
Backend `ReportingPeriod` model has sophisticated workflow:
```python
STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('open', 'Open for Data Entry'),
    ('locked', 'Locked for Review'),
    ('submitted', 'Submitted'),
    ('verified', 'Verified'),
    ('closed', 'Closed'),
]
period_type = models.CharField(max_length=20, choices=PERIOD_TYPE_CHOICES, default='annual')
status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
is_baseline = models.BooleanField(default=False)
```

Frontend form only has:
```javascript
const [form, setForm] = useState({
  name: '',
  start_date: '',
  end_date: '',
  is_active: false,  // ❌ Computed property, not a model field!
  description: '',
});
```

**Impact:**
- Cannot set period status (always defaults to 'draft')
- Cannot set period type (annual/quarterly/monthly/custom)
- Cannot mark baseline periods
- `is_active` is a computed property (lines 89-93), not a field — this creates confusion

**Fix Required:**
Update ReportingPeriodsPage form to include:
- `status` dropdown (draft/open/locked/submitted/verified/closed)
- `period_type` selector (annual/quarterly/monthly/custom)
- `is_baseline` checkbox
- Remove `is_active` from form (it's read-only)

---

### 🔴 Critical Issue #2: RBAC Bypass (Security Risk)

**Location:** [`carbon-frontend/src/apps/carbon/manifest.js:50-69`](carbon-frontend/src/apps/carbon/manifest.js:50)

**Problem:**
All navigation items have `role: '*'`:
```javascript
items: [
  { label: 'Dashboard',          path: '/carbon/dashboard',          role: '*' },
  { label: 'My Portal',          path: '/carbon/owner/portal',       role: '*' },
  // ... all items with role: '*'
  { label: 'Emission Factors',   path: '/carbon/admin/factors',      role: '*' },
  { label: 'Reporting Periods',  path: '/carbon/reporting/periods',  role: '*' },
]
```

**Impact:**
- Defeats the manifest role system declared in lines 40-44
- All users see admin pages (Emission Factors, Reporting Periods) even if they're not admins
- Data owners see items they can't use
- Security through obscurity (relying on `<AdminRoute>` wrapper only)

**Declared Roles (Unused):**
```javascript
roles: [
  { key: 'carbon:data_owner', label: 'Data Owner',    scoped: true,  ... },
  { key: 'carbon:analyst',    label: 'Analyst',       scoped: false, ... },
  { key: 'carbon:admin',      label: 'Carbon Admin',  scoped: false, ... },
]
```

**Fix Required:**
Restore proper role assignments:
```javascript
{ label: 'Dashboard',          path: '/carbon/dashboard',          role: '*' },
{ label: 'My Portal',          path: '/carbon/owner/portal',       role: 'carbon:data_owner' },
{ label: 'My Dashboard',       path: '/carbon/owner/dashboard',    role: 'carbon:data_owner' },
{ label: 'My Assets',          path: '/carbon/owner/assets',       role: 'carbon:data_owner' },
{ label: 'Data Entry Hub',     path: '/dataschema',                role: 'carbon:data_owner' },
{ label: 'Generate Report',    path: '/carbon/reporting/generate', role: 'carbon:analyst' },
{ label: 'Saved Reports',      path: '/carbon/reporting/saved',    role: 'carbon:analyst' },
{ label: 'Analytics',          path: '/carbon/analytics',          role: 'carbon:analyst' },
{ label: 'Emission Factors',   path: '/carbon/admin/factors',      role: 'carbon:admin' },
{ label: 'Reporting Periods',  path: '/carbon/reporting/periods',  role: 'carbon:admin' },
```

**Why This Happened:**
User reported role filtering wasn't working (shows only "Dashboard"). Investigation revealed role format mismatch. Instead of fixing the matching logic properly, a quick bypass was applied.

**Root Cause of Role Matching Issue:**
ShellSidebar.jsx role filter (lines 156-173) tries to convert `carbon:data_owner` → `data-owner` and match against `availablePerspectives`, but Ahmed's user doesn't have these perspective strings properly set.

---

### 🔴 Critical Issue #3: Data Owner Pages Violate Domain Isolation

**Location:** [`carbon-frontend/src/pages/data-owner/DataOwnerPortalPage.jsx:6-12`](carbon-frontend/src/pages/data-owner/DataOwnerPortalPage.jsx:1)

**Problem:**
Data Owner pages (portal, dashboard, assets) use **Catalog APIs** instead of Carbon/Emissions APIs:

```javascript
import {
  fetchDataDomains,      // ❌ Catalog API
  fetchAssetProfiles,    // ❌ Catalog API
  fetchGovernanceEvents, // ❌ Catalog API
} from '../../api/catalog';
```

Lines 263-274 show the calls:
```javascript
const domainsRes = await fetchDataDomains({}, token);
const assetsRes = await fetchAssetProfiles({}, token);
const eventsRes = await fetchGovernanceEvents({}, token);
```

**Impact:**
- Carbon app has a **hard dependency** on Catalog domain
- Violates the platform app isolation principle (PLATFORM_APP_MODEL.md)
- Cannot deploy Carbon independently
- Catalog schema changes break Carbon pages
- Creates circular dependency risk

**Architectural Principle Violated:**
From `docs/PLATFORM_APP_MODEL.md` section 2 (Layer 3 contract):
> "Apps must not directly import from other apps. Cross-app data access goes through platform services or explicit API contracts."

**Fix Required:**
1. Create Carbon-specific backend endpoints:
   - `GET /api/v1/emissions/owner/summary/` — returns org unit, modules, DQ summary
   - `GET /api/v1/emissions/owner/assets/` — returns emission-generating assets scoped to user
   - `GET /api/v1/emissions/owner/activity/` — returns recent submission/calculation events

2. Update frontend to use emissions APIs:
```javascript
import {
  fetchOwnerSummary,   // New: emissions-specific
  fetchOwnerAssets,    // New: emissions-specific
  fetchOwnerActivity,  // New: emissions-specific
} from '../../api/emissions';
```

**Why This Happened:**
Data Owner pages were created during P1 (TASK-CARBON-P1-SCOPED-OWNER-APPS.md) before emissions domain was fully defined. Quick path was to reuse existing catalog APIs.

---

### 🔴 Critical Issue #4: Data Entry Hub External Dependency

**Location:** [`carbon-frontend/src/apps/carbon/manifest.js:59`](carbon-frontend/src/apps/carbon/manifest.js:59)

**Problem:**
```javascript
{ label: 'Data Entry Hub', path: '/dataschema', role: '*' },
```

**Impact:**
- Points to `/dataschema` which is **outside Carbon namespace** (`/carbon/*`)
- Unclear ownership — is this part of Carbon or a separate studio?
- Current routing in `Shell.jsx` remaps `/dataschema` → `carbon` studio, but this is a band-aid
- Creates namespace confusion for future developers

**Background:**
Originally, "dataschema" was a separate studio (`emissions studio` activity bar icon). During consolidation, it was moved into Carbon navigation but path wasn't updated.

**Fix Required:**
**Option A (Recommended):** Move data entry under Carbon namespace
```javascript
{ label: 'Data Entry Hub', path: '/carbon/data-entry', role: 'carbon:data_owner' },
```
Create new route: `<Route path="/carbon/data-entry" element={<DataEntryPage />} />`

**Option B:** Keep `/dataschema` but document as Carbon sub-module
Update manifest with explicit note:
```javascript
{
  label: 'Data Entry Hub',
  path: '/dataschema',  // Legacy path, owned by Carbon domain
  role: 'carbon:data_owner',
  description: 'Table-driven data entry for emissions modules',
}
```

---

## Quality Concerns (Non-Critical)

### 5. Missing Empty State in ReportingPeriodsPage

**Location:** [`ReportingPeriodsPage.jsx:188-193`](carbon-frontend/src/pages/emissions/ReportingPeriodsPage.jsx:188)

Current empty state is plain text. Should have:
- Illustration or icon
- Call-to-action button
- Helpful text explaining what periods are for

### 6. No Pagination for Reporting Periods

**Location:** [`ReportingPeriodsPage.jsx:170-209`](carbon-frontend/src/pages/emissions/ReportingPeriodsPage.jsx:170)

Backend `ReportingPeriodViewSet` uses DRF's default pagination, but frontend assumes all periods fit on one page. Will break when org has 50+ periods.

**Fix:** Add Material-UI TablePagination component

### 7. Inconsistent Error Handling

**Problem:** Some pages use `useNotification()`, others use inline `<Alert>`, some use `console.error()` only.

**Examples:**
- ReportingPeriodsPage: Inline `<Alert>` (lines 140-144) ✅
- EmissionFactorsPage: Uses both drawer errors + console warnings ⚠️
- DataOwnerPortalPage: Uses `showNotification()` from context (line 283) ⚠️

**Recommendation:** Standardize on inline `<Alert>` with `onClose` handler (matches ReportingPeriodsPage pattern)

### 8. useNotification() Fragility

**Location:** All Data Owner pages (Portal, Dashboard, Assets)

```javascript
import { useNotification } from '../../components/NotificationProvider';
const { showNotification } = useNotification();
```

**Problem:** If `NotificationProvider` is not wrapped around these routes, pages crash. Creates implicit dependency.

**Fix:** Use inline Material-UI `<Snackbar>` instead (like ReportGeneratorPage does)

### 9. No Loading State for Delete Operations

**Location:** [`ReportingPeriodsPage.jsx:125-136`](carbon-frontend/src/pages/emissions/ReportingPeriodsPage.jsx:125)

Delete operation has no loading indicator. User clicks delete, sees confirmation, clicks OK, then... nothing visible happens until table refreshes.

**Fix:** Add loading state:
```javascript
const [deleting, setDeleting] = useState(null); // period ID being deleted
```

### 10. Missing Form Validation Feedback

**Location:** [`ReportingPeriodsPage.jsx:104-108`](carbon-frontend/src/pages/emissions/ReportingPeriodsPage.jsx:104)

Validation just shows generic error:
```javascript
if (!form.name || !form.start_date || !form.end_date) {
  setError('Please fill in all required fields');
  return;
}
```

**Better:** Highlight specific fields with `error` prop on `TextField`, show helper text under each field.

### 11. No Success Notifications

**Location:** After save/delete operations in ReportingPeriodsPage, EmissionFactorsPage

Users don't get confirmation that operation succeeded. Should show brief success message.

---

## Architecture Compliance Score

| Category | Score | Notes |
|----------|-------|-------|
| **Namespace Isolation** | 6/10 | `/dataschema` path violates namespace |
| **Domain Separation** | 4/10 | Data Owner pages depend on Catalog APIs |
| **RBAC Implementation** | 3/10 | All items public (`role: '*'`) |
| **Model/UI Alignment** | 5/10 | ReportingPeriod form missing key fields |
| **Error Handling** | 7/10 | Mostly good, some inconsistency |
| **Code Quality** | 8/10 | Clean React patterns, good structure |
| **API Design** | 9/10 | Well-structured, RESTful |
| **Overall** | **6/10** | Functional but needs architecture fixes |

---

## Recommendations by Priority

### P0 (Block Production)
1. **Fix RBAC bypass** — Restore proper role assignments in manifest
2. **Fix Data Owner API dependencies** — Create emissions-specific endpoints

### P1 (High Priority)
3. **Align ReportingPeriod UI with model** — Add status, period_type, is_baseline fields
4. **Resolve Data Entry Hub namespace** — Move to `/carbon/data-entry` or document ownership

### P2 (Medium Priority)
5. **Standardize error handling** — Use inline `<Alert>` everywhere
6. **Remove useNotification() dependency** — Use Material-UI Snackbar
7. **Add pagination** — TablePagination for ReportingPeriodsPage

### P3 (Nice to Have)
8. **Add success notifications** — Brief confirmation after CRUD ops
9. **Improve empty states** — Icons, better messaging
10. **Add loading indicators** — For delete operations
11. **Better form validation** — Field-level feedback

---

## Conclusion

The Carbon Footprint app is **code-complete and buildable**, but has **architectural debt** that violates platform principles. The most critical issues are:

1. RBAC is completely bypassed (security risk)
2. Data Owner pages break domain isolation (maintenance risk)
3. ReportingPeriod UI doesn't match backend model (functionality gap)
4. Namespace confusion with `/dataschema` path

**Recommendation:** Fix P0 items before production deployment. P1 items should be addressed in next sprint. P2/P3 can be scheduled for later iterations.

The app demonstrates good code quality and React patterns, but needs architectural cleanup to align with the platform model documented in `PLATFORM_APP_MODEL.md` and `STRATEGY_DATA_TRUST_PLATFORM.md`.
