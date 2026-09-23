# PV2 F-LIVE-10 — thanks after a complete write is an ack

**Date:** 2026-09-23  
**Track:** Pulse v2 Intelligence Contract (ADR-0047) · C5 / C8  
**DB:** `TEST_DB_NAME=test_nibras_dev_master` / `…_multiturn`  
**Raw:** `docs/pulse/evidence/PV2-F-LIVE-10-offline.json`

## Defect

After Chat had already handed off a bound ESS write (`prior_enough`), `_try_chat_write_handoff` re-fired `handoff_agent` on a bare thank-you so `chat-handoff-write-01` t8 would pass. That contradicted C8 (thanks = 0-LLM `answer`) and the two other bank scripts:

| Script | Utterance | Wanted | Was |
|---|---|---|---|
| `ess-loan-ar-01` t7 | «شكراً لك» | `answer` / `navigate` | `handoff_agent` |
| `plan-status-01` t8 | "Thanks for helping" | `answer` / `navigate` | `handoff_agent` |
| `chat-handoff-write-01` t8 | "Thank you for the help" | `handoff_agent` (encoded the defect) | `handoff_agent` |

## Fix

`prior_enough` + not a new write → return `None`. Thanks falls through to the existing 0-LLM ack (`try_zero_llm_answer`). Incomplete writes still `clarify`. Complete writes still `handoff_agent` once.

## Golden correction (Master)

`08-chat-handoff-write-01` t8 `decision_in`: `handoff_agent` → `answer`. `max_llm_calls` stays 0. This is not a budget loosen — C8 and the other two scripts already defined thanks as `answer`.

## Offline G5 after the fix

```
scripts_passed: 12/12
turns_passed: 96/96
router_agreement: 1.0
slot_carry_over: 1.0
language_fidelity: 1.0
llm_calls_p50: 2
llm_calls_max: 2
turns_over_budget: 0
per_objective_pass: all C1–C10 / A1 / A2 = 1.0
```

`--gate` exit 0. Unit: `test_pv2_handoff_agent` 17 · `test_pv2_zero_llm` 18. Import boundary still 9.

## Not claimed

- Live 3-script was not re-run. Loan-ar t7 should now ack; that is not recorded as live.
- 6B night 2026-09-23 stays FAIL. 4B still blocked until 2026-09-30. 6C still waits on five green nights.
