# Project Configuration
# =====================
# THIS IS THE ONLY FILE YOU EDIT WHEN COPYING .ai-toolkit TO A NEW PROJECT.
# All roles read this file first. Keep it factual, concise, and up-to-date.

# ── IDENTITY ──────────────────────────────────────────────────
PROJECT_NAME="Carbon Data Trust Platform"
PROJECT_DESCRIPTION="GHG emissions tracking, reporting, and analysis — AASTMT"
REPO_ROOT="$PWD"

# ── STACK ──────────────────────────────────────────────────────
BACKEND_FRAMEWORK="Django 5.2.3"
BACKEND_API="Django REST Framework 3.16.0"
BACKEND_DB="PostgreSQL (dev: carbon_dev, test: via pytest --reuse-db)"
BACKEND_CACHE="Redis"
BACKEND_AUTH="JWT (djangorestframework-simplejwt)"
BACKEND_VECTOR="ChromaDB (AI copilot embeddings)"

FRONTEND_FRAMEWORK="React 18 + Vite"
FRONTEND_UI="MUI (Material UI v5/v6)"
FRONTEND_CHARTS="Chart.js via react-chartjs-2"
FRONTEND_ROUTER="React Router v6"
FRONTEND_STATE="React Context API (AuthContext, ThemeContext)"

# ── PATHS ──────────────────────────────────────────────────────
BACKEND_DIR="backend"
FRONTEND_DIR="carbon-frontend"
API_PREFIX="/carbon-api/"
FRONTEND_BASENAME="/carbon/"

# ── PYTHON ─────────────────────────────────────────────────────
PYTHON_VERSION="3.12.13"
VENV_PATH=".venv"
PYTEST_FLAGS="--reuse-db -q"
MANAGE_PY="backend/manage.py"

# ── OPS ────────────────────────────────────────────────────────
OPS_SCRIPT="./manage.sh"
# Usage:
#   ./manage.sh start              # start full stack
#   ./manage.sh start backend      # start one service
#   ./manage.sh stop
#   ./manage.sh restart
#   ./manage.sh manage <django_cmd> # e.g. ./manage.sh manage migrate

# ── DEFAULT TIMEZONE ───────────────────────────────────────────
DEFAULT_TIMEZONE="Africa/Cairo"

# ── HARD RULES (Non-Negotiable) ─────────────────────────────────
# 1. NEVER run raw manage.py, npm run dev, vite, or tail -f directly.
#    ALWAYS use ./manage.sh (OPS_SCRIPT). Raw commands hang terminals.
# 2. NEVER hardcode timezone-naive datetimes. Use django.utils.timezone.
# 3. Views are THIN (parse → call service → return). Business logic in services.py.
# 4. Colors/spacing are TOKENS (theme.palette.*, spacing()). NEVER raw px/hex.
# 5. Components COMPOSE existing primitives. NEVER duplicate/fork.
# 6. Permissions are PROXIES (permission classes). NEVER inline auth checks.
# 7. BEFORE creating anything, consult .ai-toolkit/registry/ (run scan.sh if stale).
# 8. Every stateful model has explicit STATUS_CHOICES + transition methods.
# 9. All endpoints follow the unified API contract (shared/api-contract.md).
# 10. Run verification gate before shipping: ./.ai-toolkit/scripts/verify.sh full

# ── KNOWN TECH DEBT ────────────────────────────────────────────
# - seed_all.py is procedural (should be Builder pattern)
# - Some inline sx values in HeaderEnhanced.jsx (should use theme tokens)
# - No Command pattern for undo in DQ/data entry operations
# - project.config.md was blank until 2026-07-30 (now populated)

# ── PATTERN SCORECARD ──────────────────────────────────────────
# See shared/design-patterns.md for full audit
# Current: 14/23 GoF patterns actively used
# Gate: ALL 283 backend tests pass. Pattern adherence reviewed.
# =====================
# THIS IS THE ONLY FILE YOU EDIT WHEN COPYING .ai-toolkit TO A NEW PROJECT.
# All role files read this file as Step 1. Update every section below.

## PROJECT IDENTITY
PROJECT_NAME=Carbon
PROJECT_TYPE=Data Trust Platform (Django + React) — metadata-driven data governance, carbon accounting first app
WORKSPACE_ROOT=/home/ahmed/aast/carbon
DESCRIPTION=Carbon is evolving into a lighter, Ataccama-inspired Data Trust Platform that hosts domain apps on trusted data. Core: Catalog, MDM (reference data), Data Quality profiling+rules, metadata-driven schema engine (dataschema). First hosted app: Carbon emissions accounting (GHG Protocol). RBAC via ScopedRole (org-unit-scoped). Pulse = external AI/RAG system (not in-repo).

## OPS SCRIPT (Universal — how to run/stop/inspect services)
OPS_SCRIPT=./manage.sh
OPS_START=./manage.sh start [backend|frontend]          # omit service = both
OPS_STOP=./manage.sh stop [backend|frontend]
OPS_RESTART=./manage.sh restart [backend|frontend]
OPS_STATUS=./manage.sh status
OPS_LOGS=./manage.sh logs <service> <N-lines>           # bounded — never tail -f
OPS_CLEAN_PORTS=./manage.sh clean-ports
OPS_MIGRATE=./manage.sh migrate
OPS_SHELL=./manage.sh shell
OPS_TEST=./manage.sh test
OPS_DJANGO=./manage.sh manage <django-command>          # arbitrary manage.py command

## BACKEND
BACKEND_DIR=backend/
BACKEND_FRAMEWORK=Django 5.2 + Django REST Framework
BACKEND_PORT=8009
BACKEND_VENV=backend/.venv/
BACKEND_ACTIVATE=cd /home/ahmed/aast/carbon/backend && source .venv/bin/activate
BACKEND_CHECK_CMD=python manage.py check
BACKEND_DB=PostgreSQL on localhost:5432
BACKEND_QUEUE=Redis 127.0.0.1:6379
BACKEND_API_PREFIX=carbon-api

## FRONTEND
FRONTEND_DIR=carbon-frontend/
FRONTEND_FRAMEWORK=Vite + React + MUI (zinc/blue theme, compact density)
FRONTEND_PORT=5179
FRONTEND_LINT_CMD=cd /home/ahmed/aast/carbon/carbon-frontend && npm run lint
FRONTEND_BUILD_CMD=cd /home/ahmed/aast/carbon/carbon-frontend && npm run build
FRONTEND_API_HELPER=carbon-frontend/src/api/api.js (apiFetch)
FRONTEND_THEME=carbon-frontend/src/theme/carbonTheme.js
FRONTEND_BASE_PATH=/carbon/

## DESIGN SYSTEM
DESIGN_LANGUAGE=Enterprise data-platform style — dense, compact, zinc/blue palette, Inter font. Palantir/Ataccama-inspired.
DESIGN_REFERENCE_SIBLINGS=/home/ahmed/clearturn/gigacast/frontend, /home/ahmed/aast/nextlearn/apps/web
DESIGN_PRIMITIVES=PageContainer, PageHeader, DetailHeader, BaseDetailPage, DetailMainPanel, DetailMetricsPanel (src/components/layout/, src/components/detail/)
THEME_DIR=carbon-frontend/src/theme/
COMPONENTS_DIR=carbon-frontend/src/components/
BREADCRUMB_COMPONENT=carbon-frontend/src/shell/Breadcrumbs.jsx

## TIMEZONE
DEFAULT_TIMEZONE=Africa/Cairo (UTC+2/UTC+3)
BACKEND_TZ_USAGE=django.utils.timezone.now()  ← ALWAYS. Never datetime.now()
FRONTEND_TZ_USAGE=dayjs with timezone plugin

## PRODUCTION
PROD_HOST=TBD
PROD_USER=ahmed
PROD_STACK_PATH=TBD
PROD_CONTAINER=TBD
PROD_DB=TBD

## DEPLOY MODEL
DEPLOY_TYPE=Docker (docker-compose.yml at repo root)
DEPLOY_VERIFY=docker exec <container> grep -c <marker> /app/<path>  ← must be > 0

## ARCHITECTURE — Django Apps
# Core platform apps (NEVER import emissions):
ARCH_CORE_APPS=accounts, core, catalog, mdm, dq, dataschema
# Hosted apps (may import core apps, never the reverse):
ARCH_HOSTED_APPS=emissions
# Superseded / out of active scope:
ARCH_SUPERSEDED=ai_copilot (Pulse owns AI/RAG now)
# RBAC:
ARCH_RBAC=ScopedRole (user, group, org_unit, module) — org-subtree-scoped visibility + admin
ARCH_ADMIN_GROUP=admins_group

## PROJECT-SPECIFIC HARD RULES
# These are facts specific to THIS project that workers must never violate.

RULE_1=Tenant model/code is FULLY removed. Do NOT reintroduce tenant, multi-tenancy, or tenant_id anywhere.
RULE_2=Project model is FULLY removed (replaced by OrgUnit in mdm). Do NOT reintroduce Project.
RULE_3=Core apps (catalog, mdm, dq, dataschema, accounts, core) MUST NOT import from emissions. Emissions may import core.
RULE_4=API prefix is /carbon-api/ (config/urls.py). All backend routes are under this prefix.
RULE_5=Frontend base path is /carbon/. Vite base + router basename must use this.
RULE_6=Do NOT add pgvector, LLM gateway, or AI copilot features in-repo. Pulse is the external AI system.
RULE_7=UI labels: "Data Product" = Module (in code). "Table" = DataTable. NEVER use "Schema" as a label for a table.
RULE_8=Design tokens only — NO hardcoded hex colors, raw px spacing, or inline font sizes. Theme controls all.
RULE_9=ONE breadcrumb — shell/src/Breadcrumbs.jsx. NEVER render breadcrumbs inside pages.
RULE_10=Use apiFetch (src/api/api.js) for ALL API calls — it handles JWT refresh. Never raw fetch().
RULE_11=Every bug fix ships a regression test. Never fix the same bug twice — capture in playbook.
RULE_12=Org-scoped RBAC: reference data (EmissionFactor, GWP, ReferenceSet) is GLOBAL. Activity data + calculations are org-scoped.

## KEY ARCHITECTURE FILES
# Workers should read these files first when working in related areas.

BACKEND_SETTINGS=backend/config/settings.py
BACKEND_URLS=backend/config/urls.py
BACKEND_RBAC=backend/accounts/rbac_utils.py
BACKEND_SCOPED_ROLE=backend/accounts/models.py
EMISSIONS_MODELS=backend/emissions/models.py
EMISSIONS_VIEWS=backend/emissions/views.py
EMISSIONS_SERVICES=backend/emissions/services.py
CATALOG_MODELS=backend/catalog/models.py
MDM_MODELS=backend/mdm/models.py
DATASCHEMA_MODELS=backend/dataschema/models.py
DQ_SERVICES=backend/dq/services.py
FRONTEND_APP=carbon-frontend/src/App.jsx
FRONTEND_SHELL=carbon-frontend/src/shell/Shell.jsx
FRONTEND_SIDEBAR=carbon-frontend/src/shell/ShellSidebar.jsx
FRONTEND_API=carbon-frontend/src/api/api.js
FRONTEND_THEME=carbon-frontend/src/theme/carbonTheme.js
FRONTEND_MANIFEST=carbon-frontend/src/apps/carbon/manifest.js

## TESTING (see .ai-toolkit/shared/testing.md for strategy)
BACKEND_TEST_CMD=./manage.sh test                          # Django TestCase + DRF APIClient
BACKEND_TEST_SINGLE=./manage.sh test <app>.tests.test_x    # run one module
BACKEND_TEST_DIR=<app>/tests/test_*.py
FRONTEND_E2E=cd carbon-frontend && npm run test:e2e         # Playwright critical journeys
FRONTEND_E2E_DIR=carbon-frontend/e2e/
FRONTEND_UNIT=NONE (no unit runner configured — recommend adding vitest for component/unit tests)

## TROUBLESHOOTING
PLAYBOOK=.ai-toolkit/troubleshooting/playbook.md           # known issues → verified fixes
DEBUGGING_GUIDE=.ai-toolkit/shared/debugging.md            # methodology + never-fix-twice loop

## KNOWN GOTCHAS FILE
GOTCHAS_FILE=/memories/repo/carbon-gotchas.md
# Read this before debugging. Contains verified incident forensics.

## TOOLKIT INTERNALS (auto-generated / shared — reference paths)
REGISTRY_DIR=.ai-toolkit/registry/            # auto-generated codebase inventory (scan.sh)
DECISIONS_DIR=.ai-toolkit/decisions/          # ADRs — architectural decisions
SCAN_CMD=./.ai-toolkit/scripts/scan.sh        # regenerate the registry
VERIFY_CMD=./.ai-toolkit/scripts/verify.sh    # verification gate (backend|frontend|tests|antipatterns|all|full)
RETRO_CMD=./.ai-toolkit/scripts/retro.sh      # gather learnings for retrospective (playbook + ADRs + warnings)
GUARD_HOOK=.github/hooks/guard-secrets.json   # PreToolUse hook → scripts/guard.sh blocks hardcoded secrets
ONBOARDING=.ai-toolkit/ONBOARDING.md          # start-here bootstrap for a fresh chat
DEFINITION_OF_DONE=.ai-toolkit/shared/definition-of-done.md   # the completion gate
INCIDENT_RUNBOOK=.ai-toolkit/troubleshooting/incident.md      # prod-down runbook
SHARED_CONTRACTS=.ai-toolkit/shared/          # api-contract, security, data-layer, config, design-system, logging, testing, debugging, git-workflow
ROLES_DIR=.ai-toolkit/roles/                  # 8 roles: master-architect, scientific-researcher, 5 workers, curator (evolution agent)
