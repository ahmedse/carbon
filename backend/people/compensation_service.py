# File: people/compensation_service.py
# Compensation ledger service (ADR-0029) — the business logic for the
# append-only, effective-dated EmployeeCompensation ledger.
#
# Views stay thin: validate → call service → serialize → return. All money math
# happens in the DB (Decimal-exact via Sum/aggregate) — never float().
#
# RULE_3: people imports only core apps (catalog) + its own modules.

from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from catalog.audit_utils import emit_governance_event

from .chronicle import record_event
from .models import CompensationComponent, EmployeeCompensation


class CompensationService:
    """Facade over the EmployeeCompensation ledger.

    Owns: effective-dated "current" resolution, DB-computed totals, and the
    append/verify mutations (with chronicle + governance event emission).
    """

    @staticmethod
    def current_lines(employee, as_of=None):
        """Return the QuerySet of open/effective rows for ``employee`` as of
        ``as_of`` (defaults to today): ``effective_start <= as_of`` and
        (``effective_end IS NULL`` or ``effective_end >= as_of``)."""
        if as_of is None:
            as_of = timezone.localdate()
        return (
            EmployeeCompensation.objects.filter(
                employee=employee,
                effective_start__lte=as_of,
            )
            .filter(
                Q(effective_end__isnull=True) | Q(effective_end__gte=as_of)
            )
            .select_related('component', 'source_rule', 'verified_by', 'created_by')
        )

    @staticmethod
    def history_lines(employee):
        """Full ledger history for ``employee``, newest first."""
        return (
            EmployeeCompensation.objects.filter(employee=employee)
            .select_related('component', 'source_rule', 'verified_by', 'created_by')
            .order_by('-effective_start', '-created_at')
        )

    @staticmethod
    def ledger_totals(employee, as_of=None):
        """DB-computed monthly earnings/deductions for ``employee`` (Decimal-exact).

        Only ``frequency='monthly'`` lines are included; earnings vs. deductions
        are split by ``component__direction``. No float() anywhere.
        """
        current = CompensationService.current_lines(employee, as_of=as_of)
        monthly = current.filter(frequency='monthly')

        earnings = (
            monthly.filter(component__direction='earning')
            .aggregate(total=Sum('amount'))['total'] or Decimal('0')
        )
        deductions = (
            monthly.filter(component__direction='deduction')
            .aggregate(total=Sum('amount'))['total'] or Decimal('0')
        )

        return {
            'monthly_earnings': earnings,
            'monthly_deductions': deductions,
            'net_monthly': earnings - deductions,
        }

    @staticmethod
    def append_line(
        employee,
        *,
        component,
        amount,
        currency,
        frequency,
        effective_start,
        effective_end=None,
        source_rule=None,
        source_plan=None,
        reason_event=None,
        reason_note='',
        user,
    ):
        """Append a new effective-dated ledger line (additive update).

        Inside ``transaction.atomic()``: close the prior open row for the same
        component (``effective_end = new.effective_start``), create the new row,
        then emit a ``salary_change`` chronicle event and a
        ``compensation_change`` governance event. Returns the new row.
        """
        with transaction.atomic():
            EmployeeCompensation.objects.filter(
                employee=employee,
                component=component,
                effective_end__isnull=True,
            ).update(effective_end=effective_start)

            line = EmployeeCompensation.objects.create(
                employee=employee,
                component=component,
                amount=amount,
                currency=currency,
                frequency=frequency,
                effective_start=effective_start,
                effective_end=effective_end,
                source_rule=source_rule,
                source_plan=source_plan,
                reason_event=reason_event,
                reason_note=reason_note,
                created_by=user,
            )

            record_event(
                entity_type='Employee', entity_id=employee.pk,
                event_kind='salary_change',
                effective_date=effective_start,
                user=user,
                before={'component': component.code, 'amount': None},
                after={
                    'component': component.code,
                    'amount': str(amount),
                    'direction': component.direction,
                    'currency': currency,
                },
                notes=reason_note or f"New {component.code} line added",
            )
            emit_governance_event(
                entity_type='Employee', entity_id=employee.pk,
                action='compensation_change',
                before=None,
                after={
                    'component': component.code,
                    'amount': str(amount),
                    'effective_start': str(effective_start),
                },
                user=user,
            )
            return line

    @staticmethod
    def reflect_benefit(benefit, *, user):
        """Mirror (or un-mirror) an EmployeeBenefit into the compensation ledger.

        Reflect (``benefit.reflect_in_salary=True``): close any open line tagged
        ``source_benefit=benefit``, then append a NEW earning line for the
        benefit's component (default ``other_allowance``) with the benefit's
        amount and effective window. Reflection lines are additive and tagged
        with ``source_benefit`` so they never clobber manual lines that share
        the same component.

        Un-reflect (``reflect_in_salary=False``): close any open
        ``source_benefit=benefit`` lines (no-op if none).
        """
        employee = benefit.employee
        mirror_qs = EmployeeCompensation.objects.filter(
            employee=employee,
            source_benefit=benefit,
        )
        # "Still current" mirrored lines: open-ended OR ending on/after the
        # point where the new (or closed) line takes effect. This is what makes
        # reflection idempotent regardless of whether the benefit has a finite
        # effective_end.
        current_qs = mirror_qs.filter(
            Q(effective_end__isnull=True) | Q(effective_end__gte=benefit.effective_start)
        )

        with transaction.atomic():
            if not benefit.reflect_in_salary:
                current_qs.update(effective_end=timezone.localdate())
                return None

            component = benefit.component
            if component is None:
                component, _ = CompensationComponent.objects.get_or_create(
                    code='other_allowance',
                    defaults={
                        'name': 'Other Allowance',
                        'name_ar': 'بدل آخر',
                        'direction': 'earning',
                        'is_wps_relevant': True,
                        'is_variable': True,
                        'sort_order': 90,
                        'is_active': True,
                    },
                )

            # Never reflect a benefit into a deduction component.
            if component.direction != 'earning':
                current_qs.update(effective_end=timezone.localdate())
                return None

            # Close prior mirrored rows for THIS benefit only.
            current_qs.update(effective_end=benefit.effective_start)

            line = EmployeeCompensation.objects.create(
                employee=employee,
                component=component,
                amount=benefit.monthly_amount,
                currency='KWD',
                frequency='monthly',
                effective_start=benefit.effective_start,
                effective_end=benefit.effective_end,
                source_benefit=benefit,
                reason_note=f"Benefit: {benefit.benefit_type.name}",
                created_by=user,
            )

            record_event(
                entity_type='Employee', entity_id=employee.pk,
                event_kind='salary_change',
                effective_date=benefit.effective_start,
                user=user,
                before={'component': component.code, 'amount': None},
                after={
                    'component': component.code,
                    'amount': str(benefit.monthly_amount),
                    'direction': component.direction,
                    'currency': 'KWD',
                    'source': 'benefit',
                },
                notes=f"Benefit {benefit.benefit_type.name} reflected into salary",
            )
            emit_governance_event(
                entity_type='Employee', entity_id=employee.pk,
                action='compensation_change',
                before=None,
                after={
                    'component': component.code,
                    'amount': str(benefit.monthly_amount),
                    'effective_start': str(benefit.effective_start),
                    'source_benefit': benefit.pk,
                },
                user=user,
            )
            return line

    @staticmethod
    def verify_line(line, *, verified_by):
        """Mark a ledger line as verified (Tier-2 gate) and audit it."""
        line.is_verified = True
        line.verified_by = verified_by
        line.verified_at = timezone.now()
        line.save(update_fields=['is_verified', 'verified_by', 'verified_at'])

        emit_governance_event(
            entity_type='Employee', entity_id=line.employee_id,
            action='compensation_verified',
            before={'is_verified': False},
            after={
                'is_verified': True,
                'line_id': line.pk,
                'component': line.component.code,
                'amount': str(line.amount),
            },
            user=verified_by,
        )
        return line
