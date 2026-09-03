"""Phase H1-B — write-only AI action audit trail helper.

A single, append-only seam for recording AI actions to the :class:`AuditLog`
model.  Audit writes are best-effort by construction: a failed audit write
must never break the user's turn (RULE_21 — recording only, never mutating
the AI's behavior).

The ``AuditLog`` model is reused as-is (``ai.models.core.AuditLog``); no new
model or migration is introduced here.
"""

import logging

from ai.models.core import AuditLog
from ai.pii_guard import PIIGuard

logger = logging.getLogger("ai.audit")


class AuditService:
    @staticmethod
    def log(*, action, actor, actor_type="user", target=None, detail=None,
            instance_id="carbon", host_user_id=None, visibility="private"):
        """Write-only audit log. Append-only by construction — no update/delete.

        NEVER raises: an audit failure must not break the user's turn.
        """
        try:
            target_clean = PIIGuard.redact(str(target)) if target is not None else None
            detail_clean = PIIGuard.redact_dict(detail) if detail else {}
            AuditLog.objects.create(
                instance_id=instance_id,
                actor=str(actor),
                actor_type=actor_type,
                action=action,
                target=target_clean,
                detail=detail_clean,
                host_user_id=str(host_user_id) if host_user_id is not None else None,
                visibility=visibility,
            )
        except Exception:
            logger.exception("audit write failed action=%s", action)
