"""PolicyDecisionPoint port — authorization decision (default-deny, fail-closed).

The engine asks *"may this principal perform this action on these objects?"*
before any effect is emitted.  Semantics are fixed by P2-07 and must be honored
by every host implementation:

* **default deny** — absence of a permit is a refuse.
* **forbid overrides permit** — any matching deny wins.
* **evaluation error → refuse** for mandatory policies (fail-closed).
* every decision is persisted (``reason`` + ``policy_version``) for audit.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, TypedDict


class Decision(str, Enum):
    """The five PDP outcomes (P2-07)."""

    ALLOW = "allow"
    ALLOW_WITH_CONFIRMATION = "allow_with_confirmation"
    ASK = "ask"
    DEFER = "defer"
    REFUSE = "refuse"


class PolicyDecision(TypedDict, total=False):
    """A PDP decision: outcome + reason + the policy version that produced it."""

    decision: Decision
    reason: str
    policy_version: str
    # True when the decision is a fail-closed REFUSE caused by an infrastructure/
    # evaluation error (e.g. the store is unreachable) rather than a real policy
    # outcome. Lets the boundary classify it as an operational failure, not a deny.
    evaluation_error: bool


class PolicyDecisionPoint(Protocol):
    """Decides authorization for an action against current process state."""

    async def decide(
        self,
        principal: str,
        action: str,
        objects: list[str],
        process_state: dict[str, Any] | None = None,
        autonomy: str = "human_only",
        budget: dict[str, Any] | None = None,
        time: Any = None,
        *,
        actor_chain: list[dict[str, Any]] | None = None,
        request_id: str = "",
        instance_id: str = "",
        host_user_id: str | None = None,
    ) -> PolicyDecision:
        """Return a decision for ``principal`` performing ``action``.

        ``autonomy`` is a per-activity dial level (``human_only`` /
        ``act_confirm`` / …), not a standing authorization (see plan §7).
        Default-deny; forbid overrides permit; an evaluation error on a
        mandatory policy must return ``Decision.REFUSE``.

        Attribution kwargs are optional audit metadata (PEC-ID-1) and must not
        change the authorization outcome.
        """
        ...
