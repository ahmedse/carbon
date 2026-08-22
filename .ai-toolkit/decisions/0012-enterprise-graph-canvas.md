# ADR-0012 — Enterprise Graph Canvas Primitive

- **Status:** Accepted
- **Date:** 2026-08-21
- **Deciders:** Master Architect
- **Area:** frontend

## Context

W3-F shipped a live plan DAG as a layered directed execution graph. Round-1/2/3
feedback escalated the requirements: nodes THEMSELVES must be movable + resizable
(not just the canvas), status must be visible *during* execution, and the whole
surface must look modern/enterprise — maximize, export, zoom, fit, redraw, reset —
"and all enterprise modern look and feel for graph/chart or anything visual."

Three forces required a decision before dispatch:
- **Interaction is hard to get right once, let alone N times.** Pan + wheel zoom +
  per-node move/resize + zoom-to-fit + PNG export + full-screen modal is a lot of
  SVG/DOM plumbing. Hand-rolling it per graph (PlanDagGraph, and the planned
  AgentTopologyGraph / KnowledgeGraphPanel / RunTimeline / future charts) would
  duplicate ~400 lines of fiddly code and drift out of sync.
- **Reuse-before-create is already the law** (RULE_2) and ADR-0011 already forbids
  new visualization deps (no React Flow / Recharts) and forbids a *second*
  hand-rolled d3 graph. Extending that principle from "one shared d3 core" to "one
  shared graph *surface*" is the same argument, one layer up.
- **Density is the enterprise signal** (RULE_3, `compact-ui.md`). The first cut was
  "rich but bulky" — thick status borders, a 52×13 status pill, 48px-tall nodes,
  generous gaps. Top systems (Linear, Temporal, GitHub Actions, Palantir) pack
  status into a hairline border + a small accent + a compact label, not a fat pill.

## Decision

1. **One shared surface primitive.** `src/components/graph/EnterpriseGraph.jsx`
   is the Layer-2 primitive that owns ALL graph interaction: movable canvas (pan),
   movable + resizable nodes, wheel zoom + toolbar zoom in/out/fit, redraw
   (re-layout), reset (zoom=1, pan=0), PNG export (SVG→canvas 2×), full-screen
   maximize modal, and live status pulse. Every graph/chart renders *through* it.
2. **Domain adapters, not forks.** A graph of a plan is a *thin adapter*
   (`PlanDagGraph.jsx`) that supplies domain data + a `renderNode` interior +
   an optional docked `sidebar` + `nodeColor`/`nodeAriaLabel`. The primitive stays
   presentational (no fetching). Future graphs (topology, run timeline, charts)
   add adapters — they never re-implement pan/zoom/export.
3. **Node geometry rides the layout.** `layoutExecutionGraph` emits `w`/`h` on each
   laid node so the primitive can render and (re)size nodes generically without
   re-deriving `EXEC_LAYOUT`. Resize/move are per-node overrides that `redraw`
   drops. **Overrides are MERGED onto the layout node (`{ ...n, ...o }`), never
   copied field-by-field** — a pure drag stores only `{x, y}` and a pure resize
   only `{w, h}`, so the unspecified fields must fall back to the layout geometry
   (a per-field copy writes `undefined` and collapses the node / emits `NaN`).
4. **Enterprise node styling, top-systems look.** Hairline (`divider`) border,
   `rx=6`, a 3px status accent bar on the left, title + compact UPPERCASE status
   label + tool/kind meta, and a pulsing outline only on `running` nodes. Status is
   label + accent (never color alone — RULE_5). No fat pills, no thick borders.
5. **No new dependencies.** Extends ADR-0011: `d3-*` + `mermaid` remain the only
   visualization deps; everything else is native SVG/DOM.

## Alternatives Considered

- **React Flow / Recharts / X6** — rejected; ADR-0011 already forbids new charting
  deps and adds bundle weight for behavior native SVG already covers.
- **Hand-roll pan/zoom/export in each graph component** — rejected; the exact
  drift risk this ADR exists to prevent (RULE_2, Composite pattern).
- **Keep the thick status pill + colored borders** — rejected; violates the compact
  density contract (`compact-ui.md`) and reads as "bulky" rather than "rich".
- **`d3-zoom`/`d3-drag` for the new surface** — rejected; native pointer events
  are sufficient, avoid coupling the primitive to d3, and keep it testable in jsdom.

## Consequences

- **Positive:** one identical, modern, enterprise look & feel for every graph and
  chart; interaction is written/tested once; adapters shrink to ~100 lines of
  domain data; no new deps; dense, scannable nodes that show live status.
- **Negative / trade-off:** the primitive is a single chokepoint — any change to
  interaction must be backward-compatible with existing adapters (`PlanDagGraph`,
  `ForceGraph` is intentionally left on its own d3 path for now).
- **Do NOT re-try:** a second hand-rolled SVG pan/zoom/export implementation
  outside `EnterpriseGraph.jsx`; a fat status pill / thick colored node border;
  per-graph hardcoded layout constants (ride `EXEC_LAYOUT` output instead);
  a per-field override copy (see Decision 3 — merge with spread).

## References

- `carbon-frontend/src/components/graph/EnterpriseGraph.jsx` — the primitive
- `carbon-frontend/src/components/graph/PlanDagGraph.jsx` — thin domain adapter
- `carbon-frontend/src/components/graph/ForceGraph.jsx` — d3-force primitive (kept)
- `carbon-frontend/src/utils/planGraph.js` — `EXEC_LAYOUT` + `layoutExecutionGraph`
- `.ai-toolkit/shared/compact-ui.md`, `.ai-toolkit/shared/design-system.md`
- `.ai-toolkit/decisions/0011-agent-catalog-graph-reuse.md` — no-new-deps lineage
- TASKS.md W3-F / W4-F
