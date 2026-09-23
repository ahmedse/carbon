# PV2 live 3-script — 2026-09-23k

**Host:** `emp_1067` · **DB:** `nibras_dev` · **Mode:** Chat only  
**Elapsed:** ~48 s · exit 0  
**Raw:** `docs/pulse/evidence/PV2-live-recheck-2026-09-23k.json`  
In-process runner. `:8009` was already listening and was not restarted.

Human override: `seed_pulse_audit_payslips` wrote last-month (2026-08) committed
lines for emp_1067 only:

| line | amount |
|---|---|
| gross | 6500 |
| gosi | 1200 |
| loan_installment | 800 |
| net | 4500 |

Identity: `net = gross − gosi − loan_installment`. After GOSI, before loan:
`6500 − 1200 = 5300`. The bank golden that wants **3700** is not this identity
(`4500 − 800`). Pulse did not invent 3700. Goldens were not edited.

| | 23i | **23k** |
|---|---|---|
| turns_passed | 21 / 24 | **23 / 24** |
| scripts_passed | 2 / 3 | **2 / 3** |
| router_agreement | 1.0 | **1.0** |
| focus_retention | 0.769 | **0.923** |
| llm p50 / max | 0 / 2 | **0 / 2** |
| turns_over_budget | 0 / 24 | **0 / 24** |
| C2 | 0.625 | **0.875** |

```
ess-loan-ar-01            8/8 PASS
chat-handoff-write-01     8/8 PASS
payroll-followup-en-01    7/8        t1 4500 from host (2 LLM)
                                     t2–t8 0-LLM from digest
                                     t3 FAIL: mentions 5300, golden wants 3700
```

C8 must (≤2 LLM on this slice) holds. C8 goal (p50 ≤ 4 s histogram CI) is
not proven. Night 2026-09-23 FAIL not rewritten.
