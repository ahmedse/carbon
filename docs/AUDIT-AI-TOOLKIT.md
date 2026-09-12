# AUDIT — `.ai-toolkit` (Master Architect)

Date: 2026-09-12
Scope: `/home/ahmed/ws/carbon/.ai-toolkit/`
Trigger: fix stale `WORKSPACE_ROOT` + full toolkit audit.

---

## 1. Executive summary

The toolkit was **structurally broken** in four independent ways, only one of which
(the stale path) was visible to the user. All four were fixed or root-caused.

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | Stale `WORKSPACE_ROOT` `/home/ahmed/aast/carbon` | Critical (visible) | ✅ Fixed |
| 2 | Dangling symlinks (`frameworks/`, `patterns/`, `scripts/`, `universal/`) → deleted central `~/ai-toolkit/` | Critical (silent) | ✅ Fixed |
| 3 | Missing auto-generated `registry/` | High (silent) | ✅ Fixed |
| 4 | CRLF corruption in 74 toolkit files broke `scan.sh` | High (silent) | ✅ Fixed |
| 5 | Referenced scripts that were never created | Medium (drift) | ⚠️ Documented |

---

## 2. Root causes

### 2.1 Stale path (visible bug)
`project.config.md`, `roles/researcher.md`, `shared/testing.md` still referenced the
old checkout `/home/ahmed/aast/carbon`. Fixed to `/home/ahmed/ws/carbon`.

### 2.2 "Selective symlink" architecture collapsed
`frameworks/`, `patterns/`, `scripts/`, `universal/` are committed as **git symlinks**
(mode `120000`) pointing at a central `~/ai-toolkit/` "shared brain". That central
directory was deleted at some point, leaving every pointer dangling.

Two compounding factors:
- `git config core.symlinks=false` on this machine → symlinks checkout as **regular
  files containing the target path string**, so they can't resolve even if the target
  is recreated.
- Only `frameworks/patterns/scripts/universal` were symlinked; `roles/`, `shared/`,
  `project.config.md` etc. were already local. This "split-brain" design is fragile.

### 2.3 CRLF corruption silently broke `scan.sh`
74 toolkit files had CRLF line endings. `scan.sh`'s `cfg()` helper strips comments but
**not carriage returns**, so `BACKEND_DIR` resolved to `…/backend/\r`. The `[ -d ]`
test failed silently and the registry was generated empty.

### 2.4 Missing registry
`registry/` is gitignored and auto-generated. It was absent because `scan.sh` was
silently failing (see 2.3).

---

## 3. Repairs applied

1. **Path fix** — `sed` replaced all `/home/ahmed/aast/carbon` → `/home/ahmed/ws/carbon`
   across the three files. Verified: no stale paths remain.
2. **Scripts restored** — 6 scripts (`activate.sh`, `guard.sh`, `new-task.sh`,
   `retro.sh`, `scan.sh`, `verify.sh`) recovered from git history (`e3aab4c^`).
   Verified byte-identical to the central source.
3. **Symlinks flattened** — replaced dangling symlinks with real directories sourced
   from the central repo (`github.com/ahmedse/ai-toolkit`):
   - `frameworks/{django,fastapi}.md`
   - `patterns/{README,index}.md`
   - `universal/` (7 files incl. `protocols/`, `rules/`)
   - added `onboarding.sh`, `promote.sh` to `scripts/` (total 8)
4. **CRLF cleanup** — stripped `\r` from all toolkit text files. Verified 0 remaining
   (outside auto-generated `registry/`).
5. **Registry regenerated** — `scan.sh` now produces populated output
   (`api.md` 486 lines, `models.md`, `services.md`, `components.md`, `config-keys.md`).

---

## 4. Remaining gaps (documentation/implementation drift)

These are referenced by docs but do **not** exist in carbon history or the central
repo — they were documented ahead of (or instead of) implementation:

| Reference | Referenced from | Reality |
|-----------|-----------------|---------|
| `scripts/audit-routes.py` | `project.config.md` RULE_22 | Does not exist anywhere |
| `scripts/audit-imports.sh` | docs | Does not exist anywhere |
| `scripts/verify-intelligence.sh` | `testing.md` RULE_8 (`verify.sh intelligence`) | Does not exist; recovered `verify.sh` supports only `backend\|frontend\|tests\|antipatterns\|all\|full` |
| `universal/rules/model-serving-boundary.md` | `base-rules.md`, `model-serving-runbook.md` | Does not exist in central repo |
| `scripts/check-i18n-keys.js` | docs | **Exists** at `carbon-frontend/scripts/check-i18n-keys.js` (docs path is wrong) |

`check-i18n-keys.js` is a path mismatch only — the others must be re-authored (or the
references removed) as a follow-up. No stubs were created (anti-thin-implementation).

---

## 5. Recommendations

1. **De-symlink permanently** (done here) — the "shared brain" symlink design is
   incompatible with `core.symlinks=false` and single-machine deletion. Keep the
   toolkit self-contained.
2. **Recreate central `~/ai-toolkit`** only if other projects (`gigacast`) still
   depend on it. Source: `git clone https://github.com/ahmedse/ai-toolkit.git`.
3. **Fix repo-wide CRLF** — `backend/**/*.py` (and ~2040 other files) still carry CRLF.
   This is why `registry/` regenerates with CRLF. Add `* text=auto eol=lf` enforcement
   via `git add --renormalize`.
4. **Reconcile drift** — either implement `audit-routes.py`, `audit-imports.sh`,
   `verify-intelligence.sh`, `model-serving-boundary.md` or remove their references.
   Fix the `check-i18n-keys.js` path in docs.

---

## 6. Validation

- ✅ `scan.sh` → populated registry (486-line `api.md`)
- ✅ All 8 scripts pass `bash -n`
- ✅ No stale paths (`grep -r aast` → none)
- ✅ No CRLF in `.ai-toolkit` (except auto-generated `registry/`)
- ✅ `frameworks/django.md`, `patterns/index.md`, `universal/handoff.md` all resolve
- ⚠️ 5 referenced-but-missing items documented (section 4)
