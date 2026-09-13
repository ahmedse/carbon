"""PDP v1 — host-side Policy Decision Point (P2-07).

Implements :class:`ai.engine.ports.policy.PolicyDecisionPoint` on the host
side, over Django + ``ai.models``.

Semantics (fixed by the port and honoured here):

* **default deny** — absence of any matching permit → ``Decision.REFUSE``.
* **forbid overrides permit** — any matching deny → ``Decision.REFUSE``.
* **evaluation error → refuse** for mandatory policies (fail-closed) — a
  mandatory policy that raises during evaluation yields ``Decision.REFUSE``
  with a reason naming the failure; the error is never swallowed into an allow.
* **every decision persisted** — each ``decide()`` writes one
  :class:`ai.models.pdp.PolicyDecisionRow` carrying ``reason`` +
  ``policy_version``.

This module is host-side (it MAY import Django and ``ai.models``). The only
coupling to the engine is the port types from ``ai.engine.ports.policy`` (the
seam); nothing in ``ai.engine`` imports this module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from asgiref.sync import sync_to_async

from ai.engine.ports.policy import Decision, PolicyDecision

logger = logging.getLogger("carbon.ai.pdp")

DEFAULT_POLICY_VERSION = "pdp-v1.0"

# Autonomy dial levels (P2-07 §7) ordered low → high. Unknown strings are
# treated as the most conservative level (``human_only``).
_AUTONOMY_LEVELS = {"human_only": 0, "act_confirm": 1, "auto": 2}


def _read_outcome(autonomy: str) -> Decision:
    """Read-only actions are always allowed regardless of the dial."""
    return Decision.ALLOW


def _mutation_outcome(autonomy: str) -> Decision:
    """Mutating actions are gated by the per-activity autonomy dial."""
    level = _AUTONOMY_LEVELS.get(autonomy, 0)
    if level >= 2:
        return Decision.ALLOW
    if level == 1:
        return Decision.ALLOW_WITH_CONFIRMATION
    return Decision.ASK


@dataclass(frozen=True)
class Policy:
    """A single deterministic PDP rule.

    ``matcher``, when supplied, is the full evaluation function (used by tests
    to inject a policy that raises). Otherwise matching is by ``actions``.
    ``permit_outcome`` resolves the outcome for a matched *permit* policy as a
    function of the autonomy dial.
    """

    name: str
    effect: str  # "permit" | "deny"
    reason: str
    mandatory: bool = False
    actions: frozenset[str] = frozenset()
    matcher: Callable[..., bool] | None = None
    permit_outcome: Callable[[str], Decision] | None = None

    def matches(
        self,
        principal: str,
        action: str,
        objects: list[str],
        process_state: dict[str, Any] | None,
    ) -> bool:
        """Return True if this policy applies to the request. May raise."""
        if self.matcher is not None:
            return bool(
                self.matcher(
                    principal=principal,
                    action=action,
                    objects=objects,
                    process_state=process_state,
                )
            )
        if self.actions and action not in self.actions:
            return False
        return True


# ── Default (in-code) policy table ──────────────────────────────────────────
# Exercises all three fixed semantics:
#   1. read-only permit → allow (default deny is exercised by any unknown action)
#   2. mutating permit gated by autonomy → ask / allow_with_confirmation / allow
#   3. destructive deny that overlaps the mutating permit → forbid overrides permit

_READ_ACTIONS = frozenset(
    {"read", "list", "get", "search", "view", "inspect", "retrieve", "describe"}
)
_MUTATING_ACTIONS = frozenset(
    {"create", "update", "upsert", "write", "send", "execute", "run", "archive", "delete"}
)
_DESTRUCTIVE_ACTIONS = frozenset({"delete", "purge", "drop"})

DEFAULT_POLICIES: tuple[Policy, ...] = (
    Policy(
        name="permit-read-only",
        effect="permit",
        reason="read-only action is permitted",
        actions=_READ_ACTIONS,
        permit_outcome=_read_outcome,
    ),
    Policy(
        name="permit-mutations-by-autonomy",
        effect="permit",
        reason="mutating action governed by the per-activity autonomy dial",
        actions=_MUTATING_ACTIONS,
        permit_outcome=_mutation_outcome,
    ),
    Policy(
        name="deny-destructive",
        effect="deny",
        reason="destructive actions are forbidden by policy",
        mandatory=True,
        actions=_DESTRUCTIVE_ACTIONS,
    ),
)


class PDP:
    """Host-side Policy Decision Point v1.

    Deterministic and offline: evaluation is a pure table scan, no LLM, no
    network. Decisions are persisted via ``ai.models.pdp.PolicyDecisionRow``.
    """

    def __init__(
        self,
        policies: tuple[Policy, ...] = DEFAULT_POLICIES,
        policy_version: str = DEFAULT_POLICY_VERSION,
    ) -> None:
        self._policies: tuple[Policy, ...] = tuple(policies)
        self._policy_version = policy_version

    @property
    def policy_version(self) -> str:
        return self._policy_version

    async def decide(
        self,
        principal: str,
        action: str,
        objects: list[str],
        process_state: dict[str, Any] | None = None,
        autonomy: str = "human_only",
        budget: dict[str, Any] | None = None,
        time: Any = None,
    ) -> PolicyDecision:
        """Return a decision for ``principal`` performing ``action``.

        Default-deny; forbid overrides permit; an evaluation error on a
        mandatory policy returns ``Decision.REFUSE`` (fail-closed). Every call
        is persisted.
        """
        objects = list(objects or [])

        matched_permits: list[Policy] = []
        matched_deny: Policy | None = None

        for policy in self._policies:
            try:
                applies = policy.matches(principal, action, objects, process_state)
            except Exception as exc:  # noqa: BLE001 — fail-closed boundary
                if policy.mandatory:
                    return await self._persist(
                        principal=principal,
                        action=action,
                        objects=objects,
                        decision=Decision.REFUSE,
                        reason=(
                            f"mandatory policy {policy.name!r} failed during "
                            f"evaluation: {type(exc).__name__}: {exc}"
                        ),
                        autonomy=autonomy,
                        process_state=process_state,
                        budget=budget,
                    )
                logger.warning(
                    "non-mandatory policy %r raised and was skipped: %s",
                    policy.name,
                    exc,
                )
                continue

            if not applies:
                continue

            if policy.effect == "deny":
                matched_deny = policy
            else:
                matched_permits.append(policy)

        # forbid overrides permit — deny always wins.
        if matched_deny is not None:
            return await self._persist(
                principal=principal,
                action=action,
                objects=objects,
                decision=Decision.REFUSE,
                reason=matched_deny.reason,
                autonomy=autonomy,
                process_state=process_state,
                budget=budget,
            )

        # default deny — no permit matched.
        if not matched_permits:
            return await self._persist(
                principal=principal,
                action=action,
                objects=objects,
                decision=Decision.REFUSE,
                reason=(
                    f"default deny: no permit policy matched action {action!r}"
                ),
                autonomy=autonomy,
                process_state=process_state,
                budget=budget,
            )

        outcome = self._resolve(matched_permits, autonomy)
        return await self._persist(
            principal=principal,
            action=action,
            objects=objects,
            decision=outcome,
            reason=self._permit_reason(matched_permits, outcome, autonomy),
            autonomy=autonomy,
            process_state=process_state,
            budget=budget,
        )

    # ── internals ───────────────────────────────────────────────────────────

    @staticmethod
    def _resolve(matched_permits: list[Policy], autonomy: str) -> Decision:
        """Pick the most restrictive outcome across matching permits."""
        ranking = {
            Decision.REFUSE: 0,
            Decision.ASK: 1,
            Decision.DEFER: 2,
            Decision.ALLOW_WITH_CONFIRMATION: 3,
            Decision.ALLOW: 4,
        }
        outcomes = [
            policy.permit_outcome(autonomy)
            if policy.permit_outcome is not None
            else Decision.ALLOW_WITH_CONFIRMATION  # conservative default
            for policy in matched_permits
        ]
        return min(outcomes, key=lambda d: ranking[d])

    @staticmethod
    def _permit_reason(
        matched_permits: list[Policy], outcome: Decision, autonomy: str
    ) -> str:
        names = ", ".join(p.name for p in matched_permits)
        if outcome is Decision.ALLOW:
            return f"permitted by {names} (autonomy={autonomy})"
        if outcome is Decision.ALLOW_WITH_CONFIRMATION:
            return f"permitted by {names}; confirmation required (autonomy={autonomy})"
        if outcome is Decision.ASK:
            return f"permitted by {names}; human approval required (autonomy={autonomy})"
        return f"permitted by {names}"

    async def _persist(
        self,
        *,
        principal: str,
        action: str,
        objects: list[str],
        decision: Decision,
        reason: str,
        autonomy: str,
        process_state: dict[str, Any] | None,
        budget: dict[str, Any] | None,
    ) -> PolicyDecision:
        from ai.models.pdp import PolicyDecisionRow

        await sync_to_async(PolicyDecisionRow.objects.create, thread_sensitive=True)(
            principal=principal,
            action=action,
            resource_objects=objects,
            decision=decision.value,
            reason=reason,
            policy_version=self._policy_version,
            autonomy=autonomy,
            process_state=process_state,
            budget=budget,
        )
        return {
            "decision": decision,
            "reason": reason,
            "policy_version": self._policy_version,
        }


_default_pdp = PDP()


async def decide(
    principal: str,
    action: str,
    objects: list[str],
    process_state: dict[str, Any] | None = None,
    autonomy: str = "human_only",
    budget: dict[str, Any] | None = None,
    time: Any = None,
) -> PolicyDecision:
    """Module-level convenience wrapper over the default :class:`PDP`."""
    return await _default_pdp.decide(
        principal=principal,
        action=action,
        objects=objects,
        process_state=process_state,
        autonomy=autonomy,
        budget=budget,
        time=time,
    )
