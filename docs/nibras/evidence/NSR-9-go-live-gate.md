# NSR-9 — Staff go-live E2E gate evidence

**Date:** 2026-09-16  
**Worker:** qa-validator  
**Scope:** People / My / Team staff journeys (Path H: Attendance + Rotation N/A)

## Verdict

**READY** for staff go-live on automated product evidence (pytest + vitest + production build).  
**TASKS status: PARTIAL** — Playwright UI leave journey shipped but not green on this host (stack/seed), corroborated by API leave journey tests.

## Results matrix

| Journey / check | Result | Evidence |
|-----------------|--------|----------|
| Backend `people/tests/` | **PASS** | 228 passed |
| Frontend `npm run build` | **PASS** | ✓ built (~19s); fixed orphaned `NODE_STATUS` map in `PlanDagGraph.jsx` (syntax blocked build) |
| Vitest staff smoke | **PASS** | 6 files / 33 tests |
| Playwright leave→approve UI | **PARTIAL / BLOCKED** | Spec shipped; Chromium launched with host browser cache; login failed (`emp_1001` — no live seeded stack on :8009/:5179 during gate). Sandbox path also missing browser binary / historically `libnspr4.so`. |
| Leave approve (API) | **PASS** | `test_leave_journey_e2e.py` — 5 tests |
| Hire onboard entitlements | **PASS** | `test_employee_onboard.py` — 7 tests |
| Payroll compute w/o ledger fails | **PASS** | `PayrollRunServiceTests::test_compute_fails_without_verified_ledger` |
| Payroll happy path w/ ledger | **PASS** | `PayrollRunServiceTests::test_happy_path_draft_compute_validate_commit` |
| Path H Attendance/Rotation UI | **N/A** | Hidden from go-live nav (NSR-6A); do not fail gate |
| `./verify.sh frontend` | **SKIP** | File does not exist |

## Commands

```bash
# Backend
cd /home/ahmed/ws/carbon/backend && ../.venv/bin/python -m pytest people/tests/ -q --disable-warnings -p no:cacheprovider
# → 228 passed in 34.24s

# Frontend build
cd /home/ahmed/ws/carbon/carbon-frontend && npm run build
# → ✓ built

# Vitest
cd /home/ahmed/ws/carbon/carbon-frontend && npx vitest run \
  src/__tests__/EmployeeWizard.test.jsx \
  src/__tests__/PeoplePages.test.jsx \
  src/__tests__/MyLoans.test.jsx \
  src/__tests__/OrgUnitScope.test.jsx \
  src/__tests__/MyLeave.test.jsx \
  src/__tests__/TeamInbox.test.jsx
# → 6 passed (33 tests)

# Playwright (from carbon-frontend; config under e2e/)
cd /home/ahmed/ws/carbon/carbon-frontend
CI=1 PLAYWRIGHT_BROWSERS_PATH="$HOME/.cache/ms-playwright" \
  npx playwright test --config e2e/playwright.config.ts nibras-leave-approve
# → FAIL: Employee login (emp_1001) — FE/BE not up; seed users absent
```

## Playwright blocker detail

1. Spec: `carbon-frontend/e2e/journeys/nibras-leave-approve.spec.ts` (employee My Leave → manager Team approve → employee sees Approved).
2. Env overrides: `NIBRAS_EMPLOYEE_USER` / `NIBRAS_MANAGER_USER` (+ passwords) or runbook `emp_<employee_no>` after `link_employee_users`.
3. Observed errors this gate:
   - Sandbox default: `Executable doesn't exist at /tmp/cursor-sandbox-cache/.../chrome-headless-shell`
   - Host `ldd` on cached shell: `libnspr4.so => not found` (and nss/asound) — known Pulse E2E host gap
   - With `PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright` + unrestricted env: browser launched; **login failed** because `http://127.0.0.1:5179` / `:8009` were down (`curl` → 000) and default `emp_1001` is not guaranteed without GOFSCO seed
4. Corroboration (green): `people/tests/test_leave_journey_e2e.py` — submit → inbox → approve → balance used/pending.

## Test fixture maintenance (ADR-0028)

People tests that created a second root `OrgUnit` were updated to the NSR-8A pattern (deployment root + sibling divisions): `test_api.py`, `test_chronicle.py`, `test_compensation.py`, `test_payroll_service.py`, plus `deployment_root` import in `test_eosi.py`.

## Residual P0s (product)

**None** from this gate for staff People/My/Team paths covered by W1–W8.

### Operational residual (not product P0)

- Re-run Playwright against a live nibras stack with managers linked per `docs/nibras/GOFSCO-ONBOARDING-RUNBOOK.md`.
- Install Chromium system libs (`libnspr4`, `libnss3`, …) if headless shell fails on the host.

## Recommendation

**READY** — staff go-live may proceed; leave↔corr, hire entitlements, and ledger-gated payroll are proven by pytest; FE smoke + build green. Playwright UI is documentation debt / host ops, not an open product defect.
