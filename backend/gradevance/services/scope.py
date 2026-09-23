"""Course / persona scoping helpers for learn + teach surfaces (ADR-0042)."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from django.db.models import QuerySet

from gradevance.models import AnalysisRun, Assignment, Course, Enrollment, Submission
from gradevance.permissions import _can


def compute_my_status(user, assignment: Assignment) -> str:
    """Student desk chip: open | drafted | submitted | released."""
    if AnalysisRun.objects.filter(
        submission__assignment=assignment,
        submission__student_user=user,
        released=True,
    ).exists():
        return "released"

    subs = list(
        Submission.objects.filter(assignment=assignment, student_user=user).only(
            "id", "text", "status"
        )
    )
    meaningful = [s for s in subs if (s.text or "").strip()]
    if not meaningful:
        return "open"

    if any(
        s.status in (Submission.STATUS_SUBMITTED, Submission.STATUS_ANALYZED)
        for s in meaningful
    ):
        return "submitted"
    if any(s.status == Submission.STATUS_DRAFT for s in meaningful):
        return "drafted"
    return "open"


def user_is_course_staff(user) -> bool:
    """True when the user may mark/manage GradeVance (existing MarkAccess logic)."""
    return _can(user, "gradevance:mark") or _can(user, "gradevance:manage")


def courses_for_student(user) -> QuerySet[Course]:
    return Course.objects.filter(
        enrollments__user=user,
        enrollments__role=Enrollment.ROLE_STUDENT,
        enrollments__active=True,
    ).distinct()


def teacher_enrollment_course_ids(user) -> list[UUID]:
    return list(
        Enrollment.objects.filter(
            user=user,
            role__in=[Enrollment.ROLE_TA, Enrollment.ROLE_INSTRUCTOR],
            active=True,
        ).values_list("course_id", flat=True)
    )


def courses_for_teacher(user) -> QuerySet[Course]:
    """Courses the teacher owns via enrollment; all courses if staff with zero rows."""
    ids = teacher_enrollment_course_ids(user)
    if ids:
        return Course.objects.filter(id__in=ids)
    if user_is_course_staff(user):
        # Transition compat: seeded demos have no Enrollment rows yet.
        return Course.objects.all()
    return Course.objects.none()


def teach_course_scope_ids(user) -> Optional[list[UUID]]:
    """Return course UUID list to filter teach APIs, or None if unrestricted.

    Instructor/TA enrollments win. Otherwise live duties that grant
    ``gradevance:view`` supply the org units, and courses on those units
    (and their children) are included. A global duty with no deployment
    root stays unrestricted.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return []
    if getattr(user, "is_superuser", False):
        return None
    ids = teacher_enrollment_course_ids(user)
    if ids:
        return ids
    from accounts.rbac_utils import org_scope_for_capability

    scope = org_scope_for_capability(user, "gradevance:view")
    if scope.unrestricted:
        return None
    if not scope.ids:
        return []
    return list(
        Course.objects.filter(org_unit_id__in=scope.ids).values_list("id", flat=True)
    )


def student_can_access_assignment(user, assignment: Assignment) -> bool:
    """Published assignment on an enrolled course, or open practice (no course)."""
    if assignment.status != Assignment.STATUS_PUBLISHED:
        return False
    if assignment.course_id:
        return Enrollment.objects.filter(
            course_id=assignment.course_id,
            user=user,
            role=Enrollment.ROLE_STUDENT,
            active=True,
        ).exists()
    # Practice / open formative with no course — submit capability required.
    return assignment.mode == Assignment.MODE_FORMATIVE and (
        _can(user, "gradevance:submit")
        or _can(user, "gradevance:manage")
        or _can(user, "gradevance:view")
    )


def redact_run_payload_for_student(run, payload: dict) -> dict:
    """Strip summative bands when the run is not yet released to the student."""
    asg = run.submission.assignment
    if asg.mode == Assignment.MODE_SUMMATIVE and not run.released:
        payload = dict(payload)
        payload["advisory_bands"] = {"withheld": True}
        if "rubric_scores" in payload:
            payload["rubric_scores"] = []
    return payload
