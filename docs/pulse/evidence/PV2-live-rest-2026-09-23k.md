# PV2 live rest-bank — 2026-09-23k

**Host:** `emp_1067` · **DB:** `nibras_dev` · **Mode:** Chat only  
**Scripts:** `0[235679]` (the six not in the 01/04/08 slice)  
**Raw:** `docs/pulse/evidence/PV2-live-rest-2026-09-23k.json`

G5 offline on the full 12-script stub bank stayed **96/96**.

| | rest live |
|---|---|
| turns_passed | 33 / 48 |
| scripts_passed | 2 / 6 |
| router_agreement | 0.958 |
| focus_retention | 0.885 |
| llm p50 / max | 2 / 6 |
| turns_over_budget | 12 / 48 |

```
ess-leave-en-01           6/8  t2 llm=3; t3 tool_answer llm=5
ess-attendance-mixed-01   6/8  t1–t2 llm=3
entity-focus-switch-01    8/8 PASS
grounded-recall-01        3/8  Engineering not in digest; t2 llm=6
plan-status-01            8/8 PASS
language-fidelity-ar-01   2/8  t4–t5 lang=en; several llm=3
```

This is not the 01/04/08 C2 slice. Goldens not edited. Night 2026-09-23 FAIL
not rewritten. 6B not run (mutating; needs STACK-HOLD).
