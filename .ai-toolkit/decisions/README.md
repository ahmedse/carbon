# Architecture Decision Records (ADRs)

**Purpose:** record every non-trivial architectural decision ONCE so it is never
re-debated, re-investigated, or accidentally reversed by a worker who lacks context.

This is how we stop "why did we do it this way?" from costing tokens every session.

## When to write an ADR
- A choice with trade-offs that a future worker might question or undo.
- A breaking change (API shape, DB field, config key).
- A "we tried X, it failed, we chose Y" learning (so nobody re-tries X).
- A cross-cutting convention (auth scheme, error format, deploy method).

## When NOT to
- Obvious, low-stakes, or fully-reversible local choices.

## How
```bash
cp .ai-toolkit/decisions/0000-template.md .ai-toolkit/decisions/00NN-short-title.md
# fill it in, keep it short (half a page)
```

## Rules
- Number sequentially. NEVER delete an ADR — supersede it (set Status: Superseded by 00NN).
- Master Architect owns ADRs. Workers READ them before touching the relevant area.
- Link the ADR from the relevant TASKS.md phase when it constrains the work.

## Index
| # | Title | Status |
|---|-------|--------|
| [0001](0001-pattern-architecture.md) | Pattern architecture (Strategy/Command) | Accepted |
| [0010](0010-data-product-domain-neutral.md) | Data Product must not carry GHG `scope` (domain vocabulary stays out of the generic core) | Accepted |
| [0011](0011-agent-catalog-graph-reuse.md) | Unified Agent Catalog + graph visualization reuse (extract `ForceGraph.jsx`; no new deps) | Accepted |
| [0012](0012-enterprise-graph-canvas.md) | Enterprise Graph Canvas primitive — one shared surface (pan/zoom/move/resize/export/maximize/live status); thin domain adapters; no new deps | Accepted |
| [0013](0013-ai-agent-platform-gap-closure.md) | Next-Gen AI Agent Platform gap closure — output-quality drift, bounded retry/backoff, plan templates, run comparison, non-data domain adapters | Accepted |
| [0014](0014-pulse-chat-agent-mode-split.md) | Pulse Chat / Agent mode split — mode is workspace-level, safety contract always visible | Accepted |
| [0015](0015-multi-instance-single-tenant-deployment.md) | Multi-instance single-tenant deployment — one codebase, N isolated deployments; no fork, no tenant_id | Accepted |
| [0016](0016-domain-app-ai-contract.md) | Domain App AI Contract — manifest-driven extension model (`DomainAIOperations` ABC) | Accepted |
| [0019](0019-contextual-inspector-drawer.md) | Contextual Inspector Drawer — unify Notes drawer + per-page metrics panels into one registry-driven global drawer | Proposed |
| [0024](0024-pulse-0.2-north-star.md) | Pulse 0.2 north star, invariants I1–I8 & anti-drift rails (import-boundary gate + UX acceptance rubric) | Accepted |

<!-- Add a row per ADR. Keep newest at the bottom. -->
