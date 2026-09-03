# DESIGN — People/HR Reference Data Governance + Single-Root Org Scoping

**Status:** Ratified (Master Architect, ADR-0027 + ADR-0028)
**Date:** 2026-08-30
**Domain:** `mdm` (reference core) + `people` (Nibras HRMS wedge)
**Canonical for:** any worker touching People metadata/lookups or org-unit scoping.

---

## 1. Problem statement (two defects, both confirmed in code)

### Defect A — Reference data is *half-wired* and *inconsistent*

The Trust Platform already has a proper reference-data core: `mdm.ReferenceSet` +
`mdm.ReferenceValue`, with steward, domain (`catalog.DataDomain`), version,
lifecycle (`draft→active→deprecated→archived` + `transition_to()`), and temporal
validity (`valid_from`/`valid_to` + `get_current_values(as_of=…)`).

But the `people` domain does **not** actually reference it. Only 4 fields route
through the core, and they do it weakly — as **plain `CharField`s storing a code
string**, validated at write-time only by `_validate_reference_code()` in
`people/serializers.py`:

| Field | ReferenceSet | Today |
|---|---|---|
| `Employee.employment_type_code` | `employment_type` | soft string |
| `Employee.contract_type_code` | `contract_type` | soft string |
| `Employee.nationality_code` | `nationality` | soft string |
| `Position.job_family_code` | `job_family` | soft string |

A string field gives **none** of the four things reference data is for:
1. **No referential integrity** — a code can be deprecated/archived later and the
   row silently keeps the stale string.
2. **No temporal binding** — `get_current_values(as_of=…)` is checked only at
   write; a payslip re-run for a past period cannot know which `ReferenceValue`
   was current then.
3. **No governance lineage** — steward/domain/provenance are unreachable from the
   record.
4. **Silent drift** — `_validate_reference_code` *passes through* when the set
   doesn't exist (correct for seeding) or when the value is blank, so a typo is
   accepted silently in production.

### Defect B — Org units are a single global tree with no root anchor

`mdm.OrgUnit` is one global self-referencing tree (no tenant field — by design,
RULE_1 / ADR-0015 "one deployment = one organisation"). But **two independent
root trees are seeded into the same table**:

- `core/management/commands/seed_aastmt_org.py` → root `AAST` (`org_type='university'`, `parent=None`)
- `mdm/management/commands/seed_gofsco_org.py` → root `GOFSCO` (`org_type='company'`, `parent=None`)

`OrgUnitViewSet.get_queryset()` lets a **global admin see the entire table**, and
`carbon-frontend/src/api/orgUnits.js::fetchOrgUnits` returns the whole flat list.
So the AASTMT deployment shows `GOFSCO → Ahmadi Base → Drilling Division…` in its
org-unit dropdowns. **Two organisations' trees mingle.**

---

## 2. Ratified decisions

### ADR-0027 — Governed lookups are FK to `ReferenceValue` (drop the code string)

Every governed lookup on a `people` record becomes a **real `ForeignKey` to
`mdm.ReferenceValue`**. The `*_code` CharFields are **removed**, not mirrored.

- **Write path:** the record stores the `ReferenceValue` PK. The `code` is
  resolved via join at read time.
- **Read path:** serializers expose the resolved value as a nested object
  `{ id, code, label, set }` (see §4). No denormalized code column.
- **Delete policy:** `on_delete=PROTECT`. A governed value in use is never
  deleted — it is `transition_to('deprecated')`/`archived`, which is the correct
  enterprise behaviour and preserves bitemporal history.
- **Why not a string mirror:** the code is reachable via one join; a mirror is a
  second source of truth that *can* drift and must be reconciled by a DQ rule
  anyway. FK-only removes the drift surface entirely.

### ADR-0028 — Single root OrgUnit = deployment anchor; seeds are instance-gated

- **One deployment = one root `OrgUnit`.** The root is the tenant anchor. Exactly
  one active `parent=None` unit per deployment; every other unit descends from it.
- **No `tenant_id`** anywhere (RULE_1). Isolation is the deployment/database
  boundary (ADR-0015).
- **Seeds are instance-gated** on `settings.INSTANCE_NAME` (`DJANGO_INSTANCE_NAME`)
  / `DJANGO_BRAND`. `seed_aastmt_org` runs only on the AASTMT instance;
  `seed_gofsco_org` only on the GOFSCO instance. They never both run on one DB.
- **All org-unit queries default to the deployment root subtree**
  (`get_descendant_ids(include_self=True)`), not the flat global list.

---

## 3. Full field inventory (single source of truth)

Three buckets. **Bucket 1** = governed reference data → FK to `ReferenceValue`.
**Bucket 2** = workflow state → stays `choices` (NOT reference data). **Bucket 3**
= versioned rule data → already correct, do not touch.

### Bucket 1 — Governed lookups (become FK to ReferenceValue)

| Model | Current field | Target field | ReferenceSet | Set exists? |
|---|---|---|---|---|
| `Employee` | `nationality` (free text) + `nationality_code` (soft) | `nationality` | `nationality` | ✅ |
| `Employee` | `employment_type_code` (soft) | `employment_type` | `employment_type` | ✅ |
| `Employee` | `contract_type_code` (soft) | `contract_type` | `contract_type` | ✅ |
| `Employee` | `gender` (free text) | `gender` | `gender` | ✅ |
| `Employee` | `rotation` (free text) | `rotation` | `rotation_pattern` | ✅ |
| `Position` | `job_family_code` (soft) | `job_family` | `job_family` | ✅ |
| `Position` | `grade` (free text) | `grade` | `grade` | ❌ new |
| `LeaveEntitlement` | `leave_type` (free text) | `leave_type` | `leave_type` | ✅ |
| `LeaveRecord` | `leave_type` (free text) | `leave_type` | `leave_type` | ✅ |
| `Loan` | `loan_type` (free text) | `loan_type` | `loan_type` | ❌ new |
| `AttendancePermission` | `permission_type` (free text) | `permission_type` | `permission_type` | ❌ new |
| `Certification` | `cert_type` (free text) | `cert_type` | `cert_type` | ❌ new |
| `RotationSchedule` | `pattern` (free text) | `pattern` | `rotation_pattern` | ✅ |
| `PayslipLine` | `line_type` (free text) | `line_type` | `payslip_line_type` | ❌ new |
| `BenefitType` | `category` (hardcoded choices) | `category` | `benefit_category` | ✅ |
| `ComplianceRule` | `category` (hardcoded choices) | `category` | `compliance_category` | ❌ new |
| `ComplianceRule` | `jurisdiction` (free text, default `KW`) | `jurisdiction` | `jurisdiction` | ❌ new |

### Bucket 2 — Workflow state (stay `choices`, NOT reference data)

`PayrollRun.status`, `Position.status`, `LeaveRecord.status`, `Loan.status`,
`LoanInstallment.status`, `AttendanceRecord.status`, `PersonnelEvent.ENTITY_CHOICES`,
`PersonnelEvent.KIND_CHOICES`.

> State machines are owned by the process, not stewarded master data. Do **not**
> move them into MDM. (`PersonnelEvent.KIND_CHOICES` is the only borderline case —
> promote later only if a governed cross-domain HR event taxonomy is required.)

### Bucket 3 — Business rules (already correct)

`ComplianceRule` is the *versioned* rule library (KLL/PIFSS/WPS):
`is_authoritative`, `provenance`, `inputs_schema`, `formula_ref`, `test_cases`.
This is **rule data**, not reference data. Do not change its shape (only its
`category`/`jurisdiction` fields become governed per Bucket 1).

---

## 4. Read/write contract (FK-only)

### Serializer read shape (every Bucket-1 field)

```json
{
  "nationality": { "id": 12, "code": "EGY", "label": "Egyptian", "set": "nationality" }
}
```

`null` when unset. The nested object is produced by a shared
`GovernedValueField`/`serializer` in `mdm/serializers.py` (one implementation,
reused by all 17 fields — no per-field ad-hoc resolution).

### Serializer write shape

Accept **either** of (resolve to `ReferenceValue` PK, then validate current-ness
against the correct `ReferenceSet`):

```json
{ "nationality": 12 }                    // ReferenceValue id
{ "nationality": "EGY" }                 // code (resolved within the field's set)
```

Illegal/invalid → `ValidationError` (400). Blank/`null` → null (optional fields).

### Temporal correctness

The FK pins to a *specific* `ReferenceValue` row, so a historical record keeps
its value even after the set evolves. Read-time "as-of" rendering uses
`get_current_values(as_of=…)` only where a *current label* is wanted (e.g. UI
dropdowns); stored records always render their bound value's `code`/`label`.

---

## 5. Phased plan

| Phase | Role | Scope | Status |
|---|---|---|---|
| NIR-5A | backend-worker | Models + migration: add FKs, drop free-text/code strings, data-migrate code→PK | READY |
| NIR-5B | backend-worker | Serializers/views/seeds/DQ: `GovernedValueField`, write resolution, seed updates | READY |
| NIR-5C | backend-worker | Seed 7 new reference sets (admin data, RULE_16) | READY |
| NIR-5D | frontend-worker | People pages render nested refs; dropdowns source reference sets | PLANNED |
| NIR-6A | backend-worker | Single-root invariant + instance-gated seeds | READY |
| NIR-6B | frontend-worker | Org-unit dropdown/tree scoped to deployment root | PLANNED |

Details in `TASKS.md` (Phases NIR-5A…NIR-6B). This doc is the canonical spec; the
phases point here and carry only dispatch-specific steps.

---

## 6. Non-negotiables

1. **RULE_16 — no fabrication.** New reference sets/values are seeded by admins
   (management commands are the sanctioned admin-entry path), never created by
   application/serializer code at write time.
2. **No `tenant_id`** on any model (RULE_1). Single-root org scoping only.
3. **`on_delete=PROTECT`** on every Bucket-1 FK. Governed values are deprecated,
   never deleted.
4. **One implementation of value resolution** (`GovernedValueField`) — no 17-way
   copy-paste.
5. **Test partitioning** (TASKS.md MASTER DIRECTIVE): backend runs one app at a
   time (`pytest people -q`, `pytest mdm -q`), never the full suite.
