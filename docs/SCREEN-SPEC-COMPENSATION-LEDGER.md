# Screen Spec — Compensation Ledger (Employee Pay Tab)
# Canonical per `.ai-toolkit/shared/frontend-ready.md` (RULE_29 — Frontend Definition of Ready).
# This is the FIRST spec authored under the Screen Spec Gate. A worker does NOT code this view
# before all 9 artifacts below are complete. Consumed by TASKS.md Phase NIR-7B.

---

## Artifact 1 — User Story + Acceptance

**Story:** As an HR/payroll user with compensation access, I want to view an employee's
compensation ledger (earnings, deductions, net monthly) and — if I can manage payroll —
append a new effective-dated line, so that the ledger is the single audited source of truth
for what an employee is paid.

**Acceptance (Given/When/Then):**

- **Happy path (view):** Given a user with `people:view_compensation`, when they open the
  Pay tab, then they see Earnings + Deductions sections (each with a monthly total), a Net
  Monthly bar, and a History accordion of all lines, newest first.
- **Empty:** Given an employee with no active lines, when the tab loads, then the user sees an
  explicit empty state ("no active compensation lines") — and, if they can manage, a
  "Add First Component" action.
- **Error:** Given the ledger fetch fails, when the tab renders, then the user sees a friendly
  error with a Retry action (never a blank screen, never a raw stack trace).
- **Forbidden:** Given a user WITHOUT `people:view_compensation`, when the tab loads, then they
  see a protected-data notice (no amounts revealed).
- **Add line (manage):** Given a user with `people:manage`, when they open "Add Component",
  fill component/amount/currency/frequency/effective-start/reason, and submit, then the line is
  appended, the prior open line for that component is closed, a success toast confirms, and the
  ledger refreshes.
- **Add line (validation):** Given a required field is missing or the amount is invalid, when
  the user submits, then they see an inline error and the form is NOT cleared (input preserved).
- **Permission:** Given a user with `people:view_compensation` but NOT `people:manage`, then the
  "Add Component" / "Add First Component" buttons are NOT rendered.

---

## Artifact 2 — Journey Map

```
Employee detail page → "Pay" tab
   └─ (fetch ledger) → [loading skeleton] → one of:
        ├─ forbidden → protected notice (terminal)
        ├─ error    → message + Retry → (re-fetch)
        ├─ empty    → empty state + "Add First Component" (manage only)
        └─ loaded   → Earnings/Deductions + Net Monthly + History
                          └─ (manage) "Add Component" → SystemDialog
                                ├─ fill + submit → success toast → close → refresh (stale→loaded)
                                └─ validation error → inline error, form preserved
```
Friction points to watch: (1) the reveal is audited — do not over-fetch; (2) closing the
previous open line is a server-side side effect — surface it via the refreshed history, not a
client-side guess; (3) the form must not wipe input on error.

---

## Artifact 3 — IA Placement

- Live inside the **Employee detail page** as a tab (`src/apps/people/tabs/EmployeePayTab.jsx`),
  switched via the existing MUI `<Tabs>` + `<Tab>` pattern (BaseDetailPage) — **not** the sidebar,
  **not** a new route. No `studioFromPath()` / `App.jsx` route change.
- Primary action ("Add Component") = ONE button in the ledger header (top-right), per
  design-principles #11 (deliberate actions; no ambiguous row-click side effects).

---

## Artifact 4 — Composition Spec (reuse, never invent)

```
EmployeePayTab  (rendered inside the existing employee detail tab shell)
├─ Ledger header          → Typography (title + "as of <date>") + ONE Button "Add Component" [manage only]
├─ Earnings LedgerSection → Paper + Table (component, amount, frequency, period, verified badge)
├─ Deductions LedgerSection → Paper + Table (same shape)
├─ Net Monthly bar        → Paper (Gross · Deductions · Net Monthly, tabular-nums)
├─ History Accordion      → MUI Accordion + Table (component, direction chip, amount, period, status chip)
└─ AddCompLineDialog      → SystemDialog (src/components/SystemDialog.jsx)  ← NOT raw Drawer
    └─ Form (Stack): Component Select · Amount TextField(number) · Currency Select ·
       Frequency Select · Effective Start TextField(date) · Reason TextField(multiline)
```

**Reuse audit (mandatory):**
- [x] Dialog = `SystemDialog` (`src/components/SystemDialog.jsx`) — matches all sibling people pages.
- [x] Empty state = `EmptyState` (`src/components/Page/EmptyState.jsx`).
- [x] Feedback = `useNotification()` → `notify` (success) / `notifyFromError` (error). Never `alert()`.
- [x] Loading = MUI `Skeleton` (not `CircularProgress`).
- [x] Amounts/dates/status = `formatAmount` / `formatDate` / `statusColor` / `statusLabelKey` from `../utils`.
- [x] Chips = theme `MuiChip` overrides (density), NOT inline `height`/`fontSize`.
- [x] API = `src/api/people.js` (via `apiFetch`) — `fetchCompensationLedger`, `createCompensationLine`,
      `fetchCompensationComponents`. Remove the dead `revealEmployeeCompensation` duplicate.

---

## Artifact 5 — Complete State Matrix

### Page (data fetching)
| State | Rendering |
|-------|-----------|
| `idle` | Nothing (or skeleton if imminent) |
| `loading` | **Skeleton** (rows) — never a bare spinner, never blank |
| `loading-empty` | Skeleton → empty state |
| `empty` | `EmptyState` + "Add First Component" (manage only) |
| `loaded` | Earnings/Deductions + Net Monthly + History |
| `partial` | Show loaded lines + non-blocking warning if a section failed |
| `error` | Friendly message + **Retry** action |
| `forbidden` (403) | Protected-data notice (no amounts) |
| `stale` | Keep showing data + subtle progress while refreshing after an add |

### Component (interaction)
| State | Where |
|-------|-------|
| `default/hover/active/focus/focus-visible` | Buttons, selects, accordion summary |
| `disabled` | "Add Component" hidden for non-manage; form buttons disabled while submitting |
| `readonly` | Ledger table cells |
| `loading` | Component Select while `fetchCompensationComponents` resolves |
| `submitting` | Dialog submit button disabled + progress; ledger enters `stale` |
| `optimistic` | *(not required here — append is confirmed by server, not optimistic)* |
| `error` | Inline field/Alert in dialog (form preserved) |
| `selected/checked/expanded` | History accordion open/closed |
| `success` | Success toast → close dialog |

**The three empty states are DISTINCT — never conflate:**
no-data ("no active lines — add the first") vs no-results ("filter matched nothing") vs
loading-empty (fetch returned 0 — show empty, not error). This view has **no-data** only (no filters).

---

## Artifact 6 — Data Contract

All via `apiFetch` (JWT refresh), base `/carbon-api/people/` (`ROOT = 'people/'`).

| Op | Endpoint | Request | Response |
|----|----------|---------|----------|
| Ledger | GET `employees/<id>/compensation/` | — | `{ employee_id, as_of, revealed_by, totals:{monthly_earnings, monthly_deductions, net_monthly}, current:[Line], history:[Line], basic_salary }` |
| Add line | POST `employees/<id>/compensation/` | `{ component(id), amount, currency, frequency, effective_start, reason_note }` | `201 Line` |
| Components | GET `compensation-components/` | optional `?direction=` | list of `{ id, code, name, name_ar, direction, ... }` (may be paginated `{results:[...]}`) |

`Line` (EmployeeCompensationSerializer): `id, employee, component, component_code, component_name,
component_direction, component_is_eosi_base, component_is_gosi_base, component_sort_order, amount,
currency, frequency, effective_start, effective_end, source_rule, source_plan, reason_event,
reason_note, is_verified, verified_by, verified_by_name, verified_at, created_at, created_by,
created_by_name`.

- Direction classifier = `component_direction` from the API (`earning`/`deduction`). **Do NOT**
  hand-roll `EARNING_TYPES`/`DEDUCTION_TYPES`/`isEarning`.
- `403` = forbidden (protected notice). `400` = field validation (inline, form preserved).
- The verify endpoint (`POST employees/<id>/compensation/<line_id>/verify/`) is **out of scope**
  for NIR-7B (no UI action wires to it yet) — flagged, not implemented.

---

## Artifact 7 — Accessibility (WCAG AA)

- [x] Form controls: `FormControl`/`InputLabel` + `label` tied to each `Select`/`TextField`.
- [x] Icon-only buttons have `aria-label`.
- [x] Status never color-alone: `VerifiedBadge` = icon + label; `DirectionChip` = text label.
- [x] Keyboard reachable + visible `focus-visible` on every interactive element.
- [x] Errors announced: form error via `Alert` (role=alert) / `aria-live`; no silent failure.
- [x] Contrast ≥ 4.5:1 via theme tokens (no raw hex).
- [x] Amounts/IDs/codes rendered `dir="ltr"` (Arabic must not mirror them).

---

## Artifact 8 — Performance Envelope

- [x] Single GET for the ledger (no N+1); components list is fetched **lazily** only when the
      dialog opens.
- [x] Per-employee line counts are small — no virtualization/pagination required here.
- [x] `useMemo` for the earnings/deductions split + totals render; stable callbacks (`useCallback`)
      for the form handlers.
- [x] No search input → no debounce needed.
- [x] Route already lazy-loaded via the app manifest; no new bundle weight.
- [x] No `if (!ledger) return null` (blank frame) — all states rendered.

---

## Artifact 9 — i18n / RTL

- [x] Every user-facing string via `t()` (react-i18next), keys in **both** `en` and `ar`
      people catalogs. Coverage: "Verified"/"Pending", "Earning"/"Deduction", "Open"/"Closed",
      "Compensation Ledger", "Earnings", "Deductions", "Gross Monthly"/"Total Deductions"/
      "Net Monthly", "History", "No historical lines.", "No active compensation lines.",
      "Add Component"/"Add First Component"/"Cancel"/"Add", "Component"/"Amount"/"Currency"/
      "Frequency"/"Monthly"/"Annual"/"Effective Start"/"Reason / Note", protected-data notice.
- [x] `node scripts/check-i18n-keys.js` → 0 missing keys (no silent `fallbackLng` to en in ar).
- [x] Directional icons mirrored in RTL (via `LanguageProvider`); `dir`/`lang` never hardcoded.
- [x] `dir="ltr"` on amount/code/ID cells.

---

## Anti-patterns (instant reject — do NOT ship these)

- Raw `Drawer` instead of `SystemDialog`; raw `fontSize`/`height`/`width`/`bgcolor` literals.
- Bare `CircularProgress` instead of skeleton; `if (!ledger) return null`.
- Error `Alert` with no Retry; form cleared on validation error.
- `EARNING_TYPES`/`DEDUCTION_TYPES`/`isEarning` classifier (use `component_direction`).
- Dead `revealEmployeeCompensation` left in `src/api/people.js`.
- Hardcoded English strings not `t()`-wrapped.

*Source: `docs/SCREEN-SPEC-COMPENSATION-LEDGER.md` — authored by Master Architect under RULE_29.*
