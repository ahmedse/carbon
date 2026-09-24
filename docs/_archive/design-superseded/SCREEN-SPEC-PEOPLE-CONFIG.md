# Screen Spec — People Config (Compliance + Compensation)
# Canonical per `.ai-toolkit/shared/frontend-ready.md` (9 artifacts).
# Consumed by TASKS.md Phase NSR-5B. Route: `/people/config`.

---

## Artifact 1 — User Story + Acceptance

**Story:** As an HR/config admin with People access, I want to create and update
compliance rules and register compensation components/plan rows from App Config,
so that statutory figures and C&B matrix data are managed in-product without
Django admin.

**Acceptance (Given/When/Then):**

- **Happy path (compliance create):** Given People access, when the user opens
  Compliance → Add Rule, fills required fields, and saves, then POST
  `compliance-rules/` succeeds, the dialog closes, a success toast shows, and
  the grid refreshes.
- **Happy path (compliance update):** Given an existing rule, when the user edits
  and saves, then PATCH `compliance-rules/<id>/` succeeds and the row updates.
- **Happy path (compliance delete):** Given an existing rule, when the user
  confirms delete, then DELETE returns 204 and the row disappears.
- **Happy path (component create):** Given a global admin, when they add a
  compensation component, then POST `compensation-components/` returns 201 and
  the list refreshes. Non-admin: Add is hidden or API 403 surfaces as error toast.
- **Happy path (plan create):** Given a global admin, when they add a plan row
  (component + amount + effective_start), then POST `compensation-plan/` returns
  201 and the matrix refreshes.
- **Empty:** Given no rules / components / plans, when the tab loads, then an
  empty state explains why + offers the create action (when permitted).
- **Error:** Given a list fetch fails, when the tab renders, then ErrorAlert +
  Retry (never blank).
- **Forbidden (403):** Given POST/PATCH/DELETE returns 403, when save/delete
  fails, then a human toast shows the API message; form input is preserved.
- **Reference / Overview:** Reference Data tab remains registry-driven CRUD.
  Overview stays informational (identity + roles).

---

## Artifact 2 — Journey Map

```
/people/config
 ├─ Overview (informational) → identity key/value + roles table
 ├─ Reference Data → ReferenceDataManager (unchanged)
 ├─ Compliance Rules
 │    └─ load GET compliance-rules/
 │         ├─ loading | error+retry | empty+Add | loaded grid
 │         └─ Add/Edit → SystemDialog → POST|PATCH → toast → refresh
 │         └─ Delete → ConfirmDialog → DELETE → toast → refresh
 └─ Compensation
      ├─ Components: GET compensation-components/ → create-only SystemDialog (POST)
      └─ Plans: GET compensation-plan/ → create-only SystemDialog (POST)
```

Friction: (1) compensation write is admin-only on the API — gate UI with
`isGlobalAdminFlag`; (2) no PATCH/detail for components/plans — do not invent
edit UI; (3) `inputs_schema` is JSON — validate client-side before POST.

---

## Artifact 3 — IA Placement

- Existing route `/people/config` (`PeopleConfigPage`), under Configuration nav.
- Tabs inside the page (not sidebar): Overview | Reference | Compliance |
  Compensation.
- No new `App.jsx` routes. RULE_9: no in-page breadcrumbs.

---

## Artifact 4 — Composition Spec

```
PeopleConfigPage
├─ PageContainer + PageHeader
├─ Tabs (Overview | Reference | Compliance | Compensation)
├─ Overview → Paper identity grid + roles Table (read-only)
├─ Reference → ReferenceDataManager (existing)
├─ ComplianceRulesPanel
│    ├─ Stack header + Button "Add Rule"
│    ├─ StandardDataGrid | LoadingSkeleton | ErrorAlert | EmptyState
│    ├─ SystemDialog (create/edit form)
│    └─ ConfirmDialog (delete)
└─ CompensationConfigPanel
     ├─ Components section (grid + Add Component SystemDialog) [admin]
     └─ Plans section (grid + Add Plan SystemDialog) [admin]
```

### Reuse audit
- [x] SystemDialog / ConfirmDialog / StandardDataGrid / PageContainer / PageHeader
- [x] LoadingSkeleton / ErrorAlert / EmptyState
- [x] api/people.js helpers via apiFetch — no raw fetch
- [x] FONT / theme tokens — no magic hex/px

---

## Artifact 5 — State Matrix

### Page / tab data
| State | Rendering |
|-------|-----------|
| loading | LoadingSkeleton (table) |
| empty | EmptyState + create CTA when permitted |
| loaded | StandardDataGrid |
| error | ErrorAlert + onRetry |
| forbidden | Toast on write; list may still load for viewers |
| stale | Keep rows visible while refresh after save |

### Dialog / actions
| State | Behavior |
|-------|----------|
| default / open / closed | SystemDialog |
| submitting | primary action disabled + progress |
| error | snackbar; form preserved |
| success | toast + close + reload |
| disabled | Add hidden when not global admin (compensation) |

---

## Artifact 6 — Data Contract

Verified against `backend/people/urls.py` + serializers (NSR-5B — no invented fields).

| Method | Path | Notes |
|--------|------|-------|
| GET | `/carbon-api/people/compliance-rules/` | `{count, results:[…]}` |
| POST | `/carbon-api/people/compliance-rules/` | 201 body = serializer fields |
| GET/PATCH/DELETE | `/carbon-api/people/compliance-rules/<pk>/` | PATCH partial; DELETE 204 |
| GET | `/carbon-api/people/compensation-components/` | array of active components; `?direction=` |
| POST | `/carbon-api/people/compensation-components/` | **admin only** 403 otherwise |
| GET | `/carbon-api/people/compensation-plan/` | array; `?pay_grade=` `?job_family=` |
| POST | `/carbon-api/people/compensation-plan/` | **admin only** 403 otherwise |

**Compliance writable fields:** `rule_id`, `version`, `name`, `description`,
`jurisdiction`, `category`, `effective_date`, `formula_ref`, `source_citation`,
`inputs_schema`, `is_authoritative`, `provenance`, `test_cases`.
Read-only: `id`, `created_at`, `updated_at`.

**Component writable fields:** `code`, `name`, `name_ar`, `direction`, `category`,
`is_eosi_base`, `is_gosi_base`, `is_wps_relevant`, `is_taxable`, `is_variable`,
`governing_rule`, `sort_order`, `valid_from`, `valid_to`, `is_active`.

**Plan writable fields:** `org_unit`, `pay_grade_code`, `job_family_code`,
`component`, `amount`, `currency`, `frequency`, `effective_start`,
`effective_end`, `is_active`. Read-only expansions: `component_code`,
`component_name`, `component_direction`.

**Gap (documented, not invented):** no PATCH/DELETE for compensation
components or plans — UI is create + list only.

---

## Artifact 7 — Accessibility (WCAG AA)

- IconButtons have `aria-label` from i18n (`common.edit` / delete / add).
- Dialogs trap focus via SystemDialog; Esc/Cancel closes without save.
- Status chips use label text, not color alone.
- Form labels via TextField `label`; required fields marked.
- Keyboard: tab through grid actions and dialog fields.

---

## Artifact 8 — Performance Envelope

- Route already `React.lazy` in `App.jsx`.
- One list fetch per active tab/section; no N+1.
- Grids compact; paginate client-side if >50 rows (DataGrid default).
- Debounce not required (no live search in v1).
- Bundle: panels co-located under people chunk; no new heavy deps.

---

## Artifact 9 — i18n / RTL

- All user strings in `people` namespace (`en` + `ar`).
- Tab keys: `configTabOverview|Reference|Compliance|Compensation`.
- Category / direction labels via i18n keys, not hardcoded English in chips.
- RTL: Stack/Grid + MUI logical props; no LTR-only absolute positioning.
- Dates via existing `formatDate` helper.

---

## Out of scope
- PeopleHome (NSR-5C).
- Backend PATCH for compensation entities.
- Leave Policy tab (lives on `/people/policies`).
