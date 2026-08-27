# DESIGN — Contextual Inspector Drawer

> Unified global right drawer: Notes + context-relevant tabs (Health, Governance,
> Activity, Lineage, …). Replaces the per-page `EntityDetailShell` metrics panel.
> See **ADR-0019** for the decision summary.

**Status:** ✅ **Implemented (Phases A–D complete, 2026-08-27).** Phase E (config/persistence/a11y/perf polish) pending. **Owner:** Master Architect.

---

## 1. Problem

Two right-edge panels fight for the same edge, both resizable, both collapsible to a
rail, both persisting width/tab state:

| Panel | Where | Tabs | State |
|-------|-------|------|-------|
| Global Notes drawer | `Shell.jsx` (`NotesDrawer`/`NotesPanel`) | Notes (fixed) | open/pin/width/tab, context-aware |
| Per-page metrics panel | `EntityDetailShell` (3-col) via `useDetailPanel` | page-specific | open/width/tab/config (gear), per-page key |

The metrics panel is re-implemented across **14 pages** (`ModuleWorkspacePage`,
`MyDataPage`, `DataEntryPage`, `RowDetailPage`, and 9 catalog/admin detail pages),
each with its own hard-coded tab array and chrome. This is duplication and a UX smell:
users see two different "drawers" on the same edge and two different mental models.

**Goal:** one global, context-driven right drawer.

---

## 2. Research — top systems

| System | Pattern adopted |
|--------|-----------------|
| **VS Code** | Activity bar + **contribution points** (`registerWebviewViewProvider`): views register by id; the container shows the ones relevant to the active context. → our tab **registry**. |
| **Figma** | Right properties panel changes with selection (Design / Prototype / Inspect). → context-dependent tabs. |
| **Linear / Notion / GitHub** | Contextual right "inspector": comments, activity, metadata, sub-items — one surface, content follows selection. → Notes + Activity + Governance in one drawer. |
| **Chrome DevTools** | Dockable, resizable tabbed **drawer**. → drawer chrome + tab bar. |
| **Supabase / Retool / Hasura** | Right inspector shows table metadata / relationships / activity for the selected entity. → Health + Lineage + Governance tabs. |

**Design-system wisdom (IBM Carbon, Material 3, Ant Design, Polaris):**
- **One surface** for a given edge; don't stack two.
- **Context is a first-class signal** — panels derive from selection, not page.
- **Persist intent** (open/width/active-tab), **respect pin** (no surprise collapse).
- **Tokens only** (RULE_8), **compact density** (see `.ai-toolkit/shared/compact-ui.md`).
- **WAI-ARIA tabs** (`tablist`/`tab`/`tabpanel`, `aria-selected`), `role="complementary"`,
  visible focus, keyboard nav.

---

## 3. Principles adopted

1. **Single surface** — one drawer, one rail, one width/pin/tab state.
2. **Registry, not markup** — tabs register declaratively; the drawer composes them.
3. **Context-driven** — tabs appear because the active entity matches, not because a
   page hard-codes them.
4. **Self-contained tabs** — each tab fetches by `context.id`; no prop-drilling of page
   data into a global surface.
5. **Lazy + keep-mounted** — render only the active tab, but keep it mounted (avoid
   refetch flicker on tab switch).
6. **Graceful empty states** — every tab renders a useful empty state when there is no
   selection or no data.

---

## 4. Flaws avoided (anti-patterns)

| Flaw | How avoided |
|------|-------------|
| Two drawers on the same edge | Delete `EntityDetailShell` metrics panel; one drawer. |
| Context loss (tab doesn't know the entity) | `matches(context)` predicate + context-id fetch. |
| N+1 refetch on every tab switch | keep-mounted + per-tab cache keyed by context id. |
| Tab explosion (too many tabs) | `matches()` filters to relevant; user can hide tabs (gear). |
| Surprise collapse when context changes | preserve existing pin semantics (`NotesContext`). |
| Blank/flicker on switch | skeleton + keep-mounted. |
| a11y gaps | ARIA tab pattern + keyboard + `role="complementary"`. |
| State duplication | single persisted key namespace `carbon-inspector-*`. |

---

## 5. Target architecture

```
Shell.jsx
 └─ <InspectorProvider>           // drawer chrome state + registry + active context
     └─ <InspectorDrawer>         // collapsed → <InspectorRail/> ; open → resizable panel
         └─ <InspectorPanel>      // header (pin/collapse) + tab bar + body
             ├─ Tab "Notes"       // NotesTab (uses NotesContext data layer)
             └─ Tab* (context)    // Health / Governance / Activity / Lineage / Impact …
                                  //   auto-added from InspectorTabRegistry.matches(ctx)
```

### 5.1 Registry (singleton, mirrors `WidgetRegistry.js`)

```js
// inspector/InspectorTabRegistry.js
const registry = new Map(); // id -> provider

export function registerInspectorTab(provider) {
  registry.set(provider.id, provider);
}
export function tabsFor(context) {
  return [...registry.values()]
    .filter((p) => !p.matches || p.matches(context))
    .sort((a, b) => (a.order ?? 100) - (b.order ?? 100));
}
```

Provider shape:
```js
{
  id: 'health',
  label: () => t('inspector.tabs.health'),
  icon: MonitorHeartIcon,
  order: 10,
  matches: (ctx) => ctx?.entityType === 'module',
  render: (ctx) => <ModuleHealthTab context={ctx} />,
}
```

### 5.2 Context

Extend the existing notes context signal — `NotesContext.setContexts([{entityType,
entityId, label, payload}])` — as the **single source of truth**. `payload` carries the
entity object(s) a tab needs before it self-fetches (optional fast-path).

New `InspectorContext` owns: `open`, `pinned`, `width`, `activeTab`, tab-visibility
`config`, and reads `contexts` from `NotesContext`. Persisted keys migrate
`carbon-notes-*` → `carbon-inspector-*` (read old key once for continuity).

### 5.3 Drawer chrome

- **Rail (collapsed):** slim edge button (today's `NotesRail`) — generic label
  "Inspector", opens the drawer.
- **Panel (open):** header (pin + collapse) + scrollable tab bar + body.
- **Resize:** keep the existing edge-drag handle (LTR/RTL-aware).
- **Config (gear):** per-tab show/hide persisted per user (adopt `useDetailPanel`'s
  config concept into the inspector).

---

## 6. Migration plan (phased, each independently shippable)

### Phase A — Foundation (no behavior change) ✅ **Done**
- Create `InspectorTabRegistry` + `InspectorContext`/`InspectorProvider`.
- Generalize `NotesPanel` → `InspectorPanel` (Notes fixed first tab; registry tabs
  appended); rename `NotesDrawer` → `InspectorDrawer`, keep `NotesRail`/`InspectorRail`.
- Wire into `Shell.jsx`. At this stage only "Notes" still renders. No regression.

### Phase B — Pilot: `ModuleWorkspacePage` ✅ **Done**
- Convert its 4 tabs (Health / Lineage / Governance / Activity) into registered,
  self-contained inspector tabs (`entityType: 'module'`).
- Page sets context (`setContexts`) with module payload instead of rendering
  `EntityDetailShell` metrics panel.
- Delete `useDetailPanel` usage + metrics panel from this page.
- Parity check: same tabs, same data, same config, same collapse behavior.

### Phase C — Migrate the remaining 13 pages ✅ **Done**
- `MyDataPage` (Trust/Impact/Activity), `DataEntryPage`, `RowDetailPage`,
  `OrgUnitDetailPage`, `AssetDetailPage`, `DataProductDetailPage`,
  `DataSourcesDetailPage`, `DomainDetailPage`, `ExportsDetailPage`,
  `ImportsDetailPage`, `ReferenceSetDetailPage`, `TagDetailPage`, `RuleDetailPage`,
  plus `CalculationsPage` (entityType `calculation`) — 14 pages total.
- Each: register tabs (with `matches`), set context, drop metrics panel.

### Phase D — Deprecate & delete ✅ **Done**
- Removed `useDetailPanel` and the `EntityDetailShell` three-column path (both files
  deleted — no importers remained).

### Phase E — Polish (config, persistence, a11y, perf) — pending
- Per-entity-type remembered active tab; per-user tab visibility (gear).
- Lazy render + keep-mounted + per-context cache.
- ARIA tabs, keyboard nav, `role="complementary"`.
- Per-tab empty states + skeletons.

---

## 7. Definition of Done

- [x] One global drawer; `EntityDetailShell` metrics panel fully removed.
- [x] Tabs auto-discover from context (no page hard-codes the tab bar).
- [x] Notes behavior (contexts, reactions, comments, pin) unchanged — existing
      `notes.drawer.test.jsx` / `EmissionsDashboard.notes.test.jsx` still green.
- [x] New unit tests: registry matching, drawer tab composition, config persistence,
      a11y (roles/labels), self-fetching tabs.
- [x] `npm run lint` + `npm run build` green; Playwright smoke on 2 migrated pages (en + ar) — pending (Phase E).

## 8. Open questions (to confirm before Phase B)

1. **Self-fetch vs. payload fast-path** — prefer self-fetch (decoupled); confirm we accept
   the extra fetch on first open of a tab (mitigated by keep-mounted + cache).
2. **Tab ordering** — Notes first, then Health, Governance, Activity, Lineage, Impact?
3. **Bottom panel later?** (VS Code style) — out of scope now; ADR leaves the door open.
