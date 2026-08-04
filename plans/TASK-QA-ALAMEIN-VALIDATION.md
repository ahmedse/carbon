# TASK-QA-ALAMEIN-VALIDATION — QA/Validator Phase
# Role: QA/Validator · Model: DeepSeek-V3
# Depends on: Alamein Campus test journey fully built by Master Architect
# Estimated effort: M (50-70 checklist items across 4 layers)

---

## TASK IDENTITY

| Field | Value |
|-------|-------|
| **Task ID** | QA-ALAMEIN-01 |
| **Assigned Role** | qa-validator |
| **Recommended Model** | DeepSeek-V3 |
| **Predecessor** | Manual build of Alamein Campus (Master Architect follows `alamein-campus/ALAMEIN_TEST_JOURNEY.md`) |
| **Input** | `alamein-campus/ALAMEIN_TEST_JOURNEY.md` (728 lines, 7 phases, 15 modules, 5 scoped users) |
| **Output** | `TASK-RESULT-QA-ALAMEIN-01.md` (checklist matrix + findings + evidence) |
| **Gate** | All checklist items executed; L1→L4 evidence captured; severity assigned for every finding |

---

## PRE-FLIGHT (read BEFORE executing ANY checklist item)

1. Read `.ai-toolkit/project.config.md` — HARD RULES, ops script, test commands, known debt
2. Read `.ai-toolkit/shared/qa-framework.md` — 4-layer model, evidence standards, severity classification
3. Read `.ai-toolkit/shared/security.md` — RBAC expectations, ScopedRole contract
4. Read `.ai-toolkit/shared/api-contract.md` — expected response shapes, error formats
5. Read `alamein-campus/ALAMEIN_TEST_JOURNEY.md` — full test journey (you validate, you don't build)
6. Read `backend/emissions/models.py` — understand `ReportingPeriod`, `EmissionFactor`, `Calculation`, `CalculationRule`, `VerificationRecord`
7. Read `backend/accounts/rbac_utils.py` — understand `get_visible_module_ids()` contract
8. Run `./.ai-toolkit/scripts/scan.sh` — refresh registry before starting

## TEST USERS & CREDENTIALS

| Username | Password | Role | Expected Visibility (15 modules) |
|---|---|---|---|
| `ahmed` | `AdminPa_132` | Platform Admin | ALL 15 modules |
| `alamein.admin` | `Alamein_2026` | Carbon Admin | ALL 15 modules |
| `alamein.medical` | `Alamein_2026` | Data Owner | M1, M2, M11, M12, M13, M14, M15 (7 modules) |
| `alamein.transport` | `Alamein_2026` | Data Owner | M6, M7 (2 modules) |
| `alamein.finance` | `Alamein_2026` | Data Owner | M3, M4, M5 (3 modules) |
| `alamein.hotels` | `Alamein_2026` | Data Owner | M8, M9, M10 (3 modules) |

## ENVIRONMENT

- **Backend**: http://localhost:8009 (prefix: `/carbon-api/`)
- **Frontend**: http://localhost:5179 (base: `/carbon/`)
- **DB**: PostgreSQL localhost:5432
- **Services must be running**: `./manage.sh start`

---

# LAYER 1 — STRUCTURE (run first — if this fails, STOP and report)

> Tool: `./.ai-toolkit/scripts/verify.sh full` + manual checks

| # | Check | Method | Expected | Actual | Severity | Evidence |
|---|-------|--------|----------|--------|----------|----------|
| L1-1 | Backend compiles | `cd backend && ../.venv/bin/python manage.py check` | 0 issues | | P0 if fail | Paste output |
| L1-2 | All backend tests pass | `./manage.sh test` | 329+ tests, 0 failures | | P0 if fail | Paste summary |
| L1-3 | Frontend builds | `cd carbon-frontend && npm run build` | 0 errors | | P0 if fail | Paste output |
| L1-4 | Frontend lints clean (0 errors) | `cd carbon-frontend && npm run lint` | 0 errors (warnings baseline OK) | | P1 if errors | Paste error count |
| L1-5 | No hardcoded secrets in app code | `./.ai-toolkit/scripts/verify.sh antipatterns` | PASS or explained warnings | | P0 if secrets found | Paste output |
| L1-6 | Migrations up to date | `cd backend && ../.venv/bin/python manage.py makemigrations --check` | "No changes detected" | | P0 if pending | Paste output |
| L1-7 | No dead import paths (emissions imports catalog but NOT reverse) | `grep -rn "from emissions" backend/catalog/ backend/mdm/ backend/dq/ backend/dataschema/ backend/core/` | 0 results | | P0 if found | Paste output |
| L1-8 | All 5 Alamein users exist in DB | `cd backend && ../.venv/bin/python manage.py shell -c "from django.contrib.auth import get_user_model; print(get_user_model().objects.filter(username__startswith='alamein.').count())"` | 5 | | P0 if ≠5 | Paste count |
| L1-9 | Alamein OrgUnit tree exists | `cd backend && ../.venv/bin/python manage.py shell -c "from mdm.models import OrgUnit; ou=OrgUnit.objects.filter(code='ALAMEIN').first(); print(ou.get_descendant_count() if ou else 'NOT FOUND')"` | ≥5 descendants | | P0 if not found | Paste count |

---

# LAYER 2 — SECURITY (RBAC + Auth + Isolation)

> Tool: `curl` with varied JWT tokens + Browser login/logout

## 2.1 Authentication Gate

| # | Check | Method | Expected | Actual | Severity | Evidence |
|---|-------|--------|----------|--------|----------|----------|
| L2-1 | Unauthenticated API calls rejected | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8009/carbon-api/emissions/dashboard/` | 401 | | P0 | Paste status |
| L2-2 | Unauthenticated frontend routes redirect to /login | Browser: navigate to `/carbon/dashboard` without login | Redirect to `/login` | | P0 | Snapshot |
| L2-3 | JWT refresh works (token doesn't expire during test) | Login → wait 4+ minutes → hit any authed endpoint | 200 still (token refreshed) | | P1 | Status code |

## 2.2 RBAC — Cross-Org Isolation (THE CRITICAL GATE)

> For each scoped user below, obtain JWT, then query `/carbon-api/emissions/owner/summary/`
> (or the equivalent endpoint that returns visible modules).

| # | Check | Method | Expected | Actual | Severity | Evidence |
|---|-------|--------|----------|--------|----------|----------|
| L2-4 | `alamein.transport` sees ONLY Transport modules | Login as alamein.transport → `/carbon/my-data` | 2 modules (M6, M7). 0 from Medicine/Hotels/Finance/Hospital | | P0 | Paste module names returned |
| L2-5 | `alamein.hotels` sees ONLY Hotels modules | Login as alamein.hotels → `/carbon/my-data` | 3 modules (M8, M9, M10) | | P0 | Paste module names |
| L2-6 | `alamein.finance` sees ONLY Finance modules | Login as alamein.finance → `/carbon/my-data` | 3 modules (M3, M4, M5) | | P0 | Paste module names |
| L2-7 | `alamein.medical` sees Medicine + Hospital modules | Login as alamein.medical → `/carbon/my-data` | 7 modules (M1, M2, M11, M12, M13, M14, M15) | | P0 | Paste module names |
| L2-8 | `alamein.admin` sees ALL 15 modules | Login as alamein.admin → `/carbon/my-data` | 15 modules | | P0 | Paste count |
| L2-9 | `ahmed` (platform admin) sees ALL 15 | Login as ahmed → `/carbon/my-data` | 15 modules | | P0 | Paste count |

## 2.3 RBAC — Write Protection

| # | Check | Method | Expected | Actual | Severity | Evidence |
|---|-------|--------|----------|--------|----------|----------|
| L2-10 | Data owner can enter data in their org | Login as alamein.transport → `/carbon/my-data` → M6 → Data Entry → Add row | 201 Created | | P0 if 403 | Status code |
| L2-11 | Data owner CANNOT access other org's data entry | Login as alamein.transport → curl to M1 (Medicine) data entry endpoint with their token | 403 or 404 | | P0 if 200 | Status code |
| L2-12 | Admin pages blocked for data owners | Login as alamein.transport → navigate to `/carbon/admin/factors` | Unauthorized, redirect, or empty (not the full admin page) | | P1 | Snapshot or status |
| L2-13 | Admin pages blocked for data owners | Login as alamein.transport → navigate to `/carbon/reporting/periods` | Unauthorized, redirect, or empty | | P1 | Snapshot or status |

## 2.4 Governance Policy Enforcement

| # | Check | Method | Expected | Actual | Severity | Evidence |
|---|-------|--------|----------|--------|----------|----------|
| L2-14 | Scope 1 module deletion blocked by policy | Login as ahmed → try to delete a Scope 1 module with data (M1 or M6 or M11) | Blocked with policy message | | P1 if deletable | Error message |
| L2-15 | Hospital module non-owner edit blocked | Login as alamein.transport → try to PATCH M11 (Hospital) | 403 | | P1 if 200 | Status code |

---

# LAYER 3 — BEHAVIOR (API Contracts + States + Navigation)

> Tool: Browser (frontend) + `curl` (API)

## 3.1 Core Pages — 200s & Rendering

| # | Check | Method | Expected | Actual | Severity | Evidence |
|---|-------|--------|----------|--------|----------|----------|
| L3-1 | Carbon Dashboard loads | Login as ahmed → `/carbon/dashboard` | Page renders. Scope breakdown shows data. Charts visible. | | P0 if error | Snapshot |
| L3-2 | My Data (L1) loads per user | Login as each of 5 scoped users → `/carbon/my-data` | Page renders for ALL 5. Module cards shown. | | P0 if error | Count: 5/5 |
| L3-3 | Module workspace (L2) loads | Click any module on L1 | Subtitle shows row count. Grid loads. No "0 rows but 48 shown." | | P1 | Snapshot + row count |
| L3-4 | Data Entry (L3) loads | Click a table in L2 → Data Entry page | Grid with rows loads. "Add Row" button visible. | | P0 if error | Snapshot |
| L3-5 | Row Detail (L4) loads | Click a row in L3 | Right panel opens. DQ Metrics, Lineage, Related tabs all render. | | P1 if blank tab | Snapshot of each tab |
| L3-6 | Reporting Periods page loads | Login as ahmed → `/carbon/reporting/periods` | List of periods shown. "FY 2024 — Alamein" exists. | | P1 | Snapshot |
| L3-7 | Calculations page loads | Login as ahmed → `/carbon/calculations` | Calculation results visible. Scoped to modules. | | P1 | Snapshot |
| L3-8 | Verification page loads | Login as ahmed → `/carbon/verification` | Verification records shown for FY 2024 — Alamein. | | P1 | Snapshot |

## 3.2 Right Panel — All 4 Levels (the unified detail panel)

| # | Check | Method | Expected | Actual | Severity | Evidence |
|---|-------|--------|----------|--------|----------|----------|
| L3-9 | L1 panel: Trust tab shows DQ gauge | `/carbon/my-data` → click a module card | Right panel opens. Trust tab shows DQ percentage gauge. | | P1 | Snapshot |
| L3-10 | L1 panel: Impact tab shows SBTi + consumers | Same panel → Impact tab | Shows SBTi trajectory and data consumers list | | P2 | Snapshot |
| L3-11 | L1 panel: Activity tab shows filter chips | Same panel → Activity tab | Shows timeline with filter chips (Created, Updated, etc.) | | P2 | Snapshot |
| L3-12 | L2 panel: Health tab shows DQ per table | Module workspace → click table row | Health tab shows DQ rules + pass/fail for that table | | P1 | Snapshot |
| L3-13 | L2 panel: Lineage tab shows upstream/downstream | Same panel → Lineage tab | Shows linked modules, emission factors, calc chain | | P2 | Snapshot |
| L3-14 | L2 panel: Governance tab shows policies | Same panel → Governance tab | Lists active governance policies for this module | | P2 | Snapshot |
| L3-15 | L3 panel: Row Context shows DQ + asset | Data Entry → click a row | DQ Metrics tab shows per-row rule results + asset info | | P1 | Snapshot |
| L3-16 | L3 panel: Evidence tab | Same row → Evidence tab | Shows uploaded evidence files, Upload button works | | P1 | Snapshot |
| L3-17 | L3 panel: Calculations tab | Same row → Calculations tab | Shows linked EmissionFactor + CO₂e result | | P1 | Snapshot |
| L3-18 | L4 panel: Lineage tab shows calc chain | Row Detail → Lineage tab | Shows activity data → EF → CO₂e chain | | P2 | Snapshot |
| L3-19 | L4 panel: Related tab shows FK-linked rows | Row Detail → Related tab | Shows rows linked by foreign keys | | P2 | Snapshot |
| L3-20 | Gear icon works on ALL 4 levels | Click gear ⚙ on L1, L2, L3, L4 panels | Settings panel opens. Tabs can be shown/hidden. Selection persists. | | P2 | 4/4 pass |

## 3.3 Data Entry — Full CRUD Roundtrip

| # | Check | Method | Expected | Actual | Severity | Evidence |
|---|-------|--------|----------|--------|----------|----------|
| L3-21 | Create a new row | L3 → Add Row → fill fields → Save | Row appears in grid. 201 response. | | P0 if fail | Status code + row ID |
| L3-22 | Edit an existing row | L3 → click row → Edit → change value → Save | Value persists. 200 response. | | P0 if fail | Old→New value |
| L3-23 | Delete a row | L3 → select row → Delete → confirm | Row removed from grid. 204 response. | | P1 | Row count before/after |
| L3-24 | Bulk CSV import (download template first) | L3 → Import → Download Template → Fill → Upload | Rows imported. Success count shown. | | P1 | Imported count |
| L3-25 | Export selected rows to CSV | L3 → select rows → Export CSV | CSV downloads. Row count matches selection. | | P2 | File row count |

## 3.4 Data Quality Execution

| # | Check | Method | Expected | Actual | Severity | Evidence |
|---|-------|--------|----------|--------|----------|----------|
| L3-26 | DQ rules exist (9+ rules) | API: `GET /carbon-api/dq/rules/` or frontend `/catalog/dq-rules` | ≥9 rules for Alamein tables | | P1 | Count |
| L3-27 | DQ checks run (module Health tab) | L2 → click module → Health tab | DQ score %. Rules listed with pass/fail/warn. | | P1 | Snapshot |
| L3-28 | Row-level DQ visible | L3 row → DQ Metrics tab | Per-row DQ breakdown with rule results | | P2 | Snapshot |
| L3-29 | Failing rules highlighted | Module Health tab — introduce a NULL in a NOT NULL column | Rule shows as failed (red) | | P1 | Snapshot |

## 3.5 Evidence Upload

| # | Check | Method | Expected | Actual | Severity | Evidence |
|---|-------|--------|----------|--------|----------|----------|
| L3-30 | Evidence upload works | L3 → row → Evidence tab → Upload file | File appears. Download works. | | P1 | Snapshot |
| L3-31 | Trust tab shows evidence count | L1 → module → Trust tab | "N evidence documents" matches uploads | | P2 | Count match |

## 3.6 Calculations

| # | Check | Method | Expected | Actual | Severity | Evidence |
|---|-------|--------|----------|--------|----------|----------|
| L3-32 | Calculation rules exist (14 rules) | `/carbon/admin/rules` | 14 rules — one per table | | P1 | Count |
| L3-33 | CO₂e appears in row detail | L3 → any row → CO₂e chip visible | Value > 0 (not null, not 0) | | P0 if zero | Sample value |
| L3-34 | Lineage tab shows calc chain | Row → Lineage tab | Activity field → EmissionFactor → CO₂e result | | P2 | Snapshot |

## 3.7 Navigation & Breadcrumbs

| # | Check | Method | Expected | Actual | Severity | Evidence |
|---|-------|--------|----------|--------|----------|----------|
| L3-35 | Breadcrumb complete L1→L2→L3→L4 | Navigate deep: My Data → Module → Table → Row | Breadcrumb shows all 4 levels with names | | P1 | Snapshot |
| L3-36 | Back button works each level | Click Back at L2, L3, L4 | Returns to previous level correctly | | P1 | 3/3 pass |
| L3-37 | Browser tab title correct | Check `<title>` on L3 (Data Entry) | Shows table name, not "Table Data" | | P1 | Paste title |
| L3-38 | Direct URL navigation works | Paste `/carbon/my-data/row/{tableId}/{rowId}` in browser | Row detail page loads correctly | | P2 | Status 200 |

## 3.8 Bug Baseline Verification (Phase 7 of journey)

| # | Check | Method | Expected | Actual | Severity | Evidence |
|---|-------|--------|----------|--------|----------|----------|
| L3-39 | P0-1: Browser tab title on Data Entry | L3 page → check `<title>` | NOT "Table Data". Shows table/module name. | | P1 if still broken | Paste title |
| L3-40 | P1-2: Subtitle row count matches grid | L2 page → compare subtitle "X rows" to actual grid rows | Counts match | | P1 if mismatch | Both numbers |
| L3-41 | P1-3: L4 breadcrumb includes module + table | Row Detail → breadcrumb | Shows Module Name > Table Name > Row | | P1 if missing | Snapshot |
| L3-42 | P1-4: History tab shows meaningful entries | L3 row → History tab | Shows "Created", "Updated field X" etc. Not "Calc update —" | | P2 | Snapshot |
| L3-43 | P2-1: L1 Scope/Status dropdowns open | My Data → click Scope dropdown | Dropdown opens. Options clickable. | | P2 if broken | Snapshot |

---

# LAYER 4 — SCENARIO (End-to-End User Journeys)

> Tool: Browser simulation — full walkthrough

## 4.1 Data Owner Journey (alamein.medical)

| # | Check | Method | Expected | Actual | Severity | Evidence |
|---|-------|--------|----------|--------|----------|----------|
| L4-1 | Login → My Data → Module → Table → Enter Data → See CO₂e | Full walkthrough as alamein.medical | End-to-end works. All 7 modules visible. | | P0 if broken | Step-by-step snapshots |
| L4-2 | Evidence upload + verify appears | Same journey → upload evidence → check Trust tab | Evidence appears. Trust score updates. | | P1 | Before/after DQ score |
| L4-3 | Cannot cross into other org | Try to navigate to a Finance or Transport module (direct URL) | Blocked or not visible | | P0 if accessible | Status/snapshot |

## 4.2 Admin Journey (ahmed)

| # | Check | Method | Expected | Actual | Severity | Evidence |
|---|-------|--------|----------|--------|----------|----------|
| L4-4 | Create Reporting Period → verify status workflow | `/carbon/reporting/periods` → create → open → lock → submit → verify → close | All 6 transitions work. State machine valid. | | P1 | Status after each transition |
| L4-5 | Set up calc rules → run calculations → verify results | `/carbon/admin/rules` add rule → `/carbon/calculations` run | CO₂e values generated. Non-zero. | | P0 if zero | Sample calc values |
| L4-6 | Create governance policy → verify it blocks action | `/catalog/policies` → add policy → try blocked action | Policy enforced. Action blocked with message. | | P1 | Error message |

## 4.3 Cross-Browser / Mobile

| # | Check | Method | Expected | Actual | Severity | Evidence |
|---|-------|--------|----------|--------|----------|----------|
| L4-7 | Dark mode renders correctly | Toggle dark mode in any page | All pages render. No invisible text. Contrast sufficient. | | P3 | Before/after snapshot |
| L4-8 | 404 page for bad routes | Navigate to `/carbon/nonexistent-page` | Friendly 404 page, not white screen or JSON error | | P2 | Snapshot |

---

# DATA EXPECTATIONS (reference for validation)

| Metric | Expected Count |
|---|---|
| Org Units | 6 (Alamein Campus + 5 departments) |
| Users (alamein.*) | 5 |
| Modules (Data Products) | 15 |
| Tables | 15 |
| Data Rows | ~150 across all tables |
| Evidence Files | 4+ (4 PDFs provided) |
| DQ Rules | 9+ |
| Calculation Rules | 14 |
| Reporting Periods | ≥1 (FY 2024 — Alamein) |
| Governance Policies | ≥1 |
| Scopes Covered | 1, 2, 3 |

---

# EXECUTION PROTOCOL

1. **Start at L1.** Run `verify.sh full`. If L1 fails, write TASK-RESULTS immediately with failures — DO NOT proceed.
2. **L2 first with curl, then browser.** Security is gated: if RBAC isolation fails (L2-4 through L2-9), that's P0 — stop and report.
3. **L3 systematically.** Go page by page, tab by tab. Fill Actual + Evidence for every single row.
4. **L4 as final walkthrough.** This is the "real user" test — if anything fails here that passed in L3, flag it.
5. **Write TASK-RESULTS.md** with:
   - Executive summary (pass/fail counts per layer)
   - Complete checklist matrix (EVERY row filled)
   - Findings grouped by severity (P0→P3)
   - `verify.sh` output pasted
   - Recommendations for Master Architect
6. **Evidence rules** (non-negotiable):
   - Every claim has proof (HTTP status, snapshot, terminal output)
   - Raw output first, THEN interpretation
   - Severity ALWAYS assigned
   - Surprises documented (even "good" ones → P4 note)

---

# VERIFICATION GATE (what "done" means)

- [ ] All 51 checklist items have Actual + Severity + Evidence filled
- [ ] `./.ai-toolkit/scripts/verify.sh full` output pasted in results
- [ ] Every P0/P1 finding has reproduction steps
- [ ] RBAC isolation verified for all 5 scoped users
- [ ] Cross-org data leak tested (negative case)
- [ ] `TASK-RESULT-QA-ALAMEIN-01.md` written and committed
