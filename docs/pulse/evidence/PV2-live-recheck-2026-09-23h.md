# PV2 live 3-script — 2026-09-23h

**Host:** `emp_1067` · **DB:** `nibras_dev` · **Mode:** Chat only  
**Elapsed:** 56 s · exit 0  
**Raw:** `docs/pulse/evidence/PV2-live-recheck-2026-09-23h.json`  
`:8009` was not started. The runner is in-process.

A non-empty-looking `list_my_payslips` digest no longer hides the history
fallback. Synthesis text that says “found no payslips” seeds `last_results`
`count=0` so the next turn can answer at 0 LLM.

| | 23e | 23g | **23h** |
|---|---|---|---|
| turns_passed | 19 / 24 | 18 / 24 | **21 / 24** |
| scripts_passed | 2 / 3 | 1 / 3 | **2 / 3** |
| router_agreement | 1.0 | — | **1.0** |
| focus_retention | 0.692 | 0.615 | **0.769** |
| llm p50 / max | 1 / 3 | 1 / 3 | **0 / 3** |
| turns_over_budget | 4 / 24 | 5 / 24 | **1 / 24** |

```
ess-loan-ar-01            8/8 PASS
chat-handoff-write-01     8/8 PASS
payroll-followup-en-01    5/8        t2/t4/t6/t7/t8 pass at 0 LLM
                                     t1 still synthesis llm=3, misses 4500
                                     t3 misses 3700; t5 misses 800
                                     No invented 4500 / 3700 / 800
                                     t6 echoes the user-typed 2,000 as unconfirmed
```

C3, C5, C6, C8 (this slice) = 1.0. C2 = 0.625. C1 focus 0.769, under 0.95.
Goldens not edited. Night 2026-09-23 FAIL not rewritten. G5 stayed 96/96.
