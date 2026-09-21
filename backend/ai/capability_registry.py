"""Host-side capability → host-action registry (P3-01).

Single source of truth for resolving a capability contract's ``host_action``
key to a host callable (or the human-task sentinel). Deliberately import-free
(stdlib only) so both :mod:`ai.models.capability` (the loader) and
:mod:`ai.models.process` (the process validator) may import it with no cycle and
no database access at import time.

Registry values are ``"module:qualname"`` paths. They are resolved **lazily**
with :func:`importlib.import_module` by the loader — never here — so this module
never imports ``dq``, ``ai.predicates``, or any Django app at import time.

The human-task sentinel marks capabilities whose effect is a durable human task
(the P3-09 inbox), not a synchronous host callable. The loader recognizes it and
permits it only for ``kind == "human_task"``.
"""

from __future__ import annotations

# Sentinel for human-task capabilities (P3-09 inbox; not a module path).
HUMAN_TASK_SENTINEL = "human_task:inbox"

# host_action key → "module:qualname" (or the human-task sentinel).
HOST_ACTION_REGISTRY: dict[str, str] = {
    # ── DQ pilot (P3-02 / docs/pulse/PILOT.md ``dq.rule.release``) ──────────
    # validate (read-only) → review (human task) → publish (mutation) → verify
    # (assertion). The DQ host today exposes rule-running as its single host
    # service; ``validate`` binds to it as the read-only projection and
    # ``publish`` binds to the same service as the post-approval mutation whose
    # consent gate (RULE_21) lives in the command boundary. A dedicated
    # ``dq.services.publish_rule`` will supersede the publish binding in P3-05a.
    "dq.rule.validate": "dq.services:run_single_rule",
    "dq.rule.publish": "dq.services:run_single_rule",
    "dq.rule.active_revision_matches_approved_revision": (
        "ai.predicates:dq_rule_active_revision_matches_approved_revision"
    ),
    # ── Nibras People & Payroll run lifecycle (domain_packs/nibras) ─────────
    # draft → compute (mutation) → validate (mutation) → review (human task) →
    # commit (mutation, final/irreversible; triggers WPS SIF) → verify
    # (assertion). Each mutation binds to its DRF run-lifecycle view; the
    # command boundary owns the consent gate (RULE_21). Read bindings back the
    # process's grounding lookups. Values resolve lazily (no people import here).
    "payroll.run.compute": "people.views:PayrollRunComputeView",
    "payroll.run.validate": "people.views:PayrollRunValidateView",
    "payroll.run.commit": "people.views:PayrollRunCommitView",
    "payroll.run.list": "people.views:PayrollRunListCreateView",
    "payroll.run.get": "people.views:PayrollRunDetailView",
    "payroll.payslip.list": "people.views:PayslipLineListView",
    "payroll.run.committed_and_variance_clean": (
        "ai.predicates:payroll_run_committed_and_variance_clean"
    ),
    # ── Nibras Leave request lifecycle (domain_packs/nibras) ───────────────
    # submit (mutation) → review (human task) → record (mutation) → verify
    # (assertion). Mutations/reads bind to existing People leave views; review
    # uses the inbox sentinel and resolves fail-closed like payroll.
    "leave.request.submit": "people.self_views:LeaveSelfCollectionView",
    "leave.request.record": "people.views:LeaveRecordDetailView",
    "leave.request.list": "people.views:LeaveRecordListCreateView",
    "leave.entitlement.list": "people.views:LeaveEntitlementListCreateView",
    "leave.request.recorded_and_entitlement_decremented": (
        "ai.predicates:leave_request_recorded_and_entitlement_decremented"
    ),
    # ── Nibras Loan request lifecycle (domain_packs/nibras) ────────────────
    # submit (mutation) → review (human task) → activate (mutation) → verify
    # (assertion). Mutations/reads bind to People loan views; review uses the
    # inbox sentinel and resolves fail-closed like payroll/leave.
    "loan.request.submit": "people.self_views:LoanSelfCollectionView",
    "loan.request.activate": "people.views:LoanDetailView",
    "loan.list": "people.views:LoanListCreateView",
    "loan.installment.list": "people.views:LoanInstallmentListCreateView",
    "loan.request.activated_and_scheduled": (
        "ai.predicates:loan_request_activated_and_scheduled"
    ),
    # ── Nibras Employee onboarding lifecycle (PEC-5B) ─────────────────────
    # submit (mutation) → review (human task) → activate (mutation, final) →
    # verify (assertion). Binds to People employee views; review uses inbox.
    "employee.onboarding.submit": "people.views:EmployeeListCreateView",
    "employee.onboarding.activate": "people.views:EmployeeDetailView",
    "employee.onboarding.list": "people.views:EmployeeListCreateView",
    "employee.onboarding.get": "people.views:EmployeeDetailView",
    "employee.onboarding.completed_and_payroll_eligible": (
        "ai.predicates:employee_onboarding_completed_and_payroll_eligible"
    ),
    # ── Nibras GOSI/WPS SIF filing lifecycle (PEC-5A / P5) ────────────────
    # generate (mutation) → validate (mutation) → review (human task) →
    # submit (mutation, final/irreversible statutory filing) → verify
    # (assertion). Generate/submit bind to the existing WPS export view;
    # validate binds to payroll validations list; review uses the inbox
    # sentinel. Values resolve lazily (no people import here).
    "gosi_wps.sif.generate": "people.views:PayrollRunWPSExportView",
    "gosi_wps.sif.validate": "people.views:PayrollRunValidationsListView",
    "gosi_wps.sif.submit": "people.views:PayrollRunWPSExportView",
    "gosi_wps.sif.submitted_and_reconciled": (
        "ai.predicates:gosi_wps_sif_submitted_and_reconciled"
    ),
    # Human-task sentinel (recognized by the loader, not importable).
    HUMAN_TASK_SENTINEL: HUMAN_TASK_SENTINEL,
}
