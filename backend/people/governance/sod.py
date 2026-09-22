"""Shared host Separation-of-Duties gate (ADR-0045 / RULE_34 / NPS-1).

Plane A enforcement for admin irreversibles: stamp preparer on the first
staging mutation; refuse the final effect when actor == preparer.

Employee-originated leave/loan SoD remains Correspondence (ADR-0030) — this
module does not replace that spine.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

# Subject type tokens (stable; stored on SoDPreparation.subject_type).
SUBJECT_PAYROLL_RUN = "payroll_run"
SUBJECT_WPS_FILING = "wps_filing"
SUBJECT_EMPLOYEE = "employee"
SUBJECT_ATTENDANCE_PERMISSION = "attendance_permission"

ACTION_COMMIT = "commit"
ACTION_SUBMIT = "submit"
ACTION_ACTIVATE = "activate"
ACTION_APPROVE = "approve"


class SoDViolation(Exception):
    """Host SoD refused — map to HTTP 403 at DRF / host_executor boundaries."""

    def __init__(self, message: str, *, code: str = "sod_violation"):
        super().__init__(message)
        self.code = code


def record_preparer(
    *,
    subject_type: str,
    subject_id: int,
    user,
    process_key: str = "",
    overwrite: bool = False,
) -> None:
    """First-writer-wins stamp (unless ``overwrite=True``).

    No-op when ``user`` is missing — staging without an authenticated actor
    cannot establish SoD; irreversible steps will then fail-closed.
    """
    if user is None or not getattr(user, "pk", None):
        return
    from people.models import SoDPreparation

    existing = SoDPreparation.objects.filter(
        subject_type=subject_type, subject_id=subject_id,
    ).first()
    if existing is not None and not overwrite:
        return
    if existing is not None and overwrite:
        existing.preparer = user
        existing.prepared_at = timezone.now()
        if process_key:
            existing.process_key = process_key
        existing.save(update_fields=["preparer", "prepared_at", "process_key"])
        return
    SoDPreparation.objects.create(
        subject_type=subject_type,
        subject_id=subject_id,
        preparer=user,
        process_key=process_key or "",
        prepared_at=timezone.now(),
    )


def get_preparer(*, subject_type: str, subject_id: int):
    """Return preparer User or None."""
    from people.models import SoDPreparation

    row = (
        SoDPreparation.objects.select_related("preparer")
        .filter(subject_type=subject_type, subject_id=subject_id)
        .first()
    )
    return row.preparer if row else None


def require_distinct_actor(
    *,
    subject_type: str,
    subject_id: int,
    actor,
    action: str,
) -> None:
    """Refuse when actor is missing, preparer missing, or actor == preparer.

    Fail-closed (ADR-0045): no preparer stamp → cannot finalize.
    """
    if actor is None or not getattr(actor, "pk", None):
        raise SoDViolation(
            f"SoD refused: authenticated actor required for {action}.",
            code="sod_missing_actor",
        )
    preparer = get_preparer(subject_type=subject_type, subject_id=subject_id)
    if preparer is None:
        raise SoDViolation(
            f"SoD refused: no preparer recorded for this {subject_type} — "
            f"complete the staging step first, then a distinct actor must {action}.",
            code="sod_missing_preparer",
        )
    if int(preparer.pk) == int(actor.pk):
        raise SoDViolation(
            f"SoD refused: preparer cannot {action} "
            f"(separation of duties — requester/preparer ≠ approver).",
            code="sod_same_actor",
        )


# Alias used at irreversible boundaries.
require_sod = require_distinct_actor
