# PV2 live 3-script re-check — 2026-09-23

**Track:** PV2 — Pulse v2 Intelligence Contract (ADR-0047) · **Phase:** 0C re-check after P1–P5 + C8/C5  
**Host user:** `emp_1067` · **DB:** `nibras_dev` · **Mode:** Chat only (ADR-0046)  
**Command:** `python -m ai.eval.multiturn.runner --scripts 'scripts/0[148]-*.yaml' --live --host-user emp_1067 --no-isolated-db --verbose --report /tmp/pv2-0c-live-recheck-20260923.json`  
**Raw:** `docs/pulse/evidence/PV2-live-recheck-2026-09-23.json`

Human approved 2026-09-23 10:54 +03. No `manage.sh` start/restart/kill. Elapsed 129 s. Exit 0.

## Headline vs 2026-09-22 baseline

| | 2026-09-22 P0 | 2026-09-23 re-check |
|---|---|---|
| turns_passed | 0 / 24 | **13 / 24** |
| router_agreement | 0.50–0.625 | **0.667** |
| language_fidelity | 0.81 / 1.00 / 1.00 | **1.0** |
| focus_retention | 0.40–0.50 | **0.615** |
| slot_carry_over | (not reported per-script) | **1.0** |
| llm_calls_p50 | 3 | **2** |
| llm_calls_max | 5 | **5** |
| turns_over_budget | 19 / 24 | **5 / 24** |
| scripts_passed | 0 / 3 | 0 / 3 |

Scripts still fail as wholes (goldens are turn-strict). The movement is turn-level, not a claim that live is G5-green.

## Per script

```
                         turns_passed  router  lang_fid  focus   llm_p50  llm_max  over
ess-loan-ar-01 (AR)          6/8        0.875    1.00     0.75      2        3      1/8
chat-handoff-write-01 (EN)   7/8        1.000    1.00     1.00      0        3      1/8
payroll-followup-en-01 (EN)  0/8        0.125    1.00     0.00      2        5      3/8
```

Per-script router = `1 - decision_failures/8`. Focus from `mentions_any` on applicable turns.

### ess-loan-ar-01 — 6/8

- t1 `handoff_agent` llm=0 Arabic — F-LIVE-1 (English refuse) closed on live.
- t2 `answer` llm=3 — mentions miss `٥٠٠٠`/`dinar` (reply used `5000 دينار`) + over budget.
- t3–t6 `answer` llm=2 Arabic — amount/type carried; t6 answers approval-odds instead of navigating (F-LIVE-3 closed on live).
- t7 `handoff_agent` llm=0 — golden wants `answer|navigate` for «شكراً لك». Same thanks-after-handoff policy as 08 t8.
- t8 `handoff_agent` llm=0 — restates emergency + 5000.

### chat-handoff-write-01 — 7/8

- t1–t2 `clarify` llm=0 (incomplete write).
- t3 `handoff_agent` llm=0 — F-LIVE-4 closed on live.
- t4–t7 honest Chat/Agent wording (F-LIVE-7 still holds).
- t6 `answer` llm=3 only miss (budget).
- t8 thanks restates handoff llm=0 — as scripted.

No Chat host mutation. No “I need your approval” from Chat.

### payroll-followup-en-01 — 0/8

F-LIVE-6 (HR 403 / `list_payslip_lines`) did not recur as a 403. The new live hole is **grounded self-service numbers**:

- t1 `tool_answer` llm=5 — “search returned general payslip information, not your actual records”; no `4500`.
- t2/t4/t5/t6 `clarify` — menu instead of the prior payslip.
- t3 `tool_answer` llm=5 — no `3700`.
- t7 `tool_answer` llm=2 — calendar search, not a date.
- t8 `answer` llm=3 — how to download (decision ok vs `answer|handoff_agent`; over budget).

C2 live on this script is **0.0**. Do not treat 2C as “payslip recall done.”

## Findings status after this run

| ID | Status | Evidence this run |
|---|---|---|
| F-LIVE-1 | closed | loan-ar t1 Arabic `handoff_agent` llm=0 |
| F-LIVE-2 | closed | Chat never asked for approval / never mutated |
| F-LIVE-3 | closed | loan-ar t6 `answer`, not `navigate` |
| F-LIVE-4 | closed | handoff t3 `handoff_agent` llm=0 |
| F-LIVE-5 | mostly closed | p50 3→2; max still 5 on payroll tool turns |
| F-LIVE-6 | 403 closed; numbers open | no 403; still 0/8 mentions |
| F-LIVE-7 | holds | handoff t4–t7 honest boundary |
| F-LIVE-8 | holds | Arabic + amount + type carried |
| F-LIVE-9 | **open** | payroll live cannot surface emp_1067 net/GOSI/loan figures |
| F-LIVE-10 | closed offline | thanks after a complete write is 0-LLM ack (live 3-script not re-run) |

## Per-objective (this 3-script slice)

```
C1 0.375   C2 0.0   C3 0.75   C5 0.875   C6 0.875   C8 0.75
```

Offline G5 (stub, 12×8) is unchanged: router 0.979, slot 1.0, llm p50/max 2, turns 94/96. This file is **live** only.

## What this does not close

- 6B night 1 (mutating Chat→Agent→Approve) is a separate ledger.
- 4B Arbiter flip still blocked until 2026-09-30.
- 6C ADR-0047 Accepted still waits on G5 + five green nights.
- Goldens were not edited.
