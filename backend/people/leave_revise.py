"""Revise a leave subject when its correspondence is edited (sent_back).

Layering: domain owns LeaveRecord field rules (balance, overlap, dates). The
correspondence edit view calls ``apply_leave_payload_edit`` — fsm never imports
people.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .leave_days import leave_days_json
from .leave_guards import (
    MAX_BACKDATED_LEAVE_DAYS,
    SUBJECT_TYPE,
    compute_balance,
    record_blocks_overlap,
)
from .leave_type_resolve import resolve_leave_type
from .models import LeaveRecord


class LeaveReviseError(Exception):
    """Domain validation failure for a leave payload edit."""

    def __init__(self, detail, *, error_kind=None, status_code=400, **extra):
        super().__init__(detail)
        self.detail = detail
        self.error_kind = error_kind
        self.status_code = status_code
        self.extra = extra


def _parse_leave_fields(payload: dict):
    if not isinstance(payload, dict):
        raise LeaveReviseError('payload must be an object', error_kind='invalid_payload')

    leave_type_raw = payload.get('leave_type')
    if not isinstance(leave_type_raw, str) or not leave_type_raw.strip():
        raise LeaveReviseError('leave_type is required', error_kind='leave_type_required')

    leave_type_value = resolve_leave_type(leave_type_raw)
    if leave_type_value is None:
        raise LeaveReviseError(
            f'"{leave_type_raw.strip()}" is not a recognised leave type.',
            error_kind='invalid_leave_type',
        )

    try:
        start_date = date.fromisoformat(str(payload.get('start_date', '')))
        end_date = date.fromisoformat(str(payload.get('end_date', '')))
    except (ValueError, TypeError) as exc:
        raise LeaveReviseError(
            'Invalid start_date/end_date (expected ISO date)',
            error_kind='invalid_dates',
        ) from exc

    if end_date < start_date:
        raise LeaveReviseError(
            'end_date must be on or after start_date',
            error_kind='invalid_dates',
        )

    today = timezone.localdate()
    if start_date < today - timedelta(days=MAX_BACKDATED_LEAVE_DAYS):
        raise LeaveReviseError(
            (
                f'Leave cannot start on {start_date} — that is more '
                f'than {MAX_BACKDATED_LEAVE_DAYS} days before today '
                f'({today}).'
            ),
            error_kind='invalid_dates',
        )

    try:
        days = Decimal(str(payload.get('days')))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise LeaveReviseError(
            'days must be a positive number',
            error_kind='invalid_days',
        ) from exc
    if days <= 0:
        raise LeaveReviseError(
            'days must be a positive number',
            error_kind='invalid_days',
        )

    note = payload.get('note', '') or ''
    if not isinstance(note, str):
        note = str(note)

    return leave_type_value, start_date, end_date, days, note


def apply_leave_payload_edit(corr, payload: dict) -> tuple[dict, str]:
    """Validate payload, update linked LeaveRecord, return (normalized_payload, title).

    Raises ``LeaveReviseError`` on domain failure.
    """
    if corr.subject_type != SUBJECT_TYPE or not corr.subject_id:
        raise LeaveReviseError(
            'Correspondence has no leave subject to revise',
            error_kind='no_subject',
            status_code=409,
        )

    record = LeaveRecord.objects.select_related('employee', 'leave_type').filter(
        pk=corr.subject_id,
    ).first()
    if record is None:
        raise LeaveReviseError(
            'Linked leave record not found',
            error_kind='no_subject',
            status_code=409,
        )
    if record.status != 'draft':
        raise LeaveReviseError(
            f'Cannot revise leave in status {record.status!r}',
            error_kind='invalid_status',
            status_code=409,
        )

    leave_type_value, start_date, end_date, days, note = _parse_leave_fields(payload)
    leave_type = leave_type_value.code
    profile = record.employee

    year = timezone.now().year
    _, _, _, _, remaining = compute_balance(profile, leave_type, year)
    if days > remaining:
        raise LeaveReviseError(
            (
                f'Insufficient {leave_type} leave balance '
                f'(requested {leave_days_json(days)}, '
                f'remaining {leave_days_json(remaining)}).'
            ),
            error_kind='insufficient_balance',
            remaining=leave_days_json(remaining),
        )

    for other in LeaveRecord.objects.filter(employee=profile).exclude(pk=record.pk):
        if not record_blocks_overlap(other):
            continue
        if other.start_date <= end_date and other.end_date >= start_date:
            raise LeaveReviseError(
                (
                    f'Those dates overlap an existing {other.leave_type.code} '
                    f'leave ({other.start_date}→{other.end_date}, '
                    f'status={other.status}).'
                ),
                error_kind='overlap',
            )

    normalized = {
        'leave_type': leave_type,
        'start_date': str(start_date),
        'end_date': str(end_date),
        'days': leave_days_json(days),
        'note': note,
    }
    title = f'Leave request {leave_type} {start_date}→{end_date}'

    with transaction.atomic():
        record.leave_type = leave_type_value
        record.start_date = start_date
        record.end_date = end_date
        record.days = days
        record.save(update_fields=['leave_type', 'start_date', 'end_date', 'days'])

    return normalized, title
