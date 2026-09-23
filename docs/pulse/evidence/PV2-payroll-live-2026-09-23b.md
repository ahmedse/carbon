# PV2 payroll live re-measure — 2026-09-23b

`--live --host-user emp_1067 --no-isolated-db` · script `payroll-followup-en-01` only · Chat · 97 s.

```
turns_passed 0/8   router 0.125   language 1.0   focus 0.2
llm p50 3   llm max 5   over_budget 5/8
C1 0.0   C2 0.0
```

Intent now lands `list_my_payslips` (conf 0.92–0.95) on net pay / take-home. That is the F-LIVE-9 routing fix.

Execute still fails: `call_host_api` returns the 403-twin message (“I can only read your own records … list_my_payslips”) even after intent named that twin. Draft then says “general payroll guidance, not your actual payslips.” t5 did list **loans** (draft 2000 / emergency 5000). Goldens still want 4500 / 3700 / 800 / 2000. Goldens not loosened.

Remaining hole is host execute of `list_my_payslips` / `people/me/payslips/` for emp_1067, not intent routing.
