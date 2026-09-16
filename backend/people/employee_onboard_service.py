# File: people/employee_onboard_service.py
# Hire/onboarding hooks (NSR-4A) — leave entitlement propagation + optional
# opening basic compensation ledger line.
#
# Views stay thin: after Employee save, call ``onboard_employee``. Leave
# eligibility/propagation lives in leave_policy_service (not duplicated here).
# Opening basic is never fabricated: only when ``opening_basic`` is provided.
#
# Verification policy: opening ledger lines are appended **unverified**.
# NSR-2A payroll requires a verified monthly ``basic`` line — HR must verify
# (CompensationService.verify_line) before the employee can be paid.

from decimal import Decimal

from django.utils import timezone

from .compensation_service import CompensationService
from .leave_policy_service import propagate_for_employee
from .models import CompensationComponent


def onboard_employee(employee, *, opening_basic=None, currency='KWD', user=None):
    """Run post-hire hooks for ``employee``.

    Args:
        employee: saved ``Employee`` instance.
        opening_basic: optional Decimal (or numeric) monthly basic amount.
            When None/omitted, no compensation ledger line is created.
        currency: ISO currency for the opening line (default ``KWD``).
        user: acting user for ledger provenance (may be None).

    Returns:
        dict with ``leave`` (propagate_for_employee result) and
        ``opening_line`` (EmployeeCompensation or None).

    Raises:
        CompensationComponent.DoesNotExist: when ``opening_basic`` is set but
            catalog component ``code='basic'`` is not seeded (production
            expects seed; tests must create the component).
    """
    leave_result = propagate_for_employee(employee)

    opening_line = None
    if opening_basic is not None:
        amount = opening_basic if isinstance(opening_basic, Decimal) else Decimal(str(opening_basic))
        component = CompensationComponent.objects.get(code='basic')
        effective_start = employee.join_date or timezone.localdate()
        opening_line = CompensationService.append_line(
            employee,
            component=component,
            amount=amount,
            currency=currency or 'KWD',
            frequency='monthly',
            effective_start=effective_start,
            reason_note='Opening basic on hire',
            user=user,
        )
        # Intentionally leave is_verified=False — payroll (NSR-2A) requires
        # HR verification before the line is used as basic SoT.

    return {
        'leave': leave_result,
        'opening_line': opening_line,
    }
