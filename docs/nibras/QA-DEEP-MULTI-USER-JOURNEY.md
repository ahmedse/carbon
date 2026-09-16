# Nibras Deep Multi-User QA Journey Plan

**Product:** Nibras HRMS — People / My / Team only  
**Exclude:** Pulse, AI, ECF, Carbon emissions, AAST data-trust UI  
**Date:** 2026-09-16  
**Audience:** QA + Master Architect + GOFSCO UAT leads  
**Companion metrics canvas:** open beside chat in Cursor canvases (`nibras-deep-qa-plan.canvas.tsx`)  
**Baseline:** NSR W0–W9 product **READY** · Playwright UI leave journey ops residual · Path H Attendance/Rotation **N/A**

---

## 0. How to run this plan

1. Seed per [`GOFSCO-ONBOARDING-RUNBOOK.md`](GOFSCO-ONBOARDING-RUNBOOK.md) on a **dedicated** nibras DB (`DJANGO_BRAND=nibras`).
2. Assign managers (import does **not** set `Employee.manager`) → re-run `link_employee_users`.
3. Cast personas (Section 2) — minimum **8 named humans**, recommended **15+** for concurrency.
4. Execute **Wave U0 → U7** (Section 10). Log every case in the scorecard (Section 11).
5. Compute **all metrics** (Section 1). Exit only when **Exit Criteria** (Section 12) pass.

**Ports:** FE `http://localhost:5179` · BE `http://localhost:8009` · API `/carbon-api/`

**Evidence folder:** `docs/nibras/evidence/deep-qa/<YYYY-MM-DD>/`  
Store: screenshots, JWT curl transcripts, pytest/vitest/playwright logs, metric CSV.

---

## 1. Metrics catalog (measure everything)

Record each metric after every wave and at final gate. Formula → target → evidence source.

### 1.1 Coverage & execution

| ID | Metric | Formula | Target | Source |
|----|--------|---------|--------|--------|
| M-COV-01 | Case execution rate | executed / planned cases | ≥ 95% | Scorecard |
| M-COV-02 | P0 case pass rate | P0 pass / P0 executed | **100%** | Scorecard |
| M-COV-03 | P1 case pass rate | P1 pass / P1 executed | ≥ 95% | Scorecard |
| M-COV-04 | Persona coverage | personas with ≥1 full journey / cast size | **100%** of cast | Cast log |
| M-COV-05 | Domain coverage | domains with ≥1 P0 green / 12 domains | **12/12** | Domain map §3 |
| M-COV-06 | Edge-case density | edge cases executed / edge catalog | ≥ 85% | §5–§8 |
| M-COV-07 | Automation corroboration | automated green / critical journeys | ≥ 90% | pytest/vitest/PW |
| M-COV-08 | Manual-only residual | manual-only P0s still open | **0** | Scorecard |

### 1.2 Journey outcome (happy path)

| ID | Metric | Formula | Target | Source |
|----|--------|---------|--------|--------|
| M-J-01 | Leave request→approve loop success | loops OK / attempts | ≥ 98% | My→Team→balance |
| M-J-02 | Leave reject loop correctness | reject→status rejected + balance unused | **100%** | Corr + LeaveRecord |
| M-J-03 | Leave send-back→resubmit success | resubmit→pending again | ≥ 95% | Corr events |
| M-J-04 | Leave cancel by requestor | cancel→cancelled; balance freed | **100%** | me/leave + corr |
| M-J-05 | Loan mgr→finance approve → installments | loans with schedule / approved loans | **100%** | loan-installments |
| M-J-06 | Profile-change apply precision | allowlisted fields applied; forbidden ignored | **100%** | Employee GET |
| M-J-07 | Hire→entitlement presence | new hires with ≥1 entitlement (when join_date+policy match) | ≥ 95% | leave-entitlements |
| M-J-08 | Payroll compute fail-closed | compute fails when no verified ledger / attempts | **100%** | payroll-runs/compute |
| M-J-09 | Payroll compute success w/ ledger | success when verified monthly line exists | ≥ 98% | compute→commit |
| M-J-10 | WPS export after commit | wps downloadable / committed runs | ≥ 95% | …/wps/ |
| M-J-11 | Multi-step loan finance gate | finance cannot act before manager; after manager can | **100%** | corr policy steps |
| M-J-12 | Cross-app consistency D-loop | My status = Team = People LeaveRecord | **100%** sampled | 3-way GET |

### 1.3 Balance & money invariants

| ID | Metric | Formula | Target | Source |
|----|--------|---------|--------|--------|
| M-BAL-01 | Leave conservation | entitled + carried − used − pending = remaining (±0.01) | **100%** of balances checked | me/leave-balance |
| M-BAL-02 | Pending does not inflate used | after submit, used unchanged; pending ↑ | **100%** | before/after |
| M-BAL-03 | Approve moves pending→used | Δused = days; pending ↓ | **100%** | journey samples |
| M-BAL-04 | Over-balance reject rate | requests > remaining → 4xx / attempts | **100%** | POST me/leave |
| M-BAL-05 | Loan installment sum | Σ installment.amount = principal (±0.005) | **100%** | installments |
| M-BAL-06 | Loan schedule count | installment count = tenure months (policy) | **100%** | materialize |
| M-BAL-07 | Idempotent rematerialize | 2nd materialize creates 0 new rows | **100%** | re-approve / re-run |
| M-BAL-08 | Payslip net identity | net = gross − deductions (±0.005) | ≥ 99% lines | payslip-lines |
| M-BAL-09 | Ledger vs payslip basic | committed basic matches verified ledger | **100%** | payroll + compensation |
| M-BAL-10 | Opening_basic unverified | hire opening line `verified=False` until HR verify | **100%** | compensation lines |

### 1.4 Security / CBAC / tenancy

| ID | Metric | Formula | Target | Source |
|----|--------|---------|--------|--------|
| M-SEC-01 | Unauthenticated deny | 401 on people/me/team/corr matrix | **100%** | curl matrix |
| M-SEC-02 | No-capability deny | 403 on people admin without cap | **100%** | test user |
| M-SEC-03 | Me isolation | emp A never sees emp B leave/loan/payslip | **100%** | cross-GET |
| M-SEC-04 | Team inbox isolation | manager sees only actionable / reports | **100%** | inbox vs reports |
| M-SEC-05 | Org-scope isolation | people:view user only sees own org subtree | **100%** | employees list |
| M-SEC-06 | Compensation hide | without view_compensation, amounts redacted/forbidden | **100%** | Pay tab / API |
| M-SEC-07 | Profile allowlist integrity | forbidden fields never applied | **100%** | §5.5 negatives |
| M-SEC-08 | Single-root org | active parent=None count = 1 | **1** | ORM check |
| M-SEC-09 | Seed instance gate | wrong brand seed → CommandError | **100%** | smoke |
| M-SEC-10 | Foreign org unit absent | picker never lists non-deployment units | **100%** | FE + API |

### 1.5 Governance / reference data

| ID | Metric | Formula | Target | Source |
|----|--------|---------|--------|--------|
| M-GOV-01 | Governed write accept | valid code/id on FK fields → 2xx | ≥ 99% | wizard/API |
| M-GOV-02 | Governed write reject | invalid code → 400 | **100%** | negative matrix |
| M-GOV-03 | No soft `*_code` write | Employee create/update rejects or ignores legacy keys | **100%** | payload audit |
| M-GOV-04 | Nested read shape | Bucket-1 fields return `{id,code,label,set}` or null | ≥ 99% | GET samples |
| M-GOV-05 | PROTECT on delete | deleting in-use ReferenceValue blocked | **100%** | admin attempt |
| M-GOV-06 | Ref set completeness | 7 NSR-7A sets present + leave_type + nationality… | checklist | shell count |

### 1.6 Policy / Kuwait / compliance

| ID | Metric | Formula | Target | Source |
|----|--------|---------|--------|--------|
| M-POL-01 | Kuwaitization annual days | KW staff annual entitled matches policy (e.g. 42 vs 30) | **100%** sampled | entitlements |
| M-POL-02 | Rotation-scoped leave | only matching rotation employees get policy | **100%** | propagate |
| M-POL-03 | Version immutability | published version snapshot stable after edit | **100%** | versions API |
| M-POL-04 | Propagate idempotency | 2nd propagate does not duplicate entitlements | **100%** | counts |
| M-POL-05 | EOSI numeric | eosi endpoint returns number for active expat/kw | ≥ 95% | …/eosi/ |
| M-POL-06 | Authoritative rules present | seeded KLL/PIFSS/WPS rules is_authoritative | checklist | compliance-rules |

### 1.7 UX / FE integrity (staff)

| ID | Metric | Formula | Target | Source |
|----|--------|---------|--------|--------|
| M-UX-01 | Path H nav absence | Attendance + Rotation absent from People nav & home | **100%** | visual + PeoplePages |
| M-UX-02 | Org picker tree order | parents before children; labels indented/full_path | ≥ 95% checks | People pickers |
| M-UX-03 | Breadcrumb honesty | People/My/Team trails match ROUTE_CONFIG | ≥ 95% | spot pages |
| M-UX-04 | i18n EN/AR parity | critical strings present both langs | ≥ 98% keys touched | i18n audit |
| M-UX-05 | Empty/loading/error states | grids show four states, no blank crash | ≥ 95% pages | visual |
| M-UX-06 | Salary honesty copy | Pay UI does not invent basic from Employee.basic_salary | **100%** | Pay tab |

### 1.8 Reliability / concurrency / ops

| ID | Metric | Formula | Target | Source |
|----|--------|---------|--------|--------|
| M-REL-01 | Concurrent leave submit | N employees submit same minute; all consistent | ≥ 95% | §7 |
| M-REL-02 | Double-approve safe | 2nd approve is no-op or 4xx; no double used days | **100%** | race script |
| M-REL-03 | Double-compute safe | recompute draft does not duplicate payslip lines wrongly | policy-defined | payroll |
| M-REL-04 | Session expiry | expired JWT → re-login; no silent 500 | **100%** | manual |
| M-REL-05 | FE build | `npm run build` | PASS | CI/local |
| M-REL-06 | people pytest | full `people/tests/` | PASS (baseline 228+) | pytest |
| M-REL-07 | Vitest staff pack | 6 files (MyLeave, TeamInbox, Wizard, PeoplePages, MyLoans, OrgUnitScope) | PASS | vitest |
| M-REL-08 | Playwright leave UI | nibras-leave-approve green on seeded stack | PASS (ops) | PW |

### 1.9 Volume / scale (GOFSCO cohort)

| ID | Metric | Formula | Target | Source |
|----|--------|---------|--------|--------|
| M-VOL-01 | Linked users | emp_* with my:access / imported headcount | ≥ 98% | link command |
| M-VOL-02 | Managers with team:access | managers with ≥1 report / managers intended | **100%** | CBAC derive |
| M-VOL-03 | Employees with join_date | non-null join_date / headcount | ≥ 90% UAT cohort | SQL |
| M-VOL-04 | Employees with entitlements | with ≥1 entitlement / active with join_date | ≥ 90% | SQL |
| M-VOL-05 | Org units under single root | all active OU descendant of deployment root | **100%** | get_deployment_root |
| M-VOL-06 | Payroll cohort size | employees in run org subtree | logged | payroll run |

**Metric rollup score:**  
`GateScore = weighted(M-COV-02×5 + M-J-*×3 + M-BAL-*×4 + M-SEC-*×5 + M-GOV-*×3 + M-REL-05..07×2)`  
Declare **UAT PASS** only if P0 metrics (bold targets at 100%) all hit.

---

## 2. Persona cast (many users)

Assign real `emp_<no>` after import. Keep a **Cast sheet** (name, employee_no, org, manager, kuwaitization, rotation, caps).

| Cast ID | Persona | Caps needed | Org suggestion | Must exercise |
|---------|---------|-------------|----------------|---------------|
| U-EMP-A | Field employee ESS | my:access, correspondence:submit | Drilling / CT | Leave, loan, profile-change, payslips |
| U-EMP-B | Office employee ESS | same | FIN or HR | Leave + profile |
| U-EMP-C | Kuwaiti national | same + kuwaitization=True | any | Policy day counts |
| U-EMP-D | Expat | kuwaitization=False | Operations Crew | EOSI + annual days |
| U-EMP-E | Rotation worker | rotation set (e.g. 2/1) | Yard/Store | Rotation-scoped leave |
| U-EMP-F | Zero-balance edge | join_date null or no policy | any | Leave reject / empty UI |
| U-EMP-G | Inactive employee | is_active=False | any | me API fail-closed |
| U-MGR-1 | Line manager | + team:access, correspondence:act | reports A/B/E | Inbox approve/reject/send-back |
| U-MGR-2 | Second manager | same | other division | Isolation vs MGR-1 |
| U-FIN-1 | Finance approver | correspondence:finance (+ my) | FIN | Loan step-2 |
| U-HR-1 | People lead | people:manage, correspondence:admin | HR | Hire, policy, payroll, config |
| U-HR-2 | People analyst | people:view (no manage) | HR | Read-only; 403 on compute/config write |
| U-PAY-1 | Payroll operator | people:manage (+ compensation view) | FIN/HR | Ledger verify → compute → WPS |
| U-ADM-1 | Global admin | `*` / ahmed | — | Break-glass only; not daily path |
| U-NEG-1 | No-cap user | JWT only, no people/my/team | — | 401/403 matrix |

**Minimum cast for Wave U1:** EMP-A, EMP-C, MGR-1, FIN-1, HR-1, NEG-1 (6).  
**Full deep run:** all 15.

### Manager wiring checklist (blocking)

- [ ] `Employee.manager_id` set for every ESS user who will request leave/loan  
- [ ] `link_employee_users` re-run after manager changes  
- [ ] MGR-1 can open `/team` and see ≥1 actionable item after EMP-A submits  
- [ ] MGR-2 never sees EMP-A items unless in chain  

---

## 3. Domain map (12 domains)

| # | Domain | Primary apps | P0? |
|---|--------|--------------|-----|
| D01 | Auth & session | all | Y |
| D02 | Org & positions | People | Y |
| D03 | Employee lifecycle | People | Y |
| D04 | Leave policy & entitlements | People | Y |
| D05 | Leave request & approval | My + Team + People | Y |
| D06 | Loans & installments | My + Team + People | Y |
| D07 | Profile change | My + Team + People | Y |
| D08 | Compensation ledger & pay | People | Y |
| D09 | Payroll run & WPS | People | Y |
| D10 | Certifications | People | P1 |
| D11 | Compliance / EOSI | People | P1 |
| D12 | CBAC / isolation / Path H | all | Y |

---

## 4. Environment gates (before journeys)

| Gate | Check | PASS |
|------|-------|------|
| G0 | `DJANGO_BRAND=nibras`, dedicated DB | settings + DB name |
| G1 | `OrgUnit` active roots = 1 (`parent=None`) | ORM count == 1 |
| G2 | `seed_gofsco_org` + rules + correspondence done | runbook § |
| G3 | Employees imported (not `seed_gofsco`) | headcount > 0 |
| G4 | `link_employee_users` done | emp_* login works |
| G5 | Managers wired | Team inbox non-empty after test submit |
| G6 | ReferenceSets: grade, loan_type, cert_type, … + leave_type | count checks |
| G7 | FE :5179 + BE :8009 healthy | curl 200 |
| G8 | Path H: Attendance/Rotation **not** in nav | visual |

---

## 5. Journey catalog — deep cases by domain

Legend: **P0** must pass · **P1** should pass · **P2** nice · **NEG** negative · **EDGE** edge · **CONC** concurrency · **MULTI** multi-user

### 5.1 D01 — Auth & session

| ID | Pri | Type | Actors | Steps (short) | Expected | Metric |
|----|-----|------|--------|---------------|----------|--------|
| J-AUTH-01 | P0 | — | NEG-1 | Login invalid password | 401; no token | M-SEC-01 |
| J-AUTH-02 | P0 | — | EMP-A | Login valid → My | `/my` loads profile | M-J |
| J-AUTH-03 | P0 | NEG | EMP-A | Call people employees list | 403 without people:view | M-SEC-02 |
| J-AUTH-04 | P1 | EDGE | EMP-A | Expire/remove token mid-session | forced re-auth | M-REL-04 |
| J-AUTH-05 | P0 | — | all | Unauthenticated GET me/leave/inbox | 401 matrix | M-SEC-01 |

### 5.2 D02 — Org & positions

| ID | Pri | Type | Actors | Steps | Expected | Metric |
|----|-----|------|--------|-------|----------|--------|
| J-ORG-01 | P0 | — | HR-1 | List org units in wizard | Only deployment subtree; tree order | M-SEC-10, M-UX-02 |
| J-ORG-02 | P0 | NEG | HR-1 / ADM | Attempt second active root | ValidationError / 400 | M-SEC-08 |
| J-ORG-03 | P0 | — | HR-1 | Create Position grade+job_family via governed values | Nested read OK | M-GOV-01/04 |
| J-ORG-04 | P1 | EDGE | HR-1 | Position with blank grade | Allowed if optional; null nested | M-GOV |
| J-ORG-05 | P1 | — | HR-2 | Positions list read-only | GET OK; POST 403 | M-SEC-02 |

### 5.3 D03 — Employee lifecycle

| ID | Pri | Type | Actors | Steps | Expected | Metric |
|----|-----|------|--------|-------|----------|--------|
| J-EMP-01 | P0 | — | HR-1 | Wizard hire: org, join_date, governed nationality/employment/contract/gender/rotation, opening_basic | Employee created; entitlements if policy match; opening ledger **unverified** | M-J-07, M-BAL-10 |
| J-EMP-02 | P0 | NEG | HR-1 | Wizard payload with `nationality_code` | Must not rely on soft key; use `nationality` code | M-GOV-03 |
| J-EMP-03 | P0 | NEG | HR-1 | Invalid nationality code | 400 | M-GOV-02 |
| J-EMP-04 | P0 | — | HR-1 | Deactivate EMP then login as EMP | me fail-closed | M-SEC |
| J-EMP-05 | P0 | — | HR-1 | Reactivate | ESS restored | — |
| J-EMP-06 | P1 | EDGE | HR-1 | Hire without join_date | Zero/empty entitlements; UI honest | M-VOL-03 |
| J-EMP-07 | P1 | EDGE | HR-1 | Hire KW vs expat same day | Different annual entitlements after propagate | M-POL-01 |
| J-EMP-08 | P1 | MULTI | HR-1, EMP-A | Set manager EMP-A→MGR-1; EMP requests leave | Appears in MGR-1 inbox only | M-SEC-04 |
| J-EMP-09 | P2 | — | HR-1 | Timeline events after hire/edit | chronicle entries | — |

### 5.4 D04 — Leave policy & entitlements

| ID | Pri | Type | Actors | Steps | Expected | Metric |
|----|-----|------|--------|-------|----------|--------|
| J-POL-01 | P0 | — | HR-1 | Create/edit leave policy + version | versions ≥2; snapshot frozen | M-POL-03 |
| J-POL-02 | P0 | — | HR-1 | Propagate | Entitlements for in-scope only | M-POL-02 |
| J-POL-03 | P0 | — | HR-1 | Propagate twice | No duplicate unique (emp,year,type) | M-POL-04 |
| J-POL-04 | P0 | EDGE | HR-1 | Policy applies_to_kuwaitization=True | Only KW get days | M-POL-01 |
| J-POL-05 | P1 | EDGE | HR-1 | Policy applies_to_rotations=['2/1'] | Only 2/1 employees | M-POL-02 |
| J-POL-06 | P1 | EDGE | HR-1 | Contract-type scoped policy | Out-of-scope emp gets 0 | — |
| J-POL-07 | P2 | — | HR-2 | Propagate without manage | 403 | M-SEC-02 |

### 5.5 D05 — Leave request & approval (core multi-user)

| ID | Pri | Type | Actors | Steps | Expected | Metric |
|----|-----|------|--------|-------|----------|--------|
| J-LV-01 | P0 | MULTI | EMP-A → MGR-1 | Balance → request N days → Team approve → balance | pending↑ then used↑; LeaveRecord approved; corr approved | M-J-01, M-BAL-01..03, M-J-12 |
| J-LV-02 | P0 | MULTI | EMP-A → MGR-1 | Request → reject | rejected; used unchanged; remaining restored | M-J-02 |
| J-LV-03 | P0 | MULTI | EMP-A → MGR-1 | Request → send-back → edit → resubmit → approve | events chain correct | M-J-03 |
| J-LV-04 | P0 | — | EMP-A | Request → cancel before approve | cancelled; pending cleared | M-J-04 |
| J-LV-05 | P0 | NEG | EMP-A | Request days > remaining | 400; no corr or failed closed | M-BAL-04 |
| J-LV-06 | P0 | NEG | EMP-A | Overlapping dates with existing approved | 400 or policy reject | EDGE |
| J-LV-07 | P0 | NEG | EMP-B | Approve own request via corr API | 403 | M-SEC-04 |
| J-LV-08 | P0 | NEG | MGR-2 | Approve EMP-A item | 403 / not in inbox | M-SEC-04 |
| J-LV-09 | P1 | EDGE | EMP-A | Sick vs annual type | Correct leave_type FK nested | M-GOV-04 |
| J-LV-10 | P1 | EDGE | EMP-F | No entitlement | Honest empty; cannot submit | M-UX-05 |
| J-LV-11 | P0 | CONC | EMP-A | Double-click approve (MGR) | No double used days | M-REL-02 |
| J-LV-12 | P1 | CONC | EMP-A,B,C | 3 parallel leave submits | All consistent balances | M-REL-01 |
| J-LV-13 | P1 | MULTI | EMP-A → MGR-1 → HR | If multi-step leave policy | Each step gates next | M-J-11 analog |
| J-LV-14 | P0 | — | EMP-A | My Requests detail timeline | Events match actions | — |
| J-LV-15 | P1 | — | HR-1 | People Leave grid shows approved record | Same id/status as My | M-J-12 |

### 5.6 D06 — Loans & installments

| ID | Pri | Type | Actors | Steps | Expected | Metric |
|----|-----|------|--------|-------|----------|--------|
| J-LN-01 | P0 | MULTI | EMP-A → MGR-1 → FIN-1 | Loan request → mgr approve → finance approve | Loan active; installments materialized | M-J-05, M-BAL-05/06 |
| J-LN-02 | P0 | NEG | FIN-1 | Act before manager step | 403 / not actionable | M-J-11 |
| J-LN-03 | P0 | — | EMP-A | My loans list nested loan_type label | Display label not `[object]` | M-UX |
| J-LN-04 | P0 | — | HR-1 | People Loans + installments grid | Matches My | M-J-12 |
| J-LN-05 | P0 | EDGE | HR-1 / system | Re-trigger materialize | Idempotent; same count | M-BAL-07 |
| J-LN-06 | P1 | NEG | EMP-A | Invalid loan_type code | 400 | M-GOV-02 |
| J-LN-07 | P1 | MULTI | EMP-A → MGR-1 | Reject at manager | Loan cancelled; 0 installments | M-J-02 analog |
| J-LN-08 | P1 | EDGE | EMP-A | Principal 0 or negative | 400 | — |
| J-LN-09 | P2 | EDGE | EMP-A | Very long tenure | Schedule length matches policy | M-BAL-06 |

### 5.7 D07 — Profile change

| ID | Pri | Type | Actors | Steps | Expected | Metric |
|----|-----|------|--------|-------|----------|--------|
| J-PC-01 | P0 | MULTI | EMP-A → MGR-1 | Change name_en_* + nationality → approve | Fields applied on Employee | M-J-06 |
| J-PC-02 | P0 | NEG | EMP-A → MGR-1 | Payload includes basic_salary, org_unit, manager, civil_id, kuwaitization | **Ignored** on apply | M-SEC-07 |
| J-PC-03 | P0 | — | EMP-A | Reject profile change | Employee unchanged | — |
| J-PC-04 | P1 | EDGE | EMP-A | Gender/nationality as governed codes | Nested after apply | M-GOV-04 |
| J-PC-05 | P1 | EDGE | EMP-A | Empty change set | 400 or no-op | — |

### 5.8 D08 — Compensation ledger & pay honesty

| ID | Pri | Type | Actors | Steps | Expected | Metric |
|----|-----|------|--------|-------|----------|--------|
| J-CB-01 | P0 | — | PAY-1 | View Pay tab before verify | Shows unverified / no fake basic | M-UX-06 |
| J-CB-02 | P0 | — | PAY-1 | Verify opening_basic line | verified=True | M-BAL-10 |
| J-CB-03 | P0 | NEG | HR-2 | Verify without manage/comp | 403 | M-SEC-06 |
| J-CB-04 | P1 | — | PAY-1 | Add compensation component + plan row | Create OK (POST-only) | residual note |
| J-CB-05 | P1 | EDGE | PAY-1 | Two overlapping ledger lines | Service rules documented; no silent double-count | EDGE |

### 5.9 D09 — Payroll & WPS

| ID | Pri | Type | Actors | Steps | Expected | Metric |
|----|-----|------|--------|-------|----------|--------|
| J-PR-01 | P0 | NEG | PAY-1 | Compute run for emp **without** verified ledger | Fail-closed error | M-J-08 |
| J-PR-02 | P0 | — | PAY-1 | Verify ledger → compute → validate → commit | Payslip lines; status committed | M-J-09 |
| J-PR-03 | P0 | — | PAY-1 | WPS export | File parseable | M-J-10 |
| J-PR-04 | P0 | — | EMP-A | My payslips after commit | Sees own lines only | M-SEC-03 |
| J-PR-05 | P0 | NEG | EMP-B | GET EMP-A payslip by id | 404/403 | M-SEC-03 |
| J-PR-06 | P1 | EDGE | PAY-1 | Org-scoped run | Only subtree employees | M-SEC-05 |
| J-PR-07 | P1 | CONC | PAY-1 | Double compute | No corrupt duplicate nets | M-REL-03 |
| J-PR-08 | P1 | — | PAY-1 | Net identity on lines | M-BAL-08 | M-BAL-08 |
| J-PR-09 | P2 | NEG | HR-2 | Commit without manage | 403 | M-SEC-02 |

### 5.10 D10 — Certifications

| ID | Pri | Type | Actors | Steps | Expected | Metric |
|----|-----|------|--------|-------|----------|--------|
| J-CT-01 | P1 | — | HR-1 | Create cert with governed cert_type | Nested label in UI | M-GOV |
| J-CT-02 | P1 | EDGE | HR-1 | Expired cert on profile | Warning/urgency banner | M-UX |
| J-CT-03 | P2 | NEG | HR-1 | Invalid cert_type | 400 | M-GOV-02 |

### 5.11 D11 — Compliance / EOSI

| ID | Pri | Type | Actors | Steps | Expected | Metric |
|----|-----|------|--------|-------|----------|--------|
| J-EO-01 | P1 | — | HR-1 | GET eosi for EMP-D expat | Numeric | M-POL-05 |
| J-EO-02 | P1 | — | HR-1 | GET eosi for EMP-C KW | Numeric / rule path | M-POL-05 |
| J-EO-03 | P1 | — | HR-1 | Compliance rules list authoritative | Seeded present | M-POL-06 |
| J-EO-04 | P2 | EDGE | HR-1 | Compliance category/jurisdiction governed | Nested if UI wired; else API | residual |

### 5.12 D12 — CBAC, isolation, Path H

| ID | Pri | Type | Actors | Steps | Expected | Metric |
|----|-----|------|--------|-------|----------|--------|
| J-CBAC-01 | P0 | MATRIX | cast | Cap matrix appendix A | All cells match | M-SEC-* |
| J-PH-01 | P0 | NEG | HR-1 | People nav / home | No Attendance, no Rotation | M-UX-01 |
| J-PH-02 | P2 | EDGE | HR-1 | Deep-link `/people/attendance` | Unsupported; do not brief as go-live | note only |
| J-ISO-01 | P0 | MULTI | MGR-1 vs MGR-2 | Inbox contents disjoint | M-SEC-04 |
| J-ISO-02 | P0 | MULTI | EMP-A vs EMP-B | me/* isolation | M-SEC-03 |

---

## 6. End-to-end mega-scripts (run as theatre)

### Script S1 — “Monday morning leave” (4 users)
EMP-A, EMP-B, MGR-1, HR-1  
1. Both employees request leave same week (different dates).  
2. MGR-1 approves A, send-back B.  
3. B resubmits; MGR-1 approves.  
4. HR-1 confirms People Leave grid + balances.  
**Pass:** M-J-01, M-J-03, M-J-12, M-BAL-01.

### Script S2 — “Loan to payroll” (5 users)
EMP-A, MGR-1, FIN-1, PAY-1, EMP-A  
1. Loan full chain → installments.  
2. PAY-1 ensures ledger verified; payroll compute includes loan deduction line if designed.  
3. Commit + EMP-A sees payslip.  
**Pass:** M-J-05, M-J-09, M-SEC-03.  
**Note:** If loan deduction not yet in compute formula, mark **N/A formula** but installments must still exist.

### Script S3 — “New joiner first 48h” (3 users)
HR-1, new EMP, MGR-1  
1. Hire with opening_basic + join_date + manager.  
2. Propagate if needed; link user.  
3. EMP requests leave (if entitled); MGR approves.  
4. PAY verifies ledger; payroll dry-run compute.  
**Pass:** M-J-07, M-BAL-10, M-J-08/09.

### Script S4 — “Forbidden profile heist” (2 users)
EMP-A, MGR-1  
1. EMP submits profile_change with salary+org+manager spoof.  
2. MGR approves.  
3. Assert Employee salary/org/manager **unchanged**; names updated.  
**Pass:** M-SEC-07 **100%**.

### Script S5 — “Wrong org / wrong brand” (ops)
ADM + shell  
1. `DJANGO_BRAND=aastmt seed_gofsco_org` → CommandError.  
2. Confirm single root.  
3. Confirm FE org picker has no foreign tree.  
**Pass:** M-SEC-08/09/10.

### Script S6 — “Stress hour” (10+ users)
N employees submit leave; 2 managers approve/reject mix; 1 HR watches grids.  
**Pass:** M-REL-01 ≥95%; zero balance drift (M-BAL-01).

---

## 7. Concurrency & race protocol

| Race | Method | Pass |
|------|--------|------|
| Double approve | Two browsers same corr approve | One success; used days = once |
| Approve + cancel race | EMP cancel while MGR approves | Terminal state consistent; no partial used |
| Dual submit overlap | Two leave POSTs overlapping dates | At most one accepted |
| Dual payroll compute | Two compute clicks | Payslip lines coherent |
| Dual propagate | Two propagate | No duplicate entitlements |

Automate where possible with pytest; else two humans + stopwatch.

---

## 8. Negative matrix (must be red)

| Surface | Attack | Expected |
|---------|--------|----------|
| me/leave | other employee_id in body | ignored / 403 |
| me/payslips | enumerate ids | only own |
| correspondence/approve | non-approver | 403 |
| employees POST | analyst | 403 |
| payroll compute | missing ledger | 4xx business error |
| governed FK | garbage code | 400 |
| profile apply | salary field | ignored |
| seed | wrong brand | CommandError |
| OrgUnit | second root | ValidationError |

---

## 9. Path H & explicit non-goals

**Do not** fail UAT for:

- Attendance UI / Rotation UI missing from nav (required hidden)
- Attendance→OT→payroll timesheet drivers
- Pulse coworker journeys
- HR Reporting module / GOFSCO catalog #7–8 not built
- Admin OrgUnitsPage flat list (People pickers are in scope)

**Do** record as residuals (non-blocking unless P0 elsewhere):

- CompensationPlan soft `*_code` fields  
- ComplianceRule UI governed lag  
- My NewRequestDialog loan_type free-text  
- Playwright host libs / seed for UI E2E  

---

## 10. Execution waves

| Wave | Focus | Cast | Exit |
|------|-------|------|------|
| **U0** | Env gates G0–G8 + metric sheet blank | Ops + HR-1 | All gates PASS |
| **U1** | Auth + CBAC + Path H + Me isolation | EMP-A, MGR-1, HR-2, NEG-1 | M-SEC-01..06, M-UX-01 |
| **U2** | Leave full theatre S1 + edges J-LV-* | EMP-A/B/C, MGR-1/2, HR-1 | M-J-01..04, M-BAL-01..04 |
| **U3** | Loan S2 + finance gate | + FIN-1, PAY-1 | M-J-05/11, M-BAL-05..07 |
| **U4** | Profile allowlist S4 | EMP-A, MGR-1 | M-SEC-07, M-J-06 |
| **U5** | Hire + ledger + payroll S3 | HR-1, PAY-1, new EMP | M-J-07..10 |
| **U6** | Policy KW/rotation + EOSI + certs | HR-1, EMP-C/D/E | M-POL-* |
| **U7** | Concurrency S6 + mega regression + metrics rollup | Full cast | GateScore + Exit §12 |

Parallelism: U2/U3/U4 can run on separate cohorts after U1 green.

---

## 11. Scorecard template

Copy per run:

```
Run ID: NIBRAS-DEEP-YYYYMMDD
Cast size: __
Cases planned: __
Cases executed: __
P0 pass/fail: __ / __
P1 pass/fail: __ / __
Blockers (P0):
  -
Metrics JSON/CSV: docs/nibras/evidence/deep-qa/.../metrics.csv
Sign-off QA: ________  Master: ________
```

Case row columns: `ID | Pri | Result | Actor(s) | Evidence path | Metric IDs | Notes`

---

## 12. Exit criteria (UAT sign-off)

**PASS (staff deep UAT complete)** when all true:

1. M-COV-02 = 100% (all P0 cases)  
2. All **100% target** metrics in §1.2–1.5 that were in scope are green  
3. Scripts S1, S3, S4, S5 PASS; S2 PASS or documented N/A on deduction formula only  
4. `people/tests/` green; vitest staff pack green; `npm run build` green  
5. Playwright leave UI PASS **or** explicit Master waiver with API journey green + ops ticket  
6. Path H confirmed hidden  
7. No open product P0; residuals listed with owners  

**FAIL / BLOCKED** if any P0 metric misses or balance/money invariant breaks.

---

## 13. Automation map (don’t re-test blind)

| Journey | Prefer automation | Manual still needed |
|---------|-------------------|---------------------|
| Leave approve loop | `test_leave_journey_e2e.py` + PW `nibras-leave-approve` | Multi-browser race |
| Hire entitlements | `test_employee_onboard.py` | Wizard UX governed dropdowns |
| Payroll ledger SoT | `test_payroll_service.py` | WPS file open in Excel |
| Loan installments | `test_loan_installments.py` | Finance persona UI |
| Profile allowlist | `test_profile_change_apply.py` | Spoof field UX |
| CBAC | `test_cbac.py`, `test_api.py` | Real JWT users |
| Org root | `test_org_unit_root.py` | FE picker visual |
| Path H | `PeoplePages` / `PeopleManifest` vitest | Visual nav |

---

## 14. Appendix A — CBAC expectation matrix

| Cap / action | EMP | MGR | FIN | HR manage | Analyst | None |
|--------------|-----|-----|-----|-----------|---------|------|
| GET me/* | Y | Y | Y | Y | Y | N |
| POST me/leave | Y | Y | Y | Y | Y | N |
| GET correspondence/inbox | N* | Y | Y** | Y | N* | N |
| POST approve (as approver) | N | Y | Y** | Y | N | N |
| GET employees | N | N | N | Y | Y | N |
| POST employees | N | N | N | Y | N | N |
| payroll compute | N | N | N | Y | N | N |
| people config write | N | N | N | Y | N | N |

\* unless derived team:access from reports / pending approver  
\*\* finance step only when policy says so  

---

## 15. Appendix B — Suggested metrics.csv header

```csv
run_id,metric_id,value,target,pass,wave,notes,evidence_uri
```

---

## 16. Related docs

- [`GOFSCO-ONBOARDING-RUNBOOK.md`](GOFSCO-ONBOARDING-RUNBOOK.md)  
- [`../QA-MANUAL-PEOPLE-MY-TEAM.md`](../QA-MANUAL-PEOPLE-MY-TEAM.md) — shorter manual checklist (A/B/C/D)  
- [`evidence/NSR-9-go-live-gate.md`](evidence/NSR-9-go-live-gate.md) — automation baseline  
- ADRs 0027 (governed FK), 0028 (single-root), 0029 (ledger payroll), 0030 (as applicable)  

---

*End of deep multi-user QA journey plan. This is the execution bible for many-user Nibras staff UAT — not Pulse.*
