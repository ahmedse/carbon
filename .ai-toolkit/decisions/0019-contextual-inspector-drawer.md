# ADR-0019 — Contextual Inspector Drawer: unify Notes + per-page metrics panels

- **Status:** Accepted (Phases A–D implemented, 2026-08-27; Phase E polish pending)
- **Date:** 2026-08-27
- **Deciders:** Master Architect
- **Area:** frontend
- **Extends:** ADR-0012 (shared surface primitives), ADR-0010 (domain-neutral core)

## Context

The platform has **two right-edge panels competing for the same edge**:

1. **Global Notes drawer** — `NotesDrawer`/`NotesPanel` (docked in `Shell.jsx` via
   `DOCKED_PANES`). Has a tab bar (today only "Notes"), entity-context awareness
   (`NotesContext.setContexts`), pin/unpin, resizable, persisted state, and a collapsed
   rail. Its code already anticipates "more tabs (governance history, …)".
2. **Per-page metrics panel** — `EntityDetailShell` three-column layout driven by
   `useDetailPanel`. Hard-coded tabs per page (ModuleWorkspace: Health/Lineage/
   Governance/Activity; MyData: Trust/Impact/Activity; DataEntry; RowDetail; and 9+
   catalog/admin detail pages). Each page re-implements tab chrome, config (gear),
   width persistence, and a collapse rail — **~14 near-duplicate implementations**.

The user asked to remove the per-page panel and unify it with the global drawer.

## Decision

1. **One global right drawer** — rename/generalize the Notes drawer into a
   **Contextual Inspector Drawer**. Notes stays the fixed first tab; context-relevant
   tabs (Health, Governance, Activity, Lineage, Impact, …) appear based on the active
   entity, not on the page.
2. **Registry-based tab discovery (contribution-point pattern)** — a singleton
   `InspectorTabRegistry` (mirrors the existing `WidgetRegistry.js` singleton). A tab
   declares `{ id, label, icon, matches(context), render(context) }`. The drawer
   computes visible tabs = `[notes, ...registry.matches(activeContext)]`.
3. **Context is the single source of truth** — reuse the existing `NotesContext`
   `setContexts` signal (entityType/entityId/label). Pages that today render a metrics
   panel instead **set the inspector context**; tabs appear automatically. Tab
   components become **self-contained** (fetch by context id) so they work regardless
   of which page set the context.
4. **Keep the Notes data layer** (`NotesContext` notes caches/reactions/comments)
   intact; add a thin `InspectorContext` for drawer chrome (open/pin/width/activeTab),
   the registry, and tab visibility config. The persisted UI keys migrate over.
5. **Delete** `useDetailPanel` + the `EntityDetailShell` three-column path once all
   pages migrate (keep the simple legacy layout if still referenced).

## Alternatives Considered

- **Option A — keep two panels, "link" them** (hide one when other opens). Rejected:
  still two chrome surfaces, duplicated state, and no single context model.
- **Option B — render page tabs INTO NotesPanel as children** (prop-drill per page).
  Rejected: couples the global drawer to page layout, reintroduces duplication, and
  doesn't give a "smart" auto-discover context behavior.
- **Option C — a bottom dockable Panel (VS Code style) instead of a right drawer.**
  Rejected for now: the existing Notes drawer + right-docked Pulse pane already commit
  the right edge; a bottom panel would add a third surface and a larger migration.

## Consequences

- **Positive:** one surface, one context model, ~14 duplicated panels deleted; tabs
  auto-discover from context; config + persistence centralized; consistent a11y.
- **Negative / trade-off:** migration touches all detail pages; tab components must be
  refactored from prop-driven (`module/tables/token`) to context-id-driven (self-fetch).
- **Do NOT re-try:** per-page hard-coded tab arrays; two parallel right drawers;
  prop-drilling page data into a global drawer.

## References

- `docs/DESIGN-CONTEXTUAL-INSPECTOR-DRAWER.md` (full research + migration plan)
- `carbon-frontend/src/notes/NotesContext.jsx`, `NotesDrawer.jsx`, `NotesPanel.jsx`
- `carbon-frontend/src/components/entity/EntityDetailShell.jsx`, `useDetailPanel.jsx`
- `carbon-frontend/src/config/WidgetRegistry.js` (registry singleton precedent)
