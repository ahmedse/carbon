# TASKS — Active Phase Pointer

**Maintained by:** Master Architect · **Updated:** 2026-08-02

The active plan is **`plans/CARBON_ENTERPRISE_READINESS_PLAN.md`** (E0→E6), based on
`CARBON_MASTER_AUDIT_20260802.md`. This file only tracks *where we are* — phase specs live in
the plan, results live in `TASK-RESULTS-E*.md`.

Previous content (Phase 08 hardening) was completed 2026-07-29 and is superseded.

## Current status

| Phase | Title | Status | Result record |
|---|---|---|---|
| E0 | Gate & toolkit trust | ✅ DONE 2026-08-02 (Master-verified) | TASK-RESULTS-E0.md |
| E1 | Security lockdown | ✅ DONE 2026-08-02 (Master-verified) | TASK-RESULTS-E1.md |
| E2 | Carbon deployment blockers | ⬜ READY — E2-B1 next (backend-worker, DeepSeek-V3) | — |
| E3 | Carbon enterprise features | ⬜ blocked on E2 | — |
| E4 | Frontend hygiene & design system | ⬜ can parallel E2/E3-backend | — |
| E5 | Backend hygiene & platform coverage | ⬜ blocked on E2-backend | — |
| E6 | Docs, archive, deployment readiness | ⬜ last | — |

**Human decisions pending** (see plan header): credential rotation · git history scrub ·
canonical grid factor · PDF at go-live? · PROD_* values · CI platform.

## Worker activation — E2-B1 (paste to a DeepSeek-V3 chat)

> Your role is **backend-worker** for the Carbon Data Trust Platform.
> 1. Read `.ai-toolkit/project.config.md`
> 2. Read `.ai-toolkit/shared/base-rules.md`
> 3. Read `.ai-toolkit/roles/backend-worker.md`
> 4. Read `plans/CARBON_ENTERPRISE_READINESS_PLAN.md` — Phase E2-B1 (RBAC reconciliation)
> 5. Confirm your role and begin. Report to `TASK-RESULTS-E2-B1.md` with terminal proof.
