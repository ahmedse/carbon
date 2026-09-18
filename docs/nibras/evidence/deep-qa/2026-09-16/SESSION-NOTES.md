# Deep QA session — COMPLETE · 2026-09-17

**Scope:** Nibras People / My / Team (not Pulse)  
**Seat:** Master Nibras (RULE_30)  
**Plan:** `docs/nibras/QA-DEEP-MULTI-USER-JOURNEY.md`

## Scorecard

| Scope | Done | Total | % |
|-------|------|-------|---|
| **P0 (M-COV-02)** | **46** | **46** | **100%** |
| P1 | **28** | 28 | **100%** |
| P2 | **7** | 7 | **100%** |
| **All cases** | **81** | **81** | **100%** |

Canvas: `nibras-deep-qa-plan.canvas.tsx`

## Product fixes

| ID | Fix | Evidence |
|----|-----|----------|
| **J-EMP-06** | null `join_date` → no entitlements | `99000` ents=0; control `99001` ents=5 |
| **Gender DQ** | compare `.code` not `set:code` | hire `gender=female` → 201 `99010` |
| **J-LV-11** | FSM row-lock on approve | pytest duplex: 1 ok + 1 conflict |

## Ops

| Item | Status |
|------|--------|
| **STACK-RELEASE** | **DONE** — COMMS `20260917-5` closes hold `20260917-4` |
| **Playwright NSR-9** | Chromium launches; **login Invalid credentials** — `ChangeMe_132` ≠ DB hash for `emp_1001`. Spec default manager fixed to `emp_1399`. Re-run after: `export EMPLOYEE_DEFAULT_PASSWORD=…` (same as `link_employee_users`) then `npx playwright test --config e2e/playwright.config.ts nibras-leave-approve` |
| **J-ORG-01** | Accepted: flat list by name; tree via `/tree/` + FE |

## Artifacts

Hires `9091701` · `99000` · `99001` · `99010` · payroll run **17** · cert 20
