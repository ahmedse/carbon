# Frontend Definition of Ready — The Screen Spec Gate
# Read by: Master Architect (authors the spec), Product/UX Designer (authors story/journey/acceptance),
#          Frontend Worker (consumes the spec — does NOT invent), QA/Validator (validates against it).
# Purpose: a page/view/component is NEVER coded before its spec is complete. This is the anti-spaghetti law.

---

## THE LAW (non-negotiable)

> **A page, view, or reusable component SHALL NOT be coded until its full spec is complete and approved.**
> The spec = story + journey + acceptance + composition + **complete state matrix** + data contract
> + a11y + performance + i18n. "Complete" means every one of the 9 artifacts below exists.

If a Frontend Worker is asked to build a view and the spec is missing or incomplete →
**STOP and report to Master Architect.** Do not improvise, do not "just start with the happy path."

Why: a view coded before its spec exists is how projects rot into spaghetti — every missing
state becomes a crash, every missed string becomes an English-in-Arabic bug, every missed
perf consideration becomes a janky table. The spec is cheap; the rework is not.

---

## The 9 Artifacts (all required before code)

| # | Artifact | Author | Source of truth |
|---|----------|--------|-----------------|
| 1 | User story + acceptance criteria | Product/UX Designer | `user-stories.md` |
| 2 | Journey / workflow map (if multi-step) | Product/UX Designer | `user-stories.md` |
| 3 | IA placement (nav location) | Product/UX Designer | `ux-patterns.md` |
| 4 | **Screen/component composition spec** | Master Architect | THIS file §Artifact 4 |
| 5 | **Complete state matrix** | Master Architect | THIS file §State Matrix |
| 6 | Data contract (endpoints, shapes, errors) | Master Architect | `api-contract.md` |
| 7 | Accessibility checklist (WCAG AA) | Master Architect | `design-system.md` RULE 11 |
| 8 | Performance envelope | Master Architect | THIS file §Performance |
| 9 | i18n / RTL plan | Master Architect | `frontend-worker.md` + RULE_8 |

---

## Artifact 4 — Screen/Component Composition Spec

Before coding, name the EXACT tree of components the view is made from, and for each
component its **props/API**, its **data source**, and its **states**. Never leave this to
the worker to improvise.

```markdown
## Screen: <Route> — <Title>
Owner: <role>   IA: <nav path>   Route: </carbon/...>

### Composition tree (primitives first — REUSE, never invent)
PageContainer
 └─ PageHeader (title, primary action = ONE button top-right)
 └─ StandardDataGrid  ← data source: GET /carbon-api/<resource>/
 │    props: rows, columns, getRowId, loading, density="compact"
 │    states: loading | empty | error | loaded | forbidden
 └─ <Domain>FormDialog  ← SystemDialog, NOT raw Drawer
      props: open, initialValues, onSubmit
      states: idle | submitting | error | success
      data source: POST /carbon-api/<resource>/

### Reuse audit (do this, don't skip)
- [ ] Searched src/components/ — no existing primitive duplicated
- [ ] Form uses SystemDialog (or the project's modal primitive), never raw Drawer/Dialog
- [ ] Data grid uses StandardDataGrid + getRowId, never raw table for >20 rows
- [ ] Feedback uses NotificationProvider.notify / notifyFromError, never alert()
```

---

## Artifact 5 — Complete State Matrix (canonical)

The 4 data states (loading/error/empty/loaded) are the MINIMUM. This is the FULL matrix.
Every page and every interactive component must enumerate which states it handles.

### Page-level (data fetching)
| State | Meaning | Required rendering |
|-------|---------|--------------------|
| `idle` | Not yet fetched | Nothing yet (or skeleton if imminent) |
| `loading` | First fetch in flight | **Skeleton** (preferred) or spinner — never blank |
| `loading-empty` | Fetch returned 0 rows | Skeleton then empty state |
| `empty` | No data exists | Empty state: explain WHY + next action ("Create first X") |
| `loaded` | Data present | The data view |
| `partial` | Some rows loaded/failed | Show loaded + a non-blocking warning for the failed part |
| `error` | Fetch failed | Human message + **retry action** — never a dead end |
| `forbidden` | 403 / no permission | Explain what's protected + what permission is needed |
| `stale` | Refreshing in background | Keep showing data + subtle progress indicator |

### Component-level (interaction)
| State | Example |
|-------|---------|
| `default` / `hover` / `active` / `focus` / `focus-visible` | buttons, links, rows |
| `disabled` / `readonly` | buttons, inputs — show WHY if possible |
| `loading` | inline spinner on the affected element |
| `submitting` | form button disabled + progress |
| `optimistic` | optimistic UI applied, pending server confirm |
| `error` | inline field error / operation failed |
| `selected` / `checked` / `expanded` / `open` | rows, checkboxes, accordions |
| `success` | post-action toast / inline confirm |

### The three "empty" states are DIFFERENT — never conflate
- **no data** ("you have no records yet — create one")
- **no results** ("your filter/search matched nothing — clear filters")
- **loading empty** (fetch succeeded but returned 0 — do NOT show "error")

---

## Artifact 8 — Performance Envelope

Perf is a spec, not an afterthought. State the budget for every view:

- **Route-level code splitting** — every namespace/page is `React.lazy()`-loaded; no single giant bundle.
- **Virtualize > ~200 rows** / paginate > ~50 rows (see `ux-patterns.md` Data Tables).
- **Memoize** expensive derivations (`useMemo`); **stable callbacks** (`useCallback`); no inline object/array props that bust `React.memo`.
- **Debounce** search (forgiving, 250–400ms); no fetch/parse per keystroke.
- **No N+1 API calls** from the frontend — batch or use a single list endpoint.
- **Images**: `loading="lazy"` + responsive sizes.
- **Web Vitals targets**: LCP < 2.5s, INP < 200ms, CLS < 0.1.
- **Bundle budget**: initial route chunk < ~250 KB gzip; flag any dependency that blows it.

---

## The Screen Spec Template (copy per view)

```markdown
## Screen Spec: <Route> — <Title>
Owner: <role>   IA: <nav path>

### Story
As a <role>, I want <goal>, so that <value>.

### Acceptance (Given/When/Then — happy + edges)
Scenario: happy path ...
Scenario: empty ...
Scenario: error ...
Scenario: permission ...

### Journey (if multi-step)
Entry → ... → Success   (note friction/drop-off points)

### Composition (Artifact 4)
<component tree + reuse audit>

### State Matrix (Artifact 5)
Page states: loading | empty | error | forbidden | loaded | partial
Component states: <list per interactive component>

### Data Contract (Artifact 6)
- GET  /carbon-api/<resource>/  → {count, results:[...]}  (DRF paginated)
- POST /carbon-api/<resource>/  → 201 {id,...} | 400 field errors | 403
- 403 semantics: <what the forbidden state shows>

### A11y (Artifact 7)
- [ ] keyboard reachable + focus-visible  [ ] icons have aria-label
- [ ] status = badge + label (never color alone)  [ ] forms: label + aria-live errors

### Performance (Artifact 8)
- lazy route?  virtualize/paginate threshold?  memoized?  debounce?  bundle budget?

### i18n / RTL (Artifact 9)
- [ ] every string via t() + key in BOTH en + ar catalogs
- [ ] directional icons mirrored in RTL  [ ] code/IDs/emails dir="ltr"
```

---

## Anti-patterns (instant reject — a view coded without its spec)

- A view/component built before Artifacts 1–9 exist
- A "happy path only" build — missing empty/error/loading states
- A form using a raw Drawer/Dialog instead of the project's modal primitive
- A string not wrapped in `t()` and missing from the AR catalog
- A table rendering hundreds/thousands of rows with no virtualization/pagination
- A full-page re-render on every keystroke (no debounce/memo)

---

*Source: ~/ai-toolkit/shared/frontend-ready.md — shared across all projects. This is the frontend
completion gate: a view is not "ready" until this spec is complete; a view is not "done" until it
satisfies this spec (validated by QA Layer 4).*
