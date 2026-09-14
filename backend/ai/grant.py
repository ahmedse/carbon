"""Host-side business-approval grant resolution (P3-06).

This module is the host-side counterpart to the boundary's ``grant`` stage
(``CommandBoundary`` stage 8). It is strictly separate from:

* **authorization** — :mod:`ai.pdp` (can the principal act? default-deny), and
* **consent** — ``CommandBoundary`` stage 7 (RULE_21, per-action confirmation).

A grant is a durable, human-minted approval that pins the *exact* material
effect. This resolver reads :class:`ai.models.approval.ApprovalGrant` and, when
no active, fully-matching grant exists, records the refusal as a
:class:`ai.models.pdp.PolicyDecisionRow` with ``stage="grant"`` so the audit
ledger attributes the refusal to the grant stage (not the PDP stage).

The engine never imports this module (RULE_20 / ADR-0007); the boundary only
receives this callable by constructor injection (``grant_resolver=``).
"""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import sync_to_async

from ai.models.approval import ApprovalGrant, canonicalize_args
from ai.models.pdp import PolicyDecisionRow

logger = logging.getLogger("carbon.ai.grant")

GRANT_REFUSAL_REASON = "grant: no active, fully-matching ApprovalGrant"


async def _record_grant_refusal(command: Any, principal: str) -> None:
    """Persist a ``stage="grant"`` refusal row so the refusal is attributed."""
    await sync_to_async(PolicyDecisionRow.objects.create, thread_sensitive=True)(
        principal=principal,
        action=command.action or command.tool,
        resource_objects=command.objects or [],
        decision="refuse",
        reason=GRANT_REFUSAL_REASON,
        policy_version="grant",
        stage="grant",
        autonomy=command.autonomy,
        process_state=command.process_state,
        budget=command.budget,
    )


async def resolve_grant(command: Any) -> dict[str, Any] | None:
    """Return the active, fully-matching grant (id + granted_by), else ``None``.

    When no match exists (or the command carries no capability), a refusal row
    is persisted with ``stage="grant"`` and ``None`` is returned so the boundary
    refuses. Matching is exact across every pinned dimension: any change to
    ``process_version``, ``capability_version``, ``canonical_args``,
    ``object_revisions``, or ``evidence_digest`` — or a mismatched object
    identity — invalidates the grant (fail-closed).
    """
    if not command.capability:
        return None

    canonical = canonicalize_args(command.params or {})
    grant = await sync_to_async(ApprovalGrant.find_active, thread_sensitive=True)(
        capability=command.capability,
        process_version=command.process_version or "",
        capability_version=command.capability_version or "",
        canonical_args=canonical,
        object_revisions=command.object_revisions or {},
        evidence_digest=command.evidence_digest or "",
        object_id=command.object_id or None,
        object_type=command.object_type or None,
        process_instance=command.process_instance or None,
    )
    if grant is not None:
        return {"id": grant.id, "granted_by": grant.granted_by}

    principal = command.principal or (
        command.scope.user_identifier if command.scope is not None else ""
    )
    await _record_grant_refusal(command, principal)
    return None


__all__ = ["resolve_grant", "GRANT_REFUSAL_REASON"]
