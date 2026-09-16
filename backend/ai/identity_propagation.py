"""Identity propagation helpers (PEC-ID-1 / ADR-0033).

Builds audit-only ``actor_chain`` attribution for PDP / grant ledger rows.
Does **not** change CBAC decisions — attribution is metadata only.

In-process host effects continue to use
``user_token=f"inproc:{instance_id}:{host_user_id}"`` (engine_runtime);
this module never invents JWTs or IdP exchanges (Phase 2).
"""

from __future__ import annotations

import uuid
from typing import Any


def new_request_id() -> str:
    """Return a fresh per-effect correlation id."""
    return str(uuid.uuid4())


def resolve_request_id(request_id: str | None) -> str:
    """Use the supplied request id or mint one."""
    rid = (request_id or "").strip()
    return rid or new_request_id()


def build_actor_chain(
    *,
    user_id: str | None,
    instance_id: str | None = "",
    request_id: str | None = "",
    tool: str | None = None,
    action: str | None = None,
) -> list[dict[str, Any]]:
    """Return ordered ``user → engine → tool`` hops for audit.

    ``request_id`` / ``instance_id`` are echoed on the user hop so a single
    chain document is self-describing when exported.
    """
    uid = str(user_id).strip() if user_id else ""
    iid = str(instance_id).strip() if instance_id else ""
    rid = resolve_request_id(request_id)

    chain: list[dict[str, Any]] = [
        {
            "role": "user",
            "id": uid,
            "instance_id": iid,
            "request_id": rid,
        },
        {
            "role": "engine",
            "id": "inproc",
            "instance_id": iid,
            "token_form": f"inproc:{iid}:{uid}" if uid else f"inproc:{iid}:",
        },
    ]
    tool_id = (tool or action or "").strip()
    if tool_id:
        chain.append({"role": "tool", "id": tool_id})
    return chain


def attribution_from_command(command: Any) -> dict[str, Any]:
    """Extract persistable attribution fields from a ``Command``-like object."""
    host_user_id = getattr(command, "host_user_id", None)
    if not host_user_id and getattr(command, "scope", None) is not None:
        host_user_id = getattr(command.scope, "user_identifier", None) or None
    if not host_user_id:
        principal = getattr(command, "principal", None)
        host_user_id = str(principal) if principal else None

    instance_id = getattr(command, "instance_id", "") or ""
    request_id = resolve_request_id(getattr(command, "request_id", None) or "")
    tool = getattr(command, "tool", "") or ""
    action = getattr(command, "action", "") or ""

    # Keep Command.request_id stable for the rest of the boundary hop.
    if hasattr(command, "request_id") and not (getattr(command, "request_id", None) or "").strip():
        command.request_id = request_id

    chain = build_actor_chain(
        user_id=host_user_id,
        instance_id=instance_id,
        request_id=request_id,
        tool=tool,
        action=action,
    )
    return {
        "actor_chain": chain,
        "request_id": request_id,
        "instance_id": instance_id,
        "host_user_id": str(host_user_id) if host_user_id else None,
    }


__all__ = [
    "attribution_from_command",
    "build_actor_chain",
    "new_request_id",
    "resolve_request_id",
]
