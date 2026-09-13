"""HostActions port — host-effect execution (mutations + read-only actions).

The engine never mutates host state itself (RULE_21).  It *proposes* an action
and the host command boundary (P2-06) applies identity → scope → contract →
validate → PDP → consent → budget → idempotency → execute → verify.  This port
is the engine-facing half of that seam; ``ActionProposal`` is the D1 wording's
"business effect" the engine emits.
"""
from __future__ import annotations

from typing import Any, Protocol, TypedDict


class ActionProposal(TypedDict, total=False):
    """A proposed host action (declared tool + params + consent requirement)."""

    action: str
    tool: str
    params: dict[str, Any]
    objects: list[str]
    requires_confirmation: bool
    idempotency_key: str | None


class ActionOutcome(TypedDict, total=False):
    """The confirmed outcome of a host action."""

    status: str  # "executed" | "confirmed" | "refused" | "deferred" | "failed"
    result: Any
    confirmation_token: str | None
    error: str | None
    event_ids: list[str]


class HostActions(Protocol):
    """Executes host effects on the engine's behalf, always behind consent."""

    async def propose_action(
        self,
        tool: str,
        params: dict[str, Any],
        objects: list[str],
        requires_confirmation: bool = True,
        idempotency_key: str | None = None,
    ) -> ActionProposal:
        """Declare an action the engine wants the host to perform (no effect yet)."""
        ...

    async def execute_action(
        self, proposal: ActionProposal, confirmation_token: str | None = None
    ) -> ActionOutcome:
        """Ask the host command boundary to execute a confirmed proposal.

        For ``requires_confirmation=True`` proposals the host refuses without a
        valid ``confirmation_token`` (fail-closed).  Read-only actions may pass
        ``requires_confirmation=False``.
        """
        ...
