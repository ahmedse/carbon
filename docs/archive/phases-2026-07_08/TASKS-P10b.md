# TASKS-P10b — Carbon Console + Data Owner + Legacy Redirects Audit (Routes 12–36)

**Phase:** P10b | **Role:** qa-validator | **Model:** DeepSeek-V3
**Source Plan:** `CARBON_QA_ENTERPRISE_VALIDATION_PLAN.md` §10.1.2–10.1.4

---

## YOUR MISSION

Audit 25 frontend routes grouped in 3 tiers:
- **Carbon Console** (16 routes, #12–27): full checklist
- **Data Owner** (6 routes, #28–33): redirect verification only
- **Legacy Redirects** (3 routes, #34–36): delete-or-keep recommendation

---

## CREDENTIALS (Fixed Test Users)

```
Username               Password           Role/Group            Scope
admin                  admin123           admins_group          global
dataowner1             owner123           dataowners_group      global
viewer1                viewer123          viewers_group         global (READ-ONLY)
analyst1               analyst123         analysts_group        global (READ-ONLY)
transport_officer      transport123       dataowners_group      OrgUnit: Transport (scoped)
```

**Token endpoint:** `POST http://localhost:8009/carbon-api/token/` — `{"username":"...","password":"..."}`
**Frontend origin:** `http://localhost:5179` (basename `/carbon/`)

---

## TIER 1: Carbon Console Pages (Routes #12–27)

### Audit Matrix — 16 routes × 3 roles (admin, dataowner1, viewer1)

| # | Route | Page | Roles | Priority |
|---|-------|------|-------|----------|
| 12 | `/carbon/console` | CarbonConsolePage | ALL 5 | HIGH |
| 13 | `/carbon/dashboard` | EmissionsDashboard | ALL 5 | HIGH |
| 14 | `/carbon/analytics` | AnalyticsDashboard | admin, analyst, viewer | MED |
| 15 | `/carbon/my-data` | MyDataPage | ALL 5 | HIGH |
| 16 | `/carbon/my-data/:moduleId` | ModuleWorkspacePage | dataowner1, admin | MED |
| 17 | `/carbon/my-data/:moduleId/:tableId` | DataEntryPage | dataowner1, admin | MED |
| 18 | `/carbon/my-data/row/:tableId/:rowId` | RowDetailPage | ALL 5 | HIGH (P9 fixed — re-verify) |
| 19 | `/carbon/calculations` | CalculationsPage | dataowner1, admin | MED |
| 20 | `/carbon/verification` | VerificationPage | dataowner1, auditor, admin | MED |
| 21 | `/carbon/admin/factors` | EmissionFactorsPage | admin only | LOW |
| 22 | `/carbon/admin/rules` | CalculationRulesPage | admin only | LOW |
| 23 | `/carbon/admin/gwp` | GWPReferencePage | admin only | LOW |
| 24 | `/carbon/admin/targets` | SBTiTargetsPage | admin only | LOW |
| 25 | `/carbon/reporting/generate` | ReportGeneratorPage | ALL 5 | HIGH |
| 26 | `/carbon/reporting/saved` | SavedReportsPage | ALL 5 | MED |
| 27 | `/carbon/reporting/periods` | ReportingPeriodsPage | admin only | LOW |

### Parameters for dynamic routes
- For `:moduleId`: use `31` (Carbon Footprint module)
- For `:tableId`: use any table ID from MyDataPage
- For `:rowId`: use any row ID from RowDetailPage

---

## WEB PAGE VALIDATION CHECKLIST (Tier 1)

For each page, check these 10 items:

| # | Check | Method | Expected |
|---|-------|--------|----------|
| W1 | **RENDER** | Navigate, read snapshot | No console errors |
| W2 | **LOADING** | Refresh or throttle network | Loading skeleton/spinner before content |
| W3 | **EMPTY** | Filter to no results or role with no data | Sensible empty state, not blank |
| W4 | **ERROR** | Intentionally break an API call | Friendly error, not white screen |
| W5 | **DARK_MODE** | Toggle, reload page | Dark mode applies correctly |
| W6 | **BREADCRUMB** | Read breadcrumb trail | Present, matches page hierarchy |
| W7 | **TITLE** | Check `document.title` | Page-specific (should now be "X — Carbon Platform" per P10a-FIX) |
| W8 | **RESPONSIVE** | Resize to 768px | Layout adapts, no horizontal overflow |
| W9 | **KEYBOARD** | Tab through controls | Focus ring visible, logical order |
| W10 | **NO_404_LINKS** | Click sidebar/header links | No broken internal links |

### Special RBAC checks (viewer1)
- [ ] Admin-only routes (#21–24, #27): viewer1 → 403/redirect/no access
- [ ] Write buttons (edit/delete/create): **hidden** for viewer1
- [ ] `/carbon/my-data` → viewer1: read-only view, no edit buttons

### Special RBAC checks (dataowner1)
- [ ] Can access `/carbon/my-data/:moduleId/:tableId` (DataEntryPage)
- [ ] Can access `/carbon/calculations`, `/carbon/verification`
- [ ] Admin-only routes → blocked/redirected

---

## TIER 2: Data Owner Redirect Routes (#28–33)

**Role:** admin only (verify redirect mechanics)

| # | Route | Expected Redirect | 
|---|-------|-------------------|
| 28 | `/carbon/owner/assets` | Should render DataOwnerAssetsPage |
| 29 | `/carbon/owner/portal` | → `/carbon/console` |
| 30 | `/carbon/owner/dashboard` | → `/carbon/console` |
| 31 | `/data-owner` | → `/carbon/console` |
| 32 | `/data-owner/dashboard` | → `/carbon/console` |
| 33 | `/data-owner/assets` | → `/carbon/owner/assets` |

For each: navigate → verify URL changes correctly → verify target page renders.

---

## TIER 3: Legacy Redirect Routes (#34–36)

| # | Route | Redirect Target | Recommendation |
|---|-------|-----------------|----------------|
| 34 | `/carbon/data-entry` | → `/carbon/my-data` | Keep if external links exist |
| 35 | `/carbon/data-entry/entry/:m/:t` | → `/carbon/my-data/:m/:t` | **DELETE** if no external links |
| 36 | `/carbon/data-entry/row/:t/:r` | → `/carbon/my-data/row/:t/:r` | **DELETE** if no external links |

For each: verify redirect works → recommend DELETE or KEEP.

---

## VERIFICATION GATE

Before finalizing:
```bash
./.ai-toolkit/scripts/verify.sh full
cd carbon-frontend && npm run build
```
Paste raw output. Report failures — don't fix.

---

## REPORT DELIVERABLE

Write **`TASK-RESULTS-P10b.md`** with:

1. **Executive Summary** — items tested, pass/fail/issue count
2. **Tier 1 Checklist Matrix** — 16 routes with W1-W10 + RBAC checks
3. **Tier 2 Redirect Results** — pass/fail per redirect
4. **Tier 3 Legacy Recommendations** — DELETE or KEEP per route
5. **Findings** — P0/P1/P2 with evidence
6. **Verification Output** — terminal paste
7. **Recommendations** for Master

---

## DO NOT TOUCH
- Any `.py` file
- Any `.jsx`/`.js` file (unless explicitly testing error states — revert after)
- `manage.sh`, docker, config files
- Database — read-only
- **You are QA/Validator — test, measure, report. Zero application code.**
