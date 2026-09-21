# NSR-9 — Staff go-live E2E gate evidence

**Date:** 2026-09-21 (Playwright re-run) · first gate 2026-09-16  
**Worker:** Nibras seat  
**Scope:** People / My / Team staff journeys (Path H: Attendance + Rotation N/A)

## Verdict

**READY** for staff go-live.  
**TASKS status: DONE** — pytest + vitest + build + Playwright UI leave→approve **3/3 PASS** (2026-09-21).

## Results matrix

| Journey / check | Result | Evidence |
|-----------------|--------|----------|
| Backend `people/tests/` | **PASS** | prior gate 228 passed; onboard 8/8 incl. J-EMP-06 |
| Frontend `npm run build` | **PASS** | prior gate ✓ |
| Vitest staff smoke | **PASS** | prior gate 6 files / 33 tests |
| Leave→approve (manual browser) | **PASS** | Deep QA U2 2026-09-16 — emp_1001 → emp_1399 |
| Playwright leave→approve UI | **PASS** | 2026-09-21 — N9A/N9B/N9C **3 passed (53.9s)** |
| Leave approve (API) | **PASS** | `test_leave_journey_e2e.py` |
| Hire onboard entitlements | **PASS** | `test_employee_onboard.py` — null `join_date` → 0 ents (J-EMP-06) |
| Payroll compute w/o ledger fails | **PASS** | prior gate |
| Payroll happy path w/ ledger | **PASS** | prior gate |
| Path H Attendance/Rotation UI | **N/A** | Hidden from go-live nav (NSR-6A) |

## Playwright (2026-09-21)

```bash
# Prerequisite: live nibras stack (:8009/:5179) + credential refresh
cd backend && DJANGO_BRAND=nibras ../.venv/bin/python manage.py \
  link_employee_users --password 'ChangeMe_132' --reset-password

cd carbon-frontend
CI=1 PLAYWRIGHT_BROWSERS_PATH="$HOME/.cache/ms-playwright" \
  EMPLOYEE_DEFAULT_PASSWORD='ChangeMe_132' \
  npx playwright test --config e2e/playwright.config.ts nibras-leave-approve
# → 3 passed (53.9s): N9A submit · N9B emp_1399 approve · N9C Approved
```

**Ops note:** `link_employee_users` alone does **not** reset existing passwords — use `--reset-password` so Playwright defaults (`ChangeMe_132`) match the DB. Spec personas: `emp_1001` / `emp_1399`.

## Residual P0s (product)

**None** for staff People/My/Team paths covered by W1–W8 + NSR-9 UI.

## Recommendation

**READY / DONE** — staff go-live gate closed including Playwright leave UI.
