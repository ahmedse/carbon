# PV2 live rest after 23m profile bind

**Host:** `emp_1067` · **DB:** `nibras_dev` · **Mode:** Chat only  
G5 offline still **96/96**. Goldens not edited. 6B not run.

| Script | prior | **23m** | note |
|---|---|---|---|
| grounded-recall-01 | 3/8 | **6/8** | t1 1067 at 1 LLM; t2/t6 Coiled Tubing ≠ Engineering |
| entity-focus-switch-01 | 8/8 hollow | **1/8 honest** | emp_1067 `resolve_entity` is 403 `people:view`. Reena 1009 exists (CEO Office). Goldens want Finance/Senior Analyst. |
| plan-status-01 | 8/8 | **8/8 PASS** | |
| memory-learn-fact-01 | — | **8/8 PASS** | 0 LLM throughout |
| date-awareness-01 | — | **5/8** | payday not guessed (no 25 Sep); leave start 3 LLM from host |
| nav-zero-llm-01 | — | **7/8** | t3 loan-types went ReAct (4 LLM, tool_answer) |
| language-fidelity-ar-01 | 7/8 (23l) | not re-run | t2 golden ٦٠٠٠/dinar ≠ host 6500 |

Named coworker lookup still does not call `resolve_entity`. Pulse did not invent
Senior Analyst / Finance / Operations / payday the 25th.

Raw: `PV2-live-06-2026-09-23m.json`, `/tmp/pv2-live-0507-20260923m.json`,
`/tmp/pv2-live-1011-20260923m.json`, `/tmp/pv2-live-rest-20260923m.json` (nav).
