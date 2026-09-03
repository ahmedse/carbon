# QA Framework — 4-Layer Validation Model

**Purpose:** The single source of truth for how QA/Validator runs checks, classifies
severity, and produces evidence. Every QA task plan (`TASK-QA-*`) and every QA report
(`TASK-RESULT-QA-*`) follows this model.

---

## The 4-Layer Model

Validation always proceeds L1 → L4. If L1 fails hard, fix/flag before continuing.

### LAYER 1 — Structural Gate
Static health of the codebase before any behavioral validation.

```bash
./.ai-toolkit/scripts/verify.sh full     # django check, backend tests, frontend lint/build, antipatterns
cd carbon-frontend && npm run build      # clean build, 0 new errors
```

| Check | Tool | Expected |
|-------|------|----------|
| django check | `verify.sh backend` | `GATE PASSED` |
| no missing migrations | `verify.sh backend` | `GATE PASSED` |
| backend tests | `verify.sh tests` | OK (note: test DB first build takes minutes) |
| frontend lint | `verify.sh frontend` | 0 new errors |
| frontend build | `npm run build` | Clean build |
| anti-patterns | `verify.sh antipatterns` | No hardcoded secrets / naive datetimes |

### LAYER 2 — Security (API-Level RBAC)
Behavioral security checks at the HTTP layer, always with real JWTs.

| Check | Method | Expected |
|-------|--------|----------|
| Unauthenticated → 401 | `curl` no token, any protected endpoint | `HTTP 401` |
| Admin read | admin JWT → GET | `HTTP 200` |
| Admin write | admin JWT → POST/PATCH/DELETE | `HTTP 2xx` |
| Scoped user read | scoped JWT → list | Only own subtree/module set |
| Scoped user write out-of-scope | scoped JWT → write to other org | `HTTP 403` (or 404) |
| Cross-org isolation | two data owners | No data overlap |

**RBAC source of truth:** `get_visible_org_units(user)` and `get_allowed_module_ids(user)`
in `backend/accounts/rbac_utils.py`. Global admins + global visibility-role holders see
everything; no-role users see nothing (restrictive default).

### LAYER 3 — Functional (API behavior vs spec)
Every endpoint in the task spec: method, status code, response shape, pagination,
filtering, soft-delete, error format. One row per check, marked ✅ / ❌ / ⚠.

Pagination gotcha: DRF list endpoints return `{count, page_size, page, results}` when
pagination is active — validate `results`, never assume a bare list.

### LAYER 4 — UX / Browser Audit
Per page × per role, the 10-point checklist — validated **against the Screen Spec**
(`shared/frontend-ready.md`): every state in the view's state matrix must render correctly,
not just the happy path (loading/empty/error/forbidden/partial/stale + disabled/submitting/optimistic/selected).

| # | Check | Expected |
|---|-------|----------|
| W1 | RENDER | No console errors |
| W2 | LOADING | Skeleton/spinner while fetching |
| W3 | EMPTY | Sensible empty state |
| W4 | ERROR | Friendly error message, no crash |
| W5 | DARK_MODE | Toggle works, theme applies |
| W6 | BREADCRUMB | Present + correct |
| W7 | TITLE | Page-specific `document.title` (not platform default) |
| W8 | RESPONSIVE | Adapts at 768px |
| W9 | KEYBOARD | Focus visible, logical tab order |
| W10 | NO_404_LINKS | No broken internal links |

---

## Evidence Standards

1. Every finding: exact reproduction steps (URL, method, body, role).
2. Every API check: `HTTP <code>` from curl with a real JWT.
3. Before/after evidence for any state-changing check.
4. Classify each finding: **runtime bug** vs **documentation mismatch** vs **test fragility**.

## Severity Classification

| Severity | Meaning | Example |
|----------|---------|---------|
| **P0** | Critical — blocks deployment / data loss / security hole | Auth bypass, migration failure, 500 on core endpoint |
| **P1** | High — core feature broken, wrong data exposed | RBAC leak, wrong totals, broken write path |
| **P2** | Medium — works but wrong behavior or documented mismatch | 404 on documented endpoint, wrong doc param |
| **P3** | Low — polish, cosmetic, non-blocking debt | Missing page title, no breadcrumb, hardcoded colors |

## Output Format (TASK-RESULTS-*)

```
# TASK-RESULTS-<ID> — QA Validation Report
Date / Role / Model / Phase / Source

## Executive Summary      (verdict + issue counts by severity)
## Layer 1: Structural Gate Results
## Layer 2: Security (API-Level RBAC)
## Layer 3: Functional
## Layer 4: UX / Browser Audit
## Findings               (ID | severity | symptom | evidence | suggested owner)
## Gate Verdict           (PASSED / PASSED WITH FINDINGS / FAILED + defect handoff list)
```

Verdict rules:
- Any P0 → **FAILED** (blocking).
- P1 findings → **PASSED WITH FINDINGS**.
- Only P2/P3 → **PASSED WITH FINDINGS** (list them).
- Clean → **PASSED**.

## QA ↔ Debugger/Fixer Handoff

The QA/Validator does NOT fix code. Findings are handed to the Debugger/Fixer, which:
1. Writes a regression test FIRST (red → green, `shared/testing.md` RULE 1).
2. Applies the minimal fix.
3. Runs `verify.sh` + `manage.sh test`.
4. Appends a `PB-NN` entry to `troubleshooting/playbook.md`.
