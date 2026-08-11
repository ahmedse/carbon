# TASK-RESULTS-QA-BUGQUEUE-2026-08-11 — QA Validation Report

- **Date:** 2026-08-11
- **Role:** QA/Validator (DeepSeek-V3)
- **Scope:** Independent 4-layer validation of bug-queue closeouts (BUG-03, BUG-04, BUG-06, swagger 500 fix, connections test fixes) + pending BUG-05 + verify.sh tooling integrity
- **Method:** QA Framework 4-layer model (`.ai-toolkit/shared/qa-framework.md`)

---

## Executive Summary

| Area | Verdict |
|---|---|
| L1 Structural Gate | ⚠️ PASSED WITH FINDINGS — 2 tooling defects in `verify.sh` make the gate a **false green** |
| L2 Security/RBAC | 🔴 **1 P1 write-path RBAC leak** (org-units CREATE not scoped); read isolation verified ✅ |
| L3 Functional | ✅ BUG-04, BUG-06, swagger, connections all verified live; BUG-05 doc mismatch confirmed |
| L4 UX/Browser | ✅ Renders, breadcrumb, title, dark mode all work; only React Router v7 future-flag warnings |

**Verdict: PASSED WITH FINDINGS** (3×P1 handed to Debugger/Fixer — see Findings)

The Debugger/Fixer's claimed fixes (BUG-03, BUG-04, BUG-06, swagger, connections) are **verified REAL** at the HTTP layer with live JWTs, plus standalone GREEN test runs. Two new P1 defects surfaced in the verification itself.

---

## Layer 1: Structural Gate Results

| Check | Result | Evidence |
|---|---|---|
| django check | ✅ | `verify.sh backend` → GATE PASSED |
| no missing migrations | ✅ | `verify.sh backend` → GATE PASSED |
| backend tests (direct) | ✅ **272 tests OK** (61.8s) | `.venv/bin/python backend/manage.py test` → `OK` |
| backend tests (via gate) | 🔴 **NEVER RUNS** | `verify.sh tests` → `ValueError: Empty module name` (see QA-F1) |
| frontend lint | ⚠️ 4 errors / 62 warnings | see QA-F5 |
| frontend build | ✅ clean build 16.28s | `npm run build` → `✓ built` (chunk-size warnings only) |
| anti-patterns | (not run via full — gate broken) | — |

### L1 Findings

**QA-F1 (P1) — `verify.sh tests` never runs tests: empty-string label**
- Reproduction: `./.ai-toolkit/scripts/verify.sh tests` → `✗ backend tests` + traceback
  `ValueError: Empty module name` (Django `import_module('')`).
- Root cause: `verify.sh:58` runs `manage.py test "${TEST_ARGS:-}"`. When `TEST_ARGS`
  is unset, the quoted expansion still passes an **empty-string argument**, and Django
  rejects `test ""` at discovery.
- Proven: `.venv/bin/python manage.py test ""` reproduces the identical traceback;
  `manage.py test` (no args) runs 272 tests OK.
- Fix owner: Debugger/Fixer — change to `manage.py test $TEST_ARGS` (unquoted, empty-safe)
  or `TEST_ARGS=${TEST_ARGS:+-} ...` guard.

**QA-F2 (P1) — `verify.sh` is a false green: subshell `fail()` never propagates**
- Reproduction: `verify.sh tests` printed `✗ backend tests` **and then** `GATE PASSED`.
- Root cause: `verify_backend`, `verify_tests`, `verify_frontend` all run inside
  `( cd ... )` subshells; the `fail()` helper sets `FAIL=1` **inside the subshell**,
  which does not propagate to the parent — so the final verdict is computed from the
  parent's still-zero `FAIL`. Any failing check is masked.
- Impact: every prior `verify.sh GATE PASSED` for backend/frontend/tests is untrustworthy.
- Fix owner: Debugger/Fixer — hoist the check functions out of subshells (use
  `cd "$BACKEND_DIR"` + `cd -`/pushd-popd) or pass exit codes up; add a regression check
  that a deliberately failing check yields `GATE FAILED`.

---

## Layer 2: Security (API-Level RBAC)

Live probes, real JWTs, `http://localhost:8009`.

| Check | Result | Evidence |
|---|---|---|
| Unauthenticated → 401 | ✅ | `GET /carbon-api/mdm/org-units/` no token → `HTTP 401` |
| Admin read | ✅ | `ahmed` JWT → 27 orgs (full visibility) |
| Scoped read (BUG-03) | ✅ | `alamein.transport` JWT → **exactly 1 org** (`النقل — Transportation`) |
| Cross-org read isolation | ✅ | `get_visible_org_units`: transport=1, finance=1, alamein.admin=6 (Campus subtree), ahmed=27 |
| Scoped PATCH out-of-scope | ✅ | PATCH `/mdm/org-units/2/` as transport → `HTTP 404` (queryset-scoped via `get_object`) |
| Scoped DELETE out-of-scope | ✅ | DELETE `/mdm/org-units/2/` as transport → `HTTP 404` |
| **Scoped CREATE out-of-scope** | 🔴 | **POST `/mdm/org-units/` with `parent: 1` (AAST) as transport → `HTTP 201` created** (see QA-F3) |

### L2 Findings

**QA-F3 (P1) — OrgUnit write path is not RBAC-scoped (admin-only claim not enforced)**
- Reproduction: as `alamein.transport` (data owner scoped to Transportation only):
  ```bash
  curl -X POST http://localhost:8009/carbon-api/mdm/org-units/ \
    -H "Authorization: Bearer <transport-jwt>" -H "Content-Type: application/json" \
    -d '{"name":"QA-Test-Org","parent":1,"org_type":"campus"}'
  # → HTTP 201 {"id":33, ... "full_path":"AAST / QA-Test-Org"}
  ```
- Root cause: `OrgUnitViewSet` (`backend/mdm/views.py:465`) declares
  `permission_classes = [IsAuthenticated]` and its docstring says "Only admin can write",
  but **no admin/permission check exists** in `perform_create` (or update/destroy).
  The `parent` FK is accepted from the client with no scope validation.
  (Note: `get_object()` in PATCH/DELETE is scoped via `get_queryset()`, which is why
  only CREATE is exploitable — but the "admin only" contract is still unenforced.)
- Probe artifact cleaned up: `QA-Test-Org` (id=33) hard-deleted after capture.
- Fix owner: Debugger/Fixer — enforce admin/`CanManageReferenceValues`-style permission
  on write methods (or validate `parent` against `get_visible_org_units` in
  `perform_create`), with a regression test (scoped user POST out-of-scope parent → 403).

---

## Layer 3: Functional (API behavior vs spec)

| Check | Result | Evidence |
|---|---|---|
| BUG-04 list-level tree (admin) | ✅ | `GET /carbon-api/mdm/org-units/tree/` → roots `[AAST, AASTMT, ENG2..ENG5]`, nested `children` (AAST → Smart Village, Alamein Campus…) |
| BUG-04 list-level tree (scoped) | ✅ | As transport → `[{"name":"النقل — Transportation"}]` (HTTP 200) |
| BUG-04 regression tests | ✅ | `OrgUnitRbacScopingTestCase` → 7 tests OK standalone |
| Swagger UI (swagger 500 fix) | ✅ | `GET /carbon-api/swagger/` → HTTP 200 (15,699 bytes, renders). Schema JSON is embedded inline (no standalone `/swagger.json` path — by design, only UI mounted) |
| BUG-06 evidence pagination | ✅ | `GET /carbon-api/evidence/?page=1` → paginated dict `{count, page_size, page, results, total_pages, next, previous}` |
| BUG-06 regression tests | ✅ | `evidence.tests.test_evidence_api` alone → 18 tests OK (previously failed alone — fix confirmed) |
| Connections secret masking | ✅ | `GET /carbon-api/connections/sources/` → 2 sources, **no** `password/secret/api_key/token` fields present |
| Connections + mdm + swagger tests | ✅ | 4 fixed modules together → **46 tests OK** standalone |
| **BUG-05** `?format=pdf` | ✅ (confirmed) | `GET /carbon-api/carbon/report/?format=pdf` → `HTTP 404` (DRF format-suffix conflict) |
| **BUG-05** `?output_format=pdf` | ✅ (confirmed) | `GET /carbon-api/carbon/report/?output_format=pdf&year=2025` → `HTTP 200` JSON report |
| **BUG-05** endpoint path | ⚠️ note | Actual path is `/carbon-api/carbon/report/` (**not** `/emissions/report/`); doc fix should use this path |

### L3 Notes
- BUG-05 conclusion: the doc fix (B1.11 row → `?output_format=pdf`) is **correct**; the
  view already accepts both params (`views.py:844`), the 404 is DRF format-suffix
  routing colliding with `?format=`. Doc-only change needed, plus correcting the URL
  prefix in the plan if it says `/emissions/`.
- Evidence list count=1 (admin) — data present, pagination shape verified.

---

## Layer 4: UX / Browser Audit (spot-check)

Admin role, `http://localhost:5179/carbon/`, Org Units page + login + platform home.

| # | Check | Result | Evidence |
|---|---|---|---|
| W1 | RENDER | ✅ | No console errors (only React Router v7 future-flag warnings) |
| W2 | LOADING | ✅ | Spinner on login submit; top progressbar on route change |
| W3 | EMPTY | ⚠️ not exercised (data present) | n/a |
| W4 | ERROR | ✅ | Unknown route → dedicated "Page Not Found" page (graceful) |
| W5 | DARK_MODE | ✅ | Toggle → body bg `rgb(9,9,11)` (zinc-950), button flips to "Light mode" |
| W6 | BREADCRUMB | ✅ | Home › Admin › Organisation Units (single source `shell/Breadcrumbs.jsx`) |
| W7 | TITLE | ✅ | "Org Units — Carbon Data Trust", "Platform — Carbon Data Trust", "Sign In — Carbon Data Trust" |
| W8 | RESPONSIVE | ⚠️ not exercised | n/a |
| W9 | KEYBOARD | ⚠️ not exercised | n/a |
| W10 | NO_404_LINKS | ✅ | Nav links resolve; intentional 404 route handled by NotFound |

### L4 Notes
- React Router v7 future-flag warnings (2 console warnings) — cosmetic, non-blocking (P3).

---

## Findings Summary

| ID | Severity | Area | Finding | Owner |
|----|----------|------|---------|-------|
| QA-F1 | **P1** | Tooling | `verify.sh tests` passes empty-string label → tests never run (`ValueError: Empty module name`) | Debugger/Fixer |
| QA-F2 | **P1** | Tooling | `verify.sh` false green — `fail()` in subshell doesn't propagate → gate always says PASSED | Debugger/Fixer |
| QA-F3 | **P1** | Security | OrgUnit CREATE not RBAC-scoped — scoped data owner created org under AAST (HTTP 201) despite "admin only" contract | Debugger/Fixer |
| QA-F4 | P2 | Docs | QA plan `TASK-QA-ALAMEIN-VALIDATION.md` documents `alamein.transport`/`Alamein_2026` — live login fails (both documented passwords 401) | Debugger/Fixer (reset or fix docs) |
| QA-F5 | P3 | Frontend | Lint: 4 errors (unused vars in `PlatformConfigPage.jsx`, `EmissionFactorsPage.jsx`, `ShellSidebar.jsx`; `__dirname` in `vitest.config.js`) + 62 warnings | Frontend Worker |
| QA-F6 | P3 | Frontend | React Router v7 future-flag console warnings (2) | Frontend Worker |

---

## Gate Verdict

**PASSED WITH FINDINGS**

Verified-good from this run (hand back to Master as closed):
- ✅ BUG-03 (org-units read scoping) — live HTTP + tests
- ✅ BUG-04 (list-level tree endpoint) — live HTTP + tests + swagger docs
- ✅ BUG-06 (evidence pagination test fragility) — alone-GREEN proof
- ✅ Swagger 500 fix — UI 200
- ✅ Connections secret masking + test fixes
- ✅ BUG-05 root cause confirmed (doc-only fix direction validated)

Handed to Debugger/Fixer (fix order):
1. **QA-F3 (P1, security)** — org-units write RBAC. Most urgent: live 201-by-scoped-user.
2. **QA-F1 + QA-F2 (P1, tooling)** — make `verify.sh` honest (empty-label guard +
   subshell FAIL propagation + a negative-test that a failing check → GATE FAILED).
3. QA-F4 (P2) — reset `alamein.transport` password or fix QA plan creds.
4. QA-F5/F6 (P3) — frontend lint debt, future-flag warnings.

Every fix ships a regression test (RULE_11) and a playbook PB-NN entry.
