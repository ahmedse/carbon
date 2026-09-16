# Deep QA live browser session — 2026-09-16

**Scope:** Nibras People / My / Team (not Pulse)  
**Seat:** Master Nibras  
**Plan:** `docs/nibras/QA-DEEP-MULTI-USER-JOURNEY.md`

## Scorecard (board)

| Scope | Done | Total | % |
|-------|------|-------|---|
| All cases | **11** | 81 | **14%** |
| **P0 only (M-COV-02)** | **11** | **46** | **24%** |
| Leave P0 | 6 | 10 | 60% |
| Loans P0 | 3 | 5 | 60% |

Canvas: `nibras-deep-qa-plan.canvas.tsx` (execution board). Not UAT PASS until P0 = 100%.

## Stack

FE :5179 · BE :8009 · PG — RUNNING (`manage.sh` URL = `http://localhost:5179/`)  
**STACK-HOLD Nibras until 22:00+03** (COMMS 20260916-11). Shared lease rule binding in `multi-master.md`.

**Ops note:** BE drops tonight = kill/`manage.sh start` + agent sandbox PG false-negative (PB-50), not Django product crash.

## Cast

| ID | User | Role |
|----|------|------|
| EMP | `emp_1001` | ESS |
| MGR | `emp_1399` | Manager of 1001 |
| FIN | `emp_1132` | `finance_group` ScopedRole (provisioned this session — live DB had empty finance_group) |

## Cases

| ID | Result | Evidence |
|----|--------|----------|
| J-LV-01 approve | **PASS** | `CRS-2026-0025` Approved |
| J-LV-04 cancel | **PASS** | Cancel FE shipped; `CRS-2026-0026` Cancelled |
| J-LV-02 reject | **PASS** | `CRS-2026-0027` Rejected; balance unused restored |
| J-LV-03 send-back→resubmit→approve | **PASS** | `CRS-2026-0028` |
| J-LV-06 overlap (NEG) | **PASS** | UI “Overlaps an existing leave request”; `j-lv-06-overlap-ui.png` |
| **J-LV-05** days > remaining | **PASS** | 29 working days vs 22 rem → UI **“Insufficient leave balance — 22 days remaining”** |
| **J-LN-01** loan EMP→MGR→FIN | **PASS** | UI submit `CRS-2026-0032` / Loan **23**; mgr approve → `in_review`; fin approve → **approved**; loan **active**; **6** installments |
| **J-LN-02** finance before mgr | **PASS** | FIN approve while step 0 → **403** not current approver |
| **J-LN-03** My loans label | **PASS** | Card shows **Personal Loan** (not `[object]`); 500.00 / 6 mo / Active |
| P1 URL + throttle | **FIXED** | PB-48/49 |

## FE gaps closed

- Cancel + **Resubmit** on `/my/requests/:id`

## Honest residuals

| Residual | Severity | Notes |
|----------|----------|-------|
| J-LV-05 / 07 / 08 / 11 | P0 | Not executed |
| J-LN-04 People Loans grid | P0 | Not executed |
| J-LN-05 rematerialize idempotent | P0 EDGE | Not executed |
| J-EMP-* hire | P0 | Queued |
| Playwright host | ops | NSR-9 PARTIAL |
| finance_group empty pre-cast | seed/ops | FIN cast hand-provisioned emp_1132 |

## Next open

J-LN-04/05 · J-EMP-01 hire · remaining leave NEG/CONC
