"""Employee self-service surface (Phase OF-8).

The ``/people/me/`` endpoints that let an active employee read their own
profile and leave balance, list/detail their leave records, and submit a new
leave request. Submission is where subject creation lives: it creates a
``people.LeaveRecord`` AND a governed ``correspondence.Correspondence``, then
drives it through ``correspondence.fsm.submit_correspondence``.

Layering: ``people`` imports ``correspondence`` (one-way). The engine is never
touched — only ``fsm``, ``serializers``, ``models`` and the exception types.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from correspondence import fsm
from correspondence.exceptions import InvalidTransition, SubmissionBlocked
from correspondence.models import ACTIONABLE, Correspondence
from correspondence.policies import PolicyNotFound
from correspondence.serializers import CorrespondenceDetailSerializer
from mdm.models import ReferenceValue

from .models import AttendancePermission, Employee, LeaveRecord, Loan, PayslipLine
from .permissions import IsActiveEmployee, HasTeamAccess
from .leave_days import leave_days_json
from .leave_guards import (
    MAX_BACKDATED_LEAVE_DAYS,
    SUBJECT_TYPE,
    compute_balance as _compute_balance,
    linked_actionable_corr as _linked_actionable_corr,
    linked_approved_corr as _linked_approved_corr,
    record_blocks_overlap as _record_blocks_overlap,
)
from .leave_type_resolve import allowed_leave_type_payload, resolve_leave_type
from .manager_routing import manager_routing_block_response
from .self_serializers import (
    EmployeeSummarySerializer,
    LeaveBalanceSerializer,
    LeaveRecordDetailSerializer,
    LeaveRecordSerializer,
    TeamLeaveRecordSerializer,
)
from .serializers import AttendancePermissionSerializer, LoanSerializer, PayslipLineSerializer

# Payroll run statuses whose payslip lines are final and safe to expose to the
# employee (F10). Draft/computed runs are internal and stay hidden.
COMMITTED_RUN_STATUSES = ('validated', 'committed')


# ── helpers ────────────────────────────────────────────────────────────────

def _corr_type_value(code='leave_request'):
    """The governed ``<code>`` corr_type ReferenceValue."""
    return ReferenceValue.objects.get(
        reference_set__name='correspondence_type', code=code,
    )


# ── views ──────────────────────────────────────────────────────────────────

class EmployeeMeView(APIView):
    permission_classes = [IsAuthenticated, IsActiveEmployee]

    def get(self, request):
        profile = request.user.employee_profile
        return Response(EmployeeSummarySerializer(profile).data)


class LeaveBalanceView(APIView):
    permission_classes = [IsAuthenticated, IsActiveEmployee]

    def get(self, request):
        profile = request.user.employee_profile
        year = timezone.now().year
        codes = list(
            ReferenceValue.objects
            .filter(reference_set__name='leave_type')
            .order_by('sort_order', 'code')
            .values_list('code', flat=True)
        )
        balances = []
        for code in codes:
            entitled, carried_forward, used, pending, remaining = _compute_balance(
                profile, code, year,
            )
            balances.append({
                'leave_type': code,
                'entitled': entitled,
                'carried_forward': carried_forward,
                'opening_balance': entitled + carried_forward,
                'used': used,
                'pending': pending,
                'remaining': remaining,
            })
        return Response(LeaveBalanceSerializer(balances, many=True).data)


class LeaveSelfCollectionView(APIView):
    """GET lists my leave records; POST submits a new leave request."""

    permission_classes = [IsAuthenticated, IsActiveEmployee]

    def get(self, request):
        profile = request.user.employee_profile
        qs = LeaveRecord.objects.filter(employee=profile)
        return Response(LeaveRecordSerializer(qs, many=True).data)

    def post(self, request):
        profile = request.user.employee_profile
        blocked = manager_routing_block_response(profile)
        if blocked is not None:
            return blocked
        data = request.data or {}

        leave_type_raw = data.get('leave_type')
        if not isinstance(leave_type_raw, str) or not leave_type_raw.strip():
            return Response(
                {
                    'detail': 'leave_type is required',
                    'error_kind': 'leave_type_required',
                    'hints': {'allowed_types': allowed_leave_type_payload()},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        leave_type_value = resolve_leave_type(leave_type_raw)
        if leave_type_value is None:
            return Response(
                {
                    'detail': (
                        f'"{leave_type_raw.strip()}" is not a recognised leave type. '
                        'Pick one of the allowed types.'
                    ),
                    'error_kind': 'invalid_leave_type',
                    'hints': {
                        'requested': leave_type_raw.strip(),
                        'allowed_types': allowed_leave_type_payload(),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        leave_type = leave_type_value.code

        try:
            start_date = date.fromisoformat(str(data.get('start_date', '')))
            end_date = date.fromisoformat(str(data.get('end_date', '')))
        except (ValueError, TypeError):
            return Response(
                {
                    'detail': 'Invalid start_date/end_date (expected ISO date)',
                    'error_kind': 'invalid_dates',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if end_date < start_date:
            return Response(
                {
                    'detail': 'end_date must be on or after start_date',
                    'error_kind': 'invalid_dates',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.localdate()
        if start_date < today - timedelta(days=MAX_BACKDATED_LEAVE_DAYS):
            return Response(
                {
                    'detail': (
                        f'Leave cannot start on {start_date} — that is more '
                        f'than {MAX_BACKDATED_LEAVE_DAYS} days before today '
                        f'({today}).'
                    ),
                    'error_kind': 'invalid_dates',
                    'hints': {
                        'requested_start': str(start_date),
                        'today': str(today),
                        'earliest_allowed': str(
                            today - timedelta(days=MAX_BACKDATED_LEAVE_DAYS)
                        ),
                        'suggestion': 'Use the intended date this year.',
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            days = Decimal(str(data.get('days')))
        except (InvalidOperation, ValueError, TypeError):
            return Response(
                {
                    'detail': 'days must be a positive number',
                    'error_kind': 'invalid_days',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if days <= 0:
            return Response(
                {
                    'detail': 'days must be a positive number',
                    'error_kind': 'invalid_days',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        year = timezone.now().year
        _, _, _, _, remaining = _compute_balance(profile, leave_type, year)
        if days > remaining:
            return Response(
                {
                    'detail': (
                        f'Insufficient {leave_type} leave balance '
                        f'(requested {leave_days_json(days)}, '
                        f'remaining {leave_days_json(remaining)}).'
                    ),
                    'error_kind': 'insufficient_balance',
                    'remaining': leave_days_json(remaining),
                    'hints': {
                        'leave_type': leave_type,
                        'requested_days': leave_days_json(days),
                        'remaining': leave_days_json(remaining),
                        'suggestion': 'Pick another leave type or a shorter period.',
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        for record in LeaveRecord.objects.filter(employee=profile):
            if not _record_blocks_overlap(record):
                continue
            if record.start_date <= end_date and record.end_date >= start_date:
                return Response(
                    {
                        'detail': (
                            f'Those dates overlap an existing {record.leave_type.code} '
                            f'leave ({record.start_date}→{record.end_date}, '
                            f'status={record.status}).'
                        ),
                        'error_kind': 'overlap',
                        'hints': {
                            'overlapping_start': str(record.start_date),
                            'overlapping_end': str(record.end_date),
                            'overlapping_type': record.leave_type.code,
                            'overlapping_status': record.status,
                            'suggestion': 'Pick another day that is free.',
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        note = data.get('note', '') or ''

        try:
            with transaction.atomic():
                record = LeaveRecord.objects.create(
                    employee=profile,
                    leave_type=leave_type_value,
                    start_date=start_date,
                    end_date=end_date,
                    days=days,
                    status='draft',
                )
                corr = Correspondence.objects.create(
                    corr_type=_corr_type_value(),
                    subject_type=SUBJECT_TYPE,
                    subject_id=record.pk,
                    org_unit=profile.org_unit,
                    requester=request.user,
                    title=f'Leave request {leave_type} {start_date}→{end_date}',
                    payload={
                        'leave_type': leave_type,
                        'start_date': str(start_date),
                        'end_date': str(end_date),
                        'days': leave_days_json(days),
                        'note': note,
                    },
                    status='draft',
                    reference_no=f'DRAFT-{uuid.uuid4().hex[:12]}',
                )
                corr = fsm.submit_correspondence(
                    corr=corr, by=request.user, subject=record,
                    subject_label=SUBJECT_TYPE,
                )
        except SubmissionBlocked as exc:
            return Response(
                {'detail': 'Submission blocked by DQ gate', 'failures': exc.failures},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PolicyNotFound:
            return Response(
                {'detail': 'No workflow policy configured'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except InvalidTransition as exc:
            return Response(
                {'detail': f'Invalid transition: {exc}'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            CorrespondenceDetailSerializer(corr).data,
            status=status.HTTP_201_CREATED,
        )


class LeaveSelfDetailView(APIView):
    permission_classes = [IsAuthenticated, IsActiveEmployee]

    def get(self, request, pk):
        profile = request.user.employee_profile
        record = get_object_or_404(LeaveRecord, pk=pk, employee=profile)
        return Response(LeaveRecordDetailSerializer(record).data)


class LoanSelfCollectionView(APIView):
    """GET lists my loans; POST submits a new loan request (governed)."""

    permission_classes = [IsAuthenticated, IsActiveEmployee]

    def get(self, request):
        profile = request.user.employee_profile
        qs = Loan.objects.filter(employee=profile)
        return Response(LoanSerializer(qs, many=True).data)

    def post(self, request):
        profile = request.user.employee_profile
        blocked = manager_routing_block_response(profile)
        if blocked is not None:
            return blocked
        data = request.data or {}

        loan_type = data.get('loan_type')
        if loan_type is None or (isinstance(loan_type, str) and not loan_type.strip()):
            return Response(
                {'detail': 'loan_type is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from mdm.governed import resolve_reference_value
            loan_type_rv = resolve_reference_value(
                'loan_type',
                loan_type.strip() if isinstance(loan_type, str) else loan_type,
                require_current=False,
            )
        except Exception:
            loan_type_rv = None
        if loan_type_rv is None:
            return Response(
                {'detail': f'Unknown loan_type {loan_type!r}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            principal = Decimal(str(data.get('principal')))
        except (InvalidOperation, ValueError, TypeError):
            return Response(
                {'detail': 'principal must be a positive number'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if principal <= 0:
            return Response(
                {'detail': 'principal must be a positive number'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            interest_rate = Decimal(str(data.get('interest_rate', '0')))
        except (InvalidOperation, ValueError, TypeError):
            return Response(
                {'detail': 'interest_rate must be a non-negative number'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if interest_rate < 0:
            return Response(
                {'detail': 'interest_rate must be a non-negative number'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            term_months = int(data.get('term_months'))
        except (ValueError, TypeError):
            return Response(
                {'detail': 'term_months must be a positive integer'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if term_months <= 0:
            return Response(
                {'detail': 'term_months must be a positive integer'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            start_date = date.fromisoformat(str(data.get('start_date', '')))
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Invalid start_date (expected ISO date)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        notes = data.get('notes', '') or ''

        try:
            with transaction.atomic():
                loan = Loan.objects.create(
                    employee=profile,
                    loan_type=loan_type_rv,
                    principal=principal,
                    interest_rate=interest_rate,
                    term_months=term_months,
                    start_date=start_date,
                    notes=notes,
                    status='draft',
                )
                corr = Correspondence.objects.create(
                    corr_type=_corr_type_value('loan_request'),
                    subject_type='people.Loan',
                    subject_id=loan.pk,
                    org_unit=profile.org_unit,
                    requester=request.user,
                    title=f'Loan request {loan_type_rv.code} {principal}',
                    payload={
                        'loan_type': loan_type_rv.code,
                        'principal': str(principal),
                        'interest_rate': str(interest_rate),
                        'term_months': term_months,
                        'start_date': str(start_date),
                        'notes': notes,
                    },
                    status='draft',
                    reference_no=f'DRAFT-{uuid.uuid4().hex[:12]}',
                )
                corr = fsm.submit_correspondence(
                    corr=corr, by=request.user, subject=loan,
                    subject_label='people.Loan',
                )
        except SubmissionBlocked as exc:
            return Response(
                {'detail': 'Submission blocked by DQ gate', 'failures': exc.failures},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PolicyNotFound:
            return Response(
                {'detail': 'No workflow policy configured'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except InvalidTransition as exc:
            return Response(
                {'detail': f'Invalid transition: {exc}'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            CorrespondenceDetailSerializer(corr).data,
            status=status.HTTP_201_CREATED,
        )


class PayslipSelfCollectionView(APIView):
    """GET lists my committed/validated payslip lines (self-service F10)."""

    permission_classes = [IsAuthenticated, IsActiveEmployee]

    def get(self, request):
        profile = request.user.employee_profile
        qs = PayslipLine.objects.filter(
            employee=profile,
            payroll_run__status__in=COMMITTED_RUN_STATUSES,
        )
        return Response(PayslipLineSerializer(qs, many=True).data)


class PayslipSelfDetailView(APIView):
    """GET a single committed/validated payslip line of mine (self-service F10)."""

    permission_classes = [IsAuthenticated, IsActiveEmployee]

    def get(self, request, pk):
        profile = request.user.employee_profile
        line = get_object_or_404(
            PayslipLine,
            pk=pk,
            employee=profile,
            payroll_run__status__in=COMMITTED_RUN_STATUSES,
        )
        return Response(PayslipLineSerializer(line).data)


class ProfileChangeSelfView(APIView):
    """POST submits a profile-change request for the current employee.

    No new model is created — the Correspondence is typed against the existing
    ``people.Employee`` profile and carries a per-field ``{from, to}`` payload.
    """

    permission_classes = [IsAuthenticated, IsActiveEmployee]

    def post(self, request):
        profile = request.user.employee_profile
        data = request.data or {}

        changes = data.get('changes')
        if not isinstance(changes, dict) or not changes:
            return Response(
                {'detail': 'changes must be a non-empty object of {field: {from, to}}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for field, change in changes.items():
            if not isinstance(change, dict) or 'to' not in change:
                return Response(
                    {'detail': f'change for {field!r} must be an object with a "to" value'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            with transaction.atomic():
                corr = Correspondence.objects.create(
                    corr_type=_corr_type_value('profile_change'),
                    subject_type='people.Employee',
                    subject_id=profile.pk,
                    org_unit=profile.org_unit,
                    requester=request.user,
                    title='Profile change request',
                    payload={'changes': changes},
                    status='draft',
                    reference_no=f'DRAFT-{uuid.uuid4().hex[:12]}',
                )
                corr = fsm.submit_correspondence(
                    corr=corr, by=request.user, subject=profile,
                    subject_label='people.Employee',
                )
        except SubmissionBlocked as exc:
            return Response(
                {'detail': 'Submission blocked by DQ gate', 'failures': exc.failures},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PolicyNotFound:
            return Response(
                {'detail': 'No workflow policy configured'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except InvalidTransition as exc:
            return Response(
                {'detail': f'Invalid transition: {exc}'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            CorrespondenceDetailSerializer(corr).data,
            status=status.HTTP_201_CREATED,
        )


class AttendancePermissionSelfCollectionView(APIView):
    """GET lists my attendance permissions; POST submits via Correspondence."""

    permission_classes = [IsAuthenticated, IsActiveEmployee]

    def get(self, request):
        profile = request.user.employee_profile
        qs = AttendancePermission.objects.filter(employee=profile)
        return Response(AttendancePermissionSerializer(qs, many=True).data)

    def post(self, request):
        from people.attendance_ess import (
            AttendanceESSError,
            submit_my_attendance_permission,
        )

        try:
            corr = submit_my_attendance_permission(request.user, request.data or {})
        except AttendanceESSError as exc:
            body = {"detail": exc.detail, **exc.extra}
            return Response(body, status=exc.status)

        return Response(
            CorrespondenceDetailSerializer(corr).data,
            status=status.HTTP_201_CREATED,
        )


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


class DirectReportsView(APIView):
    """GET — employees who report to the current manager (Team Directory)."""

    permission_classes = [IsAuthenticated, IsActiveEmployee, HasTeamAccess]

    def get(self, request):
        profile = request.user.employee_profile
        qs = (
            Employee.objects.filter(manager=profile)
            .select_related('position', 'org_unit', 'manager')
            .order_by('employee_no')
        )
        return Response(EmployeeSummarySerializer(qs, many=True).data)


class TeamLeaveView(APIView):
    """GET — leave overlapping a calendar month for direct reports (Who's Out).

    Includes approved leave and in-flight ESS requests (LeaveRecord stays
    ``draft`` until Correspondence resolves — filter those by actionable corr).
    """

    permission_classes = [IsAuthenticated, IsActiveEmployee, HasTeamAccess]

    def get(self, request):
        from django.db.models import Exists, OuterRef, Q

        profile = request.user.employee_profile
        today = timezone.localdate()
        try:
            year = int(request.query_params.get('year', today.year))
            month = int(request.query_params.get('month', today.month))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'year and month must be integers', 'error_kind': 'invalid_month'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if month < 1 or month > 12 or year < 2000 or year > 2100:
            return Response(
                {'detail': 'year/month out of range', 'error_kind': 'invalid_month'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        start, end = _month_bounds(year, month)
        pending_corr = Correspondence.objects.filter(
            subject_type=SUBJECT_TYPE,
            subject_id=OuterRef('pk'),
            status__in=ACTIONABLE,
        )
        qs = (
            LeaveRecord.objects.filter(
                employee__manager=profile,
                start_date__lte=end,
                end_date__gte=start,
            )
            .annotate(_pending=Exists(pending_corr))
            .filter(
                Q(status__in=('submitted', 'approved'))
                | Q(status='draft', _pending=True)
            )
            .select_related('employee', 'leave_type')
            .order_by('start_date', 'employee__employee_no')
        )
        return Response({
            'year': year,
            'month': month,
            'items': TeamLeaveRecordSerializer(qs, many=True).data,
        })
