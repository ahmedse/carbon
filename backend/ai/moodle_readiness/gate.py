"""Student-surface consent + cohort + RBAC gate (default-OFF).

A future student Pulse surface consults :func:`consult_student_surface` with a
:class:`StudentSurfaceContext`. The gate **rejects by default** and returns a
typed :class:`GateReason`. It is a pure function: no Django, no DB, no turn
path imports it (see ``tests/test_moodle_readiness.py`` for the proof).

Exact rules live in ``docs/pulse/aast-med/READINESS-SPEC.md`` § consent / cohort
/ RBAC / audit. This module is the code side of K11/S1; it does not open any
surface by itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

__all__ = [
    "Cohort",
    "ConsentRecord",
    "GateDecision",
    "GateReason",
    "StudentSurfaceContext",
    "consult_student_surface",
]


class GateReason(str, Enum):
    """Typed allow/deny reason. Deny reasons are stable audit tokens."""

    ALLOW = "allow"
    COURSE_NOT_LISTED = "course_not_listed"
    STUDENT_COHORTS_EMPTY = "student_cohorts_empty"
    NOT_IN_STUDENT_COHORT = "not_in_student_cohort"
    L5_NOT_PASSABLE = "l5_not_passable"
    STUDENT_NOTICE_UNPUBLISHED = "student_notice_unpublished"
    COURSE_NOT_OPENABLE = "course_not_openable"
    NO_CONSENT = "no_consent"
    CONSENT_REVOKED = "consent_revoked"
    CONSENT_COURSE_MISMATCH = "consent_course_mismatch"
    CONSENT_POLICY_STALE = "consent_policy_stale"


@dataclass(frozen=True)
class ConsentRecord:
    """One explicit, per-student, per-course opt-in.

    Cohort membership is never consent (spec: consent cannot be implied by
    enrolment or cohort). ``policy_version`` must match the surface's current
    policy or the record is stale and denies.
    """

    subject_id: str
    course_shortname: str
    policy_version: int
    granted: bool = False
    granted_at: str | None = None


@dataclass(frozen=True)
class Cohort:
    """Moodle system-cohort allow-list, by idnumber, never an enrolment.

    Mirrors the plugin settings ``local_pulse/staff_cohorts`` and
    ``local_pulse/student_cohorts``. An empty ``student_ids`` means
    faculty-only and blocks every student (R3).
    """

    staff_ids: frozenset[str] = field(default_factory=frozenset)
    student_ids: frozenset[str] = field(default_factory=frozenset)

    @property
    def students_empty(self) -> bool:
        return not self.student_ids

    def is_student(self, user_id: str) -> bool:
        return str(user_id or "") in self.student_ids

    def is_staff(self, user_id: str) -> bool:
        return str(user_id or "") in self.staff_ids


@dataclass(frozen=True)
class StudentSurfaceContext:
    """Everything the gate is allowed to know. Every field defaults closed."""

    user_id: str = ""
    course_shortname: str = ""
    cohort: Cohort = field(default_factory=Cohort)
    consent: ConsentRecord | None = None
    enabled_courses: frozenset[str] = field(default_factory=frozenset)
    can_open_course: bool = False
    l5_passable: bool = False
    student_notice_published: bool = False
    policy_version: int = 1


@dataclass(frozen=True)
class GateDecision:
    """Result of the gate. ``reason is GateReason.ALLOW`` iff ``allowed``."""

    allowed: bool
    reason: GateReason

    def __bool__(self) -> bool:  # a denied decision is falsy
        return self.allowed


def _deny(reason: GateReason) -> GateDecision:
    return GateDecision(allowed=False, reason=reason)


def consult_student_surface(context: StudentSurfaceContext) -> GateDecision:
    """Allow a student turn only when every artifact holds; else deny typed.

    Check order is the spec order so the first failure is the audit reason.
    An unset context (all defaults) denies on ``course_not_listed``.
    """
    ctx = context if isinstance(context, StudentSurfaceContext) else StudentSurfaceContext()
    shortname = str(ctx.course_shortname or "").strip()

    if not shortname or shortname not in ctx.enabled_courses:
        return _deny(GateReason.COURSE_NOT_LISTED)
    if ctx.cohort.students_empty:
        return _deny(GateReason.STUDENT_COHORTS_EMPTY)
    if not ctx.cohort.is_student(ctx.user_id):
        return _deny(GateReason.NOT_IN_STUDENT_COHORT)
    if not ctx.l5_passable:
        return _deny(GateReason.L5_NOT_PASSABLE)
    if not ctx.student_notice_published:
        return _deny(GateReason.STUDENT_NOTICE_UNPUBLISHED)
    if not ctx.can_open_course:
        return _deny(GateReason.COURSE_NOT_OPENABLE)

    consent = ctx.consent
    if consent is None:
        return _deny(GateReason.NO_CONSENT)
    if not consent.granted:
        return _deny(GateReason.CONSENT_REVOKED)
    if str(consent.course_shortname or "") != shortname:
        return _deny(GateReason.CONSENT_COURSE_MISMATCH)
    if int(consent.policy_version) != int(ctx.policy_version):
        return _deny(GateReason.CONSENT_POLICY_STALE)

    return GateDecision(allowed=True, reason=GateReason.ALLOW)
