# Screen Spec — Payslip lines and retro run

People surfaces only: Payslip page and Payroll Runs. No new app.

## Artifact 1 — User story

As a payroll reviewer I read each payslip line with its policy version and the regulation version it was checked against. As a payroll preparer I open a retro from a committed run without creating a second run on the same period.

## Artifact 2 — Acceptance

- A committed run shows an Open retro action. The dialog asks for a start and end that are not the source period.
- Same-period retro stays refused. The form keeps what was typed and shows the error.
- The payslip grid lists employee, line type, amount, rule id, rule version, and regulation version. Row click highlights only.
- Search and the line-type filter still apply. Empty, loading, and error states stay the existing page states.

## Artifact 3 — Layout

Existing Payroll Runs page and Payslip page. Compact density. SystemDialog for the retro. No new button padding.

## Artifact 4 — States

Loading skeleton, error with retry, empty copy, and the populated grid. Retro dialog: idle, saving, and error with the dates preserved.

## Artifact 5 — Data

`GET /payroll-runs/`, `POST /payroll-runs/<id>/retro/` with `period_start` and `period_end`, `GET /payslip-lines/`. Regulation version is `inputs.regulation_version`.

## Artifact 6 — Permissions

Same as payroll runs: `people:manage` for retro and compute. Read of lines follows the existing payslip permission.

## Artifact 7 — Copy

English and Arabic keys: `actionOpenRetro`, `retroRunTitle`, `retroRunHint`, `colRegulationVersion`.

## Artifact 8 — Not in this screen

Chat does not open a retro or commit a run. The one-active-period constraint is not relaxed.

## Artifact 9 — Proof

`people/tests/test_payslip_policy.py` commits the mixed month and refuses a same-period retro. Browser pass only if a dev server is already listening.
