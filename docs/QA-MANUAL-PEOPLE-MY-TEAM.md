# Manual QA Checklist — People / My / Team (Nibras HRMS)

> **Scope:** End-to-end, hand-testable processes for the People (HR admin),
> My (employee self-service), and Team (manager approvals) apps, plus the
> GOFSCO HRMS compliance verification matrix.
>
> **Last updated:** 2026-09-08
>
> **How to use:** Work top-to-bottom. Each case has a **Goal**, **Preconditions**,
> numbered **Steps**, **Expected** result, and an explicit **PASS** criterion.
> Mark ✅ / ❌ and log any deviation.

---

## 0. Test Environment

| Item | Value |
|------|-------|
| Backend base URL | `http://localhost:8009` |
| API prefix | `/carbon-api/` |
| Frontend URL | `http://localhost:5179` |
| Admin login (People admin) | `ahmed` / `AdminPa_132` |
| Employee self-service (test users) | seeded GOFSCO employees `GF-001` … `GF-005` (see `seed_gofsco.py`) |
| Database | PostgreSQL `nibras_dev` (brand `nibras`) |

**Login path:** frontend → sign in → JWT issued at `POST /carbon-api/token/`.

**Note:** JWT role for `ahmed` resolves to the self-service profile with balances
(annual=30, sick=21, emergency=3, maternity=90, unpaid=30, paternity=0). To test the
"manager approves" chain you need a second user mapped to an employee with a `manager`
(self-FK) set to the requestor.

---

## Part A — People App (HR admin / back office)

### A1. Add a new employee (end-to-end)
- **Goal:** HR creates a full employee record with contract + position + Kuwaitization + rotation.
- **Preconditions:** At least one `Position` and one contract-type reference value exist.
- **Steps:**
  1. Navigate **People → Employees** (`/people/employees`).
  2. Click **Add Employee**.
  3. Fill required fields: name, national ID / civil ID, `employee_number`, hire/`join_date`.
  4. Select `position`, set `basic_salary`, set `contract_type_code`.
  5. Set `kuwaitization` (on/off) and `rotation` (e.g. `1/1`, `2/1`, `3/1`, `5/1`).
  6. Optional: set `manager` (self-FK) to an existing employee.
  7. Save.
- **Expected:** New row appears in the grid with correct badge for Kuwaitization and rotation shown.
- **PASS:** `GET /carbon-api/people/employees/<id>/` returns the record with all fields persisted; grid reflects it after refresh.

### A2. Edit an employee + re-activation lifecycle
- **Goal:** HR updates employee details; deactivate and reactivate work.
- **Preconditions:** Employee from A1 exists.
- **Steps:**
  1. Open employee detail page, edit `basic_salary` or `position`, save.
  2. Click **Deactivate** → confirm.
  3. Confirm employee leaves active lists (`is_active=False`).
  4. Click **Reactivate** → confirm.
- **Expected:** Changes persist; deactivation flips `is_active=False`; reactivation restores `is_active=True`.
- **PASS:** After each step, `GET` detail reflects the expected `is_active` / edited field.

### A3. Positions CRUD
- **Goal:** Create/edit a `Position`.
- **Steps:** **People → Positions** → Add → fill title/grade/org unit → Save → Edit → Save.
- **Expected:** Position appears and edits persist.
- **PASS:** `GET /carbon-api/people/positions/<id>/` reflects edits.

### A4. Compliance rules CRUD (GOFSCO issue #1 — rule engine)
- **Goal:** Create an authoritative compliance rule with inputs schema + expression.
- **Steps:**
  1. **People → Policies → Compliance Rules** (`/people/config` / rules list).
  2. Add rule: `rule_id` (e.g. `kw-eosi-accrual`), `version`, `name`, `description`.
  3. Define `inputs_schema` and the computation/expression.
  4. Mark `is_authoritative=True` with provenance.
  5. Save, then edit and confirm versioning bumps.
- **Expected:** Rule persists, is listed, and is flagged authoritative.
- **PASS:** `GET /carbon-api/people/compliance-rules/<id>/` returns the rule with correct `inputs_schema`, `is_authoritative=True`, and provenance.

### A5. Leave Policy — create + grouping/tagging (LPR-4)
- **Goal:** Create a leave policy with `category` + `tags` grouping.
- **Steps:**
  1. **People → Policies** (`/people/policies`).
  2. Click **Add Policy**.
  3. Pick `leave_type`, set `default_entitled_days`, `accrual_method`, `max_carryover_days`, `is_carryover_allowed`.
  4. Set `status` (draft/active/deprecated), `effective_from`/`effective_to`.
  5. Set **category** (e.g. `Leave`) and **tags** (e.g. `["annual","expat"]`).
  6. Save.
- **Expected:** Policy appears under its category, tags visible/filterable.
- **PASS:** Grid filter by category and tag returns only matching policies; `GET /carbon-api/people/leave-policies/<id>/` shows `category` + `tags`.

### A6. Leave Policy — Kuwaitization + rotation scope (LPR-5 / GOFSCO #2/#3)
- **Goal:** Two policies: Kuwaiti-only (42 days) and non-Kuwaiti-only (30 days); a rotation-scoped policy.
- **Steps:**
  1. Create policy `annual-kuwaiti`: `applies_to_kuwaitization = Kuwaiti only`, `default_entitled_days = 42`.
  2. Create policy `annual-expat`: `applies_to_kuwaitization = Non-Kuwaiti only`, `default_entitled_days = 30`.
  3. Create policy `rotation-leave`: `applies_to_rotations = ["2/1","3/1"]`.
  4. Save each.
- **Expected:** Scoping fields persist and are displayed.
- **PASS:** `GET .../leave-policies/<id>/` returns the correct `applies_to_kuwaitization` and `applies_to_rotations`.

### A7. Leave Policy — versioning + snapshot (LPR-3A)
- **Goal:** Fork/snapshot a policy and view version history.
- **Steps:**
  1. Open an active policy, trigger **New Version / Fork** (edit → save new version).
  2. Open **Version History** (`/leave-policies/<id>/versions/`).
- **Expected:** A new immutable version is recorded with a snapshot of fields (incl. the new scope fields).
- **PASS:** `GET .../versions/` shows ≥2 versions; the latest snapshot includes `applies_to_kuwaitization` and `applies_to_rotations`.

### A8. Leave Policy — propagate to entitlements (LPR-2A)
- **Goal:** Propagate a policy to eligible employees for a year.
- **Steps:**
  1. From policy detail, trigger **Propagate** for the current year (dry-run first, then apply).
  2. Review the dry-run eligible count (should respect Kuwaitization/rotation/gender/service/org/contract scope).
- **Expected:** `LeaveEntitlement` rows are created only for eligible employees; idempotent on re-run.
- **PASS:** `GET /carbon-api/people/leave-entitlements/` shows entitlements with `policy` provenance, only for in-scope employees; re-running does not duplicate/overwrite.

### A9. Leave entitlements + leave records (HR view)
- **Goal:** HR lists entitlements and manual leave records.
- **Steps:** **People → Leave** → review entitlements; add a manual `LeaveRecord` for an employee.
- **Expected:** Record created with correct `leave_type` and dates.
- **PASS:** `GET /carbon-api/people/leave-records/` lists the new record.

### A10. Benefit types + employee benefits
- **Goal:** Create benefit types (GOFSCO C&B categories) and assign a benefit to an employee.
- **Steps:**
  1. **People → Config → Benefit Types** → add types: `ACCOM`, `VEHICLE`, `MEDICAL`, `SCHOOL`, `TICKETS`, `OT_BASE`.
  2. Assign a benefit to an employee with a value.
- **Expected:** Types and assignments persist.
- **PASS:** `GET /carbon-api/people/benefit-types/` and `/people/benefits/` reflect the data.

### A11. Compensation components + plan + ledger + verify
- **Goal:** Define compensation components, build a plan, and verify a per-employee ledger line.
- **Steps:**
  1. **People → Config** → add compensation components (basic, housing, transport, social, kuwaitization, overtime, tickets, school, vehicle, gosi_employee, eosi_accrual, loan_deduction).
  2. Create a compensation plan referencing components.
  3. Open an employee compensation ledger and **Verify** a line.
- **Expected:** Components/plan persist; a ledger line can be verified.
- **PASS:** `GET /carbon-api/people/compensation-components/` and `/people/compensation-plan/` return rows; `POST /employees/<id>/compensation/<line_id>/verify/` returns 200.

### A12. Loans + installments
- **Goal:** Issue a loan and generate installments.
- **Steps:** **People → Loans** → add loan (principal, terms) → confirm installment schedule is created.
- **Expected:** Loan + installment rows persist with correct amounts.
- **PASS:** `GET /carbon-api/people/loans/` and `/people/loan-installments/` list the loan and its installments.

### A13. Attendance records + permissions
- **Goal:** Record attendance and an attendance permission (e.g. late arrival / early leave).
- **Steps:** **People → Attendance** → add record; add an `AttendancePermission` entry.
- **Expected:** Both persist.
- **PASS:** `GET .../attendance/` and `.../attendance-permissions/` list new rows.

### A14. Certifications
- **Goal:** Add an employee certification.
- **Steps:** **People → Certifications** → add certification (name, issue/expiry) for an employee.
- **Expected:** Persists and shows on employee record.
- **PASS:** `GET .../certifications/` lists it.

### A15. Rotation schedules
- **Goal:** Define a rotation schedule (e.g. `1/1`, `2/1`).
- **Steps:** **People → Rotation** → add schedule with pattern + dates.
- **Expected:** Persists.
- **PASS:** `GET .../rotation-schedules/` lists it.

### A16. Payroll run — create → compute → validate → commit → WPS (GOFSCO issue #4)
- **Goal:** Full payroll lifecycle ends with WPS export.
- **Preconditions:** Employees with compensation + benefits exist; a run period is set.
- **Steps:**
  1. **People → Payroll** → create a `PayrollRun` for a period.
  2. Click **Compute** (`POST /payroll-runs/<id>/compute/`).
  3. Click **Validate** (`POST /payroll-runs/<id>/validate/`), review validations.
  4. Click **Commit** (`POST /payroll-runs/<id>/commit/`).
  5. Click **WPS Export** (`POST /payroll-runs/<id>/wps/`).
- **Expected:** Compute populates payslip lines; validate returns a validation list; commit finalizes; WPS returns an export file/link.
- **PASS:** Each endpoint returns 200/201 with expected payload; WPS export is downloadable/parseable.

### A17. EOSI (end-of-service indemnity) + timeline
- **Goal:** Compute EOSI for an employee and view lifecycle timeline.
- **Steps:** **People → Employees** → open employee → **EOSI**; view **Timeline**.
- **Expected:** EOSI calculation returns a figure; timeline lists personnel events.
- **PASS:** `GET .../employees/<id>/eosi/` returns a numeric result; `GET .../employees/<id>/timeline/` lists events.

---

## Part B — My App (employee self-service)

### B1. View my profile
- **Goal:** Employee sees own profile.
- **Steps:** **My → Dashboard** (`/my`).
- **Expected:** Own employee record rendered.
- **PASS:** `GET /carbon-api/people/me/` returns the signed-in employee's profile.

### B2. View my leave balance
- **Goal:** Employee sees entitled / carried / used / pending / remaining.
- **Steps:** **My → My Leave** (`/my/leave`).
- **Expected:** Balance widget shows all five figures.
- **PASS:** `GET /carbon-api/people/me/leave-balance/` returns 200 with the five fields.

### B3. Request a day off (leave request)
- **Goal:** Employee submits a leave request → creates LeaveRecord + governed Correspondence.
- **Steps:**
  1. **My → My Leave** → **Request Leave**.
  2. Pick leave type, start/end dates.
  3. Submit.
- **Expected:** Confirmation; the request appears in **My Requests**.
- **PASS:** `POST /carbon-api/people/me/leave/` returns 201; the new leave appears in `/people/me/leave/` and a correspondence is created.

### B4. Track my requests
- **Goal:** Employee sees submitted/in-progress/rejected requests with status.
- **Steps:** **My → My Requests** (`/my/requests`) → open a request detail (`/my/requests/:id`).
- **Expected:** Status + history shown.
- **PASS:** `GET /carbon-api/people/me/leave/<id>/` reflects the current status.

### B5. Request a profile change
- **Goal:** Employee submits a personal-data change request.
- **Steps:** **My → Dashboard** → **Request Profile Change** → fill fields → submit.
- **Expected:** Change request submitted (and routed for approval).
- **PASS:** `POST /carbon-api/people/me/profile-change/` returns 201/200 and the request is visible to the manager inbox.

### B6. My loans
- **Goal:** Employee sees own loans.
- **Steps:** **My → Dashboard** → loans section.
- **Expected:** Own loan records listed.
- **PASS:** `GET /carbon-api/people/me/loan/` returns own loans.

---

## Part C — Team App (manager approvals)

### C1. Approvals inbox
- **Goal:** Manager sees actionable requests for their team.
- **Steps:** **Team → Approvals Inbox** (`/team`).
- **Expected:** Requests with status `submitted`/`in_review` appear.
- **PASS:** `GET /carbon-api/correspondence/inbox/` returns actionable items for the manager.

### C2. Approve a request
- **Goal:** Manager approves a leave request.
- **Steps:** Open a request in the inbox → **Approve**.
- **Expected:** Status advances; requestor's balance/status reflects approval.
- **PASS:** `POST /carbon-api/correspondence/<id>/approve/` returns 200; employee's request status becomes approved.

### C3. Reject a request
- **Goal:** Manager rejects with a reason.
- **Steps:** Open request → **Reject** → enter reason.
- **Expected:** Request marked rejected, reason recorded.
- **PASS:** `POST .../reject/` returns 200 and detail shows the rejection.

### C4. Send back for revision
- **Goal:** Manager sends a request back to the requestor.
- **Steps:** Open request → **Send Back** → note.
- **Expected:** Request returns to requestor with note.
- **PASS:** `POST .../send-back/` returns 200; requestor can edit and resubmit.

### C5. Multi-step approval chain
- **Goal:** A request flows through a 2-step chain (e.g. supervisor → HR).
- **Steps:** Submit as employee → approve as step-1 approver → approve as step-2 approver.
- **Expected:** Request progresses through both steps before final approval.
- **PASS:** Inbox shows the request to the correct approver at each step; final status only after the last approval.

---

## Part D — Cross-app journey (the "request a day off" full loop)

**Goal:** Validate the complete loop end-to-end across My → Team → People.

1. **Employee** (My): request annual leave via `/my/leave`.
2. **Manager** (Team): see it in inbox, **Approve**.
3. **Employee** (My): see request status `approved`; leave balance **pending/used** updated.
4. **HR** (People): see the `LeaveRecord` in `/people/leave-records/`; see the entitlement decremented.
5. **HR** (People): (optional) include the day in a payroll run to confirm attendance/payroll integration.

**PASS:** Every handoff above is observed in the correct app; no step silently drops data.

---

## GOFSCO HRMS Verification Matrix

| # | GOFSCO issue | Where handled | How to verify manually |
|---|--------------|---------------|------------------------|
| 1 | Compliance rule engine (authoritative, versioned) | `people.ComplianceRule` | A4 — create authoritative rule, verify `is_authoritative` + version |
| 2 | Kuwaitization leave (Kuwaiti 42 vs expat 30 days) | `LeavePolicy.applies_to_kuwaitization` | A6 + A8 — two scoped policies, propagate to correct employees |
| 3 | Rotation leave scoping | `LeavePolicy.applies_to_rotations` | A6 + A8 — rotation-scoped policy propagates only to matching rotations |
| 4 | Payroll lifecycle → WPS | `people.PayrollRun` + WPS export | A16 — compute→validate→commit→WPS |
| 5 | EOSI indemnity | `people.EmployeeEOSI` | A17 — EOSI returns a figure |
| 6 | Benefits & compensation C&B categories | `BenefitType` + `CompensationComponent` | A10 + A11 — all 6 categories present |
| 7 | HR Reporting | **Not built** (dashboard/report module) | N/A — tracked as roadmap gap |
| 8 | HR Modules (full module registry) | **Not built** (module catalog) | N/A — tracked as roadmap gap |

> **Seed data:** `manage.py seed_gofsco` seeds employees/benefits/certs/loans;
> `manage.py seed_gofsco_rules` seeds authoritative compliance rules + leave
> policies + benefit types. Run both before starting the checklist.

---

## Sign-off

- [ ] Part A (People) — all PASS
- [ ] Part B (My) — all PASS
- [ ] Part C (Team) — all PASS
- [ ] Part D (cross-app) — PASS
- [ ] GOFSCO matrix — issues 1–6 verified (7–8 acknowledged as not built)

**Tester:** ____________  **Date:** ____________
