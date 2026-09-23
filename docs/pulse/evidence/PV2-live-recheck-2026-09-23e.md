# PV2 live 3-script — 2026-09-23e

**Host:** `emp_1067` · **DB:** `nibras_dev` · **Mode:** Chat only  
**Elapsed:** 82 s · exit 0  
**Raw:** `docs/pulse/evidence/PV2-live-recheck-2026-09-23e.json`  
`:8009` was stopped. The runner is in-process. No `manage.sh` start.

| | 23d | 23e |
|---|---|---|
| turns_passed | 16 / 24 | **19 / 24** |
| scripts_passed | 1 / 3 | **2 / 3** |
| router_agreement | 0.833 | **1.0** |
| focus_retention | 0.538 | **0.692** |
| llm p50 / max | 2 / 3 | **1 / 3** |
| turns_over_budget | 7 / 24 | **4 / 24** |

```
ess-loan-ar-01            8/8 PASS   t2 confirm = handoff_agent llm=0, echoes ٥٠٠٠
chat-handoff-write-01     8/8 PASS
payroll-followup-en-01    3/8        t4, t7, t8 pass. t7/t8 are 0 LLM.
                                     t1/t3/t5 still miss 4500/3700/800. No invented figures.
```

C3, C5, C6, C8 (loan script) = 1.0 on this slice. C2 = 0.375. C1 focus 0.692, under 0.95. Goldens not edited. Night 2026-09-23 FAIL not rewritten.
