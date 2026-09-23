# PV2 live 3-script — 2026-09-23i

**Host:** `emp_1067` · **DB:** `nibras_dev` · **Mode:** Chat only  
**Elapsed:** ~50 s · exit 0  
**Raw:** `docs/pulse/evidence/PV2-live-recheck-2026-09-23i.json`  
`:8009` was not started. The runner is in-process.

t1’s extra LLM was ReAct `_observe`, not single-pass synthesis. Empty
`list_my_payslips` now returns the honest copy from observe — no third call.

| | 23h | **23i** |
|---|---|---|
| turns_passed | 21 / 24 | **21 / 24** |
| scripts_passed | 2 / 3 | **2 / 3** |
| router_agreement | 1.0 | **1.0** |
| focus_retention | 0.769 | **0.769** |
| llm p50 / max | 0 / 3 | **0 / 2** |
| turns_over_budget | 1 / 24 | **0 / 24** |

```
ess-loan-ar-01            8/8 PASS
chat-handoff-write-01     8/8 PASS
payroll-followup-en-01    5/8        t1 now llm=2 (budget pass), still misses 4500
                                     t2/t4/t6/t7/t8 pass at 0 LLM
                                     t3 misses 3700; t5 misses 800
                                     No invented 4500 / 3700 / 800
```

C8 on this slice is 1.0 (over 0, max 2). C2 is 0.625 — host rows still missing.
Goldens not edited. Night 2026-09-23 FAIL not rewritten. G5 stayed 96/96.
