# UX Interaction Patterns
# Read by: Product/UX Designer + Frontend Worker. The behavioral counterpart to design-system.md.
# design-system.md = how it looks. THIS = how it behaves. Reuse these patterns; never reinvent.

---

## Navigation & Information Architecture
- **One primary navigation model per app** (sidebar OR top-tabs) — never both competing.
- App-internal navigation = **tabs inside the page**, not new drawer entries (see project.config.md → NAVIGATION_PATTERN).
- Max 2 levels deep before it needs restructuring. Deep nesting = IA failure.
- Every screen answers: where am I, what can I do here, how do I get back.
- Breadcrumbs for depth > 1. Active state always visible in nav.

## Page Anatomy (consistent skeleton every screen)
```
[ Header: title + primary action (top-right) + context/filters ]
[ Body:   the 4 data states — loading / error / empty / loaded  ]
[ Footer/pagination if list ]
```
Primary action is ONE button, top-right, semantic color. Secondary actions are subtler.

## Forms
- **Label above field.** Inline validation on blur, not only on submit.
- Show the error next to the field + a summary if many. Never a raw stack trace.
- Required fields marked; optional is the exception, not the rule (Principle 7).
- Disable submit only when truly invalid; show WHY it's disabled.
- Preserve input on error — never clear a form the user spent time on.
- Destructive/irreversible submit → confirmation with the consequence spelled out.

## Data Tables & Lists (enterprise density)
- Compact by default; column choices reflect the user's scan priority (id, status, key metric, time).
- Sort on the columns that matter; persist sort/filter in the URL for shareability.
- Row actions on hover or in an overflow menu — not a wall of buttons per row.
- Empty state explains why + offers the next action (e.g., "Create your first model").
- Pagination or virtualization for > ~50 rows; never render thousands blindly.
- **DataGrid unique id**: `StandardDataGrid` (MUI X) throws `rows must have a unique id` when API rows lack a top-level `id`. For non-CRUD payloads (predictions keyed by `prediction_id`, slow-movers by `item_code`, analytics rows) ALWAYS pass `getRowId={(row) => row.<unique-key>}`. Example: `getRowId={(row) => row.prediction_id ?? row.customer_code}`.

## Feedback & System State
- **< 100ms:** optimistic UI or instant local response.
- **100ms–1s:** inline spinner on the affected element.
- **> 1s:** skeleton + progress; keep the rest of the UI interactive.
- Success → brief toast/inline confirm. Error → persistent, actionable message.
- Long jobs → show progress + let the user leave and come back (status surface).

## Destructive & Irreversible Actions
- Confirm with a modal that NAMES the consequence ("Delete 3 models permanently?").
- Prefer **undo** (soft delete + snackbar) over confirm dialogs where feasible.
- Type-to-confirm only for high-blast-radius ops (delete project, drop data).

## Search, Filter, Empty
- Search is forgiving (debounced, case-insensitive, partial). Show result count.
- Filters are visible, removable chips; "clear all" always available.
- No-results empty state differs from no-data empty state — say which and how to proceed.

## Notifications & Errors
- Transient success = toast (auto-dismiss). Actionable/error = inline or persistent.
- Never stack modal on modal. Never block the app for a non-critical message.
- System/network errors: human sentence + retry, log detail for the debugger — not the user.

## Multi-Step / Wizards
- Show total steps + current position. Allow back without data loss.
- Validate per step; don't dump all errors at the end.
- Save draft state so a refresh doesn't destroy progress.

## Keyboard & Power Users
- All primary actions keyboard-reachable; visible focus ring (design-system RULE 11).
- Common shortcuts consistent across apps (search, save, new). Document them.

## Responsive & Density
- Design for the primary device first (enterprise = desktop-dense), degrade gracefully.
- Reflow, don't hide critical actions on smaller widths. Tables → cards on narrow screens.

## Conversational & AI Surfaces (chat, agents, copilots)
- Model the density of VSCode Copilot Chat: **content-first, chrome on hover**.
- Message stream shows content only; actions (copy / retry / feedback / menu) appear in a
  hover toolbar on the message, never as an always-on button row.
- No technical noise in the stream: raw latency (`3886ms`), token counts, and cost live in
  a tooltip/menu — never as a bare inline chip.
- Status is exceptional, not ambient: show a chip ONLY on failure/interrupted, not a
  standing "AI"/"You" caption on every message.
- Sessions are first-class: grouped by time (Today / Yesterday / 7 days / Older),
  collapsible, with per-item hover actions (rename / pin / archive / delete) and
  relative timestamps.
- Empty/zero-count toggles (e.g. "Archived (0)") are hidden entirely when N === 0.
- Markdown responses render through a dedicated renderer; never dump raw markdown into a `<p>`.
- Input bar: comfortable min/max rows, Enter=send / Shift+Enter=newline, a stop/interrupt
  control while streaming that swaps to retry on completion.
- A "what went into this answer" (provenance/context) affordance is a small ⓘ hover target,
  not always-visible noise.

---

## Anti-patterns (instant reject in UX review)
- Blank screen while loading (use skeleton). Dead-end error with no next step.
- A form that clears on error. A destructive action with no confirm/undo.
- Two navigation models competing. Color-only status. Modal-on-modal.
- Reinventing an interaction that already exists elsewhere in the app.

---

*Source: ~/ai-toolkit/shared/ux-patterns.md — shared across all projects*
