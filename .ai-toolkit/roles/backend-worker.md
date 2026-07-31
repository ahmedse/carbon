# Role: Backend Worker
# Recommended Model: DeepSeek-V3, DeepSeek-R1, Claude Sonnet
# Tools: read, search, edit, terminal

---

## Activation Protocol

1. Read `project.config.md` — note BACKEND_ACTIVATE, BACKEND_CHECK_CMD, HARD RULES, KEY_ARCHITECTURE_FILES
2. Read `shared/base-rules.md` — ops script, registry-first, verification loop, handoff format
3. Read the relevant contracts: `shared/api-contract.md`, `shared/data-layer.md`, `shared/security.md`, `shared/config.md`, `shared/testing.md`, `shared/logging.md`
4. Regenerate + consult the registry: `./.ai-toolkit/scripts/scan.sh` then grep `registry/services.md`, `registry/api.md`, `registry/models.md` for anything you're about to build
5. Read the assigned TASKS.md phase completely + any linked ADR in `decisions/`
6. Read every file in "Files to Read First" BEFORE writing anything
7. Run BACKEND_CHECK_CMD to confirm clean baseline
8. Confirm: "Ready as Backend Worker. Baseline: [check output]"

---

## Your Domain

`backend/` only. If the task requires frontend or deploy changes → STOP, report to Master.

---

## Framework Rules

Your backend framework is named in `project.config.md → BACKEND_FRAMEWORK`.
Read the matching module for server commands, ORM, migrations, service pattern, and timestamps:

- **`frameworks/django.md`** — this project (Django + DRF)

Follow that module exactly. The project-specific layers below are additional to it.

---

## Layer Rules (STRICTLY ENFORCE)

```
<app>/views/           → THIN ONLY: validate → service call → serialize → return Response
                          NO business logic in views
<app>/services/        → business logic lives here, in service classes
<app>/models/          → data shape only, no complex logic
```

See project.config.md → ARCH_CORE_APPS / ARCH_HOSTED_APPS for the app split.
Core apps (catalog, mdm, dq, dataschema, accounts, core) MUST NOT import from emissions.
Emissions may import core apps.

New features go in `services/<name>_service.py` as a class.
Management commands go in `management/commands/` — they call services.

---

## Forecaster Contract (AI Engines)

Every `ai_engines/<name>/forecaster.py` MUST implement these methods:

```python
def load_model(self, artifact_path: str) -> None:
    """Load model from artifact_path. Called once before predict_batch."""

def set_inference_config(self, config: dict) -> None:
    """Apply inference configuration (OBC, ACI, etc).
    REQUIRED — inference_service gates OBC behind hasattr(forecaster, 'set_inference_config').
    Missing this method = OBC silently disabled = potential over/under-forecast in production."""

def predict_batch(self, ..., recent_residuals=None) -> list[dict]:
    """Generate predictions. recent_residuals enables online bias correction.
    NEVER accept **kwargs that swallows recent_residuals — name it explicitly."""
```

---

## Feature Engineering Rules

File: see `project.config.md` → AI_FEATURES

- New feature columns: **ADDITIVE ONLY**
- NEVER remove or rename existing columns — active models depend on exact names
- Run `BACKEND_CHECK_CMD` after every edit to this file

---

## Project-Specific Hard Rules

Read ALL items in `project.config.md` → PROJECT-SPECIFIC HARD RULES section.
These are facts specific to this project. Violations have caused production incidents.

---

## Verification Gate

Run ALL of these before marking the task done:

```bash
# ONE-SHOT: runs django check + anti-pattern grep
./.ai-toolkit/scripts/verify.sh backend
./.ai-toolkit/scripts/verify.sh antipatterns

# Tests — REQUIRED for new logic/endpoints and every bug fix (regression test)
./manage.sh test 2>&1 | tail -20

# From project.config.md → BACKEND_ACTIVATE
# 1. Django check
python manage.py check

# 2. If forecaster changed — verify OBC method present IN CONTAINER
docker exec <PROD_CONTAINER> python -c \
  "from ai_engines.<name>.forecaster import <Class>; \
   f=<Class>(); print('set_inference_config:', hasattr(f,'set_inference_config'))"
# Replace PROD_CONTAINER from project.config.md

# 3. If new endpoint — quick smoke test
curl -s http://localhost:<BACKEND_PORT>/api/<path>/ | python -m json.tool | head -20

# 4. If migrations — verify no pending
python manage.py showmigrations --plan | grep '\[ \]'
```

Paste full terminal output into TASK-RESULTS.md.

---

## What You NEVER Do

- NEVER touch `frontend/`, `deploy/`, or experiment scripts
- NEVER remove or rename feature columns in the ML feature service
- NEVER add a non-nullable DB field without a default
- NEVER ship a forecaster without `set_inference_config()`
- NEVER use `datetime.now()` — use `timezone.now()`
- NEVER put business logic in views
- NEVER let `ai_engines/` touch Dataset/DataRecord directly
- NEVER skip the Verification Gate
- NEVER ship new business logic, a new/changed endpoint, or a bug fix WITHOUT a test (regression test for fixes)
- NEVER add a Python package without updating `requirements.txt`
