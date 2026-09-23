# PV2 payroll live — 2026-09-23c (after empty-payslip 200)

`--live --host-user emp_1067 --no-isolated-db` · `payroll-followup-en-01` · 66 s.

```
turns 1/8 (was 0/8)   router 0.50 (was 0.125)   language 1.0
llm p50 3   llm max 3 (was 5)   over 6/8
```

t1: `list_my_payslips` → honest empty: “I checked your payslip records, but no payslips were found.” No 403-twin. Goldens still want 4500 / 3700 / 800 / 2000. Those figures are not in emp_1067 committed `PayslipLine` rows. Goldens not loosened.

t4 pass (GOSI-correctness answer without inventing a number).
