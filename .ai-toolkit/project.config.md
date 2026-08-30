# PROJECT CONFIG — Carbon Data Trust Platform
# ============================================
# THIS IS THE ONLY FILE YOU EDIT WHEN COPYING .ai-toolkit TO A NEW PROJECT.
# All role files read this file as Step 1. Update every section below.
# Format: one KEY=VALUE per line. Keep it factual, concise, and up-to-date.
# Last audited: 2026-08-02.

## PROJECT IDENTITY
PROJECT_NAME=Carbon
PROJECT_TYPE=Data Trust Platform (Django + React) — metadata-driven data governance, carbon accounting first app
WORKSPACE_ROOT=/home/ahmed/aast/carbon
DESCRIPTION=Carbon is evolving into a lighter, Ataccama-inspired Data Trust Platform that hosts domain apps on trusted data. Core: Catalog, MDM (reference data), Data Quality profiling+rules, metadata-driven schema engine (dataschema). First hosted app: Carbon emissions accounting (GHG Protocol). RBAC via ScopedRole (org-unit-scoped). Pulse = in-hand stateless reasoning engine (vendored under backend/ai/engine/); Carbon owns all AI knowledge/memory/learning/feedback.

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
BACKEND_VENV=.venv                                      # repo-root venv — backend/venv and backend/.venv do NOT exist
BACKEND_ACTIVATE=cd /home/ahmed/aast/carbon && source .venv/bin/activate
BACKEND_CHECK_CMD=python manage.py check
BACKEND_DB=PostgreSQL on localhost:5432
BACKEND_QUEUE=Redis 127.0.0.1:6379
BACKEND_API_PREFIX=carbon-api

## PYTHON
PYTHON_VERSION=3.12.13
VENV_PATH=.venv                                         # repo root; verify.sh resolves $VENV_PATH/bin/python (never `source`)
PYTEST_FLAGS=--reuse-db -q
MANAGE_PY=backend/manage.py

## FRONTEND
FRONTEND_DIR=carbon-frontend/
FRONTEND_FRAMEWORK=React 19.1 + Vite 6
FRONTEND_UI=MUI v7.1 (zinc/blue theme, compact density)
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
PROD_HOST=72.60.83.189
PROD_USER=ahmed
PROD_SSH=carbon-prod
PROD_STACK_PATH=/srv/carbon
PROD_CONTAINER=carbon-backend
PROD_PORT=8006
PROD_DB=carbon_prod (PostgreSQL 16 on host, accessed via host.docker.internal)
PROD_DOMAIN=carbon.clearturn.tech
PROD_SSL=Let's Encrypt (certbot)
PROD_DEPLOY_SCRIPT=deploy/carbon/redeploy-carbon.sh
PROD_TAG=v1.2.0

## DEPLOY MODEL
DEPLOY_TYPE=Docker (docker-compose.yml at repo root)
DEPLOY_VERIFY=docker exec <container> grep -c <marker> /app/<path>  ← must be > 0

## ARCHITECTURE — Django Apps
# Core platform apps (NEVER import emissions):
ARCH_CORE_APPS=accounts, core, catalog, mdm, dq, dataschema, connections, evidence, importexport
# Hosted apps (may import core apps, never the reverse):
ARCH_HOSTED_APPS=emissions
# Superseded / out of active scope:
ARCH_SUPERSEDED=ai_copilot (superseded by backend/ai/)
# ── AI Architecture ─────────────────────────────────────────────────
# NAMING: "AI" or "Carbon AI" = the ENTIRE backend/ai/ system. Never "Pulse" in user-facing text.
# FULL CONTRACT: .ai-toolkit/shared/ai-contract.md — THE binding AI contract (v2.0, updated 2026-08-15)
# FULL ADRs: decisions/0004 (3-layer arch), 0007 (in-hand engine), 0008 (monolith), 0009 (seam swap)
ARCH_AI_NAME=AI (Carbon AI) — the ENTIRE backend/ai/ system: orchestrator + guards + memory + engine + workspace.
ARCH_AI_ROOT=backend/ai/ — single Django app for all AI tiers. No new AI Django apps (ADR-0008).
ARCH_AI_ENTRY=CarbonIntelligence (ai/intelligence.py) — ONLY entry point. All Carbon code calls it.
ARCH_AI_LAYERS=3 layers: Platform AI (ai/protocol.py) → Domain AI (ai/domain/{app}.py) → Security Guards (ai/guards.py)
ARCH_AI_ENGINE=backend/ai/engine/ — in-process stateless reasoning engine (TurnPipelineRunner, six-witness pipeline, LLM router, KG, memory, skills). Adapter seam: ai/providers/pulse.py. No runtime provider swap (ADR-0007).
ARCH_AI_STORE=backend/ai/store.py — DjangoStore: CBAC-partitioned (app_identifier/org_unit_id/host_user_id/visibility). Carbon owns ALL durable AI state.
ARCH_AI_PLATFORM_OPS=dq.validate, dq.suggest, query.nl, query.explain, schema.analyze, fix.suggest, chat — work on ANY table, ANY app
ARCH_AI_DOMAIN_OPS=Per-app ABCs in ai/domain/{app}.py — anomaly.detect, anomaly.explain, report.draft (emissions). ⚠️ ai/domain/emissions.py NOT YET CREATED.
ARCH_AI_GUARDS=ScopeGuard, AccessGuard, DataIsolationGuard, MutationGuard, RateLimiter — run BEFORE every AI call
ARCH_AI_WORKSPACE=Conversation CRUD: ai/workspace_api.py. Ops observability: ai/ops_api.py. Models: ai/models/workspace.py.
ARCH_AI_MISSING=WorkspaceContext (§11 in ai-contract.md), streaming SSE path, feedback persistence, ai/domain/emissions.py
ARCH_AI_TASK_6=report.draft (async, 60s) — Dashboard data → narrative GHG report draft
ARCH_AI_DISCOVERY=No HTTP agent-card (engine is in-hand). Engine capabilities validated at import/startup.
ARCH_AI_PACKAGE=Modular monolith: ONE Django app (backend/ai/). All Pulse modules are internal Python packages (engine/, knowledge/, memory/, graph/, ingestion/, proactive/, archetypes/, learning/, feedback/). One backend/ai/models/ + one migrations/ namespace. NO new Django apps.
ARCH_AI_EXTENSIBILITY=New AI capability = register a tool/workflow, NOT a new app. Tool registry: engine/agent/registry.py + tools.py. MCP: engine/agent/mcp_client.py (MCP servers = discovered remote tools). Generic workflows: six-witness pipeline + learning loops as declarative specs. Plugins: ToolPlugin/WorkflowPlugin ABC, self-register at startup.
ARCH_AI_PORTABILITY=Portable contract: one facade (CarbonIntelligence), one stable contract (AIProvider ABC + task envelope), zero upward imports (layer imports NOTHING from catalog/mdm/dq/emissions/accounts/core; domain apps plug IN via ai/domain/{app}.py), injected deps (config/DB/cache via bootstrap). Migrate = copy package + adapt bootstrap.
ARCH_AI_CONSOLE=docs/PULSE_CONSOLE_DESIGN.md — the admin "Pulse" section: 16 panels across 5 groups (Overview/Workspace/Conversations + Intelligence Core + Agents & Tooling + Feedback & Learning + Observability). Frontend Phase A builds full menu + live Overview/Workspace/Conversations + shared placeholder for gated panels.
ARCH_AI_OPS_API=backend/ai/ops_api.py + ops_urls.py (Phase 2b) — read-only DRF viewsets for every Phase 2 model under /carbon-api/ai/pulse/ (health, tasks, knowledge, memory, graph, agents, mcp, tools, skills, archetypes, prompts, feedback, learning, monitoring, audit, logs). CBAC-scoped, read-only (RULE_21).
# RBAC:
ARCH_RBAC=ScopedRole (user, group, org_unit, module) — org-subtree-scoped visibility + admin
ARCH_ADMIN_GROUP=admins_group

## PROJECT-SPECIFIC HARD RULES
# These are facts specific to THIS project that workers must never violate.

RULE_1=Tenant model/code is FULLY removed. Do NOT reintroduce tenant, multi-tenancy, or tenant_id anywhere.
RULE_2=Project model is FULLY removed (replaced by OrgUnit in mdm). Do NOT reintroduce Project.
RULE_3=Core apps (accounts, core, catalog, mdm, dq, dataschema, connections, evidence, importexport) MUST NOT import from emissions. Emissions may import core.
RULE_4=API prefix is /carbon-api/ (config/urls.py). All backend routes are under this prefix.
RULE_5=Frontend routes are ABSOLUTE and namespace-prefixed (/carbon/*, /admin/*, /catalog/*, /dq/*, /settings, /help, /emissions). VITE_BASE (router basename) MUST stay "/" — App.jsx already carries the namespace prefixes, so any non-/ basename would double-prefix and 404.
RULE_6=Pulse is IN-HAND, vendored under backend/ai/engine/ (stateless engine only — agent/llm/cognition/core). Pulse holds NO memory, does NO learning, stores NO graphs. All durable AI state (conversations, knowledge, memory, feedback, graphs) is Carbon-owned via Django apps in backend/ai/. NO separate AI database: durable state → Carbon Postgres; transient/queue state → Redis.
RULE_13=Pulse engine is called in-process (in-hand), NOT over HTTP and NOT dependent on being online. The task envelope (docs/PULSE_CONTRACT_SPEC.md) remains the internal async job contract carried over Redis, not a network boundary. Graceful degradation: timeout 10s sync, 60s async; fall back to deterministic path on failure.
RULE_14=DQ Level 2 (nl_check rules) are evaluated by Pulse. Carbon sends row data + natural language rule → Pulse returns {passed, explanation, failed_rows}. DQ executor Phase A (deterministic: unique/threshold/reference_integrity) runs locally; Phase B (nl_check) calls Pulse.
RULE_7=UI labels: "Data Product" = Module (in code). "Table" = DataTable. NEVER use "Schema" as a label for a table.
RULE_8=Design tokens only — NO hardcoded hex colors, raw px spacing, or inline font sizes. Theme controls all.
RULE_9=ONE breadcrumb — shell/src/Breadcrumbs.jsx. NEVER render breadcrumbs inside pages.
RULE_10=Use apiFetch (src/api/api.js) for ALL API calls — it handles JWT refresh. Never raw fetch().
RULE_11=Every bug fix ships a regression test. Never fix the same bug twice — capture in playbook.
RULE_12=Org-scoped RBAC: reference data (EmissionFactor, GWP, ReferenceSet) is GLOBAL. Activity data + calculations are org-scoped.
RULE_15=Every new route path MUST be added to studioFromPath() in Shell.jsx. The function maps paths→sidebar studios. Missing entries cause the sidebar to switch to "Home" (only Platform Home link visible). See the comment block in Shell.jsx:38-52.
RULE_16=Every full page MUST wrap its content in PageContainer (src/components/layout/PageContainer.jsx) or BaseDetailPage (src/components/detail/BaseDetailPage.jsx). NEVER render a raw <Box> as the page root. Tab sub-components rendered inside a detail page are exempt.
RULE_17=Tab switching MUST use MUI <Tabs> + <Tab> with localStorage persistence (matching BaseDetailPage pattern). NEVER use ad-hoc <Button> rows for tab navigation.
RULE_18=AI CONTRACT IS BINDING — Every AI operation MUST follow .ai-toolkit/shared/ai-contract.md. Scope is MANDATORY. NEVER call a provider directly — always through CarbonIntelligence. ai/protocol.py is the canonical contract; it imports NOTHING from Django, DRF, requests, or any provider.
RULE_19=DOMAIN AI ISOLATION — Adding a new domain app's AI operations: create ai/domain/{app}.py with a DomainAIOperations ABC. NEVER add domain-specific methods to ai/protocol.py (platform ABC). Guards run automatically — domain developer does NOT write scope checks.
RULE_20=NO DATA LEAKAGE — AI provider MUST NOT use data from App A when processing App B. Scope.org_unit_ids filters ALL queries. DataIsolationGuard sanitizes responses. Cache keys include app_identifier. No cross-app embeddings or knowledge graph sharing.
RULE_21=NO AUTO-MUTATION — AI suggests, Carbon executes. NEVER auto-apply AI-suggested fixes. Fix suggestions ALWAYS have requires_confirmation=True. AI MUST NOT execute INSERT/UPDATE/DELETE/DROP. MutationGuard validates provider responses.
RULE_22=NO DANGLING ROUTES — every top-level route namespace MUST register an index route at its bare root (e.g. /carbon→/carbon/console, /admin→/admin/users, /settings/profile→/settings), so a bare namespace path or deployment mount path never 404s. Every navigate()/Navigate/Link/to=/href=/path: target MUST resolve to a <Route> in App.jsx. Enforce with .ai-toolkit/scripts/audit-routes.py (wired into verify.sh frontend/all/full).
RULE_23=NO IMPLEMENTATION LEAKAGE — user-facing text (UI labels, status/progress copy, empty states, error messages, AI assistant replies, docs) MUST describe OUTCOMES (WHAT the user gets / WHAT is happening), NEVER internals (HOW). Forbidden in user-facing copy: engine/pipeline mechanics ("translating to SQL", "analyzing table profile"), internal component names (Pulse, dispatch, runner), internal status codes (provider_unavailable, pulse_unavailable, skipped_unavailable), and provider/vendor jargon UNLESS a model selector is an explicit user-facing feature. Prefer "Working on your answer…" over "Translating question to SQL…"; "I couldn't reach the AI service" over "AI provider is currently unavailable".
RULE_24=DEEPSEEK MODEL TIERING — ALL workers run V4-Flash for every task (edits, tests, classification, regex/rule synthesis, nl_check, JSON generation, CRUD, migrations, fixes). V4-Pro is reserved EXCLUSIVELY for the Master Architect role. Flash is ~3x cheaper than Pro.
RULE_25=MAXIMIZE CACHE HITS (biggest lever) — keep a STABLE, long-lived system prompt + tool definitions at the FRONT of every LLM call; never rotate them between calls. DeepSeek prefix-cache: hit ≈ $0.007/M vs miss ≈ $0.22/M (~30x). Append new context AFTER the stable prefix, never reorder the prefix.
RULE_26=OFF-PEAK + TOKEN DISCIPLINE — run batch/async generations outside DeepSeek peak. Egypt (UTC+3): peak = 04:00-07:00 and 09:00-13:00 Cairo; off-peak = 13:00-04:00 Cairo (half price). Cap output tokens; prefer concise structured JSON; retrieve-don't-stuff.
RULE_27=STORAGE PATTERN (hosted apps) — owned/derived domain data = typed Django models in the app (people.Employee, emissions.Calculation); `dataschema.DataTable/DataRow` = governed measurements ONLY (inbound records whose shape another system owns). Governance audit (catalog.GovernanceEvent) is generic — fires on any entity. DQ rules+engine are decoupled; typed-field binding = `dq.ModelRuleAssignment` (model_label string, NOT ContentType/GenericForeignKey). NEVER add a generic per-row typed DQ result store — persist run-scoped summaries. See ADR 0025 + docs/STORAGE-PATTERN-HOSTED-APPS.md.

## KEY ARCHITECTURE FILES
# Workers should read these files first when working in related areas.

BACKEND_SETTINGS=backend/config/settings.py
BACKEND_URLS=backend/config/urls.py
BACKEND_RBAC=backend/accounts/rbac_utils.py
BACKEND_SCOPED_ROLE=backend/accounts/models.py
AI_PROTOCOL=backend/ai/protocol.py
AI_INTELLIGENCE=backend/ai/intelligence.py
AI_GUARDS=backend/ai/guards.py
AI_DOMAIN_PROTOCOL=backend/ai/domain_protocol.py
AI_PULSE_PROVIDER=backend/ai/providers/pulse.py
AI_OPS_API=backend/ai/ops_api.py
AI_CONSOLE_DESIGN=docs/PULSE_CONSOLE_DESIGN.md
AI_HTTP_TRANSPORT=backend/ai/providers/_http.py
AI_CONTRACT=.ai-toolkit/shared/ai-contract.md
AI_ADR=.ai-toolkit/decisions/0004-ai-multi-app-architecture.md
EMISSIONS_MODELS=backend/emissions/models.py
EMISSIONS_VIEWS=backend/emissions/views.py
EMISSIONS_SERVICES=backend/emissions/services.py
CATALOG_MODELS=backend/catalog/models.py
MDM_MODELS=backend/mdm/models.py
DATASCHEMA_MODELS=backend/dataschema/models.py
PEOPLE_MODELS=backend/people/models.py
STORAGE_PATTERN_DOC=docs/STORAGE-PATTERN-HOSTED-APPS.md
STORAGE_ADR=.ai-toolkit/decisions/0025-typed-vs-dataschema-storage.md
DQ_SERVICES=backend/dq/services.py
FRONTEND_APP=carbon-frontend/src/App.jsx
FRONTEND_SHELL=carbon-frontend/src/shell/Shell.jsx
FRONTEND_SIDEBAR=carbon-frontend/src/shell/ShellSidebar.jsx
FRONTEND_API=carbon-frontend/src/api/api.js
FRONTEND_THEME=carbon-frontend/src/theme/carbonTheme.js
FRONTEND_MANIFEST=carbon-frontend/src/apps/carbon/manifest.js

## WORKER MODEL POLICY (budget directive, updated 2026-08-18 — DeepSeek V3/R1 RETIRED)
WORKER_MODEL_POLICY=ALL worker roles (backend, frontend, devops, data-ml, debugger-fixer, qa-validator, product-designer, researcher, curator)=DeepSeek V4-Flash; ONLY master-architect=DeepSeek V4-Pro; Kimi models OFF roster (cost). V3/R1 are RETIRED on the provider — never reference them.
WORKER_MODEL_RUNTIME=Workers run on DeepSeek via VSCode Copilot custom models.

## DEEPSEEK PRICING (effective 2026-08-16, per 1M tokens — the post-hike schedule)
DEEPSEEK_V4_FLASH=cache-hit $0.007 off / $0.014 peak · cache-miss $0.22 off / $0.44 peak · output $0.66 off / $1.32 peak
DEEPSEEK_V4_PRO=cache-hit $0.022 off / $0.044 peak · cache-miss $0.66 off / $1.32 peak · output $1.98 off / $3.96 peak
DEEPSEEK_PEAK_UTC=01:00-04:00 and 06:00-10:00 UTC (all else off-peak = half price). Peak = 04:00-07:00 and 09:00-13:00 Cairo.
DEEPSEEK_CONTEXT=1M context, 384K max output. Cache hit is ~30x cheaper than miss — RULE_25 is the #1 cost lever.

## TESTING (see .ai-toolkit/shared/testing.md for strategy)
# NOTE: use python -m pytest (NOT ./manage.sh test) — manage.py test hits a
# Conflicting 'aiconversation' models error under the unittest loader.
BACKEND_TEST_CMD=cd backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai dq accounts -q
BACKEND_TEST_SINGLE=cd backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest <app>/tests/test_x.py -q
BACKEND_TEST_DIR=<app>/tests/test_*.py
BACKEND_TEST_COUNT=741 passing (pytest ai dq accounts, as of 2026-08-15)
FRONTEND_UNIT=Vitest 4 + RTL — cd carbon-frontend && npm test (330 tests, as of 2026-08-15)
FRONTEND_E2E=Playwright — npx playwright test --config e2e/playwright.config.ts (journey-09: 4 tests)

## TROUBLESHOOTING
PLAYBOOK=.ai-toolkit/troubleshooting/playbook.md           # known issues → verified fixes
DEBUGGING_GUIDE=.ai-toolkit/shared/debugging.md            # methodology + never-fix-twice loop

## KNOWN GOTCHAS FILE
GOTCHAS_FILE=/memories/repo/carbon-gotchas.md
# Read this before debugging. Contains verified incident forensics.

## KNOWN TECH DEBT (audit 2026-08-02)
DEBT_SX_TOKENS=34 hex / 52 px in sx props; ~237 hardcoded hex total across 37 frontend files — cleanup pending
DEBT_FRONTEND_TESTS=Frontend unit tests minimal (3 files / 8 tests); no e2e (no Playwright); no CI
DEBT_GUARD_HOOK=guard.sh NOT wired (.github/hooks/ absent) — manual/CI use only, wiring pending
DEBT_REGISTRY=Registry is auto-generated — run ./.ai-toolkit/scripts/scan.sh if stale
DEBT_DONE_P1_P6=2026-07-31 remediation complete: dual ORM removed, 12 unused deps removed, ai_copilot + dead dashboard pages removed, 6 services.py created, 28 backend tests added, 5 frontend hooks extracted, ADR-0002 Command pattern, SeedBuilder (seed_all.py), sx hex 90→34, Vitest+RTL scaffolding, registry regenerated

## PATTERN SCORECARD (see shared/design-patterns.md for full audit)
PATTERN_SCORECARD=15/23 GoF patterns actively used (Builder added P5-G1)
PATTERN_GATE=ALL 329 backend tests pass. Pattern adherence reviewed.

## TOOLKIT INTERNALS (auto-generated / shared — reference paths)
REGISTRY_DIR=.ai-toolkit/registry/            # auto-generated codebase inventory (scan.sh)
DECISIONS_DIR=.ai-toolkit/decisions/          # ADRs — architectural decisions
SCAN_CMD=./.ai-toolkit/scripts/scan.sh        # regenerate the registry
VERIFY_CMD=./.ai-toolkit/scripts/verify.sh    # verification gate (backend|frontend|tests|antipatterns|all|full)
RETRO_CMD=./.ai-toolkit/scripts/retro.sh      # gather learnings for retrospective (playbook + ADRs + warnings)
GUARD_HOOK=NOT WIRED — .github/hooks/guard-secrets.json does not exist; scripts/guard.sh available for manual/CI use (hook wiring pending)
ONBOARDING=.ai-toolkit/ONBOARDING.md          # start-here bootstrap for a fresh chat
DEFINITION_OF_DONE=.ai-toolkit/shared/definition-of-done.md   # the completion gate
INCIDENT_RUNBOOK=.ai-toolkit/troubleshooting/incident.md      # prod-down runbook
SHARED_CONTRACTS=.ai-toolkit/shared/          # api-contract, security, data-layer, config, design-system, logging, testing, debugging, git-workflow
ROLES_DIR=.ai-toolkit/roles/                  # 10 roles: master-architect, researcher, 6 workers (backend, frontend, devops, data-ml, debugger-fixer, qa-validator), product-designer, curator
