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


def _host_api_outcome(autonomy: str) -> Decision:
    """Host API calls are always PDP-permitted.

    Read vs. mutation confirmation is decided at the call site
    (``ai.engine.agent.tools.execute_call_host_api``) via
    ``Command.requires_confirmation`` and the executor closure's own method
    check, so stage 6 returns a clean ALLOW and stage 7 consent is skipped.
    """
    return Decision.ALLOW


def _cancel_outcome(autonomy: str) -> Decision:
    """Cancel is a run-lifecycle stop — permitted, but never silently so.

    ``cancel`` is deliberately NOT a read and NOT a data mutation: it carries
    its own named action set + policy row so it is always auditable and never
    falls through to the read/mutation tables. The human-initiated stop is its
    own confirmation, and the boundary never requires a grant for ``cancel``
    (a user can always stop their own run).
    """
    return Decision.ALLOW


def _compensate_outcome(autonomy: str) -> Decision:
    """Compensate reverses prior effects and always requires confirmation.

    Compensation is gated as strictly as a destructive mutation: beyond this
    PDP decision it carries ``requires_grant=True`` (a durable, human-minted
    ``ApprovalGrant``) at the boundary, and it can never piggyback on a
    ``cancel`` decision.
    """
    return Decision.ALLOW_WITH_CONFIRMATION


# ── Skill tool authorization (P4-04) ──────────────────────────────────────
# Tool name → capability key.  A skill may only declare a tool for which the
# invoking principal holds the mapped capability.  This map is intentionally
# minimal and honest; new tool↔capability pairs are added here, never inferred
# from the (untrusted) skill body.

TOOL_CAPABILITY_MAP: dict[str, str] = {
    "code_execute": "ai:code_execute",
    "web_search": "ai:web_search",
    "web_research": "ai:web_search",
}


def authorized_tool_names(
    principal_capabilities: set[str] | frozenset[str],
) -> frozenset[str]:
    """Return the subset of :data:`TOOL_CAPABILITY_MAP` the principal may use.

    Pure helper (no Django imports): a ``"*"`` capability grants every mapped
    tool; otherwise a tool is authorized only when its mapped capability is
    present.  An empty/unknown capability set yields an empty result
    (fail-closed).
    """
    caps = set(principal_capabilities or ())
    if "*" in caps:
        return frozenset(TOOL_CAPABILITY_MAP.keys())
    return frozenset(
        tool for tool, capability in TOOL_CAPABILITY_MAP.items()
        if capability in caps
    )


def _deny_unauthorized_skill_tool(
    *,
    principal: str,
    action: str,
    objects: list[str],
    process_state: dict[str, Any] | None,
    **kwargs: Any,
) -> bool:
    """Matcher for ``deny-unauthorized-skill-tool``.

    Only evaluates ``invoke_skill``.  When the skill body declared no
    ``allowed_tools`` this matcher returns ``False`` (nothing to enforce, the
    historical behaviour is preserved).  When tools ARE declared, the
    ``authorized_tools`` set must be present and a set of strings; any
    mismatch raises ``ValueError``.  Because this policy is mandatory, a raise
    is turned into ``Decision.REFUSE`` by :meth:`PDP.decide` (fail-closed).
    """
    if action != "invoke_skill":
        return False

    state = process_state or {}
    declared = state.get("skill_allowed_tools")
    if not declared:
        return False

    authorized = state.get("authorized_tools")
    if not isinstance(authorized, (list, tuple, set, frozenset)):
        raise ValueError("authorized_tools missing for invoke_skill (fail-closed)")
    if not all(isinstance(tool, str) for tool in authorized):
        raise ValueError("authorized_tools missing for invoke_skill (fail-closed)")

    violations = sorted(set(declared) - set(authorized))
    if violations:
        raise ValueError(
            f"skill declares unauthorized tool(s): {', '.join(violations)}"
        )
    return False


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
_CANCEL_ACTIONS = frozenset({"cancel"})
_COMPENSATE_ACTIONS = frozenset({"compensate"})

DEFAULT_POLICIES: tuple[Policy, ...] = (
    Policy(
        name="permit-read-only",
        effect="permit",
        reason="read-only action is permitted",
        actions=_READ_ACTIONS,
        permit_outcome=_read_outcome,
    ),
    Policy(
        name="permit-cancel-run",
        effect="permit",
        reason="cancel stops the run; no further work will start",
        actions=_CANCEL_ACTIONS,
        permit_outcome=_cancel_outcome,
    ),
    Policy(
        name="permit-compensate-effects",
        effect="permit",
        reason="compensate reverses prior effects and requires separate approval",
        actions=_COMPENSATE_ACTIONS,
        permit_outcome=_compensate_outcome,
    ),
    Policy(
        name="permit-mutations-by-autonomy",
        effect="permit",
        reason="mutating action governed by the per-activity autonomy dial",
        actions=_MUTATING_ACTIONS,
        permit_outcome=_mutation_outcome,
    ),
    Policy(
        name="permit-host-api-call",
        effect="permit",
        reason="host API calls are permitted (confirmation gated at the call site)",
        actions=frozenset({"call_host_api"}),
        permit_outcome=_host_api_outcome,
    ),
    Policy(
        name="permit-proactive-delivery",
        effect="permit",
        reason=(
            "proactive delivery is a permitted host effect (P2-06e); the "
            "insight was already computed and the channel is routed at the "
            "call site, so stage 6 allows and stage 7 consent is skipped"
        ),
        actions=frozenset({"deliver"}),
        permit_outcome=_host_api_outcome,
    ),
    Policy(
        name="permit-skill-invocation",
        effect="permit",
        reason=(
            "skill invocation is a permitted orchestration effect (P3-10); "
            "the referenced process's own steps enforce their individual "
            "PDP/consent/grant gates when each activity runs, so stage 6 "
            "allows and stage 7 consent is skipped at the invoke seam"
        ),
        actions=frozenset({"invoke_skill"}),
        permit_outcome=_host_api_outcome,
    ),
    Policy(
        name="deny-unauthorized-skill-tool",
        effect="deny",
        reason="skill declares a tool the principal is not authorized to use (fail-closed)",
        mandatory=True,
        matcher=_deny_unauthorized_skill_tool,
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
        *,
        actor_chain: list[dict[str, Any]] | None = None,
        request_id: str = "",
        instance_id: str = "",
        host_user_id: str | None = None,
    ) -> PolicyDecision:
        """Return a decision for ``principal`` performing ``action``.

        Default-deny; forbid overrides permit; an evaluation error on a
        mandatory policy returns ``Decision.REFUSE`` (fail-closed). Every call
        is persisted.

        Attribution kwargs (``actor_chain`` / ``request_id`` / ``instance_id`` /
        ``host_user_id``) are audit-only (PEC-ID-1) and never influence matching.
        """
        objects = list(objects or [])
        attr = {
            "actor_chain": list(actor_chain or []),
            "request_id": request_id or "",
            "instance_id": instance_id or "",
            "host_user_id": host_user_id,
        }

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
                        **attr,
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
                **attr,
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
                **attr,
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
            **attr,
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
        actor_chain: list[dict[str, Any]] | None = None,
        request_id: str = "",
        instance_id: str = "",
        host_user_id: str | None = None,
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
            stage="pdp",
            process_state=process_state,
            budget=budget,
            actor_chain=list(actor_chain or []),
            request_id=request_id or "",
            instance_id=instance_id or "",
            host_user_id=host_user_id,
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
    *,
    actor_chain: list[dict[str, Any]] | None = None,
    request_id: str = "",
    instance_id: str = "",
    host_user_id: str | None = None,
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
        actor_chain=actor_chain,
        request_id=request_id,
        instance_id=instance_id,
        host_user_id=host_user_id,
    )
