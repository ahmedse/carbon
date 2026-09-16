# Screen Spec — Employee Wizard (Hire / Onboarding) · NSR-4B acceptance addendum
# Extends the existing wizard composition in `EmployeeWizard.jsx` (Identity →
# Employment → Compensation → Review). Full 9-artifact historical design:
# `docs/_archive/design-superseded/DESIGN-EMPLOYEE-ONBOARDING-WIZARD.md`.

---

## Artifact 1 — Acceptance (NSR-4B)

**Story:** As an HR user hiring an employee, I want the wizard to require manager
and join date, optionally capture opening basic (compensation-gated), and tell me
that leave entitlements are ready while opening basic must be verified on the Pay
tab before payroll.

**Acceptance (Given/When/Then):**

- **Manager required:** Given the Employment step, when manager is empty and the
  user clicks Next, then validation fails with `errManagerRequired` and the step
  does not advance.
- **Join date required:** Given the Employment step, when join date is empty,
  then Next is blocked (`errJoinDateRequired`) — already enforced; retained.
- **Civil ID:** Given Civil ID is filled, when it is not exactly 12 digits, then
  Identity validation fails. Civil ID remains optional (API `blank=True`).
- **Opening basic (gated):** Given `people:view_compensation` (or implied by
  `people:manage` / global admin via `useCompensationAccess`), when creating
  (not editing), then the Compensation step shows an optional Opening basic
  field. Without compensation access, the field is hidden.
- **Payload honesty (NSR-2B still applies):** Given Save on create, when
  opening basic is set, then POST body includes write-only `opening_basic` and
  **never** `basic_salary`. When opening basic is empty/whitespace, `opening_basic`
  is omitted. Edit mode never sends `opening_basic`.
- **Success toast:** Given a successful create, when the dialog closes, then the
  snackbar shows entitlements/payroll readiness (`employeeOnboardReady`): leave
  entitlements ready; verify opening basic on Pay tab before payroll.
- **Edit path:** Given editing an existing employee with compensation access,
  then Compensation shows read-only reflected basic (no opening-basic write).

---

## Artifact 2 — Journey (hire path)

```
Employees → Add Employee → Wizard
  Identity (name; civil_id format if present)
  → Employment (employee_no, org_unit, **manager**, **join_date**, …)
  → Compensation (optional opening_basic if canViewCompensation)
  → Review → Save → POST /people/employees/ (+ opening_basic?)
       → snackbar: employeeOnboardReady
       → (BE NSR-4A) leave propagate + optional unverified ledger line
```

---

## Artifact 6 — Data contract (create)

| Field | Required (FE) | Notes |
|-------|---------------|-------|
| `manager` | yes | PK of reporting manager |
| `join_date` | yes | ISO date |
| `civil_id` | no | 12 digits when present |
| `opening_basic` | no | write-only; string decimal; create only |
| `basic_salary` | — | **never sent** from wizard |

---

## Artifact 9 — i18n keys (en + ar)

`errManagerRequired`, `errOpeningBasicInvalid`, `formOpeningBasic`,
`formOpeningBasicHint`, `openingBasicNone`, `wizardOpeningBasicIntro`,
`wizardOnboardReadyHint`, `employeeOnboardReady`.

---

*NSR-4B 2026-09-16 — Frontend Worker acceptance addendum.*
