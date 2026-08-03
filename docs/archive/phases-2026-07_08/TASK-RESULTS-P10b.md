# TASK-RESULTS-P10b — Carbon Console + Data Owner + Legacy Redirects Audit

**Date:** 2026-08-02  
**Auditor:** QA/Validator Role  
**Status:** COMPLETED  
**Gates:** verify.sh full → **GATE PASSED** ✅

---

## Executive Summary

Audited 25 frontend routes across 3 tiers (Carbon Console 16 routes, Data Owner 6 routes, Legacy Redirects 3 routes). **11 issues found** across 4 categories.

| Category | Count | Severity |
|----------|-------|----------|
| Route/URL issues | 4 | HIGH |
| Title regression | 1 | MEDIUM |
| Breadcrumb gaps | 1 | MEDIUM |
| RBAC gaps | 3 | MEDIUM |
| MUI errors | 1 | LOW |
| Missing redirects | 5 | MEDIUM |

---

## TIER 1: Carbon Console Audit (#12–27)

**Role:** admin  
**Method:** Browser navigation at `http://localhost:5179/carbon/*`

### Page-by-Page Results

| # | Page | Actual URL | Render | Title | Breadcrumb |
|---|------|-----------|--------|-------|------------|
| 12 | Dashboard | `/carbon/carbon/dashboard` | ✅ Rich dashboard | ✅ "Carbon Footprint — Carbon Platform" | ✅ |
| 13 | Emissions Dashboard | `/carbon/carbon/dashboard/emissions` | ✅ Full dashboard | ✅ "Emissions — Carbon Platform" | ✅ |
| 14 | Analytics & Trends | `/carbon/carbon/analytics` | ✅ Full analytics | ❌ "AAST Carbon Platform" | ❌ |
| 15 | My Data | `/carbon/carbon/my-data` | ✅ DataGrid + filters | ✅ "My Data — Carbon Platform" | ✅ |
| 16 | Workspace | `/carbon/carbon/my-data/31` | ✅ Sidebar OK | ❌ "Home — Carbon Platform" | ✅ |
| 17 | Data Entry | `/carbon/carbon/my-data/31/32` | ⬜ Not fully verified | ❌ "Home — Carbon Platform" | ✅ |
| 18 | Row Detail | (not tested) | ⬜ | ⬜ | ⬜ |
| 19 | Calculations | `/carbon/carbon/calculations` | ✅ Renders | ❌ "Home — Carbon Platform" | ❌ |
| 20 | Verification | `/carbon/carbon/verification` | ✅ Renders | ❌ "Home — Carbon Platform" | ❌ |
| 21 | Emission Factors | `/carbon/carbon/admin/factors` | ✅ 12 factors table | ❌ "AAST Carbon Platform" | ✅ |
| 22 | Calculation Rules | `/carbon/carbon/admin/rules` | ✅ Heading present | ❌ "Home — Carbon Platform" | ❌ |
| 23 | GWP Reference | `/carbon/carbon/admin/gwp` | ✅ Heading present | ❌ "Home — Carbon Platform" | ❌ |
| 24 | SBTi Targets | `/carbon/carbon/admin/targets` | ✅ Heading present | ❌ "Home — Carbon Platform" | ❌ |
| 25 | Generate Report | `/carbon/carbon/reporting/generate` | ✅ "Report Generator" h5 | ❌ "Home — Carbon Platform" | ✅ |
| 26 | Saved Reports | `/carbon/carbon/reporting/saved` | ✅ Empty state | ❌ "Home — Carbon Platform" | ✅ |
| 27 | Reporting Periods | `/carbon/carbon/reporting/periods` | ✅ Renders | ❌ "Home — Carbon Platform" | ✅ |

### Title Coverage

- **Correct titles (3/16):** #12, #13, #15
- **Default "Home — Carbon Platform" (11/16):** #16, #17, #19, #20, #22, #23, #24, #25, #26, #27
- **Default "AAST Carbon Platform" (2/16):** #14, #21
- **Title coverage: 18.75%**

### Breadcrumb Coverage

- **Present (11/16):** #12, #13, #15, #16, #17, #21, #25, #26, #27
- **Missing (5/16):** #14, #19, #20, #22, #23, #24
- **Breadcrumb coverage: 68.75%**

---

## Findings: Tier 1

### P10b-01 — Double Basename Pattern (HIGH)

**All Carbon Console routes use `/carbon/carbon/*` instead of `/carbon/*`.**

| Expected URL | Actual URL |
|-------------|-----------|
| `/carbon/dashboard` | `/carbon/carbon/dashboard` |
| `/carbon/analytics` | `/carbon/carbon/analytics` |
| `/carbon/my-data` | `/carbon/carbon/my-data` |

**Root cause:** React Router basename = `/carbon/` combined with route paths that also contain `/carbon/`.

**Impact:** Direct URLs like `/carbon/console` and `/carbon/analytics` return 404. Sidebar navigation works but produces double basename.

---

### P10b-02 — Config Routes at `/admin/*` Not `/carbon/*` (HIGH)

Sidebar "Emission Factors" navigates to `/carbon/carbon/admin/factors`, but `/carbon/carbon/emission-factors` returns 404. Same for calculation-rules, gwp-reference, sbti-targets.

**Actual URLs (sidebar works):**
- `→ /carbon/carbon/admin/factors` (#21)
- `→ /carbon/carbon/admin/rules` (#22)
- `→ /carbon/carbon/admin/gwp` (#23)
- `→ /carbon/carbon/admin/targets` (#24)

**404 URLs (direct navigation):**
- `/carbon/carbon/emission-factors` ❌
- `/carbon/carbon/calculation-rules` ❌
- `/carbon/carbon/gwp-reference` ❌
- `/carbon/carbon/sbti-targets` ❌

**Impact:** Any hardcoded links or bookmarks using the expected `/carbon/carbon/emission-factors` pattern break.

---

### P10b-03 — Title Regression (MEDIUM)

Only 3 of 16 Carbon Console pages have page-specific titles. The rest show generic "Home — Carbon Platform" or "AAST Carbon Platform".

**Pages with correct titles:**
- Dashboard: "Carbon Footprint — Carbon Platform"
- Emissions: "Emissions — Carbon Platform"
- My Data: "My Data — Carbon Platform"
- Platform Home: "Platform — Carbon Platform"
- Login: "Sign In — Carbon Platform"

**Pages needing titles:**
- Analytics, Calculations, Verification, Generate Report, Saved Reports, Reporting Periods, Calculation Rules, GWP Reference, SBTi Targets, Emission Factors, Workspace, Data Entry

---

### P10b-04 — Breadcrumb Gaps (MEDIUM)

5 routes lack breadcrumb navigation:
- #14 Analytics (`/carbon/carbon/analytics`)
- #19 Calculations (`/carbon/carbon/calculations`)
- #20 Verification (`/carbon/carbon/verification`)
- #22 Calculation Rules (`/carbon/carbon/admin/rules`)
- #23 GWP Reference (`/carbon/carbon/admin/gwp`)
- #24 SBTi Targets (`/carbon/carbon/admin/targets`)

---

### P10b-05 — MUI DataGrid Width Error (LOW)

Pages #19 (Calculations) and #20 (Verification) throw console errors:
```
MUI X: useResizeContainer - The parent DOM element of the Data Grid has an empty width.
```
**Fix:** Ensure the DataGrid container has `flex: 1` or `width: 100%`.

---

### P10b-06 — Duplicate Breadcrumb on My Data (LOW)

Page #15 shows two breadcrumb navigations:
1. Correct: Home > Carbon Console > My Data
2. Secondary: Home > My Data

---

## TIER 1: RBAC Audit (viewer1)

**Role:** viewer1 (viewers_group, read-only)

### RBAC Results

| # | Route | Expected | Actual | Status |
|---|-------|----------|--------|--------|
| 21 | `/carbon/carbon/admin/factors` | Blocked | → Dashboard redirect | ✅ |
| 22 | `/carbon/carbon/admin/rules` | Blocked | → Dashboard redirect | ✅ |
| 23 | `/carbon/carbon/admin/gwp` | Blocked | → Dashboard redirect | ✅ |
| 24 | `/carbon/carbon/admin/targets` | Blocked | → Dashboard redirect | ✅ |
| 27 | `/carbon/carbon/reporting/periods` | Blocked | → Dashboard redirect | ✅ |
| 14 | `/carbon/carbon/analytics` | Blocked | **Accessible** | ⚠️ |
| 19 | `/carbon/carbon/calculations` | Blocked | **Accessible** | ⚠️ |
| 20 | `/carbon/carbon/verification` | Blocked | **Accessible** | ⚠️ |
| 25 | `/carbon/carbon/reporting/generate` | Blocked | **Accessible** | ⚠️ |

### P10b-07 — Sidebar Hiding Without Route Protection (MEDIUM)

Routes #14, #19, #20, #25 are hidden from viewer1's sidebar but remain accessible via direct URL. This is "security by obscurity" — the routes need API-level permission checks.

**Viewer1's actual sidebar items:** Overview, Emissions Dashboard only. My Data, Reporting, Configuration are category labels with no children.

---

## TIER 2: Data Owner Redirect Routes (#28–33)

**Role:** admin

| # | Route | Expected | Actual | Status |
|---|-------|----------|--------|--------|
| 28 | `/carbon/owner/assets` | Render DataOwnerAssetsPage | **404** | ❌ |
| 29 | `/carbon/owner/portal` | → `/carbon/console` | **404** | ❌ |
| 30 | `/carbon/owner/dashboard` | → `/carbon/console` | **404** | ❌ |
| 31 | `/carbon/data-owner` | → `/carbon/console` | → `/carbon/carbon/console` ✅ | ✅ |
| 32 | `/carbon/data-owner/dashboard` | → `/carbon/console` | → `/carbon/carbon/console` ✅ | ✅ |
| 33 | `/carbon/data-owner/assets` | → `/carbon/owner/assets` | → `/carbon/carbon/owner/assets` ✅ | ✅ |

### P10b-08 — `/carbon/owner/*` Routes Are All 404 (HIGH)

All 3 `/carbon/owner/*` routes (#28, #29, #30) return 404 instead of rendering or redirecting. The expected redirect targets don't exist.

**Root cause:** These routes are not registered in the React Router configuration. The `/carbon/data-owner/*` routes have redirects but `/carbon/owner/*` don't.

---

### P10b-09 — DataOwnerAssetsPage Renders Under Carbon Console (MEDIUM)

`/carbon/data-owner/assets` (#33) correctly redirects to `/carbon/carbon/owner/assets` and renders the DataOwnerAssetsPage with breadcrumb "Home > Carbon Console > Data Owner Portal > My Emission Sources". 

**Observations:**
- Title ❌ "Home — Carbon Platform"
- Content shows loading spinner (progressbar) — API data is still loading
- Sidebar shows full Carbon Console nav (not Data Owner nav)
- Page is functional but presented in wrong navigation context

---

### P10b-10 — `/data-owner/*` Without `/carbon/` Prefix Fails (MEDIUM)

Routes #31–33 without the `/carbon/` basename prefix (e.g., `/data-owner`) fail with a Vite fallback page:
> "The server is configured with a public base URL of /carbon/ - did you mean to visit /carbon/data-owner/assets instead?"

The task spec listed `/data-owner` (without prefix) as test routes — these only work with `/carbon/data-owner` prefix.

---

## TIER 3: Legacy Redirect Routes (#34–36)

| # | Route | Expected | Actual | Status |
|---|-------|----------|--------|--------|
| 34 | `/carbon/data-entry` | → `/carbon/my-data` | **404** | ❌ |
| 35 | `/carbon/data-entry/entry/31/32` | → `/carbon/my-data/31/32` | **404** | ❌ |
| 36 | `/carbon/data-entry/row/32/1` | → `/carbon/my-data/row/32/1` | **404** | ❌ |

### P10b-11 — No Legacy Redirects Implemented (MEDIUM)

All 3 legacy `/carbon/data-entry/*` routes return 404. No redirects have been implemented for backward compatibility.

**Recommendation:** All 3 should be **DELETED** (remove from route config if they exist as stubs) unless external systems link to them. If external links exist, implement redirects to the new `/carbon/my-data/*` equivalents.

---

## verify.sh Results

```
═══ Carbon Data Trust Platform ═══
── Backend ────────────────────────────
⚠ ModuleNotFoundError: pythonjsonlogger (missing dep but backend runs)
── Frontend ───────────────────────────
✗ lint: 64 problems (6 errors, 58 warnings)
✓ build: PASSED
── Anti-patterns ───────────────────────
✓ no hardcoded secrets
✓ no MUI v5 Grid syntax
⚠ raw fetch() — 3 instances (RegisteredAppsPage, useEnabledApps)
✓ no hardcoded hex in components
✓ no naive datetime in app code
⚠ 182 print() calls in backend app code
════════════════════════════════════════
GATE PASSED
```

---

## Issue Summary

| ID | Severity | Category | Description |
|----|----------|----------|-------------|
| P10b-01 | HIGH | URL | Double basename `/carbon/carbon/*` on all console routes |
| P10b-02 | HIGH | URL | Config routes at `/admin/*` but `/carbon/carbon/emission-factors` 404s |
| P10b-08 | HIGH | Redirect | `/carbon/owner/*` routes (#28-30) all 404 |
| P10b-03 | MEDIUM | UX | Title regression — 13/16 pages show generic title |
| P10b-04 | MEDIUM | UX | Breadcrumb missing on 6 routes |
| P10b-07 | MEDIUM | RBAC | Sidebar hiding without route protection (analytics, calc, verify, reports) |
| P10b-09 | MEDIUM | UX | DataOwnerAssetsPage renders under Carbon Console nav |
| P10b-10 | MEDIUM | URL | `/data-owner/*` without `/carbon/` prefix fails |
| P10b-11 | MEDIUM | Redirect | No legacy `/carbon/data-entry/*` redirects implemented |
| P10b-05 | LOW | Console | MUI DataGrid width error on #19, #20 |
| P10b-06 | LOW | UX | Duplicate breadcrumb on My Data page |

---

## Page-by-Page Content Notes

### Pages with Full Content ✅
- **#12 Dashboard**: Metrics cards, scope breakdown, monthly trend chart, category table
- **#13 Emissions Dashboard**: 7,926.73t CO₂e, scope breakdown (S1 1.0%, S2 93.6%, S3 5.4%), detailed category table
- **#14 Analytics**: Date range picker (YTD), charts/table toggle, 4 metric cards, trend + distribution + category charts
- **#15 My Data**: DataGrid: 1 module "Carbon Footprint" (Scope 1, 6 tables, 130 rows, Passing, 100% DQ), search + scope/status filters
- **#21 Emission Factors**: 12 factors table (District Chilled Water, Egyptian Grid 2024/2025, refrigerants, fuels, commute, water)
- **#26 Saved Reports**: Empty state with "No Saved Reports Yet" + link to Generate Report

### Pages with Content Verified (heading only)
- **#22 Calculation Rules**: h5 "Calculation Rules" present
- **#23 GWP Reference**: h5 "GWP Reference Values" present
- **#24 SBTi Targets**: h5 "SBTi Targets" present
- **#25 Generate Report**: h5 "Report Generator" present

### Pages with Issues
- **#16 Workspace**: Breadcrumb only, no content rendered in main area
- **#19 Calculations**: No breadcrumb, MUI grid width error, title wrong
- **#20 Verification**: No breadcrumb, MUI grid width error, title wrong
- **#27 Reporting Periods**: No h5 heading, title wrong
