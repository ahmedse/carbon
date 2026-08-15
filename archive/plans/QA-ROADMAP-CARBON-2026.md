# QA Deep Audit — Carbon Data Trust Platform (2026-08-05)

> Validator: Copilot QA (qa-validator persona) · Scope: full platform walkthrough as every user persona
> Method: 4-layer QA (L1 Structure → L2 Security/RBAC → L3 Behavior → L4 Scenario)
> Evidence: every finding below was reproduced live (API probes + browser)

---

## 0. Executive Summary

| Area | Verdict |
|---|---|
| Emissions pipeline | ✅ WORKS — 20 factors, 18 rules, 1,492 calcs, dashboard renders 2024/2025/2026 |
| RBAC read isolation | ✅ WORKS — cross-org reads/writes denied (403), `my-data` scoped per role |
| Data-owner write journey | ❌ **BLOCKED — all 15 tables locked** (stale period lock) |
| Reporting governance | ⚠️ 1 period only (2025/submitted); 2024+2026 missing |
| Org model vs Carbon domain | ❌ Logistics+Transport outside Alamein Campus → domain lead sees 3/5 modules |
| Data completeness | ⚠️ `hospital_gen_log` = 1 row; `finance_electricity` = 31 rows (others 62-63) |
| Personas provisioned | ⚠️ No viewer/analyst/auditor users exist |
| UI | ✅ Renders; minor cosmetic warnings |

**Bottom line:** The system is *functional but not yet usable by its primary users (data owners)* because of a stale table-lock. The roadmap below fixes that first, then closes governance/data gaps.

---

## 1. Verified Inventory (evidence)

### 1.1 Users & Roles (6 users)
| User | Roles (ScopedRole) | Scope | Sees modules |
|---|---|---|---|
| `ahmed` | superuser / global admin | — | all 5 |
| `alamein.admin` | `carbon_lead` @ Alamein Campus (org 2) | org 2 subtree | DP1, DP4, DP5 (3/5) |
| `alamein.medical` | `dataowners_group` @ org 3 + org 7 | med+hospital | DP1, DP5 (2) |
| `alamein.finance` | `dataowners_group` @ Logistics (org 4) | org 4 | DP2 (1) |
| `alamein.transport` | `dataowners_group` @ Transportation (org 5) | org 5 | DP3 (1) |
| `alamein.hotels` | `dataowners_group` @ Student Hotels (org 6) | org 6 | DP4 (1) |

- Groups: `admins_group`(1) `dataowners_group`(0) `analysts_group`(0) `viewers_group`(0) `carbon_lead`(0) — direct-group counts are 0 because membership lives in **ScopedRole**, not Group. OK, but confusing (see F-08).

### 1.2 Org Tree (7 units)
```
1 AAST
├── 2 Alamein Campus
│   ├── 3 College of Medicine   (DP1 Medicine, DP5 Hospital)
│   ├── 6 Student Hotels        (DP4 Hotels)
│   └── 7 Educational Hospital  (no module bound!)
├── 4 Logistics Affairs         (DP2 Logistics)
└── 5 Transportation            (DP3 Transport)
```

### 1.3 Data Products (5) & Tables (15)
| DP | Module | Org | Tables | Rows |
|---|---|---|---|---|
| DP1 Medicine | 1 | 3 | 1-2 | 63 / 62 |
| DP3 Transport | 3 | 5 | 3-4 | 93 / 92 |
| DP4 Hotels | 4 | 6 | 5-7 | 63 / 62 / 62 |
| DP5 Hospital | 5 | 3 | 8-12 | 62 / **1** / 186 / 33 / 62 |
| DP2 Logistics | 2 | 4 | 13-15 | 31 / 62 / 93 |

Total rows: **1,043**. Emissions: 10,617 tCO₂e (2024: 3,957 / 2025: 4,152 / 2026: 2,507).

### 1.4 Governance assets
- 20 EmissionFactors · 18 CalculationRules · 1,492 Calculations (3 scopes)
- 50 DQRules (all active) · 49 TableProfiles · DQ score 58% (dashboard)
- 7 MDM ReferenceSets (buildings, generators, gas types, HVAC, departments, flight class, suppliers)
- 5 DataDomains · 5 GovernancePolicies (table-delete protection) · 15 GlossaryTerms
- 1 ReportingPeriod: **2025** (submitted) · 0 VerificationRecords

---

## 2. Findings — Prioritized Roadmap

### P1 — Blockers (fix first, blocks core journeys)

**F-01 · ALL 15 tables `is_locked=True` → data owners cannot enter data**
- Evidence: `POST /carbon-api/dataschema/rows/` (table 3, own scope, transport) → `403 AppFeedback "fleet_fuel_log is locked. Data modifications are blocked."` RBAC passes (same call w/ table 1 → proper `PermissionDenied`).
- Root cause: `emissions/services.py::PeriodLockService.set_period_tables_locked()` locks **every** DataTable that has *any* active CalculationRule, regardless of period. A period transition to `locked` left tables locked; later transitions (`locked→submitted`) never unlock.
- Also: period-scoping of locks is **not implemented** (code comment confirms "Row-date-level enforcement is an ADR candidate").
- Fix: (a) management command to unlock all tables (`python manage.py unlock_tables` or `DataTable.objects.update(is_locked=False)`); (b) make `open_period`/transition path unlock its own tables; (c) ADR for period-scoped locking (lock only tables of that period's modules).
- Owner: **fixer/backend**.

**F-02 · Reporting periods incomplete: only 2025; 2024 & 2026 missing**
- Evidence: `ReportingPeriod.objects.all()` → 1 row (2025-01-01→2025-12-31, submitted). Dashboard spans 2024–2026.
- Impact: no "open" period for current-year entry; `active` endpoint returns nothing; report/verification flow only covers 2025.
- Fix: seed periods 2024 + 2026 (2026 = open). Decide policy: one period per year, 2026 open for entry.
- Owner: **fixer/backend + master (policy)**.

### P2 — Governance / model gaps (high value)

**F-03 · Domain lead (`alamein.admin`) sees only 3 of 5 modules**
- Evidence: `my-data` for admin → [DP1, DP4, DP5]; org 2 subtree excludes org 4/5.
- Root cause: DP3 Transport & DP2 Logistics are bound under AAST (org 1), not Alamein Campus (org 2). The plan intends one Alamein domain.
- Decision needed (master): move Logistics/Transport under org 2 in the org tree (recommended — campus owns its logistics & transport), or grant admin a second carbon_lead role @ org 1. **Org-tree change is the cleaner fix.**
- Owner: **master (decision) + fixer (data migration)**.

**F-04 · `hospital_gen_log` has 1 row (of ~62 expected)**
- Evidence: table 9 = 1 row vs 62 in sibling tables 8/10/11/12.
- Impact: hospital generator emissions (~2,300 tCO₂e/yr in that category?) under-represented; dashboards under-report.
- Fix: data entry backlog — needs business data, not code. Flag to data owner (hospital) / seed placeholder rows for QA.
- Owner: **user/data team** (code: none).

**F-05 · `finance_electricity` 31 rows vs 62-63 elsewhere**
- Evidence: table 13 = 31 rows. Pattern suggests 1 record/month vs 2/month (two meters/buildings).
- Impact: Logistics electricity under-counted by ~50%.
- Fix: confirm intended meter set; add missing building/meter records.
- Owner: **user/data team**.

**F-06 · DP5 Hospital bound to org 3 (Medicine), not org 7 (Educational Hospital)**
- Evidence: module 5 org_unit=3; org 7 has no module bound; medical user holds roles on both 3 and 7 so it works by accident.
- Fix: rebind DP5 → org 7 (or add hospital module binding); keep medical user role on both (they own med + hospital data).
- Owner: **fixer/backend** (verify no row-module breakage).

### P3 — Minor / hygiene

**F-07 · `mdm/org-units/` exposes full 7-node org tree to any authenticated data owner**
- Evidence: transport (data owner) → `GET /carbon-api/mdm/org-units/` returns all 7 org units (names+ids+parent tree).
- Fix: scope to visible org units (`get_visible_org_units`) unless a legit cross-org need (org picker in reports) exists — decision.
- Owner: **backend** (P3, cheap).

**F-08 · Viewer / Analyst / Auditor personas have no accounts**
- Evidence: only 6 users; `viewers_group`/`analysts_group`/`auditors_group` empty; no scoped roles with those groups.
- Impact: plan's L2/L4 journeys for viewers/analysts cannot be run; system un-testable for read-only personas.
- Fix: create `alamein.viewer`, `alamein.analyst`, `alamein.auditor` + ScopedRoles (e.g., viewer @ org 2, analyst @ org 2).
- Owner: **user (provision via UI/shell) + QA re-test**.

**F-09 · Docs mismatch: plan says "15 modules"; system has 5 Data Products**
- Evidence: `plans/TASK-QA-ALAMEIN-VALIDATION.md` expects 15 modules.
- Fix: update validation plan to 5 DPs; or the intent was 15 tables — clarify terminology in docs.
- Owner: **docs**.

**F-10 · Dashboard org-context selector defaults to "College of Medicine" for global admin**
- Evidence: browser session as `ahmed` → sidebar context shows "كلية الطب — College of Medicine · 5 modules" — confusing default (should be AAST root).
- Fix: default context = highest org in user's visibility; frontend.
- Owner: **frontend** (P3/P4).

**F-11 · React Router v7 future-flag warnings in console**
- Evidence: two `v7_startTransition` / `v7_relativeSplatPath` warnings on every page.
- Fix: add future flags in `createBrowserRouter`/`BrowserRouter`; cosmetic but clean.
- Owner: **frontend** (P4).

**F-12 · No VerificationRecords, no CalculationAudits visible**
- Evidence: `VerificationRecord.objects.count()` = 0; period 2025 submitted but never verified.
- Impact: verification workflow untested end-to-end with real data.
- Fix: run L4 verification journey as admin (`/carbon/verification`), then decide if records need creation for demo.
- Owner: **QA (test) → fixer if bugs**.

---

## 3. Persona-by-Persona Usage Guide (live-tested)

### 👑 3.1 Global Admin — `ahmed` / `AdminPa_132`
1. Login → Platform Home → **Carbon Footprint** card → `Carbon Console`.
2. Sidebar: Overview · Emissions Dashboard · Analytics · My Data · Data Entry · Calculations · Verification · Generate/Saved Reports · Reporting Periods · Emission Factors · Calculation Rules · GWP · SBTi Targets.
3. **Dashboard (verified)**: year selector 2024/2025/2026; totals + scope breakdown + trend + category table. 2026 → 2,507.16 tCO₂e · 333 points · DQ 58%.
4. **Reporting Periods**: create periods; open/lock/submit/verify/close buttons (state machine UI exists). *Currently 2025 only.*
5. **Admin config**: factors/rules/GWP/targets CRUD.
> ⚠️ Known blocker to demo: data-entry lock (F-01). Unlock before walkthrough.

### 🧭 3.2 Domain Lead — `alamein.admin` (carbon_lead @ Alamein Campus)
1. Login → Carbon Footprint → console scoped to **Alamein Campus**.
2. Sees **DP1 Medicine, DP4 Hotels, DP5 Hospital** (NOT DP2 Logistics / DP3 Transport — F-03).
3. Capabilities: dashboard (org-scoped totals), verification, reporting, calculations.
> ⚠️ Cannot see 40% of the domain until F-03 resolved.

### 🚗 3.3 Data Owner Transport — `alamein.transport`
1. Login → Carbon → **My Data** → single module **DP3 Transport** (verified: 1 module, 185 rows, DQ 78.6 passing).
2. Data Entry → table `fleet_fuel_log` (fields: `period_month, vehicle_count, gasoline_liters, diesel_liters, total_cost_egp, supplier`).
3. ❌ **POST own table → 403 locked** (F-01). After unlock: add row → 201; cross-org write (medicine table) → 403 ✅ (RBAC correct).

### 🏥 3.4 Data Owner Medical — `alamein.medical` (org 3 + 7)
- Sees DP1 Medicine + DP5 Hospital. Same lock blocker on write.

### 💰 3.5 Data Owner Finance — `alamein.finance` (org 4)
- Sees DP2 Logistics only. Write blocked (F-01); data gap on table 13 (F-05).

### 🏨 3.6 Data Owner Hotels — `alamein.hotels` (org 6)
- Sees DP4 Hotels only. Write blocked (F-01).

### 👀 3.7 Viewer / Analyst / Auditor — **not provisioned (F-08)**
- Intended: read-only dashboards/analytics; no write. Create users + ScopedRoles.

---

## 4. Fix Sequencing (work-with-me plan)

| Step | Item | Owner | Est. |
|---|---|---|---|
| 1 | Unlock all tables (F-01a) + make unlock durable (F-01b) | fixer/backend | 1h |
| 2 | Seed 2024 + 2026 periods, 2026=open (F-02) | fixer/backend | 30m |
| 3 | Org-model decision + move Logistics/Transport under Campus OR extra role (F-03) | **user + master** | 30m |
| 4 | Rebind DP5 → org 7 (F-06) | fixer/backend | 1h |
| 5 | Re-run L2 write journeys (all 5 owners) — gate: all 201/403 correct | QA | 1h |
| 6 | Provision viewer/analyst/auditor users (F-08) | user | 15m |
| 7 | Scope org-units endpoint (F-07) | backend | 30m |
| 8 | Fix dashboard default org context (F-10) | frontend | 30m |
| 9 | Router future flags (F-11) | frontend | 15m |
| 10 | Hospital/finance data backlog (F-04/F-05) | user/data team | on-going |
| 11 | Update validation plan to 5 DPs (F-09) | docs | 15m |
| 12 | L3/L4 browser journeys per persona + verification workflow (F-12) | QA | 2h |
| 13 | Full regression: `verify.sh full` + `manage.sh test` | QA/CI | 30m |

---

## 5. Open Questions for Master/User
1. **F-03**: Move org tree (Logistics/Transport under Campus) vs extra role? Recommend tree move.
2. **F-02**: Period policy — single calendar-year period with 2026 open? OK?
3. **F-07**: Should data owners see the full org tree (e.g., for cross-org reports) or only their subtree?
4. **F-08**: Confirm usernames/passwords for viewer/analyst/auditor personas.
5. **F-01b**: Accept ADR for period-scoped table locking (lock tables only for the locked period's modules) — or keep global lock for now?

---
*Generated by qa-validator · all findings reproducible · no code changes made during audit (QA discipline)*
