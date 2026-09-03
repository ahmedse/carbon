# File: people/views.py
# People & Payroll API views (thin — orchestration lives in services).
#
# CBAC (NIR-1C): reads → ``people:view``, writes → ``people:manage``.
# Superusers and global admins bypass capability checks (full access).
# RULE_12: employee/payroll reads are org-scoped for non-admin users via
# ``accounts.rbac_utils.get_visible_org_units``.

import csv
import io
from datetime import date

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import ProtectedError, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.rbac_utils import get_visible_org_units
from catalog.audit_utils import emit_governance_event
from core.feedback import AppFeedback

from .calculation_engine import NonAuthoritativeRuleError
from .chronicle import record_event, snapshot_employee, snapshot_position
from .compensation_service import CompensationService
from .services import CalculationService
from .models import (
    AttendancePermission,
    AttendanceRecord,
    BenefitType,
    Certification,
    CompensationComponent,
    CompensationPlan,
    ComplianceRule,
    Employee,
    EmployeeBenefit,
    EmployeeCompensation,
    LeaveEntitlement,
    LeaveRecord,
    Loan,
    LoanInstallment,
    PayrollRun,
    PayrollRunValidation,
    PayslipLine,
    PersonnelEvent,
    Position,
    RotationSchedule,
)
from .permissions import PeopleAccess, is_global_admin
from .sensitivity import (
    COMPENSATION_FIELDS,
    can_view_compensation,
    mask_employee,
    mask_employee_list,
)
from .serializers import (
    AttendancePermissionSerializer,
    AttendanceRecordSerializer,
    BenefitTypeSerializer,
    CertificationSerializer,
    CompensationComponentSerializer,
    CompensationPlanSerializer,
    ComplianceRuleSerializer,
    EmployeeBenefitSerializer,
    EmployeeCompensationSerializer,
    EmployeeSerializer,
    LeaveEntitlementSerializer,
    LeaveRecordSerializer,
    LoanInstallmentSerializer,
    LoanSerializer,
    PayrollRunSerializer,
    PayrollRunValidationSerializer,
    PayslipLineSerializer,
    PersonnelEventSerializer,
    PositionSerializer,
    RotationScheduleSerializer,
)
from .payroll_service import PayrollRunService, PayrollServiceError, _json_safe
from .validation import persist_findings, validate_write


def _visible_org_unit_ids(user):
    """Org unit ids the user may view (RULE_12 org scoping)."""
    return [ou.id for ou in get_visible_org_units(user)]


def _scoped(user, queryset, org_lookup):
    """Apply RULE_12 org scoping to ``queryset`` for non-global-admins."""
    if is_global_admin(user):
        return queryset
    return queryset.filter(**{org_lookup: _visible_org_unit_ids(user)})


def _blocked_write_response(instance):
    """Return a 422 Response when the Tier-1 DQ gate blocks the write, else None."""
    gate = validate_write(instance)
    if gate["blocked"]:
        return Response(
            {
                "detail": "DQ validation blocked this write",
                "sample_failures": gate["sample_failures"],
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return None


class ComplianceRuleListCreateView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request):
        qs = ComplianceRule.objects.all()
        return Response({
            'count': qs.count(),
            'results': ComplianceRuleSerializer(qs, many=True).data,
        })

    def post(self, request):
        serializer = ComplianceRuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ComplianceRuleDetailView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request, pk):
        rule = get_object_or_404(ComplianceRule, pk=pk)
        return Response(ComplianceRuleSerializer(rule).data)

    def patch(self, request, pk):
        rule = get_object_or_404(ComplianceRule, pk=pk)
        serializer = ComplianceRuleSerializer(rule, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        rule = get_object_or_404(ComplianceRule, pk=pk)
        emit_governance_event(
            entity_type='ComplianceRule',
            entity_id=rule.pk,
            action='delete',
            before={'pk': rule.pk},
            after=None,
            user=request.user,
        )
        rule.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmployeeListCreateView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request):
        if is_global_admin(request.user):
            qs = Employee.objects.all()
        else:
            qs = Employee.objects.filter(
                org_unit_id__in=_visible_org_unit_ids(request.user),
            )
        return Response({
            'count': qs.count(),
            'results': mask_employee_list(
                EmployeeSerializer(qs, many=True).data, request.user,
            ),
        })

    def post(self, request):
        serializer = EmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = Employee(**serializer.validated_data)
        blocked = _blocked_write_response(instance)
        if blocked is not None:
            return blocked
        serializer.save()
        record_event(
            entity_type='Employee', entity_id=serializer.instance.pk, event_kind='hired',
            effective_date=timezone.localdate(), user=request.user,
            before=None, after=snapshot_employee(serializer.instance),
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class EmployeeDetailView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def _get_queryset(self, user):
        if is_global_admin(user):
            return Employee.objects.all()
        return Employee.objects.filter(
            org_unit_id__in=_visible_org_unit_ids(user),
        )

    def get(self, request, pk):
        employee = get_object_or_404(self._get_queryset(request.user), pk=pk)
        return Response(mask_employee(EmployeeSerializer(employee).data, request.user))

    def patch(self, request, pk):
        employee = get_object_or_404(self._get_queryset(request.user), pk=pk)
        before = snapshot_employee(employee)
        old_salary = employee.basic_salary
        serializer = EmployeeSerializer(employee, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(employee, field, value)
        blocked = _blocked_write_response(employee)
        if blocked is not None:
            return blocked
        serializer.save()
        if old_salary != employee.basic_salary:
            event_kind = 'salary_change'
        elif before.get('org_unit_id') != employee.org_unit_id:
            event_kind = 'transferred'
        else:
            event_kind = 'profile_updated'
        record_event(
            entity_type='Employee', entity_id=employee.pk, event_kind=event_kind,
            effective_date=timezone.localdate(), user=request.user,
            before=before, after=snapshot_employee(employee),
        )
        return Response(serializer.data)

    def delete(self, request, pk):
        employee = get_object_or_404(self._get_queryset(request.user), pk=pk)
        was_active = employee.is_active
        before = snapshot_employee(employee)
        employee.is_active = False
        employee.save(update_fields=['is_active', 'updated_at'])
        emit_governance_event(
            entity_type='Employee',
            entity_id=employee.pk,
            action='delete',
            before={'is_active': was_active},
            after={'is_active': False},
            user=request.user,
        )
        record_event(
            entity_type='Employee', entity_id=employee.pk, event_kind='deactivated',
            effective_date=timezone.localdate(), user=request.user,
            before=before, after=None,
            notes='Soft delete (is_active=False)',
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmployeeCompensationView(APIView):
    """Full compensation ledger for one employee.

    GET  /employees/<pk>/compensation/
         Returns: current ledger (active today) with totals + full history.
         Requires ``people:view_compensation``. Every reveal is audited.

    POST /employees/<pk>/compensation/
         Append a new effective-dated line to the ledger.
         Requires ``people:manage`` (PeopleAccess non-GET gate).
         Always emits a ``salary_change`` PersonnelEvent.
    """

    permission_classes = [IsAuthenticated, PeopleAccess]

    def _get_employee(self, request, pk):
        qs = (
            Employee.objects.all()
            if is_global_admin(request.user)
            else Employee.objects.filter(org_unit_id__in=_visible_org_unit_ids(request.user))
        )
        return get_object_or_404(qs, pk=pk)

    def get(self, request, pk):
        if not can_view_compensation(request.user):
            return Response(
                {'detail': 'You do not have permission to view compensation.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        employee = self._get_employee(request, pk)
        today = timezone.localdate()

        current_qs = CompensationService.current_lines(employee, as_of=today)
        history_qs = CompensationService.history_lines(employee)
        current_data = EmployeeCompensationSerializer(current_qs, many=True).data
        history_data = EmployeeCompensationSerializer(history_qs, many=True).data
        totals = CompensationService.ledger_totals(employee, as_of=today)

        emit_governance_event(
            entity_type='Employee',
            entity_id=employee.pk,
            action='view_compensation',
            before=None,
            after={'as_of': str(today), 'lines_count': len(current_data)},
            user=request.user,
        )
        return Response({
            'employee_id': employee.pk,
            'as_of': str(today),
            'revealed_by': request.user.get_username(),
            'totals': totals,
            'current': current_data,
            'history': history_data,
            # legacy scalar kept for backwards compatibility during transition
            'basic_salary': str(employee.basic_salary),
        })

    def post(self, request, pk):
        """Append a new ledger line — the additive compensation update."""
        employee = self._get_employee(request, pk)
        ser = EmployeeCompensationSerializer(data={
            **request.data,
            'employee': employee.pk,
        })
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        line = CompensationService.append_line(
            employee,
            component=data['component'],
            amount=data['amount'],
            currency=data.get('currency', 'KWD'),
            frequency=data.get('frequency', 'monthly'),
            effective_start=data['effective_start'],
            effective_end=data.get('effective_end'),
            source_rule=data.get('source_rule'),
            source_plan=data.get('source_plan'),
            reason_event=data.get('reason_event'),
            reason_note=data.get('reason_note', ''),
            user=request.user,
        )
        return Response(EmployeeCompensationSerializer(line).data, status=status.HTTP_201_CREATED)


class CompensationComponentListView(APIView):
    """List all active compensation components (the governed catalog)."""

    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request):
        qs = CompensationComponent.objects.filter(is_active=True)
        if request.query_params.get('direction'):
            qs = qs.filter(direction=request.query_params['direction'])
        return Response(CompensationComponentSerializer(qs, many=True).data)

    def post(self, request):
        if not is_global_admin(request.user):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        ser = CompensationComponentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data, status=status.HTTP_201_CREATED)


class CompensationPlanListView(APIView):
    """The compensation matrix (config layer above the per-employee ledger)."""

    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request):
        qs = CompensationPlan.objects.filter(is_active=True).select_related('component', 'org_unit')
        if request.query_params.get('pay_grade'):
            qs = qs.filter(pay_grade_code=request.query_params['pay_grade'])
        if request.query_params.get('job_family'):
            qs = qs.filter(job_family_code=request.query_params['job_family'])
        return Response(CompensationPlanSerializer(qs, many=True).data)

    def post(self, request):
        if not is_global_admin(request.user):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        ser = CompensationPlanSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data, status=status.HTTP_201_CREATED)


class EmployeeCompensationVerifyView(APIView):
    """Mark a compensation line as verified (Tier-2 verification gate)."""

    permission_classes = [IsAuthenticated, PeopleAccess]

    def post(self, request, employee_pk, line_pk):
        line = get_object_or_404(EmployeeCompensation, pk=line_pk, employee_id=employee_pk)
        CompensationService.verify_line(line, verified_by=request.user)
        return Response(EmployeeCompensationSerializer(line).data)


class EmployeeDeactivateView(APIView):
    """Governed off-boarding: reason + effective date, soft delete, full audit trail.

    Replaces a bare DELETE. Deactivation is a lifecycle transition, so we require a
    reason and record it in both the chronicle and the governance audit trail.
    """

    permission_classes = [IsAuthenticated, PeopleAccess]

    def post(self, request, pk):
        employee = get_object_or_404(
            Employee.objects.all() if is_global_admin(request.user)
            else Employee.objects.filter(org_unit_id__in=_visible_org_unit_ids(request.user)),
            pk=pk,
        )
        reason = (request.data or {}).get('reason', '').strip()
        if not reason:
            raise AppFeedback(
                code='reason_required',
                title='Reason required',
                detail='A deactivation reason is required.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        effective_date = (request.data or {}).get('effective_date') or timezone.localdate().isoformat()
        was_active = employee.is_active
        before = snapshot_employee(employee)
        employee.is_active = False
        employee.save(update_fields=['is_active', 'updated_at'])
        emit_governance_event(
            entity_type='Employee',
            entity_id=employee.pk,
            action='deactivate',
            before={'is_active': was_active},
            after={'is_active': False, 'reason': reason, 'effective_date': str(effective_date)},
            user=request.user,
        )
        record_event(
            entity_type='Employee', entity_id=employee.pk, event_kind='deactivated',
            effective_date=timezone.localdate(), user=request.user,
            before=before, after=None,
            notes=reason,
        )
        return Response(mask_employee(EmployeeSerializer(employee).data, request.user))


class EmployeeReactivateView(APIView):
    """Re-onboard an inactive employee (records a ``reactivated`` chronicle entry)."""

    permission_classes = [IsAuthenticated, PeopleAccess]

    def post(self, request, pk):
        employee = get_object_or_404(
            Employee.objects.all() if is_global_admin(request.user)
            else Employee.objects.filter(org_unit_id__in=_visible_org_unit_ids(request.user)),
            pk=pk,
        )
        before = snapshot_employee(employee)
        employee.is_active = True
        employee.save(update_fields=['is_active', 'updated_at'])
        emit_governance_event(
            entity_type='Employee',
            entity_id=employee.pk,
            action='reactivate',
            before={'is_active': False},
            after={'is_active': True},
            user=request.user,
        )
        record_event(
            entity_type='Employee', entity_id=employee.pk, event_kind='reactivated',
            effective_date=timezone.localdate(), user=request.user,
            before=before, after=snapshot_employee(employee),
            notes=(request.data or {}).get('notes', '') or 'Reactivated',
        )
        return Response(mask_employee(EmployeeSerializer(employee).data, request.user))


class PayrollRunListCreateView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request):
        if is_global_admin(request.user):
            qs = PayrollRun.objects.all()
        else:
            qs = PayrollRun.objects.filter(
                org_unit_id__in=_visible_org_unit_ids(request.user),
            )
        return Response({
            'count': qs.count(),
            'results': PayrollRunSerializer(qs, many=True).data,
        })

    def post(self, request):
        serializer = PayrollRunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PayrollRunDetailView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def _get_queryset(self, user):
        if is_global_admin(user):
            return PayrollRun.objects.all()
        return PayrollRun.objects.filter(
            org_unit_id__in=_visible_org_unit_ids(user),
        )

    def get(self, request, pk):
        run = get_object_or_404(self._get_queryset(request.user), pk=pk)
        return Response(PayrollRunSerializer(run).data)

    def patch(self, request, pk):
        run = get_object_or_404(self._get_queryset(request.user), pk=pk)
        serializer = PayrollRunSerializer(run, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        run = get_object_or_404(self._get_queryset(request.user), pk=pk)
        if run.status == 'committed':
            raise AppFeedback(
                code='run_committed',
                title='Cannot delete: run is committed',
                detail='Cannot delete: run is committed',
                context={'payroll_run_id': run.pk, 'status': run.status},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        emit_governance_event(
            entity_type='PayrollRun',
            entity_id=run.pk,
            action='delete',
            before={'pk': run.pk, 'status': run.status},
            after=None,
            user=request.user,
        )
        run.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PayslipLineListView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request):
        qs = PayslipLine.objects.all()
        run_id = request.query_params.get('payroll_run')
        if run_id:
            qs = qs.filter(payroll_run_id=run_id)
        return Response({
            'count': qs.count(),
            'results': PayslipLineSerializer(qs, many=True).data,
        })


# ── NIR-3E: People & Payroll API surface ────────────────────────────────────
# Thin list-create / detail views over the new models, mirroring the NIR-1C
# pattern (CBAC + RULE_12 org scoping + Tier-1 DQ write gate).

class _GatedListCreateView(APIView):
    """Base list-create view: CBAC, RULE_12 org scoping, Tier-1 write gate."""

    permission_classes = [IsAuthenticated, PeopleAccess]
    model = None
    serializer_class = None
    org_lookup = None  # e.g. 'org_unit_id__in'; None → global reference data
    chronicle_event_kind = None  # set by subclasses that emit a PersonnelEvent on create

    def get(self, request):
        qs = self.model.objects.all()
        if self.org_lookup is not None:
            qs = _scoped(request.user, qs, self.org_lookup)
        return Response({
            'count': qs.count(),
            'results': self.serializer_class(qs, many=True).data,
        })

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.model(**serializer.validated_data)
        blocked = _blocked_write_response(instance)
        if blocked is not None:
            return blocked
        serializer.save()
        if self.chronicle_event_kind and type(serializer.instance) is Position:
            record_event(
                entity_type=type(serializer.instance).__name__,
                entity_id=serializer.instance.pk,
                event_kind=self.chronicle_event_kind,
                effective_date=timezone.localdate(), user=request.user,
                before=None, after=snapshot_position(serializer.instance),
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class _GatedDetailView(APIView):
    """Base detail view: CBAC, RULE_12 org scoping, Tier-1 write gate."""

    permission_classes = [IsAuthenticated, PeopleAccess]
    model = None
    serializer_class = None
    org_lookup = None
    chronicle_event_kind = None  # set by subclasses that emit a PersonnelEvent on update
    chronicle_snapshot = None  # callable: instance → dict snapshot (see chronicle.py)

    def _get_queryset(self, user):
        qs = self.model.objects.all()
        if self.org_lookup is not None:
            qs = _scoped(user, qs, self.org_lookup)
        return qs

    def get(self, request, pk):
        instance = get_object_or_404(self._get_queryset(request.user), pk=pk)
        return Response(self.serializer_class(instance).data)

    def patch(self, request, pk):
        instance = get_object_or_404(self._get_queryset(request.user), pk=pk)
        before = self.chronicle_snapshot(instance) if self.chronicle_snapshot else None
        serializer = self.serializer_class(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(instance, field, value)
        blocked = _blocked_write_response(instance)
        if blocked is not None:
            return blocked
        serializer.save()
        if self.chronicle_event_kind and before is not None and self.chronicle_snapshot is not None:
            record_event(
                entity_type=type(instance).__name__, entity_id=instance.pk,
                event_kind=self.chronicle_event_kind,
                effective_date=timezone.localdate(), user=request.user,
                before=before, after=self.chronicle_snapshot(instance),
            )
        return Response(serializer.data)

    def delete_guard(self, instance):
        """Business-rule guard evaluated before a hard delete.

        Subclasses return an ``AppFeedback`` to block the delete, else ``None``.
        """
        return None

    def delete(self, request, pk):
        instance = get_object_or_404(self._get_queryset(request.user), pk=pk)
        guard = self.delete_guard(instance)
        if guard is not None:
            raise guard
        emit_governance_event(
            entity_type=type(instance).__name__,
            entity_id=instance.pk,
            action='delete',
            before={'pk': instance.pk},
            after=None,
            user=request.user,
        )
        if self.chronicle_event_kind:
            record_event(
                entity_type=type(instance).__name__, entity_id=instance.pk,
                event_kind='position_closed',
                effective_date=timezone.localdate(), user=request.user,
                before=self.chronicle_snapshot(instance) if self.chronicle_snapshot else None,
                after=None,
            )
        try:
            instance.delete()
        except ProtectedError as exc:
            raise AppFeedback(
                code='protected_relation',
                title='Cannot delete: referenced records exist',
                detail=str(exc),
                context={'pk': instance.pk},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


# Position (org-scoped via its own org_unit FK)
class PositionListCreateView(_GatedListCreateView):
    model = Position
    serializer_class = PositionSerializer
    org_lookup = 'org_unit_id__in'
    chronicle_event_kind = 'position_opened'


class PositionDetailView(_GatedDetailView):
    model = Position
    serializer_class = PositionSerializer
    org_lookup = 'org_unit_id__in'
    chronicle_event_kind = 'profile_updated'
    # staticmethod so ``self.chronicle_snapshot(instance)`` passes only ``instance``
    # (a plain function assigned to a class becomes a bound method otherwise).
    chronicle_snapshot = staticmethod(snapshot_position)

    def patch(self, request, pk):
        instance = get_object_or_404(self._get_queryset(request.user), pk=pk)
        before = snapshot_position(instance)
        old_status = instance.status
        serializer = self.serializer_class(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(instance, field, value)
        blocked = _blocked_write_response(instance)
        if blocked is not None:
            return blocked
        serializer.save()
        if old_status != instance.status:
            status_kind = {
                'filled': 'position_filled',
                'frozen': 'position_frozen',
                'open': 'position_opened',
                'closed': 'position_closed',
            }.get(instance.status, 'profile_updated')
            event_kind = status_kind
        else:
            event_kind = 'profile_updated'
        record_event(
            entity_type='Position', entity_id=instance.pk, event_kind=event_kind,
            effective_date=timezone.localdate(), user=request.user,
            before=before, after=snapshot_position(instance),
        )
        return Response(serializer.data)

    def delete_guard(self, instance):
        if instance.direct_reports.exists():
            return AppFeedback(
                code='position_has_subordinates',
                title='Cannot delete: position has subordinate positions',
                detail=(
                    f"Position '{instance.code}' has "
                    f"{instance.direct_reports.count()} subordinate position(s)."
                ),
                context={
                    'position_id': instance.pk,
                    'subordinate_count': instance.direct_reports.count(),
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return None


# LeaveEntitlement (employee-linked)
class LeaveEntitlementListCreateView(_GatedListCreateView):
    model = LeaveEntitlement
    serializer_class = LeaveEntitlementSerializer
    org_lookup = 'employee__org_unit_id__in'


class LeaveEntitlementDetailView(_GatedDetailView):
    model = LeaveEntitlement
    serializer_class = LeaveEntitlementSerializer
    org_lookup = 'employee__org_unit_id__in'


# LeaveRecord (employee-linked)
class LeaveRecordListCreateView(_GatedListCreateView):
    model = LeaveRecord
    serializer_class = LeaveRecordSerializer
    org_lookup = 'employee__org_unit_id__in'


class LeaveRecordDetailView(_GatedDetailView):
    model = LeaveRecord
    serializer_class = LeaveRecordSerializer
    org_lookup = 'employee__org_unit_id__in'


# BenefitType (global reference data — no org scope)
class BenefitTypeListCreateView(_GatedListCreateView):
    model = BenefitType
    serializer_class = BenefitTypeSerializer
    org_lookup = None

    def get(self, request):
        qs = self.model.objects.all()
        if 'active' in request.query_params:
            qs = qs.filter(is_active=request.query_params['active'].lower() in ('1', 'true', 'yes'))
        return Response({
            'count': qs.count(),
            'results': self.serializer_class(qs, many=True).data,
        })


class BenefitTypeDetailView(_GatedDetailView):
    model = BenefitType
    serializer_class = BenefitTypeSerializer
    org_lookup = None

    def delete_guard(self, instance):
        if instance.employee_benefits.exists():
            return AppFeedback(
                code='benefit_type_in_use',
                title='Cannot delete: benefit type is in use',
                detail=(
                    f"Benefit type '{instance.code}' is referenced by "
                    f"{instance.employee_benefits.count()} employee benefit(s)."
                ),
                context={
                    'benefit_type_id': instance.pk,
                    'employee_benefit_count': instance.employee_benefits.count(),
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return None


# EmployeeBenefit (employee-linked)
class EmployeeBenefitListCreateView(_GatedListCreateView):
    model = EmployeeBenefit
    serializer_class = EmployeeBenefitSerializer
    org_lookup = 'employee__org_unit_id__in'


class EmployeeBenefitDetailView(_GatedDetailView):
    model = EmployeeBenefit
    serializer_class = EmployeeBenefitSerializer
    org_lookup = 'employee__org_unit_id__in'


# Loan (employee-linked)
class LoanListCreateView(_GatedListCreateView):
    model = Loan
    serializer_class = LoanSerializer
    org_lookup = 'employee__org_unit_id__in'


class LoanDetailView(_GatedDetailView):
    model = Loan
    serializer_class = LoanSerializer
    org_lookup = 'employee__org_unit_id__in'

    def delete_guard(self, instance):
        if instance.installments.exists():
            return AppFeedback(
                code='loan_has_installments',
                title='Cannot delete: loan has installments',
                detail=(
                    f"Loan #{instance.pk} has {instance.installments.count()} installment(s)."
                ),
                context={
                    'loan_id': instance.pk,
                    'installment_count': instance.installments.count(),
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return None


# LoanInstallment (loan-linked → employee)
class LoanInstallmentListCreateView(_GatedListCreateView):
    model = LoanInstallment
    serializer_class = LoanInstallmentSerializer
    org_lookup = 'loan__employee__org_unit_id__in'


class LoanInstallmentDetailView(_GatedDetailView):
    model = LoanInstallment
    serializer_class = LoanInstallmentSerializer
    org_lookup = 'loan__employee__org_unit_id__in'


# AttendanceRecord (employee-linked)
class AttendanceRecordListCreateView(_GatedListCreateView):
    model = AttendanceRecord
    serializer_class = AttendanceRecordSerializer
    org_lookup = 'employee__org_unit_id__in'


class AttendanceRecordDetailView(_GatedDetailView):
    model = AttendanceRecord
    serializer_class = AttendanceRecordSerializer
    org_lookup = 'employee__org_unit_id__in'


# AttendancePermission (employee-linked)
class AttendancePermissionListCreateView(_GatedListCreateView):
    model = AttendancePermission
    serializer_class = AttendancePermissionSerializer
    org_lookup = 'employee__org_unit_id__in'


class AttendancePermissionDetailView(_GatedDetailView):
    model = AttendancePermission
    serializer_class = AttendancePermissionSerializer
    org_lookup = 'employee__org_unit_id__in'


# Certification (employee-linked)
class CertificationListCreateView(_GatedListCreateView):
    model = Certification
    serializer_class = CertificationSerializer
    org_lookup = 'employee__org_unit_id__in'


class CertificationDetailView(_GatedDetailView):
    model = Certification
    serializer_class = CertificationSerializer
    org_lookup = 'employee__org_unit_id__in'


# RotationSchedule (employee-linked)
class RotationScheduleListCreateView(_GatedListCreateView):
    model = RotationSchedule
    serializer_class = RotationScheduleSerializer
    org_lookup = 'employee__org_unit_id__in'


class RotationScheduleDetailView(_GatedDetailView):
    model = RotationSchedule
    serializer_class = RotationScheduleSerializer
    org_lookup = 'employee__org_unit_id__in'


# PayrollRunValidation (run-scoped, READ-ONLY — list only)
class PayrollRunValidationsListView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request, pk):
        qs = PayrollRunValidation.objects.filter(payroll_run_id=pk)
        if not is_global_admin(request.user):
            qs = qs.filter(
                payroll_run__org_unit_id__in=_visible_org_unit_ids(request.user),
            )
        return Response({
            'count': qs.count(),
            'results': PayrollRunValidationSerializer(qs, many=True).data,
        })


# ── Run lifecycle endpoints (thin delegation to PayrollRunService) ───────────

class PayrollRunComputeView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def post(self, request, pk):
        run = get_object_or_404(
            _scoped(request.user, PayrollRun.objects.all(), 'org_unit_id__in'), pk=pk,
        )
        service = PayrollRunService()
        try:
            result = service.compute(run)
        except PayrollServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(result)


class PayrollRunValidateView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def post(self, request, pk):
        run = get_object_or_404(
            _scoped(request.user, PayrollRun.objects.all(), 'org_unit_id__in'), pk=pk,
        )
        service = PayrollRunService()
        try:
            result = service.validate(run)
        except PayrollServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        persist_findings(run, result.get("findings", []))
        return Response(result)


class PayrollRunCommitView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def post(self, request, pk):
        run = get_object_or_404(
            _scoped(request.user, PayrollRun.objects.all(), 'org_unit_id__in'), pk=pk,
        )
        service = PayrollRunService()
        try:
            result = service.commit(run)
        except PayrollServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        persist_findings(run, result.get("findings", []))
        return Response(result)


def _render_wps_csv(records):
    """Render WPS records (engine ``format_wps_record`` payloads) as CSV text.

    Column order follows the first record's ``record`` key order; subsequent
    records fill missing keys with empty strings so the file stays rectangular.
    """
    if not records:
        return ""
    columns = list(records[0]["record"].keys())
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for item in records:
        record = item["record"]
        writer.writerow([record.get(col, "") for col in columns])
    return buf.getvalue()


class PayrollRunWPSExportView(APIView):
    """Download a committed run's WPS file (CSV) built from the WPS rule.

    Only a *committed* run may be exported, and only when an authoritative
    ``category='wps'`` compliance rule exists — otherwise 409 (no fabrication).
    """

    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request, pk):
        run = get_object_or_404(
            _scoped(request.user, PayrollRun.objects.all(), 'org_unit_id__in'), pk=pk,
        )
        service = PayrollRunService()
        try:
            result = service.wps_export(run)
        except PayrollServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        response = HttpResponse(
            _render_wps_csv(result["records"]), content_type="text/csv",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="wps_run_{run.pk}.csv"'
        )
        return response


# ── P1: PersonnelEvent chronicle (append-only read endpoints) ──────────────

class EmployeeTimelineView(APIView):
    """GET people/employees/<pk>/timeline/ — chronicle for one employee (RULE_12 scoped)."""
    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request, pk):
        qs = Employee.objects.all() if is_global_admin(request.user) else Employee.objects.filter(
            org_unit_id__in=_visible_org_unit_ids(request.user),
        )
        employee = get_object_or_404(qs, pk=pk)
        events = PersonnelEvent.objects.filter(
            entity_type='Employee', entity_id=employee.pk,
        )
        return Response(PersonnelEventSerializer(events, many=True).data)


class EmployeeEOSIView(APIView):
    """GET people/employees/<pk>/eosi/?as_of=YYYY-MM-DD — EOSI provision with lineage.

    Wraps the existing CalculationService.calculate_eosi engine. Computes ONLY
    from an authoritative category='eosi' ComplianceRule (no fabrication): 409
    when no authoritative rule exists. CBAC (people:view) + RULE_12 org scoping.
    """

    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request, pk):
        qs = Employee.objects.all() if is_global_admin(request.user) else Employee.objects.filter(
            org_unit_id__in=_visible_org_unit_ids(request.user),
        )
        employee = get_object_or_404(qs, pk=pk)

        as_of = None
        as_of_raw = request.query_params.get('as_of')
        if as_of_raw:
            try:
                as_of = date.fromisoformat(as_of_raw)
            except ValueError:
                return Response(
                    {'detail': "Invalid 'as_of' date; use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            result = CalculationService.calculate_eosi(employee, as_of=as_of)
        except NonAuthoritativeRuleError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)

        payload = _json_safe({
            'value': result['value'],
            'lineage': result['lineage'],
            'as_of': as_of or timezone.localdate(),
        })
        return Response(payload)


class PositionTimelineView(APIView):
    """GET people/positions/<pk>/timeline/ — chronicle for one position (RULE_12 scoped)."""
    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request, pk):
        qs = Position.objects.all() if is_global_admin(request.user) else Position.objects.filter(
            org_unit_id__in=_visible_org_unit_ids(request.user),
        )
        position = get_object_or_404(qs, pk=pk)
        events = PersonnelEvent.objects.filter(
            entity_type='Position', entity_id=position.pk,
        )
        return Response(PersonnelEventSerializer(events, many=True).data)


class OrgUnitTimelineView(APIView):
    """GET people/org-units/<pk>/timeline/ — org chronicle from catalog.GovernanceEvent
    (mdm/views.py already emits create/update/delete governance events)."""
    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request, pk):
        from catalog.models import GovernanceEvent
        events = GovernanceEvent.objects.filter(
            entity_type='OrgUnit', entity_id=pk,
        ).order_by('-timestamp')
        return Response(events.values(
            'id', 'action', 'entity_type', 'entity_id',
            'before', 'after', 'timestamp', 'user_id',
        ))


class PersonnelEventListView(APIView):
    """GET people/events/?entity_type=&kind=&from=&to= — cross-entity chronicle feed.
    RULE_12: non-admins see only events for entities inside their visible org units."""

    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request):
        qs = PersonnelEvent.objects.all()
        entity_type = request.query_params.get('entity_type')
        kind = request.query_params.get('kind')
        from_date = request.query_params.get('from')
        to_date = request.query_params.get('to')
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        if kind:
            qs = qs.filter(event_kind=kind)
        if from_date:
            qs = qs.filter(effective_date__gte=from_date)
        if to_date:
            qs = qs.filter(effective_date__lte=to_date)
        if not is_global_admin(request.user):
            from django.db.models import Q
            visible = _visible_org_unit_ids(request.user)
            qs = qs.filter(
                Q(entity_type='Employee', entity_id__in=Employee.objects.filter(org_unit_id__in=visible).values('pk'))
                | Q(entity_type='Position', entity_id__in=Position.objects.filter(org_unit_id__in=visible).values('pk'))
            )
        return Response({
            'count': qs.count(),
            'results': PersonnelEventSerializer(qs, many=True).data,
        })
