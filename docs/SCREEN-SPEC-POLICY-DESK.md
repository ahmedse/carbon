# Screen Spec — Policy desk (Data Trust admin)

Canonical per `.ai-toolkit/shared/frontend-ready.md`. The lifecycle desk is a Data Trust admin surface. The People app remains the control plane for payroll fields. This spec is the contract for `/catalog/policy-versions`.

---

## Artifact 1 — User Story + Acceptance

**Story:** As a platform admin who administers Data Trust, I want one desk that lists every policy version, shows its state, and publishes only after I see the diff, the example result, and the floor result, so that the person who prepared the version cannot publish it.

**Who:**

| Action | Who | Capability |
|--------|-----|------------|
| Create and edit a draft, submit it | People lead on People Config → Compliance | `people:manage` (`people_lead`) |
| List, submit, publish on this desk | Platform admin and catalog lead | `catalog:manage_policies` |

`catalog:manage_policies` is the existing Data Trust capability “Manage Governance Policies”. The `admin` and `admins_group` wildcards include it. `catalog_lead` holds it directly. `people_lead` does not. No new permission name.

**Acceptance:**

- **List:** Given a user with `catalog:manage_policies`, when they open the desk, then they see policy, version, state, citation, and effective date. States are Draft, In review, Authoritative, and Superseded.
- **Find:** Search, a state filter, column sort, and paging are on the grid.
- **Highlight:** A row click highlights that row and does not publish.
- **Publish:** An explicit Publish action opens a SystemDialog with the diff, example pass or fail, floor pass or fail, and the latest governance event. Confirm runs publish.
- **Same actor:** Given the publisher is the preparer, when they confirm, then the desk shows the refusal and the version stays In review.
- **People:** The People Compliance tab can create and submit drafts. It has no Publish button. In-review rows link to this desk.
- **Copy:** Desk labels are policy, version, state, floor, citation, and governance event. The desk does not name a country, a pay process, or a brand.

---

## Artifact 2 — Journey Map

```
Catalog → Policy versions
   └─ (fetch versions) → [skeleton] → one of:
        ├─ error → message + Retry
        ├─ empty → empty state
        └─ loaded → FilteredDataGrid
              ├─ row click → highlight only
              ├─ Draft → Submit
              └─ In review → Publish → SystemDialog
                    ├─ diff, examples, floor, event
                    ├─ confirm → success → refresh
                    └─ refusal → inline error, dialog stays
```

People Config → Compliance stays the draft editor. Its in-review action navigates here (`?focus=<id>`), which highlights the row and does not publish.

---

## Artifact 3 — IA Placement

- Route: `/catalog/policy-versions`
- Studio: Catalog (Data Trust), Govern group, beside Access Policies and Audit Log.
- Guard: `CatalogRoute` plus `catalog:manage_policies`.
- API: `/carbon-api/catalog/policy-versions/` (list, detail, submit, publish). Not under `/people/`.
- Storage stays the existing versioned row. This screen does not add a second store.

---

## Artifact 4 — Composition Spec (reuse, never invent)

```
PolicyDeskPage
├─ FilteredDataGrid (search, state SearchSelect, sort, paging, compact)
│    columns: Policy, Version, State, Citation, Effective date, Actions
│    row click → highlight only
└─ SystemDialog “Publish version”
     ├─ FormField policy (read-only)
     ├─ FormField version (read-only)
     ├─ Diff table (field, before, after)
     ├─ Examples pass/fail
     ├─ Floor pass/fail
     └─ Governance event (action, before state, after state)
```

**Reuse audit:**

- [x] Page shell = `FilteredDataGrid` → `PageContainer` + `PageHeader`
- [x] Dialog = `SystemDialog`
- [x] Fields = `FormField`
- [x] State filter = `SearchSelect` inside `FilteredDataGrid`
- [x] Empty / error / loading = `EmptyState`, `ErrorAlert`, `LoadingSkeleton` via the grid and page
- [x] Feedback = `useNotification()`
- [x] Density = compact grid, small controls
- [x] No JSON textarea as the editor

---

## Artifact 5 — Complete State Matrix

| State | Rendering |
|-------|-----------|
| loading | Skeleton |
| empty | Empty state |
| loaded | Grid |
| error | Message + Retry |
| forbidden | Route guard redirects |
| stale | Grid stays up while a submit or publish refreshes |

| Interaction | Where |
|-------------|--------|
| row click | Highlight only |
| Submit | Draft rows, explicit |
| Publish | In review rows, explicit, dialog |
| disabled | Publish confirm disabled while the request is in flight |

---

## Artifact 6 — Data Contract

`GET /carbon-api/catalog/policy-versions/?state=&q=`

```
{ count, results: [{ id, policy, version, name, state, citation, effective_date, preparer_id, publisher_id }] }
```

`GET /carbon-api/catalog/policy-versions/<id>/` adds `examples`, `floors`, `diff`, `event`.

`POST .../submit/` and `POST .../publish/` return the public row.

Publish refusals: `sod_same_actor` (403), `sod_missing_preparer` (403), `examples_failed` (409), `floor_failed` (409), `citation_required` (409), `not_in_review` (409).

---

## Artifact 7 — Permission

Documented capability: **`catalog:manage_policies`**.

That capability already means administer Data Trust governance policies. User `admin` (group `admin`, wildcard) can publish. `people_lead` drafts and submits on People and cannot call this desk.

---

## Artifact 8 — Out of scope

- Payroll divisors, fractions, caps, and sheet examples stay on People Config.
- No second publish control on People.
- No new visual language, no new permission name, no second rule table.
- Browser verification is not claimed by this spec’s first build unless a dev server was already listening.

---

## Artifact 9 — Tests

- API: the desk list returns a version, and `publisher_id` is not `preparer_id`.
- API: same-actor publish is `sod_same_actor`.
- UI: the grid renders a version and the four state labels; Publish is a dialog action.
- UI: People Compliance renders no Publish button.
