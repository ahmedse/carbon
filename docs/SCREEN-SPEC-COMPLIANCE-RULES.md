# Screen Spec — People Config, Compliance rules
# Canonical per `.ai-toolkit/shared/frontend-ready.md`.
# Surface: existing People Config → Compliance tab. No new app, no new route.

---

## Artifact 1 — User story + acceptance

**Story:** As a people lead, I want to draft a compliance rule, have a different person publish it, and keep a published version unchanged, so payroll lineage keeps naming the version that was in force.

**Acceptance:**

- **Loaded:** The Compliance tab lists rules in a FilteredDataGrid with search, a status filter (Draft / In review / Authoritative / Superseded), column sort, and paging.
- **Row click:** Highlights the row only. It does not open the editor.
- **Draft:** People lead can create and edit a draft. Divisor, fraction, and cap are structured fields. Full JSON is behind an advanced disclosure.
- **Submit:** Freezes the draft (In review). Edit and delete are refused.
- **Publish:** Opens a SystemDialog with example results, floor results, citation, and the active-employee count. A second people:manage user publishes. The drafter is refused.
- **Published:** Edit copies forward to the next draft version. Delete is refused.
- **Error:** A failed save or publish leaves the form values in place and shows the server detail.
- **Empty / error / loading:** Empty state with New version, error with retry, loading skeleton. No blank body.
- **Access:** people:view lists. people:manage writes. Chat does not publish.

---

## Artifact 2 — Journey

```
People Config → Compliance tab
  loading skeleton → empty | error+retry | loaded grid
  New version / Edit draft → SystemDialog
       save → toast, refresh
       validation or 409 → dialog stays, values kept
  Submit (draft) → In review
  Publish (in review) → SystemDialog preview → confirm
       second person → Authoritative
       same person → 403 sod_same_actor, dialog stays
  New version (authoritative) → next draft, source row unchanged
```

---

## Artifact 3 — IA

Existing People Config tabs (Overview, Reference, Compliance, Compensation). No new route. No `studioFromPath` change.

---

## Artifact 4 — Composition

```
ComplianceRulesPanel (tab body, embedded)
├─ Header row: title + Button "New version" size="small"
├─ FilteredDataGrid embedded
│    search, status SearchSelect, sort, pageSize 25, density compact
│    onRowClick → highlight only
│    row actions: Edit draft | Submit | Publish | New version | Delete draft
├─ Draft SystemDialog
│    FormField + SearchSelect (jurisdiction, category)
│    divisor, fraction numerator/denominator, cap months
│    Accordion: advanced JSON
└─ Publish SystemDialog (preview) and Delete SystemDialog
```

Reuse: FilteredDataGrid, SystemDialog, FormField, SearchSelect, LoadingSkeleton, ErrorAlert, EmptyState. No ConfirmDialog. No is_authoritative Switch. No raw table.

---

## Artifact 5 — State matrix

| State | Rendering |
|---|---|
| loading | LoadingSkeleton variant table |
| error | ErrorAlert + retry |
| empty | EmptyState + New version |
| loaded | FilteredDataGrid |
| filter empty | Grid empty copy |
| saving | Save disabled, values kept |
| publish preview loading | Dialog body skeleton text |
| publish refused | Dialog stays, server detail shown |

---

## Artifact 6 — Data contract

- `GET /carbon-api/people/compliance-rules/` → `{count, results[]}`. `lifecycle` is read-only.
- `POST` creates a draft. `is_authoritative` is ignored.
- `PATCH /compliance-rules/{id}/` drafts only. Authoritative or in-review → 409 `immutable_rule` or `frozen_draft`.
- `DELETE` drafts only → 409 `immutable_rule` otherwise.
- `POST .../copy-forward/` from a published row → 201 draft.
- `POST .../submit/` → in review.
- `GET .../preview/` → examples, floors, citation, active_employees.
- `POST .../publish/` → 200, or 403 `sod_same_actor` / `sod_missing_preparer`, or 409 `examples_failed` / `floor_failed` / `citation_required`.

---

## Artifact 7 — Accessibility

Labels on every field. Icon buttons have aria-labels. Status is a text chip, not color alone. Dialogs trap focus via SystemDialog. Keyboard sort on the grid.

---

## Artifact 8 — Performance

The catalog is small. Client-side filter and page size 25. No unbounded second fetch on row click.

---

## Artifact 9 — i18n

New strings in `en/people.json` and `ar/people.json`. No hardcoded English in the panel beyond translation keys.
