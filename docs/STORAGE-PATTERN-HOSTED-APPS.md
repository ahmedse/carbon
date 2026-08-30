# Storage Pattern for Hosted Apps — Typed Tables vs `dataschema`

**Status:** Accepted · 2026-08-30 · see `.ai-toolkit/decisions/0025-typed-vs-dataschema-storage.md`

This note answers a question every hosted app on the Carbon Data Trust Platform hits:
*"Where should my domain data live — typed Django models, or `dataschema.DataTable/DataRow`?
And if I use typed tables, do I lose governance, DQ, and lineage?"*

The short answer: **an app that owns its data should use typed tables. You do not lose
governance/DQ/MDM by doing so — because the trust primitives are not monolithic.**

## The trust stack is not all-or-nothing

"Governance" and "DQ" each split into a **decoupled half** (works on any typed table) and
a **`dataschema`-coupled half** (only works on `DataTable`/`DataRow`). Knowing the seam is
the whole point.

### Governance

| Half | Mechanism | Typed tables? |
|---|---|---|
| Audit trail | `GovernanceEvent(entity_type, entity_id, before, after)` via `catalog.audit_utils.emit_governance_event()` | ✅ generic target, no FK — `mdm.ReferenceSet` already uses it |
| Asset catalog + quality badge + visual lineage | `catalog.AssetProfile` (FK→`DataTable`/`DataField`), `catalog.TableRelation` (`DataTable`→`DataTable`) | ❌ `dataschema`-only |

### Data Quality

| Half | Mechanism | Typed tables? |
|---|---|---|
| Rule definitions | `dq.DQRule` — standalone, no `dataschema` FK (ADR 0006) | ✅ independent, reusable |
| Evaluation engine | `dq/engine.py::evaluate(rule_def, rows)` — pure fn over any object with `.id` + `.values` | ✅ table-agnostic |
| Binding a rule to a **dataschema** target | `dq.RuleFieldAssignment.data_table/data_field` | ❌ `dataschema`-only |
| Binding a rule to a **typed-model** target | `dq.ModelRuleAssignment(rule, model_label, field_name)` | ✅ generic platform primitive |
| Persisted result / score / profile / freshness | `DQResult`, `TableProfile`, `FieldProfile` | ❌ `dataschema`-only |

**Consequence:** DQ is **target-agnostic**. One `DQRule` catalog + one `engine.evaluate()`
bind to *both* dataschema fields (`RuleFieldAssignment`) and typed-model fields
(`ModelRuleAssignment`). What remains `dataschema`-only is the *persisted* result/score/
profile/freshness. For typed tables, evaluate via `dq.typed_gate.check_instances()` (same
verdict shape as `gate.check_rows`) and persist **run-scoped summaries** in the domain —
never a per-row typed result store (it explodes at scale).

> **`ModelRuleAssignment` is a `dq` core primitive**, not per-app: `dq` references models
> by `model_label` (validated via `apps.get_model` in `clean()`) and never imports an app,
> so RULE_3 holds. Hosted apps only *register rows*. It is the typed-model twin of
> `RuleFieldAssignment`.

### MDM / Reference data

Fully decoupled — usable by any typed model, and already in use
(`people.Employee.org_unit → mdm.OrgUnit`). `ReferenceValue` carries **temporal validity**
(`ReferenceSet.get_current_values(as_of=...)`), ideal for HR/domain enums whose valid set
changes over time (nationality, contract type, grade, GOSI category).

## The reference implementation: `emissions`

`emissions` already draws the correct line:

| Emissions layer | Storage | In DQ/catalog graph? |
|---|---|---|
| Inbound **measurements** (activity data) | `dataschema.DataRow` | ✅ DQ-scored, catalogued |
| **Reference/authority** (`EmissionFactor`, `CalculationRule`) | typed | ❌ self-versioned |
| **Master/config** (`OrganizationalBoundary`, `ReportingPeriod`) | typed | ❌ |
| **Results** (`Calculation`, FK→`DataRow`) | typed | ❌ carries lineage breadcrumb |

Only the noisy inbound **measurements** go to `dataschema` — that is where persisted DQ
scoring earns its keep. Everything owned/authoritative/derived is typed.

## The rule for a system-of-record hosted app

If your app **owns** its data (it is the system of record, not a consumer of an upstream
ERP), apply this split:

1. **Master data, domain state, results → typed models.** You get DB referential
   integrity, strong types (`Decimal`, dates), and per-row org-scope (RULE_12) that
   `dataschema` JSON rows cannot give.
2. **No `AssetProfile`/quality badge/visual lineage on those tables** — accepted, by
   design (emissions master data has none either).
3. **Emit `GovernanceEvent`** on regulated/material writes (salary change, run commit) —
   the audit half of governance *is* available; use it.
4. **Bind `mdm.ReferenceSet`/`ReferenceValue`** for enums, preferring temporal-valid
   reference sets over hardcoded choices.
5. **Bind DQ rules to typed fields via `dq.ModelRuleAssignment`** (generic); run with
   `dq.typed_gate.check_instances()`; persist run-scoped summaries in the domain. Route
   only measurements needing a persisted DQ *score/profile/freshness* through `dataschema`.
6. **Lineage seam:** any typed result derived from a governed measurement carries the
   source `DataRow` id / `row_hash` (like `Calculation.data_row`), keeping replay and any
   future `dataschema` migration additive.

## Applying it to People & Payroll (Nibras)

Nibras is the **HR system of record**, so:

| Data | Storage | Governance |
|---|---|---|
| Employee, Position, Loan, Benefit (master/state) | typed `people.*` | DB integrity + `GovernanceEvent` on material writes; MDM for enums |
| `ComplianceRule` (authority) | typed, self-versioned (`rule_id`+`version`+`is_authoritative`) | version + provenance |
| Attendance / timesheet / variable inputs (measurements) | typed now; `AttendanceRecord.source_row → dataschema.DataRow` when device/ERP feeds land | full DQ once on `dataschema` |
| `PayrollRun`, `PayslipLine`, `LoanInstallment` (results) | typed, FK/breadcrumb to source | `inputs` carries `rule_id`+`rule_version`+source `DataRow` id |

Non-negotiable seam: `PayslipLine.inputs` (and any measurement-derived figure) carries the
source `DataRow` id / `row_hash`, so governing attendance via `dataschema` later is
additive, not a rewrite.
