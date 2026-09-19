"""Provision opaque student keys from an NRPS membership list."""
from __future__ import annotations

from dataclasses import dataclass

from gradevance.lti import LtiLaunchContext
from gradevance.lti.nrps import NrpsMember, parse_nrps_membership_page
from gradevance.lti.provision import provision_user_from_launch
from gradevance.models import Course, Enrollment


@dataclass
class RosterSyncResult:
    created: int
    existing: int
    usernames: list[str]
    enrollments_upserted: int = 0


def role_from_lti_roles(roles: tuple[str, ...] | list[str]) -> str | None:
    """Map IMS LTI roles → Enrollment.role (or None if no roster role)."""
    joined = " ".join(str(r).lower() for r in roles)
    # TeachingAssistant URIs often contain "Instructor#" — check TA first.
    if "teachingassistant" in joined or "teaching assistant" in joined:
        return Enrollment.ROLE_TA
    if "instructor" in joined or "faculty" in joined:
        return Enrollment.ROLE_INSTRUCTOR
    if "learner" in joined or "student" in joined:
        return Enrollment.ROLE_STUDENT
    return None


def ensure_enrollment(
    course: Course,
    user,
    role: str,
    *,
    source: str = Enrollment.SOURCE_NRPS,
) -> Enrollment:
    """Create or update an active Enrollment for (course, user)."""
    obj, _created = Enrollment.objects.update_or_create(
        course=course,
        user=user,
        defaults={
            "role": role,
            "source": source,
            "active": True,
        },
    )
    return obj


def resolve_course_for_nrps_context(context_id: str | None) -> Course | None:
    """Best-effort Course lookup from LTI context id.

    TODO: persist ``Course.lti_context_id`` (or a mapping table) once LMS
    contexts are linked at deep-link / launch time. Today we match ``code``
    when the context id equals an existing course code.
    """
    if not context_id:
        return None
    return Course.objects.filter(code=context_id).first()


def sync_nrps_members_to_users(
    *,
    iss: str,
    deployment_id: str,
    members: list[NrpsMember] | list[dict],
    course: Course | None = None,
    context_id: str | None = None,
) -> RosterSyncResult:
    """Idempotent: each NRPS user_id → ``lti:{iss}:{user_id}`` User + groups.

    When a Course can be resolved (explicit ``course`` or ``context_id`` →
    ``resolve_course_for_nrps_context``), also upsert Enrollment rows.
    """
    created = 0
    existing = 0
    names: list[str] = []
    enrollments_upserted = 0
    resolved = course or resolve_course_for_nrps_context(context_id)

    for raw in members:
        if isinstance(raw, dict):
            m = NrpsMember(
                user_id=str(raw.get("user_id") or ""),
                roles=tuple(raw.get("roles") or ()),
                name=str(raw.get("name") or ""),
                email=str(raw.get("email") or ""),
                status=str(raw.get("status") or "Active"),
            )
        else:
            m = raw
        if not m.user_id or m.status.lower() not in ("active", ""):
            continue
        ctx = LtiLaunchContext(
            iss=iss,
            sub=m.user_id,
            deployment_id=deployment_id,
            roles=m.roles,
        )
        result = provision_user_from_launch(ctx, email=m.email or None, name=m.name or None)
        if result.created:
            created += 1
        else:
            existing += 1
        names.append(result.username)

        if resolved is not None:
            role = role_from_lti_roles(m.roles)
            if role:
                from django.contrib.auth import get_user_model

                user = get_user_model().objects.filter(username=result.username).first()
                if user:
                    ensure_enrollment(resolved, user, role, source=Enrollment.SOURCE_NRPS)
                    enrollments_upserted += 1

    return RosterSyncResult(
        created=created,
        existing=existing,
        usernames=names,
        enrollments_upserted=enrollments_upserted,
    )


def sync_nrps_payload(
    *,
    iss: str,
    deployment_id: str,
    payload: dict,
    course: Course | None = None,
    context_id: str | None = None,
) -> RosterSyncResult:
    ctx = context_id
    if ctx is None:
        raw_ctx = payload.get("context")
        if isinstance(raw_ctx, dict):
            ctx = raw_ctx.get("id")
    return sync_nrps_members_to_users(
        iss=iss,
        deployment_id=deployment_id,
        members=parse_nrps_membership_page(payload),
        course=course,
        context_id=ctx,
    )
