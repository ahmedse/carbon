# PV2 live 3-script — 2026-09-23d (after F-LIVE-10)

**Host:** `emp_1067` · **DB:** `nibras_dev` · **Mode:** Chat only  
**Command:** `python -m ai.eval.multiturn.runner --scripts 'scripts/0[148]-*.yaml' --live --host-user emp_1067 --no-isolated-db`  
**Raw:** `docs/pulse/evidence/PV2-live-recheck-2026-09-23d.json`  
**Elapsed:** 129 s · exit 0

This process started before the 4B default flip. It measures F-LIVE-10, not Arbiter-on.

| | 2026-09-23 morning | 23d |
|---|---|---|
| turns_passed | 13 / 24 | **16 / 24** |
| scripts_passed | 0 / 3 | **1 / 3** (`chat-handoff-write-01`) |
| router_agreement | 0.667 | **0.833** |
| slot_carry_over | 1.0 | 1.0 |
| language_fidelity | 1.0 | 1.0 |
| llm p50 / max | 2 / 5 | **2 / 3** |
| turns_over_budget | 5 / 24 | 7 / 24 |

```
ess-loan-ar-01            7/8   t7 thanks = answer llm=0 (F-LIVE-10). t2 mentions + budget.
chat-handoff-write-01     8/8   PASS. t8 thanks = answer llm=0.
payroll-followup-en-01    1/8   t4 only. Still no 4500. tool_answer on t1/t2/t5.
```

C5 1.0 · C6 1.0 · C2 0.125. Goldens not edited. Night 2026-09-23 FAIL not rewritten.
