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
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum
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

from .models import LeaveEntitlement, LeaveRecord, Loan, PayslipLine
from .permissions import IsActiveEmployee
from .self_serializers import (
    EmployeeSummarySerializer,
    LeaveBalanceSerializer,
    LeaveRecordDetailSerializer,
    LeaveRecordSerializer,
)
from .serializers import LoanSerializer, PayslipLineSerializer

SUBJECT_TYPE = 'people.LeaveRecord'

# Payroll run statuses whose payslip lines are final and safe to expose to the
# employee (F10). Draft/computed runs are internal and stay hidden.
COMMITTED_RUN_STATUSES = ('validated', 'committed')


# ── helpers ────────────────────────────────────────────────────────────────

def _corr_type_value(code='leave_request'):
    """The governed ``<code>`` corr_type ReferenceValue."""
    return ReferenceValue.objects.get(
        reference_set__name='correspondence_type', code=code,
    )


def _linked_actionable_corr(record) -> bool:
    """True if this leave record has a workflow correspondence awaiting action."""
    return Correspondence.objects.filter(
        subject_type=SUBJECT_TYPE,
        subject_id=record.pk,
        status__in=ACTIONABLE,
    ).exists()


def _linked_approved_corr(record) -> bool:
    """True if this leave record has a workflow correspondence that was approved.

    NSR-1B mirrors terminal correspondence onto ``LeaveRecord.status``; this
    Correspondence lookup remains as a fallback for any pre-sync rows that
    still show ``draft`` while their correspondence is already ``approved``.
    """
    return Correspondence.objects.filter(
        subject_type=SUBJECT_TYPE,
        subject_id=record.pk,
        status='approved',
    ).exists()


def _record_blocks_overlap(record) -> bool:
    """Whether an existing leave record should block a new request."""
    if record.status in ('approved', 'submitted'):
        return True
    # In-flight draft records whose correspondence is still actionable block
    # overlapping requests until the workflow resolves.
    return _linked_actionable_corr(record)


def _compute_balance(profile, code, year):
    """Return ``(entitled, carried_forward, used, pending, remaining)`` Decimals."""
    agg = LeaveEntitlement.objects.filter(
        employee=profile, year=year, leave_type__code=code,
    ).aggregate(
        total_entitled=Sum('entitled_days'),
        total_carried=Sum('carried_forward'),
    )
    entitled = agg['total_entitled'] or Decimal('0')
    carried_forward = agg['total_carried'] or Decimal('0')
    # Opening balance is the entitlement plus whatever carried forward from last year.
    opening_balance = entitled + carried_forward

    used = Decimal('0')
    for record in LeaveRecord.objects.filter(
        employee=profile, leave_type__code=code, start_date__year=year,
    ):
        if record.status == 'approved' or _linked_approved_corr(record):
            used += record.days

    pending = Decimal('0')
    for record in LeaveRecord.objects.filter(employee=profile, leave_type__code=code):
        if _linked_actionable_corr(record):
            pending += record.days

    remaining = max(Decimal('0'), opening_balance - used - pending)
    return entitled, carried_forward, used, pending, remaining


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
        data = request.data or {}

        leave_type = data.get('leave_type')
        if not isinstance(leave_type, str) or not leave_type.strip():
            return Response(
                {'detail': 'leave_type is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        leave_type_value = ReferenceValue.objects.filter(
            reference_set__name='leave_type', code=leave_type,
        ).first()
        if leave_type_value is None:
            return Response(
                {'detail': 'Invalid leave_type'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            start_date = date.fromisoformat(str(data.get('start_date', '')))
            end_date = date.fromisoformat(str(data.get('end_date', '')))
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Invalid start_date/end_date (expected ISO date)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if end_date < start_date:
            return Response(
                {'detail': 'end_date must be on or after start_date'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            days = Decimal(str(data.get('days')))
        except (InvalidOperation, ValueError, TypeError):
            return Response(
                {'detail': 'days must be a positive number'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if days <= 0:
            return Response(
                {'detail': 'days must be a positive number'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        year = timezone.now().year
        _, _, _, _, remaining = _compute_balance(profile, leave_type, year)
        if days > remaining:
            return Response(
                {'detail': 'Insufficient leave balance', 'remaining': remaining},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for record in LeaveRecord.objects.filter(employee=profile):
            if not _record_blocks_overlap(record):
                continue
            if record.start_date <= end_date and record.end_date >= start_date:
                return Response(
                    {'detail': 'Overlaps existing leave request'},
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
                        'days': str(days),
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
