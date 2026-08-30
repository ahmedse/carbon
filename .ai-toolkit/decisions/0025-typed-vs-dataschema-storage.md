# ADR 0025 — Storage pattern for hosted apps: typed tables for owned data, dataschema for governed measurements

- **Status:** Accepted
- **Date:** 2026-08-30
- **Deciders:** Master Architect
- **Area:** data | cross-cutting

## Context
Carbon is a Data Trust core (Catalog, MDM, DQ, metadata-driven `dataschema`) that
*hosts* domain apps. A recurring question when building a hosted app (emissions,
People & Payroll/Nibras, future domains) is **where owned domain data should live**:
as typed Django models in the app, or as `dataschema.DataTable/DataRow` (JSON rows).

The assumption "you must use `dataschema` to get governance/DQ/lineage" is **false**.
Verified against the code, both governance and DQ split into a **decoupled half**
(usable by typed tables) and a **dataschema-coupled half** (not):

- **Governance — audit half (decoupled):** `catalog.GovernanceEvent(entity_type,
  entity_id, before, after)` via `catalog.audit_utils.emit_governance_event()` is a
  generic string+int target with no FK. `mdm.ReferenceSet.transition_to()` already
  uses it on a typed model.
- **Governance — catalog half (coupled):** `catalog.AssetProfile` (FK→`DataTable`/
  `DataField`), quality-status rollup, and `catalog.TableRelation` lineage graph
  (`DataTable`→`DataTable`) are hard-wired to `dataschema`.
- **DQ — rules + engine (decoupled):** `dq.DQRule` is standalone (ADR 0006);
  `dq/engine.py::evaluate(rule_def, rows)` is a pure function over any object with
  `.id` + `.values` (the gate wraps raw dicts in `_RowProxy`).
- **DQ — binding + results (coupled):** `dq.RuleFieldAssignment`, `DQResult`,
  `TableProfile`, `FieldProfile`, and freshness checks all FK→`DataTable`/`DataField`.
  To let DQ target **typed models** too, `dq` gains a generic (platform-level) twin of
  `RuleFieldAssignment` — `dq.ModelRuleAssignment(rule, model_label, field_name)` — so
  any hosted app binds `DQRule`s to typed fields without `dataschema`. This is a `dq`
  **core** primitive, not per-app; apps only register rows.
- **MDM (fully decoupled):** any typed model can FK `mdm.OrgUnit` (already:
  `people.Employee.org_unit`) or bind `mdm.ReferenceSet`/`ReferenceValue`
  (temporal validity via `get_current_values(as_of=...)`).

`emissions` already embodies the target split: inbound **measurements** (activity
data) live in `dataschema.DataRow`; **reference/authority** (`EmissionFactor`,
`CalculationRule`), **master/config** (`OrganizationalBoundary`, `ReportingPeriod`),
and **results** (`Calculation`, FK→`DataRow`) are typed and sit outside the DQ/catalog
graph.

## Decision
For a hosted app that is the **system of record** for its domain data:

1. **Owned master data, domain state, and results → typed Django models.** This buys
   DB referential integrity (FKs, unique constraints, `Decimal`, per-row org-scope for
   RULE_12) that `dataschema` JSON rows cannot provide. Mirrors emissions
   (`OrganizationalBoundary`/`ReportingPeriod`/`Calculation`).
2. **Do NOT expect `AssetProfile`, quality badges, or visual lineage** for those typed
   tables — that half of governance is dataschema-only, and that is acceptable/by-design
   for owned data.
3. **DO emit `GovernanceEvent`** on regulated/material writes (e.g. salary change,
   payroll-run commit) via `emit_governance_event(entity_type='...', entity_id=...)`,
   exactly as `ReferenceSet` does. The audit half of governance *is* available to typed
   tables and must be used for auditability.
4. **Bind `mdm.ReferenceSet`/`ReferenceValue`** for domain enums (nationality, contract
   type, grade, GOSI category), preferring reference sets with temporal validity over
   hardcoded choices.
5. **Bind DQ rules to typed fields via the generic `dq.ModelRuleAssignment`** primitive
   (`rule`, `model_label`="app.Model", `field_name`) — the typed-model twin of
   `RuleFieldAssignment`. Runner `dq.typed_gate.check_instances()` projects instances to
   `{field: value}` dicts and reuses `dq.engine.evaluate()` (same verdict shape as
   `gate.check_rows`). `dq` references models by label (validated via `apps.get_model` in
   `clean()`) and never imports an app — RULE_3 stays clean. Choose `model_label` string
   over a `ContentType`/`GenericForeignKey` (this repo avoids generic FKs).
6. **Do NOT add a generic per-row typed `DQResult` store** — at scale it explodes. Persist
   **run-scoped summaries** in the domain (e.g. `people.PayrollRunValidation` with counts +
   `sample_failures[:20]`). Route inbound *measurements* needing a persisted DQ
   *score/profile/freshness* through `dataschema` (the emissions "activity data" analog);
   everything owned/derived stays typed and uses `ModelRuleAssignment`.
7. **Lineage seam:** any typed *result* derived from a governed measurement must carry
   the source `dataschema.DataRow` id / `row_hash` (as `emissions.Calculation.data_row`
   does), so replay and future dataschema migration stay additive, not a rewrite.

## Alternatives Considered
- **All owned data in `dataschema.DataRow` (pure Option B)** — rejected: loses DB
  referential integrity and strong types on money/date math, gives only coarse
  per-`Module` (per-table) org-scope which collides with RULE_12's per-row scoping, and
  is slow to build. Governance gained is mostly irrelevant for SoR-owned master data.
- **Typed-only with no `dataschema` at all** — rejected for high-volume noisy
  *measurements* (attendance), where persisted DQ scoring/profiling genuinely earns its
  keep and only exists on `dataschema` targets.
- **Overload `RuleFieldAssignment` with a nullable typed target** — rejected: muddies the
  dataschema binding. A separate `ModelRuleAssignment` keeps each binding table single-
  purpose.
- **`ContentType`/`GenericForeignKey` target on `ModelRuleAssignment`** — rejected: this
  repo avoids generic FKs; `model_label` + `apps.get_model` validation is greppable and
  sufficient for admin-managed, low-volume bindings.
- **Generic per-row typed `DQResult`/score store** — deferred: per-row persistence
  explodes at payroll scale; add a ContentType-targeted result store only if a central
  typed-DQ dashboard is later required (separate decision).

## Consequences
- **Positive:** owned data keeps DB-enforced integrity + per-row org-scope; auditability
  via `GovernanceEvent`; reference data via MDM; DQ becomes target-agnostic (one catalog +
  engine binds to both `dataschema` and typed models via `ModelRuleAssignment`);
  measurements still get full persisted DQ when they need it; clean, additive path later.
- **Negative / trade-off:** typed tables get no catalog card / quality badge / visual
  lineage; DQ on typed data is validator-only (no persisted `DQResult`) unless routed
  through `dataschema`; two storage modes to reason about per app.
- **Do NOT re-try:** putting SoR master data in `dataschema.DataRow` "to get governance"
  — the governance you'd gain (AssetProfile/lineage) doesn't need JSON storage, and the
  integrity you'd lose does.

## References
- `backend/catalog/models.py` (`AssetProfile`, `GovernanceEvent`, `TableRelation`)
- `backend/catalog/audit_utils.py` (`emit_governance_event`)
- `backend/dq/models.py` (`DQRule`, `RuleFieldAssignment`, `DQResult`, `TableProfile`,
  `FieldProfile`), `backend/dq/engine.py` (`evaluate`), `backend/dq/gate.py` (`_RowProxy`)
- `backend/mdm/models.py` (`OrgUnit`, `ReferenceSet.get_current_values`, `ReferenceValue`)
- `backend/emissions/models.py` (`Calculation.data_row`, `CalculationRule`,
  `OrganizationalBoundary`, `ReportingPeriod`) — the reference split
- `backend/people/models.py` (Nibras HR — SoR, applies this ADR)
- ADR 0006 (DQ rule standalone), ADR 0010 (domain vocabulary out of generic core)
- `docs/STORAGE-PATTERN-HOSTED-APPS.md`
