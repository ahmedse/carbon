# ADR 0060 — Data Migration Studio (two destination kinds)

- **Status:** Accepted
- **Date:** 2026-09-28
- **Deciders:** Master Architect (Nibras). Human "go" 2026-09-28 supersedes pending Catalog ACK 20260928-1 for installing `inbound`. Catalog still owns DMS-2.
- **Area:** backend | frontend | data | cross-cutting

## Context
GOFSCO must leave Hard Task. HR (`emp_2378` prepares; `emp_2400` commits) will upload
CSV, map columns, smoke-test, and commit. The same studio must also serve the original
Carbon path: schema → Data Product → `DataTable` / `DataRow`.

Those stores are different (ADR 0025 / RULE_27). Today's scraps are not the product:
`importexport.ImportJob` writes only `DataRow`; `BulkImportWizard` parses in the
browser; `import_gofsco_employees` is a developer command. Putting employees in a
Data Product "to get governance" repeats the rejected Option B of ADR 0025. Copying
the wizard into every hosted app repeats the parser.

## Decision
1. **Product** is **Data Migration Studio** (shared pipe + Wizard). It is **not**
   a new Activity Bar studio. IA stays in the two existing apps (RULE_5, one
   nav per app):
   - People: `/people/import`, `/people/import/:id` — typed cartridges only.
   - Catalog Studio: existing **Imports** `/catalog/imports` (+ `/:id`) —
     Data Product kind only. `importexport` stays the Data Product writer.
   Django app `inbound` (core).
2. **Two destination kinds**, never one mapper:
   - `data_product` — commit via existing `ImportService` / `BulkImportService` into
     a `DataTable`. Catalog owns this adapter.
   - `typed_object` — commit via a **named cartridge** registered by a hosted app
     (`EmployeeSnapshot`, `LeaveOpeningBalance`, `LeaveHistory`). Nibras owns People
     cartridges. The platform never imports `people`.
3. **Pipe** (in `inbound`, domain-free): file bytes, hash, encoding, delimiter,
   saved template, value crosswalk, staged projections, smoke envelope, reject CSV,
   reconcile counts, prepare vs commit. Registry is a label + callback the app
   registers at `AppConfig.ready()` — same direction as `dq.ModelRuleAssignment`.
4. **Cartridges are declared load objects**, not ORM reflection. No
   `Employee._meta` field picker. A new object is a new cartridge.
5. **Typed commit** goes through the domain service and emits `GovernanceEvent`.
   Smoke uses `dq.typed_gate` and a run-scoped summary. No `DataRow` as the
   employee or leave record. Attendance may still keep `source_row` (Path M).
6. **Doors:** HR uses People → Configuration → Import. Stewards use Catalog
   Studio → Connect & move → Imports. Same `Wizard` chrome; kind is locked by
   the door. No `/migrate` activity. No Import item on My/Team.
7. **v1 Master defaults** (human may override before DMS-3):
   - First typed object: `EmployeeSnapshot` (key `employee_no`).
   - Leave history is conversion (already decided; no manager notify; no live
     approval path).
   - Opening-balance number wins; history rows must not add to `used_days`.
   - Prepare ≠ commit. `inbound:commit` is the write. `emp_2400` (People lead)
     commits; `emp_2378` prepares. `ahmed` may both.
   - Payroll history / YTD is out of v1.
8. **Pulse:** Chat does not commit a load (ADR-0046). No Agent write tool until a
   later phase + Catalog/Pulse COMMS.

## Alternatives Considered
- **Studio inside Catalog / Dataset Hub** — rejected: DatasetVersion stores
  `DataRow`; PII and steward-approve are the wrong ACL/SoD for HR SoR.
- **Studio only inside `people`** — rejected: the Data Product path already exists
  and would be rebuilt.
- **New hosted app `migration`** — rejected: hosted apps must not import siblings.
- **Extend `ImportJob` with nullable `data_table` + `model_label`** — rejected:
  one binding, two jobs (same class as overloading `RuleFieldAssignment`).
- **Generic map onto any `app.Model.field`** — rejected: LSMW class of error.

## Consequences
- **Positive:** one receive/map/smoke chrome; two honest commits; RULE_3 holds;
  Data Trust and Nibras both consume the studio; second typed domain (EduOS)
  registers a cartridge without a new wizard.
- **Negative / trade-off:** new core app; Catalog ACK before install; two adapters
  to test; PII lives on the batch until retention policy, not on a Data Product.
- **Do NOT re-try:** landing people master data as `DataRow` for DTI/lineage;
  browser-only parse as the source of truth; treating Dataset approval as HR
  commit; Pulse Chat Confirm for load commit.

## References
- ADR 0025, 0006, 0010, 0027, 0040, 0046
- RULE_3, RULE_27, RULE_30, RULE_35
- `docs/migration/DATA-MIGRATION-STUDIO.md`
- `docs/migration/SCREEN-SPEC-DMS.md`
- Track **DMS** in `TASKS.md`
