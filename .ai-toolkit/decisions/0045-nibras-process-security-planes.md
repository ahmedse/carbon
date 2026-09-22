# ADR-0045 — Nibras process security planes (host SoD vs Pulse dials)

- **Status:** Accepted
- **Date:** 2026-09-21
- **Deciders:** Master Architect (Nibras + Pulse)
- **Area:** security · cross-cutting (People host + Pulse process governance)
- **Extends:** ADR-0030 (correspondence SoD spine), ADR-0031 D10 (PDP ≠ grant ≠ consent),
  ADR-0044 (dual catalog), RULE_21

## Context

Nibras ships six governed `ProcessDefinition`s (leave, loan, payroll, GOSI/WPS,
onboarding, attendance). YAML declares `human_only`, `separation_of_duties`, and
`refuse_if` (e.g. requester ≠ approver). Operators and agents may treat that as
**host security**. It is not.

Today there are **two planes**:

| Plane | What it enforces | Where |
|-------|------------------|-------|
| **A — Host HR** | CBAC (`people:*`, `my:access`, correspondence caps), org-unit queryset scope, Correspondence FSM + `skip_if_self` for leave/loan | `people/permissions.py`, `people/views.py`, `ai/host_executor.py` `_people_scope`, `correspondence/fsm.py` / `routing.py` |
| **B — Pulse dials** | Process YAML autonomy/SoD declarations, RULE_21 consent, `ApprovalGrant` on CommandBoundary, inbox authority (**NPS-2:** Nibras review caps resolve to host CBAC via `ai.governance.review_authority`; unmapped Pulse caps still default `ai:operator`) | `domain_packs/nibras/processes/*.yaml`, `ai/command_boundary.py`, `ai/grant.py`, `ai/task_inbox.py`, `ai/governance/review_authority.py` |

**Plane B does not close Plane A.** A user with `people:manage` can call DRF lifecycle
endpoints (payroll commit, WPS submit, employee activate, attendance approve) without
Pulse SoD. Catalog `permissions:` lists are capability-id echoes — **not** Django groups.

## Decision

1. **Honesty rule (non-negotiable).** Never claim a process step is “role-secured” or
   “SoD-enforced” unless the **host** path that commits the effect enforces it.
   Process YAML alone is a **dial contract** (validated by agent-bank tests), not an ACL.

2. **Current honesty matrix** (update when host wiring changes; CI locks it):

   | Process | Submit (host) | Final effect (host) | Host SoD today |
   |---------|---------------|---------------------|----------------|
   | `leave.request.lifecycle` | `/me/leave` + correspondence | Manager corr approve → signal | **correspondence** |
   | `loan.request.lifecycle` | `/me/loan` + correspondence | Manager→finance corr | **correspondence** |
   | `payroll.run.lifecycle` | `people:manage` + org | Distinct actor commit via `people.governance.sod` | **host_gate** |
   | `gosi_wps.sif.lifecycle` | `people:manage` + org | Distinct actor WPS submit | **host_gate** |
   | `employee.onboarding.lifecycle` | `people:manage` + org | Distinct actor activate | **host_gate** |
   | `attendance.permission.lifecycle` | `/me/attendance-permissions` + correspondence | Manager corr approve → signal (`approved=true`) | **correspondence** |

   Admin create/PATCH for attendance remains an ops fallback with NPS-1 SoD
   (`people.governance.sod`); Agent happy path is ESS only.

   **NPS-2 review authority** (Pulse inbox `required_authority`, not host SoD):

   | Capability | CBAC authority | Typical group |
   |------------|----------------|---------------|
   | `leave.request.review` | `correspondence:act` | `manager_group` |
   | `attendance.permission.review` | `correspondence:act` | `manager_group` |
   | `loan.request.review` | `correspondence:finance` | `finance_group` |
   | `payroll.run.review` / `gosi_wps.sif.review` / `employee.onboarding.review` | `people:manage` | `people_lead` |

3. **Proper closure (platform mechanism — forbid ad-hoc).** Closing residual gaps (if any)
   uses one **shared host governance gate**, not per-view one-liners. **NPS-1 shipped:**
   `people.governance.sod` + `SoDPreparation` — stamp on compute/generate/create; refuse
   same-actor on commit/submit/activate/approve (DRF + host_executor). **NPS-2 shipped:**
   `ai.governance.review_authority` maps Nibras `*.review` human_task capabilities to host
   CBAC (`correspondence:act` / `correspondence:finance` / `people:manage`); enqueue +
   inbox decide/list use that authority — `ai:operator` is **not** a substitute for HR.

   - **Employee-originated requests** (leave, loan, future attendance self-service):
     route through **ADR-0030 Correspondence** (role routing + `skip_if_self`). Agent
     tools bind self-service / corr paths, not admin PATCH as the happy path.
   - **Admin lifecycle irreversibles** (payroll commit, GOSI submit, onboarding activate,
     attendance approve until ESS exists): introduce a single reusable host module
     (e.g. `people.governance.sod` or correspondence-backed prep/approve records) that
     enforces preparer ≠ approver (and optional grant digest) **inside the DRF/service
     boundary** that commits the effect. Wire every irreversible view through that module.
   - Pulse CommandBoundary consent + `ApprovalGrant` remain **necessary for Agent**
     (ADR-0031 D10) and **insufficient alone** for host SoD.
   - Pulse inbox review authority for Nibras processes must resolve through
     `ai.governance.review_authority` (NPS-2), never hardcode `ai:operator` for HR reviews.

4. **Forbidden shortcuts**
   - Patching only `host_executor` / Agent confirm while leaving DRF open.
   - Inventing Django permissions per capability id without a CBAC mapping ADR.
   - Treating `ai:operator` inbox as substitute for manager/finance HR roles.
   - Marking a process “secure” in SCOREBOARD/README because YAML has SoD.

5. **Evidence.** Honesty matrix test
   `ai/tests/test_nibras_process_security_planes.py` + playbook PB-61. After host SoD
   ships, flip matrix rows and add service-level refuse tests (same actor → 403/422).

## Alternatives Considered

- **“Pulse consent is enough.”** Rejected — DRF bypass is the attack path.
- **Scatter `if request.user == preparer` in each view.** Rejected — firefighting;
  drifts; violates shared spine (ADR-0030 / single gate).
- **Disable all admin writes; Agent-only.** Rejected — ops need admin; security must
  hold on both doors.

## Consequences

- **Positive:** Security claims match enforcement; workers know Plane A vs B; closure
  path is platform-shaped.
- **Trade-off:** Document residual risk; do not paper over Plane A vs B. Host SoD
  (NPS-1) and review→HR CBAC (NPS-2) closed the prior dial-only / operator-as-HR gaps
  for the six Nibras processes.
- **Do NOT re-try:** Claiming YAML SoD = host SoD; Agent-only patches; ad-hoc per-endpoint
  SoD without shared module; substituting `ai:operator` for manager/finance/`people:manage`.

## References

- `.ai-toolkit/shared/security.md` §RULE 11
- `.ai-toolkit/troubleshooting/playbook.md` PB-61
- `.ai-toolkit/project.config.md` RULE_34
- ADR-0030, ADR-0031 D10, ADR-0044
- `domain_packs/nibras/README.md` · `docs/pulse/PULSE-AGENTIC-WORKFLOW-AUDIT-KB.md` §7
