"""Revise an attendance permission when its correspondence is edited (sent_back)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from .models import AttendancePermission

SUBJECT_TYPE = 'people.AttendancePermission'


class AttendanceReviseError(Exception):
    def __init__(self, detail, *, error_kind=None, status_code=400, **extra):
        super().__init__(detail)
        self.detail = detail
        self.error_kind = error_kind
        self.status_code = status_code
        self.extra = extra


def _parse_attendance_fields(payload: dict):
    if not isinstance(payload, dict):
        raise AttendanceReviseError('payload must be an object', error_kind='invalid_payload')

    permission_type = payload.get('permission_type')
    if permission_type is None or (
        isinstance(permission_type, str) and not permission_type.strip()
    ):
        raise AttendanceReviseError(
            'permission_type is required',
            error_kind='permission_type_required',
        )

    try:
        from mdm.governed import resolve_reference_value
        perm_value = resolve_reference_value(
            'permission_type',
            permission_type.strip() if isinstance(permission_type, str) else permission_type,
            require_current=False,
        )
    except Exception:
        perm_value = None
    if perm_value is None:
        raise AttendanceReviseError(
            'Invalid permission_type',
            error_kind='invalid_permission_type',
        )

    try:
        day = date.fromisoformat(str(payload.get('date', '')))
    except (ValueError, TypeError) as exc:
        raise AttendanceReviseError(
            'Invalid date (expected ISO date)',
            error_kind='invalid_dates',
        ) from exc

    try:
        hours = Decimal(str(payload.get('hours')))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise AttendanceReviseError(
            'hours must be a positive number',
            error_kind='invalid_hours',
        ) from exc
    if hours <= 0:
        raise AttendanceReviseError(
            'hours must be a positive number',
            error_kind='invalid_hours',
        )

    notes = payload.get('notes', '') or ''
    if not isinstance(notes, str):
        notes = str(notes)

    return perm_value, day, hours, notes


def _requester_profile(corr):
    try:
        return corr.requester.employee_profile
    except ObjectDoesNotExist:
        return None
    except AttributeError:
        return None


def _ensure_pending_permission(corr, perm_value, day, hours, notes):
    record = None
    if corr.subject_id:
        record = AttendancePermission.objects.select_related(
            'employee', 'permission_type',
        ).filter(pk=corr.subject_id).first()

    if record is not None:
        if record.status != 'pending' and corr.status == 'sent_back':
            # In-flight send_back must stay pending until manager re-approves.
            record.status = 'pending'
            record.approved = False
            record.save(update_fields=['status', 'approved'])
        return record

    profile = _requester_profile(corr)
    if profile is None:
        raise AttendanceReviseError(
            'Requester has no employee profile to attach permission',
            error_kind='no_profile',
            status_code=409,
        )

    record = AttendancePermission.objects.create(
        employee=profile,
        date=day,
        permission_type=perm_value,
        hours=hours,
        status='pending',
        approved=False,
        notes=notes,
    )
    corr.subject_type = SUBJECT_TYPE
    corr.subject_id = record.pk
    corr.save(update_fields=['subject_type', 'subject_id', 'updated_at'])
    return record


def apply_attendance_payload_edit(corr, payload: dict) -> tuple[dict, str]:
    if corr.subject_type and corr.subject_type != SUBJECT_TYPE:
        raise AttendanceReviseError(
            'Correspondence subject is not an attendance permission',
            error_kind='wrong_subject',
            status_code=409,
        )

    perm_value, day, hours, notes = _parse_attendance_fields(payload)

    with transaction.atomic():
        record = _ensure_pending_permission(corr, perm_value, day, hours, notes)
        record.permission_type = perm_value
        record.date = day
        record.hours = hours
        record.notes = notes
        record.status = 'pending'
        record.approved = False
        record.save(update_fields=[
            'permission_type', 'date', 'hours', 'notes', 'status', 'approved',
        ])

    normalized = {
        'permission_type': perm_value.code,
        'date': str(day),
        'hours': str(hours),
        'notes': notes,
        'permission_id': record.pk,
    }
    title = f'Attendance permission {perm_value.code} {day}'
    return normalized, title
