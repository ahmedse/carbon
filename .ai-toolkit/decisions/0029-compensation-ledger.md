# ADR-0029 — Compensation ledger: append-only effective-dated lines with provenance

- **Status:** Accepted
- **Date:** 2026-09-02
- **Deciders:** Master Architect
- **Area:** backend — `people` (Nibras HRMS compensation domain)

## Context

The first compensation implementation added three models
(`CompensationComponent`, `CompensationPlan`, `EmployeeCompensation`) plus a
per-employee ledger endpoint, but did so with several unresolved decisions:

1. **Business logic in the view** — `EmployeeCompensationView.post()` mutated the
   ledger (close-previous-line) inline, and `get()` computed earnings/deductions
   totals in Python over serialized data (using `float()` on `Decimal` money).
   This violates the Facade/Thin-View contract.
2. **Permission mismatch** — the write path gated on the *view* permission
   (`people:view_compensation`) instead of the *manage* capability; the
   docstring referenced a `people:manage_compensation` capability that does not
   exist in `accounts/capabilities.py`.
3. **Two sources of truth** — the `EmployeeCompensation` docstring claimed
   `Employee.basic_salary` "is migrated as an initial 'basic' component row",
   but no such data migration existed; `basic_salary` remained a parallel legacy
   scalar.

This ADR settles those decisions so the ledger is a single, verified source of
truth.

## Decision

### 1. Append-only, effective-dated ledger (confirmed)

`EmployeeCompensation` is the single source of truth for earnings/deductions:

- Rows are **never updated in place** for a salary change. A change appends a new
  row with a new `effective_start`; the prior open row for the same component is
  **closed** (`effective_end = new.effective_start`).
- "Current" = rows where `effective_start <= as_of` and
  (`effective_end IS NULL` or `effective_end >= as_of`).
- Every insert emits a `PersonnelEvent('salary_change')` (chronicle) and a
  `catalog.GovernanceEvent('compensation_change')` (audit), inside the same
  transaction.

### 2. Provenance is mandatory, not decorative

Each ledger row records **why** the amount exists, via `source_rule` (FK
`ComplianceRule`), `source_plan` (FK `CompensationPlan`), `reason_event` (FK
`PersonnelEvent`), plus `created_by` / `verified_by`. `reason_note` is free text
for the human context. Verification is a Tier-2 gate (`is_verified`,
`verified_by`, `verified_at`).

### 3. `basic_salary` is migrated, then demoted to a legacy mirror

- A **data migration** seeds one `basic` `CompensationComponent` ledger row per
  employee whose `basic_salary > 0` (component `code='basic'`, direction
  `earning`), with `effective_start = join_date` (or today when `join_date` is
  null), open-ended, `reason_note='Migrated from Employee.basic_salary'`.
- `Employee.basic_salary` is **kept** during transition (it is referenced by the
  calculation engine and frontend), but is **no longer authoritative**: the
  ledger is. The API response retains a `basic_salary` field for backwards
  compatibility, clearly labelled legacy.

### 4. Permission model (resolves the mismatch)

- **Read** compensation = `people:view_compensation` (restricted, audited reveal).
- **Write** compensation (append line, verify line) = `people:manage`, already
  enforced by the `PeopleAccess` permission class for non-GET methods. No new
  capability is added; the redundant/wrong inner `can_view_compensation` checks
  on the write paths are **removed**.

### 5. Computation lives in a service; totals in the DB

- New `people/services.py`-adjacent `CompensationService` (in
  `people/compensation_service.py`) owns: `current_lines(employee, as_of)`,
  `ledger_totals(employee, as_of)` (DB `aggregate`, `Decimal`-exact), and
  `append_line(...)` / `verify_line(...)` (transactional, emit events).
- Views become thin: validate → call service → serialize → return.

## Consequences

- Backend: service extraction + permission fix + data migration + admin
  registration + tests (NIR-7A).
- Frontend: pay tab reads the unchanged envelope (`current`/`history`/`totals`/
  `component_direction`); no API shape change (NIR-7B).
- `Employee.basic_salary` remains until a later phase removes it and rewires the
  calculation engine to read the ledger.

Refs: TASKS.md NIR-7A / NIR-7B.
