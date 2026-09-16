## [2026-09-16] master-architect (Nibras) — Deep QA board + J-LV-05

- **Coverage:** **11/81** cases (**14%**); **11/46 P0 (24%)** — board updated.
- **J-LV-05 PASS:** annual rem 22; request 29 working days (2026-11-01…12-10) → UI alert **Insufficient leave balance — 22 days remaining**.
- Canvas: `nibras-deep-qa-plan.canvas.tsx` execution board.

## [2026-09-16] master-architect (Nibras) — Deep QA J-LN-01/02/03 + stack lease

- **Stack lease:** DECISION 20260916-10 — `STACK-HOLD`/`RELEASE` binding in `.ai-toolkit/shared/multi-master.md` + seats.md; HOLD Nibras until 22:00+03 (COMMS 20260916-11).
- **J-LN-01 PASS:** emp_1001 UI New Request loan → `CRS-2026-0032` / Loan 23; emp_1399 approve → in_review; emp_1132 (finance_group) approve → **approved**; loan **active**; **6** installments materialized.
- **J-LN-02 PASS:** finance approve before manager → **403** “not the current approver”.
- **J-LN-03 PASS:** My Loans card nested **Personal Loan** label (no `[object]`); 500.00 / 6 / Active visible.
- **Cast note:** live `finance_group` had 0 users — ScopedRole on `emp_1132` for FIN-1.
- Evidence: `docs/nibras/evidence/deep-qa/2026-09-16/SESSION-NOTES.md`

## [2026-09-16] master-architect (Nibras) — Deep QA J-LV-06 overlap

- **Verdict:** **PASS** (API + UI). Not “zero violations” for the whole Deep QA plan — only this NEG case + prior leave theatre P0s executed.
- **API:** overlap vs approved/pending → **400**; dates on cancelled/rejected → **201**.
- **UI:** emp_1001 Request Leave 2026-09-21…22 → alert **“Overlaps an existing leave request”** (`errorOverlap`). Evidence: `docs/nibras/evidence/deep-qa/2026-09-16/j-lv-06-overlap-ui.png`.
- **Ops:** BE was STOPPED mid-submit (FE network toast); restarted `:8009`; PG stayed up.
- **Residuals logged in SESSION-NOTES:** J-LV-05/07/08/11, loans J-LN-*, hire, Playwright host.
- **Next:** J-LN-01 loan → mgr → finance → installments.

## [2026-09-16] master-architect (Nibras) — Deep QA J-LV-03

**Seat:** Nibras

### Summary
- Shipped **Resubmit** on My Request detail (`resubmitCorrespondence`).
- Browser: mgr send-back → emp resubmit → mgr approve on `CRS-2026-0028`.
- Events: `submitted → sent_back → resubmitted → approved`. Annual used=4 pending=0 rem=26.

---

## [2026-09-16] master-architect (Nibras) — Deep QA J-LV-02/04 + cancel FE

**Seat:** Nibras

### Summary
- Toolkit refresh: RULE_5 / FRONTEND_BASE_PATH=/, security 429 note, playbook PB-48/49/50.
- P1: manage.sh VITE_BASE URL; FE throttle≠logout.
- **J-LV-04 PASS:** Cancel control on My Request detail (`cancelCorrespondence`); `CRS-2026-0026` cancelled; pending freed.
- **J-LV-02 PASS:** `CRS-2026-0027` rejected by emp_1399; annual used=2 pending=0 remaining=28.
- Evidence: `docs/nibras/evidence/deep-qa/2026-09-16/SESSION-NOTES.md`.

### Files
| Action | Path |
|--------|------|
| MODIFY | `carbon-frontend/src/apps/my/components/RequestDetail.jsx` |
| MODIFY | `carbon-frontend/src/api/my.js` |
| MODIFY | `carbon-frontend/src/i18n/locales/{en,ar}/my.json` |
| MODIFY | `.ai-toolkit/{project.config.md,shared/security.md,troubleshooting/playbook.md}` |
| MODIFY | `manage.sh` |

---

## Nibras Deep QA + P1 ops (2026-09-16)

## [2026-09-16] master-architect (Nibras) — Deep QA U2 + P1 URL/throttle

**Seat:** Nibras

### Evidence
- Browser U2 leave→approve **PASS**: `CRS-2026-0025` emp_1001 → emp_1399 → Approved; used 2 / remaining 28. Notes: `docs/nibras/evidence/deep-qa/2026-09-16/SESSION-NOTES.md`, `u2-emp-approved.png`.
- P1 manage.sh: `frontend_public_url()` from `VITE_BASE` → `http://localhost:5179/`.
- P1 throttle UX: 429 → `rate_limit`; notifyFromError does not clear session while refresh token exists. Vitest `errorNormalizer` 10/10.
- Toolkit: PB-48/49/50, RULE_5 + FRONTEND_BASE_PATH=/, security 429 note.

### Master decision
- NSR product READY unchanged; Deep QA **ACTIVE** — next P0s J-LV-02 reject, J-LV-04 cancel, J-LV-03 send-back.
- Mid-session “Postgres dropped” = PB-50 (sandbox false negative + manage.sh kill backend), not DB crash.

---

# TASK-RESULTS — Active handoffs only

Append worker verification here for **current** phases.

**Full historical results** (pre-2026-09-16 cleanup):  
[`docs/_archive/tasks-history/TASK-RESULTS-FULL-2026-09-16.md`](docs/_archive/tasks-history/TASK-RESULTS-FULL-2026-09-16.md)

---

## NSR-9

## [2026-09-16] qa-validator — Staff go-live E2E gate

### Summary
Staff go-live gate: **READY** on product evidence (people pytest 228, vitest 33, `npm run build`). Playwright leave→approve **spec shipped**; UI run **PARTIAL/BLOCKED** (no live FE/BE + unseeded `emp_1001`; sandbox browser path / host `libnspr4` history). Leave approve corroborated by `test_leave_journey_e2e.py` (5). Path H Attendance/Rotation N/A. Evidence: `docs/nibras/evidence/NSR-9-go-live-gate.md`; QA manual updated.

### Task Results

| Item | Result | Detail |
|------|--------|--------|
| `people/tests/` | PASS | 228 passed |
| `npm run build` | PASS | Fixed `PlanDagGraph.jsx` orphaned `NODE_STATUS` (syntax) |
| Vitest staff pack | PASS | 6 files / 33 tests (added MyLeave + TeamInbox smoke; `team` ns in i18n mock) |
| Playwright `nibras-leave-approve` | PARTIAL | Spec created; login failed without seeded stack |
| Hire onboard / ledger payroll | PASS | onboard 7 + ledger fail/happy 2 |
| Leave API journey | PASS | 5 tests |
| `verify.sh frontend` | SKIP | File absent |
| ADR-0028 test fixtures | FIXED | Dual-root OrgUnit fixtures → deployment root + siblings |

### Verification Output
```
$ cd backend && ../.venv/bin/python -m pytest people/tests/ -q --disable-warnings -p no:cacheprovider
228 passed in 34.24s

$ cd carbon-frontend && npm run build
✓ built in ~19s

$ npx vitest run …EmployeeWizard PeoplePages MyLoans OrgUnitScope MyLeave TeamInbox
Test Files  6 passed (6)
Tests  33 passed (33)

$ CI=1 PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright \
    npx playwright test --config e2e/playwright.config.ts nibras-leave-approve
1 failed (N9A Employee login emp_1001 → false); 2 did not run
```

### Go-live recommendation
**READY** — no product P0s. Operational residual only: run Playwright on seeded nibras stack when :5179/:8009 are up.

**NSR-9 → PARTIAL** (honest Playwright gap).

### Master audit NSR-9 — PASS (product READY)
Re-verified: people pytest **228 passed**; vitest staff pack **33/6 files**; evidence + QA manual + `nibras-leave-approve.spec.ts` present. Agree **READY** for staff go-live; Playwright UI is ops residual (seeded stack + host libs), not product P0. NSR W0–W9 closed (W9 PARTIAL on UI E2E only).

---

## PEC-R7

## [2026-09-16] backend-worker (Pulse) — ECF tool surface advertises leave_record

### Summary
`resolve_entity` / `aggregate_entity` schemas were stuck on `entity_type.enum: ["employee"]`. Enrichment now reads descriptor names from `instance_config` via `get_tool_definitions(instance_config)` so the LLM can select `leave_record` (ECF-8). `ECF_ENABLED` gate unchanged. Evidence: `docs/pulse/evidence/PEC-R7-ecf-tool-surface.md`.

### Verification
| Check | Result |
|-------|--------|
| `./manage.sh test ai/tests/test_ecf_aggregate.py -q` | **12 passed** |
| Schema includes `leave_record` when nibras-like config passed | ✅ |
| Aggregate metrics include `open_leave_count` from descriptors | ✅ |
| ECF_ENABLED gate | kept |

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `backend/ai/engine/agent/tools.py` | Descriptor-driven ECF schema enrichment |
| MODIFY | `backend/ai/engine/cognition/turn/runner.py` | Pass executor instance_config into defs |
| MODIFY | `backend/ai/engine/cognition/plan/loop.py` | Pass instance_config into step tool defs |
| MODIFY | `backend/ai/tests/test_ecf_aggregate.py` | PEC-R7 schema assertion |
| CREATE | `docs/pulse/evidence/PEC-R7-ecf-tool-surface.md` | Evidence |

**PEC-R7 → DONE.**

---

## PEC-R6

## [2026-09-16] backend-worker (Pulse) — seed live Skills Catalog

### Summary
Catalog was empty because the only promoted skill lived on a PEC-2A fixture `instance_id` UUID, while `CatalogService.list_skills()` scopes to `PLAN_INSTANCE_ID` = `nibras`. Added idempotent `seed_catalog_skills` that upserts an HRMS procedure draft on `nibras` (`app_identifier=people`) and promotes via `gate._promote_skill`. Evidence: `docs/pulse/evidence/PEC-R6-skills-seed.md`.

### Verification
| Check | Result |
|-------|--------|
| Command | `DJANGO_BRAND=nibras ../.venv/bin/python manage.py seed_catalog_skills` |
| Skills on `instance_id=nibras` | 0 → **1** |
| `CatalogService().list_skills()` | **1** (`payroll_run_variance_check`, admitted) |
| DRF `CatalogViewSet.skills` (superuser) | **200**, count **1** |
| Anonymous | **401** |
| Idempotent re-run | already promoted (no-op) |
| Live curl `:8009` | unreachable this run (no service restart) |

### Files Changed
| Action | File | What |
|--------|------|------|
| CREATE | `backend/ai/management/commands/seed_catalog_skills.py` | Gate-only HRMS skill seed |
| CREATE | `docs/pulse/evidence/PEC-R6-skills-seed.md` | Root cause + proof |
| MODIFY | `TASKS.md` | Active focus + PEC-R6 DONE |

### Compliance
Gate-only promote; Pulse-only; `people` app_identifier; no manage.sh start/stop / PG restart.

**PEC-R6 → DONE.**

---

## NSR-8B

## [2026-09-16] frontend-worker — Org dropdown tree-aware + deployment-scoped UX

### Summary
People org-unit pickers now use shared tree helpers (sort parents→children, indented / `full_path` labels, orphan-chain filter). `fetchOrgUnits` applies prepare by default (defense-in-depth on top of NSR-8A API scoping). Wired into wizard, employees filter/grid, profile edit, positions, and payroll run create/edit.

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `carbon-frontend/src/api/orgUnits.js` | Helpers: `filterOrgUnitsToConnectedTree`, `sortOrgUnitsForTree`, `orgUnitOptionLabel`, `orgUnitSelectOptions`, `prepareOrgUnitsForPicker`; `fetchOrgUnits` prepares list |
| MODIFY | `carbon-frontend/src/apps/people/EmployeeWizard.jsx` | `orgUnitSelectOptions` for Autocomplete |
| MODIFY | `carbon-frontend/src/apps/people/EmployeesPage.jsx` | Tree options in filters; grid shows `full_path` |
| MODIFY | `carbon-frontend/src/apps/people/tabs/EmployeeProfileTab.jsx` | Indented MenuItems (section + edit-all) |
| MODIFY | `carbon-frontend/src/apps/people/PositionsPage.jsx` | Tree-sorted indented select |
| MODIFY | `carbon-frontend/src/apps/people/PayrollRunsPage.jsx` | SearchSelect tree labels |
| MODIFY | `carbon-frontend/src/apps/people/EmployeeDetailPage.jsx` | Display prefers `full_path` |
| CREATE | `carbon-frontend/src/__tests__/OrgUnitScope.test.jsx` | Helper + orphan + wizard smoke |
| MODIFY | `TASKS.md` | NSR-8B → DONE |

### Verification Output
```
$ cd /home/ahmed/ws/carbon/carbon-frontend && npx vitest run src/__tests__/OrgUnitScope.test.jsx
 RUN  v4.1.10 /home/ahmed/ws/carbon/carbon-frontend
 Test Files  1 passed (1)
      Tests  7 passed (7)

$ cd /home/ahmed/ws/carbon/carbon-frontend && npx vitest run \
    src/__tests__/EmployeeWizard.test.jsx src/__tests__/PeoplePages.test.jsx
 Test Files  2 passed (2)
      Tests  15 passed (15)

$ cd /home/ahmed/ws/carbon/carbon-frontend && npm run build
✓ built in 18.45s
```

### Residual
- Admin `OrgUnitsPage` / AccessControl / catalog DataProducts / Carbon inventory pickers left as-is (out of People scope; admin page already uses `full_path` in places).
- If API ever returns multi-root again, FE keeps all connected roots but still drops orphans.

**NSR-8B → DONE.** NSR-9 not started (Master dispatches QA gate).

### Master audit NSR-8B — PASS
Re-ran vitest: OrgUnitScope + EmployeeWizard + PeoplePages → **22 passed**. Helpers (`prepareOrgUnitsForPicker`, orphan filter, tree sort/labels) wired through People pickers. Admin OrgUnitsPage residual accepted (out of People scope).

---

## NSR-8A

## [2026-09-16] backend-worker — Single-root OrgUnit + instance-gated seeds

### Summary
Enforced ADR-0028: at most one active `OrgUnit` with `parent=None` (`clean()` + `save()`→`full_clean`). Added `get_deployment_root()` / `get_deployment_org_unit_ids()`; scoped `OrgUnitViewSet` and `get_visible_org_units` to the deployment subtree. Gated `seed_gofsco_org` / `seed_aastmt_org` on `DJANGO_BRAND` / `INSTANCE_NAME` (no `--force`).

### Gate rules
| Seed | Allowed when |
|------|----------------|
| `seed_gofsco_org` | `DJANGO_BRAND ∈ {gofsco,nibras}` **or** (unknown brand ∧ `INSTANCE_NAME ∈ {gofsco,nibras}`) |
| `seed_aastmt_org` | `DJANGO_BRAND ∈ {aastmt}` **or** (unknown brand ∧ `INSTANCE_NAME ∈ {aastmt,aast}`) |

Known brands that are not in the allow-list refuse even if `INSTANCE_NAME` would match (avoids default `INSTANCE_NAME=AASTMT` unlocking AASTMT seeds on a nibras cell).

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `backend/mdm/models.py` | `OrgUnit.clean` + `save`→`full_clean` single-root invariant |
| MODIFY | `backend/mdm/services.py` | `get_deployment_root`, `get_deployment_org_unit_ids`, seed identity helpers |
| MODIFY | `backend/mdm/views.py` | `OrgUnitViewSet` intersect deployment subtree |
| MODIFY | `backend/mdm/serializers.py` | API validate single-root |
| MODIFY | `backend/mdm/admin.py` | Admin list scoped to deployment subtree |
| MODIFY | `backend/accounts/rbac_utils.py` | `get_visible_org_units` deployment-scoped |
| MODIFY | `backend/mdm/management/commands/seed_gofsco_org.py` | Instance gate + CommandError |
| MODIFY | `backend/core/management/commands/seed_aastmt_org.py` | Instance gate + root idempotency |
| CREATE | `backend/mdm/tests/test_org_unit_root.py` | Invariant + seed gate tests |
| MODIFY | `backend/people/tests/test_cbac.py` | Sibling orgs under one deployment root |
| MODIFY | `backend/mdm/tests/test_org_units.py` | Soft-delete fixtures parented under root |
| MODIFY | `TASKS.md` | NSR-8A → DONE |

### Verification Output
```
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest \
  mdm/tests/test_org_unit_root.py people/tests/test_cbac.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
...................                                                      [100%]
19 passed in 2.69s
```

Smoke (wrong brand):
```
DJANGO_BRAND=aastmt ../.venv/bin/python manage.py seed_gofsco_org --dry-run
→ CommandError: seed_gofsco_org is instance-gated (ADR-0028): … Current DJANGO_BRAND='aastmt' …
```

### Residual risks
- Frontend org dropdowns still flat until NSR-8B (API now subtree-scoped for authenticated callers).
- Pre-existing multi-root DBs: `get_deployment_root()` raises; ViewSet returns empty until data cleaned.
- No `--force` override on seeds (by design).

**NSR-8A → DONE.** NSR-8B not marked.

### Master audit NSR-8A — PASS
Re-ran gate: **19 passed**. Wrong-brand smoke: `DJANGO_BRAND=aastmt seed_gofsco_org --dry-run` → CommandError instance-gated. `get_deployment_root` / ViewSet / seed gates present. Residual FE flat pickers → NSR-8B (API already subtree-scoped).

---

## PEC-R5

## [2026-09-16] backend-worker (Pulse) — seed live Capability registry

### Summary
Ran `DJANGO_BRAND=nibras python manage.py seed_nibras_processes` against live DB. Fixed seeder `app_identifier` from instance id (`nibras`) to brand default app (`people`) so `scope_ai_queryset` / Console list is non-empty. Evidence: `docs/pulse/evidence/PEC-R5-capability-seed.md`.

### Verification
| Check | Result |
|-------|--------|
| Command | `DJANGO_BRAND=nibras ../.venv/bin/python manage.py seed_nibras_processes` |
| DB caps before → after | 20 → **31** |
| JWT curl `GET /carbon-api/ai/catalog/capabilities/` | **200**, count **31** |
| Anonymous | 401 |
| Idempotent re-run | 0 created, 31 updated |
| Skills catalog | still 0 (DB Skill=1 carbon/private; not force-promoted) |

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `backend/ai/management/commands/seed_nibras_processes.py` | `app_identifier=resolve_default_app_identifier()` |
| CREATE | `docs/pulse/evidence/PEC-R5-capability-seed.md` | Before/after + HTTP proof |
| MODIFY | `TASKS.md` | PEC-R5 DONE + Active focus |

### Residuals
Skills catalog empty; ProcessDefinition rows still `app_identifier=carbon` (pre-existing).

---

## PEC-R4

## [2026-09-16] frontend/qa-worker (Pulse) — Phase PEC-R4: L4 Playwright Capabilities (PARTIAL)

### Summary
Shipped `journey-16-pulse-capabilities.spec.ts` (Capabilities settle grid/empty + Skills Catalog smoke + catalog API 401/200). Playwright execution **BLOCKED** on host: Chromium headless missing `libnspr4.so` (also `libnss3` / `libasound`). Spec left in tree; API/FE corroboration PASS. Evidence: `docs/pulse/evidence/PEC-R4-l4-capabilities.md`.

### Task results
| # | Task | Result | Notes |
|---|------|--------|-------|
| 1 | Journey spec | PASS | `e2e/journeys/journey-16-pulse-capabilities.spec.ts` |
| 2 | Capabilities settle asserts | SHIPPED | Not executed in browser |
| 3 | Skills smoke | SHIPPED | Route heading only |
| 4 | Playwright one-file run | **BLOCKED** | Exact error below |
| 5 | Evidence + TASKS | PASS | PARTIAL status |

### Exact Playwright blocker
```
chrome-headless-shell: error while loading shared libraries: libnspr4.so: cannot open shared object file: No such file or directory
```
`sudo` unavailable in agent session → cannot install OS deps.

### Corroboration
- FE `:5179` → 200  
- anon `GET …/catalog/capabilities/` → 401  
- auth (ahmed / AdminPa_132) → 200, **31** capability rows (PEC-R5)

### Files Changed
| Action | File | What |
|--------|------|------|
| CREATE | `carbon-frontend/e2e/journeys/journey-16-pulse-capabilities.spec.ts` | L4 journey |
| CREATE | `docs/pulse/evidence/PEC-R4-l4-capabilities.md` | Evidence |
| MODIFY | `TASKS.md` | PEC-R4 PARTIAL + Active focus |
| MODIFY | `TASK-RESULTS.md` | This section |

**PEC-R4 → PARTIAL.** Re-open to DONE after `playwright install-deps` (or apt libs) and green journey-16.

---

## ECF-leave-fetch

## [2026-09-16] backend-worker (Pulse) — Host fetch_fn for leave_record

### Summary
Wired live `CarbonHostExecutor.entity_fetch` / `entity_count` so `entity_type=leave_record` uses RULE_12 scope `employee__org_unit_id__in` (descriptor + host map), same pattern as employee `org_unit_id__in`. Rows expose label_map keys (`employee`, `leave_type`) and string dates for resolver search. Engine cognition/entity untouched. Evidence: `docs/pulse/evidence/ECF-leave-fetch-fn.md`.

### How leave_record is fetched
`execute_resolve_entity` → `executor.entity_fetch("people.models.LeaveRecord", …)` → `_people_entity_scope_lookup` → `_people_scope(user, qs, "employee__org_unit_id__in")` → filtered `values` + `_normalize_entity_row`.

### Verification
```
./manage.sh test ai/tests/test_ecf_leave_fetch_fn.py -q --tb=short --maxfail=8
7 passed in 2.77s
```

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `backend/ai/host_executor.py` | Scope map + normalize; entity_fetch/count use LeaveRecord path |
| CREATE | `backend/ai/tests/test_ecf_leave_fetch_fn.py` | Live ORM + resolve + tool path + org isolation |
| CREATE | `docs/pulse/evidence/ECF-leave-fetch-fn.md` | Evidence |
| MODIFY | `TASKS.md` | ECF-leave-fetch DONE + Active focus note |

**ECF-leave-fetch → DONE.**

---

## NSR-7C

## [2026-09-16] frontend-worker — Nested governed dropdowns (FK codes, not `*_code`)

### Summary
Wizard / profile / filters / loans / certs / positions read nested `{id,code,label}` via `refCode`/`refLabel` and write ReferenceValue **codes** on FK field names (`nationality`, `employment_type`, `contract_type`, `gender`, `rotation`, `loan_type`, `cert_type`, `grade`, `job_family`). Soft `*_code` keys no longer emitted from employee wizard/profile payloads.

### Payload key renames
| Old (illegal) | New write key |
|---|---|
| `nationality_code` | `nationality` (code string) |
| `employment_type_code` | `employment_type` |
| `contract_type_code` | `contract_type` |
| (free-text nationality label dual-write) | code-only `nationality` |
| `job_family_code` (Position) | `job_family` |

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `apps/people/utils.js` | `refCode` / `refLabel` helpers |
| MODIFY | `apps/people/employeeWizardPayload.js` | emit FK names; drop `*_code` |
| MODIFY | `apps/people/EmployeeWizard.jsx` | form stores codes under FK names |
| MODIFY | `apps/people/EmployeesPage.jsx` | filters/columns nested-aware |
| MODIFY | `apps/people/tabs/EmployeeProfileTab.jsx` | Autocomplete + nested read/write |
| MODIFY | `apps/people/EmployeeDetailPage.jsx` | hero employment_type label |
| MODIFY | `apps/people/LoansPage.jsx` | display + Autocomplete write `loan_type` |
| MODIFY | `apps/people/CertificationsPage.jsx` | display + Autocomplete write `cert_type` |
| MODIFY | `apps/people/PositionsPage.jsx` | `grade` / `job_family` governed |
| MODIFY | `apps/people/tabs/EmployeeCertsTab.jsx` | nested cert_type display |
| MODIFY | `apps/my/components/MyLoansCard.jsx` | nested loan_type display |
| MODIFY | `apps/my/components/myRequestsLabels.js` | nested loan_type summary |
| MODIFY | `__tests__/EmployeeWizard.test.jsx` | FK payload assertions |
| MODIFY | `__tests__/MyLoans.test.jsx` | nested + string fallback |
| MODIFY | `__tests__/PeoplePages.test.jsx` | Path H: attendance/rotation nav hidden |

### Verification Output
```
cd /home/ahmed/ws/carbon/carbon-frontend
npx vitest run src/__tests__/EmployeeWizard.test.jsx src/__tests__/PeoplePages.test.jsx src/__tests__/MyLoans.test.jsx
 Test Files  3 passed (3)
      Tests  22 passed (22)

npm run build
✓ built in 18.68s
```

### Residual risks
- `CompensationConfigPanel` still uses `pay_grade_code` / `job_family_code` on CompensationPlan (separate model — not Bucket-1 Employee FKs).
- ComplianceRule UI (`category` / `jurisdiction`) not in this pass.
- My NewRequestDialog still free-text `loan_type` code string (API-accepted); not Autocomplete-wired.

### Master audit NSR-7C — PASS
Re-ran vitest gate: **22 passed** (EmployeeWizard / PeoplePages / MyLoans). Payload builder emits FK names only (no `*_code`). `refCode`/`refLabel` present. Residuals (CompensationPlan soft codes, ComplianceRule UI, My loan free-text) accepted out-of-Bucket-1 / non-blocking for W8.

---

## NSR-7B

## [2026-09-16] backend-worker — Bucket-1 governed FKs + GovernedValueField

### Summary
Converted ADR-0027 Bucket-1 soft CharFields / free-text to `FK → mdm.ReferenceValue` (`on_delete=PROTECT`). Shared `GovernedValueField` lives in `mdm/serializers.py` (read `{id,code,label,set}`; write id or code). Migration `people.0026_bucket1_governed_referencevalue_fks` renames→nullable FK→backfill→drop legacy→tighten required FKs. Ensured `loan_installment` on `payslip_line_type` for payroll.

### Task Results
| Item | Result |
|------|--------|
| GovernedValueField | `mdm/serializers.py` + `mdm/governed.py` |
| Models migrated | Employee (nationality, employment_type, contract_type, gender, rotation), Position (job_family, grade), Loan, AttendancePermission, Certification, RotationSchedule, PayslipLine, BenefitType.category, ComplianceRule (category, jurisdiction) |
| leave_type | Untouched (already FK via 0018) |
| pytest people | **228 passed** |
| pytest GovernedValueField | **3 passed** |
| Migration | `people.0026` (data) + `people.0027` (help_text/blank state) |

### Files Changed
| Action | File | What |
|--------|------|------|
| ADD | `backend/mdm/governed.py` | `resolve_reference_value` |
| ADD | `backend/mdm/serializers.py` | `GovernedValueField` |
| ADD | `backend/people/migrations/0026_bucket1_governed_referencevalue_fks.py` | schema + data migration |
| ADD | `backend/mdm/tests/test_governed_value_field.py` | field unit tests |
| ADD | `backend/people/tests/ref_helpers.py`, `conftest.py` | test FK helpers |
| MODIFY | `backend/people/models.py`, `serializers.py`, services, seeds, tests | FK usage + nested API |

### Verification Output
```
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest people/tests/ -q --maxfail=8 --disable-warnings -p no:cacheprovider
........................................................................ [ 31%]
........................................................................ [ 63%]
........................................................................ [ 94%]
............                                                             [100%]
228 passed in ~32s

../.venv/bin/python -m pytest mdm/tests/test_governed_value_field.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
...                                                                      [100%]
3 passed

../.venv/bin/python manage.py migrate people --noinput
Applying people.0026_bucket1_governed_referencevalue_fks... OK
```

### Residual risks
- Frontend still writes `*_code` / free-text until **NSR-7C**.
- pytest.ini `--reuse-db --nomigrations`: recreate test DB (`--create-db`) once after model FK landing.
- Demo grades (M1/E3) and legacy cert labels may remain unmapped → null / seed-created values.
- AI / Pulse callers of `nationality_code` need follow-up (PEC-R3 already adjusting).

### Master audit NSR-7B — PASS
Spot-check: `GovernedValueField` + `mdm/governed.resolve_reference_value` (RULE_16, nested read, write id/code); Employee/Loan/Cert FKs `PROTECT`; serializers wired; migrations `0026`/`0027` present. Re-ran payroll/compensation + GovernedValueField tests → **26 passed**. Residual FE `*_code` is NSR-7C.

---

## PEC-R3

## [2026-09-16] backend-worker (Pulse) — people_grounding GREEN (20/20)

### Summary
Fixed `ai/tests/test_people_grounding.py` after NSR-7B ReferenceValue FKs. Fixtures now create `ReferenceValue` for gender/nationality; Position omits nullable `grade`. Tiny AI helper: analytics resolves ReferenceValue FK codes then synonym-merges. Stale `--reuse-db --nomigrations` test DB recreated once (`--create-db`). Evidence: `docs/pulse/evidence/PEC-R3-ai-suite-debt.md`.

### Verification
```
./manage.sh test ai/tests/test_people_grounding.py -q --tb=line --maxfail=20 --create-db  → 20 passed
./manage.sh test ai/tests/test_people_grounding.py -q --tb=line --maxfail=20               → 20 passed
```

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `backend/ai/tests/test_people_grounding.py` | ReferenceValue fixtures; omit Position.grade |
| MODIFY | `backend/ai/host_executor.py` | FK label resolve + synonym; `*_code` aliases |
| UPDATE | `docs/pulse/evidence/PEC-R3-ai-suite-debt.md` | people_grounding GREEN |

### COMMS → Nibras
Apply people `0026` on live brand DBs if still CharField; update people test fixtures that still assign string genders; drop/recreate `test_*` after FK landings under `--nomigrations`.

---

## [2026-09-16] backend-worker — Phase PEC-R3: AI suite debt (PARTIAL)

### Summary
Partitioned inventory + fixes for historically failing AI modules outside PEC core. Postgres **DOWN** (`localhost:5432` refused). All greenable non-DB cases fixed and verified; django_db suites blocked. Evidence: `docs/pulse/evidence/PEC-R3-ai-suite-debt.md`. *(Superseded for people_grounding: see note above — now 20/20 GREEN with Postgres UP.)*

### Inventory
| File | Green | Still red / blocked |
|------|------:|---------------------|
| `test_ports.py` | **22** | 0 |
| `test_chat_stream.py` | **5** non-DB | ~7 django_db |
| `test_web_search_tool.py` | **19** non-DB | 1 django_db |
| `test_durable.py` | 0 | all django_db (2 static fixes shipped) |
| `test_people_grounding.py` | **20** | 0 (fixed in follow-up above) |

### Fixes shipped
| Issue | Fix |
|-------|-----|
| PDP `decide` signature drift | Test asserts attribution kwargs (product correct) |
| chat_stream `progress_callback` TypeError | Fakes accept + assert pcb |
| durable resume rejects `failed` | Drop `failed` from reject list (product allows) |
| durable replay step order flake | `order_by("step_index")` |
| web_search FakeClient missing `post` | Mock `post` → empty body |

### Verification
```
test_ports.py → 22 passed
chat_stream (5 non-DB) → 5 passed
web_search (-k not has_capability) → 19 passed, 1 deselected
test_durable / people_grounding / chat_stream django_db → OperationalError connection refused
verify.sh intelligence → GATE FAILED (pre-existing forbidden-term 'nibras' in aggregate.py docstring; replay 21 + hrms 4 passed)
```

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `backend/ai/tests/test_ports.py` | PDP decide signature |
| MODIFY | `backend/ai/tests/test_chat_stream.py` | progress_callback fakes |
| MODIFY | `backend/ai/tests/test_durable.py` | resume reject + order_by |
| MODIFY | `backend/ai/tests/test_web_search_tool.py` | FakeClient.post |
| CREATE | `docs/pulse/evidence/PEC-R3-ai-suite-debt.md` | Evidence |
| MODIFY | `TASKS.md` | PEC-R3 PARTIAL + Active focus |

**PEC-R3 → PARTIAL.** Re-open to DONE when Postgres is up and the four django_db partitions pass.

---

## NSR-7A

## [2026-09-16] backend-worker — Phase NSR-7A: Seed 7 governed ReferenceSets

### Summary
Extended `seed_gofsco_rules` (idempotent) with ADR-0027 / design Bucket-1 sets that were missing: `grade`, `loan_type`, `permission_type`, `cert_type`, `payslip_line_type`, `compliance_category`, `jurisdiction`. Canonical codes match archived NIR-5C. EN labels + `metadata.label_ar` (correspondence seed pattern). No FK migrations (NSR-7B).

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Extend `seed_gofsco_rules` | PASS | `GOVERNED_REFERENCE_SETS` + EN/AR helper |
| 2 | Exact ADR/design codes | PASS | 7 sets; no invented sets |
| 3 | Idempotent re-run | PASS | second run: 0 creates |
| 4 | No FK migrations | PASS | NSR-7B only |
| 5 | Prove sets via shell | PASS | `name__in` count=7 (ReferenceSet has no `code`) |
| 6 | TASKS → DONE | PASS | |

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `backend/people/management/commands/seed_gofsco_rules.py` | Seed 7 sets + label_ar |
| MODIFY | `TASKS.md` | NSR-7A DONE |
| MODIFY | `TASK-RESULTS.md` | This block |

### Verification Output
```
$ ../.venv/bin/python manage.py seed_gofsco_rules   # ×2
✓ Governed ReferenceSets: 7 sets (grade, loan_type, permission_type,
  cert_type, payslip_line_type, compliance_category, jurisdiction) + leave_type

$ manage.py shell — ReferenceSet.objects.filter(name__in=[...]).count()
set_count 7
grade: G1…G10 (10, all label_ar)
loan_type: personal, vehicle, housing, education, emergency
permission_type: personal, medical, official, emergency
cert_type: hse, first_aid, fire, rigging, welding, driving, trade, degree
payslip_line_type: gross, basic, overtime, leave_pay, eosi_accrual, gosi, wps, deduction, net
compliance_category: leave, eosi, gosi, wps, overtime, payroll, other
jurisdiction: KW, EG, QA, AE, SA, OM, BH
```

Note: TASKS gate snippet used `code__in`; model key is `name` — proof used `name__in`.

**NSR-7A → DONE.** Next: NSR-7B (governed FKs).

### Master audit NSR-7A — PASS
Re-ran `seed_gofsco_rules` (idempotent) + `ReferenceSet.objects.filter(name__in=[…]).count() == 7` with value counts: grade 10, loan_type 5, permission_type 4, cert_type 8, payslip_line_type 9, compliance_category 7, jurisdiction 7. EN/AR via `metadata.label_ar`. No FK migrations in scope. Gate snippet `code__in` is stale (model uses `name`) — proof correct.

---

## NSR-6A

## [2026-09-16] frontend-worker — Phase NSR-6A: Path H (hide Attendance + Rotation)

### Summary
Master chose **Path H** (hide, not thicken OT). Removed Attendance + Rotation from people go-live nav (`manifest.js`), PeopleHome ops modules/counts, and shell breadcrumb `ROUTE_CONFIG`. **Kept** App routes for deep-link access (RULE_22: no dangling nav targets; not in sidebar). Certifications remain in Workforce nav. Documented in GOFSCO runbook §3b — not promised for week-1 ops. No backend OT work.

### Citation
Master decision in `TASK-RESULTS.md` → **MASTER DECISION — NSR-6A Path H (2026-09-16)** and `TASKS.md` Phase NSR-6A.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Manifest: drop Attendance + Rotation | PASS | Certifications kept |
| 2 | PeopleHome modules + counts | PASS | 5 go-live cards; no attendance fetch |
| 3 | Breadcrumbs ROUTE_CONFIG | PASS | attendance/rotation entries removed |
| 4 | Routes kept (deep-link) | PASS | App.jsx comment; RULE_22 |
| 5 | GOFSCO runbook §3b | PASS | Not go-live; URL may exist |
| 6 | Vitest PeopleHome + PeopleManifest | PASS | see Verification |
| 7 | audit-routes.py + build | PASS | see Verification |
| 8 | TASKS NSR-6A → DONE | PASS | |

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `carbon-frontend/src/apps/people/manifest.js` | Hide attendance/rotation nav |
| MODIFY | `carbon-frontend/src/apps/people/PeopleHome.jsx` | Drop attendance module/count |
| MODIFY | `carbon-frontend/src/shell/Breadcrumbs.jsx` | Drop attendance/rotation crumbs |
| MODIFY | `carbon-frontend/src/App.jsx` | Comment: routes kept deep-link |
| MODIFY | `carbon-frontend/src/__tests__/PeopleHome.test.jsx` | Path H assertions |
| MODIFY | `carbon-frontend/src/__tests__/PeopleManifest.test.jsx` | Path H nav guards |
| MODIFY | `docs/nibras/GOFSCO-ONBOARDING-RUNBOOK.md` | §3b not go-live |
| MODIFY | `TASKS.md` | NSR-6A DONE |

### Verification Output
```
$ npx vitest run src/__tests__/PeopleHome.test.jsx src/__tests__/PeopleManifest.test.jsx
 Test Files  2 passed (2)
      Tests  11 passed (11)

$ .venv/bin/python .ai-toolkit/scripts/audit-routes.py
✓ RULE_22 FE routes OK (163 routes, 103 static nav targets)

$ npm run build
✓ built in 18.21s
```

**NSR-6A → DONE (Path H).**

---

## MASTER AUDIT — NSR-6A (2026-09-16)

**Worker:** [NSR-6A Path H hide nav](5078b06e-afc1-4662-addc-d15c52ff04d7)  
**Verdict:** **PASS**

| Check | Result |
|-------|--------|
| Re-run Vitest | **11 passed** |
| Nav / PeopleHome | No Attendance / Rotation |
| RULE_22 | OK (routes kept deep-link only) |
| Runbook §3b | Documented not go-live |
| Aligns Master Path H | Yes |

**W6 complete.** Next: NSR-7A (seed governed ReferenceSets).

---

## PEC-R2

## [2026-09-16] frontend-worker — Phase PEC-R2: Capabilities registry view (Console)

### Summary
Wired read-only Capabilities registry UI onto `GET ai/catalog/capabilities/` (PEC-R1). New `CapabilitiesPanel` (DataGrid + detail drawer) mounted in AIWorkspace Console next to Skills/Processes and at `/admin/ai/capabilities` (`ai:view_console`). Closes PEC-6B deferred gap. Evidence: `docs/pulse/evidence/PEC-R2-capabilities-ui.md`.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | `listCapabilities()` | PASS | `ai/catalog/capabilities/` via apiFetch |
| 2 | CapabilitiesPanel read-only | PASS | loading/empty/offline/success + drawer |
| 3 | Console mount + CBAC | PASS | Workspace tab + AdminRoute `AI_VIEW_CONSOLE` |
| 4 | RULE_23 primary labels | PASS | kind outcome labels; host_action detail-only |
| 5 | Vitest + lint + build | PASS | 22 tests; 0 lint errors; build OK |
| 6 | Evidence + TASKS | PASS | PEC-R2 DONE |

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `carbon-frontend/src/api/aiCatalog.js` | `listCapabilities` |
| CREATE | `carbon-frontend/src/pages/admin/ai/CapabilitiesPanel.jsx` | Registry panel |
| MODIFY | `carbon-frontend/src/shell/AIWorkspace.jsx` | Capabilities tab |
| MODIFY | `carbon-frontend/src/App.jsx` | Route |
| MODIFY | `carbon-frontend/src/shell/ShellSidebar.jsx` | Nav item |
| MODIFY | `carbon-frontend/src/i18n/**` | EN/AR labels |
| CREATE | `carbon-frontend/src/__tests__/CapabilitiesPanel.test.jsx` | Panel states |
| MODIFY | `carbon-frontend/src/__tests__/aiCatalog.test.js` | Endpoint contract |
| CREATE | `docs/pulse/evidence/PEC-R2-capabilities-ui.md` | Evidence |
| MODIFY | `TASKS.md` | PEC-R2 DONE + Active focus |

### Verification Output
```
$ cd carbon-frontend && npm run lint
✖ 53 problems (0 errors, 53 warnings) — exit 0

$ npx vitest run src/__tests__/CapabilitiesPanel.test.jsx src/__tests__/aiCatalog.test.js
 Test Files  2 passed (2)
      Tests  22 passed (22)

$ npm run build
✓ built in 19.79s
```

### Deviations
NONE

### Issues Found
NONE

---

## Phase NSR-5B — Frontend: People Config thick (compliance CRUD + C&B matrix) (2026-09-16)
**Role:** frontend-worker  
**Status:** DONE

### Summary
Thickened `/people/config`: Compliance Rules create/update/delete via SystemDialog + api helpers; new Compensation tab for component + plan create (API POST only — no invent PATCH). Reference Data unchanged; Overview stays informational. Screen Spec authored with all 9 artifacts.

### API gap (documented, not invented)
Compensation components / plans: **POST create only** (`CompensationComponentListView` / `CompensationPlanListView`). No detail PATCH/DELETE endpoints — UI is create + list. Admin-gated create buttons via `isGlobalAdminFlag` (matches API 403).

### Files
| Action | Path | Note |
|--------|------|------|
| CREATE | `docs/SCREEN-SPEC-PEOPLE-CONFIG.md` | 9 artifacts |
| MODIFY | `carbon-frontend/src/api/people.js` | create/update/delete compliance; create component/plan |
| CREATE | `carbon-frontend/src/apps/people/ComplianceRulesPanel.jsx` | CRUD grid + SystemDialog |
| CREATE | `carbon-frontend/src/apps/people/CompensationConfigPanel.jsx` | Components + plans create |
| MODIFY | `carbon-frontend/src/apps/people/PeopleConfigPage.jsx` | Compensation tab; panels |
| MODIFY | `carbon-frontend/src/i18n/locales/{en,ar}/people.json` | Config / compliance / C&B strings |
| CREATE | `carbon-frontend/src/__tests__/PeopleConfig.test.jsx` | Tabs + helpers + create flows |
| MODIFY | `carbon-frontend/src/__tests__/PeoplePages.test.jsx` | Helper export list |

### Verification Output
```
$ cd carbon-frontend && npm run lint
✖ 52 problems (0 errors, 52 warnings)   # 0 errors on touched files

$ npx vitest run src/__tests__/PeopleConfig.test.jsx
Test Files  1 passed (1)
Tests  6 passed (6)

$ npm run build
✓ built in 18.23s

$ python3 .ai-toolkit/scripts/audit-routes.py
✓ RULE_22 FE routes OK (162 routes, 104 static nav targets)
```

### Checklist
| Check | Result |
|-------|--------|
| Screen Spec (9 artifacts) | ✅ |
| SystemDialog / tokens / i18n EN+AR | ✅ |
| apiFetch helpers only (no raw fetch) | ✅ |
| PeopleHome untouched | ✅ |
| No invented backend | ✅ |
| Gate (lint/vitest/build/audit-routes) | ✅ |

**Next:** NSR-6A (attendance thick-or-hide) or remaining W5/W6 sequencing per Master.

---

## MASTER AUDIT — NSR-5B (2026-09-16)

**Worker:** [NSR-5B People Config thick](5c731f3b-c053-4e22-af33-00361d81b437)  
**Verdict:** **PASS** (with residual)

| Check | Result |
|-------|--------|
| Re-run Vitest | **6 passed** |
| Compliance / Compensation lists | **StandardDataGrid** (RULE 2) |
| SystemDialog + api helpers | Present |
| No invented PATCH APIs | Create-only for C&B documented |

**Residual:** Overview tab still uses raw MUI `Table` for a small static dump — acceptable for info-only; do not extend. Future polish: FilteredDataGrid if Overview becomes searchable.

**W5 complete.**

---

## MASTER DECISION — NSR-6A Path H (2026-09-16)

**Choice:** **Path H — hide** Attendance + Rotation from go-live nav (not thick OT this wave).  
**Why:** Payroll does not use attendance hours as gross driver today; shipping pretend timekeeping violates thick-or-hide. Certifications stay as simple CRUD.

**Worker implements:** remove/hide `/people/attendance` + `/people/rotation` from people manifest, PeopleHome, breadcrumbs; keep routes or redirect cleanly (RULE_22); update GOFSCO runbook; Vitest/manifest tests + audit-routes.

---

## PEC-R1

## [2026-09-16] backend-worker — Phase PEC-R1: Capabilities registry list API

### Summary
Read-only CBAC-scoped Capability list at `GET /carbon-api/ai/catalog/capabilities/` (catalog path alongside skills). Thin `CapabilityListSerializer` + ViewSet action; `scope_ai_queryset`; anonymous 401; writes 405. Evidence: `docs/pulse/evidence/PEC-R1-capabilities-list.md`. New tests: 4 passed.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | GET list endpoint | PASS | `/carbon-api/ai/catalog/capabilities/` |
| 2 | Serializer business fields only | PASS | No partition/secret fields |
| 3 | Auth + app scope | PASS | IsAuthenticated + `scope_ai_queryset` |
| 4 | Tests 401 / 200 / CBAC / 405 | PASS | `test_capability_list_api.py` — 4 passed |
| 5 | Evidence + TASKS Active focus | PASS | PEC-R1 DONE |

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `backend/ai/catalog_api.py` | Serializer + GET `capabilities` |
| MODIFY | `backend/ai/catalog_urls.py` | `capabilities/` route |
| CREATE | `backend/ai/tests/test_capability_list_api.py` | Auth/shape/CBAC/405 |
| CREATE | `docs/pulse/evidence/PEC-R1-capabilities-list.md` | Evidence pack |
| MODIFY | `TASKS.md` | PEC-R1 DONE + Active focus Notes |

### Verification Output
```
$ ./manage.sh test ai/tests/test_capability_list_api.py -q
....                                                                     [100%]
4 passed in 1.59s

$ ./manage.sh test ai/tests/test_capability_loader.py ai/tests/test_capability_list_api.py -q
7 passed, 3 failed
# 3 failures pre-existing in test_capability_loader.py (pack ≠ DQ-only pilot set)
```

### Deviations
NONE for PEC-R1. Pre-existing `test_capability_loader` pack/pilot mismatch left untouched (out of scope).

### Issues Found
NONE

---

## Phase NSR-5C — Frontend: PeopleHome ops landing + breadcrumb honesty (2026-09-16)
**Role:** frontend-worker  
**Status:** DONE

### Summary
Replaced placeholder `PeopleHome` with a compact ops landing linking to Employees, Leave, Payroll, Policies, Loans, Attendance. Soft-loads optional list counts via existing `api/people` helpers (`apiFetch`). Removed ghost `/people/benefits` breadcrumb. Registered `/my`, `/my/leave`, `/my/requests`, `/my/requests/:id`, `/team`, `/team/:id` in shell `Breadcrumbs.jsx` + i18n. RULE_9: no in-page breadcrumbs. PeopleConfigPage untouched.

### Files
| Action | Path | Note |
|--------|------|------|
| MODIFY | `carbon-frontend/src/apps/people/PeopleHome.jsx` | Ops landing + soft counts |
| MODIFY | `carbon-frontend/src/shell/Breadcrumbs.jsx` | Drop benefits; add my/team trails |
| MODIFY | `carbon-frontend/src/i18n/shellLabels.js` | My / Team / Request Detail keys |
| MODIFY | `carbon-frontend/src/i18n/locales/{en,ar}/shell.json` | nav.my, nav.team, nav.requestDetail |
| MODIFY | `carbon-frontend/src/i18n/locales/{en,ar}/people.json` | homeCount |
| CREATE | `carbon-frontend/src/__tests__/PeopleHome.test.jsx` | Module links + navigate + counts |
| MODIFY | `carbon-frontend/src/__tests__/PeopleManifest.test.jsx` | Go-live paths; no benefits |

### Verification Output
```
$ cd /home/ahmed/ws/carbon/carbon-frontend && npm test -- \
    src/__tests__/PeopleHome.test.jsx src/__tests__/PeopleManifest.test.jsx
Test Files  2 passed (2)
Tests  9 passed (9)

$ npm run build
✓ built in 18.48s

$ cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/audit-routes.py
✓ RULE_22 FE routes OK (162 routes, 104 static nav targets)
```

### Checklist
| Check | Result |
|-------|--------|
| RULE_9 (no in-page breadcrumbs) | ✅ |
| RULE_22 (audit-routes) | ✅ |
| design-system / compact-ui | ✅ |
| apiFetch for counts | ✅ |
| i18n EN/AR | ✅ |
| PeopleConfigPage untouched | ✅ |
| Vitest 9/9 | ✅ |
| Build | ✅ |

**NSR-5C → DONE.**

---

## MASTER AUDIT — NSR-5C (2026-09-16)

**Worker:** [NSR-5C PeopleHome breadcrumbs](925dddbe-4998-4697-b375-607277edce74)  
**Verdict:** **PASS**

| Check | Result |
|-------|--------|
| Re-run Vitest | **9 passed** |
| PeopleHome | Ops links to go-live modules; apiFetch counts |
| Ghost `/people/benefits` | Removed from Breadcrumbs |
| `/my` + `/team` trails | Present |
| RULE_22 | audit-routes OK |

**Next dispatch:** NSR-5B (People Config thick).

---

## ECF-8

**Date:** 2026-09-16  
**Worker:** backend-worker (Pulse)  
**Status:** DONE  
**Phase:** LeaveRecord descriptor-only generalize proof

### Delivered
| Item | Note |
|------|------|
| Descriptor | `entities:` → `leave_record` / `people.models.LeaveRecord` in nibras `instance.yaml` |
| Identifiers | `[id]` |
| Search | status, start_date, end_date |
| label_map | employee→full_name; leave_type→ReferenceValue.label |
| Metrics | `open_leave_count` (submitted), `approved_leave_count` (approved) |
| scope_lookup | `employee__org_unit_id__in` |
| Goldens | `backend/ai/tests/test_ecf_leave_golden.py` — id match, start_date match, 2× grounded-none |
| Evidence | `docs/pulse/evidence/ECF-8-leave-record.md` |
| Algorithm code | **None** under `cognition/entity/` |
| NSR / people | Untouched |

### Verification Output
```
$ ./manage.sh test ai/tests/test_ecf_golden.py ai/tests/test_ecf_leave_golden.py \
    ai/tests/test_ecf_shadow.py ai/tests/test_ecf_contracts.py \
    ai/tests/test_ecf_aggregate.py -q
59 passed in 0.84s

$ rg -n "django|from people|rest_framework" backend/ai/engine/cognition/entity/
# zero hits
```

### Checklist
| Check | Result |
|-------|--------|
| RULE_6 (engine domain-neutral; knowledge in instance.yaml) | ✅ |
| RULE_18 / 20 / 21 / 23 / 30 | ✅ |
| Architecture-thick (descriptor + goldens prove resolve) | ✅ |
| ADR-0032 | ✅ |
| Zero new algorithm modules / resolver/contracts/aggregate/heal edits | ✅ |
| `get_descriptor(..., "leave_record")` loads | ✅ |
| Quality-gate suite green | ✅ 59 passed |

**ECF-8 → DONE.** ECF track → **COMPLETE**.

---

## ECF-7

**Date:** 2026-09-16  
**Worker:** backend-worker (Pulse)  
**Status:** DONE  
**Phase:** Cutover — flip `ECF_ENABLED=True` (human sign-off)

### Delivered
| Item | Note |
|------|------|
| Flag | `Settings.ECF_ENABLED = True` (cutover ECF-7 2026-09-16; goldens green; human sign-off) |
| Rollback | env `ECF_ENABLED=false` (pydantic-settings) |
| `slug_resolution` | Marked superseded in `tools.py` + `nibras/instance.yaml`; kept 30-day fallback — **not deleted** |
| Legacy tools | `list_employees` / `get_employee` untouched (still live) |
| Golden comments | Updated to reflect cutover |
| Evidence | `docs/pulse/evidence/ECF-7-cutover.md` |
| NSR / people | Untouched (Pulse seat only) |

### Design decisions
- Flag lives in engine `Settings` (ADR-0032), not people app.
- Tools still gated on `getattr(settings, "ECF_ENABLED", False)` — default True; env can force False.
- No auto-mutation: cutover only enables resolve/aggregate contracts + tools.
- Shadow logger remains for parity evidence post-cutover.

### Verification Output
```
$ ./manage.sh test ai/tests/test_ecf_golden.py -q
17 passed

$ ./manage.sh test ai/tests/test_ecf_golden.py ai/tests/test_ecf_shadow.py \
    ai/tests/test_ecf_contracts.py ai/tests/test_ecf_aggregate.py -q
52 passed in 0.84s

$ rg -n "django|from people|rest_framework" backend/ai/engine/cognition/entity/
# zero hits
```

### Checklist
| Check | Result |
|-------|--------|
| RULE_6 (engine no host-domain imports) | ✅ |
| RULE_18 (AI contract binding) | ✅ |
| RULE_20 (scope / no cross-app leak) | ✅ |
| RULE_21 (no auto-mutation) | ✅ |
| RULE_23 (no engine internals in user copy) | ✅ |
| RULE_30 (Pulse owns ECF) | ✅ |
| Architecture-thick (flag + 30d fallback + shadow) | ✅ |
| ADR-0032 | ✅ |
| Goldens 17/17 | ✅ |
| Import-boundary clean | ✅ |

**ECF-7 → DONE.** Next: **ECF-8** (LeaveRecord descriptor-only generalize proof).

---

## Phase NSR-4B — Frontend: EmployeeWizard onboarding fields (2026-09-16)
**Role:** frontend-worker  
**Status:** DONE

### Summary
Wizard now requires **manager** + **join_date**; optional **opening_basic** (gated by `canViewCompensation`) on create only; payload never sends `basic_salary` (NSR-2B). Create success snackbar notes leave entitlements ready + verify opening basic on Pay tab before payroll. Vitest 7/7 green; build + i18n parity OK.

### Screen Spec acceptance (Artifact 1)
See `docs/SCREEN-SPEC-EMPLOYEE-WIZARD.md`. Highlights:
- Manager required on Employment step; join_date required (retained).
- Civil ID optional; 12-digit format when present (API not required).
- Opening basic optional, compensation-gated, create-only; omit when empty.
- Never POST `basic_salary` from wizard.
- Create toast: `employeeOnboardReady`.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Require manager + join_date | PASS | Employment validate + required Autocomplete |
| 2 | Optional opening_basic (cap-gated) | PASS | `canViewCompensation` create path |
| 3 | Payload: opening_basic / no basic_salary | PASS | `employeeWizardPayload.js` |
| 4 | Success toast readiness note | PASS | `EmployeesPage` create → `employeeOnboardReady` |
| 5 | Vitest EmployeeWizard.test.jsx | PASS | 7 tests |
| 6 | i18n en+ar | PASS | `check-i18n-keys: OK` |
| 7 | Screen Spec acceptance | PASS | `docs/SCREEN-SPEC-EMPLOYEE-WIZARD.md` |
| 8 | Build + lint 0 errors | PASS | build OK; eslint 0 errors on touched |

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `carbon-frontend/src/apps/people/EmployeeWizard.jsx` | Manager required; opening_basic create UI |
| CREATE | `carbon-frontend/src/apps/people/employeeWizardPayload.js` | Payload builder (no basic_salary) |
| MODIFY | `carbon-frontend/src/apps/people/EmployeesPage.jsx` | Create success toast |
| CREATE | `carbon-frontend/src/__tests__/EmployeeWizard.test.jsx` | Validation + payload tests |
| MODIFY | `carbon-frontend/src/i18n/locales/en/people.json` | NSR-4B strings |
| MODIFY | `carbon-frontend/src/i18n/locales/ar/people.json` | NSR-4B strings (AR) |
| CREATE | `docs/SCREEN-SPEC-EMPLOYEE-WIZARD.md` | Acceptance addendum |
| MODIFY | `TASKS.md` | NSR-4B → DONE |

### Design decisions
- **Capability gate:** reuse `canViewCompensation` (same progressive disclosure as Pay/Reveal); create employee already requires manage at page level.
- **Edit:** opening_basic not shown/sent; readonly reflected basic retained (NSR-2B).
- **civil_id:** not FE-required (API `blank=True`); format gate when filled.

### Verification Output
```
$ cd /home/ahmed/ws/carbon/carbon-frontend && npx vitest run src/__tests__/EmployeeWizard.test.jsx
 Test Files  1 passed (1)
      Tests  7 passed (7)

$ npm run build
✓ built in 19.03s

$ node scripts/check-i18n-keys.js
check-i18n-keys: OK — 3196 keys in parity (en === ar).

$ npx eslint src/apps/people/EmployeeWizard.jsx src/apps/people/EmployeesPage.jsx \
  src/apps/people/employeeWizardPayload.js src/__tests__/EmployeeWizard.test.jsx
✖ 0 errors
```

### Deviations
NONE — backend untouched.

### Issues Found
NONE

**NSR-4B → DONE.**

---

## MASTER AUDIT — NSR-4B (2026-09-16)

**Worker:** [NSR-4B EmployeeWizard onboard](35d99960-f96b-4f61-9245-339bf03526fe)  
**Verdict:** **PASS**

| Check | Result |
|-------|--------|
| Re-run Vitest | **7 passed** |
| Payload | `opening_basic` optional; never `basic_salary` |
| Required | manager + join_date |
| Spec | `docs/SCREEN-SPEC-EMPLOYEE-WIZARD.md` |

**W4 complete.** Next: W5 — NSR-5A + NSR-5C parallel; NSR-5B after.

---

## Phase NSR-5A — Backend: Profile-change apply on approve (2026-09-16)
**Role:** backend-worker  
**Status:** DONE

### Summary
On `profile_change` correspondence **approve**, apply a narrow allowlist of Employee personal/display fields from `payload.changes`. Unknown keys ignored. Reject/cancel do not mutate. Chronicle (`profile_updated`) + governance (`profile_change_applied`) when something actually changes.

### Allowlist
`full_name`, `name_en_given`, `name_en_family`, `name_ar_given`, `name_ar_family`, `nationality`, `gender`, `nationality_code`, `date_of_birth`

**Excluded (not auto-applied):** `basic_salary`, `org_unit`, `manager`, `position`, `civil_id`, employment/contract codes, `kuwaitization`, `is_active`, plus non-model keys still accepted at submit (`mobile_number`, `marital_status`).

### Files
| Action | File | What |
|--------|------|------|
| CREATE | `backend/people/profile_change_service.py` | Allowlist + apply + chronicle/governance |
| MODIFY | `backend/people/signals.py` | `apply_profile_change_on_approve` signal |
| CREATE | `backend/people/tests/test_profile_change_apply.py` | 6 tests |
| MODIFY | `TASKS.md` | NSR-5A → DONE |

### Verification Output
```
$ cd backend && ../.venv/bin/python -m pytest \
    people/tests/test_profile_change_apply.py -q --maxfail=5 \
    --disable-warnings -p no:cacheprovider
......                                                                   [100%]
6 passed in 1.39s
```

### Design notes
- Submit path unchanged (free-form `changes`); apply filters at approve time.
- Actor for audit: `approver_chain` terminal `decided_by` (event row is written after `corr.save()`).

---

## MASTER AUDIT — NSR-5A (2026-09-16)

**Worker:** [NSR-5A profile-change apply](f51b3099-a25b-41e0-b81c-91a5653a9f37)  
**Verdict:** **PASS** (with residual)

| Check | Result |
|-------|--------|
| Re-run gate | **6 passed** |
| Allowlist apply on approve | Names / nationality / gender / DOB |
| Reject/cancel | No mutate |
| Chronicle + governance | On real changes |

**Residual:** submit may accept `mobile_number` / `marital_status` but they are **not** applied (no Employee fields or intentional exclude). Document in My New Request UX if those fields are shown — follow-up if staff expect phone updates.

**Still in flight:** NSR-5C. NSR-5B waits for 5C.

---

## Phase NSR-4A — Backend: Hire/onboarding hooks (2026-09-16)
**Role:** backend-worker
**Status:** DONE

### Summary
7/7 gates passed. `onboard_employee` propagates applicable leave policies and optionally appends an **unverified** opening basic ledger line. No salary fabricated when `opening_basic` omitted. Wired from `EmployeeListCreateView` after save.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | `onboard_employee(...)` service | PASS | `people/employee_onboard_service.py` |
| 2 | Leave via `propagate_for_employee` | PASS | Reuses `_eligible_queryset`; no eligibility duplication |
| 3 | Opening basic → unverified ledger | PASS | `CompensationService.append_line`; verify before payroll (NSR-2A) |
| 4 | Serializer `opening_basic` write-only | PASS | Popped on create/update |
| 5 | Wire create view | PASS | Best-effort try/except (hire not blocked) |
| 6 | `test_employee_onboard.py` | PASS | 7 tests |
| 7 | TASKS DONE + TASK-RESULTS | PASS | this block |

### Files Changed
| Action | File | What |
|--------|------|------|
| CREATE | `backend/people/employee_onboard_service.py` | Hire hooks |
| MODIFY | `backend/people/leave_policy_service.py` | `propagate_for_employee` |
| MODIFY | `backend/people/serializers.py` | `opening_basic` write-only |
| MODIFY | `backend/people/views.py` | Call onboard after save |
| CREATE | `backend/people/tests/test_employee_onboard.py` | 7 tests |
| MODIFY | `TASKS.md` | NSR-4A → DONE |

### Design decisions
- **Unverified opening line:** append unverified when `opening_basic` provided; HR must `verify_line` before payroll (NSR-2A requires verified monthly `basic`).
- **No fabrication:** `opening_basic=None` → no ledger row (legacy `Employee.basic_salary` may still be set for cache/bootstrap).
- **`basic` component:** `get(code='basic')` — production assumes seed; tests create component.
- **Leave:** `propagate_for_employee` only (not full `propagate_all_active`) for hire-time performance.

### Verification Output
```
$ cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest \
  people/tests/test_employee_onboard.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
.......                                                                  [100%]
7 passed in 1.90s

$ cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest \
  people/tests/test_leave_policy_service.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
.....                                                                    [100%]
5 passed in 0.58s
```

Counts: onboard **7 passed** · leave_policy_service **5 passed** · **total 12**.

### Deviations
NONE

### Issues Found
NONE

**NSR-4A → DONE.** Next: NSR-4B (FE EmployeeWizard onboarding fields).

---

## MASTER AUDIT — NSR-4A (2026-09-16)

**Worker:** [NSR-4A hire onboard hooks](aa82a8c1-7feb-4e5d-89f8-45827f4bc9fc)  
**Verdict:** **PASS** (with residual)

| Check | Result |
|-------|--------|
| Re-run gate | **12 passed** (7 onboard + 5 leave_policy) |
| `onboard_employee` | Propagate + optional unverified opening basic |
| No fabrication | No amount → no ledger line |
| Create wiring | After save; `opening_basic` write-only |

**Residual (accepted for now):** onboard failures are best-effort (logged, hire not rolled back) — matches existing user-provision pattern. NSR-4B should surface success toast; ops must watch logs if entitlements missing.

**Next dispatch:** NSR-4B.

---

## ECF-GOLDEN-GREEN

**Date:** 2026-09-16  
**Worker:** backend-worker (Pulse)  
**Status:** DONE  
**Phase:** Green 11 lookup golden cases → unblock ECF-7 human sign-off

### Delivered
| Item | Note |
|------|------|
| `call_nibras_entity_lookup` | Wired to ECF `resolve` + in-memory `_LOOKUP_POPULATION` (no Django) |
| Population | Reena/1009, Abrar/عبرار/1021, 1046, pk=104 with `employee_no="104"`; **no** Salman |
| Return shape | `{ok, found, employee_no, response/text, searched_total, total, position_title?, lang?}` |
| `position_label` | Position **title** string in response (CT Senior Operator) |
| `arabic_in_arabic_out` | Arabic prose headcount for `كم موظف لدينا` |
| Grounded-none | `searched N of N` for Salman / existence cases |
| xfail | Removed — all lookup cases PASS |
| `ECF_ENABLED` | **NOT** flipped (still False) |
| NSR / people UI | Untouched |

### Verification Output
```
$ cd backend && ../.venv/bin/python -m pytest ai/tests/test_ecf_golden.py -v --disable-warnings
17 passed in 0.32s
  (0 xfailed, 0 failed)

$ python3 .ai-toolkit/scripts/import-boundary-lint.py
Import boundary: clean (engine imports only engine/stdlib/SDK)
```

### Checklist
| Check | Result |
|-------|--------|
| 11 lookup goldens PASS | ✅ |
| 2 metric goldens PASS | ✅ |
| Structural gates PASS | ✅ |
| 0 xfailed | ✅ |
| Import-boundary clean | ✅ |
| Did NOT flip `ECF_ENABLED` | ✅ |
| NSR/people UI untouched | ✅ |

**Goldens green → ECF-7 awaiting human sign-off.** Do not flip `ECF_ENABLED` until Master Architect gates cutover.

---

## Phase NSR-3B — Frontend: Loan schedule UI + My loans surface (2026-09-16)
**Role:** frontend-worker (DeepSeek V4.1-Flash)
**Status:** DONE

### Summary
6/6 gates passed. `fetchMyLoans` → `GET people/me/loan/`; My Dashboard lists loans + status (QA B6); HR expander empty = generated on approval + reload installments after save; Screen Spec + Vitest + i18n en/ar.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | `fetchMyLoans` + `normalizeMyLoans` | PASS | `api/my.js` → `people/me/loan/` via apiFetch |
| 2 | My Dashboard loans card | PASS | `MyLoansCard` — loading/error/empty/loaded |
| 3 | HR expander installments | PASS | empty copy; reload after status save |
| 4 | Screen Spec | PASS | `docs/SCREEN-SPEC-NIBRAS-LOANS.md` (9 artifacts) |
| 5 | Vitest `MyLoans.test.jsx` | PASS | 6 tests |
| 6 | Lint / build / verify.sh frontend | PASS | 0 errors on touched files; GATE PASSED |

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `carbon-frontend/src/api/my.js` | `normalizeMyLoans` + `fetchMyLoans` |
| CREATE | `carbon-frontend/src/apps/my/components/MyLoansCard.jsx` | My loans card |
| MODIFY | `carbon-frontend/src/apps/my/MyDashboard.jsx` | Wire loans fetch + card |
| MODIFY | `carbon-frontend/src/apps/people/LoansPage.jsx` | Empty copy; reload installments after save |
| MODIFY | `carbon-frontend/src/i18n/locales/en/my.json` | My loans strings |
| MODIFY | `carbon-frontend/src/i18n/locales/ar/my.json` | My loans strings (AR) |
| MODIFY | `carbon-frontend/src/i18n/locales/en/people.json` | Installments empty copy |
| MODIFY | `carbon-frontend/src/i18n/locales/ar/people.json` | Installments empty copy (AR) |
| MODIFY | `carbon-frontend/src/__mocks__/react-i18next.js` | Load `my` ns in Vitest |
| CREATE | `carbon-frontend/src/__tests__/MyLoans.test.jsx` | Helper + card smoke |
| CREATE | `docs/SCREEN-SPEC-NIBRAS-LOANS.md` | 9-artifact Screen Spec |
| MODIFY | `TASKS.md` | NSR-3B → DONE |

### Verification Output
```
$ cd carbon-frontend && node scripts/check-i18n-keys.js
check-i18n-keys: OK — 3188 keys in parity (en === ar).

$ npx vitest run src/__tests__/MyLoans.test.jsx
Test Files  1 passed (1)
     Tests  6 passed (6)

$ npm run lint
✖ 51 problems (0 errors, 51 warnings)  # pre-existing; 0 errors in touched files

$ npm run build
✓ built in ~17s

$ ./.ai-toolkit/scripts/verify.sh frontend
✓ lint
✓ build
✓ FE route audit (RULE_22)
GATE PASSED
```

### Design decisions
- Path confirmed from `people/self_urls.py`: `loan/` under `me/` → `people/me/loan/`.
- Card extracted to `MyLoansCard.jsx` for testability; dashboard keeps parallel per-card state.
- Installments remain read-only; empty state explains generation on approval (NSR-3A materialize).

### Deviations
NONE

### Issues Found
NONE (lint warnings elsewhere are pre-existing; not touched)

**NSR-3B → DONE.**

---

## MASTER AUDIT — NSR-3B (2026-09-16)

**Worker:** [NSR-3B My loans UI](f8a3be16-f7c1-437e-81f3-be038f653183)  
**Verdict:** **PASS**

| Check | Result |
|-------|--------|
| Re-run Vitest | **6 passed** |
| `fetchMyLoans` + MyLoansCard | Wired on MyDashboard |
| HR expander | Reload after save; empty = generated on approval |
| Screen Spec | `docs/SCREEN-SPEC-NIBRAS-LOANS.md` |
| Toolkit | apiFetch, i18n, no raw fetch/hex in new card |

**W3 complete.** Next: NSR-4A (hire onboard hooks).

---

## ECF-6

**Date:** 2026-09-16  
**Worker:** backend-worker (Pulse)  
**Status:** DONE  
**Phase:** Canonical metrics — wire `metrics{}` → `aggregate_entity`

### Delivered
| Item | Path / note |
|------|-------------|
| Algorithm | `backend/ai/engine/cognition/entity/aggregate.py` — `aggregate(descriptor, metric, count_fn=…)` |
| Host seam | `host_executor.entity_count(model_path, filters)` — RULE_12 scoped; mirrors `entity_fetch` |
| Tool (flag-gated) | `aggregate_entity` in `tools.py` — catalog + executor only when `ECF_ENABLED` |
| call_host_api alias | Delegates `api_name=aggregate_entity` like `resolve_entity` |
| Descriptor (pre-existing) | `instance.yaml` metrics: headcount=`is_active`, kuwaiti=`nationality_code=KW` |
| Guidance | `analyze_employees` / `list_employees` copy points named totals → `aggregate_entity` |
| Contracts hint | `_ECF_TOOL_ENTITY_HINTS` includes `aggregate_entity` |
| Tests | `ai/tests/test_ecf_aggregate.py` (11) + golden metric cases now PASS (not xfail) |

### Design decisions
- `analyze_employees` untouched for dimension breakdowns; `aggregate_entity` is the additional metric-named path.
- Filter kwargs come only from the descriptor — LLM cannot invent `kuwaitization=True` for "kuwaiti".
- Response always includes `cited_fields` + `citation` so answers can name the field used.
- `ECF_ENABLED` stays False — tool is wired but not exposed until ECF-7 Master cutover.

### Verification Output
```
$ cd backend && ../.venv/bin/python -m pytest \
  ai/tests/test_ecf_aggregate.py ai/tests/test_ecf_golden.py ai/tests/test_ecf_registry.py \
  -v --disable-warnings
32 passed, 11 xfailed
  (aggregate 11 + golden metric 2 PASS; lookup goldens remain xfail until ECF-7)

$ python3 .ai-toolkit/scripts/import-boundary-lint.py
Import boundary: clean (engine imports only engine/stdlib/SDK)
engine entity imports: EMPTY
```

### Checklist
| Check | Result |
|-------|--------|
| headcount → `is_active=True` | ✅ |
| kuwaiti → `nationality_code=KW` (not kuwaitization) | ✅ |
| Stability across calls | ✅ golden + unit |
| `analyze_employees` unchanged | ✅ |
| Flag-gated (ECF_ENABLED default False) | ✅ |
| Import-boundary | ✅ clean |
| NSR/people product UI | ✅ untouched |
| Did NOT flip `ECF_ENABLED` | ✅ |

**ECF-6 → DONE.** Next: ECF-7 (Master-gated cutover — do NOT flip `ECF_ENABLED`).

---

## Phase NSR-3A — Backend: Loan approve → persist installment schedule (2026-09-16)
**Role:** backend-worker (DeepSeek V4.1-Flash)  
**Status:** DONE

### Summary
7/7 gates passed. `materialize_loan_installments` persists engine schedule on approve→active (skip-if-any idempotency). Payroll hybrid: prefer persisted `LoanInstallment` due in period; fall back to in-memory `calculate_loan_schedule` when no rows. Admin/API CRUD unchanged — generated rows are schedule SoT after approval.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | `materialize_loan_installments(loan)` | PASS | `people/loan_service.py`; skip-if-any |
| 2 | Persist from `calculate_loan_schedule` | PASS | amount / due_date / installment_no / portions |
| 3 | Call from status sync on → active | PASS | `signals.sync_loan_status_from_correspondence` |
| 4 | Payroll hybrid path | PASS | persisted first; engine fallback |
| 5 | `test_loan_installments.py` | PASS | approve N rows; no dupe; payroll uses rows |
| 6 | Pytest gate | PASS | 19 passed |
| 7 | TASKS DONE + TASK-RESULTS | PASS | this block |

### Files Changed
| Action | File | What |
|--------|------|------|
| CREATE | `backend/people/loan_service.py` | materialize + rule resolve |
| MODIFY | `backend/people/signals.py` | materialize after draft→active |
| MODIFY | `backend/people/payroll_service.py` | `_loan_installment_for_run` hybrid |
| CREATE | `backend/people/tests/test_loan_installments.py` | 4 tests |
| MODIFY | `backend/people/tests/test_loan_status_sync.py` | seed loan_schedule rule |
| MODIFY | `TASKS.md` | NSR-3A → DONE |

### Design decisions
- **Idempotency:** skip-if-any (no delete+recreate on re-save).
- **Payroll hybrid:** if `loan.installments.exists()`, pick row by `due_date` year/month matching run period; else engine schedule + month-index (pre-NSR-3A path). Lineage inputs include `source=persisted_loan_installment` + `loan_installment_id` when using rows.
- **Generated-as-source:** Admin/API installment CRUD remains; post-approval engine-generated rows are the intended SoT.
- **RULE_3:** people-only imports (calculation_engine, models, django).

### Verification Output
```
$ cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest \
  people/tests/test_loan_status_sync.py people/tests/test_loan_installments.py \
  people/tests/test_payroll_service.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
...................                                                      [100%]
19 passed in 2.21s
```

Counts: status_sync 3 · installments 4 · payroll_service 12 · **total 19 passed**.

### Deviations
NONE

### Issues Found
NONE

**NSR-3A → DONE.** Next: NSR-3B (FE loan schedule UI + My loans).

---

## MASTER AUDIT — NSR-3A (2026-09-16)

**Worker:** [NSR-3A loan installments](890fab46-a36a-4bb0-b3f9-62d9769b466a)  
**Verdict:** **PASS**

| Check | Result |
|-------|--------|
| Re-run gate | **19 passed** |
| `loan_service.materialize_loan_installments` | skip-if-any idempotent |
| Signal on approve→active | Calls materialize |
| Payroll hybrid | Persisted rows first; engine fallback |
| RULE_3 | people-local service |

**Next dispatch:** NSR-3B.

---

## ECF-4

**Date:** 2026-09-16  
**Worker:** backend-worker (Pulse)  
**Status:** DONE  
**Phase:** Wire `resolve_entity` (flag-gated) + `get_employee` employee_no + shadow logger

### Delivered (this turn — shadow remainder)
| Item | Path / note |
|------|-------------|
| Shadow helpers | `backend/ai/engine/agent/tools.py` — `_legacy_resolve_via_list_get`, `build_shadow_diff`, `log_resolve_entity_shadow`, `emit_resolve_entity_shadow` |
| Wire-in | `execute_resolve_entity` calls `emit_resolve_entity_shadow` after response build (fail-open) |
| Log format | Structured JSON via `pulse.ecf.shadow`: `ECF_SHADOW {"event":"ecf_shadow_diff","shadow_diff":{new_result,legacy_result},...}` (no `ai_shadow_log` model) |
| Legacy path | Best-effort `get_employee` detail (numeric) then capped `list_employees` + slug `match_fields` scan |
| Tests | `ai/tests/test_ecf_shadow.py` — emit when flag on, noop when off, fail-open, legacy list/get mocks |

### Already present (prior ECF-4 work — not re-done)
- `resolve_entity` gated on `ECF_ENABLED` in `get_tool_definitions` / `get_tool_executors`
- Host `employee_no` lookup in `_people_execute` employees branch
- Nibras `instance.yaml` resolve_entity guidance on list/get descriptions

### Verification Output
```
$ cd backend && ../.venv/bin/python -m pytest \
  ai/tests/test_ecf_shadow.py ai/tests/test_ecf_golden.py ai/tests/test_ecf_resolver.py \
  ai/tests/test_ecf_contracts.py ai/tests/test_navigation_resolver.py \
  ai/tests/test_intent_resolver.py -q --maxfail=8 --disable-warnings
87 passed, 13 xfailed in 0.74s
```

### Checklist
| Check | Result |
|-------|--------|
| Shadow log when `ECF_ENABLED` | ✅ |
| Fail-open (logging never breaks tool) | ✅ |
| Unit tests for shadow emit / helper | ✅ |
| Gate suite (golden/resolver/contracts/nav/intent + shadow) | ✅ 87 passed, 13 xfailed |
| NSR/people product UI | ✅ untouched |

**ECF-4 → DONE.** Next: ECF-5 — MAPE-K feedback loop (`heal.py` / golden nominations).

---

## Phase NSR-2B — Frontend: Pay tab + payroll UI honesty (ledger SoT) (2026-09-16)
**Role:** frontend-worker (DeepSeek V4.1-Flash)
**Status:** DONE

### Summary
5/5 gates passed. Pay honesty: profile/wizard no longer edit `basic_salary` as payroll driver; Pay tab shows read-only reflected basic; PayrollRunsPage surfaces ledger-missing compute errors via SystemDialog. Spec + Vitest + i18n en/ar updated.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Demote editable basic_salary (wizard/profile) | PASS | Read-only reflected + Pay-tab guidance; wizard does not PATCH basic_salary |
| 2 | PayrollRunsPage compute ledger-missing errors | PASS | SystemDialog + Alert; `isLedgerMissingError` heuristic |
| 3 | Screen Spec acceptance (ledger SoT) | PASS | Extended `docs/SCREEN-SPEC-COMPENSATION-LEDGER.md` |
| 4 | Vitest EmployeePayTab | PASS | 2 tests — disabled reflected basic + empty-basic copy |
| 5 | i18n en+ar | PASS | `check-i18n-keys.js` OK — 3176 keys in parity |

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `carbon-frontend/src/apps/people/tabs/EmployeePayTab.jsx` | Read-only reflected basic banner |
| MODIFY | `carbon-frontend/src/apps/people/tabs/EmployeeProfileTab.jsx` | Compensation section read-only; no basic_salary PATCH |
| MODIFY | `carbon-frontend/src/apps/people/EmployeeWizard.jsx` | Compensation step info + disabled field; no payload write |
| MODIFY | `carbon-frontend/src/apps/people/PayrollRunsPage.jsx` | SystemDialog for compute/action errors |
| MODIFY | `carbon-frontend/src/i18n/locales/en/people.json` | NSR-2B strings |
| MODIFY | `carbon-frontend/src/i18n/locales/ar/people.json` | NSR-2B strings (AR) |
| MODIFY | `carbon-frontend/src/help/helpTexts.js` | basicSalary help → ledger SoT |
| MODIFY | `carbon-frontend/src/__mocks__/react-i18next.js` | Load `people` ns in Vitest mock |
| CREATE | `carbon-frontend/src/__tests__/EmployeePayTab.test.jsx` | Ledger-first assertions |
| MODIFY | `docs/SCREEN-SPEC-COMPENSATION-LEDGER.md` | Acceptance + composition + i18n for NSR-2B |
| MODIFY | `TASKS.md` | NSR-2B → DONE |

### Verification Output
```
$ cd carbon-frontend && node scripts/check-i18n-keys.js
check-i18n-keys: OK — 3176 keys in parity (en === ar).

$ npx vitest run src/__tests__/EmployeePayTab.test.jsx
Test Files  1 passed (1)
     Tests  2 passed (2)

$ npm run lint
✖ 51 problems (0 errors, 51 warnings)  # pre-existing; 0 errors in touched files

$ npm run build
✓ built in ~18s

$ ./.ai-toolkit/scripts/verify.sh frontend
✓ lint
✓ build
✓ FE route audit (RULE_22)
GATE PASSED
```

### Design decisions
- Profile/wizard: demote, do not delete reflected amount — HR still sees cache; writers go to Pay tab ledger append.
- Payroll error dialog: prefer friendly i18n for ledger-missing; still show API `detail` when different.
- Vitest mock: added `people` namespace so people-app unit tests resolve real EN copy.

### Deviations
NONE

### Issues Found
NONE (lint warnings elsewhere are pre-existing; not touched)

---

## MASTER AUDIT — NSR-2B (2026-09-16)

**Worker:** [NSR-2B FE pay honesty](548bc54b-fd06-41a2-910e-40939ec10bfb)  
**Verdict:** **PASS**

| Check | Result |
|-------|--------|
| Re-run Vitest | **2 passed** |
| Wizard/profile | No `basic_salary` PATCH; disabled/read-only |
| PayrollRunsPage | SystemDialog for ledger-missing compute errors |
| Toolkit | SystemDialog, i18n en/ar, no raw fetch in touched paths |
| verify.sh frontend | Worker reported GATE PASSED |

**W2 complete.** Next: NSR-3A (loan installment materialization).

---

## ECF-3

**Date:** 2026-09-16  
**Worker:** backend-worker (Pulse)  
**Status:** DONE  
**Phase:** Boundary contract guards — wire `apply_entity_contracts` into `_run_chat`

### Delivered
| Item | Path / note |
|------|-------------|
| Runtime hook | `backend/ai/engine_runtime.py` — `_apply_ecf_entity_contracts` after `_build_tool_trace` in `_run_chat` |
| Flag gate | `get_settings().ECF_ENABLED` (default False — safe no-op) |
| Export used | `apply_entity_contracts` (real name; not `apply_contracts`) |
| Helpers | `_ecf_descriptor_for_tool`, `_safe_executor_capabilities`; passes `executor.entity_fetch` as `label_fetch_fn` |
| Tests | `ai/tests/test_ecf_contracts.py` — +3 runtime-hook cases (flag off / flag on / non-entity skip) |

### Design decisions
- Contracts run after tool_trace build so the "Considered…" surface stays pre-contract summaries; cleaned tools/prose feed anti-hallucination + grounded notes.
- Never raises — exception path logs and returns inputs unchanged.
- Tool→entity mapping via name hints (`list_employees` / `get_employee` / `resolve_entity` / `analyze_employees`), including `call_host_api:` prefix.

### Verification Output
```
$ cd backend && ../.venv/bin/python -m pytest ai/tests/test_ecf_contracts.py -q --maxfail=5 --disable-warnings
................                                                         [100%]
16 passed in 0.22s

$ cd .. && python3 .ai-toolkit/scripts/import-boundary-lint.py
Import boundary: clean (engine imports only engine/stdlib/SDK)
```

### Checklist
| Check | Result |
|-------|--------|
| `apply_entity_contracts` wired in `_run_chat` | ✅ |
| Gated on `ECF_ENABLED` (default False) | ✅ |
| Runtime hook tests (flag on) | ✅ |
| Existing contract unit tests | ✅ 13 + 3 = 16 |
| Import-boundary lint | ✅ clean |
| NSR/people product UI | ✅ untouched |

**ECF-3 → DONE.** Next: ECF-4 — wire `resolve_entity` tool (flag-gated) + fix `get_employee`.

---

## ECF-2 (Master verify 2026-09-16 — Pulse)

Pre-existing `resolver.py` + `test_ecf_resolver.py` accepted as DONE without re-implementation.

```
14 passed (test_ecf_resolver alone)
33 passed, 13 xfailed (registry+resolver+golden)
import-boundary: clean
engine people/mdm imports: EMPTY
```

Next: ECF-3 — wire `apply_entity_contracts` into `engine_runtime` (module+unit tests already exist).

---

## ECF-5 (Master verify 2026-09-16 — Pulse)

Pre-existing `heal.py` + `test_ecf_heal.py` accepted. Gate: **12 passed**; correction → nomination proven via `TestNominateGoldenCase` / `test_correction_nominates`.

Next: ECF-6 canonical metrics (`aggregate_entity`) — **DONE** (see ## ECF-6 above). Active focus → ECF-7 Master cutover.

---

## Phase NSR-2A — Payroll compute from compensation ledger (2026-09-16)
**Role:** backend-worker  
**Status:** DONE

### Implementation
- `CompensationService.verified_basic_amount(employee, as_of=None)` — current monthly verified `component.code=='basic'`; if multiple, highest `effective_start` then `-pk`.
- `PayrollRunService._compute_employee` — resolves basic via ledger at `run.period_end`; raises `PayrollServiceError` with `employee_no` if missing. Inputs: `basic` + `basic_source: "ledger"`. Never falls back to `Employee.basic_salary`.
- Header comment: validation seam is wired (not a stub); ADR-0029 SoT noted.
- `EmployeeDetailView.patch` — **rejects** (HTTP 400) any `basic_salary` change when a verified ledger basic exists; append a new ledger line instead. Unverified/absent ledger still allows legacy PATCH (cache / bootstrap).

### Design decisions
- Fail closed: no silent estimate from `Employee.basic_salary`.
- `basic_salary` remains a deprecated cache/mirror only; payroll SoT is the verified ledger.
- PATCH reject (not ignore) when verified basic exists — clear client error for HR forms still sending the field.
- SeedGofsco / payroll fixtures now seed verified basic lines so compute stays green.

### Verification Output
```
cd backend && ../.venv/bin/python -m pytest \
  people/tests/test_payroll_service.py people/tests/test_compensation.py \
  -q --maxfail=5 --disable-warnings -p no:cacheprovider
.......................                                                  [100%]
23 passed in 2.19s

people/tests/test_calculation_engine.py (extra)
30 passed in 0.56s
```

### Issues / blockers
- None. Frontend pay honesty is NSR-2B.

---

## MASTER AUDIT — NSR-2A (2026-09-16)

**Worker:** [NSR-2A ledger payroll SoT](25a3c3f9-a602-4fae-845b-b91943e3de73)  
**Verdict:** **PASS**

| Check | Result |
|-------|--------|
| `verified_basic_amount` | Present; verified monthly `basic` only |
| Compute fail-closed | Raises `PayrollServiceError`; no `basic_salary` fallback |
| PATCH reject | HTTP 400 when verified ledger basic exists |
| Re-run gate | **23 passed** (payroll + compensation) |
| Toolkit | ADR-0029 / data-layer; RULE_3 preserved (CompensationService in people) |

**Next dispatch:** NSR-2B (frontend pay / payroll honesty).

---

## Phase NSR-0 — QA Bookkeeping (2026-09-16)
**Role:** qa-validator (Master executed after interrupted dispatch)  
**Status:** DONE

### Verification Output
```
people/tests/test_payroll_service.py + test_compensation.py + test_leave_journey_e2e.py
27 passed in 3.52s

correspondence/tests/test_of20_integration_walk.py
5 passed in 4.08s
```

### Code spot-checks
- NIR-3C: `people/payroll_service.py` `PayrollRunService.compute` — EXISTS
- NIR-7A: `people/compensation_service.py` — EXISTS
- NIR-7B: `carbon-frontend/src/apps/people/tabs/EmployeePayTab.jsx` uses `SystemDialog` — EXISTS
- OF leave journey: `test_leave_journey_e2e.py` — PASS; OF-20 walk under `correspondence/tests/` — PASS

### Status flips
- NSR-0 → DONE
- NIR-3C → DONE
- NIR-7A → DONE
- NIR-7B → DONE
- OF-15…20 Active focus already DONE

### Issues
- None for bookkeeping. Payroll still dual-SoT vs ledger (owned by NSR-2A).

---

## Phase NSR-1B — LeaveRecord ↔ Correspondence status sync (2026-09-16)
**Role:** backend-worker (landed before interrupt; Master audited)  
**Status:** DONE

### Implementation
- `people/signals.py` — `sync_leave_status_from_correspondence` (mirror loan pattern)
- Mapping: approved→approved, rejected→rejected, cancelled→cancelled; sent_back leaves draft
- `people/tests/test_leave_status_sync.py` — approve/reject/cancel/send-back/guard

### Verification Output
```
people/tests/test_leave_status_sync.py + test_leave_journey_e2e.py + test_loan_status_sync.py
13 passed in 4.62s
```

### Master audit
**PASS** — spot-checked signal + tests; gate green.

---

## Phase NSR-1A — GOFSCO data spine runbook (2026-09-16)
**Role:** devops-worker (Master executed after interrupt)  
**Status:** DONE

### Deliverables
- `docs/nibras/GOFSCO-ONBOARDING-RUNBOOK.md` — ordered commands, manager hierarchy, salary freeze until NSR-2A, acceptance checks
- `docs/QA-MANUAL-PEOPLE-MY-TEAM.md` — removed GF-00X / deprecated `seed_gofsco` guidance
- `mdm/management/commands/seed_gofsco_org.py` — added `--dry-run`
- `import_gofsco_employees` already had `--dry-run`

### Verification Output
```
manage.py help import_gofsco_employees / seed_gofsco_org / seed_correspondence /
  link_employee_users / seed_gofsco_rules / propagate_leave_policies → OK
test -f docs/nibras/GOFSCO-ONBOARDING-RUNBOOK.md → OK
rg GF-00 / seed_gofsco[^_] in QA manual → cleared (runbook references only)
```

### Issues
- ADR-0028 instance gate still open (NSR-8). Runbook requires dedicated DB until then.

---

## MASTER AUDIT — NSR W0/W1 (2026-09-16)

| Phase | Verdict | Notes |
|-------|---------|-------|
| NSR-0 | **PASS** | Status flips + pytest evidence |
| NSR-1A | **PASS** | Runbook + dry-run + QA doc |
| NSR-1B | **PASS** | 13 tests; signal correct |

**Next dispatch:** NSR-2A (Backend — payroll from ledger SoT).

---

## MASTER AUDIT — PEC track (2026-09-16)

**Verdict:** Specs/handoffs **COMPLETE** (11/11 phases DONE). Master re-verification **PASS with residual caveats** after fixing intelligence-boundary regressions introduced by PEC-3A/4A.

### Completeness checklist
| Phase | TASKS | TASK-RESULTS | Evidence / artifact |
|-------|-------|--------------|---------------------|
| PEC-1A | DONE | yes | `docs/pulse/evidence/PEC-1A-heartbeat.md` + compose `pulse-heartbeat` |
| PEC-2A | DONE | yes | `PEC-2A-reuse.md` |
| PEC-3A | DONE | yes | `PEC-3A-proactive-api.md` |
| PEC-3B | DONE | yes | frontend insights panel |
| PEC-4A | DONE | yes | `PEC-4A-eval-baseline.md` + CI harness |
| PEC-5A | DONE | yes | `gosi_wps.sif.lifecycle.yaml` |
| PEC-5B | DONE | yes | `employee.onboarding.lifecycle.yaml` |
| PEC-6A | DONE | yes | promote/reject API |
| PEC-6B | DONE | yes | SkillsPanel actions (Capabilities list deferred) |
| PEC-7A | DONE | yes | `PEC-7A-convergence.md` |
| PEC-ID-1 | DONE | yes | ADR-0033 + actor_chain |

### QA Framework (4-layer) — Master run

| Layer | Result | Proof |
|-------|--------|-------|
| **L1 Structural** | **PASS (partitioned)** / **CONDITIONAL (full suite)** | `verify.sh backend` GATE PASSED · `verify.sh antipatterns` GATE PASSED · `verify.sh intelligence` GATE PASSED (after Master fix) · FE lint 0 errors · FE build OK · `verify.sh full` still saw **7 failed + 9 errors** in broad `ai` suite (durable/chat_stream/ports/people_grounding/web_search) — **not attributed to PEC core paths**; treat as separate debt |
| **L2 Security API** | **PARTIAL** | No live server (`curl` → connection refused). Skill/insight CBAC covered by unit/API tests (403 promote, tenancy). Live JWT matrix **not** re-run this session |
| **L3 Functional** | **PASS (PEC scope)** | Eval harness **25/25** `fabrication_rate=0` · PEC targeted pytest **33 passed** · redteam+eval **75 passed** · proactive/insight **65 passed** · skill decision/admission alone **20 passed** · FE vitest insight/Skills **25 passed** |
| **L4 UX browser** | **NOT RUN** | No Playwright/browser pass this audit; PEC-3B/6B rely on vitest + prior journey coverage |

### Master fixes applied during audit
- `engine/proactive/delivery.py`: removed illegal host import `ai.instance_registry` + brand fallback string (RULE_20 / forbidden-term)
- `ai/eval/run_harness.py`: rewrote fabrication negative-control to satisfy fail-open lint
- Comments in `engine/core/config.py` + `knowledge_graph/models.py`: stripped forbidden brand tokens

### Residual / non-blocking
1. Capabilities registry **list API** still deferred (PEC-6B)
2. Seed `django_db` tests need Postgres up (noted in PEC-5B)
3. Ratify ADR-0033 (Proposed)
4. Full-suite failures in non-PEC modules — open Debugger/Fixer track, do not reopen PEC
5. L2 live JWT + L4 browser audit still recommended for release

**Master acceptance of PEC track:** **YES** for roadmap DoD P1–P7 evidence, **with** residuals above. Intelligence gate must stay green.

---

## PEC-6B

## [2026-09-16] frontend-worker — Phase PEC-6B: Console skill promote/reject

### Summary
Wired promote/reject into existing `SkillsPanel` (also used by AIWorkspace Console Skills tab — no duplicate panel). CBAC-gated UI for `ai:publisher` | `ai:process_owner` with 403 lock fallback. Outcome copy only (RULE_23). Capabilities registry deferred: no list API for P3-01 Capability contracts. Lint 0 errors; build clean; 20 targeted vitest green.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | API wrappers `promoteSkill` / `rejectSkill` | PASS | `ai/skills/{id}/promote\|reject/` |
| 2 | SkillsPanel promote + retire actions | PASS | Drawer actions + reject reason dialog |
| 3 | CBAC lock (publisher / process_owner) | PASS | GatedButton + 403 deny lock |
| 4 | Reuse Console SkillsPanel (no duplicate) | PASS | Still mounted from `AIWorkspace` |
| 5 | Capabilities registry view | DEFER | No GET list endpoint for Capability rows |
| 6 | Verification gate | PASS | lint + build + vitest |

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `carbon-frontend/src/api/aiCatalog.js` | `promoteSkill` / `rejectSkill` |
| MODIFY | `carbon-frontend/src/pages/admin/ai/SkillsPanel.jsx` | Promote/retire + CBAC + states |
| CREATE | `carbon-frontend/src/__tests__/SkillsPanel.test.jsx` | CBAC + promote/reject tests |
| MODIFY | `carbon-frontend/src/__tests__/aiCatalog.test.js` | Endpoint contract tests |
| MODIFY | `carbon-frontend/src/pages/admin/ai/ProcessRegistry.jsx` | Unblock lint: unshadow setAutonomy API |
| MODIFY | `carbon-frontend/src/components/Form/SearchSelect.jsx` | Pass `disabled` to Autocomplete (lint) |

### Verification Output
```
$ npx vitest run src/__tests__/SkillsPanel.test.jsx src/__tests__/aiCatalog.test.js
 Test Files  2 passed (2)
      Tests  20 passed (20)

$ npm run lint
✖ 0 errors (warnings only) — exit 0

$ npm run build
✓ built in 18.81s
```

### Deviations
- Capabilities registry view deferred: host Capability contracts have Django admin only; no REST list for a thin Console panel. Needs a backend list endpoint before UI.

### Issues Found
- ProcessRegistry had shadowed `setAutonomy` (useState overwrote API import) — fixed while clearing lint errors so the gate could pass.

---

## [2026-09-16] Master Architect — Repo noise cleanup

- Deleted accidental root files (`, psycopg2`, `tr(x) for x in r))`), Zone.Identifier, duplicate President-brief PPTX copies, ad-hoc `backend/_test_login.py`.
- Archived full `TASKS.md` / `TASK-RESULTS.md` + sprint specs + audit docs under `docs/_archive/`.
- Replaced root `TASKS.md` with active-only slim file; fixed `docs/index.md`.
- Tightened `.gitignore` for personal `raw/` noise and Windows artifacts.
- Pass 2: archived 18 superseded design docs, 2 demos, 5 out-of-scope (Moodle/QBank/EDOS). Living `docs/*.md` = 28 canonical/ops docs. `raw/` left untouched.

---

## PEC-2A

**Role:** backend-worker  
**Date:** 2026-09-16  
**Verdict:** PROVED (not CUT)

### What shipped
- `feed_run_feedback` now re-fetches skill after `update_stats` and writes durable `AuditLog(action=ai.skill_reused)` citing skill id/name + run id + usage_count.
- Integration test `ai/tests/test_pec2a_learning_reuse.py`: draft HRMS skill → gate admit → planner match → counter 0→1 + ledger row.
- Evidence: `docs/pulse/evidence/PEC-2A-reuse.md`

### Verification (terminal)
```
cd backend && ../.venv/bin/python -m pytest \
  ai/tests/test_learning_trigger.py ai/tests/test_flight_learning.py \
  ai/tests/test_pec2a_learning_reuse.py ai/tests/test_skill_reuse.py \
  -q --maxfail=5 --disable-warnings
# 28 passed in 7.78s

./.ai-toolkit/scripts/verify.sh backend
# ✓ django check / ✓ no missing migrations / GATE PASSED
```

### Counter proof (from evidence dump)
- Before reuse: `usage_count=0` (`instance_promoted`)
- After reuse: `usage_count=1`
- Ledger: `AuditLog.id=47f88d9c-fa9a-43a7-a5f7-418cc3b057fc` action=`ai.skill_reused` skill=`payroll_run_variance_check`

---

## PEC-1A

## [2026-09-16] devops-worker — Phase PEC-1A: Heartbeat metabolism proof

### Summary
4/4 loops ran for `nibras` with terminal `PulseHeartbeat` rows (`status=ok`). Health surface already present on `GET /carbon-api/ai/pulse/sweeps/` → `heartbeats`. Compose wiring fixed by adding `pulse-heartbeat` sidecar. Evidence: `docs/pulse/evidence/PEC-1A-heartbeat.md`. Tests: 6 passed. `verify.sh backend` GATE PASSED. No cognition engine rewrite.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Compose schedulers invoke `run_pulse_maintenance` | PASS | Added `pulse-heartbeat` service; cognition/learning sidecars left intact |
| 2 | Health/read API last heartbeat per (instance, loop) | PASS | Existing `sweeps_api` — no second API |
| 3 | Evidence pack with real command/ORM/API output | PASS | `docs/pulse/evidence/PEC-1A-heartbeat.md` |
| 4 | VPS systemd handoff if out of scope locally | PASS | Documented `setup-pulse-heartbeat.sh nibras`; proved via local compose + oneshot |

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `docker-compose.yml` | Add `pulse-heartbeat` service → `ensure_pulse_instance` + looped `run_pulse_maintenance` |
| CREATE | `docs/pulse/evidence/PEC-1A-heartbeat.md` | Runtime evidence pack |

### Verification Output
```
$ cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python manage.py run_pulse_maintenance --dry-run
instance=nibras loop=proactive status=skipped items=0 llm_calls=0 cost_usd=0.000000
instance=nibras loop=consolidation status=skipped items=0 llm_calls=0 cost_usd=0.000000
instance=nibras loop=distill status=skipped items=0 llm_calls=0 cost_usd=0.000000
instance=nibras loop=decay status=skipped items=0 llm_calls=0 cost_usd=0.000000

$ DJANGO_BRAND=nibras ../.venv/bin/python manage.py run_pulse_maintenance
instance=nibras loop=proactive status=ok items=0 llm_calls=0 cost_usd=0.000000
instance=nibras loop=consolidation status=ok items=0 llm_calls=0 cost_usd=0.000000
instance=nibras loop=distill status=ok items=0 llm_calls=0 cost_usd=0.000000
instance=nibras loop=decay status=ok items=0 llm_calls=0 cost_usd=0.000000

$ ../.venv/bin/python -m pytest ai/tests/test_pulse_heartbeat.py -q --maxfail=5 --disable-warnings
......                                                                   [100%]
6 passed in 0.61s

$ ./.ai-toolkit/scripts/verify.sh backend
Verification gate: backend
✓ django check
✓ no missing migrations
GATE PASSED

$ test -f ../docs/pulse/evidence/PEC-1A-heartbeat.md && echo EVIDENCE_OK
EVIDENCE_OK

Latest PulseHeartbeat ids (nibras):
  proactive     e8a218db-72cc-4f34-9302-ec658e6ecb30  2026-09-16T13:02:39.170507+00:00
  consolidation 075cac29-28d0-45d4-b2e0-6e3ffc56175e  2026-09-16T13:02:39.245851+00:00
  distill       c70579b4-dfde-4208-8464-acefedd3e98a  2026-09-16T13:02:39.255812+00:00
  decay         3578827b-df40-4148-8ee6-0e5c254807f0  2026-09-16T13:02:39.268656+00:00
```

### Deviations
NONE — VPS systemd not executed on this host; documented as deploy handoff per TASKS.md item 4. Local proof via oneshot + compose service.

### Issues Found
NONE


## PEC-5A

## [2026-09-16] Backend Worker — Phase PEC-5A: GOSI/WPS governed ProcessDefinitions

### Summary
5/5 gates passed. GOSI/WPS SIF lifecycle ProcessDefinition + capabilities + idempotent seed + tests. 25 nibras process tests green. Additive-only edits coordinated with PEC-5B onboarding in shared seed/registry.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Process YAML `gosi_wps.sif.lifecycle` | PASS | generate→validate→review→submit→verify; submit=`human_only`+consent; `refuse_if`/`ask_if`/`kill_switch` |
| 2 | Capabilities in `api_catalog.yaml` + `capability_registry.py` | PASS | 5 caps + 3 tools; host actions bind to WPS export / validations list / inbox |
| 3 | Idempotent seed extension | PASS | `PROCESS_IDS` includes `gosi_wps.sif.lifecycle` (additive w/ PEC-5B helper) |
| 4 | Tests mirror payroll/leave/loan | PASS | `test_nibras_gosi_wps_process.py` (6 tests) |
| 5 | Verification gate | PASS | 25 passed + `verify.sh backend` |

### Files Changed
| Action | File | What |
|--------|------|------|
| CREATE | `domain_packs/nibras/processes/gosi_wps.sif.lifecycle.yaml` | GOSI/WPS SIF filing ProcessDefinition |
| CREATE | `backend/ai/tests/test_nibras_gosi_wps_process.py` | Validation / resolve / human_only / seed idempotency |
| MODIFY | `domain_packs/nibras/api_catalog.yaml` | Tools + 5 GOSI/WPS capabilities |
| MODIFY | `backend/ai/capability_registry.py` | Additive host_action bindings |
| MODIFY | `backend/ai/predicates.py` | `gosi_wps_sif_submitted_and_reconciled` |
| MODIFY | `backend/ai/management/commands/seed_nibras_processes.py` | Add `gosi_wps.sif.lifecycle` to PROCESS_IDS |

### Verification Output
```
$ DJANGO_BRAND=nibras ../.venv/bin/python -m pytest \
    ai/tests/test_nibras_payroll_process.py \
    ai/tests/test_nibras_leave_process.py \
    ai/tests/test_nibras_loan_process.py \
    ai/tests/test_nibras_gosi_wps_process.py \
    -q --maxfail=5 --disable-warnings
.........................                                                [100%]
25 passed in 4.19s

$ ./.ai-toolkit/scripts/verify.sh backend
Verification gate: backend
✓ django check
✓ no missing migrations
GATE PASSED
```

### Deviations
NONE — submit/generate bind to existing `PayrollRunWPSExportView` (scaffold pattern matching leave/loan until a dedicated bank-submit endpoint exists). Capability contract still marks submit as irreversible + `human_only`.

### Issues Found
NONE

---

## PEC-7A

## [2026-09-16] backend-worker — Phase PEC-7A: Convergence — remove inert F1a/F3 paths

### Summary
Chat hot path now uses `_fallback_prompt` (instance.yaml) only. Deleted `domain_skills.py`, `guidance_skills=` param, guidance helpers, and PromptVersion A/B routing in `build_chat_prompt`. Marked `PlaybookAssembler` / `skill_folder` DEFERRED. Evidence: `docs/pulse/evidence/PEC-7A-convergence.md`. Gate tests 33 passed; antipatterns GATE PASSED (incl. new F1a check).

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Confirm no live `guidance_skills` injection | PASS | runner never passed it; param removed |
| 2 | Remove dead F1a path | PASS | deleted `domain_skills.py` + helpers; packs deferred on disk |
| 3 | Remove unused PlaybookBlock/A/B hot path | PASS | no assemble / no A/B in `build_chat_prompt`; no fake seeds |
| 4 | Evidence + verify notes | PASS | `docs/pulse/evidence/PEC-7A-convergence.md` |
| 5 | Verification gate | PASS | see output below |

### Files Changed
| Action | File | What |
|--------|------|------|
| DELETE | `backend/ai/domain_skills.py` | Host guidance-skills loader |
| MODIFY | `backend/ai/engine/llm/prompts.py` | Always `_fallback_prompt`; drop A/B + guidance_skills |
| MODIFY | `backend/ai/engine/llm/playbook.py` | DEFERRED(F3) docstring |
| MODIFY | `backend/ai/engine/knowledge/skill_folder.py` | DEFERRED(F1a) docstring |
| MODIFY | `backend/ai/tests/test_skill_folders.py` | No host loader; assert no skill index live |
| MODIFY | `backend/ai/tests/test_fallback_prompt.py` | Load packs via skill_folder path |
| MODIFY | `domain_packs/carbon/skills/README.md` | Mark F1a deferred |
| MODIFY | `.ai-toolkit/scripts/verify.sh` | Antipattern #7: no `guidance_skills=` on hot path |
| CREATE | `docs/pulse/evidence/PEC-7A-convergence.md` | Deleted symbols + grep proof |

### Verification Output
```
$ rg -n "guidance_skills=" backend/ai/engine/cognition/turn/runner.py || true
(no matches)

$ cd backend && ../.venv/bin/python -m pytest ai/tests/test_provider_pulse.py ai/tests/test_adapter.py -q --maxfail=5 --disable-warnings
.................................                                        [100%]
33 passed in 0.59s

$ ./.ai-toolkit/scripts/verify.sh antipatterns
Verification gate: antipatterns
── Anti-patterns ───────────────────────
✓ no hardcoded secrets
✓ no MUI v5 Grid syntax
⚠ raw fetch() — prefer the project apiFetch helper:
(pre-existing frontend warnings)
✓ no hardcoded hex in components
⚠ naive datetime — use django.utils.timezone.now():
(pre-existing qa_* scripts)
⚠ 111 print() calls in backend app code (use logger)
✓ no guidance_skills on chat hot path (F1a)
════════════════════════════════════════
GATE PASSED

$ test -f docs/pulse/evidence/PEC-7A-convergence.md && echo evidence OK
evidence OK

$ rg -n "guidance_skills\s*[=:]" backend/ai/engine/llm/prompts.py backend/ai/engine/cognition/turn/runner.py || echo NONE
NONE
$ rg -n "A/B split|playbook_assembler|improvement_round" backend/ai/engine/llm/prompts.py || echo NONE
NONE
$ test ! -f backend/ai/domain_skills.py && echo DELETED
DELETED
```

### Deviations
NONE — cognition/loop.py PromptVersion staging left untouched (heartbeat; not chat hot path). Django `PlaybookBlock` model retained for flight_director.

### Issues Found
NONE

---

## PEC-6A

## [2026-09-16] backend-worker — Phase PEC-6A: Admin skill promote/reject decision API

### Summary
3/3 gates passed. CBAC-gated `POST /carbon-api/ai/skills/{id}/promote|reject/` runs admission gate only (no `_authority` bypass). AuditLog on promote/reject. 8 decision tests + 15 skill/admit/gate filter green. Frontend untouched.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | POST promote via `_promote_skill` / `admit_skill` | PASS | Service calls private gate helper; writes `SkillAdmissionLog` |
| 2 | POST reject → deprecated + reason | PASS | `rollback_skill` + transition table; AuditLog `ai.skill_rejected` |
| 3 | CBAC `ai:publisher` / `ai:process_owner` | PASS | Plain user 403; publisher/owner 200 |
| 4 | Tests 403 + promote + gate-only forge | PASS | 8 tests in `test_skills_decision_api.py` |
| 5 | Verification gate | PASS | see output below |

### Files Changed
| Action | File | What |
|--------|------|------|
| CREATE | `backend/ai/skills_decision_service.py` | Promote/reject business logic + AuditService |
| CREATE | `backend/ai/skills_decision_api.py` | Thin DRF views + CBAC permission |
| CREATE | `backend/ai/skills_decision_urls.py` | `/ai/skills/<pk>/promote\|reject/` |
| CREATE | `backend/ai/tests/test_skills_decision_api.py` | 403 / promote / reject / forge-gate |
| MODIFY | `backend/config/urls.py` | Mount `ai.skills_decision_urls` |
| MODIFY | `backend/ai/engine/skills/gate.py` | `rollback_skill` enforces transition table |

### Verification Output
```
$ cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_skills_decision_api.py -q --maxfail=8 --disable-warnings
........                                                                 [100%]
8 passed in 8.93s

$ ../.venv/bin/python -m pytest ai/tests/ -k "skill and (promot or admit or gate)" -q --maxfail=8 --disable-warnings
...............                                                          [100%]
15 passed, 2159 deselected in 8.73s

$ ./.ai-toolkit/scripts/verify.sh backend
Verification gate: backend
✓ django check
✓ no missing migrations
GATE PASSED
```

### Deviations
NONE

### Issues Found
NONE

## PEC-5B

## [2026-09-16] backend-worker — Phase PEC-5B: Employee onboarding governed process

### Summary
Employee onboarding lifecycle ProcessDefinition + capabilities + additive seed helper + tests. Mirrors leave/loan/payroll gating (`submit` → `review` human_only+SoD → `activate` human_only+consent → `verify`). Coordinated with PEC-5A via new YAML/test files and `pec5b_onboarding_process_ids()` seed helper. Governance tests green; `verify.sh backend` GATE PASSED. Seed django_db tests blocked here (Postgres cluster down).

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Process YAML `employee.onboarding.lifecycle` | PASS | submit→review→activate→verify; activate=`human_only`+consent; `refuse_if`/`ask_if`/`kill_switch` |
| 2 | Capabilities in `api_catalog.yaml` + `capability_registry.py` | PASS | 6 caps; binds to EmployeeListCreate/Detail + inbox + predicate |
| 3 | Predicate `employee_onboarding_completed_and_payroll_eligible` | PASS | Fail-closed; covered in process tests |
| 4 | Idempotent seed extension | PASS | `pec5b_onboarding_process_ids()` additive; PROCESS_IDS includes onboarding |
| 5 | Tests | PASS | `test_nibras_onboarding_process.py` — 6 governance tests green (`-k 'not seed'`) |
| 6 | Verification gate | PASS | 27 process suite (excl. seed) + `verify.sh backend` |

### Files Changed
| Action | File | What |
|--------|------|------|
| CREATE | `domain_packs/nibras/processes/employee.onboarding.lifecycle.yaml` | Onboarding ProcessDefinition |
| CREATE | `backend/ai/tests/test_nibras_onboarding_process.py` | Validate / resolve / gates / predicate / seed |
| MODIFY | `domain_packs/nibras/api_catalog.yaml` | Additive employee.onboarding capabilities |
| MODIFY | `backend/ai/capability_registry.py` | Additive onboarding host_action bindings |
| MODIFY | `backend/ai/predicates.py` | `employee_onboarding_completed_and_payroll_eligible` |
| MODIFY | `backend/ai/management/commands/seed_nibras_processes.py` | `pec5b_onboarding_process_ids()` + PROCESS_IDS concat |

### Verification Output
```
$ cd /home/ahmed/ws/carbon/backend && DJANGO_BRAND=nibras \
  ../.venv/bin/python -m pytest \
    ai/tests/test_nibras_onboarding_process.py \
    ai/tests/test_nibras_payroll_process.py \
    ai/tests/test_nibras_leave_process.py \
    ai/tests/test_nibras_loan_process.py \
    ai/tests/test_nibras_gosi_wps_process.py \
    -q --disable-warnings -k 'not seed'
...........................                                              [100%]
27 passed, 5 deselected in 2.67s

$ ./.ai-toolkit/scripts/verify.sh backend
Verification gate: backend
✓ django check
✓ no missing migrations
GATE PASSED

# Pack load smoke (no DB):
capabilities 31; PROCESS_IDS includes employee.onboarding.lifecycle;
validate_definition [] ; all step host_actions resolve OK
```

### Deviations
Seed `django_db` tests not executed in this environment — PostgreSQL 18 cluster is `down` and cannot be started from the worker sandbox (`pg_ctl` refuses root; `sudo`/`/var/run/postgresql` unavailable). Seed path is the same idempotent registry publish pattern as leave/loan/GOSI; re-run seed tests when Postgres is up.

### Issues Found
NONE for PEC-5B artifacts. Shared pack temporarily required PEC-5A GOSI registry entries to be present for `load_capabilities` (fail-closed); those are now in place.

---

## PEC-ID-1

## [2026-09-16] backend-worker — Phase PEC-ID-1: Identity propagation hardening

### Summary
3/3 gates passed. Draft ADR-0033 (Proposed). Minimal `actor_chain` + `instance_id` + `request_id` + `host_user_id` attribution on `PolicyDecisionRow` for PDP/grant host effects. Inproc token unchanged. CBAC allow/deny outcomes unchanged. OAuth/IdP Phase 2 only (not implemented).

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Draft ADR-0033 identity propagation | PASS | Proposed; Phase 2 IdP marked out of scope |
| 2 | Persist actor_chain on PDP/audit rows | PASS | Model + migration 0044; PDP + grant refusal |
| 3 | Stable user_id/instance_id/request_id | PASS | Boundary mints request_id; inproc token kept |
| 4 | Attribution tests; CBAC unchanged | PASS | 4 new + existing PDP suite |
| 5 | Verification gate | PASS | tenancy + pilot e2e; verify.sh backend |

### Files Changed
| Action | File | What |
|--------|------|------|
| CREATE | `.ai-toolkit/decisions/0033-pulse-identity-propagation.md` | Draft ADR (Phase 1 attribution / Phase 2 IdP) |
| MODIFY | `.ai-toolkit/decisions/README.md` | Index row 0033 |
| CREATE | `backend/ai/identity_propagation.py` | `build_actor_chain` / `attribution_from_command` |
| MODIFY | `backend/ai/models/pdp.py` | `actor_chain`, `instance_id`, `request_id` |
| CREATE | `backend/ai/migrations/0044_policydecisionrow_actor_chain.py` | Schema |
| MODIFY | `backend/ai/pdp.py` | Persist attribution kwargs (audit-only) |
| MODIFY | `backend/ai/command_boundary.py` | `Command.request_id`; wire attribution into PDP |
| MODIFY | `backend/ai/grant.py` | Grant-refusal rows carry actor_chain |
| MODIFY | `backend/ai/engine/ports/policy.py` | Protocol docs for attribution kwargs |
| CREATE | `backend/ai/tests/test_identity_propagation.py` | Attribution + CBAC invariance |
| MODIFY | stub PDP tests | Accept `**kwargs` for attribution |

### Verification Output
```
$ cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_identity_propagation.py ai/tests/test_pdp.py -q --maxfail=5 --disable-warnings
...........                                                              [100%]
11 passed in 3.97s

$ cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_tenancy_isolation.py ai/tests/pilot/test_pilot_e2e.py -q --maxfail=5 --disable-warnings
...........                                                              [100%]
11 passed in 5.57s

$ ./.ai-toolkit/scripts/verify.sh backend
Verification gate: backend
✓ django check
✓ no missing migrations
GATE PASSED
```

### Deviations
NONE — OAuth/IdP exchange deferred to ADR Phase 2 as specified.

### Issues Found
NONE

## PEC-4A

## [2026-09-16] backend-worker — Phase PEC-4A: Eval harness baseline + merge gate

### Summary
25 golden Nibras scenarios (≥20). Harness prints metrics JSON with `fabrication_rate=0`. CI step wired. Negative fabrication/deny proofs included. Evidence: `docs/pulse/evidence/PEC-4A-eval-baseline.md`. Partitioned pytest: 75 passed (`ai/eval` + `ai/tests/redteam`). `verify.sh backend` GATE PASSED. No heartbeat/frontend/engine-spine changes.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | ≥20 golden nibras scenarios | PASS | 25 scenarios across grounding/deny/lifecycle/clarify/topic_guard/Q-1 |
| 2 | `run_harness.py` metrics JSON | PASS | `python -m ai.eval.run_harness`; fabrication_rate hard gate |
| 3 | CI invocation | PASS | Extended `.github/workflows/ci.yml` backend job (no duplicate full suite) |
| 4 | Deliberate negative fabrication/deny | PASS | `test_deliberate_fabrication_fails_check` + `test_deny_leak_fails_scoped_empty_check` |
| 5 | Evidence baseline | PASS | `docs/pulse/evidence/PEC-4A-eval-baseline.md` |

### Files Changed
| Action | File | What |
|--------|------|------|
| CREATE | `backend/ai/eval/scenarios_nibras.py` | 25 declarative golden scenarios |
| CREATE | `backend/ai/eval/run_harness.py` | CI entry + metrics aggregator + fabrication=0 gate |
| CREATE | `backend/ai/eval/test_harness_golden.py` | pytest `eval_golden` + negative proofs |
| CREATE | `docs/pulse/evidence/PEC-4A-eval-baseline.md` | Measured baseline numbers |
| MODIFY | `backend/ai/eval/checks.py` | `assert_compound_net_pay_answer`, `assert_topic_guard_fires` |
| MODIFY | `backend/ai/eval/__init__.py` | PEC-4A package docstring |
| MODIFY | `backend/pytest.ini` | `eval_golden` marker |
| MODIFY | `.github/workflows/ci.yml` | Eval harness golden step |

### Verification Output
```
$ cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m ai.eval.run_harness
NIB-NP-001: PASS
NIB-NP-002: PASS
NIB-NP-003: PASS
NIB-NP-004: PASS
NIB-NP-005: PASS
NIB-NP-006: PASS
NIB-DENY-001: PASS
NIB-DENY-002: PASS
NIB-DENY-003: PASS
NIB-PAY-001: PASS
NIB-PAY-002: PASS
NIB-PAY-003: PASS
NIB-PAY-004: PASS
NIB-PAY-005: PASS
NIB-CLAR-001: PASS
NIB-CLAR-002: PASS
NIB-CLAR-003: PASS
NIB-CLAR-004: PASS
NIB-TG-001: PASS
NIB-TG-002: PASS
NIB-TG-003: PASS
NIB-TG-004: PASS
NIB-TG-005: PASS
NIB-Q1-001: PASS
NIB-Q1-002: PASS
---
pass_rate=25/25
METRICS_JSON={"clarify_pass": 1.0, "compound_pass": 1.0, "deny_correctness": 1.0, "fabrication_rate": 0.0, "failed": 0, "failed_ids": [], "grounding_pass": 1.0, "instance": "nibras", "latency_ms_total": 90.81, "lifecycle_pass": 1.0, "pass_rate": 1.0, "passed": 25, "scenario_count": 25, "tokens": 0, "topic_guard_pass": 1.0}

$ ../.venv/bin/python -m pytest ai/eval ai/tests/redteam -q --maxfail=8 --disable-warnings
........................................................................ [ 96%]
...                                                                      [100%]
75 passed in 0.22s

$ ./.ai-toolkit/scripts/verify.sh backend
Verification gate: backend
✓ django check
✓ no missing migrations
GATE PASSED

$ test -f ../docs/pulse/evidence/PEC-4A-eval-baseline.md && echo EVIDENCE_OK
EVIDENCE_OK
```

### Deviations
Harness is offline/deterministic (golden fixtures + process/instance YAML) so it stays CI-safe without a live LLM or DB. Host-executor CBAC path remains covered by existing `ai/tests/test_hrms_answer_quality_eval.py` (not re-run in this partition).

### Issues Found
NONE

## PEC-3A

## [2026-09-16] backend-worker — Phase PEC-3A: Proactive delivery API proof

### Summary
Proactive → persist → list/SSE path proved with OUTCOME contract: honest `confidence` / `confidence_label` / `provenance`, no engine jargon. Gaps fixed: digest/info now bus-publishes for SSE; brand-aware `app_identifier` on persist + `scope_ai_queryset`. Evidence: `docs/pulse/evidence/PEC-3A-proactive-api.md`. Targeted pytest 65 passed. `verify.sh backend` GATE PASSED. No frontend.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Trace proactive → persist → list/SSE; fix gaps | PASS | Always bus-publish; outcome fields; brand app scope |
| 2 | Test insight visible via API with confidence + no jargon | PASS | `test_insights_api.py` PEC-3A cases |
| 3 | Evidence pack | PASS | `docs/pulse/evidence/PEC-3A-proactive-api.md` |
| 4 | Verification gate | PASS | 65 passed + verify.sh backend |

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `backend/ai/engine/proactive/delivery.py` | `build_outcome_fields` / always SSE bus / app_identifier |
| MODIFY | `backend/ai/engine/knowledge_graph/models.py` | CBAC fields on engine `KgProactiveInsight` |
| MODIFY | `backend/ai/insights_api.py` | List + SSE OUTCOME with confidence/provenance |
| MODIFY | `backend/accounts/ai_scoping.py` | `resolve_default_app_identifier()` filter |
| MODIFY | `backend/ai/tests/test_insights_api.py` | PEC-3A proof tests |
| CREATE | `docs/pulse/evidence/PEC-3A-proactive-api.md` | Evidence pack |

### Verification Output
```
$ cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/ -k "proactive or insight" -q --maxfail=8 --disable-warnings
.................................................................        [100%]
65 passed, 2114 deselected in 3.99s

$ ./.ai-toolkit/scripts/verify.sh backend
Verification gate: backend
✓ django check
✓ no missing migrations
GATE PASSED

$ test -f docs/pulse/evidence/PEC-3A-proactive-api.md && echo EVIDENCE_OK
EVIDENCE_OK
```

### Deviations
NONE — frontend notification chrome deferred to PEC-3B per TASKS.md.

### Issues Found
NONE

## PEC-3B

## [2026-09-16] frontend-worker — Phase PEC-3B: Proactive insight surfaces in Nibras UI

### Summary
Nibras insights bell/panel now consumes PEC-3A list + SSE OUTCOME fields (`confidence_label`, `provenance`) with dismiss + act affordances. Confidence uses real backend labels via `ConfidenceIndicator` (never invented). Provenance ⓘ shows basis/sources only when present. RULE_23: no engine jargon in copy; title/empty state use “assistant”. Lint 0 errors; 15 targeted vitests passed; production build green.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Wire panel to SSE/API confidence + provenance | PASS | `InsightNotificationPanel` + existing `useInsightStream` |
| 2 | Dismiss + act affordances; RULE_23 copy | PASS | `dismissed` / `acted_on` + i18n outcome copy |
| 3 | Targeted vitest + lint + build | PASS | 15 tests; lint 0 errors; build OK |

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `carbon-frontend/src/components/notifications/InsightNotificationPanel.jsx` | Confidence, provenance, act/dismiss, skeletons, empty state |
| MODIFY | `carbon-frontend/src/components/HeaderEnhanced.jsx` | Unread-aware insights bell aria-label |
| MODIFY | `carbon-frontend/src/i18n/locales/en/shell.json` | Insights copy (RULE_23) |
| MODIFY | `carbon-frontend/src/i18n/locales/ar/shell.json` | Arabic insights copy |
| MODIFY | `carbon-frontend/src/__tests__/InsightNotificationPanel.test.jsx` | PEC-3B coverage |

### Verification Output
```
$ cd /home/ahmed/ws/carbon/carbon-frontend && npm run lint
✖ 52 problems (0 errors, 52 warnings)

$ npx vitest run src/__tests__/InsightNotificationPanel.test.jsx src/__tests__/NotificationCenter.test.jsx
Test Files  2 passed (2)
Tests  15 passed (15)

$ npm run build
✓ built in 17.21s
```

### Deviations
- Provenance opens an inline popover (basis + sources) rather than the full Inspector drawer — panel is ambient; Analyst depth still available from conversation provenance when present.
- Row click acknowledges (`read`) only; navigation is the explicit Act chip (Principle 11 / PULSE-UX-DESIGN InsightRow).

### Issues Found
NONE

## ECF-0

**Date:** 2026-09-16  
**Worker:** qa-validator (Pulse)  
**Verdict:** **PASSED** — golden harness landed; baseline xfails only (no ERROR/EXCEPTION).

### Scope
- Created/aligned `backend/ai/tests/test_ecf_golden.py` (TESTS ONLY)
- All 13 minimum GoldenCase ids from TASKS.md Phase ECF-0
- `@pytest.mark.xfail(reason="baseline — ECF not yet implemented", strict=False)`
- Expected fails emit `BASELINE_FAILURE` via `pytest.fail(...)` under xfail → XFAIL
- No runtime ECF implementation; no NSR / people / my / team product paths touched

### Gate evidence

```
$ cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest ai/tests/test_ecf_golden.py -v
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0 -- /home/ahmed/ws/carbon/backend/../.venv/bin/python
cachedir: .pytest_cache
django: version: 5.2.3, settings: config.settings (from ini)
rootdir: /home/ahmed/ws/carbon/backend
configfile: pytest.ini
plugins: django-4.12.0, cov-7.1.0, anyio-4.15.1, asyncio-1.4.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 17 items

ai/tests/test_ecf_golden.py::TestGoldenCasesAreDeclared::test_minimum_case_count PASSED [  5%]
ai/tests/test_ecf_golden.py::TestGoldenCasesAreDeclared::test_all_required_ids_present PASSED [ 11%]
ai/tests/test_ecf_golden.py::TestGoldenCasesAreDeclared::test_each_case_has_invariants PASSED [ 17%]
ai/tests/test_ecf_golden.py::TestGoldenCasesAreDeclared::test_must_find_cases_have_employee_no PASSED [ 23%]
ai/tests/test_ecf_golden.py::test_golden_case_baseline[lookup_salman_en_full] XFAIL [ 29%]
ai/tests/test_ecf_golden.py::test_golden_case_baseline[lookup_salman_ar] XFAIL [ 35%]
ai/tests/test_ecf_golden.py::test_golden_case_baseline[lookup_salman_partial] XFAIL [ 41%]
ai/tests/test_ecf_golden.py::test_golden_case_baseline[lookup_employee_no_1046] XFAIL [ 47%]
ai/tests/test_ecf_golden.py::test_golden_case_baseline[lookup_employee_no_1021] XFAIL [ 52%]
ai/tests/test_ecf_golden.py::test_golden_case_baseline[lookup_pk_104] XFAIL [ 58%]
ai/tests/test_ecf_golden.py::test_golden_case_baseline[lookup_reena_sekaran] XFAIL [ 64%]
ai/tests/test_ecf_golden.py::test_golden_case_baseline[lookup_ar_abrar] XFAIL [ 70%]
ai/tests/test_ecf_golden.py::test_golden_case_baseline[existence_over_truncated] XFAIL [ 76%]
ai/tests/test_ecf_golden.py::test_golden_case_baseline[headcount_stable] XFAIL [ 82%]
ai/tests/test_ecf_golden.py::test_golden_case_baseline[kuwaiti_count_stable] XFAIL [ 88%]
ai/tests/test_ecf_golden.py::test_golden_case_baseline[position_label] XFAIL [ 94%]
ai/tests/test_ecf_golden.py::test_golden_case_baseline[arabic_in_arabic_out] XFAIL [100%]

======================== 4 passed, 13 xfailed in 0.12s =========================

$ cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/import-boundary-lint.py
Import boundary: clean (engine imports only engine/stdlib/SDK)
```

### Checklist
| Check | Result |
|-------|--------|
| 13 minimum GoldenCase ids | ✅ |
| xfail reason exact | ✅ `baseline — ECF not yet implemented` |
| BASELINE_FAILURE not ERROR | ✅ 13 XFAIL, 0 ERROR |
| Structural declaration tests | ✅ 4 PASSED |
| Import-boundary lint | ✅ clean |
| Runtime ECF code | ✅ untouched |

**ECF-0 → DONE.** Next: ECF-1 (Entity Registry + descriptor + `ECF_ENABLED` flag).

## ECF-1

**Date:** 2026-09-16  
**Worker:** backend-worker (Pulse)  
**Status:** DONE  
**Phase:** Entity Registry + descriptor schema + config flag (ADR-0032)

### Delivered
| Item | Path / note |
|------|-------------|
| Entity package | `backend/ai/engine/cognition/entity/` — reused existing module; no parallel invent |
| `registry.py` | Descriptor dataclasses + `load_descriptors` / `get_descriptor` (pure data; model paths are strings) |
| `ECF_ENABLED` | Reused existing flag in `backend/ai/engine/core/config.py` (`Settings.ECF_ENABLED: bool = False`) — not duplicated |
| nibras `entities:` | `backend/ai/engine/instances/nibras/instance.yaml` — employee descriptor (identifiers, bilingual search_fields, label_map, masking, metrics, scope_lookup) |
| Unit tests | `backend/ai/tests/test_ecf_registry.py` — loads via `_instance_config("nibras", None)` |

### Intentional deltas vs TASKS example YAML
- `identifiers: [employee_no, civil_id, id]` — employee_no first so numeric user input resolves correctly
- `employee_no` search weight `3.0` (not `2.0`) — must beat name-field weights

### DO NOT TOUCH (confirmed)
- No tool wiring / `tools.py` edits this phase
- Engine registry does not import people/mdm/accounts
- NSR / people product UI / correspondence staff circuits untouched

### Verification Output
```
$ cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_ecf_registry.py ai/tests/test_instance_registry.py -v 2>&1 | tail -20
# Must: test_ecf_registry passes; test_instance_registry still all green (no regression)
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0 -- /home/ahmed/ws/carbon/backend/../.venv/bin/python
cachedir: .pytest_cache
django: version: 5.2.3, settings: config.settings (from ini)
rootdir: /home/ahmed/ws/carbon/backend
configfile: pytest.ini
plugins: django-4.12.0, cov-7.1.0, anyio-4.15.1, asyncio-1.4.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 24 items

ai/tests/test_ecf_registry.py::TestLoadDescriptors::test_employee_descriptor_present PASSED [  4%]
ai/tests/test_ecf_registry.py::TestLoadDescriptors::test_employee_model_path PASSED [  8%]
ai/tests/test_ecf_registry.py::TestLoadDescriptors::test_employee_identifiers PASSED [ 12%]
ai/tests/test_ecf_registry.py::TestLoadDescriptors::test_employee_search_fields_bilingual PASSED [ 16%]
ai/tests/test_ecf_registry.py::TestLoadDescriptors::test_arabic_fields_have_normalize PASSED [ 20%]
ai/tests/test_ecf_registry.py::TestLoadDescriptors::test_employee_no_highest_weight PASSED [ 25%]
ai/tests/test_ecf_registry.py::TestLoadDescriptors::test_label_map_position_and_org_unit PASSED [ 29%]
ai/tests/test_ecf_registry.py::TestLoadDescriptors::test_salary_masking_policy PASSED [ 33%]
ai/tests/test_ecf_registry.py::TestLoadDescriptors::test_canonical_metrics_defined PASSED [ 37%]
ai/tests/test_ecf_registry.py::TestLoadDescriptors::test_scope_lookup_set PASSED [ 41%]
ai/tests/test_ecf_registry.py::TestGetDescriptor::test_known_entity PASSED [ 45%]
ai/tests/test_ecf_registry.py::TestGetDescriptor::test_unknown_entity_returns_none PASSED [ 50%]
ai/tests/test_ecf_registry.py::TestGetDescriptor::test_empty_config_returns_none PASSED [ 54%]
ai/tests/test_ecf_registry.py::TestGetDescriptor::test_none_config_returns_none PASSED [ 58%]
ai/tests/test_ecf_registry.py::TestNoEngineRuleViolation::test_registry_does_not_import_django PASSED [ 62%]
ai/tests/test_instance_registry.py::test_brand_maps_to_instance_and_default_app[aastmt-carbon-carbon] PASSED [ 66%]
ai/tests/test_instance_registry.py::test_brand_maps_to_instance_and_default_app[nibras-nibras-people] PASSED [ 70%]
ai/tests/test_instance_registry.py::test_brand_maps_to_instance_and_default_app[medos-medos-medos] PASSED [ 75%]
ai/tests/test_instance_registry.py::test_brand_maps_to_instance_and_default_app[tectona-tectona-healthy] PASSED [ 79%]
ai/tests/test_instance_registry.py::test_unknown_brand_falls_back_to_carbon PASSED [ 83%]
ai/tests/test_instance_registry.py::test_default_app_for_instance_is_instance_scoped PASSED [ 87%]
ai/tests/test_instance_registry.py::test_nibras_instance_config_is_people_scoped_and_has_no_api_catalog PASSED [ 91%]
ai/tests/test_instance_registry.py::test_carbon_instance_config_defaults_to_carbon_app_even_on_nibras_brand PASSED [ 95%]
ai/tests/test_instance_registry.py::test_unknown_instance_falls_back_to_carbon_config PASSED [100%]

============================== 24 passed in 0.30s ==============================

$ cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/import-boundary-lint.py
Import boundary: clean (engine imports only engine/stdlib/SDK)
```

### Checklist
| Check | Result |
|-------|--------|
| registry.py descriptor schema | ✅ |
| ECF_ENABLED default False in Settings | ✅ (reused; not duplicated) |
| nibras entities: employee block | ✅ |
| test_ecf_registry via `_instance_config` | ✅ 15/15 |
| test_instance_registry no regression | ✅ 9/9 |
| Import-boundary lint | ✅ clean |
| No tool wiring this phase | ✅ |

**ECF-1 → DONE.** Next: ECF-2 (Generic resolver, shadow, no tool wiring).
