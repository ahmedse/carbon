"""Admin skill promote/reject decisions (PEC-6A).

Promotion is gate-only: this service calls ``gate._promote_skill`` (which
always runs the four critics via ``admit_skill``).  There is no path that
sets ``instance_promoted`` by writing status directly or forging the
promotion token.

Reject deprecates the skill through ``gate.rollback_skill`` after the
closed transition table allows it, and records an audit row either way.
"""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from rest_framework.exceptions import NotFound, ValidationError

from accounts.ai_scoping import scope_ai_queryset
from ai.audit_service import AuditService
from ai.engine.skills._authority import assert_allowed_transition
from ai.instance_registry import resolve_instance_id
from ai.models.core import Skill
from ai.store import get_store

logger = logging.getLogger("carbon.ai.skills_decision")


def _serialize_skill(skill: Skill) -> dict[str, Any]:
    return {
        "id": skill.id,
        "name": skill.name,
        "kind": skill.kind,
        "status": skill.status,
        "gate_status": skill.gate_status,
        "promoted_at": skill.promoted_at.isoformat() if skill.promoted_at else None,
        "promoted_by": skill.promoted_by,
        "usage_count": skill.usage_count,
    }


def _scoped_skill(user, skill_id: str) -> Skill:
    qs = scope_ai_queryset(Skill.objects, user)
    skill = qs.filter(id=skill_id).first()
    if skill is None:
        raise NotFound({"error": "not_found", "detail": "Skill not found."})
    return skill


def promote_skill(*, user, skill_id: str) -> dict[str, Any]:
    """Run the admission gate and promote on admit; audit the decision."""
    skill = _scoped_skill(user, skill_id)
    actor = str(user.pk)
    promoted_by = f"admin:{user.username}"

    async def _go():
        from ai.engine.skills.gate import _promote_skill

        factory = get_store().get_session_factory()
        async with factory() as db:
            return await _promote_skill(skill.id, db, promoted_by=promoted_by)

    try:
        promoted = async_to_sync(_go)()
    except ValueError as exc:
        AuditService.log(
            action="ai.skill_promote_denied",
            actor=actor,
            host_user_id=actor,
            target=skill.id,
            instance_id=skill.instance_id or resolve_instance_id(),
            detail={
                "name": skill.name,
                "reason": str(exc),
                "decision": "denied",
            },
            visibility="shared",
        )
        raise ValidationError(
            {"error": "admission_rejected", "detail": str(exc)}
        ) from exc

    AuditService.log(
        action="ai.skill_promoted",
        actor=actor,
        host_user_id=actor,
        target=promoted.id,
        instance_id=promoted.instance_id or resolve_instance_id(),
        detail={
            "name": promoted.name,
            "kind": promoted.kind,
            "promoted_by": promoted.promoted_by,
            "gate_status": promoted.gate_status,
            "decision": "promote",
        },
        visibility="shared",
    )

    # Re-read via Django ORM so the response reflects the committed row.
    skill.refresh_from_db()
    return {
        "decision": "promote",
        "verdict": "admitted",
        "skill": _serialize_skill(skill),
    }


def reject_skill(*, user, skill_id: str, reason: str = "") -> dict[str, Any]:
    """Deprecate a skill with an optional reason; audit the decision."""
    skill = _scoped_skill(user, skill_id)
    actor = str(user.pk)
    reason = (reason or "").strip()

    try:
        assert_allowed_transition(skill.status, "deprecated")
    except ValueError as exc:
        raise ValidationError(
            {"error": "illegal_transition", "detail": str(exc)}
        ) from exc

    async def _go():
        from ai.engine.skills.gate import rollback_skill

        factory = get_store().get_session_factory()
        async with factory() as db:
            return await rollback_skill(skill.id, db, reason=reason)

    try:
        async_to_sync(_go)()
    except ValueError as exc:
        raise ValidationError(
            {"error": "reject_failed", "detail": str(exc)}
        ) from exc

    skill.refresh_from_db()
    AuditService.log(
        action="ai.skill_rejected",
        actor=actor,
        host_user_id=actor,
        target=skill.id,
        instance_id=skill.instance_id or resolve_instance_id(),
        detail={
            "name": skill.name,
            "kind": skill.kind,
            "reason": reason[:500],
            "decision": "reject",
            "status": skill.status,
            "gate_status": skill.gate_status,
        },
        visibility="shared",
    )
    return {
        "decision": "reject",
        "verdict": "rejected",
        "skill": _serialize_skill(skill),
    }
