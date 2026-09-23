# PV2-6B — Nightly live ESS smoke soak

Chat → Agent → Approve as `emp_1067` (leave, loan, attendance).
Required: **5** consecutive live PASS nights.
Dry-run / SKIP / FAIL do not count. Do not back-date rows.

Streak: **0/5**. Soak complete: **False**.

Job landed 2026-09-23. First mutating night needs STACK-HOLD + human approval
(`PULSE_NIGHTLY_LIVE=1 --live --i-have-stack-hold --host-user emp_1067`).

```
cd backend && PULSE_NIGHTLY_LIVE=1 ../.venv/bin/python -m ai.eval.nightly_ess_smoke \
  --live --i-have-stack-hold --host-user emp_1067 --record
```

| Night | Status | Leave | Loan | Attendance | Notes |
|---|---|---|---|---|---|
| — | no live nights yet | — | — | — | SOAKING |
