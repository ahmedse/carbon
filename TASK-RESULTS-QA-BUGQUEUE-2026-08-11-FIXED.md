# TASK-RESULTS-QA-BUGQUEUE-2026-08-11-FIXED — Debugger/Fixer Handoff

- **Date:** 2026-08-11
- **Role:** Debugger/Fixer
- **Source:** `TASK-RESULTS-QA-BUGQUEUE-2026-08-11.md` (QA/Validator 4-layer run)
- **Scope:** QA-F3 (P1 security), QA-F1 + QA-F2 (P1 tooling), QA-F4 (P2 docs/data), QA-F5 (P3 lint — 4 errors only)
- **Verdict per gate:** `verify.sh backend` ✅ PASSED · `verify.sh tests` ✅ PASSED (Ran 274) · `verify.sh frontend` ✅ PASSED · `verify.sh full` ❌ GATE FAILED — **solely** on pre-existing debt outside this fix's scope (see Issues Found)

---

## Summary

| # | Gate | Status | Evidence |
|---|------|--------|----------|
| 1 | QA-F3 regression red→green | ✅ | 201→403, 200→403; full `mdm.tests` 23 tests OK |
| 2 | QA-F3 live HTTP (scoped POST) | ✅ | HTTP 403 (was 201); reads still 200; admin write 201 |
| 3 | QA-F1 `verify.sh tests` runs tests | ✅ | `✓ backend tests (Ran 274 test)` |
| 4 | QA-F2 failing check → GATE FAILED | ✅ | `TEST_ARGS=mdm.tests.does_not_exist` → GATE FAILED, EXIT=1 (before: GATE PASSED, EXIT=0) |
| 5 | Full backend suite | ✅ | **274 tests OK** (was 272; +2 new) |
| 6 | QA-F4 credentials | ✅ | all 5 `alamein.*` users authenticate with documented `Alamein_2026` (live token 200) |
| 7 | QA-F5 lint errors | ✅ | 4 errors → 0 errors (62 warnings remain, noted debt) |
| 8 | Playbook | ✅ | PB-17, PB-18, PB-19, PB-20 appended |

---

## QA-F3 (P1, SECURITY) — OrgUnit write path not RBAC-scoped

### Root cause (1 line)
`OrgUnitViewSet` (`backend/mdm/views.py`) declared `permission_classes = [IsAuthenticated]` and `perform_create` accepted a client-supplied `parent` FK with **no write-time admin/scope check** — reads were scoped, writes were not.

### Fix applied
- `backend/mdm/views.py` L481 — `permission_classes = [ReadAnyWriteGlobalAdmin]` (reused the existing class at `accounts/permissions.py` L94, already imported and used by `BindFieldView` at `mdm/views.py` L383 — reuse over invent). Any authenticated user reads; only superusers / global `admins_group` (org_unit=None) write. Org-scoped admins become read-only — matches the view's own "Only admin can write" docstring contract.

### Regression test (red → green)
- `backend/mdm/tests/test_org_units.py` L326 `test_scoped_user_cannot_create_org_unit` — scoped data owner POST with out-of-scope parent (AAST) must be 403 (was 201).
- L340 `test_scoped_user_cannot_write_in_own_subtree` — in-scope PATCH must be 403 (was 200).
- **Red:** `Ran 9 tests … FAILED (failures=2)` — `AssertionError: 201 != 403`, `AssertionError: 200 != 403`.
- **Green:** `mdm.tests.test_org_units` → `Ran 23 tests … OK`.

### Live verification (running backend :8009, real JWTs)
```
POST /carbon-api/mdm/org-units/ as alamein.transport (parent:1) → HTTP 403  {"error":"PermissionDenied",...}
GET  /carbon-api/mdm/org-units/  as alamein.transport → HTTP 200  {"count":1, ... "النقل — Transportation"}
POST /carbon-api/mdm/org-units/  as ahmed (admin)      → HTTP 201  (probe row id=34, then soft-DELETE → 204)
```
Probe artifacts cleaned up (QA-Test-Org was already hard-deleted by QA; my admin probe row deleted after capture).

### Design question for Master
`ReadAnyWriteGlobalAdmin` makes **org-scoped admins read-only**. If the platform ever needs org-scoped admins to write within their own subtree, that requires a new scoped-write permission class — deliberately not invented here (minimal fix + reuse rule). The docstring ("Only admin can write") matches the global-admin gate.

---

## QA-F1 (P1, TOOLING) — `verify.sh tests` never ran tests

### Root cause
`verify.sh` ran `"$PY" manage.py test "${TEST_ARGS:-}"` — unset `TEST_ARGS` expands to a quoted empty-string argument → Django `ValueError: Empty module name` at discovery. Tests NEVER ran through the gate.

### Fix applied
- `.ai-toolkit/scripts/verify.sh` `verify_tests()` (~L57-76) — empty-safe guard: `if [ -n "${TEST_ARGS:-}" ]; then "$PY" manage.py test $TEST_ARGS; else "$PY" manage.py test; fi`, exit code captured in `rc`, same log-to-`/tmp/vt.log` + pass/fail structure preserved.

### Evidence
```
Before: verify.sh tests → ✗ backend tests + ValueError: Empty module name … GATE PASSED (EXIT=0)
After:  verify.sh tests → ✓ backend tests (Ran 274 test) … GATE PASSED (EXIT=0)
```

---

## QA-F2 (P1, TOOLING) — `verify.sh` false green (subshell FAIL loss)

### Root cause
`verify_backend`, `verify_tests`, `verify_frontend` ran inside `( cd … )` **subshells**; `fail()` set `FAIL=1` inside the subshell only — parent always saw `FAIL=0` → always `GATE PASSED`.

### Fix applied
- `.ai-toolkit/scripts/verify.sh` L42-46, L46-55, L57-76, L79-86 — hoisted the `cd` out of the subshells (each function `cd "$BACKEND_DIR"/"$FRONTEND_DIR"`, runs checks, `cd "$ROOT"` back), so `fail()` mutates the parent shell's `FAIL`. Same output format; no rewrite. Inline comment documents why (QA-F2).

### Before/After evidence (negative self-test)
```
Before (broken gate):  verify.sh tests → ✗ … GATE PASSED, EXIT=0        ← false green
After (honest gate):   TEST_ARGS=mdm.tests.does_not_exist verify.sh tests → ✗ … GATE FAILED — fix before reporting done, EXIT=1
                       verify.sh full  → GATE FAILED, EXIT=1 (pre-existing debt now surfaced — see Issues Found)
```

### Full-gate verdict + test count (as required)
```
verify.sh full →
  ✓ django check   ✓ no missing migrations   ✓ backend tests (Ran 274 test)
  ✓ lint           ✓ build
  ✓ no hardcoded secrets   ✓ no hardcoded hex in components   ✓ no naive datetime
  ✗ MUI v5 Grid syntax (DQHubPage.jsx:512 — pre-existing debt, outside scope)
  ⚠ raw fetch() (ForgotPasswordPage/ResetPasswordPage) · ⚠ 4 print() calls
  → GATE FAILED, EXIT=1
```
All domains touched by this task pass; the red items are pre-existing debt that the fixed gate now honestly reports (previously invisible).

---

## QA-F4 (P2, DOCS/DATA) — stale documented credentials

### Root cause
5 `alamein.*` dev users existed with correct roles but passwords that had drifted from the documented `Alamein_2026` (`plans/TASK-QA-ALAMEIN-VALIDATION.md`, `alamein-campus/README.md`, `ALAMEIN_TEST_JOURNEY.md`, `generate_checklist.py`). Verified in shell: `alamein.transport` / `alamein.admin` rejected `Alamein_2026`, `Transport_123`, `aast123` — all False. `transport.officer` (from `seed_aastmt_org.py`) doesn't exist in this DB (seed never run).

### Resolution
Reset all 5 existing `alamein.*` users to the documented dev password via Django shell (`u.set_password('Alamein_2026')`), verified per-user (`check_password → True`) and live:
```
POST /carbon-api/token/  {"username":"alamein.transport","password":"Alamein_2026"} → HTTP 200 (refresh+access tokens)
```
**Why this path:** project convention documents dev/test credentials in plans and seeds (`Transport_123`, `Facilities_123`, `AdminPa_132`, `demo123!`); the QA plan is meant to be runnable as-written. Docs now match reality — no doc edits needed. Dev-DB-only credential, no production impact. This is a dev user password change — flagged for the record (PB-20).

---

## QA-F5 (P3, FRONTEND — 4 lint errors only)

| File | Line | Error | Fix |
|------|------|-------|-----|
| `carbon-frontend/src/pages/admin/PlatformConfigPage.jsx` | ~64 | unused `e` in `catch (e)` | `catch {` (optional catch binding) |
| `carbon-frontend/src/pages/emissions/EmissionFactorsPage.jsx` | 38 | unused `scopeColors` | removed const (Chip uses theme tokens) |
| `carbon-frontend/src/shell/ShellSidebar.jsx` | 272 | unused `moduleSummary` destructure | destructure only `userOrgUnit` |
| `carbon-frontend/vitest.config.js` | 9 | `__dirname` no-undef (ESM) | `resolve(import.meta.dirname, '.env')` (Node v20.20.2 supports it) |

Evidence: `npm run lint` → `✖ 62 problems (0 errors, 62 warnings)`; `npx vitest run` → 321 tests pass (1 pre-existing collection failure — see Issues Found). 62 warnings left as noted debt per task instruction.

---

## Playbook entries added
- `PB-17` — OrgUnit write path not RBAC-scoped (QA-F3) · regression: 2 tests in `OrgUnitRbacScopingTestCase`
- `PB-18` — verify.sh empty-string test label (QA-F1)
- `PB-19` — verify.sh false green, subshell FAIL loss (QA-F2)
- `PB-20` — stale `alamein.*` dev credentials (QA-F4)

GOTCHAS: `GOTCHAS_FILE` (`/memories/repo/carbon-gotchas.md`) does not exist yet — no entry to update; PB entries carry the forensics.

---

## Test suite final count
```
.venv/bin/python backend/manage.py test --noinput → Found 274 test(s). … OK   (was 272; +2 QA-F3 regression)
```

## Issues Found (logged, NOT fixed — scope discipline)
1. `verify.sh full` surfaces pre-existing fail-level debt: MUI v5 `<Grid item xs={6} md={3}>` in `carbon-frontend/src/pages/catalog/DQHubPage.jsx:512` (v5→v7 `size={{}}` migration needed); raw `fetch()` in `ForgotPasswordPage.jsx` / `ResetPasswordPage.jsx`; 4 `print()` calls in backend app code. These were invisible before QA-F2's gate fix.
2. Vitest miscollects a Playwright spec: `carbon-frontend/tests/phase1-enterprise.spec.cjs` (uses `test.describe`) fails under `vitest run`. **Proven pre-existing** — identical failure with the original `vitest.config.js` (stash/pop test). 321 real tests pass.
3. `seed_aastmt_org.py` users (`transport.officer` / `Transport_123`, `facilities.officer`) don't exist in the dev DB — seed hasn't been run; `plans/TASK-QA-DEEP-MYDATA.md` references them.

## Files changed
| Action | File | Lines | What |
|--------|------|-------|------|
| MODIFY | `backend/mdm/views.py` | 481 | `OrgUnitViewSet.permission_classes` → `[ReadAnyWriteGlobalAdmin]` (QA-F3) |
| MODIFY | `backend/mdm/tests/test_org_units.py` | 326–352 | +2 regression tests (QA-F3) |
| MODIFY | `.ai-toolkit/scripts/verify.sh` | 42–86 | hoisted cd out of subshells (QA-F2) + empty TEST_ARGS guard (QA-F1) |
| MODIFY | `carbon-frontend/src/pages/admin/PlatformConfigPage.jsx` | ~64 | `catch {` (QA-F5) |
| MODIFY | `carbon-frontend/src/pages/emissions/EmissionFactorsPage.jsx` | 38 | removed unused `scopeColors` (QA-F5) |
| MODIFY | `carbon-frontend/src/shell/ShellSidebar.jsx` | 272 | destructure `userOrgUnit` only (QA-F5) |
| MODIFY | `carbon-frontend/vitest.config.js` | 9 | `import.meta.dirname` (QA-F5) |
| MODIFY | `.ai-toolkit/troubleshooting/playbook.md` | 193–228 | PB-17…PB-20 |
| CREATE | `TASK-RESULTS-QA-BUGQUEUE-2026-08-11-FIXED.md` | — | this report |

## Blockers
None. Backend was never restarted (Django auto-reload picked up `views.py`; live curl proved it).
