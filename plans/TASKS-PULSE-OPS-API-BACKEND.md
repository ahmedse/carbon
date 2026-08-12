# TASKS.md — Pulse Ops Read API (Backend Phase 2b)

**Status:** DRAFT — activate after Phase 2 (persistence seam + Django models) lands.
**Role:** Backend Worker
**Model:** DeepSeek-V3
**Domain:** backend
**Prerequisite:** `plans/TASKS-PULSE-VENDOR-PHASE-2-KNOWLEDGE.md` completed.
**Primary context:** `docs/PULSE_CONSOLE_DESIGN.md` (panel→endpoint mapping), `.ai-toolkit/shared/api-contract.md`

## Objective

Expose the read-only Pulse ops API the console consumes. All endpoints are read-only
(no auto-mutation, RULE_21), CBAC-scoped by the caller's `app_identifier` + org subtree.

## Endpoints (all under `/carbon-api/ai/pulse/`)

| Endpoint | Data | Backing |
|---|---|---|
| `GET health/` | ProviderStatus (name/version/healthy/modules) | `CarbonIntelligence.health_check()` |
| `GET tasks/{task_id}/` | Task envelope status | `CarbonIntelligence.get_task_status()` |
| `GET knowledge/` | knowledge entities | Phase 2 `KnowledgeEntity` models |
| `GET memory/` | long-term + episodic memory | Phase 2 memory models |
| `GET graph/nodes/`, `graph/edges/` | knowledge graph | Phase 2 `KgNode/KgEdge/KgProvenance` |
| `GET agents/`, `agents/{id}/runs/` | agents + handoffs + runs/steps | Phase 2 `Agent/AgentHandoff/Run/RunStep` |
| `GET mcp/` | MCP server registry + status + discovered tools | Phase 2 MCP registry model |
| `GET tools/`, `tools/{id}/executions/` | tool catalog + executions | Phase 2 `ToolExecution` |
| `GET skills/` | skills + admission log | Phase 2 `Skill/SkillAdmissionLog` |
| `GET archetypes/` | archetype definitions | Phase 2 archetype models |
| `GET prompts/` | prompt versions + playbook blocks | Phase 2 `PromptVersion/PlaybookBlock` |
| `GET feedback/` | accept/reject/correct outcomes | Phase 2 `Feedback` |
| `GET learning/` | consolidation/distillation runs | Phase 2 learning run records |
| `GET monitoring/` | LLM usage, token cost, latency, ops runs | Phase 2 `LLMCallLog/OpsRun` |
| `GET audit/` | AI audit events | Phase 2 AI audit model |
| `GET logs/` | engine + inference logs | Phase 2 logs |

## Tasks

1. CREATE `backend/ai/ops_api.py` — DRF read-only viewsets (`ReadOnlyModelViewSet`) for each
   Phase 2 model above, with `get_queryset()` filtered by the caller's `app_identifier` + org
   subtree (reuse `guards.py` scope helpers).
2. CREATE `backend/ai/ops_urls.py` — router wiring all `pulse/` routes above.
3. MODIFY `backend/config/urls.py` — include `ops_urls` under `/carbon-api/ai/pulse/`.
4. CREATE `backend/ai/serializers.py` additions (or a new `ops_serializers.py`) for each model.
5. MODIFY `backend/ai/tests/` — add coverage: list endpoints return only the caller's scope.

## DO NOT TOUCH
- `carbon-frontend/**`
- `backend/ai/protocol.py`, `intelligence.py` (reuse, don't change signatures)

## GATES
  cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check → pass
  cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run → no drift
  cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests -q → pass
  cd /home/ahmed/aast/carbon && bash ./.ai-toolkit/scripts/verify.sh backend → pass

## HARD RULES
- Read-only. No POST/PUT/DELETE except where a config mutation is explicitly human-approved (none in this phase).
- CBAC scope filtering on every queryset (RULE_20).
- No separate AI DB; no raw SQLAlchemy exposure through the API.
