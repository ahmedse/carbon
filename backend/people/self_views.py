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

from .models import LeaveEntitlement, LeaveRecord
from .permissions import IsActiveEmployee
from .self_serializers import (
    EmployeeSummarySerializer,
    LeaveBalanceSerializer,
    LeaveRecordDetailSerializer,
    LeaveRecordSerializer,
)

SUBJECT_TYPE = 'people.LeaveRecord'


# ── helpers ────────────────────────────────────────────────────────────────

def _corr_type_value():
    """The governed ``leave_request`` corr_type ReferenceValue."""
    return ReferenceValue.objects.get(
        reference_set__name='correspondence_type', code='leave_request',
    )


def _linked_actionable_corr(record) -> bool:
    """True if this leave record has a workflow correspondence awaiting action."""
    return Correspondence.objects.filter(
        subject_type=SUBJECT_TYPE,
        subject_id=record.pk,
        status__in=ACTIONABLE,
    ).exists()


def _record_blocks_overlap(record) -> bool:
    """Whether an existing leave record should block a new request."""
    if record.status in ('approved', 'submitted'):
        return True
    # Draft records submitted through the correspondence engine keep a 'draft'
    # LeaveRecord status but their correspondence is actionable.
    return _linked_actionable_corr(record)


def _compute_balance(profile, code, year):
    """Return ``(entitled, used, pending, remaining)`` Decimals for one code."""
    entitled = LeaveEntitlement.objects.filter(
        employee=profile, year=year, leave_type__code=code,
    ).aggregate(total=Sum('entitled_days'))['total'] or Decimal('0')

    used = LeaveRecord.objects.filter(
        employee=profile, leave_type__code=code, status='approved',
        start_date__year=year,
    ).aggregate(total=Sum('days'))['total'] or Decimal('0')

    pending = Decimal('0')
    for record in LeaveRecord.objects.filter(employee=profile, leave_type__code=code):
        if _linked_actionable_corr(record):
            pending += record.days

    remaining = max(Decimal('0'), entitled - used - pending)
    return entitled, used, pending, remaining


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
            entitled, used, pending, remaining = _compute_balance(
                profile, code, year,
            )
            balances.append({
                'leave_type': code,
                'entitled': entitled,
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
        _, _, _, remaining = _compute_balance(profile, leave_type, year)
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
