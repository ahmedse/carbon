# File: people/loan_service.py
# Loan installment materialization (NSR-3A).
#
# When a Loan becomes active (correspondence approve / status sync), persist
# ``LoanInstallment`` rows from ``calculate_loan_schedule``. Generated rows are
# the schedule source of truth for payroll; Admin/API CRUD remains available
# but should treat engine-generated rows as authoritative after approval.
#
# Idempotency: skip-if-any — if the loan already has installment rows, return
# them unchanged (no delete+recreate). Safe on correspondence re-save.
#
# RULE_3: people imports only its own modules + django — never emissions/AI.

from __future__ import annotations

from datetime import date

from django.db import transaction

from . import calculation_engine
from .models import ComplianceRule, Loan, LoanInstallment


class LoanServiceError(Exception):
    """Raised when loan installment materialization cannot proceed."""


def _add_months(d: date, n: int) -> date:
    """Return the 1st of the month ``n`` months after ``d``'s month.

    Matches seed_gofsco / payroll month indexing (installment 1 = start month).
    """
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def _resolve_loan_schedule_rule():
    """Return (rule, allow_non_authoritative) for loan amortization.

    Prefer an authoritative ``loan_schedule`` rule (same contract as payroll).
    Fall back to any matching rule with ``allow_non_authoritative=True`` so
    demo/seed environments can still materialize.
    """
    qs = ComplianceRule.objects.filter(category__code="other").order_by(
        "-effective_date", "-updated_at",
    )
    authoritative = None
    fallback = None
    for rule in qs:
        formula = (rule.inputs_schema or {}).get("formula") or {}
        if formula.get("type") != "loan_schedule":
            continue
        if rule.is_authoritative and authoritative is None:
            authoritative = rule
        elif fallback is None:
            fallback = rule
    if authoritative is not None:
        return authoritative, False
    if fallback is not None:
        return fallback, True
    return None, False


def materialize_loan_installments(loan: Loan) -> list:
    """Persist ``LoanInstallment`` rows for ``loan`` from the calculation engine.

    Idempotent (skip-if-any): if any installments already exist for this loan,
    return the existing queryset list without creating duplicates.

    Returns:
        list of ``LoanInstallment`` instances (existing or newly created).

    Raises:
        LoanServiceError: when no ``loan_schedule`` ComplianceRule is configured.
    """
    existing = list(loan.installments.order_by("installment_no"))
    if existing:
        return existing

    rule, allow_non_auth = _resolve_loan_schedule_rule()
    if rule is None:
        raise LoanServiceError(
            "No loan_schedule ComplianceRule is configured; "
            "cannot materialize installments."
        )

    schedule = calculation_engine.calculate_loan_schedule(
        rule, loan, allow_non_authoritative=allow_non_auth,
    )
    created = []
    with transaction.atomic():
        # Re-check under the transaction to avoid races on concurrent approve.
        if loan.installments.exists():
            return list(loan.installments.order_by("installment_no"))
        for inst in schedule["installments"]:
            due = _add_months(loan.start_date, inst["installment_no"] - 1)
            row = LoanInstallment.objects.create(
                loan=loan,
                installment_no=inst["installment_no"],
                due_date=due,
                amount=inst["amount"],
                principal_portion=inst["principal_portion"],
                interest_portion=inst["interest_portion"],
                status="scheduled",
            )
            created.append(row)
    return created
