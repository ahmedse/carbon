# Nibras — Enterprise HR Data Model (Reference Data, Tenancy & Thick Entities)

> **Status:** Living design doc (v0.1 — 2026-08-30). Responds to the Master
> Architect critique of the current `people` app as "forms to fill in, not an
> enterprise HR system."
> **Author:** Master Architect. **Owned by:** ClearTurn.
> **Reads-with:** `docs/NIBRAS-MASTER-STRATEGY.md` (esp. §2.4 two-hat discipline,
> §6 compliance rule library), `backend/mdm/models.py` (ReferenceSet system),
> `backend/people/models.py` (current models).

---

## 1. THE VERDICT — what the critique is really saying

Four systemic flaws in the current `people` app, all confirmed against code:

| # | Flaw | Evidence (today) | Why it matters |
|---|------|------------------|----------------|
| F1 | **Lookups are free text or hardcoded, not governed** | `Employee.gender`, `Employee.nationality`, `LeaveRecord.leave_type`, `Loan.loan_type`, `Certification.cert_type`, `AttendancePermission.permission_type`, `RotationSchedule.pattern`, `Position.grade`, `PayslipLine.line_type` are all `CharField` free text. `BenefitType.category`, `ComplianceRule.category`, `Position.STATUS_CHOICES`, `PayrollRun.STATUS_CHOICES` are hardcoded `choices=`. | No referential integrity, no i18n labels, no lifecycle, no cross-report aggregation. "M5" and "m5" and "M 5" are three different loans. |
| F2 | **No tenant / legal-entity boundary** | `mdm.OrgUnit` is a self-referencing tree with `parent=None` as the *only* root marker. No `legal_entity`/`tenant`/`company` FK. `fetchOrgUnits` returns ALL units across ALL roots. | Data from AASTMT, GOFSCO, and future customer #2 will mingle in one tree. Org-scoped RBAC subtree expansion is meaningless without a root boundary. |
| F3 | **Compensation is one number** | `Employee.basic_salary` is a single `DecimalField`. No component ledger, no earning vs. deduction distinction, no effective dates. | Real payroll is a matrix of dated earning/deduction components (basic, housing, transport, overtime, GOSI employee share, WPS, loan installment, EOSI accrual…). One number cannot produce a legally-signable payslip. |
| F4 | **Thin entities, missing domains** | No credentials/documents/evidence, no competencies/skills, no rewards/disciplinary actions, no benefit/care-program enrollment lifecycle. `Certification` is a bare 5-field table; `PersonnelEvent` (the append-only chronicle) exists but is barely used. | HR facts must be *records with effective dates and verification*, not editable single cells. |

The user is right on every point. The fix is not more forms — it is **the same
data-trust mechanics the platform already ships** (ReferenceSet, PersonnelEvent,
ComplianceRule, evidence), applied consistently.

---

## 2. THE THREE LAWS (cross-cutting, non-negotiable)

These are the enterprise-grade invariants. Every model below obeys them.

1. **Governed enums only.** Any field whose value set is finite and meaningful to
   reporting/calculation is a `*_code` pointing at `mdm.ReferenceSet`, validated
   against *current* `ReferenceValue`s (the existing `_validate_reference_code`
   pattern in `people/serializers.py`, applied to **every** classifier, not just 4).
   Free text survives **only** for genuinely free-form attributes (notes, remarks,
   names).

2. **Additive, not overwrite.** An HR fact is an *append-only record with
   effective dates*, never an in-place `UPDATE` of a scalar. A salary change
   inserts a new effective-dated row; it does not overwrite `basic_salary`. The
   "current" value is a *derived* view over the ledger, not a stored cell. This is
   what makes history replayable, auditable, and payroll-deterministic.

3. **Verifiable.** Every regulated or identity-bearing fact carries provenance and
   can be linked to `evidence` (a scanned credential, a signed letter, a WPS
   receipt). A fact is "asserted" until a verification workflow marks it
   "verified". Payroll only consumes *verified* facts.

Two platform patterns do the heavy lifting and must be **reused, not reinvented**:
- `mdm.ReferenceSet` / `ReferenceValue` → the governed-enum catalog (F1).
- `people.PersonnelEvent` → the bitemporal append-only chronicle (F2…F4), extended
  to cover every entity, not just Employee/Position.

---

## 3. LAW 1 — THE REFERENCE DATA CATALOG (F1)

### 3.1 The rule

> Every classifier is a `ReferenceSet`. A `choices=` tuple or a free-text
> `CharField` holding an enum is a **data-model bug**, not a style preference.

### 3.2 Complete inventory — current state → target state

| Entity / field (today) | Today's type | Target ReferenceSet slug | Enterprise term |
|---|---|---|---|
| `Employee.gender` | free text | `gender` ✅ (seeded, unused) | Gender |
| `Employee.nationality` (text) + `nationality_code` | text + governed | `nationality` (collapse text→code) | Nationality |
| `Employee.employment_type_code` | governed ✅ | `employment_type` | Employment Type (FT/PT/contract/temp) |
| `Employee.contract_type_code` | governed ✅ | `contract_type` | Contract Type (limited/unlimited/…) |
| `Employee.rotation` | free text | `rotation_pattern` ✅ (seeded, unused) | Rotation / Work Schedule Pattern |
| `Employee.marital_status` (missing) | — | `marital_status` (new) | Marital Status |
| `Employee.religion` / `nationality` nuance (missing) | — | `religion` (new, sensitive) | Religion (CBAC-tiered) |
| `Employee.blood_group` (missing) | — | `blood_group` (new) | Blood Group |
| `Employee.bank` / `bank_branch` (missing) | — | `bank` (new) | Bank (WPS payee routing) |
| `Position.grade` | free text | `pay_grade` (new) | Pay Grade / Salary Grade |
| `Position.job_family_code` | governed ✅ | `job_family` | Job Family |
| `Position.job_code` (missing) | — | `job_title` or dedicated `JobCatalog` | Job / Job Classification |
| `Position.org_type` reuse | hardcoded 20 | keep `org_type` but as ref set | Org Unit Type |
| `LeaveEntitlement.leave_type` / `LeaveRecord.leave_type` | free text | `leave_type` ✅ (seeded, unused) | Absence Type (Annual/Sick/Emergency/…) |
| `LeaveRecord.status` | hardcoded | `leave_status` (new) | Absence Status |
| `Loan.loan_type` | free text | `loan_type` (new) | Deduction / Loan Type |
| `Loan.status` | hardcoded | `loan_status` (new) | Loan Status |
| `LoanInstallment.status` | hardcoded | `installment_status` (new) | Installment Status |
| `Certification.cert_type` | free text | `certification_type` (new) | Credential / Qualification Type |
| `AttendancePermission.permission_type` | free text | `permission_type` (new) | Attendance Permission Type |
| `AttendanceRecord.status` | hardcoded | `attendance_status` (new) | Attendance Status |
| `RotationSchedule.pattern` | free text | `rotation_pattern` (reuse) | Rotation Pattern |
| `BenefitType.category` | hardcoded 6 | `benefit_category` ✅ (seeded, unused) | Benefit Category |
| `BenefitType` itself | bespoke table | `benefit_plan` ref set OR keep table + category code | Benefit / Care Program |
| `PayslipLine.line_type` | free text | `compensation_component` (new — see §5.1) | Compensation Component (earning/deduction) |
| `ComplianceRule.category` | hardcoded 7 | `compliance_category` (new) | Compliance Category |
| `ComplianceRule.jurisdiction` | free text | `jurisdiction` (new: KW/SA/AE/…) | Jurisdiction |
| `PersonnelEvent.KIND_CHOICES` | hardcoded 14 | `personnel_event_kind` (new) | HR Event Type |
| `PersonnelEvent.ENTITY_CHOICES` | hardcoded 2 | `hr_entity` (new) | HR Entity Type |
| `PayrollRun.status` | hardcoded | `payroll_status` (new) | Payroll Run Status |

**Net:** today **4** governed fields. Target **≈28** ReferenceSets, of which ~5
already exist but are **seeded and unused** (gender, leave_type,
rotation_pattern, benefit_category, leave_type). The "seeded but ignored" set is
the cheapest win — the data exists, only the model + serializer need to consume it.

### 3.3 ReferenceSet governance tiers

Not every enum is equal. Classify each set by sensitivity so CBAC can gate it:

- **Tier 0 — Public**: gender, employment_type, job_family, leave_type.
- **Tier 1 — Org-visible**: pay_grade, compensation_component, benefit_category.
- **Tier 2 — Sensitive**: religion, nationality, bank. Read/write requires an
  explicit capability; never exposed in public lists.

This tiers onto the existing `ReferenceSet.domain` FK + a new `sensitivity`
field, and reuses `accounts.capabilities` for gating (no new auth mechanism).

---

## 4. LAW 2 — TENANCY: LEGAL ENTITY & ROOT ORG (F2)

### 4.1 The problem, precisely

`OrgUnit` is a tree with no root identity. Two customers' trees share one
namespace, `parent=None` is the only "root", and `get_allowed_org_unit_ids`
expands a subtree with no way to say "this subtree = this tenant." The frontend
`fetchOrgUnits` therefore lists *everything* — which is exactly the "why do I see
AASTMT's org units" leak the user flagged.

### 4.2 Target

Introduce a **Legal Entity** concept as the tenant root. Two options, ranked:

- **(A) Preferred — `mdm.LegalEntity`** as a first-class table
  (`code`, `name`, `name_ar`, `jurisdiction`, `registration_no`, `is_active`),
  with `OrgUnit.legal_entity` FK (nullable for legacy roots). This is the clean
  "customer #2 = new LegalEntity" story and matches the two-hat discipline
  (customer-specific = a LegalEntity + its config, never new code).
- **(B) Minimal — `OrgUnit.is_root` + `root_slug`** flag. Faster but weaker (a
  flag, not an entity) and does not carry legal attributes.

**Decision: (A).** AASTMT and GOFSCO each become a `LegalEntity`; every
`OrgUnit` hangs off one; every `people`/`mdm` scoped query starts from the
legal-entity subtree.

### 4.3 Scope boundary enforcement

- `get_allowed_org_unit_ids(user)` **stays** the single scoping primitive, but now
  resolves against the user's legal-entity root(s) first.
- `people/_scoped()` and `people` `org_lookup` filters already key off
  `org_unit_id`; they automatically respect the boundary once `OrgUnit` carries
  `legal_entity`.
- **Backend**: new helper `get_visible_legal_entities(user)` → `LegalEntity`
  list; global admins bypass; scoped users get their root(s).
- **Frontend**: `fetchOrgUnits(token, { legalEntityId })` and
  `fetchLegalEntities(token)`. The Employees/OrgUnits pickers always send the
  active legal entity; nothing cross-tenant is ever listed.

---

## 5. LAW 3 — THICK ENTITIES (F3 + F4)

### 5.1 Compensation as a matrix + ledger (F3)

Replace `Employee.basic_salary` (scalar) with:

```
CompensationComponent  (ReferenceSet-driven catalog — §3.2)
  code, name, name_ar, direction (earning|deduction), category,
  is_eosi_base, is_gosi_base, is_wps_relevant, is_taxable,
  sort_order, valid_from, valid_to          # governed enum + policy flags

CompensationPlan       (config: "the matrix" per job/pay-grade/org)
  org_unit FK (nullable=global), pay_grade code, job_family code,
  component code FK, amount, currency, frequency (monthly|annual),
  effective_start, effective_end            # the grid the user asked for

EmployeeCompensation   (the additive ledger per employee)
  employee FK, component FK, amount, currency, frequency,
  effective_start, effective_end,           # effective-dated, append-only
  source_rule FK(ComplianceRule, nullable), # provenance: why this amount
  reason (PersonnelEvent FK, nullable),     # the event that created it
  is_verified, verified_by, verified_at     # Law 3
```

- **"Current salary" becomes a derived query** — the set of `EmployeeCompensation`
  rows whose `effective_start <= today < effective_end`, summed by direction. No
  stored scalar to go stale.
- `basic_salary` migrates to an initial `EmployeeCompensation(component=basic)` row
  (data backfill, not data loss).
- `PayslipLine.line_type` becomes a FK/`code` to `CompensationComponent`; a
  payslip is then *exactly* the materialization of the active
  `EmployeeCompensation` + `ComplianceRule` calculations — which is already the
  lineage carrier (`rule_id`/`rule_version`/`inputs` on `PayslipLine`). This closes
  the loop between "matrix" and "signable payslip".

### 5.2 Benefits & care programs (F4)

`BenefitType` + `EmployeeBenefit` exist but are thin. Upgrade to config + enrollment:

```
BenefitPlan              (config, reusable)
  code, name, name_ar, category (benefit_category ref set),
  eligibility_rule (JSON: min service, kuwaitization, job_family),
  cost_center/org_unit scope, is_care_program (housing/medical/school/…),
  is_eosi_base, is_taxable, active

EmployeeBenefitEnrollment (additive, effective-dated)
  employee FK, benefit_plan FK, monthly_value, employee_contribution,
  employer_contribution, effective_start, effective_end,
  status (enrolled|waived|terminated), is_verified, verified_by, verified_at
```

Key upgrade over today: **enrollment is a lifecycle record** (enroll → waive →
terminate), not a static link, and benefits are **config-driven plans** (a
GOFSCO housing allowance is a configured `BenefitPlan`, never a hardcoded line).

### 5.3 Credentials / documents / evidence (F4)

`Certification` (5 fields) is a placeholder. Replace with a governed document
model that reuses the platform `evidence` app:

```
Credential               (the qualification itself)
  employee FK, credential_type (certification_type ref set),
  title, issuer, credential_no, issued_date, expiry_date,
  status (active|expired|revoked|pending_verification),
  is_verified, verified_by, verified_at

EmployeeDocument         (the artifact — scanned image/PDF)
  employee FK, document_type (document_type ref set: passport/civil_id/…),
  evidence FK (evidence.Evidence, nullable) — the governed blob + checksum,
  file_ref, physical_location (hard-copy vault reference),
  issue_date, expiry_date, is_verified, verified_by, verified_at

CredentialVerification   (append-only verification trail)
  credential FK, requested_at, verified_by, verified_at,
  method (source_check|notary|issuer_api), result (pass|fail|expired), notes
```

- Digital + physical ("hard copy location") both supported — the user's "documents
  and evidence" point.
- Expiry is first-class (renewal alerts become trivial: `expiry_date < today + 30d`).

### 5.4 Competencies & skills (F4)

```
Competency               (the taxonomy — ReferenceSet or dedicated catalog)
  code, name, name_ar, competency_type (skill|knowledge|certification|behavior),
  category (competency_category ref set), proficiency_scale FK

EmployeeCompetency       (additive, effective-dated assessment)
  employee FK, competency FK, proficiency_level (proficiency_level ref set),
  assessed_by, assessed_at, source (self|manager|assessment|credential),
  effective_start, effective_end, is_verified

LearningRecord           (optional, later phase)
  employee FK, program FK, started_at, completed_at, status, score
```

This is the seed of the **succession / gap analysis** module: competencies are
queried ("who has level-4 welding + valid KOC HSE cert"), not just displayed.

### 5.5 Rewards & penalties (F4)

Unify into an employee-relations ledger (append-only, severity-tiered):

```
EmployeeAction           (one table, two directions — config-driven)
  employee FK, action_type (employee_action_type ref set:
      reward|counseling|warning|penalty|termination|commendation|…),
  severity (severity ref set: minor|moderate|major|critical),
  effective_date, description, related_event FK (PersonnelEvent),
  issued_by, acknowledged_by, acknowledged_at,
  attachments → EmployeeDocument, is_verified, verified_by, verified_at
```

- **Config, not hardcode**: the *kinds* of reward/penalty are `ReferenceValue`s,
  so "verbal warning" vs. "written warning" vs. "suspension" is data the customer
  can change, not a migration.
- **Verifiable & append-only**: an action is recorded, acknowledged, and linked to
  evidence; never silently edited. Severity tiers feed escalation policy later.

### 5.6 The chronicle — one ring to rule them all

`PersonnelEvent` already exists as a bitemporal append-only chronicle but is
restricted to `Employee`/`Position`. Extend `ENTITY_CHOICES` → the full HR entity
set (via `hr_entity` ref set, §3.2) and **emit an event on every mutating fact**
(salary change, benefit enrollment, credential verification, disciplinary action,
leave approval). This gives a single replayable timeline + KPI source, and makes
"additive & verifiable" *systemic* rather than per-model.

---

## 6. TERMINOLOGY — enterprise names (drop the ad-hoc labels)

| Nibras today | Enterprise standard (SAP SF / Oracle HCM / Workday) |
|---|---|
| `basic_salary` | **Base Pay** component within **Compensation** |
| `*_code` fields | **Lookups / Picklists** (SF "Picklist", Oracle "Lookup") |
| `Employee` + `Position` | **Employee Central / Workforce Structures (Jobs, Positions, Grades)** |
| `LeaveRecord` | **Absence / Time Off** (Workday "Absence", SF "Time Off") |
| `BenefitType` | **Benefits / Total Rewards** |
| `Loan` | **Deduction** (recurring) within **Payroll** |
| `Certification` | **Credentials / Qualifications** (SF "Credentials", Workday "Certifications") |
| (missing) | **Competencies / Skills Cloud** (Oracle "Skills Center") |
| `PersonnelEvent` | **Effective-Dated Employment Instance / Bi-temporal History** |
| `EmployeeAction` | **Employee Relations / Disciplinary Action** (SF "Employee Relations") |
| `EmployeeDocument` | **Employee File / Document Management** (Workday "Worker Documents") |
| `ComplianceRule` | **Payroll Rules / Formula Engine** (Oracle "Fast Formula", SF "Business Rules") |

Adopting these names in UI/API labels (not necessarily code) signals competence
to an HR buyer and maps 1:1 to the competitor feature matrix in
`NIBRAS-MASTER-STRATEGY.md` §3.3.

---

## 7. PHASED PLAN

Ordered by dependency and risk. Each phase is independently shippable and gate-verified.

| Phase | Scope | Key files | Gate |
|---|---|---|---|
| **P0 — Govern the enums (F1)** | Add the ~24 missing ReferenceSets to the seed command; switch free-text fields (`gender`, `leave_type`, `loan_type`, `cert_type`, `permission_type`, `pattern`, `grade`, `line_type`) to `*_code`; extend `_validate_reference_code` to all of them. Migrate + backfill existing rows to canonical codes. | `people/models.py`, `people/serializers.py`, `people/management/commands/seed_gofsco.py`, migrations | `makemigrations --check`, backfill script run, full backend pytest |
| **P1 — Legal entity / tenancy (F2)** | Add `mdm.LegalEntity`; `OrgUnit.legal_entity` FK; root-scoping in `get_visible_org_units`; `fetchOrgUnits`/`fetchLegalEntities` + picker filters. | `mdm/models.py`, `mdm/views.py`, `accounts/rbac_utils.py`, `carbon-frontend/src/api/orgUnits.js` + pickers | cross-tenant isolation test (GOFSCO user sees zero AASTMT rows) |
| **P2 — Compensation matrix (F3)** | `CompensationComponent` (ref set + policy flags), `CompensationPlan`, `EmployeeCompensation` ledger; derived current-salary; migrate `basic_salary`; wire `PayslipLine.line_type`→component. | `people/models.py`, new `people/compensation.py` (derived view), migrations, `people/serializers.py` | one payroll month computes from ledger, traceable to components |
| **P3 — Documents & credentials (F4)** | `Credential`, `EmployeeDocument`, `CredentialVerification`; reuse `evidence.Evidence`; expiry/alerts. | `people/models.py`, `evidence/` integration, serializers/views | verify+expiry round-trip; evidence checksum linkage |
| **P4 — Benefits & care (F4)** | `BenefitPlan` + `EmployeeBenefitEnrollment` (config + lifecycle). | `people/models.py`, serializers/views | enrollment lifecycle + eosi-base computation |
| **P5 — Competencies (F4)** | `Competency`, `EmployeeCompetency`; taxonomy + assessments. | `people/models.py`, serializers/views | gap-analysis query (who has X at level Y) |
| **P6 — Rewards & penalties (F4)** | `EmployeeAction` + severity tiers + acknowledgement + evidence. | `people/models.py`, serializers/views | append-only audit; escalation-ready |
| **P7 — Unify the chronicle (F2…F4)** | Extend `PersonnelEvent` entity/kind to all entities; emit events on every mutation; timeline + KPI endpoints. | `people/models.py`, `people/signals.py`/service layer | full replay of one employee's history from events |

**Rule of thumb for every phase:** reference data (P0) first, because P1–P6 all
consume governed enums. P2 (compensation) is the *proof* phase — it's what makes
"one legally-signable payroll month" (§1.3 of the strategy doc) actually
computable from a matrix rather than a scalar.

---

## 8. OPEN DECISIONS (confirm before building)

1. **LegalEntity (A) vs. root-flag (B)** — I recommend (A) `mdm.LegalEntity`.
2. **`Competency` as ReferenceSet vs. dedicated catalog** — recommend a dedicated
   `Competency` model (it has a proficiency scale + category, richer than a flat
   enum) but a `competency_category` ref set inside it.
3. **Currency** — single-currency (KWD) now, or multi-currency columns on the
   compensation ledger from day one? Recommend `currency` column now (cheap,
   avoids a later migration) with KWD default.
4. **Scope of P0** — do we switch *every* hardcoded `choices=` (e.g. `PayrollRun.
   STATUS_CHOICES`, `ComplianceRule.CATEGORY_CHOICES`) to ref sets, or only
   user-visible classifiers? Recommend all (§3.2), status enums included — but
   confirm because it touches the compliance engine's own fields.

---

## 9. WHAT THIS IS NOT

- **Not a rewrite.** It is a *governance uplift* on top of the existing
  `mdm.ReferenceSet`, `people.PersonnelEvent`, and `ComplianceRule` machinery.
- **Not customer-specific.** Every phase is product-core (two-hat discipline);
  GOFSCO specifics land as config (rotation patterns, Kuwaitization rules, their
  benefit plans), never code.
- **Not big-bang.** Seven independently-shippable phases, P0 first.
