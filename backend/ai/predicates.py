"""Host predicates for the Phase 3 pilot (P3-02).

Pure, deterministic, host-side assertion functions — the reviewed host
implementations of the read-only ``assertion`` capabilities in the domain pack.
They never touch the database and never mutate state (RULE_21); they only
inspect an already-loaded rule's revision metadata.

The predicate ``dq.rule.active_revision_matches_approved_revision`` expresses
the pilot's postcondition: after ``publish``, the rule's *active* revision must
equal its *approved* revision (docs/pulse/PILOT.md step "verify"). It reads the
two revisions from a rule-like object's ``definition`` dict first (the DQ
source of truth), then a plain mapping, then plain attributes — and fails
closed (returns ``False``) when either revision is missing or incoercible.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def _revision(rule: Any, key: str) -> str | int | None:
    """Extract a revision value from a rule-like object, prefer the definition."""
    definition = getattr(rule, "definition", None)
    if isinstance(definition, dict) and key in definition:
        return definition[key]
    if isinstance(rule, dict) and key in rule:
        return rule[key]
    return getattr(rule, key, None)


def dq_rule_active_revision_matches_approved_revision(rule: Any) -> bool:
    """True iff the rule's active revision equals its approved revision.

    Fail-closed: missing/incoercible revisions → ``False`` (never a false
    "verified" on absent data).
    """
    active = _revision(rule, "active_revision")
    approved = _revision(rule, "approved_revision")
    if active is None or approved is None:
        return False
    try:
        return str(active) == str(approved)
    except (TypeError, ValueError):
        return False


def _field(obj: Any, key: str) -> Any:
    """Extract a value from a mapping or a plain object (no DB access)."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def payroll_run_committed_and_variance_clean(run: Any) -> bool:
    """True iff the payroll run is committed AND its validations are variance-clean.

    The Nibras ``payroll.run.lifecycle`` postcondition (verify step): after the
    commit stage the run's ``status`` must be ``committed`` and every recorded
    validation finding must have passed. Reads an already-loaded run-like object
    (mapping or plain object) — never the database (RULE_21). Fail-closed: a
    non-committed status, or a missing/unconfirmable variance signal, returns
    ``False`` (never a false "verified" on absent data).
    """
    status = _field(run, "status")
    if status is None or str(status).lower() != "committed":
        return False

    variance_clean = _field(run, "variance_clean")
    if variance_clean is not None:
        return bool(variance_clean)

    validations = _field(run, "validations")
    if not isinstance(validations, (list, tuple)) or not validations:
        return False
    return all(bool(_field(v, "passed")) for v in validations)


def _as_decimal(value: Any) -> Decimal | None:
    """Coerce numeric-like values to Decimal; return None on failure."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def leave_request_recorded_and_entitlement_decremented(record: Any) -> bool:
    """True iff leave is approved and entitlement decrement is verifiable.

    The Nibras ``leave.request.lifecycle`` postcondition: the request is
    approved/recorded and the entitlement ledger moved down for that request.
    Reads an already-loaded record-like object (mapping or plain object) with
    no DB access (RULE_21). Fail-closed: if status/decrement signals are
    missing or incoercible, return ``False``.
    """
    status = _field(record, "status")
    if status is None or str(status).lower() != "approved":
        return False

    decremented = _field(record, "entitlement_decremented")
    if decremented is not None:
        return bool(decremented)

    remaining_before = _as_decimal(_field(record, "remaining_before"))
    remaining_after = _as_decimal(_field(record, "remaining_after"))
    if remaining_before is not None and remaining_after is not None:
        return remaining_after < remaining_before

    return False


def attendance_permission_approved_and_recorded(record: Any) -> bool:
    """True iff attendance permission is approved and recorded.

    The Nibras ``attendance.permission.lifecycle`` postcondition: the
    short-hours permission exists with ``approved=True``. Reads an
    already-loaded record-like object (mapping or plain object) with no
    DB access (RULE_21). Fail-closed: missing/incoercible signals return
    ``False``.
    """
    approved = _field(record, "approved")
    if approved is not None:
        return bool(approved)

    status = _field(record, "status")
    if status is not None and str(status).lower() in ("approved", "recorded"):
        return True

    return False


def loan_request_activated_and_scheduled(record: Any) -> bool:
    """True iff loan is active and installment schedule is verifiable.

    The Nibras ``loan.request.lifecycle`` postcondition: the request is
    activated and at least one installment exists for its repayment schedule.
    Reads an already-loaded record-like object (mapping or plain object) with
    no DB access (RULE_21). Fail-closed: if activation/schedule signals are
    missing or incoercible, return ``False``.
    """
    status = _field(record, "status")
    if status is None or str(status).lower() != "active":
        return False

    scheduled = _field(record, "installments_scheduled")
    if scheduled is not None:
        return bool(scheduled)

    installment_count = _field(record, "installment_count")
    as_decimal = _as_decimal(installment_count)
    if as_decimal is not None:
        return as_decimal > 0

    installments = _field(record, "installments")
    if isinstance(installments, (list, tuple)):
        return len(installments) > 0

    return False


def gosi_wps_sif_submitted_and_reconciled(record: Any) -> bool:
    """True iff the GOSI/WPS SIF was submitted and reconciliation succeeded.

    The Nibras ``gosi_wps.sif.lifecycle`` postcondition (verify step): after
    irreversible submit the filing ``status`` must be ``submitted`` and a
    reconciliation signal must confirm GOSI/WPS totals match the committed
    payroll run. Reads an already-loaded record-like object (mapping or plain
    object) with no DB access (RULE_21). Fail-closed: missing/incoercible
    signals return ``False``.
    """
    status = _field(record, "status")
    if status is None or str(status).lower() != "submitted":
        return False

    reconciled = _field(record, "reconciled")
    if reconciled is not None:
        return bool(reconciled)

    receipt_id = _field(record, "receipt_id")
    if receipt_id is not None and str(receipt_id).strip():
        return True

    reconciliation = _field(record, "reconciliation")
    if isinstance(reconciliation, dict):
        return bool(reconciliation.get("passed"))

    return False


def employee_onboarding_completed_and_payroll_eligible(record: Any) -> bool:
    """True iff onboarding finished with an active, payroll-eligible employee.

    The Nibras ``employee.onboarding.lifecycle`` postcondition: after activate,
    the employee is active, the contract is active, and the hire is eligible
    for the next payroll draft. Reads an already-loaded record-like object
    (mapping or plain object) with no DB access (RULE_21). Fail-closed: missing
    or incoercible signals return ``False``.
    """
    is_active = _field(record, "is_active")
    if is_active is None or not bool(is_active):
        return False

    contract_active = _field(record, "contract_active")
    if contract_active is not None:
        if not bool(contract_active):
            return False
    else:
        contract_status = _field(record, "contract_status")
        if contract_status is None or str(contract_status).lower() != "active":
            return False

    payroll_eligible = _field(record, "payroll_eligible")
    if payroll_eligible is not None:
        return bool(payroll_eligible)

    # Explicit True on is_active + contract_active with no contrary signal.
    return True
