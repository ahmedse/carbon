# Pulse Console — Information Architecture & Delivery Plan

**Owner:** Master Architect
**Date:** 2026-08-12
**Status:** Accepted design (supersedes the thin 2-item "AI" menu in the prior frontend spec)

## 1. What "a complete AI section" means

The admin sidebar gets a dedicated **Pulse** section — the full operations console for the
in-hand intelligence layer. Every panel maps to a Pulse subsystem (ADR-0007/0008/0009).
This is the single place an operator views, inspects, and (where safe) configures Pulse.

## 2. Menu tree (complete)

```
PULSE
  Overview            /admin/ai            heart health, task envelope, queue, model tier
  AI Workspace        /admin/ai/workspace  conversation workspace (existing)
  Conversations       /admin/ai/conversations  transcripts (existing)

INTELLIGENCE CORE
  Knowledge Base      /admin/ai/knowledge  entities + accumulation
  Memory              /admin/ai/memory     long-term + episodic
  Knowledge Graph     /admin/ai/graph      nodes / edges / provenance (visualization)

AGENTS & TOOLING
  Agents              /admin/ai/agents     registry, handoffs, runs/steps
  MCP Servers         /admin/ai/mcp        registry, connection status, discovered tools
  Tools               /admin/ai/tools      tool catalog + executions
  Skills Catalog      /admin/ai/skills     skills + admission log
  Archetypes          /admin/ai/archetypes task archetype definitions
  Prompts & Playbook  /admin/ai/prompts    prompt versions + playbook blocks

FEEDBACK & LEARNING
  Feedback Review     /admin/ai/feedback   accept / reject / correct outcomes
  Learning Jobs       /admin/ai/learning   consolidation / distillation runs

OBSERVABILITY
  Monitoring          /admin/ai/monitoring LLM usage, token cost, latency, ops runs
  Audit Trail         /admin/ai/audit      AI audit events (distinct from platform audit)
  Logs                /admin/ai/logs       engine + inference logs
```

16 panels, 5 groups. Distinct from the existing generic `/admin/audit` + `/admin/logs`
(platform RBAC/system logs) — these are Pulse-specific data (LLM call log, AI audit events).

## 3. Panel → backend mapping

| Panel | Backend dependency | Status |
|---|---|---|
| Overview | `CarbonIntelligence.health_check()` + task status (needs endpoint) | **needs Phase 2b** |
| AI Workspace | `ai/workspace/` (exists) | **live now** |
| Conversations | `ai/workspace/` (exists) | **live now** |
| Knowledge Base | Phase 2 `knowledge/` models → read viewsets | Phase 2 |
| Memory | Phase 2 `memory/` models → read viewsets | Phase 2 |
| Knowledge Graph | Phase 2 `graph/` models → read viewsets | Phase 2 |
| Agents | Phase 2 `Agent/AgentHandoff/Run/RunStep` models | Phase 2 |
| MCP Servers | Phase 2 MCP registry model → viewsets | Phase 2 |
| Tools | Phase 2 `ToolExecution` + registry | Phase 2 |
| Skills Catalog | Phase 2 `Skill/SkillAdmissionLog` | Phase 2 |
| Archetypes | Phase 2 archetype models | Phase 2 |
| Prompts & Playbook | Phase 2 `PromptVersion/PlaybookBlock` | Phase 2 |
| Feedback Review | Phase 2 `Feedback` model | Phase 2 |
| Learning Jobs | Phase 2 learning loop run records | Phase 2 |
| Monitoring | Phase 2 `LLMCallLog/OpsRun` | Phase 2 |
| Audit Trail | Phase 2 AI audit events | Phase 2 |
| Logs | Phase 2 engine/inference logs | Phase 2 |

## 4. Delivery phases

- **Frontend Phase A (now):** complete menu (all 16) + live AI Workspace + Conversations +
  Overview (graceful degrade until health endpoint lands) + a shared
  `PulseModulePlaceholder` for the gated panels so every route resolves.
- **Backend Phase 2 (persistence):** swap SQLAlchemy seam → Django models (ADR-0009).
- **Backend Phase 2b (ops read API):** DRF read-only viewsets for every Phase 2 model +
  `GET /ai/pulse/health` + `GET /ai/pulse/tasks/{id}` + monitoring/audit/log endpoints.
- **Frontend Phase B:** replace each `PulseModulePlaceholder` with the real panel page.

## 5. Rules

- Read-only by default (RULE_21: no auto-mutation). Config mutations that do exist are
  human-approval gated and audited.
- All API via `apiFetch` (RULE_10); all pages in `PageContainer` (RULE_16); MUI Tabs
  (RULE_17); theme tokens (RULE_8); routes in `studioFromPath` (RULE_15).
- CBAC: every panel's data is scoped by the operator's `app_identifier` + org subtree.
