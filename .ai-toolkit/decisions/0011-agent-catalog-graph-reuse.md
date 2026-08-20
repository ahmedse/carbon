# ADR-0011 — Unified Agent Catalog + Graph Visualization Reuse

**Date:** 2026-08-20
**Status:** Accepted
**Author:** Master Architect
**Supersedes:** None (new decision)
**Referenced by:** `docs/DESIGN-AGENT-CATALOG.md`, TASKS.md W3-C → W3-F

---

## Context

W3-A/W3-B shipped a reviewable agentic plan lifecycle. The follow-on work needs to
(a) expose the agent/skill registry as a user-visible catalog, and (b) visualize
plans/topology/timelines without pulling in new charting dependencies.

Two forces required a decision before dispatch:
- **Catalog federation** — the DB-backed `AgentRegistry` already exists, but the
  plugin seam (`ToolPlugin`/`WorkflowPlugin`) is a second discovery surface that
  was previously invisible to the UI.
- **Visualization** — the codebase already ships a d3-force graph
  (`KnowledgeGraphPanel.jsx`) and Mermaid; duplicating a second d3 implementation
  in the new graph components would violate the "reuse before create" rule.

## Decision

1. **Catalog = read-mostly, DB is source of truth.** `catalog_service.py` queries
   `Agent`/`AgentHandoff`/`Skill`/`SkillAdmissionLog` and builds a request-time
   **federated index** that merges `AgentRegistry.list_agents` (DB) with
   `ToolPlugin`/`WorkflowPlugin` discovery from `plugins.py`. The merge is
   read-only — plugins enrich, they never override the DB.
2. **Topology is declared, never invented.** `GET /catalog/topology/` returns only
   `AgentHandoff` edges (ADR-001). No free-form graph.
3. **Extract one shared d3 core.** `ForceGraph.jsx` is extracted from
   `KnowledgeGraphPanel.jsx` and reused by `PlanDagGraph`, `AgentTopologyGraph`,
   and (non-d3) `RunTimeline`/`PlanMermaidPreview`. **No new visualization
   dependency** — `d3-*` and `mermaid` are already installed.
4. **Visualization reads refs, never re-runs work.** Graph/timeline components
   poll plan/catalog/timeline endpoints; they never trigger execution.

## Alternatives Considered

- **Adopt LangGraph/LangChain/AutoGen** — rejected; ADR-0001 + ADR-0004 forbid
  framework coupling; the existing seams already cover the need.
- **New React Flow / Recharts dependency** — rejected; violates reuse-before-create
  and adds bundle weight for features d3-force + Mermaid already cover.
- **Auto-approve replans on edit** — rejected; RULE_21 requires explicit consent.

## Consequences

- **Positive:** one federated catalog view; one shared graph primitive; no new
  deps; plan edits are consent-gated and diff-reviewed.
- **Negative / trade-off:** the federated index is request-time (not cached), so
  topology has a small per-request build cost — acceptable at current catalog size.
- **Do NOT re-try:** a second hand-rolled d3 graph outside `ForceGraph.jsx`;
  a new Django app for the catalog (ADR-0008); editing `backend/ai/engine/**`.

## References

- `backend/ai/engine/agent/registry.py` — `AgentRegistry`
- `backend/ai/engine/core/models.py` — `Agent`, `AgentHandoff`, `Skill`, `SkillAdmissionLog`
- `carbon-frontend/src/pages/admin/ai/KnowledgeGraphPanel.jsx` — d3 source to extract
- TASKS.md W3-C → W3-F
