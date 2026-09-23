# Design System Constitution — Enterprise UI/UX
# Read by: Frontend Worker (every session), Master Architect (when planning UI).
# Inspired by how top systems ship: Palantir Foundry, Ataccama, Linear, Stripe, Vercel.
#
# CORE PHILOSOPHY:
# A design system is a CONSTRAINT ENGINE, not a style guide.
# The rules physically prevent inconsistency, so 6 different LLM workers
# on 6 different models produce visually identical, professional output.

---

## The 3-Layer Model (NEVER skip a layer)

```
Layer 1: TOKENS       → colors, spacing, typography, radii, shadows, z-index
                        Single source of truth. NEVER hardcode a value.
Layer 2: PRIMITIVES   → Button, Input, Card, Badge, Table, Stack, Dialog
                        Built ONCE from tokens. Reused everywhere.
Layer 3: COMPOSED     → Feature components built by COMPOSING primitives.
                        Workers live here — they compose, they never restyle.
```

**The iron law:** A Frontend Worker COMPOSES existing primitives. They do NOT
invent new colors, spacings, or one-off styled buttons. If a primitive is
missing, that's a Master Architect decision to add to Layer 2 — not an ad-hoc fix.

---

## RULE 1 — Tokens, Never Magic Values

```jsx
// WRONG — hardcoded values (every worker picks different ones → chaos)
<Box sx={{ color: '#3b82f6', padding: '13px', marginTop: 17, borderRadius: '6px' }}>

// CORRECT — theme tokens (every worker gets identical output)
<Box sx={{ color: 'primary.main', p: 2, mt: 2, borderRadius: 1 }}>
```

- Colors: ONLY `theme.palette.*` (`primary`, `secondary`, `error`, `warning`, `success`, `info`, `text.primary`, `text.secondary`, `divider`, `background.paper`)
- Spacing: ONLY the 8px scale via `spacing()` / `sx` shorthand (`p`, `m`, `gap`). Never raw px.
- Radius: ONLY `theme.shape.borderRadius` multiples (`borderRadius: 1|2`)
- Typography: ONLY `variant="..."` — never raw `fontSize`/`fontWeight`
- Shadows: ONLY `theme.shadows[n]` / `boxShadow: 1..4`
- NEVER inline hex colors, rgb(), raw px spacing, or custom font sizes.

---

## RULE 2 — Reuse Before Create (enforced, not suggested)

Before creating ANY component, SEARCH for an existing one:

```bash
# Before writing a new button/card/table/dialog/badge:
grep -rn "export.*function.*Button\|export.*Card\|export.*Table" src/components/
ls src/components/         # scan existing primitives
```

- If a component exists → USE IT. Extend via props, never fork/duplicate.
- If it ALMOST fits → add a prop to the existing one (report to Master if it's shared).
- NEVER create `Button2`, `NewCard`, `CustomTable`. Duplication is how multi-agent frontends rot.
- One component = one file = one source of truth.
- Standard primitives already exist — reuse by name: `SystemDialog` (modal chrome), `MicroHelp` (tooltips), `FormField` (label-above-field), `SearchSelect` (the ONE searchable dropdown — see RULE 13), `FilteredDataGrid` (list shell), `PageContainer`, and `Wizard` (multi-step forms).

---

## RULE 3 — Density Is the Enterprise Signal

Top data platforms (Palantir/Ataccama) pack information. Consumer whitespace ≠ enterprise.

- Default to compact: `size="small"`, `density="compact"` on tables, inputs, buttons.
- Fixed, thin chrome: compact topbar, dense sidebars, tight table rows.
- Show more data per screen — pagination/virtualization over giant cards.
- Padding is deliberate, not decorative. No padding bloat.
- Numbers/IDs/timestamps in a monospace variant for scannability.

---

## RULE 4 — Every Data View Has 4 States (NEVER blank)

Any component that fetches data MUST handle all four:

```jsx
if (loading) return <LoadingState />;   // skeleton or spinner — never blank
if (error)   return <ErrorState onRetry={refetch} />;  // message + retry action
if (isEmpty) return <EmptyState />;     // "no data yet" + guidance, not blank
return <DataView data={data} />;        // loaded
```

- Loading: skeleton preferred over spinner for layout stability.
- Error: human message + retry, never a raw stack trace.
- Empty: explain why + what to do next.
- NEVER render a blank screen or a bare `null` while loading.

These 4 are the MINIMUM. The COMPLETE state matrix (page: `idle/loading/loading-empty/empty/loaded/partial/error/forbidden/stale`; component: `default/hover/active/focus/focus-visible/disabled/readonly/loading/submitting/optimistic/error/selected/checked/expanded/success`) is enumerated in `shared/frontend-ready.md` — a view is NOT ready until every applicable state is planned.

---

## RULE 5 — Status as First-Class Citizens

Enterprise UIs communicate state at a glance:

- Semantic color mapping is FIXED and consistent everywhere:
  - `success` = healthy/complete/online (green)
  - `warning` = degraded/pending/attention (amber)
  - `error`   = failed/offline/critical (red)
  - `info`    = neutral/informational (blue)
- Status = badge or dot + label. NEVER color alone (fails accessibility + colorblind users).
- Same status looks identical across every page. A "running" chip is the same chip everywhere.

---

## RULE 6 — Layout via Primitives, Not Margin Soup

```jsx
// WRONG — margin soup, brittle, inconsistent gaps
<div><Thing style={{ marginBottom: 12 }} /><Thing style={{ marginBottom: 12 }} /></div>

// CORRECT — layout primitives own the spacing
<Stack spacing={2}><Thing /><Thing /></Stack>
<Grid container spacing={2}><Grid size={{ xs: 12, md: 6 }}>...</Grid></Grid>
```

- Use `Stack`, `Grid`, `Box` with `gap`/`spacing` — not per-child margins.
- Spacing lives in the CONTAINER, not scattered on children.
- Alignment via flex props, not manual padding hacks.

---

## RULE 7 — Theme-Driven (dark/light ready, no hardcoded surfaces)

- All surfaces from `background.paper` / `background.default` — never `#fff`/`#000`.
- All text from `text.primary` / `text.secondary` — never hardcoded gray.
- A component must render correctly in BOTH themes without change.
- If the project has one theme now, still use tokens — future-proof and consistent.

---

## RULE 8 — Typography Hierarchy (limited, intentional)

- Use the theme's type scale via `variant` (`h1..h6`, `subtitle`, `body1/2`, `caption`, `overline`).
- Max ~5-6 distinct text styles on a screen. More = visual noise.
- Data/numbers/IDs: monospace variant. Labels: `caption`/`overline` uppercase.
- Never invent font sizes. Hierarchy comes from the scale, not random sizes.

---

## RULE 9 — Data Visualization Discipline

- Chart colors come from a FIXED categorical palette in the theme — not random per chart.
- The same series means the same color across all charts (e.g., "actual" always one color).
- Clear axes, units, and legends. No chartjunk, no 3D, no gratuitous gradients.
- Respect the semantic colors (actual vs predicted, above vs below) consistently.
- Tooltips show precise values; axes show rounded ticks.

---

## RULE 10 — Motion: Subtle, Fast, Purposeful

- Transitions 150–250ms, ease-out. Never slow, never bouncy-for-fun.
- Animate to communicate (state change, entry/exit), never to decorate.
- Respect `prefers-reduced-motion`.
- No layout-shifting animations on data load (use skeletons).

---

## RULE 11 — Accessibility Is Not Optional (WCAG AA)

- Every interactive element is keyboard reachable + has a visible focus ring.
- Icons-only buttons have `aria-label`.
- Color contrast ≥ 4.5:1 for text. Status never conveyed by color alone.
- Forms: labels tied to inputs, errors announced, required marked.
- Semantic HTML / ARIA roles for custom widgets.

---

## RULE 13 — Every Picker Is a Searchable Autocomplete

Enterprise pickers (governed enums, org units, employees, positions, domains,
owners, tags, countries, currencies…) are NEVER a raw `<Select>` / `<TextField select>`
with a wall of `<MenuItem>`s. A list of 5 is a dropdown; a list of 50+ is unusable
without search, and every picker needs to signal its async state.

- **ALWAYS use `SearchSelect`** (`src/components/Form/SearchSelect.jsx`) — the single
  searchable dropdown primitive. It provides, by default:
  - type-to-filter search (case-insensitive, partial, auto-highlight)
  - the 4 data states: loading spinner / error + Retry / empty guidance / loaded
  - clearable, keyboard-navigable, multiple, groupBy, i18n label/helper/required
- **Async options** are fed from `useReferenceOptions(setName)` (mdm.ReferenceSet) or the
  entity's list endpoint; pass `loading`/`error`/`onRetry` to `SearchSelect`. Never render
  a picker before its options resolve into one of the 4 states (a silent empty listbox is a
  defect — it reads as "no choices" when the real problem is a failed fetch).
- **Catalog Studio:** use `SearchSelect` for every entity/enum picker (domains, owners,
  stewards, tags, glossary, connection types, lineage edges, classifications) — same
  standard as `FilteredDataGrid` for lists. Do not leave bare MUI `Autocomplete` or
  raw `<Select>` walls in `src/pages/catalog/**`.
- **Elsewhere, a raw `<Select>` is acceptable ONLY for** a fixed, ≤~5 option, purely-local
  enum that cannot grow (e.g. log level: DEBUG/INFO/WARN/ERROR). Anything data-driven or
  open-ended → `SearchSelect`.

---

## RULE 14 — Every record list is a FilteredDataGrid

A page that lists records (admin tables, domain lists, inboxes, directories) is
`FilteredDataGrid` (`src/components/FilteredDataGrid.jsx`). It is not a raw MUI
`<Table>`, and it is not a bare `DataGrid` / `StandardDataGrid` with no query chrome.
Sort and paging alone are not enough.

Every such list has:

- **Search** across the fields a person would type (name, code, reference, path).
- **Relevant filters only** — the dimensions that actually split the list (type,
  parent, status, org unit, date range). Not a filter for every column. Filter
  pickers are `SearchSelect` (RULE 13), which `FilteredDataGrid` already uses.
- **Ordering** — column sort, with a default on the column people scan first.
- **Paging** — page size must be one of `rowsPerPageOptions`.
- The four data states (RULE 4). Row click highlights only; open, edit, and
  delete are explicit actions (`shared/compact-ui.md`).

A list that can grow past one page sends `q` and the active filters to the API
(`paginationMode="server"`). Client-side filter is only for a bounded set that
is already loaded.

Exceptions, and only these:

- A short key/value panel or a detail timeline of a handful of events, not a
  record list.
- A dialog that shows one already-chosen set of fewer than about eight rows
  may omit search and filters. If that set can grow, it still sorts and pages.

---

## RULE 12 — Consistency Over Cleverness

- The same action looks and behaves the same everywhere (predictability > novelty).
- Follow the existing pattern in the codebase **when that pattern is correct** — copy GOOD
  patterns for consistency, never propagate a bad one.
- If the nearest existing pattern violates a rule in this file, follow THIS file (best
  practice) and flag the old pattern as debt — don't replicate it for "consistency".
- A user should never have to relearn an interaction on a different page.
- When in doubt between two GOOD options, copy the nearest existing one — don't invent.

---

## Frontend Worker Pre-Flight Checklist (run before writing UI)

```
[ ] Searched src/components/ for an existing primitive to reuse
[ ] Confirmed I will use theme tokens (no hex, no raw px)
[ ] Confirmed MUI v6 Grid syntax (size={{...}}, no `item`)
[ ] Planned all 4 data states (loading/error/empty/loaded)
[ ] Status shown as badge/dot + label (not color alone)
[ ] Spacing via Stack/Grid gap, not per-child margins
[ ] Reviewed the reference component named in project.config.md for this project's look
[ ] Record lists use FilteredDataGrid — search, relevant filters, sort, paging (RULE 14)
```

## Anti-Patterns (instant reject in review)

- Hardcoded hex colors or raw px spacing
- Duplicated component (`Button2`, `CustomCard`)
- Raw `<Select>`/`<TextField select>` with hardcoded `<MenuItem>`s for a data-driven or
  open-ended enum/entity picker (use `SearchSelect` — RULE 13)
- A record list rendered as a raw `<Table>` or a bare DataGrid with no search and
  no relevant filters (use `FilteredDataGrid` — RULE 14)
- A picker whose listbox silently renders empty because options failed to load (missing
  loading/error/empty state)
- Blank screen while loading / no empty state
- Status shown by color with no label/icon
- Per-child `margin` instead of container spacing
- MUI v5 Grid props (`item`, `xs` as direct prop)
- Raw `fetch()` instead of the project API helper
- Inline date formatting instead of the project date util
- New one-off theme values instead of tokens
