# TASKS — Carbon Master Task List (ACTIVE)

**This is the SINGLE SOURCE OF TRUTH for outstanding work.** One worker task =
one phase entry = one Worker Role. No phase spans both backend and frontend.

> **History (DONE phases):** archived at
> [`docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md`](docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md)
> (~12k lines). Do not re-copy DONE specs into this file.
>
> **Results history:** [`docs/_archive/tasks-history/TASK-RESULTS-FULL-2026-09-16.md`](docs/_archive/tasks-history/TASK-RESULTS-FULL-2026-09-16.md)
>
> **Sprint specs:** [`docs/_archive/sprints/`](docs/_archive/sprints/)

**Status legend:** `DONE` = verified + shipped · `READY` = spec complete, dispatchable · `PLANNED` = sequenced, spec pending · `PROPOSAL` = unratified, do not dispatch · `AUDIT` = code/ADR may already exist — confirm before dispatch.

**Phase-name uniqueness:** before adding a new phase id, grep **both** this file and the archive — phase IDs are never reused.

---

## MASTER DIRECTIVE — Test Partitioning (NON-NEGOTIABLE)

Full-suite `pytest` + `pytest-xdist -n auto` spawns parallel Postgres test DBs and
**hangs the dev laptop**. xdist flags are REMOVED from `backend/pytest.ini` and MUST
NOT be re-added. Every worker MUST follow:

- **Backend:** one app at a time, never full suite:
  `python -m pytest <app> -q --maxfail=5 --disable-warnings -p no:cacheprovider`
  (e.g. `pytest ai -q`, `pytest catalog -q`, `pytest integrations -q`).
  Max 2 apps in one invocation, and only the changed app + direct dependents.
- **Frontend:** one spec file at a time, never whole suite:
  `npx vitest run src/__tests__/<file>.test.jsx`; build **once per phase**
  (`npm run build`), not per file.
- **E2E:** only when a journey changed, one spec at a time (`npx playwright test e2e/journeys/<file>`).
- **NEVER:** `pytest` with no args · `-n auto`/`--dist loadscope`/xdist · `npx vitest run` with no path.
- Stale-test-DB cleanup (only if `test_carbon*` DBs linger): see `.ai-toolkit/shared/testing.md` RULE 7.

**Frontend completion is PROVEN, not claimed:** a frontend phase is `DONE` only
when `npm run lint` + a targeted `vitest` + `npm run build` all pass. No build/test
evidence → not done.

---

## Active focus (2026-09)

| Track | Owner | Status | Notes |
|-------|-------|--------|-------|
| **MOB** (Mobile-friendly FE, ADR-0035) | **Pulse + Nibras** | **READY→DONE** | Spec `docs/mobile/SCREEN-SPECS-MOB.md` · A–E implemented 2026-09-17 · build+vitest green |
| **ECF** (Entity Capability Framework, ADR-0032) | **Pulse** | **COMPLETE** | ECF-8 DONE — LeaveRecord descriptor-only generalize proof |
| **PEC** (Pulse Enterprise Control-plane) | **Pulse** | COMPLETE | Core P1–P7 closed |
| **PEC-R** (Pulse residuals) | **Pulse** | **COMPLETE** | R4 journey-16 **3/3 PASS** · R5–R7 · leave fetch |
| **Pulse Chat QA** | **Pulse** | **ACTIVE** | Deep journey ~**86%** · **GOFSCO clarify-loop CLOSED** (530 headcount) · open PARTIAL: B1/B5/C1/C7 |
| **NSR** (Nibras Staff-Ready) | **Nibras** | **COMPLETE** | Staff go-live **READY**; Playwright leave UI **3/3 PASS** 2026-09-21 — `docs/nibras/evidence/NSR-9-go-live-gate.md` |
| **Nibras Deep QA** | **Nibras** | **COMPLETE** | **P0 46/46** · all-case **81/81** · J-EMP-06 fixed · Playwright NSR-9 **3/3** |
| **OF-15…OF-20** | **Nibras** | DONE | Leave vertical live |
| **NIR-3C / NIR-7A/B** | **Nibras** | DONE | Code+tests shipped |
| **NIR-5 / NIR-6** | **Nibras** | DONE via NSR-7/8 | Governed FKs + single-root org shipped |
| **NPS** (Nibras Process Security) | **Nibras** | **DONE** | NPS-1 SoD · NPS-2 review→HR · NPS-3 Att ESS · 6/6 deep+op PASS · My Attendance UI |
| **DTR** (Data Trust / Catalog Index) | **Catalog** | **ACTIVE** | Stewardship nudges + FilteredDataGrid→SearchSelect · DTR-3 = Pulse (other master) |
| **GradeVance E2E QA** | **EduOS** | **DONE** | Seed 6 runs + LCT report · `docs/eduos/qa-evidence/E2E-SUMMARY.json` |
| **GradeVance HITL P2** | **EduOS** | **ACTIVE** | Learning loop proven: edit→proposal→accept→bump→repin · `docs/eduos/qa-evidence/HITL-LEARNING-LOOP.json` · next: UI path + Phase C depth |
| **PV2** (Pulse v2 Intelligence Contract, ADR-0047) | **Pulse** | **ACTIVE** | **20/20 · L0–L5 · 6B DONE 5/5 · ADR-0047 Accepted** · 4A still soaking |
| **PV21** (Pulse 2.1, ADR-0049 Proposed) | **Pulse** | **ACTIVE** | Model understands, catalog executes. Flags default legacy/off. No live flip. No stack restart. |

**Multi-Master:** `.ai-toolkit/shared/multi-master.md` · seats · `docs/ops/MASTERS-COMMS.md` · RULE_30. · **This session seat: Nibras.**

**NSR principle (Nibras seat only):** every nav item under people/my/team is either architecture-thick + tested + E2E-QA’d for GOFSCO staff use, or demoted/hidden until it is.

---

## NSR — Nibras Staff-Ready (GOFSCO) · DISPATCH 2026-09-16

**Scope:** `backend/people/**`, `backend/correspondence/**` (only as ESS spine for my/team), `carbon-frontend/src/apps/{people,my,team}/**`, `carbon-frontend/src/api/{people,my,team}.js`, shell breadcrumbs/capabilities for those apps, GOFSCO seeds/import/link commands.  
**Out of scope:** Pulse/AI/ECF, emissions/Carbon hosted apps, AAST data-trust product UI, healthy/gradevance.  
**Contracts:** `shared/{api-contract,security,data-layer,testing,definition-of-done,frontend-ready,design-system,git-workflow}.md` · ADRs 0025, 0027, 0028, 0029, 0030.  
**Audit:** canvas `nibras-staff-ready.canvas.tsx` · prior audit `nibras-audit.canvas.tsx`.

### Wave map (dispatch order)

| Wave | Phases | Parallel? | Outcome |
|------|--------|-----------|---------|
| **W0** | NSR-0 | — | Bookkeeping: flip DONE; kill stale “likely shipped” |
| **W1** | NSR-1A, NSR-1B | YES (ops doc vs BE signal) | Data spine + leave status truth |
| **W2** | NSR-2A → NSR-2B | Sequential | Ledger = payroll SoT + FE pay honesty |
| **W3** | NSR-3A → NSR-3B | Sequential | Loans thick (BE then FE/My) |
| **W4** | NSR-4A → NSR-4B | Sequential | Hire/onboarding thick |
| **W5** | NSR-5A, NSR-5B, NSR-5C | Partial parallel | Profile-change apply · Config CRUD · PeopleHome |
| **W6** | NSR-6A | DONE | Path H: Attendance + Rotation hidden from go-live nav; Certifications stay |
| **W7** | NSR-7A → NSR-7B → NSR-7C | Sequential | ADR-0027 governed lookups (was NIR-5) |
| **W8** | NSR-8A → NSR-8B | Sequential | ADR-0028 single-root org (was NIR-6) |
| **W9** | NSR-9 | After W1–W5 green | QA E2E gate — **DONE** 2026-09-21: Playwright leave UI **3/3 PASS** |

**Go-live gate:** NSR-9 PASS required before declaring GOFSCO staff onboarding ready. W7/W8 may run after first cohort only if Master explicitly defers (document debt); W6 demote path is allowed instead of thicken if Master chooses hide.

---

### Phase NSR-0 — QA: Bookkeeping status flips + Active-focus truth
**Date:** 2026-09-16  
**Worker Role:** qa-validator  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — verified NSR-0 2026-09-16 (pytest people payroll/compensation/leave e2e)

#### Exact checks (read-only + status edits in TASKS.md only)
1. **NIR-3C** — prove `PayrollRunService.compute/validate/commit` + `people/tests/test_payroll_service.py` green → set NIR-3C **DONE**.
2. **NIR-7A/B** — prove `compensation_service.py` + `test_compensation.py` + `EmployeePayTab.jsx` SystemDialog → set NIR-7A/B **DONE**.
3. **OF-15…OF-20** — prove my/team leave journey files + `test_leave_journey_e2e.py` / OF-20 walk → confirm Active focus DONE (already noted above).
4. Append a short block to `TASK-RESULTS.md`: NSR-0 evidence (commands + pass counts). Do **not** change runtime code.

#### DO NOT TOUCH
Any file outside `TASKS.md` / `TASK-RESULTS.md`.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest \
  people/tests/test_payroll_service.py people/tests/test_compensation.py \
  people/tests/test_leave_journey_e2e.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
```

---

### Phase NSR-1A — DevOps+Backend: GOFSCO data spine runbook + instance safety checks
**Date:** 2026-09-16  
**Worker Role:** devops-worker (primary) · backend-worker only if a seed command is broken  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — runbook + QA manual + seed_gofsco_org --dry-run 2026-09-16

#### Files to Read First
- `backend/people/management/commands/import_gofsco_employees.py`
- `backend/people/management/commands/seed_gofsco_rules.py`
- `backend/people/management/commands/link_employee_users.py`
- `backend/people/management/commands/propagate_leave_policies.py`
- `backend/mdm/management/commands/seed_gofsco_org.py` (or current path)
- `backend/correspondence/management/commands/seed_correspondence.py` (exact name — confirm)
- `docs/QA-MANUAL-PEOPLE-MY-TEAM.md` (fix stale GF-00X references)

#### What to Build
1. Create `docs/nibras/GOFSCO-ONBOARDING-RUNBOOK.md` with ordered commands, env vars (`DJANGO_BRAND=nibras`, `INSTANCE_NAME`, `EMPLOYEE_DEFAULT_PASSWORD`), failure modes, and **acceptance SQL/ORM checks** (counts: OrgUnits, Employees, LeaveEntitlements, Users with my:access, managers with team:access).
2. Add a section **Manager hierarchy**: how to set `Employee.manager` / `OrgUnit.manager_employee_id` after import (import does not set managers — document mandatory HR step or small management command that assigns from a CSV — prefer CSV command if no UI yet).
3. Add a section **Salary honesty**: estimated `basic_salary` must be flagged; production payroll forbidden until NSR-2A or explicit freeze flag.
4. Fix stale QA manual references to GF-001…GF-005 / `seed_gofsco`.
5. If `seed_gofsco_org` / import lack any dry-run flag, add `--dry-run` only (no ADR-0028 yet — that is NSR-8).

#### DO NOT TOUCH
`backend/ai/**`, emissions apps, frontend (except QA doc if it lives under docs/).

#### Verification Gate
```bash
# Dry-run / help exits 0 for each command named in the runbook
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python manage.py help import_gofsco_employees
test -f /home/ahmed/ws/carbon/docs/nibras/GOFSCO-ONBOARDING-RUNBOOK.md
rg -n "GF-00[0-9]|seed_gofsco[^_]" /home/ahmed/ws/carbon/docs/QA-MANUAL-PEOPLE-MY-TEAM.md && exit 1 || true
```
Write TASK-RESULTS with the runbook path + any command fixes.

---

### Phase NSR-1B — Backend: LeaveRecord ↔ Correspondence status sync
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — Master audit 2026-09-16 (13 passed: leave/loan sync + leave journey)

#### Files to Read First
- `backend/people/signals.py` (loan ↔ correspondence sync — **copy this pattern**)
- `backend/people/models.py` (`LeaveRecord` status field)
- `backend/people/tests/test_loan_status_sync.py`
- `backend/people/tests/test_leave_journey_e2e.py`

#### What to Build
1. Signal (or extend existing) so Correspondence terminal states for leave-type subjects update `LeaveRecord.status` (`approved` / `rejected` / `cancelled` as model allows — map 1:1 to existing choices; do not invent new enums without migration).
2. Tests in `people/tests/test_leave_status_sync.py` (new) covering approve + reject + send-back (if send-back reopens leave).
3. Ensure balance / self-service still uses Correspondence where designed — do not break `test_leave_journey_e2e.py`.

#### DO NOT TOUCH
Frontend; payroll; AI; NIR-5 FK migrations.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest \
  people/tests/test_leave_status_sync.py people/tests/test_leave_journey_e2e.py \
  people/tests/test_loan_status_sync.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
```

---

### Phase NSR-2A — Backend: Payroll compute from compensation ledger (ADR-0029 SoT)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — ledger SoT for payroll compute 2026-09-16  
**Depends on:** NSR-0  
**Contracts:** ADR-0025, ADR-0029 · `shared/data-layer.md`

#### Objective
End dual source of truth. `PayrollRunService.compute` (and calculation engine paths used by it) must derive basic/gross from **verified ledger lines** for the period, not `Employee.basic_salary`. Keep `basic_salary` as deprecated cache only if reflection already updates it — document behavior.

#### Files to Read First
- `backend/people/payroll_service.py`
- `backend/people/calculation_engine.py`
- `backend/people/compensation_service.py`
- `.ai-toolkit/decisions/0029-compensation-ledger.md`
- `backend/people/tests/test_payroll_service.py`
- `backend/people/tests/test_compensation.py`

#### What to Build
1. Resolve period basic (and components if already modeled) via `CompensationService` totals / active lines; fail closed with clear validation error if no verified basic line exists (do **not** silently use estimate).
2. Optionally: block or warn on Employee PATCH of `basic_salary` when ledger exists (prefer: PATCH does not accept `basic_salary` for clients with `people:manage` — force ledger append). Choose one approach; document in TASK-RESULTS.
3. Update/extend tests: compute with ledger only; compute without ledger → validation failure; existing WPS tests still green.
4. Remove stale “validation seam is a STUB” comment if still present.

#### DO NOT TOUCH
Frontend Pay tab (NSR-2B); ADR-0027 migrations; AI.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest \
  people/tests/test_payroll_service.py people/tests/test_compensation.py \
  people/tests/test_calculation_engine.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
cd /home/ahmed/ws/carbon && ./.ai-toolkit/scripts/verify.sh backend
```

---

### Phase NSR-2B — Frontend: Pay tab + payroll UI honesty (ledger SoT)
**Date:** 2026-09-16  
**Worker Role:** frontend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — ledger SoT FE honesty 2026-09-16  
**Depends on:** NSR-2A  
**Screen Spec:** attach/extend `docs/SCREEN-SPEC-COMPENSATION-LEDGER.md` (9 artifacts per `shared/frontend-ready.md` — update acceptance for “payroll reads ledger”)

#### Objective
HR cannot edit a misleading basic salary field as if it drives payroll. Pay tab is the only write path for pay; payroll page surfaces validation errors when ledger missing.

#### Files to Read First
- `carbon-frontend/src/apps/people/EmployeePayTab.jsx`
- `carbon-frontend/src/apps/people/PayrollRunsPage.jsx`
- `carbon-frontend/src/api/people.js`
- `docs/SCREEN-SPEC-COMPENSATION-LEDGER.md`

#### What to Build
1. Remove or demote editable `basic_salary` on employee forms if present; show read-only “reflected basic” from ledger/API.
2. PayrollRunsPage: show API validation errors from compute when no ledger line (SystemDialog / Alert — design-system).
3. i18n en+ar for new strings.
4. Vitest: extend people pay/payroll related test file (create `src/__tests__/EmployeePayTab.test.jsx` if none) — at least one assert on ledger-first copy / disabled field.

#### DO NOT TOUCH
Backend; my/team apps.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/EmployeePayTab.test.jsx
npm run build
cd /home/ahmed/ws/carbon && ./.ai-toolkit/scripts/verify.sh frontend
```

---

### Phase NSR-3A — Backend: Loan approve → persist installment schedule
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — materialize + payroll hybrid 2026-09-16  
**Depends on:** NSR-1B (signal patterns)  
**Contracts:** ADR-0030

#### Objective
`LoanInstallment` rows are generated when a loan becomes active (correspondence approve / status sync), using existing `calculate_loan_schedule` in the engine. Payroll deduction prefers persisted installments over pure in-memory recompute (document if hybrid).

#### Files to Read First
- `backend/people/signals.py`
- `backend/people/calculation_engine.py` (`calculate_loan_schedule`)
- `backend/people/models.py` (`Loan`, `LoanInstallment`)
- `backend/people/tests/test_loan_status_sync.py`
- `backend/people/payroll_service.py` (loan deduction path)

#### What to Build
1. Service function `materialize_loan_installments(loan) -> list` — idempotent (no dupes on re-approve).
2. Call from status sync when loan → `active`.
3. Tests: approve creates N installments; re-approve does not duplicate; payroll uses rows.
4. Admin/API: keep CRUD but document generated-as-source.

#### DO NOT TOUCH
Frontend (NSR-3B); AI.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest \
  people/tests/test_loan_status_sync.py people/tests/test_loan_installments.py \
  -q --maxfail=5 --disable-warnings -p no:cacheprovider
```
(Create `test_loan_installments.py` in this phase.)

---

### Phase NSR-3B — Frontend: Loan schedule UI + My loans surface
**Date:** 2026-09-16  
**Worker Role:** frontend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — FE My loans + HR installments UI 2026-09-16  
**Depends on:** NSR-3A  
**Screen Spec:** `docs/_archive/design-superseded/SCREEN-SPEC-NIBRAS-LOANS.md`

#### Objective
HR loan expander shows generated installments (read-only is OK if generated). Employee `/my` shows loan list + status (QA B6).

#### Files to Read First
- `carbon-frontend/src/apps/people/LoansPage.jsx`
- `carbon-frontend/src/apps/my/MyDashboard.jsx`
- `carbon-frontend/src/api/people.js`, `carbon-frontend/src/api/my.js`
- `docs/QA-MANUAL-PEOPLE-MY-TEAM.md` (B6)

#### What to Build
1. `fetchMyLoans` (or equivalent) against `people/me/loan/`; dashboard or `/my` card listing loans.
2. HR expander: reload installments after status active; empty state “generated on approval”.
3. i18n; Vitest for my loans helper/render smoke (`src/__tests__/MyLoans.test.jsx`).

#### DO NOT TOUCH
Backend domain rules (NSR-3A owns them).

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/MyLoans.test.jsx
npm run build
```

---

### Phase NSR-4A — Backend: Hire/onboarding hooks (entitlement + optional opening ledger)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — hire onboard hooks 2026-09-16  
**Depends on:** NSR-1B, NSR-2A

#### Files to Read First
- `backend/people/views.py` (`EmployeeListCreateView`)
- `backend/people/leave_policy_service.py`
- `backend/people/compensation_service.py`
- `backend/people/serializers.py`

#### What to Build
1. Post-create hook / service: `onboard_employee(employee, *, opening_basic=None, user=None)`.
2. Wire from create view; tests for entitlement creation when policies exist; opening ledger line when amount provided.
3. Do not auto-fabricate salary.

#### DO NOT TOUCH
Frontend wizard (NSR-4B).

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest \
  people/tests/test_employee_onboard.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
```

---

### Phase NSR-4B — Frontend: EmployeeWizard onboarding fields
**Date:** 2026-09-16  
**Worker Role:** frontend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — wizard onboard fields 2026-09-16  
**Depends on:** NSR-4A  
**Screen Spec:** update wizard acceptance in `docs/` or TASK-RESULTS (manager required, optional opening basic, join_date required)

#### Objective
Wizard collects manager, join_date, civil_id, optional opening basic; calls API that triggers onboard hooks.

#### Files to Read First
- `carbon-frontend/src/apps/people/EmployeeWizard.jsx`
- `carbon-frontend/src/api/people.js`

#### What to Build
1. Required manager + join_date; optional opening basic (capability-gated).
2. Success path shows entitlement/payroll readiness toast.
3. Vitest wizard validation smoke.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/carbon-frontend
npx vitest run src/__tests__/EmployeeWizard.test.jsx
npm run build
```

---

### Phase NSR-5A — Backend: Profile-change apply on approve
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — allowlisted Employee apply on profile_change approve 2026-09-16  
**Depends on:** NSR-1B  
**Contracts:** ADR-0030

#### Files to Read First
- Profile-change submit path in `backend/people/self_views.py`
- `backend/people/signals.py`
- Correspondence subject adapters for profile_change

#### What to Build
1. Apply function + tests (approve mutates; reject does not; unknown field ignored/rejected).
2. If unsafe to auto-apply some fields, allowlist narrowly and document.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest \
  people/tests/test_profile_change_apply.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
```

---

### Phase NSR-5B — Frontend: People Config thick (compliance CRUD + C&B matrix)
**Date:** 2026-09-16  
**Worker Role:** frontend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — compliance CRUD + compensation create UI 2026-09-16  
**Depends on:** NSR-0  
**Screen Spec:** `docs/_archive/design-superseded/SCREEN-SPEC-PEOPLE-CONFIG.md`

#### Objective
Compliance rules create/update in UI (API already exists). Compensation components + plans admin UI (API POST exists; no page today). Reference Data stays. Overview may remain informational.

#### Files to Read First
- `carbon-frontend/src/apps/people/PeopleConfigPage.jsx`
- `carbon-frontend/src/apps/people/referenceDataRegistry.js`
- `carbon-frontend/src/api/people.js` (add missing helpers)

#### What to Build
1. Compliance CRUD using SystemDialog + api helpers.
2. New section or routes under config for components + plans (reuse PageContainer patterns from PoliciesPage).
3. Vitest smoke for new helpers; i18n; **no** raw fetch.

#### DO NOT TOUCH
If API missing fields, stop and report — do not invent backend in this phase (split to hotfix backend phase).

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/PeopleConfig.test.jsx
npm run build
cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/audit-routes.py
```

---

### Phase NSR-5C — Frontend: PeopleHome ops landing + breadcrumb honesty
**Date:** 2026-09-16  
**Worker Role:** frontend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — ops landing + breadcrumb honesty 2026-09-16  
**Depends on:** NSR-0

#### Objective
Replace placeholder `PeopleHome` with an ops landing: links/cards to Employees, Leave, Payroll, Policies, Loans, Attendance (only modules that remain in go-live nav). Fix ghost `/people/benefits` breadcrumb. Add `/my` and `/team` entries to shell `Breadcrumbs.jsx`.

#### Files to Read First
- `carbon-frontend/src/apps/people/PeopleHome.jsx`
- `carbon-frontend/src/shell/Breadcrumbs.jsx`
- People/my/team manifests

#### What to Build
1. Thick landing (counts optional via existing list APIs — don’t block on new endpoints).
2. Breadcrumb registry fix; RULE_9 — no in-page breadcrumbs.
3. Vitest: PeopleHome renders module links.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/carbon-frontend
npx vitest run src/__tests__/PeopleHome.test.jsx src/__tests__/PeopleManifest.test.jsx
npm run build
cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/audit-routes.py
```

---

### Phase NSR-6A — Backend+Frontend decision: Attendance thick-or-hide
**Date:** 2026-09-16  
**Worker Role:** master-architect decides in TASK-RESULTS; **backend-worker** implements chosen path  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — Path H (hide Attendance + Rotation from go-live nav); 2026-09-16  
**Depends on:** NSR-2A  
**Default recommendation:** **Thicken OT/hours into payroll validation seam** if GOFSCO needs timesheets in week 1; else **hide** Attendance + Rotation from people nav/manifest until a later epic (Certifications can stay as simple CRUD if HR needs credential list — still add expiry warning).

#### Master decision (2026-09-16)
**Path H.** Do not thicken OT this wave. Hide Attendance + Rotation from go-live nav/PeopleHome/breadcrumbs. Certifications remain. Document in `docs/nibras/GOFSCO-ONBOARDING-RUNBOOK.md`.

#### Objective
No pretend timekeeping. Either:
- **Path T:** attendance hours feed OT/gross rules in `calculation_engine` / validation with tests; FE remains; or
- **Path H:** remove/hide nav items + routes (RULE_22: no dangling targets); document in runbook.

Master must pick Path T or H in the dispatch message; worker implements only that path.

#### Verification Gate
Path T: pytest calculation/payroll attendance cases + FE lint/build.  
Path H: `audit-routes.py` pass + manifest tests pass + no `/people/attendance` nav entry.

**Done (Path H):** Attendance + Rotation removed from `people/manifest` nav + PeopleHome modules/counts; breadcrumb ROUTE_CONFIG entries removed; App routes kept for deep-link (documented); Certifications remain in nav; GOFSCO runbook §3b; Vitest PeopleHome + PeopleManifest; audit-routes + build.

---

### Phase NSR-7A — Backend: Seed 7 governed ReferenceSets (was NIR-5C)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — 2026-09-16  
**Depends on:** NSR-1A  
**Contracts:** ADR-0027 · `docs/DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md`

#### Objective
Seed the missing sets (grade, loan_type, permission_type, cert_type, payslip_line_type, compliance_category, jurisdiction — confirm exact codes from ADR/design doc). Idempotent; GOFSCO-oriented values.

#### Files to Read First
- ADR-0027, DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md
- `seed_gofsco_rules.py` (extend, don’t create parallel seed)

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python manage.py seed_gofsco_rules
../.venv/bin/python -c "from mdm.models import ReferenceSet; print(ReferenceSet.objects.filter(code__in=['grade','loan_type']).count())"
```

---

### Phase NSR-7B — Backend: Employee/Loan/Cert governed FKs (was NIR-5A/B)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — verified 2026-09-16 (pytest people 228 passed; GovernedValueField + Bucket-1 FKs)  
**Depends on:** NSR-7A  
**Contracts:** ADR-0027

#### Objective
Replace soft `*_code` CharFields on Employee (and loan_type, cert_type, etc. per ADR Bucket-1) with FK to `ReferenceValue`. Introduce shared `GovernedValueField` (mdm or people — prefer mdm reusable). Data migration from codes. Serializers nest `{id,code,label}`.

#### DO NOT TOUCH
Frontend dropdowns (NSR-7C). Leave `leave_type` alone (already FK).

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest people/tests/ -q --maxfail=8 --disable-warnings -p no:cacheprovider
```

---

### Phase NSR-7C — Frontend: Nested governed dropdowns (was NIR-5D)
**Date:** 2026-09-16  
**Worker Role:** frontend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Depends on:** NSR-7B

#### Objective
Wizard + filters write FKs / nested values via `useReferenceOptions`; stop writing raw `*_code` strings.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/carbon-frontend
npx vitest run src/__tests__/EmployeeWizard.test.jsx src/__tests__/PeoplePages.test.jsx
npm run build
```

---

### Phase NSR-8A — Backend: Single-root OrgUnit + instance-gated seeds (was NIR-6A)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Depends on:** NSR-1A  
**Contracts:** ADR-0028

#### Objective
`OrgUnit` invariant: at most one `parent=None` per deployment. Gate `seed_gofsco_org` / `seed_aastmt_org` on `INSTANCE_NAME` / `DJANGO_BRAND`. Add `get_deployment_root()` helper used by people visibility queries where appropriate.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest \
  mdm/tests/test_org_unit_root.py people/tests/test_cbac.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
```
(Create org root tests in this phase.)

---

### Phase NSR-8B — Frontend: Org dropdown scoped to deployment root (was NIR-6B)
**Date:** 2026-09-16  
**Worker Role:** frontend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — 2026-09-16  
**Depends on:** NSR-8A

#### Objective
Org unit pickers default to deployment subtree (API filter or FE filter using root endpoint). No cross-tree leakage in wizard/filters.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/carbon-frontend && npx vitest run src/__tests__/OrgUnitScope.test.jsx && npm run build
```

---

### Phase NSR-9 — QA: Staff go-live E2E gate
**Date:** 2026-09-16  
**Worker Role:** qa-validator  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — 2026-09-21 (pytest/vitest/build + Playwright leave UI 3/3 PASS; evidence `docs/nibras/evidence/NSR-9-go-live-gate.md`)
**Depends on:** NSR-1B, NSR-2B, NSR-3B, NSR-4B, NSR-5C (W6–W8 per Master deferral note); W7–W8 now DONE

#### Objective
Prove staff journeys with automated evidence. Update `docs/QA-MANUAL-PEOPLE-MY-TEAM.md` checklist to PASS/FAIL with links to artifacts.

#### What to Build / Run
1. Playwright: `e2e/journeys/nibras-leave-approve.spec.ts` — login employee → request leave → login manager → approve (use test fixtures / seeded users from runbook).
2. Playwright or documented API+UI hybrid: hire → entitlement present → payroll compute fails without ledger → append ledger → compute OK (may be BE pytest + thin UI check if full Playwright too heavy — prefer full UI).
3. Vitest: MyLeave + TeamInbox smoke tests added if missing.
4. Final `verify.sh frontend` + people pytest subset green.
5. Go-live recommendation: **READY** or **BLOCKED** with explicit remaining P0s.

#### DO NOT TOUCH
Product features — evidence only + missing tests.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest people/tests/ -q --maxfail=10 --disable-warnings -p no:cacheprovider
cd /home/ahmed/ws/carbon/carbon-frontend && npm run build
cd /home/ahmed/ws/carbon && npx playwright test e2e/journeys/nibras-leave-approve.spec.ts
```

---

## PEC — Pulse Enterprise Control-plane (DISPATCHED 2026-09-16)

**Canonical plan:** `docs/pulse/PULSE-ROADMAP.md` · **SSOT:** `docs/pulse/PULSE-CANONICAL.md`  
**Gap map:** Cursor canvas `pulse-enterprise-control-plane.canvas.tsx`  
**Principle:** freeze the spine (boundary/PDP/Flight Director); ship metabolism + measurement.  
**Contracts:** `shared/ai-contract.md`, `security.md`, `api-contract.md`, `testing.md`, `definition-of-done.md`  
**Test partitioning:** MASTER DIRECTIVE above — never full-suite pytest / never bare vitest.

**Wave map (dispatch order):**
| Wave | Phases | Parallel? |
|------|--------|-----------|
| **W1** | PEC-1A, PEC-4A, PEC-7A | YES — non-overlapping files |
| **W2** | PEC-2A, PEC-3A, PEC-3B | After W1 green (3B needs Screen Spec pointer below) |
| **W3** | PEC-ID-1, PEC-5A, PEC-5B, PEC-6A, PEC-6B | After W2; 6B needs Screen Spec |
| **Gate** | Master reviews TASK-RESULTS; mark DoD rows in PULSE-ROADMAP |

---

### Phase PEC-1A — DevOps+Backend: Heartbeat metabolism proof (P1)
**Date:** 2026-09-16  
**Worker Role:** devops-worker (primary) + backend-worker (health surface only if missing)  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Depends on:** —  
**Roadmap:** P1 Heartbeat

#### Context
Code already exists: `run_pulse_maintenance`, `PulseHeartbeat`, `deploy/instance/setup-pulse-heartbeat.sh`, compose `scheduler` / `learning-scheduler`, tests in `ai/tests/test_pulse_heartbeat.py`. Canonical still marks F5 open because **unattended nibras evidence + health “last heartbeat”** is not proven. This phase closes P1 with **runtime evidence**, not a rewrite.

#### Files to Read First
- `docs/pulse/PULSE-ROADMAP.md` §P1
- `backend/ai/management/commands/run_pulse_maintenance.py`
- `backend/ai/models/heartbeat.py`
- `deploy/instance/setup-pulse-heartbeat.sh`
- `docker-compose.yml` (scheduler services)
- `backend/ai/sweeps_api.py` (existing heartbeat read path)

#### Implementation
1. Confirm compose schedulers actually invoke `run_pulse_maintenance` (or equivalent) with `DJANGO_BRAND` / instance isolation. Fix command wiring if wrong.
2. Ensure a **health/read API** already exposes last heartbeat per `(instance, loop)` — extend `sweeps_api` or `healthy` only if missing; do not invent a second API.
3. Produce acceptance evidence pack under `docs/pulse/evidence/PEC-1A-heartbeat.md`:
   - command output of a real maintenance run for `nibras` (or local brand)
   - SQL/ORM dump of new `PulseHeartbeat` rows (proactive, consolidation, distill, decay)
   - health endpoint JSON showing last tick
4. If VPS systemd is out of scope for this machine, document exact `setup-pulse-heartbeat.sh nibras` steps as the deploy handoff and prove via compose timer/cron equivalent locally.

#### DO NOT TOUCH
- `backend/ai/engine/` cognition loop internals
- PDP / command_boundary
- Frontend

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python manage.py run_pulse_maintenance --dry-run 2>&1 | tee /tmp/pec1a-dry.txt
# Then a real run (brand=nibras if available):
DJANGO_BRAND=nibras ../.venv/bin/python manage.py run_pulse_maintenance 2>&1 | tee /tmp/pec1a-run.txt
../.venv/bin/python -m pytest ai/tests/test_pulse_heartbeat.py -q --maxfail=5 --disable-warnings
./.ai-toolkit/scripts/verify.sh backend
# Evidence file must exist and cite row ids / timestamps.
test -f ../docs/pulse/evidence/PEC-1A-heartbeat.md
```

#### Handoff
Write `TASK-RESULTS.md` section `## PEC-1A` with terminal proof + evidence path.

---

### Phase PEC-4A — Backend: Eval harness baseline + merge gate (P4)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Depends on:** — (parallel with PEC-1A)  
**Roadmap:** P4 Evaluation Harness

#### Context
`backend/ai/eval/` has fixtures, `golden_hrms.py`, replay, checks. Canonical: “measurably = not yet.” Need ≥20 golden scenarios for nibras, metrics (grounding-pass, deny-correctness, fabrication-rate=0, latency, tokens), and a **CI-invokable** entrypoint that fails on fabrication or deny regression.

#### Files to Read First
- `docs/pulse/PULSE-ROADMAP.md` §P4
- `backend/ai/eval/*`
- `backend/ai/tests/redteam/` (pattern for fail-closed)
- `.github/workflows/` (existing CI)

#### Implementation
1. Author/expand golden scenarios to **≥20** nibras cases covering: net-pay grounding, cross-employee deny, payroll lifecycle consent, ambiguous→clarify, compound Q-1 if feasible, topic_guard out-of-scope.
2. Add `backend/ai/eval/run_harness.py` (or pytest marker `eval_golden`) that prints pass-rate + metrics JSON.
3. Wire CI job or document exact `pytest` invocation in workflow that already runs AI tests — prefer extend existing workflow, do not create duplicate full-suite jobs.
4. Add one deliberate negative test proving fabrication/deny regression would fail the harness.
5. Evidence: `docs/pulse/evidence/PEC-4A-eval-baseline.md` with first measured baseline numbers (do not invent targets).

#### DO NOT TOUCH
- Production prompt text in `instance.yaml` except if a scenario requires a fixture override
- Frontend
- Heartbeat code (PEC-1A owns it)

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/eval ai/tests/redteam -q --maxfail=8 --disable-warnings
# Harness must print metrics; fabrication_rate must be 0.
./.ai-toolkit/scripts/verify.sh backend
test -f ../docs/pulse/evidence/PEC-4A-eval-baseline.md
```

---

### Phase PEC-7A — Backend: Convergence — remove inert F1a/F3 paths (P7 partial)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Depends on:** —  
**Roadmap:** P7 (F1a/F3 decision already: REMOVE/DEFER — fold guidance into instance.yaml)

#### Context
Canonical §12: `instance.yaml` is the single prompt-config mechanism. Filesystem `domain_packs/*/skills` guidance is inert (F1a). `PlaybookBlock` empty → unused A/B (F3). Anti-drift L6: delete or defer; do not invest.

#### Files to Read First
- `docs/pulse/PULSE-CANONICAL.md` §5, §9 F1a/F3, §12
- Grep: `guidance_skills`, `PlaybookBlock`, `build_chat_prompt`

#### Implementation
1. Confirm no live path injects `guidance_skills` from filesystem packs.
2. Remove dead call sites / loader hooks **or** mark clearly deferred with a single `# DEFERRED(F1a)` and a verify.sh antipattern that fails if someone re-wires without ADR — prefer **delete dead imports** if unused outside tests.
3. For `PlaybookBlock`: if zero rows and unused in hot path, add module docstring + skip/xfail only if tests assert empty; **do not** seed fake A/B. Prefer deleting unreachable A/B selection code if truly dead (ask Master via TASK-RESULTS if ambiguous — then leave `# DEFERRED(F3)` with ADR stub).
4. Add startup or verify check notes in evidence file.
5. Evidence: `docs/pulse/evidence/PEC-7A-convergence.md` listing deleted symbols + grep proof.

#### DO NOT TOUCH
- `instance.yaml` persona content (except typos)
- Live ProcessDefinition / Capability seed paths
- Frontend

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon && \
  rg -n "guidance_skills=" backend/ai/engine/cognition/turn/runner.py || true
cd backend && ../.venv/bin/python -m pytest ai/tests/test_provider_pulse.py ai/tests/test_adapter.py -q --maxfail=5 --disable-warnings
./.ai-toolkit/scripts/verify.sh antipatterns
test -f ../docs/pulse/evidence/PEC-7A-convergence.md
```

---

### Phase PEC-2A — Backend: Prove learning-reuse OR cut (P2)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Depends on:** PEC-1A (heartbeat drives consolidation)  
**Roadmap:** P2

#### Context
SkillAwarePlanner + flywheel + gate-only promotion exist; live reuse never observed. Need reuse counter + ledger citation **or** documented cut (L6).

#### Files to Read First
- `docs/pulse/PULSE-ROADMAP.md` §P2
- `backend/ai/feedback/skill_flywheel.py`
- `backend/ai/engine/skills/*`, planner skill preference
- `backend/ai/engine/cognition/plan/`

#### Implementation
1. Add/confirm per-skill `usage_count` (or equivalent) increments when a promoted skill drives a plan/turn; write ledger/telemetry row.
2. Write an integration test that: draft→admit/promote fixture skill → later plan matches → counter +1.
3. If the arc cannot fire on a realistic HRMS scenario after honest attempt: write `docs/pulse/evidence/PEC-2A-CUT.md` with Master decision request to remove the path — **do not leave half-dead code**.
4. Evidence: `docs/pulse/evidence/PEC-2A-reuse.md` with counter before/after.

#### DO NOT TOUCH
- Auto-promote without gate
- Frontend Console promote UI (PEC-6*)

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_learning_trigger.py ai/tests/test_flight_learning.py -q --maxfail=5 --disable-warnings
# Plus any new reuse test file created in this phase
./.ai-toolkit/scripts/verify.sh backend
```

---

### Phase PEC-3A — Backend: Proactive delivery path proof (P3 backend)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Depends on:** PEC-1A  
**Roadmap:** P3

#### Context
Delivery persists `KgProactiveInsight` + SSE exists; scheduled generation tied to heartbeat. Prove one insight reaches the API/SSE contract with provenance fields (RULE_23).

#### Files to Read First
- `backend/ai/engine/proactive/*`
- insights API / SSE surfaces
- `docs/pulse/PULSE-UX.md` rubric (outcomes-only copy)

#### Implementation
1. Trace proactive → persist → list/stream endpoints; fix gaps.
2. Test: after maintenance/proactive loop (mocked OK), insight visible via API with honest confidence + no engine jargon.
3. Evidence: `docs/pulse/evidence/PEC-3A-proactive-api.md`

#### DO NOT TOUCH
- Frontend notification chrome (PEC-3B)

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/ -k "proactive or insight" -q --maxfail=8 --disable-warnings
./.ai-toolkit/scripts/verify.sh backend
```

---

### Phase PEC-3B — Frontend: Proactive insight surfaces in Nibras UI (P3 UI)
**Date:** 2026-09-16  
**Worker Role:** frontend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Depends on:** PEC-3A  
**Screen Spec:** reuse `docs/pulse/PULSE-UX.md` + `PULSE-UX-DESIGN.md` (4-beat story, provenance, dismiss/act). No new full Screen Spec doc required if those cover the panel — attach deviations in TASK-RESULTS.

#### Implementation
1. Wire notification/insights panel to consume SSE/API from PEC-3A.
2. Dismiss + act affordances; RULE_23 copy.
3. Targeted vitest + lint + build.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/carbon-frontend && npm run lint && npx vitest run src/__tests__/*insight* src/__tests__/*notif* 2>/dev/null || npx vitest run src/__tests__/ -t "insight|proactive|notif" ; npm run build
```

---

### Phase PEC-ID-1 — Backend: Identity propagation hardening
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Depends on:** — (can start W3)  
**Contracts:** `shared/security.md`

#### Context
`engine_runtime` passes `user_token=f"inproc:{instance_id}:{host_user_id}"`. Enterprise bar (IBM): propagate/exchange, never substitute. Before MCP egress expands, introduce a **short-lived scoped host credential** (or documented actor-chain on `PolicyDecisionRow`) so every boundary hop attributes user→agent→tool.

#### Implementation
1. ADR in `.ai-toolkit/decisions/` (Master will ratify — draft ADR-00xx-pulse-identity-propagation.md).
2. Implement minimal: persist actor_chain on policy/audit rows for host effects; keep inproc token but include stable `user_id` + `instance_id` + `request_id` in all PDP decisions.
3. Tests for attribution presence; no behavior change to CBAC denies.

#### DO NOT TOUCH
- External IdP / OAuth exchange (out of scope — ADR only marks Phase 2)

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_tenancy_isolation.py ai/tests/pilot/test_pilot_e2e.py -q --maxfail=5 --disable-warnings
./.ai-toolkit/scripts/verify.sh backend
```

---

### Phase PEC-5A — Backend: GOSI/WPS governed ProcessDefinitions (P5 slice)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Depends on:** —  
**Roadmap:** P5

#### Implementation
1. Add `domain_packs/nibras/processes/` YAMLs for GOSI/WPS SIF generation lifecycle with `human_only` on irreversible submit; `refuse_if`/`ask_if`/`kill_switch`.
2. Register capabilities in `api_catalog.yaml` + `capability_registry.py` as needed.
3. Extend `seed_nibras_processes.py` idempotently; tests mirror payroll/leave/loan process tests.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_nibras_payroll_process.py ai/tests/test_nibras_leave_process.py ai/tests/test_nibras_loan_process.py -q --maxfail=5 --disable-warnings
# Plus new gosi/wps tests
./.ai-toolkit/scripts/verify.sh backend
```

---

### Phase PEC-5B — Backend: Onboarding governed process (P5 slice)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Depends on:** PEC-5A patterns  

Same pattern as PEC-5A for employee onboarding lifecycle. Evidence + seed + tests.

---

### Phase NPS-0 — Toolkit: process security honesty (ADR-0045) · DONE 2026-09-21
**Owner:** Nibras · **Status:** DONE  
**Delivered:** ADR-0045 · RULE_34 · security.md RULE 11 · PB-61 · honesty CI
`ai/tests/test_nibras_process_security_planes.py` · pack README · cursor rule.
**Does not** implement host SoD — documents residual risk and forbids firefighting.

---

### Phase NPS-1 — Backend: shared host SoD gate for admin irreversibles
**Date:** 2026-09-21  
**Worker Role:** backend-worker  
**Status:** DONE  
**Owner:** Nibras  

**Delivered:** `people.governance.sod` + `SoDPreparation` (migration 0029); stamp on
compute/generate/create; refuse same-actor on commit/WPS submit/activate/attendance
approve (views + host_executor + payroll_service); honesty matrix → `host_gate`;
`people/tests/test_host_sod.py`; deep sim two-actor (`ahmed`/`admin`); ADR-0045 /
PB-61 / RULE 11 / cursor rule updated.

---

### Phase NPS-2 — Backend: Pulse review authority → HR CBAC
**Date:** 2026-09-21  
**Worker Role:** backend-worker  
**Status:** DONE  
**Owner:** Nibras  

**Delivered:** `ai.governance.review_authority` maps Nibras `*.review` human_task
capabilities to host CBAC (`correspondence:act` leave, `correspondence:finance` loan,
`people:manage` payroll/GOSI/onboard/attendance). `enqueue_inbox_task` uses resolver
(+ brand `app_identifier` / `visibility=global`). Inbox list/stream admit designated
authorities; `list_pending` filters to tasks the principal may decide. Tests:
`ai/tests/test_review_authority.py`. ADR-0045 / RULE_34 / RULE 11 / PB-61 / pack README
updated. Unmapped Pulse caps still default `ai:operator`.

---

### Phase NPS-3 — Backend: Attendance ESS via Correspondence
**Date:** 2026-09-21  
**Worker Role:** backend-worker  
**Status:** DONE  
**Owner:** Nibras  

**Delivered:** Leave-shaped ESS for `attendance.permission.lifecycle` — corr type
`attendance_permission` + manager `skip_if_self` policy; `POST /people/me/attendance-permissions/`
(`people.attendance_ess` + self view); signal flips `approved=True`; Agent tools
`submit_my_attendance_permission` / `list_my_attendance_permissions`; capability
submit → self view; honesty matrix → `correspondence`; review authority →
`correspondence:act`. Admin create/PATCH + NPS-1 SoD kept as ops fallback. Tests:
`people/tests/test_attendance_ess.py`. Sims/host lane use ESS path.

---

### Phase NPS-4 — Backend+FE: me POST parity + My Attendance UI + 6/6 regression
**Date:** 2026-09-21  
**Worker Role:** backend-worker + frontend-worker  
**Status:** DONE  
**Owner:** Nibras (Master seat)  

**Delivered:**
- `host_executor._people_me` POST for `leave` / `loan` / `attendance-permissions` (reuses DRF self-views / `attendance_ess`) — Agent confirm path matches HTTP.
- My Attendance UI (`/my/attendance`) mirroring My Leave: SystemDialog, history table, i18n en/ar, nav/breadcrumbs/capabilities, dashboard quick action, vitest smoke.
- Deep 6/6 PASS + operator 6/6 PASS after NPS-1–3.

**Evidence:** `SESSION-20260921-132047-NIBRAS-PROCESSES` · `SESSION-20260921-132248-NIBRAS-OPERATOR` · `test_people_me_ess_post.py` · `MyAttendance.test.jsx`

---

### Phase PEC-6A — Backend: Admin skill promote/reject decision API (P6)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Depends on:** —  

#### Context
Admission gate is system-side; Console needs an **admin decision endpoint** that runs gate (or records reject) under CBAC `ai:publisher` / `ai:process_owner`. No bypass of `_authority` token.

#### Implementation
1. POST endpoints: promote (calls gate `_promote_skill` / `admit_skill` path) and reject (sets deprecated/rejected with reason).
2. CBAC-gated; audit log row.
3. Tests: non-admin 403; admin promote increments promoted; forged path still gate-only.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/ -k "skill and (promot or admit or gate)" -q --maxfail=8 --disable-warnings
./.ai-toolkit/scripts/verify.sh backend
```

---

### Phase PEC-6B — Frontend: Console promote/reject + Capabilities registry view (P6 UI)
**Date:** 2026-09-16  
**Worker Role:** frontend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Depends on:** PEC-6A  
**Screen Spec:** extend existing Console shell patterns in `AIWorkspace` Processes/Skills tabs; follow `shared/frontend-ready.md` minimally (states: loading/empty/error/success; CBAC lock). Reuse `SkillsPanel` — add actions, do not duplicate.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/carbon-frontend && npm run lint && npm run build
# targeted vitest for SkillsPanel / Console if present
```

---

## End PEC track specs

---

## PEC-R — Pulse residuals (post P1–P7)

### Phase PEC-R1 — Backend: Capabilities registry list API
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — GET `/carbon-api/ai/catalog/capabilities/` + tests 2026-09-16  
**Owner Master:** Pulse  
**Depends on:** PEC-6B deferred gap; `ai.models.capability.Capability` (P3-01)

Close the P6 Console gap: expose a **read-only** CBAC-scoped list of durable Capability contracts so Console can show the registry (PEC-6B deferred this).

#### Files to Read First
- `backend/ai/models/capability.py`
- `backend/ai/catalog_api.py` + `catalog_urls.py` (skills list pattern)
- `backend/ai/ops_api.py` / `ops_urls.py` (pulse read surfaces)
- `backend/ai/tests/test_capability_loader.py`
- `.ai-toolkit/shared/{api-contract,security,testing}.md` · RULE_21 (read-only)

#### Tasks
1. Add `GET` list endpoint for Capability rows (prefer `/carbon-api/ai/catalog/capabilities/` or `/carbon-api/ai/pulse/capabilities/` — match existing catalog/ops style; document choice).
2. Serializer: capability_id, business_name, purpose, kind, host_action, owner, version, permissions summary, requires_confirmation — **no** secrets.
3. CBAC: same class of auth as skills catalog (authenticated + app-scope); deny anonymous.
4. AppScopeMixin / org isolation respected.
5. Tests: 401 anon, 200 auth returns seeded/synced rows, scoped isolation if applicable.
6. Evidence: `docs/pulse/evidence/PEC-R1-capabilities-list.md`
7. Update Active focus Notes; append `## PEC-R1` to TASK-RESULTS.md.

#### Out of scope
- Frontend registry UI (PEC-R2)
- Mutations / create Capability via API
- people/NSR paths

#### Verification Gate
```bash
./manage.sh test ai/tests/test_capability_loader.py ai/tests/test_capability_list_api.py -q
# + any new test file named above
```

---

### Phase PEC-R2 — Frontend: Capabilities registry view (Console)
**Date:** 2026-09-16  
**Worker Role:** frontend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE — Capabilities Console UI + vitest 2026-09-16
**Owner Master:** Pulse
**Depends on:** PEC-R1 (`GET /carbon-api/ai/catalog/capabilities/`)

Wire Console Capabilities registry UI (deferred from PEC-6B) onto the new list API.

#### Files to Read First
- `carbon-frontend/src/pages/admin/ai/SkillsPanel.jsx` (pattern to reuse)
- `carbon-frontend/src/api/aiCatalog.js`
- `carbon-frontend/src/pages/admin/ai/ProcessRegistry.jsx` (optional sibling pattern)
- AIWorkspace Console tabs mounting SkillsPanel
- `.ai-toolkit/shared/{frontend-ready,design-system,api-contract}.md` · RULE_8/10/23

#### Tasks
1. Add `listCapabilities()` in `api/aiCatalog.js` → GET catalog/capabilities/
2. Add Capabilities panel (or tab) in Console — reuse SkillsPanel layout patterns (DataGrid, loading/empty/error); **read-only** (no mutate)
3. Show: business_name, kind, purpose, owner, version, requires_confirmation; never leak host_action internals in primary UI if RULE_23 prefers outcomes — host_action OK in detail drawer as technical id for admins
4. CBAC: require same console view capability as Skills/Processes (`ai:view_console` or existing pattern)
5. Vitest + lint + build proof
6. Evidence note in `docs/pulse/evidence/PEC-R2-capabilities-ui.md`
7. TASKS Active focus + TASK-RESULTS `## PEC-R2`

#### Out of scope
- Backend changes
- people/my/team UI
- Skill promote/reject changes

#### Verification Gate
```bash
cd carbon-frontend && npm run lint && npx vitest run src/__tests__/CapabilitiesPanel.test.jsx && npm run build
```

---

### Phase PEC-R3 — Backend: AI suite debt (partitioned)
**Date:** 2026-09-16  
**Worker Role:** backend-worker / debugger-fixer  
**Recommended Model:** Composer  
**Status:** DONE — 104 passed (debt partition) + L2 live JWT PASS 2026-09-16  
**Owner Master:** Pulse  
**Depends on:** Master PEC audit residuals outside PEC core

Clear historically failing / erroring AI suite modules outside PEC core: `durable`, `chat_stream`, `ports`, `people_grounding`, `web_search`. Prefer product fixes; update stale tests only when product is correct. No full `pytest ai`; maxfail=5; Pulse seat `backend/ai/**` only.

#### Tasks
1. Inventory failures in the five test files (run if DB up; else static).
2. Fix product or test defects (no skip silence unless env-gated + documented).
3. Evidence: `docs/pulse/evidence/PEC-R3-ai-suite-debt.md`
4. Active focus Notes + TASK-RESULTS `## PEC-R3`

#### Out of scope
- L2 live JWT / L4 browser · NSR · reopening PEC/ECF

#### Verification Gate
```bash
./manage.sh test ai/tests/test_ports.py -q --maxfail=5
./manage.sh test ai/tests/test_chat_stream.py -q --maxfail=5   # needs Postgres for django_db
./manage.sh test ai/tests/test_web_search_tool.py -q --maxfail=5
./manage.sh test ai/tests/test_durable.py -q --maxfail=5       # needs Postgres
./manage.sh test ai/tests/test_people_grounding.py -q --maxfail=5  # needs Postgres
```

**Shipped 2026-09-16 (PARTIAL):** ports 22/22; chat_stream non-DB 5/5; web_search non-DB 19/19; durable resume/replay test drift fixed statically; people_grounding static OK. **BLOCKED:** all django_db until Postgres.

---

## End PEC-R3

### Phase PEC-R4 — L4 Playwright: Console Capabilities
**Date:** 2026-09-16  
**Worker Role:** frontend-worker / qa  
**Recommended Model:** Composer  
**Status:** DONE — journey-16 **3/3 PASS** (2026-09-16 after install-deps); IDE browser L4 earlier  
**Owner Master:** Pulse  
**Depends on:** PEC-R2 Capabilities Console UI

Prove Console Capabilities registry UI (PEC-R2) with a single Playwright journey; optional Skills Catalog smoke (no promote/deny).

#### Tasks
1. Add/extend e2e journey (`journey-16-pulse-capabilities.spec.ts` preferred).
2. Login → `/admin/ai/capabilities` → loading settles to grid or empty (no crash); if API rows, assert `business_name`.
3. Skills tab/route smoke only.
4. Run one-file Playwright; document BLOCKED with exact error if env blocks.
5. Evidence: `docs/pulse/evidence/PEC-R4-l4-capabilities.md`
6. Active focus Notes + TASK-RESULTS `## PEC-R4`

#### Out of scope
- Full suite · manage.sh start/stop · Postgres · people/my/team · skill promote/deny mutations

#### Verification Gate
```bash
cd carbon-frontend && node node_modules/@playwright/test/cli.js test \
  --config=e2e/playwright.config.ts \
  e2e/journeys/journey-16-pulse-capabilities.spec.ts --reporter=line
```

**Shipped 2026-09-16 (PARTIAL):** spec + evidence. **BLOCKED:** Chromium headless needs `libnspr4.so` (and related) — `sudo playwright install-deps` required on host. Re-open to DONE when journey-16 green.

### Phase PEC-R5 — Seed live Capability registry
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Status:** DONE — 31 caps live; GET catalog/capabilities/ 200 non-empty (app_identifier=people)  
**Owner Master:** Pulse  
**Evidence:** `docs/pulse/evidence/PEC-R5-capability-seed.md`  
**Residual:** skills catalog empty → closed by PEC-R6  

### Phase PEC-R6 — Seed live Skills Catalog
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Status:** DONE — 1 skill on `nibras`; catalog list 200 count 1 (gate-promoted)  
**Owner Master:** Pulse  
**Evidence:** `docs/pulse/evidence/PEC-R6-skills-seed.md`  
**Command:** `DJANGO_BRAND=nibras python manage.py seed_catalog_skills`

### Phase ECF-leave-fetch — Host fetch_fn for leave_record
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Status:** DONE — live LeaveRecord entity_fetch scoped via `employee__org_unit_id__in`  
**Owner Master:** Pulse  
**Evidence:** `docs/pulse/evidence/ECF-leave-fetch-fn.md`  
**Tests:** `ai/tests/test_ecf_leave_fetch_fn.py` (7 passed)

---

## Nibras / People — open or audit-needed (summaries)

## Phase NIR-3C — Backend: Payroll-run orchestration service

**Date:** 2026-08-30
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — verified NSR-0 2026-09-16 (PayrollRunService + test_payroll_service)

### Files to Read First
- `backend/people/models.py` (`PayrollRun`, `PayslipLine`, `Employee`, `Loan`, `LoanInstallment`, `AttendanceRecord`, `LeaveRecord`)
- `backend/people/calculation_engine.py` (NIR-3B outputs)
- `backend/emissions/models.py` (`Calculation.create_from_data_row` — the source-row provenance pattern)
- `docs/NIBRAS-MASTER-STRATEGY.md` §8.2 (pipeline)

> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).

## Phase NIR-5A — Backend: People governed-lookup migration (FK to ReferenceValue, drop code strings)

**Date:** 2026-08-30
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** READY
**Canonical spec:** `docs/DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md` (§3 Bucket 1, §4, §6) + ADR-0027

### Objective
Replace every Bucket-1 metadata field in `people` with a real `ForeignKey` to
`mdm.ReferenceValue`, removing the free-text/soft-code duplicates and the string
mirrors. This is the **models + migration** phase only (serializers/views in
NIR-5B).

### Files
- `backend/people/models.py` — the only model file edited.
- New migration `backend/people/migrations/XXXX_governed_lookup_fks.py`.


> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).

## Phase NIR-5B — Backend: Governed value resolution (serializers/views/seeds/DQ)

**Date:** 2026-08-30
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** READY
**Depends on:** NIR-5A
**Canonical spec:** `docs/DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md` §4 + ADR-0027

### Objective
Build the single shared value-resolution seam and wire every Bucket-1 field
through it; update seed commands to the new FK shape.

### Files
- `backend/mdm/serializers.py` — add `GovernedValueField` (or `GovernedValueSerializer`): read → `{ id, code, label, set }`; write accepts `id` **or** `code`, resolves to `ReferenceValue` within the declared `set_name`, validates current-ness, emits `ValidationError` otherwise.
- `backend/people/serializers.py` — replace `_validate_reference_code` usage: each Bucket-1 field uses the `GovernedValueField` with its `set_name`. Update `EmployeeSerializer`/`PositionSerializer`/`BenefitTypeSerializer`/`ComplianceRuleSerializer` and any serializer for the other 8 models that expose a Bucket-1 field.
- `backend/people/management/commands/seed_gofsco.py` — update seeded employees/positions/benefits to write the FK (by code, resolved through the same helper), not string codes.
- `backend/people/views.py` — add `select_related('*_value__reference_set')` (or a `prefetch`) on list/detail querysets so read joins are cheap.

> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).

## Phase NIR-5C — Backend: Seed the 7 new reference sets (admin data)

**Date:** 2026-08-30
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** READY
**Depends on:** NIR-5A (sets can be seeded in parallel with 5B)
**Canonical spec:** `docs/DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md` §3 Bucket 1

### Objective
Seed the seven ReferenceSets that do **not** yet exist, so the NIR-5A FKs can be
satisfied. RULE_16: this is **admin data**, entered via a management command
(the sanctioned admin-entry path), never created by serializer code.

### New sets + initial values (canonical codes)
| Set `name` | `slug` | Initial codes |
|---|---|---|
| `grade` | `grade` | `G1`…`G10` (job grades) |

> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).

## Phase NIR-5D — Frontend: People pages render nested governed values + dropdowns source reference sets

**Date:** 2026-08-30
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** PLANNED
**Depends on:** NIR-5B
**Canonical spec:** `docs/DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md` §4 + TASKS.md NIR-4A patterns

### Objective
Adapt the People pages to the FK-only read shape and source create/edit dropdowns
from the governed reference sets (via the MDM reference-value API), not hardcoded
option lists.

### Scope (pointer — expand at dispatch)
- `carbon-frontend/src/api/people.js` + new `api/referenceData.js` (fetch values
  for a set: `mdm/reference-values/?reference_set=<name>` or the existing
  `mdm/reference-sets/` surface).

> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).

## Phase NIR-6A — Backend: Single-root OrgUnit invariant + instance-gated seeds

**Date:** 2026-08-30
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** READY
**Canonical spec:** `docs/DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md` §2 (ADR-0028) + §6

### Objective
Enforce "one deployment = one root `OrgUnit`" and stop the AASTMT↔GOFSCO tree
mingling at the seed layer.

### Files
- `backend/mdm/models.py` — add `clean()` to `OrgUnit`: a unit with `parent=None`
  is only allowed when no other active `parent=None` root exists for the
  deployment (block creating a second root; allow re-parent of a stale root).
  Emit a `ValidationError` on violation. (Keep idempotent seed re-runs working.)
- `backend/mdm/views.py` — `OrgUnitViewSet.get_queryset()` defaults to the

> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).

## Phase NIR-6B — Frontend: Org-unit dropdown scoped to deployment root

**Date:** 2026-08-30
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** PLANNED
**Depends on:** NIR-6A
**Canonical spec:** `docs/DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md` §2 (ADR-0028)

### Objective
`fetchOrgUnits` (and every org-unit dropdown/tree in People + Carbon) renders only
the deployment's own root subtree, shown as a tree (not a flat global list).

### Scope (pointer — expand at dispatch)
- `carbon-frontend/src/api/orgUnits.js` — default to the root-subtree endpoint
  (e.g. `mdm/org-units/?root=1` or `/tree/`) and return a nested structure.
- `PositionsPage.jsx`, `PayrollRunsPage.jsx` — replace the flat `orgUnits.map(...)`
  `MenuItem` list with a nested/indented tree (group by `full_path` or

> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).

## Phase NIR-7A — Backend: Compensation ledger remediation (service, authz, migration, admin, tests)

**Date:** 2026-09-02
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — verified NSR-0 2026-09-16 (compensation_service + test_compensation)
**Depends on:** (none — remediates unphased compensation work)
**Canonical spec:** `ADR-0029` (`.ai-toolkit/decisions/0029-compensation-ledger.md`)

### Objective
Repair the compensation ledger to the toolkit contracts: business logic out of the
view into a service, correct write authorization, `basic_salary`→ledger data
migration, admin registration, and test coverage. No API shape change.

### Scope
1. **New service** `backend/people/compensation_service.py` — `CompensationService`
   with:
   - `current_lines(employee, as_of=None)` → QuerySet of open/effective rows.

> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).

## Phase NIR-7B — Frontend: Compensation pay tab remediation (SystemDialog, tokens, i18n)

**Date:** 2026-09-02
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — verified NSR-0 2026-09-16 (tabs/EmployeePayTab.jsx SystemDialog)
**Depends on:** NIR-7A (API envelope is unchanged; can proceed in parallel)
**Canonical spec:** `ADR-0029` + `.ai-toolkit/roles/shared/compact-ui.md`,
`.ai-toolkit/roles/shared/design-system.md`

### Objective
Rewrite `carbon-frontend/src/apps/people/tabs/EmployeePayTab.jsx` to comply with
compact-ui/design-system and i18n contracts. No behavior regression.

### Scope
1. **SystemDialog, not Drawer** — replace the raw MUI `Drawer` `AddCompLineDrawer`
   with the existing `SystemDialog` component (`src/components/SystemDialog.jsx`),
   matching sibling pages (`EmployeesPage`, `BenefitsPage`).

> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).


---

# e-Office Correspondence Expansion — OF-15 … OF-20 (requests journey + workflow graph)

> **Driver:** the e-Office correspondence engine is generic and fully wired for the
> *state machine* (draft → submitted → sent_back/rejected/approved, multi-step
> `approver_chain`, per-event timeline), but only **`leave_request`** has a create
> path today (`POST /people/me/leave/` → `people/self_views.py`). The other five
> governed types (`loan_request`, `profile_change`, `internal_memo`, `circular`,
> `decision`) are seeded `ReferenceValue`s with no submit endpoint or UI. The
> "workflow graph" is currently a **vertical stepper** (`ApproverChainStepper`)
> — not a DAG. HR can see the 6-tab employee 360 but has **no Requests tab** and
> **no endpoint to list one employee's correspondence** (the `correspondence`
> list is self-scoped to `requester=request.user`).
>
> **Canonical layering (NON-NEGOTIABLE):** `correspondence` NEVER imports `people`;
> `people` reaches the engine only via `correspondence.fsm`/`services`/`models`.
> Governed enums stay `mdm.ReferenceValue` FKs. Every transition emits a
> `CorrespondenceEvent` + `emit_governance_event`.
>
> **Dependency order (do NOT reorder):** OF-15 → OF-16 (backend, can run in
> parallel) → OF-17 (needs OF-15) · OF-18 (independent, needs neither) ·
> OF-19 (needs OF-16) → OF-20 (QA, last). One phase = one worker session, one domain.

| Phase | Goal | Domain | Deps | Status |
|-------|------|--------|------|--------|
| OF-15 | Generic submit endpoint + subject adapters for the 5 remaining types + acknowledge/review transitions | backend | OF-14 | DONE |
| OF-16 | HR/admin correspondence scoping (list by employee/org/type) + correspondence notifications API (list + mark-read) | backend | — | DONE
| OF-17 | "New Request" multi-type composer + extend MyRequests/RequestDetail | frontend | OF-15 | DONE |
| OF-18 | Workflow DAG graph component + stepper↔graph toggle | frontend | — | DONE |
| OF-19 | HR 360 "Requests" tab in EmployeeDetailPage (view all of an employee's correspondence) | frontend | OF-16 | DONE |
| OF-20 | QA validation (4-layer) of the expanded e-office | qa | OF-17,18,19 | DONE |

---

### Phase OF-15 — Backend: generic submit + subject adapters + acknowledge/review transitions
**Role:** backend-worker · **Depends on:** OF-14 · **Model:** DeepSeek V4-Flash

#### Problem
Only `leave_request` is creatable. The engine already supports `subject=None`
(`submit_correspondence` skips the DQ gate) and the router already maps
`manager`/`hr`/`finance`/`specific_user`/`any_admin` roles. Three gaps:
(1) no generic create for payload-only types, (2) the `intent` field allows
`acknowledge`/`review` but `fsm` has no transition for them (an `internal_memo`
should be *acknowledged*, not "approved"), (3) the `finance` role resolves to
`[]` in `routing.py` (auto-skip) — a loan policy with a finance step would be
silently dropped, which is a thin/broken behaviour, not a real workflow.

#### Change
1. **Generic create endpoint (payload-only types)** — `backend/correspondence/views.py`:
   `POST correspondence/` (a `create` action on the ViewSet, gated by
   `correspondence:submit`). Accepts `{corr_type, title, payload, org_unit}` →
   creates a `Correspondence` with `subject_type=''`, `subject_id=None`,
   `requester=request.user`, `status='draft'`, then
   `fsm.submit_correspondence(corr, by=user, subject=None)`. Reuse the
   `CorrespondenceDetailSerializer` for the 201. Map the same engine exceptions
   (`SubmissionBlocked`→400, `PolicyNotFound`→400, `InvalidTransition`→409) via
   the existing `_transition`-style helper or an explicit try/except.
2. **`acknowledge` + `review` transitions** — `backend/correspondence/fsm.py`:
   add `acknowledge(corr, by, comment)` that marks the current step
   `decision='acknowledged'` and advances (mirrors `approve` but emits
   `event_type='acknowledged'`, no "approved" semantics), and `review(...)`
   (`decision='reviewed'`). Add a generic `act(corr, by, intent, comment)`
   dispatcher so `views.py` needs one action route, not three. Extend
   `correspondence/urls.py` with `POST correspondence/{id}/acknowledge/`.
3. **Subject adapters (typed types stay in `people`)** — `backend/people/`:
   - `POST /people/me/loan/` (loan_request): create `people.Loan` + `Correspondence`
     (`subject_type='people.Loan'`), submit via fsm. **`Loan.STATUS_CHOICES` is
     `active/paid_off/cancelled` — add `'draft'` (migration) and create the Loan in
     `draft` status (mirrors `LeaveRecord.status='draft'`).** Validate
     principal/interest_rate/term_months/start_date/loan_type before submission.
   - `POST /people/me/profile-change/` (profile_change): no new model — create a
     `Correspondence` with `subject_type='people.Employee'`, `subject_id=profile.pk`,
     `payload` = `{field: {from, to}, …}`; the HR approver applies the diff on approve.
   Keep `leave_request` untouched (already works). Memo/circular/decision use the
   generic OF-15.1 endpoint (no subject).
4. **Seed default policies for the 5 new types** — extend
   `backend/correspondence/management/commands/seed_correspondence.py`: add a
   `WorkflowPolicy` per new `corr_type` (default single step): `internal_memo`
   → `any_admin`/`acknowledge`, `circular` → `any_admin`/`acknowledge`,
   `decision` → `manager`/`approve`, `loan_request` → `manager` then `finance`
   (two steps), `profile_change` → `hr`/`approve`. Idempotent (`update_or_create`).
5. **Finance approver resolution (fix `finance` → `[]` auto-skip)** — resolve the
   finance step to a REAL pool, not an empty list:
   - `backend/accounts/capabilities.py`: add `CORRESPONDENCE_FINANCE` (key
     `correspondence:finance`, domain `correspondence`, action `finance`,
     category `admin`) to the capability registry + `ALL_CAPABILITIES`; add
     `finance_group` to `GROUP_CAPABILITIES` mapping `{correspondence:finance,
     correspondence:submit, my:access}`.
   - `backend/accounts/constants.py`: add `FINANCE_GROUP = "finance_group"` (wire
     into `GROUP_BRAND_SCOPE`/`PROTECTED_GROUPS` exactly as the other people groups
     are), then `backend/accounts/management/commands/bootstrap_platform.py`: add a
     `finance_group` `GROUP_DEFS` entry so it is created on bootstrap.
   - `backend/correspondence/routing.py`: `role == 'finance'` →
     `_users_with_capability('correspondence:finance')` (delete the `[]` literal).
   - Update `backend/accounts/tests/test_capability_rbac_extensive.py` expected-
     groups assertion to include `finance_group`.
   - Seed one finance approver in `seed_correspondence.py` (assign an existing
     employee user to `finance_group` via `ScopedRole`), so the live loan
     workflow has a real finance approver.

#### Files to Change
- `backend/correspondence/views.py` (+ `create`, `acknowledge` actions)
- `backend/correspondence/fsm.py` (+ `acknowledge`/`review`/`act`)
- `backend/correspondence/urls.py` (+ `acknowledge` route)
- `backend/correspondence/routing.py` (finance → `correspondence:finance`)
- `backend/accounts/capabilities.py` (+ `CORRESPONDENCE_FINANCE`, `finance_group`)
- `backend/accounts/constants.py` (+ `FINANCE_GROUP`)
- `backend/accounts/management/commands/bootstrap_platform.py` (+ finance group def)
- `backend/accounts/tests/test_capability_rbac_extensive.py` (expected groups)
- `backend/people/models.py` (+ `'draft'` in `Loan.STATUS_CHOICES`) + migration
- `backend/people/self_views.py` (+ `LoanSelfCollectionView`, `ProfileChangeSelfView`)
- `backend/people/urls.py` / `self_urls.py` (+ routes)
- `backend/correspondence/management/commands/seed_correspondence.py` (+ 5 policies + finance approver)
- `backend/correspondence/tests/test_api.py`, `test_fsm.py`, `backend/people/tests/` (new tests)

#### DO NOT TOUCH
- Frontend · `correspondence` importing `people` (never) · leave journey (regression).

#### Verification Gate (Master runs — paste output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python -m pytest correspondence people -q --maxfail=5 --disable-warnings -p no:cacheprovider
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
```
Report: `correspondence` + `people` suites green; new tests cover generic submit,
acknowledge/review transitions, loan/profile-change subject creation, AND finance
routing (finance step resolves to a real approver, never auto-skips); `makemigrations
--check` confirms the Loan draft-status migration is applied; no migrations drift.

---

### Phase OF-16 — Backend: HR/admin scoping + correspondence notifications API
**Role:** backend-worker · **Depends on:** — (independent; runs parallel to OF-15) · **Model:** DeepSeek V4-Flash

#### Problem
(1) The `correspondence` list is self-scoped — HR (`people:manage` /
`correspondence:admin`) cannot list an employee's requests to answer "what is
pending for this person?". (2) `fsm.notify()` writes
`correspondence.models.Notification` rows but there is **no API** to read them —
managers/requesters never see "action needed" / "status changed" in-app.

#### Change
1. **Employee-scoped correspondence list (HR)** — `backend/people/views.py`: add
   `GET /people/employees/{id}/correspondence/` (permission `PeopleAccess`), returns
   the employee's correspondence (`requester__employee_profile` OR `subject_id`
   match) via `CorrespondenceSerializer`, paginated. `people` importing
   `correspondence.serializers` is allowed (one-way).
2. **Widen the admin list filter** — `backend/correspondence/views.py`: when the
   caller holds `correspondence:admin`, allow `?requester=`, `?employee=`,
   `?org_unit=`, `?corr_type=`, `?status=` on `GET correspondence/` (non-admin
   stays self-scoped). Add a `correspondence:admin` object check.
3. **Notifications API** — `backend/correspondence/views.py` + `urls.py`: add
   `GET correspondence/notifications/` (self-scoped, `is_read` filter, unread
   count) and `POST correspondence/notifications/{id}/read/` +
   `POST correspondence/notifications/read-all/`. Serializer for
   `correspondence.models.Notification` (id, title, body, type, is_read,
   correspondence reference_no, created_at).

#### Files to Change
- `backend/people/views.py` + `urls.py` (+ employee correspondence list)
- `backend/correspondence/views.py` + `urls.py` (+ admin filters, notification actions)
- `backend/correspondence/serializers.py` (+ `NotificationSerializer`)
- `backend/correspondence/tests/test_api.py`, `backend/people/tests/` (new tests)

#### Verification Gate (Master runs — paste output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python -m pytest correspondence people -q --maxfail=5 --disable-warnings -p no:cacheprovider
```
Report: HR can list an employee's correspondence; admin filters work; notifications list/read/read-all return correct unread counts; non-admin list stays self-scoped.

---

### Phase OF-17 — Frontend: "New Request" multi-type composer + richer request list
**Role:** frontend-worker · **Depends on:** OF-15 · **Model:** DeepSeek V4-Flash

#### Objective
Let an employee submit **any** governed type (not just leave) from `/my`, and
render non-leave payloads correctly in the request list/detail.

#### Deliverables
1. `src/apps/my/components/NewRequestDialog.jsx` — type selector
   (leave/memo/circular/decision/loan/profile-change) driving a dynamic form;
   routes to the right API: leave → `POST people/me/leave/`, loan →
   `POST people/me/loan/`, profile-change → `POST people/me/profile-change/`,
   memo/circular/decision → `POST correspondence/` (generic). Show approver-chain
   preview + confirm. i18n EN/AR.
2. `src/api/my.js` — add `submitLoanRequest`, `submitProfileChange`,
   `submitGenericCorrespondence`; keep `apiFetch` only.
3. `src/apps/my/MyRequests.jsx` + `components/RequestTable.jsx` — render
   non-leave payloads (memo title/body, circular, decision, loan amount, profile
   change field diffs) as a small payload summary instead of leave dates. The
   `corr_type` filter chips already exist — verify they show all 6 types.
4. `src/apps/my/MyDashboard.jsx` — add a "New Request" quick action next to
   "Request Leave".

#### Screen Spec (RULE_29 — required before code)
**Story:** As an employee, I want to submit any request type (leave, loan, memo,
circular, decision, profile change) from one place, so I don't have to learn six
different forms. **Acceptance:** given type X → form X shows only X's fields; submit
→ 201 + success toast + list refreshes; invalid input → inline field errors; no
policy for type → clear message; non-employee → 403 handled.
**Journey:** `/my` → "New Request" → choose type → fill form → review approver
preview → submit → success → `/my/requests`.
**Composition:** `SystemDialog` (NOT raw Dialog) wrapping a type `<Select>` + a
`RequestFormSwitch` (per-type field sets) + `ApproverChainPreview`; submit button
`disabled` while `submitting`. Reuse `RequestTable`/`SummaryCard` for list/detail.
**State Matrix:** page `idle/loading/empty/error/loaded`; dialog `open/closed`;
submit `idle/submitting/error/success`; type selector `default/selected`.
**Data Contract:** `GET /carbon-api/correspondence/` (self list, `corr_type`/
`status` filters); `POST /carbon-api/people/me/leave/`, `/people/me/loan/`,
`/people/me/profile-change/`, `POST /carbon-api/correspondence/` (generic) → 201 |
400 field errors | 403. **A11y:** focus trap in dialog, `aria-live` on submit error,
labels on all inputs. **Performance:** lazy-load dialog, memoize type→field map,
debounce not needed (no search). **i18n/RTL:** every label via `t()`, keys in BOTH
`en` + `ar`; type names in Arabic.

#### Files to Change
- `src/apps/my/components/NewRequestDialog.jsx` (new)
- `src/api/my.js`
- `src/apps/my/MyRequests.jsx`, `components/RequestTable.jsx`, `MyDashboard.jsx`
- `src/i18n/locales/{en,ar}/my.json`

#### DO NOT TOUCH
- Backend · `src/apps/team/**` · raw fetch · inline hex/sx.

#### Verification Gate (Master runs — paste output)
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
node scripts/check-i18n-keys.js
npm run lint
npm run build
```
Report: i18n parity green; lint 0; build clean; smoke: submit a memo (generic) and a loan, both appear in My Requests with correct type labels.

---

### Phase OF-18 — Frontend: Workflow DAG graph + stepper↔graph toggle
**Role:** frontend-worker · **Depends on:** — (approver_chain already in detail response)

#### Objective
Replace the *only-vertical-stepper* view with an optional **node-edge workflow
graph** so the approval path is visualized as a DAG (steps as nodes colored by
decision: pending/current/approved/rejected/skipped; edges = flow). Keep the
stepper as the default and add a toggle.

#### Deliverables
1. `src/apps/my/components/WorkflowGraph.jsx` (new) — pure presentational DAG
   from `approver_chain` (`order, role, intent, decision, user_ids, comment,
   decided_at`) + `current_step`. Horizontal/SVG layout (or reuse
   `components/graph/` primitives). Color = status, NOT color-only (label each
   node with role/intent/decision text). RTL-safe.
2. Add a Stepper ↔ Graph toggle to `src/apps/my/components/RequestDetail.jsx` and
   `src/apps/team/TeamRequestDetail.jsx` (reuse `WorkflowGraph`). Default = stepper.
3. i18n: `workflowGraph` / `workflowStepper` toggle labels + node legend.

#### Screen Spec (RULE_29 — required before code)
**Story:** As an employee or manager, I want to see the approval path as a graph,
so I understand who is next and where it stalled. **Acceptance:** graph renders
one node per `approver_chain` step + a terminal node; node shows role/intent/decision
as TEXT (never color alone); `current_step` node highlighted; condition-skipped/
auto-approve steps visibly distinct from approved/rejected; empty chain → graph
empty state; RTL mirrors arrow direction.
**Composition:** `WorkflowGraph` = SVG/Styled nodes + edges built from
`approver_chain[]` + `current_step`; a `ToggleButtonGroup` (Stepper | Graph) in
`RequestDetail` + `TeamRequestDetail`. Reuse `components/graph/` primitives if they
exist — else one new presentational component (no data fetching inside).
**State Matrix:** node `pending/current/approved/rejected/acknowledged/reviewed/
skipped(auto|condition)/sent_back`; graph container `loading/empty/loaded` (reuses
detail's fetched data — no separate fetch).
**Data Contract:** consumed from the already-fetched `CorrespondenceDetailSerializer`
(`approver_chain` = `[{order, role, intent, decision, decided_by, decided_at,
comment, user_ids, auto_approve, can_skip, skip_if_self, skipped}]`, `current_step`
int, `status` str). No new endpoint. **A11y:** nodes are buttons/`tabIndex=0` with
`aria-label` (`role + intent + decision`); legend is text-based; not color-only.
**Performance:** pure function of props, `React.memo`, no effects, SVG is light
(< 50 nodes). **i18n/RTL:** legend + toggle labels via `t()` in BOTH catalogs; RTL
flips edge direction.

#### Files to Change
- `src/apps/my/components/WorkflowGraph.jsx` (new)
- `src/apps/my/components/RequestDetail.jsx`, `src/apps/team/TeamRequestDetail.jsx`
- `src/i18n/locales/{en,ar}/{my,team}.json`

#### DO NOT TOUCH
- Backend · AI `PlanDagGraph` (unrelated) · raw fetch · inline hex/sx.

#### Verification Gate (Master runs — paste output)
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
node scripts/check-i18n-keys.js
npm run lint
npm run build
```
Report: i18n parity green; lint 0; build clean; smoke: open an approved request, toggle graph → nodes show approved/rejected/skipped correctly.

---

### Phase OF-19 — Frontend: HR 360 "Requests" tab (view all of an employee)
**Role:** frontend-worker · **Depends on:** OF-16 · **Model:** DeepSeek V4-Flash

#### Objective
HR staff (holding `people:view`/`people:manage`) can open an employee's 360 and
see **all their correspondence** (leave, loans, memos, …) in a new "Requests" tab,
drill into each, and see the full timeline/chain — closing "HR can view all about
an employee".

#### Deliverables
1. `src/apps/people/tabs/EmployeeRequestsTab.jsx` (new) — `GET
   people/employees/{id}/correspondence/`; table (reference, type, title, status,
   created, resolved) + row → detail dialog/drawer (reuse `SummaryCard` +
   `ApproverChainStepper`/`WorkflowGraph` + `RequestTimeline` from `apps/my/`).
2. `src/api/people.js` — add `fetchEmployeeCorrespondence(id)`.
3. `src/apps/people/EmployeeDetailPage.jsx` — register the `Requests` tab in
   `TAB_KEYS`/`TAB_COMPONENTS` (only render for users with `people:view`).
4. i18n EN/AR for the new tab.

#### Screen Spec (RULE_29 — required before code)
**Story:** As HR, I want to see every request an employee has made (leave, loan,
memo, …) in one tab, so I can answer "what is pending for this person?".
**Acceptance:** tab lists all correspondence for the employee (reference, type,
title, status, created, resolved); filter by status/type; click a row → detail
(timeline + chain/graph); empty → "no requests yet"; 403 (no `people:view`) → tab
hidden; loading → skeleton.
**Composition:** `EmployeeRequestsTab` (inside `BaseDetailPage` tab) = `PageHeader`
(mini) + `StandardDataGrid`/table (paginated) + detail `Dialog` reusing
`SummaryCard` + `ApproverChainStepper`/`WorkflowGraph` + `RequestTimeline` from
`apps/my/`. Register in `TAB_KEYS`/`TAB_COMPONENTS`; gate on `people:view` capability.
**State Matrix:** `idle/loading/loading-empty/empty/loaded/partial/error/forbidden`;
row `selected`; detail dialog `open/closed`; filter `default/active`.
**Data Contract:** `GET /carbon-api/people/employees/{id}/correspondence/` →
paginated `CorrespondenceSerializer` (`count/results`); 403 = hidden tab; 404 =
unknown employee. **A11y:** table has row headers + focus-visible; dialog
focus-trap; status = badge + label. **Performance:** paginate >50 rows; lazy-load
detail dialog; memoize filter map. **i18n/RTL:** tab + column headers + status
labels via `t()` in BOTH catalogs.

#### Files to Change
- `src/apps/people/tabs/EmployeeRequestsTab.jsx` (new)
- `src/api/people.js`
- `src/apps/people/EmployeeDetailPage.jsx`
- `src/i18n/locales/{en,ar}/people.json`

#### Verification Gate (Master runs — paste output)
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
node scripts/check-i18n-keys.js
npm run lint
npm run build
```
Report: i18n parity green; lint 0; build clean; smoke: HR opens employee → Requests tab lists their correspondence; drill-in shows timeline.

---

### Phase OF-20 — QA validation (4-layer) of the expanded e-office
**Role:** qa-validator · **Depends on:** OF-15…OF-19 · **Model:** DeepSeek V4-Flash

#### Context
Verify the expanded e-office end-to-end; no new features. Report deficiencies with file:line + repro.

#### Layers
1. **Static/contract:** grep for `GenericForeignKey`/`ContentType` in
   `correspondence/`, hardcoded governed enums, `raw fetch(` in `src/apps/my/` +
   `src/apps/team/`, naive `datetime.now()`, `print()` debug.
2. **Unit:** one app at a time — `correspondence`, `people`, `accounts/tests/test_correspondence_caps.py`.
3. **API integration:** DRF test client walk — submit memo (generic) → inbox →
   acknowledge; submit loan → manager approve → finance approve; submit
   profile-change → hr approve; HR lists employee correspondence; notifications
   read/read-all. Confirm `correspondence` never imports `people`.
4. **Frontend build + smoke:** `npm run build` + `check-i18n-keys.js`; Playwright
   smoke of `/my` new request + `/team` + HR 360 Requests tab.

#### Verification Gate (Worker runs + reports output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python -m pytest correspondence people -q --maxfail=5 --disable-warnings -p no:cacheprovider
/home/ahmed/aast/carbon/.venv/bin/python -m pytest accounts/tests/test_correspondence_caps.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
cd /home/ahmed/aast/carbon/carbon-frontend
npm run build && node scripts/check-i18n-keys.js
```
Report: 4-layer pass/fail matrix + deficiencies with file:line + repro.

---

# Leave Policy Registry — LPR series
# Trigger: Nibras HR — the flat "one row per leave type" config tab in
# PeopleConfigPage is not a real registry. Replace with a named, lifecycle-managed,
# applicability-scoped policy registry + detail 360 + propagation + versioning.
# Full spec: tasks/TASK-LPR-POLICY-REGISTRY.md

## Phase LPR-1A — Backend: LeavePolicy registry model + API
**Role:** backend-worker · **Depends on:** OF-14 (leave_type → ReferenceValue FK) · **Model:** DeepSeek V4-Flash
**Status:** DONE — verified 2026-09-06 (migration 0021 applied, 182 people tests pass incl. 5 new LPR-1A tests)

### Objective
Evolve `LeavePolicy` from a one-row-per-leave-type config table into a named,
lifecycle-managed, applicability-scoped registry. Non-destructive migration
backfills existing rows. Add `employee_count` annotation + a basic `propagate`
action so the LPR-1B registry grid has real data to display.

### Files to Read First
- `backend/people/models.py` — `LeavePolicy` (~296), `Employee` (~76), `LeaveEntitlement` (~365)
- `backend/people/serializers.py` — `LeavePolicySerializer` (~222)
- `backend/people/views.py` — `LeavePolicyListCreateView` (~732) + `LeavePolicyDetailView` (~741)
- `backend/people/urls.py` — `leave-policies/` routes (~84-86)

### What to Build
1. **Model — add to `LeavePolicy`** (all null/blank-safe, non-breaking):
   - `name` `CharField(max_length=200, blank=True)` — human-readable policy name (primary identity).
   - `description` `TextField(blank=True)`.
   - `status` `CharField(choices=[('draft','Draft'),('active','Active'),('deprecated','Deprecated')], default='active')`.
   - `effective_from` `DateField(null=True, blank=True)`.
   - `effective_to` `DateField(null=True, blank=True)`.
   - `applies_to_org_units` `M2M('mdm.OrgUnit', blank=True, related_name='+')` — empty = all org units.
   - `applies_to_contract_types` `JSONField(default=list, blank=True)` — list of contract_type codes; empty = all.
   - Keep `is_active` (transition compat) but document `status` as the lifecycle source.
   - `__str__` → `f"{self.name} ({self.leave_type.code})"`.
2. **Migration** `0021_leave_policy_registry` (schema + data): backfill
   `name = leave_type.code`, `status = 'active' if is_active else 'deprecated'`.
3. **Serializer** — add the new fields; add read-only `employee_count`
   (`IntegerField`), annotated in the view = distinct employees with a
   `LeaveEntitlement` matching the policy's `leave_type` in the current year.
   Keep `leave_type_label`.
4. **View** — `LeavePolicyListCreateView.get_queryset()` annotates `employee_count`.
   Add `propagate` action on `LeavePolicyDetailView`:
   `POST /leave-policies/<id>/propagate/` (body `{ year }`, default current year;
   query `?dry_run=true` → returns `{ eligible, will_create, skipped }` without writing).
   Eligible = active employees matching `gender_restriction`, `min_service_days`,
   `applies_to_org_units`, `applies_to_contract_types`.
5. **URL** — `path('leave-policies/<int:pk>/propagate/', ...)` registered BEFORE `<int:pk>/`.

### DO NOT TOUCH
- `backend/correspondence/*`, `backend/ai/*`, `backend/accounts/*`, `backend/config/settings.py` (other master WIP).
- `LeaveEntitlement` schema — policy↔employee stays indirect via `leave_type` for LPR-1 (proper `policy` FK is LPR-2).
- `backend/people/management/commands/seed_gofsco.py` (other master WIP).

### Verification Gate (Worker runs + reports output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations people --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python manage.py migrate people
/home/ahmed/aast/carbon/.venv/bin/python -m pytest people -q --maxfail=5 --disable-warnings -p no:cacheprovider
```
Report: model diff, migration file name, test output, and a sample list showing `employee_count`.

---

## Phase LPR-1B — Frontend: Policy Registry grid + Policy Detail 360
**Role:** frontend-worker · **Depends on:** LPR-1A · **Model:** DeepSeek V4-Flash
**Status:** DONE — verified 2026-09-06 (build ✓, i18n 2965 keys parity ✓, PeoplePages vitest 7/7 ✓)

### Objective
Replace the flat LeavePolicy tab in `PeopleConfigPage` with a dedicated registry
(`/people/policies`) + a 360 detail page (`/people/policies/:id`), matching the
LPR-1A backend contract.

### Files to Read First
- `carbon-frontend/src/apps/people/PeopleConfigPage.jsx` (LeavePolicy tab to REMOVE)
- `carbon-frontend/src/apps/people/manifest.js` (`navigation.items`)
- `carbon-frontend/src/api/people.js` (`fetchLeavePolicies` + CRUD)
- `carbon-frontend/src/App.jsx` (people routes ~300-311)
- `carbon-frontend/src/shell/Breadcrumbs.jsx` (`/people/config` mapping ~461)
- `carbon-frontend/src/i18n/locales/en/people.json` + `ar/people.json`

### What to Build
1. **Routes** — lazy imports + routes for `/people/policies` (PoliciesPage) and
   `/people/policies/:id` (PolicyDetailPage). Add Breadcrumbs mappings.
2. **`PoliciesPage.jsx`** — FilterBar (leave_type select, status select, search),
   PolicyGrid (name, leave_type badge, status chip, default days, `employee_count`,
   `effective_from`, actions), "New Policy" CTA → create dialog.
   apiFetch-only (RULE_10), FONT theme tokens only (RULE_8).
3. **`PolicyDetailPage.jsx`** — PageHeader + 6 tabs (General / Entitlement /
   Carryover / Eligibility / Workflow / Employees); tab index persisted to
   `localStorage` (RULE_17). Reuse `BaseDetailPage` pattern.
4. **`api/people.js`** — add `propagateLeavePolicy(id, { year, dry_run }, token)`.
5. **Remove** the LeavePolicy tab from `PeopleConfigPage` (TAB_KEYS, form, grid,
   policy state, imports) — keep Overview/Reference/Compliance intact.
6. **`manifest.js`** — add `{ label: 'Policies', path: '/people/policies', role: '*' }`
   under the Configuration group.
7. **i18n** — add `people.json` keys (en + ar) for all new labels.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run build && node scripts/check-i18n-keys.js
npx vitest run src/__tests__/PeoplePages.test.jsx
```

---

## Phase LPR-2A — Backend: propagation service + entitlement `policy` FK + scheduler
**Role:** backend-worker · **Depends on:** LPR-1A · **Model:** DeepSeek V4-Flash
**Status:** DONE — verified 2026-09-06 (migration 0022 applied, 187 people tests pass incl. 5 new service tests)

### Objective
Make propagation production-grade and auditable: give each `LeaveEntitlement` a
nullable `policy` provenance link, extract the inline propagate logic from the view
into a reusable service (DRF-free), and add a year-start management command.

### Files to Read First
- `backend/people/models.py` — `LeaveEntitlement` (~365), `LeavePolicy` (~296)
- `backend/people/views.py` — `LeavePolicyPropagateView` (~807, inline logic to extract)
- `backend/people/serializers.py` — `LeaveEntitlementSerializer`
- `backend/people/services.py` — facade pattern (NO DRF imports)
- `backend/people/management/commands/link_employee_users.py` — command style

### What to Build
1. **Model** — add to `LeaveEntitlement`:
   `policy = models.ForeignKey('LeavePolicy', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')`.
   Migration `0022_leaveentitlement_policy`. Non-breaking (nullable).
2. **Service** — new `backend/people/leave_policy_service.py` (DRF-free, no `rest_framework`/`Response`):
   - `propagate_policy(policy, year=None, *, dry_run=False) -> dict` — move the eligibility filter + preview/create logic out of the view. On create, set `policy=policy` in `defaults` (record provenance). Never overwrite an existing entitlement's `entitled_days` or `policy`.
   - `propagate_all_active(year=None, *, dry_run=False) -> dict` — iterate active policies, aggregate `{ eligible, will_create, will_update, skipped, created, updated, per_policy: [...] }`.
3. **Serializer** — add read-only `policy` (id) and `policy_name` to `LeaveEntitlementSerializer` so provenance is visible in the API.
4. **View** — `LeavePolicyPropagateView.post` becomes a thin wrapper calling `propagate_policy(policy, year, dry_run=dry_run)`; identical response shape as LPR-1A.
5. **Management command** — `backend/people/management/commands/propagate_leave_policies.py`:
   `--year` (default current), `--policy-id` (optional single), `--dry-run`. Calls `propagate_all_active`. Document cron usage in the docstring. Idempotent.
6. **Tests** — `backend/people/tests/test_leave_policy_service.py` (or extend the registry test): service dry_run + create sets `policy` FK; propagate_all_active aggregates; command `--dry-run` runs without error; existing entitlement not overwritten.

### DO NOT TOUCH
- `backend/correspondence/*`, `backend/ai/*`, `backend/accounts/*`, `backend/config/settings.py`
- Any frontend file.

### Verification Gate (Worker runs + reports output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations people --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python manage.py migrate people
/home/ahmed/aast/carbon/.venv/bin/python -m pytest people -q --maxfail=5 --disable-warnings -p no:cacheprovider --create-db
```

---

## Phase LPR-2B — Frontend: batch propagation + entitlement provenance
**Role:** frontend-worker · **Depends on:** LPR-2A · **Model:** DeepSeek V4-Flash
**Status:** DONE — verified 2026-09-06 (build ✓, i18n parity ✓ 3038 keys, vitest 7/7)

### Objective
Surface the new propagation engine in the UI: batch "Propagate All Active" on the
registry page, and show policy provenance on per-employee entitlements.

### Batch API decision (from LPR-2A — CONFIRMED)
LPR-2A added **NO batch HTTP endpoint**. The only HTTP surface is the per-policy
`POST /people/leave-policies/<id>/propagate/` (body `{"year": <int>}`, query
`?dry_run=true`). `propagate_all_active` is callable ONLY via the management
command. So the frontend "Propagate All Active" button MUST loop per active policy:
1. `fetchLeavePolicies()` → filter `status === 'active'` (and legacy
   `!status && is_active`).
2. For each, `POST /people/leave-policies/<id>/propagate/` (the existing
   `propagateLeavePolicy(id, payload, token)` helper from LPR-1B).
3. Aggregate the returned `{eligible, will_create, will_update, skipped}` counts
   and show a single summary (Snackbar). No new backend needed.

### What to Build
1. `PoliciesPage.jsx` — add a "Propagate All Active" toolbar button. On click,
   loop active policies through the existing `propagateLeavePolicy` helper
   (per the batch decision above), aggregate counts, and show a summary Snackbar
   (e.g. "Propagated N policies: M entitlements created"). Disable during the run.
2. `EmployeeLeaveTab.jsx` / `EmployeeDetailPage.jsx` — display the entitlement's
   `policy_name` where the balance/entitlement rows are rendered (the serializer
   already returns read-only `policy` + `policy_name` from LPR-2A).
3. `api/people.js` — add any small helpers if needed (likely none beyond the
   existing `propagateLeavePolicy`; the "all" loop lives in the page).
4. i18n keys (en + ar) for new labels.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run build && node scripts/check-i18n-keys.js
npx vitest run src/__tests__/PeoplePages.test.jsx
```

---

## Phase LPR-3A — Backend: policy versioning (snapshot + fork semantics)
**Role:** backend-worker · **Depends on:** LPR-2A · **Model:** DeepSeek V4-Flash
**Status:** DONE — verified 2026-09-06 (migration 0023 applied, 193 people tests pass incl. 6 new versioning tests; fixed latent `policy`/`policy_version` IntegerField→source=_id serializer bug)

### Objective
Make policy edits auditable and non-destructive. Today a `PATCH /leave-policies/<id>/`
mutates the live `LeavePolicy` in place with no history, so entitlements can never
say *exactly* which configuration created them. Introduce a version ledger: each
configuration change is a new `LeavePolicyVersion` snapshot, and every entitlement
records both the `policy` (the live object) and the precise `policy_version` that
created it. Effective-date transitions are derived from the version chain.

### Files to Read First
- `backend/people/models.py` — `LeavePolicy` (~296), `LeaveEntitlement` (~405, has `policy` FK)
- `backend/people/leave_policy_service.py` — DRF-free service pattern (RULE_3) — extend, do NOT duplicate
- `backend/people/serializers.py` — `LeavePolicySerializer` (~226), `LeaveEntitlementSerializer` (~201)
- `backend/people/views.py` — `LeavePolicyListCreateView`/`LeavePolicyDetailView`/`LeavePolicyPropagateView` (~807)
- `backend/people/urls.py` — leave-policies routes (~88)
- `backend/people/management/commands/propagate_leave_policies.py` — command style

### What to Build

#### 1. Model — new `LeavePolicyVersion` (in `people/models.py`)
```python
class LeavePolicyVersion(models.Model):
    policy = models.ForeignKey(LeavePolicy, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    snapshot = models.JSONField(default=dict)   # full field capture at fork time
    change_summary = models.TextField(blank=True)
    created_by = models.ForeignKey('accounts.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('policy', 'version_number')
        ordering = ['policy', '-version_number']
        verbose_name = 'Leave Policy Version'
        verbose_name_plural = 'Leave Policy Versions'
```
- Add to `LeaveEntitlement`: `policy_version = FK('LeavePolicyVersion', null=True, blank=True, on_delete=SET_NULL, related_name='+')` (provenance at version granularity; nullable for legacy/manual rows). Migration `0023_leave_policy_versioning` (CreateModel + AddField + a RunPython backfill: for each existing entitlement with a `policy`, create version 1 from the current policy snapshot and link it — idempotent).

#### 2. Service — extend `leave_policy_service.py` (DRF-free, no `rest_framework`)
- `snapshot_policy(policy) -> dict` — serialize the policy's configurable fields (leave_type code, default_entitled_days, max_carryover_days, is_carryover_allowed, accrual_method, gender_restriction, requires_approval, min_service_days, name, description, status, applies_to_contract_types, applies_to_org_units ids) into a JSON-safe dict.
- `fork_policy(policy, *, effective_from=None, change_summary='', user=None) -> LeavePolicyVersion`:
  1. Determine `next_version = (existing max version_number) + 1` (or 1).
  2. `effective_from` defaults to `timezone.localdate()`.
  3. Close the previous version: set its `effective_to = effective_from - 1 day` (only if it was open-ended).
  4. Create the new version with `snapshot = snapshot_policy(policy)` and `version_number = next_version`.
  5. **Do NOT mutate the live `LeavePolicy` fields** (versioning records the snapshot; the live row remains the current config). Optionally align `LeavePolicy.effective_from/effective_to` to the newest version's window — your choice, but document it.
  6. Return the new version.
- `get_version_history(policy) -> list[LeavePolicyVersion]` — ordered ascending by `version_number`.
- `latest_version(policy) -> LeavePolicyVersion | None`.

#### 3. Serializer
- New `LeavePolicyVersionSerializer` — fields: `id`, `policy`, `version_number`, `effective_from`, `effective_to`, `change_summary`, `created_by`, `created_at`, `snapshot` (read-only except `change_summary`).
- `LeavePolicySerializer` — add read-only `latest_version` (int, the newest version_number or null) and `version_count` (int).
- `LeaveEntitlementSerializer` — add read-only `policy_version` (int, nullable) + `policy_version_number` (SerializerMethodField → `obj.policy_version.version_number if obj.policy_version_id else None`).

#### 4. Views + URLs (thin, service-backed)
- `LeavePolicyVersionListView` (`GET` list + `POST` fork) at `leave-policies/<int:pk>/versions/`:
  - `GET` → `{ count, results: [...] }` from `get_version_history`.
  - `POST` → body `{ change_summary, effective_from? }` → calls `fork_policy(policy, user=request.user, ...)` → 201 with the new version. Requires PeopleAccess (write gate via existing `_GatedDetailView` pattern or explicit admin check — match `LeavePolicyPropagateView`'s permission style).
- `LeavePolicyVersionDetailView` (`GET` only) at `leave-policies/<int:pk>/versions/<int:version_pk>/`.
- Wire both into `backend/people/urls.py` next to the existing leave-policies routes.

#### 5. Tests — new `backend/people/tests/test_leave_policy_versioning.py`
Follow the fixture style in `test_leave_policy_service.py`. Cover:
- (a) `snapshot_policy` captures configurable fields and is JSON-safe.
- (b) `fork_policy` first version → `version_number == 1`, `effective_from` set, previous version (none) unaffected.
- (c) `fork_policy` second fork → `version_number == 2`, and closes the prior open-ended version's `effective_to`.
- (d) `get_version_history` returns ascending order; `latest_version` returns version 2.
- (e) migration backfill: existing entitlement with `policy` gets `policy_version` linked to version 1 (simulate by asserting the FK is non-null after backfill — or, if hard to test in isolation, assert `LeaveEntitlement.policy_version` is writable and round-trips through the serializer).
- (f) `GET /leave-policies/<id>/versions/` returns history; `POST` creates version 2.

### DO NOT TOUCH
- `backend/correspondence/*`, `backend/ai/*`, `backend/accounts/*`, `backend/config/settings.py`
- Any frontend file.

### Verification Gate (run + report literal output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations people --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python manage.py migrate people
/home/ahmed/aast/carbon/.venv/bin/python -m pytest people -q --maxfail=5 --disable-warnings -p no:cacheprovider --create-db
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
```
NOTE: `--create-db` is required (new model/field + `--reuse-db --nomigrations` in pytest.ini).

---

## Phase LPR-3B — Frontend: version-history panel
**Role:** frontend-worker · **Depends on:** LPR-3A · **Model:** DeepSeek V4-Flash
**Status:** DONE — verified 2026-09-06 (build ✓, i18n parity ✓ 3075 keys, vitest 7/7)

### Objective
Surface the version ledger in the policy 360: a "Versions" tab showing the full
history, plus a "New Version" fork action that captures a change summary.

### What to Build
1. `PolicyDetailPage.jsx` — add a 7th tab `Versions` to `TAB_KEYS` (persist via the
   existing localStorage key). Render a timeline/table of versions: version number,
   effective_from → effective_to, change_summary, created_by, created_at. Show the
   `snapshot` fields in an expandable/details view (a Dialog or accordion).
2. "New Version" button in the Versions tab → opens a Dialog with a `change_summary`
   field (and optional effective_from date) → calls the fork endpoint → refreshes history.
3. `api/people.js` — add `fetchLeavePolicyVersions(policyId, token)` + `forkLeavePolicy(policyId, payload, token)`.
4. i18n keys (en + ar) for all new labels (version, version history, new version, change summary, effective from/to, etc.).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run build && node scripts/check-i18n-keys.js
npx vitest run src/__tests__/PeoplePages.test.jsx
```

---

## PULSE UNIFIED REMEDIATION PLAN — Phase 2 (Boundaries)

> Canonical spec: `docs/pulse/PULSE-UNIFIED-REMEDIATION-PLAN.md` (Gate 2).
> Tracked here for worker dispatch. Master runs all verification (workers have no terminal).

| ID | Task | Status |
|----|------|--------|
| P2-04 | import-boundary-lint enforcing | DONE |
| P2-05 | Single ORM (SQLAlchemy removed, Django canonical) | DONE — 1738 tests green, sqlalchemy uninstalled |
| P2-06a | Command Boundary core (`command_boundary.py`, 13 stages) | DONE |
| P2-07 | PDP v1 (`pdp.py`, default-deny) | DONE |
| P2-06b | Route `call_host_api` through the boundary | DONE — 1746 tests green, import-boundary-lint clean |
| P2-06c | Route worker fan-out through the boundary | DONE — 1746 tests green, import-boundary-lint clean |
| P2-08 | Domain-pack extraction (forbidden-term grep = 0) | **DONE — source neutralized, `forbidden-term-lint` EXIT 0; handoff issued to Phase 3 master** |
| P2-06e | Route proactive delivery through the boundary | **DONE — `execute_delivery_via_boundary` seam + PDP `deliver` permit; 4 tests green** |
| P2-06d | Route ReAct loop through the boundary | **DONE — `execute_step_via_boundary` seam + fail-closed `_tool_requires_confirmation`; consent gate = boundary outcome; 1772 tests green, 3 lints clean** |
| P2-06f | Route `ops_workflow` host REST through the boundary | **DONE — `_host_effect` seam helper routes 7 host REST calls; 1769 tests green, 3 lints clean** |
| P2-11 | Toolkit gates (`verify.sh intelligence` + `audit-imports` + `audit-routes`) | **DONE — `verify.sh intelligence` (import-linter + fail-open + forbidden-term + vulture-report + replay smoke) wired into CI; `audit-imports`/`audit-routes` fail on seeded violation** |
| — | `PULSE-MASTER.md` §boundary reconciled | **DONE — §2 documents the "one door" CommandBoundary routing (4 seams + PDP default-deny), wired to `verify.sh intelligence`/`audit-imports`/`audit-routes`** |

---

## P2-08 — Domain-pack extraction (DONE — source extraction/neutralization complete)

> Canonical: plan row P2-08a–g. Acceptance: **forbidden-term grep over `engine/**` = 0 per file**.
> Engine becomes domain-agnostic; Carbon-specific vocabulary/constants move to `domain_packs/carbon/`,
> loaded via a `DomainPack` port. **One PR per source (a–g).** Foundation (F) is a prerequisite.

> **STATUS: DONE (Master-verified 2026-09-13).** All domain vocabulary neutralized across
> `engine/**` (14 files). `forbidden-term-lint.py` EXIT 0, `import-boundary-lint.py` EXIT 0,
> `manage.py check` EXIT 0, full `ai` suite 1762 passed. See TASK-RESULTS.md "P2-08 source
> extraction/neutralization".

### Foundation (F) — `DomainPack` port + pack skeleton + forbidden-term lint
> **STATUS: DONE** (Master-verified 2026-09-13). `domain.py` parses, `import-boundary-lint`
> clean, zero forbidden terms in the new port files, loader loads the carbon pack + neutral fallback works.

- **CREATE `backend/ai/engine/ports/domain.py`** — `DomainPack` Protocol with accessors:
  `vocabulary() -> dict`, `api_catalog() -> dict`, `processes() -> list`, `skills() -> list`,
  `triggers() -> dict`, `prompts() -> dict`; plus a module-level `get_domain_pack()`
  loader that resolves the pack by instance/brand (default `"carbon"`) from `domain_packs/`,
  with a **neutral generic fallback** (empty collections + safe defaults) when no pack is loaded —
  the engine must boot and behave identically pack-less. Loader lives in the engine (ports read
  only); it MUST NOT import Django. YAML parsing via stdlib-only fallback if PyYAML absent.
- **CREATE `domain_packs/carbon/`** skeleton: `vocabulary.yaml`, `api_catalog.yaml`,
  `processes/`, `skills/`, `triggers.yaml`, `prompts/`. Each YAML schema is defined here so the
  seven source PRs have a fixed contract.
- **CREATE `.ai-toolkit/scripts/forbidden-term-lint.py` + `forbidden-terms.txt`** — scans
  `backend/ai/engine/**` for the domain terms listed in `forbidden-terms.txt`; allowlist keyed by
  `relpath:lineno` (same convention as `import-boundary-lint.py`). Exits 1 on any non-allowlisted
  hit, prints `Forbidden domain term: clean (engine is domain-agnostic)` on 0. This is the P2-08
  acceptance gate and feeds P2-11's `verify.sh intelligence`.

### Source PRs (one per file; forbidden-term grep must return 0 for that file)
| PR | File | Extract | Into |
|----|------|---------|------|
| a | `engine/cognition/turn/intent.py` | campus names ("South Valley","Smart Village","Abu Qir","Alamein"), `list_emission_factors`, "emission factors", GHG terms ("GHG Protocol","carbon","footprint") | `vocabulary.yaml` |
| b | `engine/cognition/plan/loop.py` | `_allow` set (`create_dq_rule`,`search_knowledge`,`get_entity_details`,`list_my_capabilities`,`plan_task`) | `api_catalog.yaml` (tool allow-list) |
| c | `engine/cognition/plan/planner.py` | supplier/module/category analysis-dimension phrases (`_MULTI_SIGNALS`) | `vocabulary.yaml` |
| d | `engine/cognition/turn/execute.py` | `"carbon_api"` source-type default + `source_map` | `api_catalog.yaml` |
| e | `engine/proactive/delivery.py` | `"carbon"` brand fallback (`app_identifier`) + channel routes | `vocabulary.yaml` / `api_catalog.yaml` |
| f | `engine/proactive/insight_generator.py` | power-domain example metric defaults (`unit_metrics`/`heat_rate`/`demand_forecasts`/`demand_actuals`/`value_mw`, `threshold_pct` 2.0/8.0, "Unit 2 Heat Rate") | `triggers.yaml` |
| g | `engine/core/config.py` | DQ/Carbon constants (`TASK_DQ_VALIDATE_TIMEOUT=10`,`TASK_DQ_SUGGEST_TIMEOUT=60`,`PULSE_CARBON_CONTEXT_ENABLED`) + "Carbon expects …" comments | `api_catalog.yaml` / `vocabulary.yaml` |

**Additional files surfaced by the lint baseline (77 hits / 16 files)** — each needs a PR too,
mostly brand-in-docstring/comments or prompt-string vocabulary. Fold into the fan-out after a–g:
`engine/__init__.py` (brand docstring), `engine/agent/plugins.py` (`create_dq_rule`),
`engine/agent/tools.py` (`footprint`/`emission factors`), `engine/cognition/turn/draft.py`
(`create_dq_rule`), `engine/cognition/turn/runner.py` (`Carbon`/`GHG`/`list_emission_factors`/
`emission factors`/`PULSE_CARBON_CONTEXT_ENABLED`/`create_dq_rule`), `engine/core/event_bus.py`
(brand docstring), `engine/knowledge_graph/store.py` (brand docstring), `engine/llm/playbook.py`
(`carbon`), `engine/llm/prompts.py` (`emission factors`/`list_emission_factors`),
`engine/memory/_redis.py` (brand docstring), `engine/proactive/trigger_evaluator.py`
(`unit_metrics` example). Prompt strings → `domain_packs/carbon/prompts/`; docstrings/comments →
neutralize in place (no data path, no port needed).

**Rules for every source PR:**
- Engine file must read via the `DomainPack` port; keep a **generic neutral fallback** so behavior
  is unchanged when no pack loads (existing fixtures must stay green).
- `import-boundary-lint` stays clean (no new `ai.` host imports; the port is `engine.ports`).
- Do NOT touch other source files — one PR = one file. Cross-cutting schema decisions go in the
  Foundation worker's PR only.

### Forbidden terms (initial `forbidden-terms.txt`, refined by Foundation worker)
`carbon`, `Carbon`, `GHG`, `GHG Protocol`, `footprint`, `emission factors`, `list_emission_factors`,
`carbon_api`, `Alamein`, `South Valley`, `Smart Village`, `Abu Qir`, `Nibras`, `unit_metrics`,
`heat_rate`, `demand_forecasts`, `demand_actuals`, `value_mw`, `Unit 2 Heat Rate`, `TASK_DQ_`,
`PULSE_CARBON_CONTEXT_ENABLED`, `create_dq_rule`. (Words like `carbon` must be word-boundary
matched so `carbon_copy`-style identifiers and generic prose don't false-positive — final list is
the Foundation worker's responsibility, reviewed by Master before dispatch of a–g.)


---

## Pulse command-boundary leftovers (audit)

## Phase P2-06b — Route `call_host_api` through the command boundary
**Role:** backend-worker · **Model:** DeepSeek V4-Flash · **Depends on:** P2-06a, P2-07 (both DONE)

> **STATUS: DONE** (Master-verified). Architectural correction applied by Master:
> the engine tool must NOT import host modules (`ai.command_boundary`,
> `ai.command_boundary_factory`, `ai.protocol`) — that violates RULE_20 / P2-04
> and `command_boundary.py`'s own "MUST NOT be imported by `ai.engine/`" contract.
> Final shape: `execute_call_host_api` delegates its resolved host-effect closure
> to `executor.execute_host_api_via_boundary(...)`; `CarbonHostExecutor` (host) is
> what actually builds the `Command` and calls `CommandBoundary.execute()`.

### Objective
Wire the production `CommandBoundary` (P2-06a) with real dependencies and route the
`call_host_api` tool (`backend/ai/engine/agent/tools.py::execute_call_host_api`) through it,
replacing its ad-hoc `requires_confirmation`/`create_pending_execution` gate with the
13-stage fail-closed boundary. Preserve the user-visible staging flow (mutations still
return `requires_confirmation` + `execution_id`).

### Files
- CREATE `backend/ai/command_boundary_factory.py` — `get_command_boundary(db, *, executor=None, ...)` wiring the real `PDP`, `DjangoLedgerAdapter`, tool catalog (registered tool names), identity resolver, params validator, budget checker.
- EDIT `backend/ai/pdp.py` — add a permit `Policy` for the `call_host_api` host action (and the host verb set) so legitimate calls are not default-denied; mutating verbs still gate on the autonomy dial.
- EDIT `backend/ai/engine/agent/tools.py` — `execute_call_host_api` builds a `Command` and calls `boundary.execute()`; the old gate moves into the boundary executor closure.
- CREATE `backend/ai/tests/test_call_host_api_boundary.py` — proves the tool routes through the boundary.

### Contract (read these first)
- `backend/ai/command_boundary.py` — `Command`, `Outcome`, `CommandBoundary.execute()`, `execute()`.
- `backend/ai/pdp.py` — `PDP`, `Policy`, `Decision`, `DEFAULT_POLICIES`.
- `backend/ai/adapters/ledger.py` — `DjangoLedgerAdapter(db)`.
- `backend/ai/engine/agent/executor.py` — `HostAPIExecutor` (staging API).

### DO NOT TOUCH
- `backend/ai/engine/` port files (engine stays portable — never import `command_boundary` from `ai/engine/`).
- `backend/ai/guards.py`, `backend/ai/protocol.py` (guard contracts unchanged).
- Frontend, `config/settings.py`, `backend/accounts/*`.

### Verification Gate (Master runs)
```bash
cd /home/ahmed/ws/carbon/backend && /home/ahmed/ws/carbon/.venv/bin/python -m pytest ai -q -k "not code_sandbox" -m "not live"
cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/import-boundary-lint.py
```

---

## Phase P2-06c — Route worker fan-out through the command boundary
**Role:** backend-worker · **Model:** DeepSeek V4-Flash · **Depends on:** P2-06a, P2-06b, P2-07 (all DONE)

> **STATUS: DONE** (Master-verified). The P1-07 interim hook call is deleted;
> `workers.py` now delegates to `CarbonHostExecutor.execute_worker_tools_via_boundary`,
> which builds a `Command` per tool call (read → `action="read"` → PDP ALLOW;
> mutation → `action="execute"` + `autonomy="human_only"` → PDP ASK → stage-7
> consent refuses, executor never runs). Engine stays host-free.

### Objective
Replace the interim P1-07 hook mechanism in `backend/ai/engine/agent/workers.py`
(`_get_hook_pipeline()` + `ExecuteWitness(is_worker=True, hook_pipeline=...)` +
`readonly_worker_hook`) with the 13-stage fail-closed `CommandBoundary`. Every
worker tool call becomes a `Command`; the boundary's PDP + consent stages block
mutations (workers are read-only), read-only tools execute. Delete the interim
hook call entirely.

### Contract (read these first)
- `backend/ai/command_boundary.py` — `Command`, `Outcome`, `CommandBoundary`, `STAGES`.
- `backend/ai/command_boundary_factory.py` — `get_command_boundary(db, *, executor, tool_catalog, ...)`, `_STATIC_TOOL_NAMES`.
- `backend/ai/pdp.py` — `DEFAULT_POLICIES`, `_READ_ACTIONS`, `_MUTATING_ACTIONS`, `_mutation_outcome`, `_read_outcome`.
- `backend/ai/engine/agent/workers.py` — current `_run_worker` / `_execute_worker_tools` / `_collect_guardrail_outcome` / `_render_worker_tool_results`.
- `backend/ai/engine/cognition/turn/execute.py` — `_execute_single_tool(tool_call, executor_override, hook_pipeline, hook_ctx_defaults, knowledge_store)` returns the completed-tool dict.
- `backend/ai/host_executor.py` — `CarbonHostExecutor.execute_host_api_via_boundary` (the P2-06b seam to mirror).

### How the boundary blocks a worker mutation (the key mechanism)
A worker mutation must be REFUSED, and its executor must NEVER run. Achieve this
with NO new PDP policy, purely by mapping the `Command` fields:

- Read-only worker tool → `Command.action="read"` → PDP `permit-read-only`
  (`"read" ∈ _READ_ACTIONS`) → `Decision.ALLOW` → stage 7 skipped → executor runs.
- Mutation worker tool → `Command.action="execute"` + `autonomy="human_only"` →
  PDP `permit-mutations-by-autonomy` → `_mutation_outcome("human_only")` →
  `Decision.ASK` → stage 7 consent (`requires_confirmation` becomes True because
  ASK ∈ {ALLOW_WITH_CONFIRMATION, ASK}; `confirmation_token`/`_confirmed` absent)
  → `Outcome(status="refused", error="consent: action requires confirmation …")`.
  The boundary executor closure is never invoked.

### Files
1. **EDIT `backend/ai/engine/agent/workers.py`**
   - Delete `_get_hook_pipeline()` and the `self._hook_pipeline` field.
   - `_run_worker`: drop the `_pipeline = self._get_hook_pipeline()` + fail-closed
     block; call the new `_execute_worker_tools` (below) instead.
   - `_execute_worker_tools` → delegate to the host executor seam:
     `self._executor.execute_worker_tools_via_boundary(tool_calls=tool_calls, instance_id=…, conversation_id=…, run_id=worker_run_id, host_user_id=getattr(self._executor, "host_user_id", None), knowledge_store=self._knowledge_store)`.
     If `self._executor` is None or lacks the seam → fail-closed: return one
     blocked dict per tool call (error "worker tool execution unavailable (no boundary seam)",
     `guardrail_flags=["worker_tool_blocked", f"blocked:{name}"]`). No engine imports
     of `command_boundary` / `command_boundary_factory` / `ai.protocol` — ever.
   - Update `_collect_guardrail_outcome` to key the block classification off
     `"worker_tool_blocked"` in `guardrail_flags` (and/or the error prefix), not
     only the old `_GUARDRAIL_CANCEL_PREFIX` string. Preserve the `WorkerArtifact`
     surface (error/guardrail_flags/detail) unchanged.

2. **EDIT `backend/ai/host_executor.py`** — add `CarbonHostExecutor.execute_worker_tools_via_boundary` (mirror the P2-06b seam):
   ```python
   async def execute_worker_tools_via_boundary(self, *, tool_calls, instance_id="",
           conversation_id="", run_id=None, host_user_id=None, knowledge_store=None) -> list[dict]:
       from ai.command_boundary import Command
       from ai.command_boundary_factory import get_command_boundary, _STATIC_TOOL_NAMES

---

## ECF — Entity Capability Framework (ADR-0032)  [2026-09-16]
## Safety: all phases flag-gated (ECF_ENABLED=False default).
## Never break: legacy list_employees / get_employee untouched until Phase ECF-7.
## ════════════════════════════════════════════════════════════════════

### Phase ECF-0 — Golden harness + baseline
**Date:** 2026-09-16  
**Worker Role:** qa-validator  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Owner Master:** Pulse  
**Role:** QA-Validator · **Model:** V4-Flash  
**Scope:** TESTS ONLY — no runtime code touched.

#### Files to create
- `backend/ai/tests/test_ecf_golden.py` — golden regression suite seeded from real failure transcript

#### Exact requirements

The test file must import nothing from ECF code (which doesn't exist yet).
It defines a declarative list of `GoldenCase` entries and a helper that calls
the live nibras instance (or a fixture version) and asserts invariants.

Each case must carry:
- `id: str` — unique slug
- `query: str` — the user message, in the language it was asked
- `must_find: bool` — True = a record must resolve; False = grounded-none required
- `employee_no: str | None` — if must_find=True, the resolved employee_no
- `invariants: list[str]` — prose invariants for the human reviewer

Minimum cases to encode (from the 2026-09-05 → 2026-09-16 transcript failures):

| id | query | must_find | employee_no | invariants |
|----|-------|-----------|-------------|------------|
| lookup_salman_en_full | `"Salman Ali Hussain Zakareya"` | False | None | grounded-none with "searched N of N"; never "not found" without count |
| lookup_salman_ar | `"سلمان علي زكريا"` | False | None | same as above; Arabic in, Arabic response |
| lookup_salman_partial | `"salman zakareya"` | False | None | partial match attempt; no hallucination |
| lookup_employee_no_1046 | `"1046"` (employee_no) | True | `"1046"` | resolves via employee_no not PK; must not return "not found" |
| lookup_employee_no_1021 | `"1021"` (employee_no) | True | `"1021"` | same |
| lookup_pk_104 | `"104"` (internal pk) | True | `"104"` | pk fallback; must resolve if pk 104 exists |
| lookup_reena_sekaran | `"Reena Sekaran"` | True | `"1009"` | name search returns correct emp_no |
| lookup_ar_abrar | `"عبرار"` | True | `"1021"` | transliteration-like Arabic partial |
| existence_over_truncated | `"is there an employee named Salman?"` | False | None | contract: must NOT produce "no such employee" without "searched N of N" |
| headcount_stable | `"كم عدد الموظفين"` | False | None | number matches DB; consistent across calls |
| kuwaiti_count_stable | `"كم كويتي موظف"` | False | None | single definition used; same number repeated; must cite which field |
| position_label | `"tell me about Reena Sekaran"` | True | `"1009"` | response contains position *title* not numeric id |
| arabic_in_arabic_out | `"كم موظف لدينا"` | False | None | response language is Arabic |

For Phase ECF-0 these tests are expected to **fail** (they document the current broken baseline).
The test runner must emit `BASELINE_FAILURE` not `ERROR` for known-bad cases —
use `@pytest.mark.xfail(reason="baseline — ECF not yet implemented", strict=False)`.

#### Contract files to read
`.ai-toolkit/shared/qa-framework.md`, `.ai-toolkit/shared/testing.md`, `.ai-toolkit/shared/uncertainty-provenance.md`

#### DO NOT TOUCH
Any file outside `backend/ai/tests/test_ecf_golden.py`. No runtime code.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_ecf_golden.py -v 2>&1 | tail -30
# Expected: all xfail or xpass — NO ERROR / EXCEPTION
cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/import-boundary-lint.py
```
Write results to `TASK-RESULTS.md` with the full pytest output block.

---

### Phase ECF-1 — Entity Registry + descriptor schema + config flag
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Owner Master:** Pulse  
**Depends on:** ECF-0 complete  
**Scope:** New module + config flag + ADR-0032 descriptor in instance.yaml. NO tool wiring yet.

#### Files to create / edit

1. **CREATE `backend/ai/engine/cognition/entity/__init__.py`** — empty
2. **CREATE `backend/ai/engine/cognition/entity/registry.py`** — descriptor dataclass + loader:

```python
# Descriptor fields (all optional except name/model):
@dataclass
class EntityDescriptor:
    name: str                          # "employee"
    model: str                         # "people.models.Employee"
    identifiers: list[str]             # ["id", "employee_no", "civil_id"]
    search_fields: list[SearchField]   # bilingual, weighted
    label_map: dict[str, LabelSource]  # {"position": LabelSource(model=..., field="title")}
    masking: dict[str, MaskPolicy]     # {"basic_salary": MaskPolicy(capability="people:view_compensation")}
    metrics: dict[str, MetricDef]      # {"headcount": MetricDef(filter={"is_active": True}), "kuwaiti": MetricDef(filter={"nationality_code": "KW"})}
    scope_lookup: str | None           # org-unit scope kwarg e.g. "org_unit_id__in"

@dataclass
class SearchField:
    field: str
    lang: str         # "en" | "ar" | "any"
    weight: float = 1.0
    normalize: str | None = None  # "arabic" | None

@dataclass  
class LabelSource:
    model: str        # dotted Django model path
    field: str        # field name on the related model

@dataclass
class MaskPolicy:
    capability: str   # Django CBAC capability key; if caller lacks it → "hidden"

@dataclass
class MetricDef:
    filter: dict      # ORM kwargs for count() filter
    description: str = ""

def load_descriptors(instance_config: dict) -> dict[str, EntityDescriptor]:
    """Load entity descriptors from instance_config['entities'] list."""
    ...

def get_descriptor(instance_config: dict, entity_type: str) -> EntityDescriptor | None:
    ...
```

3. **EDIT `backend/ai/engine/core/config.py`** — add ONE flag:
```python
ECF_ENABLED: bool = False   # Entity Capability Framework; off until ECF-7 cutover
```

4. **EDIT `backend/ai/engine/instances/nibras/instance.yaml`** — append `entities:` block:

```yaml
entities:
  - name: employee
    model: people.models.Employee
    identifiers: [id, employee_no, civil_id]
    search_fields:
      - {field: full_name,      lang: en, weight: 1.0}
      - {field: name_en_given,  lang: en, weight: 0.9}
      - {field: name_en_family, lang: en, weight: 0.9}
      - {field: name_ar_given,  lang: ar, weight: 1.0, normalize: arabic}
      - {field: name_ar_family, lang: ar, weight: 1.0, normalize: arabic}
      - {field: employee_no,    lang: any, weight: 2.0}
      - {field: civil_id,       lang: any, weight: 2.0}
    label_map:
      position:  {model: people.models.Position,  field: title}
      org_unit:  {model: mdm.models.OrgUnit,       field: name}
    masking:
      basic_salary: {capability: people:view_compensation}
    metrics:
      headcount: {filter: {is_active: true},  description: "Total active employees"}
      kuwaiti:   {filter: {nationality_code: "KW"}, description: "Employees with nationality_code=KW"}
    scope_lookup: org_unit_id__in
```

5. **CREATE `backend/ai/tests/test_ecf_registry.py`**:
- loads nibras instance.yaml via `_instance_config("nibras", None)`
- calls `load_descriptors(cfg)` → asserts "employee" present with correct fields
- unit-level; no DB; no LLM

#### Contract files to read
`.ai-toolkit/shared/base-rules.md`, `.ai-toolkit/shared/ai-contract.md`, `.ai-toolkit/shared/config.md`, `ADR-0016`, `ADR-0017`, `ADR-0032`

#### DO NOT TOUCH
`tools.py` execution paths, any existing capabilities, `list_employees`/`get_employee`, frontend, `settings.py`.
The engine must never import people/mdm/accounts directly — descriptors are pure data, model paths are strings resolved at runtime in the host layer.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_ecf_registry.py ai/tests/test_instance_registry.py -v 2>&1 | tail -20
# Must: test_ecf_registry passes; test_instance_registry still all green (no regression)
cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/import-boundary-lint.py
```
Write results to `TASK-RESULTS.md` with full pytest output.

---

### Phase ECF-2 — Generic resolver (shadow, no tool wiring)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Owner Master:** Pulse  
**Depends on:** ECF-1 complete  
**Scope:** The resolver algorithm. Purely in-engine. No host imports. No tool wiring. `ECF_ENABLED` irrelevant (not yet on the hot path).
**Master verify 2026-09-16:** `test_ecf_resolver` 14 passed; import-boundary clean; no people/mdm engine imports.

#### Files to create

1. **CREATE `backend/ai/engine/cognition/entity/resolver.py`**

Algorithm (`resolve(descriptor, query, *, fetch_fn) -> ResolveResult`):
```
1. Detect language (reuse navigation.py detect_lang)
2. Normalize query (reuse navigation.py normalize_text for Arabic; strip for English)
3. Try identifier exact match (employee_no, civil_id) → if hits → Return match
4. For each search_field in descriptor (filtered to detected lang or "any"):
     score = similarity(normalize(query), normalize(stored_value))
     Apply weight from descriptor
5. Transliteration bridge: if Arabic query and EN search fields (or vice versa),
   apply transliterate(query) and re-score
6. Threshold: score >= 0.8 → candidate; score >= 0.92 → match
7. If 0 candidates → ResolveResult(action="none", searched_total=N)
8. If 1 match (and gap >= 0.1 from next) → ResolveResult(action="match", record=...)
9. Otherwise → ResolveResult(action="disambiguate", candidates=[...])
```

`fetch_fn` is injected — the engine never imports Django. Signature:
```python
def fetch_fn(model_path: str, filters: dict, fields: list[str], limit: int) -> list[dict]: ...
```

The host layer (host_executor.py) supplies a concrete `fetch_fn` that does the ORM call.

```python
@dataclass
class ResolveResult:
    action: str          # "match" | "disambiguate" | "none"
    record: dict | None = None
    candidates: list[dict] = field(default_factory=list)
    searched_total: int = 0  # always populated — "searched N of N"
    lang: str = "en"
    query_normalized: str = ""
```

2. **CREATE `backend/ai/tests/test_ecf_resolver.py`**:
- Use an in-memory fixture of 530-ish synthetic records (no DB).
- Must prove: "Salman Ali Hussain Zakareya" → action="none", searched_total=530; "Reena Sekaran" → action="match"; "1046" (employee_no) → action="match"; Arabic "سلمان" → action="none" or disambiguate, never a confident false-negative; transliteration bridge.
- Must prove: Arabic query → Arabic-language result context.

#### Contract files to read
`.ai-toolkit/shared/base-rules.md`, `ADR-0032`, `ADR-0016/0017`, navigation.py (reuse pattern)

#### DO NOT TOUCH
`host_executor.py`, `tools.py`, `instance.yaml`, frontend. No DB ORM in this file.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_ecf_resolver.py -v 2>&1 | tail -30
cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/import-boundary-lint.py
# CRITICAL: grep -rn "from people\|import Employee\|from mdm" backend/ai/engine/ → must be EMPTY
```

---

### Phase ECF-3 — Boundary contract guards
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Owner Master:** Pulse  
**Depends on:** ECF-2 complete

#### Files to create / edit

1. **CREATE `backend/ai/engine/cognition/entity/contracts.py`** — four enforced invariants as callables hooked into the tool result pipeline:
   - `no_truncation_as_truth(tool_result, claim)`: if source `truncated=True` and claim is existence/universal ("no such", "all", "none") → rewrite claim to "searched N of N, none found in visible page; use resolve_entity for complete search"
   - `resolve_labels(data, descriptor)`: replace FK ids with human labels
   - `honest_masking(data, descriptor, capabilities)`: replace `0.000` with `"(hidden — requires salary access)"` when caller lacks capability
   - `grounded_refusal(result)`: existence-claim requires `searched_total` field populated

2. **EDIT `backend/ai/engine_runtime.py`** — in `_run_chat`, after tool results are collected (after `_build_tool_trace`), add a contract-application pass: `from ai.engine.cognition.entity.contracts import apply_contracts` (gated on `ECF_ENABLED` flag).

3. **CREATE `backend/ai/tests/test_ecf_contracts.py`**:
   - `test_truncated_source_cannot_claim_nonexistence`: assert that a "not found" from a truncated list gets rewritten.
   - `test_salary_zero_becomes_hidden_label`: assert `0.000` → `"(hidden)"` when capability absent.
   - `test_fk_id_resolved_to_label`: assert `position=170` → `position="CT Senior Operator"`.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_ecf_contracts.py -v 2>&1 | tail -20
# Full suite still green:
../.venv/bin/python -m pytest ai/ -q -k "not live" 2>&1 | tail -10
```

---

### Phase ECF-4 — Wire resolve_entity tool (flag-gated) + fix get_employee
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Owner Master:** Pulse  
**Depends on:** ECF-3 complete  
**Master note 2026-09-16:** resolve_entity tool + ECF_ENABLED gate + host employee_no + yaml copy already present. Shadow logger (`shadow_diff` → structured JSON) shipped for ECF-7 parity evidence.

#### Files to edit

1. **EDIT `backend/ai/engine/agent/tools.py`** — add `resolve_entity` to `STATIC_TOOL_DEFINITIONS` and `STATIC_TOOL_EXECUTORS` gated on `settings.ECF_ENABLED`. Reuse `get_descriptor(instance_config, entity_type)` + resolver + host `fetch_fn` bridge.

2. **EDIT `backend/ai/host_executor.py`** — in `_people_in_process` employees branch: accept `employee_no` as a lookup key in addition to PK (already has `pk` param — add `elif params.get("employee_no")` resolution).

3. **EDIT `backend/ai/engine/instances/nibras/instance.yaml`** — fix `list_employees` description to say "first 100; for lookup by name/number use resolve_entity" and `get_employee` to say "accepts numeric id OR employee_no". Do NOT change the catalog entry path.

4. **CREATE shadow logger** in `resolve_entity` executor: when `ECF_ENABLED` is True, log `shadow_diff = {new_result, legacy_result}` to `ai_shadow_log` table (or JSON log if table doesn't exist yet). This generates the parity evidence needed for ECF-7 cutover decision.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_ecf_golden.py ai/tests/test_ecf_resolver.py ai/tests/test_ecf_contracts.py ai/tests/test_navigation_resolver.py ai/tests/test_intent_resolver.py -v 2>&1 | tail -40
# ECF golden cases should be flipping from xfail to xpass progressively.
# Navigation + intent tests: zero regression.
```

---

### Phase ECF-5 — MAPE-K feedback loop (trajectory → golden)
**Date:** 2026-09-16  
**Worker Role:** data-ml-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Owner Master:** Pulse  
**Depends on:** ECF-4 complete  
**Master verify 2026-09-16:** heal.py + test_ecf_heal 12 passed; nomination write proven (tmp_path).

#### Files to create

**CREATE `backend/ai/engine/cognition/entity/heal.py`**:

```python
# MAPE-K implementation
# Monitor: hooks into contract-guard violations + user-correction signals
#           (turn with text matching "wrong"/"ليس صحيح"/"غلط" shortly after a tool call)
# Analyze: classify as Tier-1 (reversible, auto-heal) or Tier-2 (structural, propose)
# Plan + Execute:
#   Tier-1: re-resolve with broader normalization; abstain honestly; reindex stale entity cache
#   Tier-2: auto-draft a GoldenCase (nominated_by="mape_k") + write to
#            backend/ai/eval/pending_golden_nominations.json (human reviews before CI merge)
```

The pending nominations JSON is a queue; a human reviews, moves to `test_ecf_golden.py`, and runs CI. That is the "self-healing through human gate" pattern.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_ecf_heal.py -v 2>&1 | tail -20
# Prove: simulated correction → pending_golden_nominations.json gains one entry.
```

---

### Phase ECF-6 — Canonical metrics
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** DONE  
**Owner Master:** Pulse  
**Depends on:** ECF-5 complete

Wire descriptor `metrics{}` → `aggregate_entity` capability. "headcount" always uses `is_active=True` count. "kuwaiti" always uses `nationality_code="KW"`. The `analyze_employees` dimension route is unchanged; `aggregate_entity` is an additional, metric-named path.

#### Verification Gate
```bash
# Run golden "same question → same number":
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_ecf_golden.py -k "headcount_stable or kuwaiti_count_stable" -v
```

---

### Phase ECF-7 — Cutover (Master Architect gates this)
**Date:** 2026-09-16  
**Worker Role:** backend-worker (Pulse) — human sign-off received  
**Status:** DONE  
**Owner Master:** Pulse  
**Only triggers after:** ECF golden set fully green; shadow-diff review shows parity; human sign-off.

**Gate checklist (all ✅ 2026-09-16):**
- [x] Goldens: **17 passed, 0 xfailed, 0 failed**
- [x] Shadow suite green (`test_ecf_shadow.py`)
- [x] Contracts + aggregate suites green
- [x] Import-boundary: `rg` on `cognition/entity/` → zero django/people/rest_framework
- [x] Human sign-off → flip `ECF_ENABLED = True` in `Settings` (env `ECF_ENABLED=false` = emergency rollback)
- [x] `slug_resolution` marked superseded; kept as 30-day fallback (NOT deleted)
- [x] Evidence: `docs/pulse/evidence/ECF-7-cutover.md`

Next: **ECF-8** — LeaveRecord descriptor-only generalize proof.

---

### Phase ECF-8 — Generalize proof (Backend-Worker)
**Date:** 2026-09-16  
**Worker Role:** backend-worker (Pulse)  
**Status:** DONE  
**Depends on:** ECF-7  
**Evidence:** `docs/pulse/evidence/ECF-8-leave-record.md`

Onboarded `LeaveRecord` as entity #2 via **only** a descriptor entry in `nibras/instance.yaml` + golden cases (`test_ecf_leave_golden.py`). Zero new algorithm code under `cognition/entity/`. Framework generalize proof complete — ECF track COMPLETE.

---

### ECF Edge-Case Matrix (CI must cover all rows)
| Edge case | Phase | Test |
|---|---|---|
| Exists in rows > 100 (only in page 2+) | ECF-2 | test_ecf_resolver: record at index 150 resolves |
| Arabic tashkeel variants | ECF-2 | "سَلمان" = "سلمان" |
| Transliteration (Salman ↔ سلمان) | ECF-2 | near-miss candidates surfaced |
| employee_no vs PK ambiguity | ECF-4 | "1046" → emp 1046, not pk 1046 |
| Prompt injection in name query | ECF-2 | query treated as data, no eval |
| Existence claim over truncated source | ECF-3 | test_ecf_contracts |
| PII masking honest | ECF-3 | test_ecf_contracts |
| FK id label resolution | ECF-3 | test_ecf_contracts |
| Multi-tenant scope isolation | ECF-2 | fetch_fn applies scope; carbon sees no nibras data |
| Language in → language out | ECF-0 | arabic_in_arabic_out golden case |
| Canonical metric stability | ECF-6 | headcount_stable / kuwaiti_count_stable |
| New entity (no code change) | ECF-8 | LeaveRecord descriptor only |


---

## PV2 — Pulse v2 Intelligence Contract (ADR-0047) · DISPATCH 2026-09-22
## Owner Master: Pulse · Seat law: `.ai-toolkit/shared/multi-master.md`
## Plan: `docs/pulse/PULSE-V2-INTELLIGENCE-CONTRACT.md` · Objectives C1–C10 / A1–A10
## Safety: P0 is LOG-ONLY. No behavior change to routing, prompts, consent, or ADR-0046.
## ════════════════════════════════════════════════════════════════════

**Scope:** `backend/ai/**` (engine + host), `docs/pulse/**`, `.ai-toolkit/decisions/0047*`.
**Out of scope:** `backend/people/**`, `carbon-frontend/src/apps/{people,my,team}/**`, EduOS/GradeVance, Catalog/DQ.
**Contracts:** `shared/{ai-contract,testing,definition-of-done,logging,git-workflow}.md` · ADR-0014 · ADR-0046 · ADR-0047 · RULE_21 · RULE_23 · RULE_28 · RULE_35.
**Test law:** TASKS.md MASTER DIRECTIVE — one app at a time (`pytest ai/tests/<file> -q`), never full suite, never xdist.

### Wave map

| Wave | Phases | Parallel? | Outcome |
|------|--------|-----------|---------|
| **W0** | PV2-0A ∥ PV2-0B → PV2-0C | 0A ∥ 0B (disjoint files), 0C after both | Truthful instrumentation + multi-turn bank + baseline numbers |
| **W1** | PV2-1A → PV2-1B → PV2-1C | Sequential | ConversationState store · tool digests in history · memory_manager wired |
| **W2** | PV2-2A → PV2-2B | Sequential | IdentityBlock/ContextPack · all stages consume it |
| **W3** | PV2-3A ∥ PV2-3B | Parallel (loop.py vs runner.py) | Deterministic-first bound steps · surface-truthful Chat prompt |
| **W4** | PV2-4A → PV2-4B → PV2-4C | Sequential | Arbiter signals (shadow) · conflict tests · flip + kill switch |
| **W5** | PV2-5A → PV2-5B → PV2-5C | Sequential | Agent inherits ConversationState · plan_status + Chat/Agent continuity widgets |
| **W6** | PV2-6A | After W1–W5 | Multi-turn bank blocking in CI · G5 Coherence · rule file |

Phases PV2-1A … PV2-6A are **PLANNED** (spec pending; Master writes each after the previous wave's baseline numbers). Only W0 is READY below.

---

### Phase PV2-0A — Backend: truthful LLM-call meter + turn-decision signals (LOG-ONLY)
**Date:** 2026-09-22  
**Worker Role:** backend-worker  
**Recommended Model:** Cursor `composer-2.5-fast` (Zoo Code path: DeepSeek V4.1-Flash) → escalated to `claude-opus-5-5-medium` for rev2/rev2b  
**Status:** DONE — 2026-09-23 Master audit (8/8 new tests, 6× deterministic; 85/1 regression = pre-existing nav failure; import boundary unchanged at 9). rev1 composer had 3 RULE_28 defects (dead journal hook, meter clobber, `unattributed` = AutoMemoryExtractor); fixed on opus. Evidence `docs/pulse/evidence/PV2-baseline-2026-09-22.md` §1  
**Owner Master:** Pulse  
**Objectives served:** C4 (decision log), C8/A2/A9 (LLM-call budgets) — measurement only.

#### Objective
Today `TurnLedger.total_llm_calls` is hand-incremented in `runner.py` and `loop.py:1064` **assumes** "each step involves at least one LLM call" (`total_llm_calls += 1`). Nothing records *which stage* called the LLM, and nothing records *which gate* ended a turn. P0 needs truthful numbers before any behavior change. Build a context-local call meter that `route_chat` increments, tag each call with the active stage, and record which routing gates fired and which one decided the turn. **Zero behavior change** — no routing, prompt, consent, or response text may differ.

#### Files to Read First
- `backend/ai/engine/llm/router.py` (lines ~253–370, `route_chat`) — the single LLM entry point; where usage is read.
- `backend/ai/engine/cognition/turn/witnesses.py` (`TurnLedger`, lines 76–116).
- `backend/ai/engine/cognition/turn/runner.py` lines 1328–2060 (`run()` and every early `return` — pending confirm, nav fast-path, process_brief, deixis, intent short-circuit, weather force, handoff) and lines 2987–3036 (weather force).
- `backend/ai/engine/cognition/plan/loop.py` lines 340–380 and 1040–1110 (`total_llm_calls`, step latency) and ~1700–1720 (draft tokens).
- `backend/ai/step_journal.py` (`StepJournal.append`, `EVENT_*`).
- `backend/ai/engine_runtime.py` lines 395–440 (chat result dict — where `intent_zone` is surfaced).
- `backend/ai/tests/test_chat_wiring.py` — the pattern for driving a stubbed turn (`patch("ai.engine.llm.provider.get_llm_client")`).
- `backend/ai/tests/test_plans.py` `patch_engine_seams` — pattern for stubbing `route_chat` in plan tests.

#### What to Build
1. **CREATE `backend/ai/engine/llm/call_meter.py`**
   - `@dataclass class LLMCallRecord: stage: str; latency_ms: float; prompt_tokens: int; completion_tokens: int; model: str`
   - `@dataclass class CallMeter: records: list[LLMCallRecord]` with `total` (property), `by_stage() -> dict[str,int]`, `total_ms()`, `record(...)`.
   - `contextvars.ContextVar` pair: `_active_meter: ContextVar[CallMeter | None]`, `_active_stage: ContextVar[str]` (default `"unattributed"`).
   - Public API: `start_meter() -> CallMeter` (sets contextvar, returns it), `current_meter() -> CallMeter | None`, `stage(name: str)` as a context manager that sets/restores `_active_stage`, `record_call(latency_ms, prompt_tokens, completion_tokens, model)` — no-op when no meter is active.
   - Pure stdlib; import nothing from Django or host.
2. **MODIFY `backend/ai/engine/llm/router.py` `route_chat`**: after the provider call returns (where `input_tokens/output_tokens` are read, ~line 354) call `record_call(...)` with wall-clock latency of the provider call and the resolved model. Also record on the exception path with `prompt_tokens=0`. Do not change any return value or error behavior.
3. **MODIFY `backend/ai/engine/cognition/turn/witnesses.py` `TurnLedger`**: add fields  
   `llm_calls_by_stage: dict | None = None` · `llm_calls_measured: int = 0` · `decision_signals: list | None = None` · `turn_decision: str = ""`.
4. **MODIFY `backend/ai/engine/cognition/turn/runner.py`**:
   - At the top of `run()` call `meter = start_meter()`.
   - Wrap each LLM-bearing stage body in `with stage("<name>")` using exactly these names: `intent`, `retrieval_rerank`, `draft`, `critic`, `escalate`, `synthesis`, `verify`, `weather_normalize`, `fanout`, `pulse_loop`. Anything else stays `unattributed`.
   - Add a tiny helper `_signal(ledger, gate: str, fired: bool, **detail)` that appends `{"gate", "fired", "detail"}` to `ledger.decision_signals` (create the list lazily). Call it at every gate in `run()` in evaluation order with these exact gate names: `pending_confirm`, `nav_fast_path`, `process_brief_early`, `salience`, `deixis`, `intent_short_circuit`, `process_brief`, `nav_ground`, `off_limits`, `weather_force`, `skill_router`, `chat_handoff`. `fired=True` only when that gate changed the turn's path (early return or forced route); otherwise record `fired=False` with a one-key detail (e.g. `{"zone": ...}`, `{"domain": ...}`).
   - At **every** return point set `ledger.turn_decision` to one of: `memory_confirm`, `navigate`, `process_brief`, `clarify`, `refuse`, `answer`, `handoff_agent`, `tool_answer` (pick the closest; `answer` is the default for the normal draft path), and before returning copy `meter.by_stage()` → `ledger.llm_calls_by_stage`, `meter.total` → `ledger.llm_calls_measured`. Prefer one small `_finalize_meter(ledger, meter)` helper called at each return rather than duplicated code.
   - Emit **one** `logger.info("[turn-decision] conv=%s decision=%s llm=%d by_stage=%s fired=%s", ...)` per turn from `_finalize_meter` (fired = list of gate names with `fired=True`). No other new log lines.
   - Leave `total_llm_calls` hand-counting untouched (it is compared against the meter in tests; a mismatch is a finding to report, not to "fix" in this phase).
5. **MODIFY `backend/ai/engine/cognition/plan/loop.py`**:
   - Around each step execution start a step-scoped meter (`start_meter()` at step start; capture `by_stage/total/total_ms` at step end). Wrap draft / observe / synthesise / critic LLM calls with `stage("draft")`, `stage("observe")`, `stage("plan_synthesis")`, `stage("critic")`.
   - Replace the assumption at ~line 1064 (`total_llm_calls += 1`) with `total_llm_calls += step_meter.total`.
   - Add `llm_calls`, `llm_ms`, `llm_by_stage` to the payload of the existing `StepJournal.append(... EVENT_STEP_COMPLETED ...)` and paused/awaiting events for that step (add keys to the existing payload dict — do not add new events).
6. **MODIFY `backend/ai/engine_runtime.py`** chat result dict (~line 409, next to `intent_zone`): add `"turn_decision": getattr(ledger, "turn_decision", "")`, `"llm_calls": int(getattr(ledger, "llm_calls_measured", 0) or 0)`, `"llm_calls_by_stage": dict(getattr(ledger, "llm_calls_by_stage", None) or {})`. Frontend ignores unknown keys; no FE change.
7. **CREATE `backend/ai/tests/test_pv2_instrumentation.py`** (django_db where needed):
   - `test_call_meter_counts_per_stage` — unit: two `record_call` under `stage("draft")`, one under `stage("critic")` → `by_stage == {"draft": 2, "critic": 1}`, `total == 3`; no meter → `record_call` is a no-op.
   - `test_chat_turn_reports_decision_and_meter` — reuse `test_chat_wiring.py` fixtures (`django_store`, `single_pass`, stub client) → `dispatch_task("chat", …)`; assert `result["turn_decision"]` in the allowed set, `result["llm_calls"] >= 1`, `"draft" in result["llm_calls_by_stage"]`, and the ledger row / response is unchanged (`content == "This is a stubbed chat reply."`).
   - `test_nav_fast_path_records_zero_llm_and_navigate_decision` — drive a navigation utterance that today hits the deterministic nav fast-path (grep `runner.py` ~1500–1540 for the trigger; use an existing nav test's input) → `turn_decision == "navigate"`, `llm_calls == 0`, a `decision_signals` entry `nav_fast_path` with `fired=True`.
   - `test_plan_step_journal_carries_llm_calls` — reuse `test_plans.py` `patch_engine_seams` style: run one plan step with stubbed `route_chat`; assert the `EVENT_STEP_COMPLETED` (or awaiting) journal payload has integer `llm_calls` and `llm_ms >= 0`.
   - `test_meter_matches_hand_count_or_reports` — for the stubbed chat turn assert `abs(ledger.total_llm_calls - ledger.llm_calls_measured) <= 1`; if it fails, **do not loosen** — record the numbers under Issues Found in TASK-RESULTS.md and mark the test `xfail(strict=False, reason="PV2-0A baseline: hand count drift")`.

#### DO NOT TOUCH
- Any routing condition, prompt text, consent/`chat_surface_hook`, `plans_service.py`, `export_bind.py`, frontend, `backend/people/**`, `.github/workflows/**`, `docs/**` (Master owns docs).
- Do not remove or rename `total_llm_calls`; do not change any return payload other than the three additive keys in step 6.

#### Verification Gate (run + paste literal output)
```bash
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python manage.py check
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest ai/tests/test_pv2_instrumentation.py -v -p no:cacheprovider 2>&1 | tail -30
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest ai/tests/test_chat_wiring.py ai/tests/test_plans.py ai/tests/test_pulse_loop.py ai/tests/test_react_consent_boundary.py -q -p no:cacheprovider 2>&1 | tail -8
cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/import-boundary-lint.py
cd /home/ahmed/ws/carbon && ./.ai-toolkit/scripts/verify.sh antipatterns 2>&1 | tail -12
```
Expected: check clean · new tests pass (or the single documented xfail) · regression files unchanged green · import boundary clean · antipatterns no new failures.
Append to `TASK-RESULTS.md` as `## PV2-0A` (Summary · Task Results · Files Changed · Verification Output · Deviations · Issues Found). Report the observed `total_llm_calls` vs `llm_calls_measured` numbers.

- **Master notes** — Hand-count drift confirmed: `total_llm_calls` undercounts by the intent call; PV2-1x may retire hand counting in favour of the meter.

---

### Phase PV2-0B — QA: multi-turn coherence golden bank + offline runner (REPORT-ONLY)
**Date:** 2026-09-22  
**Worker Role:** qa-validator  
**Recommended Model:** Cursor `claude-4.5-haiku-thinking` (Zoo Code path: DeepSeek V4.1-Flash) → escalated to `claude-opus-5-5-medium` for rev3  
**Status:** DONE — 2026-09-23 Master audit (23 pass / 12 xfail coherence; CLI exit 0/2/3; isolated test DB proven `LLMCallLog` 3364→3364; full offline bank run by Master). rev1+rev2 haiku rejected: no DB bootstrap, exit 0 on engine error, "0.0 is correct" misreport. Known harness defect carried: stub advances per LLM call not per turn (fix in PV2-1x). Evidence §2  
**Owner Master:** Pulse  
**Objectives served:** C1, C2, C3, C6, C7, C8, C9, A1 — measurement harness only.

#### Objective
The CI eval (`ai/eval/run_harness.py`) measures single-turn grounding/deny/fabrication. Nothing measures whether Pulse **remembers the conversation**. Build a declarative multi-turn golden bank plus an offline runner that drives real `dispatch_task("chat", …)` turns with a **scripted stub LLM** (same seam as `test_chat_wiring.py`), feeds each turn the accumulated conversation history exactly as the product does, and scores coherence metrics from the response + ledger. Baseline is expected to be red — encode expectations as `xfail(strict=False)` like ECF-0. **No runtime code changes.**

#### Files to Read First
- `backend/ai/tests/test_chat_wiring.py` — stub client + `dispatch_task` pattern (copy the fixture approach).
- `backend/ai/engine_runtime.py` lines 100–125 (payload shape: `conversation_history: {conversation_id, messages:[{role,content}]}`) and 395–440 (result keys; after PV2-0A also `turn_decision`, `llm_calls`, `llm_calls_by_stage` — read them with `.get()` defaults so 0B does not depend on 0A landing first).
- `backend/ai/eval/run_harness.py` + `ai/eval/test_harness_golden.py` — metrics JSON + pass^k conventions to mirror.
- `backend/ai/eval/scenarios_nibras.py` — declarative scenario style.
- `docs/pulse/PULSE-V2-INTELLIGENCE-CONTRACT.md` §3 — objective definitions and thresholds (C1 ≥ 95%, C3 ≥ 95%, C2 100%, C7 100%, C8 ≤ 2 LLM calls).
- `docs/pulse/QA-CHAT-AGENTIC-SCENARIO-BANK.md` — existing scenario ids (PC-090/091/350) so scripts reference, not duplicate.

#### What to Build
1. **CREATE `backend/ai/eval/multiturn/__init__.py`**, **`bank.py`**, **`runner.py`**, **`scripts/*.yaml`** (12 files).
2. **Script schema (`bank.py`, dataclasses + YAML loader with validation):**
   ```yaml
   id: ess-loan-ar-01
   objective_ids: [C1, C3, C8]
   language: ar            # ar | en | mixed
   surface: chat           # chat only in P0
   persona: emp_1067
   turns:
     - user: "أريد قرض طارئ ٥٠٠٠ دينار"
       stub_reply: "..."                 # what the scripted LLM returns for THIS turn
       expect:
         decision_in: [clarify, answer, handoff_agent]
         must_not_reask_slots: [amount, loan_type]   # checked against reply text via slot patterns
         language: ar
         max_llm_calls: 2
         mentions_any: ["٥٠٠٠", "5000"]  # grounded recall of a prior fact
   ```
   Fields: `id`, `objective_ids`, `language`, `persona`, `turns[]` with `user`, `stub_reply`, optional `stub_tool_calls` (list; pass through to the stub as `tool_calls=None` for P0 unless trivially supportable), and `expect{decision_in, must_not_reask_slots, language, max_llm_calls, mentions_any, mentions_none, focus_entity}`. Validate on load; a malformed script fails loudly.
3. **Slot / language detectors (`bank.py`):** small deterministic helpers — `detect_language(text) -> "ar"|"en"|"mixed"` (Arabic Unicode range ratio), `reasks_slot(reply, slot) -> bool` using a per-slot bilingual regex table for: `amount`, `loan_type`, `leave_type`, `start_date`, `end_date`, `reason`, `date`, `time_from`, `time_to`, `employee`. Keep the table in one dict; unit-test it.
4. **Runner (`runner.py`):**
   - `run_script(script, *, instance_id="nibras") -> ScriptResult` — for each turn: build the stub client returning `stub_reply`, call `dispatch_task("chat", payload, instance_id=instance_id)` with `conversation_history.messages` = all prior `{role,content}` pairs (user + assistant content actually returned), then evaluate `expect` and collect per-turn `{decision, llm_calls, language_ok, reask_violations, mentions_ok, passed}`.
   - `run_bank(paths) -> BankReport` with metrics: `focus_retention` (turns with `mentions_any`/`focus_entity` satisfied ÷ applicable), `slot_carry_over` (1 − reask violations ÷ applicable), `tool_recall` (mentions of prior stub facts), `language_fidelity`, `router_agreement` (turns whose `decision` ∈ `decision_in` ÷ applicable), `llm_calls_p50`, `llm_calls_max`, `turns_over_budget`, and per-objective pass ratios keyed by `objective_ids`.
   - CLI: `python -m ai.eval.multiturn.runner --report /tmp/pv2-multiturn.json [--scripts <glob>]` prints a PASS/FAIL table + metrics JSON; **exit 0 always in P0** (report-only) unless a script is malformed or the engine raises.
   - Reuse `test_chat_wiring.py` env switches (`AGENT_ORCHESTRATOR_ENABLED=false`, `KG_MULTI_STEP_ENABLED=false`) so the single-pass spine runs; document in the module docstring which paths the offline tier cannot exercise (fan-out, live tools).
5. **12 scripts (`scripts/`)** — 8–12 turns each, bilingual where marked, each tagged with objective ids:
   `ess-loan-ar-01` (slot carry-over + no re-ask) · `ess-leave-en-01` (dates given turn 1, never re-asked) · `ess-attendance-mixed-01` · `payroll-followup-en-01` (net pay asked, then "and after GOSI?" → C1/C2) · `entity-focus-switch-01` ("tell me about Reena" → "her position?" → "now Salman" → "his?") · `grounded-recall-01` ("what was the number you gave me?") · `plan-status-01` ("what happened to my loan request?" → C9; expect `decision_in: [answer, handoff_agent]`, no re-derivation) · `chat-handoff-write-01` (write intent → `handoff_agent`, PC-090/091/350 semantics, never `tool_answer`) · `language-fidelity-ar-01` (Arabic throughout incl. after English tool-ish content) · `date-awareness-01` ("today's date?" never asked back) · `memory-learn-fact-01` (turn 1 teaches a fact + confirm, turn 3 uses it → C10) · `nav-zero-llm-01` (navigation turns expect `max_llm_calls: 0`).
6. **CREATE `backend/ai/eval/test_multiturn_bank.py`** marked `pytest.mark.eval_multiturn` (register the marker in `backend/pytest.ini` — additive line only): structural tests (12 scripts load, every script has ≥ 8 turns and ≥ 1 objective id, all objective ids ∈ C1–C10/A1–A10, slot regex table covers every slot referenced) **PASS**; per-script coherence expectations run under `xfail(strict=False, reason="PV2-0B baseline — Pulse v2 not yet implemented")` so red baselines show as XFAIL, never ERROR. Detector unit tests (language, reask) PASS.

#### DO NOT TOUCH
- Any runtime file under `backend/ai/engine/**`, `engine_runtime.py`, `plans_service.py`; `run_harness.py`; CI workflows; `docs/**` (Master owns docs); frontend; `backend/people/**`.

#### Verification Gate (run + paste literal output)
```bash
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest ai/eval/test_multiturn_bank.py -v -p no:cacheprovider 2>&1 | tail -40
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m ai.eval.multiturn.runner --report /tmp/pv2-multiturn.json 2>&1 | tail -40
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest ai/eval/test_harness_golden.py -q -p no:cacheprovider 2>&1 | tail -5
cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/import-boundary-lint.py
```
Expected: structural + detector tests PASS, coherence rows XFAIL (0 ERROR) · runner prints 12 scripts + metrics JSON and exits 0 · existing harness still green · import boundary clean.
Append to `TASK-RESULTS.md` as `## PV2-0B` with the metrics JSON block verbatim.

---

### Phase PV2-0C — QA: P0 baseline report (after 0A + 0B)
**Date:** 2026-09-22  
**Worker Role:** qa-validator  
**Recommended Model:** Cursor `composer-2.5-fast`  
**Status:** DONE — 2026-09-23 run by Master (both workers died 20:47 on shared test-DB collision). Offline 12×8 + live 3×8 as `emp_1067` with real LLM. Runner gained `--live/--host-user/--no-isolated-db`. Baseline: live router_agreement 0.50–0.625, llm p50=3 (answer) / 5 (tool), 19/24 turns over budget; 8 findings F-LIVE-1…8 in `docs/pulse/evidence/PV2-baseline-2026-09-22.md` §3–4  
**Owner Master:** Pulse

#### Objective
Run the multi-turn bank (offline tier) and, when `LLM_API_KEY` is present in `backend/.env`, one live pass of three scripts (`ess-loan-ar-01`, `payroll-followup-en-01`, `chat-handoff-write-01`) against the nibras dev stack as `emp_1067` (credentials per `.cursor/rules/nibras-dev-credentials.mdc`; **STACK-HOLD** in COMMS first). Record baseline numbers per objective in `docs/pulse/evidence/PV2-baseline-2026-09-22.md` (Master-reviewed) and paste the metrics JSON in TASK-RESULTS.md. No code changes.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m ai.eval.multiturn.runner --report /tmp/pv2-baseline.json 2>&1 | tail -40
```

---

### Wave W1 (P1) — dispatch order
```
W1a  PV2-1B (baseline defects, runner.py gates)  ∥  PV2-1C (memory wired + tool digests)
W1b  PV2-1A (ConversationState store + StateBlock)   — after 1B, same file runner.py
```
Parallel workers MUST set a distinct `TEST_DB_NAME` (see `config/settings.py`) — W0 workers died on a shared test-DB collision.

### Phase PV2-1B — Backend: baseline defects F-LIVE-1/3/5 (behaviour change, tested)
**Date:** 2026-09-23  
**Worker Role:** backend-worker  
**Recommended Model:** Cursor `claude-opus-5-5-medium` (runner.py → opus per ladder)  
**Status:** DONE — 2026-09-23 Master audit (25/25 new; 170 regression incl. previously-failing `test_dispatch_chat_returns_completed` — it was a nav over-fire; offline router 0.781→0.917, llm max 5→3, p50 3; import boundary 9). Config-driven scope: `topic_guard.in_scope{en,ar}` + `refusal_ar` in nibras `instance.yaml`; `FANOUT_PROBE_MIN_TOKENS` setting; `turn/language.py` helper.  
**Master notes / carried:** (a) nav still over-fires on *statements* ("I need to take annual leave from Jan 15…") — P4 Arbiter scope; (b) pre-LLM topic guard in `engine_runtime.py` refuses English-only → PV2-1D; (c) **security review**: two `intent.py` overrides (compensation; instruction-shaped-name) rewrite jailbreak-shaped messages so they are never refused — open a Sec item before P4 flip; (d) `turns_over_budget` 83→86 because ex-nav turns are now answered (2–3 calls) against YAML budgets of 0–1 — YAML untouched per RULE_28, revisit budgets in P6.  
**Owner Master:** Pulse  
**Evidence driving it:** `docs/pulse/evidence/PV2-baseline-2026-09-22.md` §3

#### Objective
Remove three deterministic defects that the live baseline proved on every turn, without touching routing precedence (that is P4):
1. **F-LIVE-5 fan-out probe.** `_try_fan_out` spends one LLM call on every answer turn (`by_stage` = `intent+fanout+draft`) and returns `None` almost always. Gate it: skip the probe when the intent zone is `ess`/`nav`/`clarify` or when `conversation_history` shows an active process brief; keep it for analytical/multi-entity questions. Add setting `FANOUT_PROBE_MIN_TOKENS` (default 12 words) — short utterances never probe. Log `fanout_skipped reason=…`.
2. **F-LIVE-1 refuse template.** The scope-refusal path (`runner.py` ≈ 2040–2051, decision `refuse`) fired on «أريد قرض طارئ ٥٠٠٠ دينار» and answered in English while listing loans as in-scope. (a) The refusal must never fire when IntentResolver's zone is in the instance's declared scope (loan/leave/payroll/attendance) — treat as `answer`/`clarify`. (b) When it does fire, the template must follow the user's language (AR/EN detection already exists — reuse `detect_language`-equivalent in engine, do not import from `ai.eval`).
3. **F-LIVE-3 nav over-fire.** Navigation short-circuit fired on questions («هل ستتم الموافقة عليه؟», "When will next month's payroll be processed?") because they contain a module noun. Rule: an utterance that is interrogative (ends with `?`/`؟`, or starts with AR/EN question words: متى/هل/كيف/لماذا/ما/when/how/why/what/is/will/can/does) and is longer than 3 tokens is **not** a navigation command unless it also contains an explicit nav verb (open/go to/show me/افتح/اذهب/أرني). Pure noun phrases ("payroll", "الرواتب") still navigate.

#### DO NOT TOUCH
`plan/loop.py`, `plans_service.py`, `engine_runtime.py`, `context_assembler.py`, `memory/**`, prompts (`prompts.py`) other than the refuse template, `ai/eval/**` (1C/1A own those).

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python manage.py check
cd /home/ahmed/ws/carbon/backend && TEST_DB_NAME=test_nibras_dev_w1b ../.venv/bin/python -m pytest ai/tests/test_pv2_baseline_defects.py -v -p no:cacheprovider
cd /home/ahmed/ws/carbon/backend && TEST_DB_NAME=test_nibras_dev_w1b ../.venv/bin/python -m pytest ai/tests/test_pv2_instrumentation.py ai/tests/test_chat_wiring.py ai/tests/test_navigation_resolver.py ai/tests/test_intent_resolver.py ai/tests/test_intent_zone.py ai/tests/test_named_leave_intent.py ai/tests/test_pulse_loop.py -q -p no:cacheprovider
cd /home/ahmed/ws/carbon/backend && TEST_DB_NAME=test_nibras_dev_w1b ../.venv/bin/python -m ai.eval.multiturn.runner --report /tmp/pv2-1b-offline.json 2>/dev/null | grep -v "Registered plugin" | tail -16
cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/import-boundary-lint.py 2>&1 | tail -2
```
**Acceptance:** new tests (≥ 8: fanout skipped on ESS/short; probe still runs on a long analytical question; AR loan not refused; refuse template AR; 4 nav-question negatives + 2 nav-noun positives) green · regression green except the known `test_dispatch_chat_returns_completed` · offline bank `router_agreement ≥ 0.85` (was 0.781) and `llm_calls_p50 ≤ 3` (was 4) · import boundary still 9.

---

### Phase PV2-1C — Backend: memory_manager wired + per-message tool digests
**Date:** 2026-09-23  
**Worker Role:** backend-worker  
**Recommended Model:** Cursor `claude-opus-5-5-medium`  
**Status:** DONE — 2026-09-23 Master audit (11/11 new; 80 regression incl. `test_chat_wiring` now green; import boundary 9). `MemoryManager(db, host_user_id)` wired; lexical recall lane in `LongTermMemory` (vector store returns nothing for facts locally); `tool_digest` persisted in `metadata_json` and replayed via `render_history_content` (≤ 200 chars, scope-filtered); runner `engine_single_pass()` fixes the ineffective `override_settings` — **PV2-0B/0C baselines ran with fan-out ON**.  
**Master notes:** (a) `_keyword_match_facts` scans all active facts in scope in Python — bound it (recency cap 500 rows) in PV2-1A or 2A; (b) `RetrievalWitness` still doesn't pass `host_user_id` — clean fix belongs to 1A (`runner.py`); (c) QA follow-up for the offline tier: authenticated persona + `learn_fact`/tool stubs so memory/digests are measurable offline.  
**Owner Master:** Pulse

#### Objective
Plan §5 P1 bullets 3–4. (1) `memory_manager=MemoryManager(db)` is constructed and passed to `TurnPipelineRunner` in `engine_runtime._run_chat` (≈ lines 181–203) so `learn_fact` recall works in Chat; regression test: turn 1 `learn_fact("my cost centre is CC-42")` (Chat-confirm path per ADR-0046) → turn 3 "what's my cost centre?" answers `CC-42` with stub LLM given the memory block. (2) `assemble_context` (`context_assembler.py`) appends a per-message tool digest (≤ 200 chars, built from `tool_trace`/`RunStep.tool_output_json` through the retrieval RBAC scope — never raw payloads) to each assistant history message that had tool results, so the model can recall "eligible=true, max=8000 SAR" three turns later. (3) Fix the offline runner caveat: `override_settings` does not reach the engine's pydantic `Settings` — set `AGENT_ORCHESTRATOR_ENABLED`/`KG_MULTI_STEP_ENABLED` via `monkeypatch.setenv` + `get_settings.cache_clear()` (or an explicit `Settings` override hook) and correct the `CAVEATS` text.

#### DO NOT TOUCH
`turn/runner.py` (1B owns it), `plan/loop.py`, `plans_service.py`, prompts other than the memory/history blocks.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python manage.py check
cd /home/ahmed/ws/carbon/backend && TEST_DB_NAME=test_nibras_dev_w1c ../.venv/bin/python -m pytest ai/tests/test_pv2_memory_digests.py -v -p no:cacheprovider
cd /home/ahmed/ws/carbon/backend && TEST_DB_NAME=test_nibras_dev_w1c ../.venv/bin/python -m pytest ai/tests/test_memory_api.py ai/tests/test_gap9_memory_confirm.py ai/tests/test_gap2_working_memory.py ai/tests/test_auto_memory.py ai/tests/test_context_assembler.py ai/tests/test_context_lifecycle.py ai/tests/test_chat_wiring.py ai/eval/test_multiturn_bank.py -q -p no:cacheprovider
cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/import-boundary-lint.py 2>&1 | tail -2
```
**Acceptance:** `learn_fact` recall test green · digest test proves ≤ 200 chars + RBAC scoping (a field outside scope is absent) · `grounded-recall-01` and `memory-learn-fact-01` scripts improve on the offline bank (report before/after) · import boundary 9.

---

### Phase PV2-1A — Backend: durable ConversationState + StateBlock in draft prompt
**Date:** 2026-09-23  
**Worker Role:** backend-worker  
**Recommended Model:** Cursor `claude-opus-5-5-medium`  
**Status:** DONE — 2026-09-23 00:55 Master audit (15/15 new; 195 passed / 12 xfail across the PV2 + adjacent suites; import boundary 9; antipatterns GATE PASSED). `state_store.py` (709 lines: schema v1, bounded, RBAC redaction on load, owner check, Redis mirror best-effort, `render_state_block` ≤ 600), loaded in `run()` and saved through the single exit seam; `TurnLedger.state_saved/state_size`; clear/undo wired; `host_user_id` reaches `RetrievalWitness`; lexical recall bounded to 500 newest rows in SQL (`Session.select` gained `order_by/limit`). Offline bank unchanged (router 0.917, p50 3, slot 1.0) — `focus_retention` cannot move in the stub tier; proven instead by a prompt-reading stub test (slots reach turns 2–3, no re-ask).  
**Master notes / carried:** (a) **bank flakiness** — `auto_memory` fire-and-forget call is counted only if it finishes before finalize → `turns_passed` swings 3–7/96 between runs. Fix in PV2-2C: report `llm_calls` = foreground only, add `llm_calls_background`; (b) topic-guard-refused turns (pre-LLM, `engine_runtime.py`) write no state → 2C; (c) `open_question.slot` empty until a slot-level clarify signal exists (3C); (d) ReAct/multi-step paths don't get the StateBlock yet → 2B.  
**Owner Master:** Pulse
**Also absorbs (from 1B/1C notes):** pass `host_user_id` through `RetrievalWitness` (`turn/retrieve.py` ← `runner.py`) instead of relying on the `MemoryManager` binding; bound `LongTermMemory._keyword_match_facts` to the 500 most-recent active rows.

#### Objective
Plan §4.2 + §5 P1 bullets 1–2, 5. New `engine/cognition/state_store.py`: `ConversationState` dataclass (schema v1 exactly as §4.2: focus, intent, slots, open_question, last_results, active_plans, decisions, language, surface_last) + `ConversationStateStore` (load/save/redact/clear; Django `ConversationContextRecord.session_json` primary, Redis mirror best-effort; v1 `version` key; bounded lists — focus 5, last_results 8, decisions 12). Populate at end of every turn in `TurnPipelineRunner` from existing signals: intent (IntentResolver), focus (`WorkingMemory`), slots (`process_brief`/`write_slots` when present), `last_results` digests (1C's digest builder), `open_question` (clarify decision + slot), `decisions` (PV2-0A `turn_decision`), `language`, `surface_last="chat"`. Render `StateBlock` (≤ 600 chars) into the draft prompt via the existing assembler. Clear on `_snapshot_with_clear_break` semantics. Tenancy: keyed by `(instance_id, conversation_id)`; redact on load by host user RBAC scope.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && TEST_DB_NAME=test_nibras_dev_w1a ../.venv/bin/python -m pytest ai/tests/test_pv2_state_store.py -v -p no:cacheprovider
cd /home/ahmed/ws/carbon/backend && TEST_DB_NAME=test_nibras_dev_w1a ../.venv/bin/python -m pytest ai/tests/test_pv2_instrumentation.py ai/tests/test_chat_wiring.py ai/tests/test_pulse_loop.py ai/eval/test_multiturn_bank.py -q -p no:cacheprovider
cd /home/ahmed/ws/carbon/backend && TEST_DB_NAME=test_nibras_dev_w1a ../.venv/bin/python -m ai.eval.multiturn.runner --report /tmp/pv2-1a-offline.json 2>/dev/null | grep -v "Registered plugin" | tail -16
```
**Acceptance:** store round-trip/redact/clear/bounded tests green · state written on 100 % of turns (assert via ledger) · offline `slot_carry_over` stays 1.0, `focus_retention` improves vs baseline (report numbers) · tenancy isolation test · import boundary 9.

---

### Wave W2 (P2) — dispatch order
```
W2a  PV2-2C role-scoped tool catalog + audience-aware persona (closes F-LIVE-6)   — after 1A (runner.py)
W2b  PV2-2A IdentityBlock + ContextPack for chat stages (draft/critic/intent/synthesis/verify)
W2c  PV2-2B ContextPack for plan stages (planner decompose / observe / plan synthesis / discovery)
```
All on `claude-opus-5-5-medium`; distinct `TEST_DB_NAME` each.

### Phase PV2-2C — Backend: role-scoped tool catalog + audience-aware persona guidance
**Date:** 2026-09-23  
**Worker Role:** backend-worker  
**Recommended Model:** inherit Master (Task may only list composer — omit model)  
**Status:** DONE — 2026-09-23 01:15 Master audit (11/11 new; 193 passed / 12 xfail; import boundary 9; antipatterns GATE PASSED; two offline bank runs identical: turns_passed 8, over_budget 82, llm p50/max **2/2**, router 0.917, slot 1.0). Foreground-only meter killed auto_memory flakiness. F-LIVE-6 closed offline (catalog + IdentityBlock + 403 twin-retry). Live payroll re-check batched for morning.  
**Owner Master:** Pulse  
**Evidence:** F-LIVE-6 root cause in `docs/pulse/evidence/PV2-baseline-2026-09-22.md` §3 — an employee was steered to `list_payslip_lines` (HR API, host 403) because the persona prompt says "You have full read access … using list_payslip_lines" and the catalog is not filtered by role.

#### Objective
1. `api_catalog` entries in `instance.yaml` gain `audience: [ess|hr|admin]` (default `hr` for unmarked; all `*_my_*` + nav routes → `ess` and `hr`). Loader validates the enum.
2. The tool list offered to the model (chat draft, tool-synthesis, discovery, planner) is filtered by the user's audience, derived once per turn from the Django user (`is_staff`/`is_superuser` → admin; People HR role/group → hr; linked `Employee` only → ess). One helper `audience_for_user(user) -> set[str]` in the host (`ai/identity_propagation.py` is the natural home) passed through `user_info`; engine filters on `user_info["audience"]` — no host import in the engine.
3. Persona guidance becomes audience-blocks: `system_prompt` keeps the shared identity; new `guidance_by_audience: {ess: …, hr: …}` in `instance.yaml`; the runner appends only the user's block. The ESS block says "use `list_my_payslips` / `list_my_leave` / `list_my_loans`; you can only read your own records"; the HR block keeps today's text. This is a precursor of P2's `IdentityBlock` — put the assembly in the new `engine/cognition/context_pack.py` as `IdentityBlock(persona, audience, guidance)` so 2A extends rather than rewrites it.
4. Host 403 on `call_host_api` must produce an honest, actionable reply in the user's language ("I can only read your own payslips — here they are" and retry with the `*_my_*` twin when one exists in the catalog), not "permission issue on your account".
5. **Deterministic LLM accounting (from 1A notes):** `_finalize_meter` reports `llm_calls` = foreground calls only (exclude stages tagged background: `auto_memory`) and adds `llm_calls_background`; ledger + chat result + multiturn runner (`ai/eval/multiturn/runner.py` reads `llm_calls`) follow. Test: 6 consecutive stubbed turns give identical `llm_calls`. This removes the 3–7/96 swing in `turns_passed`.
6. Turns refused by the pre-LLM topic guard in `engine_runtime.py` must still save `ConversationState` (decision `refuse`) — reuse the store; test.

#### DO NOT TOUCH
`plan/loop.py`, `plans_service.py` (2B), `ai/eval/**` YAML expectations. `state_store.py` may be read and called, not restructured.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python manage.py check
cd /home/ahmed/ws/carbon/backend && TEST_DB_NAME=test_nibras_dev_w2c ../.venv/bin/python -m pytest ai/tests/test_pv2_audience_catalog.py -v -p no:cacheprovider
cd /home/ahmed/ws/carbon/backend && TEST_DB_NAME=test_nibras_dev_w2c ../.venv/bin/python -m pytest ai/tests/test_pv2_baseline_defects.py ai/tests/test_pv2_state_store.py ai/tests/test_chat_wiring.py ai/tests/test_tool_execution_actions.py ai/tests/test_plans.py ai/eval/test_multiturn_bank.py -q -p no:cacheprovider
cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/import-boundary-lint.py 2>&1 | tail -2
```
**Acceptance:** `emp_1067` tool list contains `list_my_payslips` and **not** `list_payslip_lines`/`list_employees`; `admin` sees both; unknown audience → ess (least privilege); 403 twin-retry test; persona block test (ESS text present, HR text absent for an employee); regression green; import boundary 9. Live check by Master: payroll-followup t1 answers from `list_my_payslips`.

---

### Phase PV2-2A — Backend: IdentityBlock + ContextPack for every chat-turn LLM stage
**Date:** 2026-09-23  
**Worker Role:** backend-worker  
**Recommended Model:** inherit Master  
**Status:** DONE — 2026-09-23 09:20 Master audit (5/5 context_pack; 143/12 regression; offline unchanged vs 2C; import boundary 9 after fixing engine→context_assembler import)  
**Owner Master:** Pulse

#### Objective
Plan §4.3 + §5 P2 for the chat turn. `engine/cognition/context_pack.py`: `IdentityBlock` (persona · today's date + tz · user name/role/employee_no/audience · language · surface `chat` · autonomy rules for the surface = ADR-0046 wording), `StateBlock` (1A), `HistoryBlock` (1C digests), `KnowledgeBlock`/`MemoryBlock` (as today), `TaskBlock` (stage-specific). `build_context_pack(state, surface, stage, …) -> ContextPack` with `.system_prompt()` and `.user_prompt()`; hard budgets per block. Refactor consumers so **every** `route_chat` in the chat turn takes its system prompt from the pack: draft (`build_chat_prompt`), critic (`CRITIC_SYSTEM_PROMPT` → TaskBlock only), IntentResolver, tool-synthesis, verify, escalate, weather-normalize. Static test: AST/grep test asserting no `route_chat(` call site in `turn/**` passes a literal or module-level system prompt string — only `pack.system_prompt()`.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && TEST_DB_NAME=test_nibras_dev_w2a ../.venv/bin/python -m pytest ai/tests/test_pv2_context_pack.py -v -p no:cacheprovider
cd /home/ahmed/ws/carbon/backend && TEST_DB_NAME=test_nibras_dev_w2a ../.venv/bin/python -m pytest ai/tests/test_pv2_*.py ai/tests/test_chat_wiring.py ai/tests/test_intent_resolver.py ai/tests/test_critic*.py ai/eval/test_multiturn_bank.py -q -p no:cacheprovider
cd /home/ahmed/ws/carbon/backend && TEST_DB_NAME=test_nibras_dev_w2a ../.venv/bin/python -m ai.eval.multiturn.runner --report /tmp/pv2-2a-offline.json 2>/dev/null | grep -v "Registered plugin" | tail -16
```
**Acceptance:** static test green (0 stage-local identity prompts in `turn/**`); date-class golden ("what is today's date" answered from IdentityBlock, 0 tool calls); `language_fidelity` ≥ baseline; offline router/llm metrics not worse; existing harness pass^k = 3 (`ai/eval/run_harness.py` ×3).

---

### Phase PV2-2B — Backend: ContextPack for plan stages (Agent surface)
**Date:** 2026-09-23  
**Worker Role:** backend-worker  
**Recommended Model:** Cursor `claude-opus-5-5-medium`  
**Status:** DONE — 2026-09-23 09:30 Master audit (16 ContextPack; 169 regression; import boundary 9; antipatterns GATE PASSED). W2 (P2) complete.  
**Owner Master:** Pulse

#### Objective
Same pack, `surface="agent_plan" | "agent_discovery"`, consumed by planner decompose (`plan/planner.py`), step draft/observe/plan-synthesis (`plan/loop.py` ≈ 2312–2337, 2957–2988), discovery (`plans_service.start_discovery`, `plans_service.py` ≈ 2434–2457, 3887). Autonomy rules for the Agent surface = RULE_21 wording (stage with consent; never claim commit before receipt). A5 legibility: each step's pre-consent text is rendered from bound values in the user's language via TaskBlock templates (AR/EN) — no free-form identity text. Static test extended to `plan/**` and `plans_service.py`.

**Acceptance:** static test covers `plan/**`; `test_plans.py`, `test_pulse_loop.py`, `test_react_consent_boundary.py`, `test_plan_lifecycle.py` green; loan/leave/attendance ESS plan goldens produce identical step wording at pass^k = 3; import boundary 9.

---

### Wave W3 (P3) — dispatch order (after W2; files disjoint → 3A ∥ 3B, then 3C)
```
W3a  PV2-3A deterministic-first plan steps (plan/loop.py, export_bind.py)   ∥   PV2-3B truthful Chat surface + handoff_agent (turn/runner.py, engine_runtime.py)
W3b  PV2-3C discovery: no LLM on scope_route; StateBlock-aware (plans_service.start_discovery)
```

### Phase PV2-3A — Backend: deterministic-first `process_dial` steps (A2, A4, A9)
**Worker Role:** backend-worker · **Model:** inherit Master · **Status:** DONE — 2026-09-23 09:50 Master audit (12/12 + 148 W3 regression; import boundary 9) · **Owner:** Pulse

#### Objective
Plan §4.4/§5 P3. In `ReActLoop`, a step whose `tool_name == call_host_api` and whose `tool_args` are fully bound from `write_slots` (no `{{…}}` placeholders, all required catalog params present) skips DraftWitness and observe entirely: bind → stage (consent, RULE_21) → commit → deterministic summary. Summaries come from bilingual templates keyed by `api_name` (AR/EN, QA-reviewed strings in `instance.yaml` `step_templates`), rendered from bound values — never LLM prose. The `llm_meter` for such a step must read `llm_calls == 0`. Unbound/partial steps keep today's path. `_INLINE_COMMIT` path in `plans_service.confirm_step` reuses the same template for `run.final_response`.

**Acceptance:** `test_pv2_deterministic_steps.py`: loan/leave/attendance bound steps → `llm_calls == 0`, AR + EN summary snapshots, consent still required (`mutation_not_confirmed` when not granted), partial-binding step still drafts; `test_plans.py`, `test_pulse_loop.py`, `test_react_consent_boundary.py`, `test_plan_lifecycle.py` green; import boundary 9; ESS plan p50 latency (stub) reported before/after.

---

### Phase PV2-3B — Backend: truthful Chat surface — `handoff_agent` decision (C5, F-LIVE-2, F-LIVE-4)
**Worker Role:** backend-worker · **Model:** inherit Master · **Status:** DONE — 2026-09-23 09:50 Master audit (15/15 handoff + F-LIVE-2/4 Chat path; import boundary 9) · **Owner:** Pulse

#### Objective
Root cause (Master, PV2-0C): `_try_multi_step_plan` (`runner.py` ≈ 2691) runs a `process_dial` ReActLoop **inside Chat**; the mutation step pauses for consent that Chat can never grant (ADR-0046) and the user sees "I need your approval before I can proceed." Fix: (1) before running the loop in Chat, inspect the plan; if any step is a mutating `call_host_api` (catalog `requires_confirmation` or non-GET), do **not** execute — emit `TurnDecision = handoff_agent` with a deterministic bilingual reply built from the brief + bound slots ("I have: emergency loan, 5,000 SAR, 12 months. To submit it, switch to Agent — I'll carry these details over." / AR equivalent) and persist `intent`/`slots`/`open_question` into `ConversationState` (1A) so P5 can inherit them. Read-only plans still run. (2) `_should_force_action` (`engine_runtime.py:793`) becomes a logged fallback: the Chat grounding block (2A `IdentityBlock` autonomy rules) tells the model it hands off rather than calls write tools; count `force_action_fired` in the ledger; target 0 on the bank. (3) The Chat prompt must never say "CALL THE TOOL" for a write API (grep test on assembled prompt for an ESS write utterance).

**Acceptance:** `chat-handoff-write-01` t1–t3 → `handoff_agent` with slots in state and 0 host staging (`Run`/`RunStep` rows unchanged, assert); `ess-loan-ar-01` t8 no longer "approval" text; `force_action_fired == 0` on the offline bank; `test_chat_wiring.py`, `test_pv2_baseline_defects.py`, `test_pv2_state_store.py`, G2 QA bank items PC-090/091/350 (see `docs/qa`) green; import boundary 9.

---

### Phase PV2-3C — Backend: discovery without LLM on `scope_route`; never re-ask known slots (A4)
**Worker Role:** backend-worker · **Model:** inherit Master · **Status:** DONE — 2026-09-23 09:50 Master audit (5/5 discovery; import boundary 9) · **Owner:** Pulse

#### Objective
`plans_service.start_discovery`: when `scope_route` short-circuits to a known process dial, no LLM call is made (meter = 0); otherwise discovery receives the `StateBlock` (1A) and the `ContextPack(surface="agent_discovery")` (2B) and must not ask for any slot already present in `ConversationState.slots` or the brief. Clarification wording from bilingual templates.

**Acceptance:** `test_pv2_discovery.py`: short-circuit → 0 LLM calls; state with `amount` → discovery never asks amount (AR/EN); regression `test_plans.py`, `test_plan_lifecycle.py`; import boundary 9.

---

### Wave W4 (P4) — Arbiter shadow → flip
```
W4a  PV2-4A TurnDecision + Arbiter.decide + signal producers (shadow log)     — after W3
W4b  PV2-4B Flip default to Arbiter; PULSE_ARBITER=legacy kill switch         — after soak evidence
```
Calendar: W4a lands code + shadow logging → status **SOAKING** for ≥7 days of disagreement logs before W4b.

### Phase PV2-4A — Backend: Arbiter in shadow mode (C4, A10)
**Worker Role:** backend-worker · **Model:** inherit Master · **Status:** SOAKING — landed 2026-09-23 09:55; flip (4B) no earlier than 2026-09-30 · **Owner:** Pulse

#### Objective
Plan §4.1/§5 P4. New `engine/cognition/turn/arbiter.py`: `TurnDecision` enum (`refuse`, `navigate`, `clarify`, `handoff_agent`, `answer`, `tool_answer`, `memory_confirm`, … — extend from PV2-0A `turn_decision` strings already logged) + `Arbiter.decide(signals) -> TurnDecision` with documented precedence: safety/topic refuse > pending memory confirm > explicit process brief > handoff_agent (P3) > navigation > deixis/clarify > intent zone > default answer. Convert early-exit gates in `runner.py` into **signal producers** that always populate `ledger.decision_signals`; in shadow mode (`PULSE_ARBITER=shadow`, default for one release) the runner still executes the **legacy** early-exit path but logs `[arbiter-shadow] legacy=X arbiter=Y agree=bool`. Persist both to `ConversationState.decisions`. Conflict-pair unit tests (same utterance, two gates that used to race). No behavior change when agree=true; when disagree, log only.

**Acceptance:** decision log on 100% turns; shadow disagreement rate reported on offline bank; zero behavior change vs W3 offline metrics (router/llm within noise); `test_pv2_arbiter.py` green; import boundary 9. Status after merge: **SOAKING** until Master posts 7-day shadow summary.

---

### Phase PV2-4B — Backend: Arbiter flip (after soak)
**Worker Role:** backend-worker · **Model:** inherit Master · **Status:** DONE 2026-09-23 — human waived the 2026-09-30 date. Default `PULSE_ARBITER=on`; recorded decision is Arbiter; `legacy` kill switch. Offline G5 stayed 96/96. Early-return bodies were not collapsed (they agree on the bank). · **Owner:** Pulse

#### Objective
Default `PULSE_ARBITER=on`; runner executes only Arbiter's decision; `PULSE_ARBITER=legacy` kill switch for one release. Remove duplicate early-exit execution paths (signals remain). Offline router_agreement ≥ 0.98 target or document remaining gaps as explicit exceptions.

**Acceptance:** live + offline gates; kill-switch test; G2 bank still green.

---

### Wave W5 (P5) — Chat ↔ Agent continuity
```
W5a  PV2-5A Discovery/Run inherit ConversationState + ContextPack(surface=agent_*)
W5b  PV2-5B Plan lifecycle → active_plans; Chat plan_status from state (0 LLM)
W5c  PV2-5C FE: Active-plans chip + Run drawer inherited-context (RULE_23 wording)
```

### Phase PV2-5A — Backend: Agent inherits Chat state (A1)
**Worker Role:** backend-worker · **Model:** inherit Master · **Status:** DONE — 2026-09-23 10:00 Master (slots inherit into discovery brief + run) · **Owner:** Pulse

#### Objective
`start_discovery` and `_execute_plan_once` build `ContextPack(surface="agent_discovery"|"agent_plan")` from `ConversationStateStore.load`; brief enriched with slots + last_results digests. Tenancy: state keyed by `(instance_id, conversation_id)`; test isolation. Closes F-LIVE-4 carry-over of slots into Agent.

**Acceptance:** Chat→Agent golden: slots from Chat appear in discovery brief 100%; no re-ask of amount/type; `test_plans.py` + PC-090/091/350 green; import boundary 9.

---

### Phase PV2-5B — Backend: active_plans write-back + Chat plan_status (C9, A8)
**Worker Role:** backend-worker · **Model:** inherit Master · **Status:** DONE — 2026-09-23 10:10 Master audit · **Owner:** Pulse

#### Objective
Plan lifecycle events (created/paused/completed/failed) update `ConversationState.active_plans`. Chat `plan_status` / "status of my request?" answered from state + `RunStep` rows with **0 LLM calls** when state has an active plan.

**Acceptance:** active_plans reflects lifecycle 100%; plan_status golden 0 LLM; regression green.

---

### Phase PV2-5C — Frontend: continuity widgets
**Worker Role:** frontend-worker · **Model:** inherit Master or composer for pure UI · **Status:** DONE — 2026-09-23 10:08 Master · **Owner:** Pulse · **FE seats:** Pulse (+ Nibras for copy review)

#### Objective
Active-plans chip in Chat; inherited-context panel in Agent Run drawer. RULE_23 outcome wording only. No Chat Confirm for host APIs (ADR-0046). i18n AR/EN.

**Acceptance:** vitest + Playwright smoke; no new host-mutation from Chat UI.

---

### Wave W6 (P6) — Eval gate & hardening
```
W6a  PV2-6A Multi-turn bank blocking in CI (G5 Coherence) + llm_calls / latency gates
W6b  PV2-6B Nightly live Nibras smoke job (emp_1067) — DONE 5/5
W6c  PV2-6C ADR-0047 Accepted; pulse-intelligence-contract rule; YAML budget revisit
```

### Phase PV2-6A — QA/CI: multi-turn bank as blocking gate
**Worker Role:** qa-validator · **Model:** inherit Master · **Status:** DONE — 2026-09-23 10:16 Master · **Owner:** Pulse

#### Objective
Wire `ai.eval.multiturn.runner` into CI with §3 thresholds (router ≥ 0.90, slot_carry 1.0, llm p50 ≤ 2 after P3, over_budget ≤ 10%). Fix stub-per-LLM-call harness defect (advance stub per *turn*, not per call). Revisit YAML `max_llm_calls` budgets that became wrong after nav-over-fire fix (RULE_28: change budgets with Master-approved evidence, not to hide regressions).

**Acceptance:** CI red on intentional break; green on main; document thresholds in QA bank G5.

---

### Phase PV2-6B — Ops: nightly live smoke — SOAKING
**Worker Role:** qa-validator · **Model:** inherit Master · **Status:** DONE — soak 5/5 (2026-09-26–30 PASS); 2026-09-23 FAIL stays · **Owner:** Pulse

#### Objective
Scheduled job: 3 ESS journeys Chat→Agent→Approve as `emp_1067` on Nibras dev; assert host rows + IC metrics. Status **SOAKING** until 5 consecutive green nights. STACK-HOLD / COMMS before first run.

**Landed:** `python -m ai.eval.nightly_ess_smoke` · GH catalog dry-run cron `0 2 * * *` · ledger `docs/pulse/evidence/PV2-6B-{soak.md,nights.json}`. Mutating run refused unless `--live --i-have-stack-hold --host-user emp_1067` and `PULSE_NIGHTLY_LIVE=1`. Dry-run / SKIP / FAIL do not increment the streak. Do not back-date nights. Night 2026-09-23: Chat handoff + slot_carry held; Agent Approve 200; no host row. See `PV2-6B-night-2026-09-23.md`.

**2026-09-23k (Chat, not 6B):** `seed_pulse_audit_payslips` wrote emp_1067 Aug 2026 committed identity 6500/1200/800/4500 on `nibras_dev`. Live 01/04/08 is 23/24. 6B streak stays 0/5.

**2026-09-23s (not 6B):** bound lookup+write live `Run.total_llm_calls=0` on leave/loan/attendance (`PV2-6B-verify-2026-09-23s`). G5 `--gate` 96/96. Night 2026-09-23 FAIL not rewritten.

**2026-09-26 (official night 2):** `--record` PASS. Chat no mutation; confirm 200; host_row yes; plan llm 0/0/0; A9 p50 1.3 s. Streak **1/5**. See `PV2-6B-night-2026-09-26.md`.

**2026-09-27 (official night 3):** `--record` PASS. Same IC. A9 p50 1.3 s. Streak **2/5**. See `PV2-6B-night-2026-09-27.md`.

**2026-09-28 (official night 4):** `--record` PASS. Same IC. A9 p50 1.3 s. Streak **3/5**. See `PV2-6B-night-2026-09-28.md`.

**2026-09-29:** `--record` PASS. Same IC. A9 p50 1.3 s. Trailing streak **4/5**. See `PV2-6B-night-2026-09-29.md`.

**2026-09-30:** `--record` PASS. Same IC. A9 p50 1.5 s. Trailing streak **5/5**. Soak complete. See `PV2-6B-night-2026-09-30.md`.

**Acceptance:** 5 consecutive greens recorded in evidence/; then flip DONE. **Met.**

---

### Phase PV2-6C — Docs/rules: ADR-0047 Accepted + intelligence contract rule
**Worker Role:** docs / Master · **Status:** DONE — 2026-09-23 · **Owner:** Pulse

#### Objective
ADR-0047 → Accepted; `.cursor/rules/pulse-intelligence-contract.mdc`; canvas + plan doc marked v2 exit criteria met.

**Acceptance:** ADR status Accepted; rule file present; Master close-out in TASK-RESULTS. **Met** — `.ai-toolkit/decisions/0047-pulse-unified-conversation-state.md` Accepted; `.cursor/rules/pulse-intelligence-contract.mdc`; `TASK-RESULTS` PV2-6C.

**Landed:** G5 96/96 + 6B soak 5/5. Night 2026-09-23 FAIL not rewritten. 4A Arbiter shadow calendar is unchanged.

---

*End of PV2 phase specs. Calendar-bound phases stay SOAKING until elapsed — never fake a week.*
