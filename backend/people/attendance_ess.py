"""Attendance permission ESS — employee submit via Correspondence (ADR-0030).

Mirrors leave: domain row + Correspondence spine; manager approve flips
``AttendancePermission.approved`` via signal. Admin PATCH + NPS-1 SoD remains
an ops fallback (not the Agent happy path).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from correspondence import fsm
from correspondence.exceptions import InvalidTransition, SubmissionBlocked
from correspondence.models import Correspondence
from correspondence.policies import PolicyNotFound
from mdm.models import ReferenceValue

from people.models import AttendancePermission, Employee

SUBJECT_TYPE = "people.AttendancePermission"
CORR_TYPE_CODE = "attendance_permission"


class AttendanceESSError(Exception):
    """Validation / policy failure for ESS submit — map to HTTP 4xx."""

    def __init__(self, detail: str, *, status: int = 400, extra: dict | None = None):
        super().__init__(detail)
        self.detail = detail
        self.status = status
        self.extra = extra or {}


def _corr_type_value():
    return ReferenceValue.objects.get(
        reference_set__name="correspondence_type",
        code=CORR_TYPE_CODE,
    )


def submit_my_attendance_permission(user, data: dict[str, Any]) -> Correspondence:
    """Create pending AttendancePermission + submit Correspondence for manager.

    Caller must be an active employee (``user.employee_profile``). Forces
    ``approved=False``; manager corr approve sets it True via signal.
    """
    try:
        profile = user.employee_profile
    except (Employee.DoesNotExist, AttributeError):
        profile = None
    if profile is None or not getattr(profile, "is_active", False):
        raise AttendanceESSError(
            "No active employee profile is linked to your account",
            status=403,
        )

    from people.manager_routing import manager_routing_block_response

    blocked = manager_routing_block_response(profile)
    if blocked is not None:
        body = blocked.data if hasattr(blocked, "data") else {}
        raise AttendanceESSError(
            body.get("detail") or "Manager routing unavailable",
            status=blocked.status_code,
            extra={k: v for k, v in body.items() if k != "detail"},
        )

    data = data or {}
    permission_type = data.get("permission_type")
    if not isinstance(permission_type, str) or not permission_type.strip():
        raise AttendanceESSError("permission_type is required")

    perm_value = ReferenceValue.objects.filter(
        reference_set__name="permission_type",
        code=permission_type.strip(),
    ).first()
    if perm_value is None:
        raise AttendanceESSError("Invalid permission_type")

    try:
        day = date.fromisoformat(str(data.get("date", "")))
    except (ValueError, TypeError):
        raise AttendanceESSError("Invalid date (expected ISO date)") from None

    try:
        hours = Decimal(str(data.get("hours")))
    except (InvalidOperation, ValueError, TypeError):
        raise AttendanceESSError("hours must be a positive number") from None
    if hours <= 0:
        raise AttendanceESSError("hours must be a positive number")

    notes = data.get("notes", "") or ""

    try:
        with transaction.atomic():
            record = AttendancePermission.objects.create(
                employee=profile,
                date=day,
                permission_type=perm_value,
                hours=hours,
                approved=False,
                notes=notes,
            )
            corr = Correspondence.objects.create(
                corr_type=_corr_type_value(),
                subject_type=SUBJECT_TYPE,
                subject_id=record.pk,
                org_unit=profile.org_unit,
                requester=user,
                title=f"Attendance permission {permission_type} {day} ({hours}h)",
                payload={
                    "permission_type": permission_type.strip(),
                    "date": str(day),
                    "hours": str(hours),
                    "notes": notes,
                    "permission_id": record.pk,
                },
                status="draft",
                reference_no=f"DRAFT-{uuid.uuid4().hex[:12]}",
            )
            corr = fsm.submit_correspondence(
                corr=corr,
                by=user,
                subject=record,
                subject_label=SUBJECT_TYPE,
            )
    except SubmissionBlocked as exc:
        raise AttendanceESSError(
            "Submission blocked by DQ gate",
            extra={"failures": exc.failures},
        ) from exc
    except PolicyNotFound as exc:
        raise AttendanceESSError("No workflow policy configured") from exc
    except InvalidTransition as exc:
        raise AttendanceESSError(
            f"Invalid transition: {exc}",
            status=409,
        ) from exc
    except ReferenceValue.DoesNotExist as exc:
        raise AttendanceESSError(
            "attendance_permission correspondence type is not seeded",
        ) from exc

    return corr
