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

## Index (0001–0049)

| # | Title | Status |
|---|-------|--------|
| [0001](0001-pattern-architecture.md) | Design Pattern Architecture for Carbon Platform | Accepted |
| [0002](0002-command-pattern.md) | Command Pattern for Reversible Operations | Accepted |
| [0003](0003-drf-spectacular-migration.md) | Migrate from drf-yasg to drf-spectacular | Proposed |
| [0004](0004-ai-multi-app-architecture.md) | Multi-App AI Heart Architecture | Accepted |
| [0005](0005-pulse-to-ai-terminology.md) | Terminology: "Pulse" → "AI" | Accepted |
| [0006](0006-dq-rule-standalone.md) | DQ Rules Are Standalone; Bindings Are Separate | Accepted |
| [0007](0007-pulse-inhand-stateless-engine.md) | Pulse as In-Hand Stateless Engine; Carbon as System of Intelligence | Accepted |
| [0008](0008-pulse-packaging-portability.md) | Pulse Packaging: Modular Monolith, Plugin/Workflow Extensibility | Accepted |
| [0009](0009-pulse-engine-stateful-monolith.md) | Pulse Engine Is a Stateful Monolith | Accepted |
| [0010](0010-data-product-domain-neutral.md) | Data Product must not carry GHG `scope` | Accepted |
| [0011](0011-agent-catalog-graph-reuse.md) | Unified Agent Catalog + Graph Visualization Reuse | Accepted |
| [0012](0012-enterprise-graph-canvas.md) | Enterprise Graph Canvas Primitive | Accepted |
| [0013](0013-ai-agent-platform-gap-closure.md) | Next-Gen AI Agent Platform Gap Closure | Accepted |
| [0014](0014-pulse-chat-agent-mode-split.md) | Pulse Chat / Agent Mode Split | Accepted |
| [0015](0015-multi-instance-single-tenant-deployment.md) | Multi-instance single-tenant deployment | Accepted |
| [0016](0016-domain-app-ai-contract.md) | Domain App AI Contract (manifest-driven) | Accepted |
| [0017](0017-pulse-instance-yaml-seam.md) | Pulse Instance Config: YAML Seam Pattern | Accepted |
| [0018](0018-i18n-dual-language.md) | Dual-Language i18n: English + Arabic RTL | Accepted |
| [0019](0019-contextual-inspector-drawer.md) | Contextual Inspector Drawer | Accepted |
| [0020](0020-inventory-coverage.md) | Inventory Coverage for GHG accounting | Accepted |
| [0021](0021-tool-result-synthesis-stage.md) | Tool-Result Synthesis Stage | Accepted |
| [0022](0022-live-data-grounding-directive.md) | Live-Data Grounding Directive + Insight Synthesis | Accepted |
| [0023](0023-llm-intent-resolution.md) | LLM-Driven Intent Resolution (S1.5) | Accepted |
| [0024](0024-pulse-0.2-north-star.md) | Pulse 0.2 North Star, Invariants & Anti-Drift Rails | Accepted |
| [0025](0025-typed-vs-dataschema-storage.md) | Typed tables vs dataschema for hosted apps | Accepted |
| [0026](0026-pulse-0.2-close-out.md) | Pulse 0.2 Close-Out (Waves A–D) | Accepted |
| [0027](0027-governed-lookup-fk-to-referencevalue.md) | Governed lookups are FK to `ReferenceValue` | Accepted |
| [0028](0028-single-root-org-unit-instance-gated-seeds.md) | Single root OrgUnit; instance-gated seeds | Accepted |
| [0029](0029-compensation-ledger.md) | Compensation ledger (append-only, provenance) | Accepted |
| [0030](0030-eoffice-correspondence-engine.md) | e-Office Correspondence & Approval Engine | Accepted |
| [0031](0031-pulse-unified-remediation-plan.md) | Pulse Unified Remediation Plan (D1–D12) | Accepted |
| [0032](0032-entity-capability-framework.md) | Entity Capability Framework (ECF) | Accepted |
| [0033](0033-pulse-identity-propagation.md) | Pulse Identity Propagation (actor-chain) | Accepted |
| [0034](0034-resilient-agent-workflow-graph.md) | Resilient Agent Workflow Graph (typed nodes + guards) | Accepted |
| [0035](0035-responsive-shell-mobile-ia.md) | Responsive Shell IA + Mobile Density Exceptions | Accepted |
| [0036](0036-pulse-control-plane-ia.md) | Pulse Control Plane IA (admin remake) | Accepted |
| [0037](0037-modest-typography-bump.md) | Modest global typography bump (compact readability) | Accepted |
| [0038](0038-eduos-gradevance.md) | EduOS instance + GradeVance + LCT/Rubric config engines | Accepted |
| [0039](0039-data-trust-index.md) | Data Trust Index (35Q+20O+35C+10F) + Catalog SearchSelect | Accepted |
| [0040](0040-product-identity-module-vs-dataset.md) | Product identity: Module (Data Product) vs Dataset Hub | Accepted |
| [0041](0041-pulse-ops-canvas-job-map.md) | Pulse Ops Canvas (Job Map) — durable agent/ops artifact | Accepted |
| [0042](0042-gradevance-persona-apps.md) | GradeVance persona apps: Learn · Teach · Engine (three surfaces, one engine) | Accepted |
| [0043](0043-agent-four-view-cockpit.md) | Agent Four-View Cockpit (Plan · Run · Canvas · Output) | Implemented |
| [0044](0044-nibras-dual-catalog-ssot.md) | Nibras dual-catalog SSOT (pack tools ⊆ instance.yaml) | Accepted |
| [0045](0045-nibras-process-security-planes.md) | Nibras process security planes (host SoD vs Pulse dials) | Accepted |
| [0046](0046-pulse-chat-no-host-mutation-stage.md) | Pulse Chat never stages host writes; system change via Agent or host UI | Accepted |
| [0047](0047-pulse-unified-conversation-state.md) | Pulse v2: unified ConversationState, ContextPack, one decision per turn (Intelligence Contract) | Accepted |
| [0048](0048-birthright-duty-scope.md) | Birthright duty scope | Accepted |
| [0049](0049-pulse-2-1-model-understands-catalog-executes.md) | Pulse 2.1: model understands, catalog executes | Proposed |
| [0050](0050-pulse-core-domain-free-versioned-packs.md) | Pulse core is domain-free; domains are self-contained, versioned packs (gauge + pack gates) | Proposed |
| [0051](0051-excellence-ledger.md) | Excellence Ledger: one evidence store, many ladders (tier → track → subject; `excellence` DB) | Accepted |
| [0052](0052-pulse-plan-contract.md) | One Plan Contract, with authority to reject | Proposed |
| [0053](0053-pulse-no-masking-fallbacks.md) | No masking fallbacks; follow-ups answer from the last view | Proposed |
| [0054](0054-pulse-reasoning-channel.md) | Reasoning channel: rationale, step line, state-gated summary, revision | Proposed |
| [0055](0055-pulse-plan-proposal-is-the-plan.md) | A proposed plan is the plan: typed proposal, planner decides what a task is | Proposed |
| [0056](0056-pulse-one-pipeline-no-fallthrough.md) | One pipeline: the model decides, code blocks or verifies, nothing falls through | Proposed |
| [0057](0057-pulse-declared-output.md) | Declared output is the only success (I1 output-fit; no invented export) | Proposed |
| [0058](0058-pulse-catalog-request-write.md) | Catalog `kind: request` is the remaining effect when output-fit blocks | Proposed |
| [0059](0059-pulse-named-pay-structure-get.md) | A pay-structure read is a named, closed GET; analytics stays headcount | Proposed |

<!-- Add a row per ADR. Keep newest at the bottom. -->
