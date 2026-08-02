# TASKS-P10a — Core Pages Audit (Routes 1–11, 5 Roles)

**Phase:** P10a | **Role:** qa-validator | **Model:** DeepSeek-V3
**Source Plan:** `CARBON_QA_ENTERPRISE_VALIDATION_PLAN.md` §10.1.1

---

## YOUR MISSION

Audit the 11 core frontend pages against 5 RBAC roles. Execute the web page validation
checklist from `shared/qa-framework.md` §Validation Domain 1 for each page×role combination.
Report every finding with evidence. Do NOT fix anything — document and hand back.

---

## CREDENTIALS (Fixed Test Users)

```
Username               Password           Role/Group            Scope
─────────────────────────────────────────────────────────────────────
admin                  admin123           admins_group          global
dataowner1             owner123           dataowners_group      global
analyst1               analyst123         analysts_group        global (READ-ONLY)
viewer1                viewer123          viewers_group         global (READ-ONLY)
transport_officer      transport123       dataowners_group      OrgUnit: Transport (scoped)
```

**Token endpoint:** `POST http://localhost:8009/carbon-api/token/` with body `{"username":"...","password":"..."}`

---

## THE AUDIT TARGETS (11 Core Pages)

| # | Route | Page | Roles to Test |
|---|-------|------|---------------|
| 1 | `/` | PlatformHome / RoleAwareLanding | ALL 5 |
| 2 | `/login` | Login | public (no auth) + logged-in redirect |
| 3 | `/dashboard` | → `/` redirect | ALL 5 (verify redirect) |
| 4 | `/dashboard-legacy` | Dashboard (legacy) | admin(1) + viewer1(1) — **dead page candidate** |
| 5 | `/settings` | SettingsPage | ALL 5 |
| 6 | `/help` | Help | admin(1) + viewer1(1) — verify renders, no errors |
| 7 | `/feedback` | Feedback | ALL 5 — verify submit flow |
| 8 | `/emissions` | EmissionsDashboard (legacy) | admin(1) — **dead page candidate** |
| 9 | `/emissions/dashboard` | EmissionsDashboard (dup) | admin(1) — **duplicate route candidate** |
| 10 | `/emissions/report` | EmissionsReport (legacy) | admin(1) — **dead page candidate** |
| 11 | `*` (any bad route) | NotFound (404) | public (no auth) + admin(1) + viewer1(1) |

**Frontend origin:** `http://localhost:5179` (VITE_BASE=/carbon/, full URLs prefixed with `/carbon/`)

---

## WEB PAGE VALIDATION CHECKLIST (per page)

For each page you test, fill this matrix. At minimum cover admin + viewer1 + one more role per page.

| # | Check | Method | Expected |
|---|-------|--------|----------|
| W1 | **RENDER** | Navigate to page, read browser snapshot | Page renders without console errors |
| W2 | **LOADING** | Navigate with throttled network or refresh | Loading spinner/skeleton appears before data (not blank white) |
| W3 | **EMPTY** | If page shows data, filter to no results OR use role with no data | Sensible empty state ("No data found") not blank |
| W4 | **ERROR** | Intentionally break an API call (e.g., bad module ID) | Friendly error message, not white screen or crash |
| W5 | **DARK_MODE** | Toggle dark mode, reload page | Dark mode applies correctly, no hardcoded light colors |
| W6 | **BREADCRUMB** | Check breadcrumb trail (MUI Breadcrumbs) | Breadcrumb present and matches page hierarchy |
| W7 | **TITLE** | Check `document.title` | NOT "AAST Carbon Platform" default — must be page-specific |
| W8 | **RESPONSIVE** | Resize to 768px width | Layout adapts (no horizontal scroll, elements stack) |
| W9 | **KEYBOARD** | Tab through interactive elements | Focus ring visible, tab order logical |
| W10 | **NO_404_LINKS** | Click all internal links on page (nav, sidebar, breadcrumb) | No broken links (no "Page Not Found" internal redirects) |

---

## EXECUTION PROTOCOL

```
FOR each of the 11 routes:
  FOR each role assigned to that route:
    1. Log in as that role (POST /carbon-api/token/)
    2. Navigate browser to http://localhost:5179/carbon{route}
    3. Execute W1-W10 checklist
    4. Record findings immediately (Actual + Severity + Evidence)
    5. Log out or switch token for next role
```

**Priority order (if time-constrained):**
- Tier 1 (all 5 roles): routes #1 (landing), #5 (settings), #7 (feedback)
- Tier 2 (admin + viewer1 + dataowner1): routes #2, #3, #4, #6
- Tier 3 (admin only): routes #8, #9, #10 (legacy/dead-page candidates)
- Tier 4 (public + admin): route #11 (404 page)

---

## SPECIAL CHECKS FOR DEAD-PAGE CANDIDATES

For routes #4, #8, #9, #10 also answer:
- [ ] Does this page still render? (yes/no)
- [ ] Is the content duplicated elsewhere? (which route?)
- [ ] Does the sidebar/nav still link to it?
- [ ] **Recommendation:** DELETE / MERGE / KEEP ?

---

## PERMISSION-RELEVANT CHECKS

For viewer1 and analyst1 (READ_ONLY_ROLES):
- [ ] If the page has edit/delete buttons, are they HIDDEN or DISABLED? (should be hidden)
- [ ] Can viewer1 navigate to admin-only routes like `/carbon/admin/factors`? (should 403 or redirect)

For transport_officer (SCOPED role):
- [ ] Can transport_officer see data from org-units other than Transport? (should NOT)

---

## VERIFICATION GATE

Before writing the report, run:
```bash
./.ai-toolkit/scripts/verify.sh full
```
Paste the terminal output into TASK-RESULTS. If the gate fails, note what failed — you don't fix it.

---

## REPORT DELIVERABLE

Write **`TASK-RESULTS-P10a.md`** with:

1. **Executive Summary** — items tested, pass/fail/issue count
2. **Checklist Matrix** — 11 route sections, each with role columns and W1-W10 rows
3. **Findings** — Each P0/P1/P2 issue: symptom, reproduction, severity, suggested fix
4. **Dead Page Recommendations** — for routes #4, #8, #9, #10
5. **Verification Output** — raw terminal paste
6. **Recommendations** — what to dispatch next (fix these bugs? move to P10b catalog pages?)

---

## DO NOT TOUCH

- Any `.py` file in `backend/`
- Any `.jsx` / `.js` file in `carbon-frontend/`
- `manage.sh`, `docker-compose.yml`, config files
- The database — read-only access only
- **You are QA/Validator — test, measure, report. Do NOT write application code.**

---

## CONTRACTS TO FOLLOW

| Contract | File | Why |
|----------|------|-----|
| QA methodology | `.ai-toolkit/shared/qa-framework.md` | 4-layer model, checklist format, evidence rules |
| Design system | `.ai-toolkit/shared/design-system.md` | Breadcrumb, dark mode, responsiveness expectations |
| API contract | `.ai-toolkit/shared/api-contract.md` | Auth/error response shapes |
| Security | `.ai-toolkit/shared/security.md` | RBAC expectations for read-only roles |
| Base rules | `.ai-toolkit/shared/base-rules.md` | Ops commands, terminal safety |
| Project config | `.ai-toolkit/project.config.md` | Paths, ports, hard rules |
