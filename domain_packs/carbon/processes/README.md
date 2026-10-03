# Processes

ProcessDefinition YAML for the Carbon pack (ADR-0050). The engine loads these
files. It does not invent steps.

Each ProcessDefinition is a governed lifecycle over a real host feature. Every
step names a capability that corresponds to an existing Carbon host operation
(a view/service/model), and the `rule:` id references a `CR-*` rule in
`domain_packs/carbon/assurance/rules/`.

| File | What it governs | Backed by |
|---|---|---|
| `dq.rule.release.yaml` | DQ rule validate, review, publish, verify | `dq.services:run_single_rule` + P3-09 human-task inbox |
| `inventory.onboarding.lifecycle.yaml` | AASTMT benchmark O1. People write the host records. Pulse quotes the calculation payload. | `emissions/onboarding_o1.py`, `emissions/models.py` ReportingPeriod / InventorySource / EmissionFactor |
| `coverage.target.lifecycle.yaml` | Data completeness: targets over streams — declare goal, assign tasks, enter rows, calculate, derive honest progress | `emissions/views.py` CoverageTargetViewSet / CoverageTaskViewSet, `emissions/coverage_targets.py` target_progress |
| `campus.activity_intake.lifecycle.yaml` | Campus intake VERB reached from one coverage row: contract, append-only row, restatement, calculation handoff, exclusion | `emissions/campus_intake.py`, `emissions/intake_api.py` CoverageRowSubmissionAPIView / CoverageRowExclusionAPIView |
| `calculation.run.lifecycle.yaml` | Calculation / batch recalculation: legal factor, Scope 2 method, no offsets, supersede stale, audit trail | `emissions/views.py` CalculateAPIView / BatchCalculateAPIView, `emissions/models.py` Calculation + CalculationAudit |
| `period.governance.lifecycle.yaml` | Reporting-period state machine: boundary, open, lock, submit, verify, close (one open period) | `emissions/views.py` ReportingPeriodViewSet, `PeriodLockService`, `VerificationService` |
| `assurance.engagement.lifecycle.yaml` | P1 external assurance: five ISO 14064-3 VVB fields; recording does not assure | `emissions/intake_api.py` AssuranceEngagementAPIView, `emissions/campus_intake.py` assurance_status |
| `recalculation.trigger.lifecycle.yaml` | GHG Protocol Ch. 5 base-year recalculation trigger: record, measure variance, resolve, never rewrite in place | `emissions/views.py` BaseYearViewSet.recalculate + RecalculationTriggerViewSet.resolve |
| `disclosure.export.lifecycle.yaml` | P2 disclosure projection (ESRS E1-6 / IFRS S2 / CDP C6), shape_only, no new kilogram | `emissions/disclosure.py`, `emissions/views.py` DisclosureExportAPIView |

## Capabilities

Step `capability` ids name a governed host action in the same `carbon.*`
convention the O1 onboarding leaf established. Only the DQ pilot's four
capabilities are also registered as `capabilities:` contracts in
`api_catalog.yaml` and resolved by `backend/ai/capability_registry.py`; the
carbon lifecycle capabilities describe their host operation but are not
promoted to registry contracts here (that promotion is a separate,
Master-facing step and would change the pinned pilot capability set).
