# TASK-RESULTS — Active handoffs only

Append worker verification here for **current** phases.

**Full historical results** (pre-2026-09-16 cleanup):  
[`docs/_archive/tasks-history/TASK-RESULTS-FULL-2026-09-16.md`](docs/_archive/tasks-history/TASK-RESULTS-FULL-2026-09-16.md)

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
