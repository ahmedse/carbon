# ADR 0008 — Pulse Packaging: Modular Monolith, Plugin/Workflow Extensibility, Portable Contract

- **Status:** Accepted
- **Date:** 2026-08-12
- **Deciders:** Master Architect (ratified by owner)
- **Area:** cross-cutting (backend AI layer)

## Context
ADR-0007 made Pulse in-hand and stateless, with Carbon as the System of Intelligence.
Phase 2 migrates Pulse's durable-state modules (memory, knowledge, knowledge_graph,
ingestion, proactive, archetypes, learning, feedback) into Carbon. The naive mapping is
one new Django app per module → app explosion (8 migration namespaces, 8 admin surfaces,
cross-app FK friction, no clean way to move the whole layer later). The owner also wants
(1) extensibility via workflows/MCP/tooling/plugins without app sprawl and (2) a clean,
portable contract so the entire AI layer can migrate to another system.

## Decision
1. **Modular monolith — ONE Django app.** `backend/ai/` stays the single Django app.
   Pulse modules migrate as *internal Python packages* (`engine/`, `knowledge/`,
   `memory/`, `graph/`, `ingestion/`, `proactive/`, `archetypes/`, `learning/`,
   `feedback/`). All models share one `backend/ai/models/` package and ONE migrations
   namespace. **No new Django apps.**
2. **Extensibility = registry + plugins + workflows, not apps.**
   - Tool registry: `engine/agent/registry.py` + `tools.py` (already vendored). A new
     capability = register a tool.
   - MCP: `engine/agent/mcp_client.py` treats MCP servers as discovered remote tools.
   - Generic workflows: the six-witness turn pipeline and the learning loops are modeled
     as declarative workflow specs; a new workflow = a spec/class, not an app.
   - Plugins: a `ToolPlugin` / `WorkflowPlugin` ABC; plugins self-register at startup
     (Django `ready()`).
3. **Portable contract (one facade, one contract, dependency inversion).**
   - **Unified name: "Pulse"** = the whole intelligence layer. Layers within Pulse:
     Engine (stateless), Orchestrator (formerly "AI Heart"), Knowledge/Memory (state),
     Guards (CBAC).
   - Single facade: `CarbonIntelligence` — all Carbon code calls it, never the engine.
   - Single stable contract: `AIProvider` ABC + task envelope (versioned).
     `ai/protocol.py` imports nothing from Django/DRF/requests/domain apps.
   - Zero upward imports: the layer imports NOTHING from `catalog/mdm/dq/emissions/
     accounts/core`. Domain apps plug IN via `ai/domain/{app}.py`.
   - Injected dependencies (config, DB, cache) via a bootstrap — so "migrate to another
     system" = copy the package + adapt the bootstrap.

## Alternatives Considered
- **One Django app per AI module** — rejected: app explosion, fragmented migrations,
  cross-app FKs, kills portability.
- **Microservice per module** — rejected: operational overhead, breaks in-process
  performance, overkill for a modular monolith.
- **Keep "AI Heart" as a distinct system name** — rejected: folded under Pulse.

## Consequences
- **Positive:** single migration/admin surface; extensibility without app sprawl; the
  layer is portable as one package.
- **Negative / trade-off:** the package must stay self-contained (strict no-upward-import
  discipline); the registry becomes a correctness surface (needs startup-registration
  tests).
- **Do NOT re-try:** a separate Django app per AI module; naming "AI Heart" as a system
  separate from Pulse.

## References
- `.ai-toolkit/decisions/0007-pulse-inhand-stateless-engine.md`
- `docs/AI_INTELLIGENCE_ARCHITECTURE.md`
- `.ai-toolkit/shared/ai-contract.md`
- `plans/TASKS-PULSE-VENDOR-PHASE-2-KNOWLEDGE.md`
