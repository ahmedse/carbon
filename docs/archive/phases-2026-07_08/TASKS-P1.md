# TASKS-P1.md — Phase 1: Quick Wins & Foundation Cleanup
# Master Architect → Backend Worker | Date: 2026-07-31
# Role: Backend Worker | Model: DeepSeek | Budget: ~15K tokens

---

## Architecture Context (READ FIRST)

```
DATA TRUST PLATFORM (foundation — these apps serve ALL domain apps)
  accounts/      RBAC, auth, scoped roles, PlatformAppConfig
  catalog/       Data domains, glossary, tags, assets, governance
  dataschema/    Metadata-driven schema engine (tables, fields, rows)
  mdm/           Reference data (reference sets, values, org units)
  dq/            Data quality profiling, rules, results
  connections/   Data sources, consuming connections
  evidence/      File evidence uploads
  importexport/  Import/export jobs
  core/          Modules, feedback

CARBON DOMAIN APP (tenant — sits ON TOP of platform, NEVER imported by platform)
  emissions/     GHG accounting, calculations, factors, targets, reports

RULE: Platform apps NEVER import from emissions/. Carbon imports from platform.
```

## What This Phase Does

5 low-risk, high-ROI cleanup tasks. Each is independent. No models change.
No views change. Pure audit + registration + config.

---

## G1 — Register PlatformAppConfig in Django Admin

**Why:** Model exists at `accounts/models.py:101`, serializer + view work,
but it's NOT registered in `accounts/admin.py`. Admins can't manage app
enable/disable via Django admin.

**File to edit:** `backend/accounts/admin.py`

**What to do:**
1. Add `from .models import User, ScopedRole, RoleAssignmentAuditLog, PlatformAppConfig` (add `PlatformAppConfig` to existing import)
2. Add an `@admin.register(PlatformAppConfig)` class with:
   - `list_display = ['app_id', 'is_enabled', 'display_order', 'updated_at', 'updated_by']`
   - `list_filter = ['is_enabled']`
   - `search_fields = ['app_id']`
   - `list_editable = ['is_enabled', 'display_order']` (inline editing)
   - `ordering = ['display_order', 'app_id']`
3. Follow the exact same pattern/style as the existing `ScopedRoleAdmin` class

**DO NOT TOUCH:** `accounts/models.py`, `accounts/views.py`, `accounts/serializers.py`, `accounts/urls.py`

---

## G2 — Audit and Remove Unused ML Dependencies

**Why:** 10 ML packages in `requirements.txt`. `ai_copilot` was deleted.
If no code imports them, they're dead weight.

**What to do:**
1. Grep the ENTIRE `backend/` directory for imports of each package:
   ```
   sklearn, xgboost, lightgbm, shap, scipy, matplotlib, seaborn, numpy, pandas, joblib, scikit-learn
   ```
   Use: `grep -rn "import sklearn\|from sklearn\|import xgboost\|from xgboost\|import lightgbm\|from lightgbm\|import shap\|from shap\|import scipy\|from scipy" backend/ --include="*.py" | grep -v migrations | grep -v __pycache__`
2. For EACH package, document in TASK-RESULTS.md:
   - Package name
   - Found imports? (yes + file paths, or "NO IMPORTS FOUND")
3. If a package has ZERO imports anywhere: remove it from `backend/requirements.txt`
4. **DO NOT** run `pip uninstall` — only edit `requirements.txt`

**Special handling:**
- `numpy` and `pandas` — these are used by `emissions/services.py` (Decimal/Sum operations, data manipulation). Keep them.
- `joblib` — check if serialization is used. If `import joblib` found nowhere, remove.

**DO NOT TOUCH:** any `.py` files, only `requirements.txt`

---

## G3 — Audit and Remove Unused Non-ML Dependencies

**Why:** `SQLAlchemy`, `alembic`, `hijri-converter`, `GitPython` — unclear if used.

**What to do:**
1. Grep for direct imports (NOT Django ORM which uses SQL under the hood):
   ```
   grep -rn "import sqlalchemy\|from sqlalchemy" backend/ --include="*.py" | grep -v migrations
   grep -rn "import alembic\|from alembic" backend/ --include="*.py"
   grep -rn "import hijri\|from hijri" backend/ --include="*.py" | grep -v migrations
   grep -rn "import git\|from git" backend/ --include="*.py" | grep -v migrations
   ```
2. For each: document findings. If zero imports → remove from `requirements.txt`.
3. `SQLAlchemy` / `alembic`: If found imported, document WHY (dual ORM?). If not found, remove.

**DO NOT TOUCH:** any `.py` files

---

## G4 — Remove Stale References to `seed_ai_knowledge` and `backend/assets`

**Why:** These appeared in workspace listings but don't exist on disk.
Any lingering references in docs/scripts are dead.

**What to do:**
1. Grep across the ENTIRE repo (including .md, .sh, .py, .txt, .json):
   ```
   grep -rn "seed_ai_knowledge\|ai_knowledge" . --include="*.py" --include="*.md" --include="*.sh" --include="*.txt" --include="*.json" 2>/dev/null | grep -v ".git/" | grep -v "node_modules/" | grep -v "dist/" | grep -v "__pycache__"
   ```
2. Grep for `backend/assets` references:
   ```
   grep -rn "backend/assets\|assets/" . --include="*.md" --include="*.sh" --include="*.txt" 2>/dev/null | grep -v ".git/" | grep -v "node_modules/"
   ```
3. Document all findings in TASK-RESULTS.md
4. **DELETE** any stale references (edit the files to remove those lines)
5. **DO NOT** delete actual asset files or directories — only references

---

## G5 — Verify project.config.md is Current

**Why:** `project.config.md` was just updated (2026-07-31). Audit it for accuracy.

**What to do:**
1. Read `.ai-toolkit/project.config.md`
2. Verify each claim against reality:
   - `BACKEND_VECTOR` says "unused — ai_copilot removed" — correct
   - `BACKEND_DIR="backend"` — correct
   - `FRONTEND_DIR="carbon-frontend"` — correct
   - `API_PREFIX="/carbon-api/"` — verify in `backend/config/settings.py` (grep API_PREFIX)
   - `FRONTEND_BASENAME="/carbon/"` — verify in `carbon-frontend/src/App.jsx` (grep basename)
   - `PYTHON_VERSION="3.12.13"` — verify: `python3 --version`
   - `VENV_PATH=".venv"` — verify: `ls .venv/bin/python`
3. If anything is wrong, fix it. If correct, report "project.config.md verified — all claims correct."
4. **DO NOT** change config values unless they're FACTUALLY wrong (not opinion)

---

## VERIFICATION GATE (Run these and paste output in TASK-RESULTS.md)

```bash
# 1. Django system check — must pass with no errors
cd /home/ahmed/aast/carbon
./manage.sh manage check --deploy 2>&1 | tail -10

# 2. Django admin loads without import errors
./manage.sh shell -c "from accounts.admin import *; print('admin OK —', len([x for x in dir() if 'Admin' in x]), 'admin classes loaded')"

# 3. Requirements.txt is parseable
./manage.sh shell -c "
with open('backend/requirements.txt') as f:
    lines = [l.strip() for l in f if l.strip() and not l.strip().startswith('#')]
print(f'requirements.txt: {len(lines)} non-comment lines')
"

# 4. G1 proof — PlatformAppConfig is admin-registered
./manage.sh shell -c "
from django.contrib import admin
from accounts.models import PlatformAppConfig
print('PlatformAppConfig registered:', admin.site.is_registered(PlatformAppConfig))
"

# 5. Frontend build still passes
cd carbon-frontend && npm run build 2>&1 | tail -3

# 6. Git diff summary
cd /home/ahmed/aast/carbon && git diff --stat
```

## DELIVERABLE

Create `TASKS-RESULT-P1.md` containing:
1. Each G1-G5: what was changed, with before/after snippets
2. Full verification output (copy-paste terminal)
3. Any deviations or issues found
4. Final requirements.txt line count (before → after)
