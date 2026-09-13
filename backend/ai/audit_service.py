"""Phase H1-B — write-only AI action audit trail helper.

A single, append-only seam for recording AI actions to the :class:`AuditLog`
model.  Audit writes are best-effort by construction: a failed audit write
must never break the user's turn (RULE_21 — recording only, never mutating
the AI's behavior).

The ``AuditLog`` model is reused as-is (``ai.models.core.AuditLog``); no new
model or migration is introduced here.
"""

import json
import logging
from datetime import datetime, timezone

from ai.instance_registry import resolve_instance_id
from ai.models.core import AuditLog
from ai.pii_guard import PIIGuard

logger = logging.getLogger("ai.audit")


class AuditService:
    @staticmethod
    def log(*, action, actor, actor_type="user", target=None, detail=None,
            instance_id=None, host_user_id=None, visibility="private"):
        """Write-only audit log. Append-only by construction — no update/delete.

        Single write path for AI audit (P2-09): persists one ``AuditLog`` row
        AND emits the ``AI_AUDIT`` structured log line. The log line is the
        authoritative signal and is emitted even when the row write fails, so
        log and row stay paired.

        NEVER raises: an audit failure must not break the user's turn.
        """
        resolved_instance_id = instance_id or resolve_instance_id()
        target_clean = PIIGuard.redact(str(target)) if target is not None else None
        detail_clean = PIIGuard.redact_dict(detail) if detail else {}
        actor_str = str(actor)
        host_user_id_str = str(host_user_id) if host_user_id is not None else None

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor_str,
            "actor_type": actor_type,
            "action": action,
            "target": target_clean,
            "detail": detail_clean,
            "instance_id": resolved_instance_id,
            "host_user_id": host_user_id_str,
            "visibility": visibility,
        }

        try:
            AuditLog.objects.create(
                instance_id=resolved_instance_id,
                actor=actor_str,
                actor_type=actor_type,
                action=action,
                target=target_clean,
                detail=detail_clean,
                host_user_id=host_user_id_str,
                visibility=visibility,
            )
        except Exception:
            logger.exception("audit write failed action=%s", action)
        finally:
            # The log line is the authoritative signal: always emitted, even
            # when the row write failed above.
            logger.info("AI_AUDIT %s", json.dumps(record, default=str))
