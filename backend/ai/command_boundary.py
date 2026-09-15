"""Command Boundary core — the single host-side seam for every host effect.

P2-06a.  Every host-effect (mutation or read-only action) flows through one
ordered, **fail-closed** pipeline of 14 stages.  Any stage failure returns
``Outcome(status="refused"|"failed")`` — never a silent pass, never a permit
when the stage could not prove eligibility.

This module is HOST-side: it may import ``ai.engine.ports``, ``ai.guards``,
``ai.protocol``, Django, and stdlib.  It MUST NOT be imported by anything under
``ai.engine/`` (the engine stays portable and depends only on the Protocol seam
in ``ai.engine.ports``).

Folded in (not called separately):

* ``ai.guards.GuardChain`` → stages 2/3/4:
    - ``ScopeGuard``      → stage 2 (scope exists + user_identifier)
    - ``AccessGuard``     → stage 3 (org-unit / module access)
    - ``DataIsolationGuard`` → stage 4 (domain-app isolation)
  plus ``DataIsolationGuard.sanitize_response`` + ``MutationGuard.sanitize_response``
  → stage 13 (response sanitization).
* ``ai.engine.agent.guardrails.HookPipeline`` hooks → stages 7/9/14:
    - ``consent_hook``   → stage 7 (unconfirmed mutation is refused)
    - ``budget_hook``    → stage 9 (over-budget is refused)
    - ``rate_limit_hook``→ stage 9 (warn, not refuse)
    - ``redaction_hook`` → stage 14 (confidential result redaction)

Decision logic is fully constructor-injected (ports + callables) so the boundary
runs offline with fakes/stubs and never hard-depends on the real PDP or ORM.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping, MutableMapping

from ai.engine.ports import (
    ActionOutcome,
    Clock,
    Decision,
    EventBus,
    LedgerSink,
    PolicyDecision,
    PolicyDecisionPoint,
    ProcessRegistry,
)
from ai.guards import AccessGuard, DataIsolationGuard, MutationGuard, ScopeGuard
from ai.protocol import Scope

logger = logging.getLogger("carbon.ai.command_boundary")

# ── The 14 ordered stages ──────────────────────────────────────────
STAGES: tuple[str, ...] = (
    "identity",            # 1  resolve principal
    "scope",               # 2  ScopeGuard — scope exists
    "contract",            # 3  declared tool/action + AccessGuard
    "validate",            # 4  params valid + DataIsolationGuard
    "state_eligibility",   # 5  allowed in current process state
    "pdp",                 # 6  PolicyDecisionPoint → Decision
    "consent",             # 7  confirmation gate (consent_hook)
    "grant",               # 8  business-approval gate (ApprovalGrant)
    "budget",              # 9  budget + rate-limit (budget_hook)
    "revision",            # 10 object revision matches
    "execute",             # 11 idempotent execution
    "persist_events",      # 12 ledger / event port
    "verify",              # 13 verify the effect (fail-closed)
    "outcome",             # 14 sanitize + redact, emit Outcome
)


# P3-11 — host-owned run-lifecycle actions with fixed grant semantics.
#
# ``cancel`` stops a run and starts no new work: it is a declared, governed
# action but must NEVER require a grant (a user can always stop their own run).
# ``compensate`` reverses prior effects: it must ALWAYS carry its own durable
# ``ApprovalGrant`` and must never be satisfiable by a ``cancel`` authorization.
#
# These are enforced here — not left to caller discipline — so the two actions
# can never be conflated. The capability string is the action-specific grant
# binding; the boundary refuses ``compensate`` without a matching grant.
LIFECYCLE_ACTIONS: dict[str, dict[str, Any]] = {
    "cancel": {"requires_grant": False, "capability": "run.cancel"},
    "compensate": {"requires_grant": True, "capability": "run.compensate"},
}


# ── Data shapes ────────────────────────────────────────────────────────────

@dataclass
class Command:
    """A single host effect to route through the boundary.

    ``identity/principal``, ``scope``, ``action/tool``, ``params``, ``objects``
    and ``idempotency_key`` are the core contract; the remaining fields feed the
    later stages (PDP, consent, budget, revision, isolation).
    """

    principal: str | None = None            # resolved identity (or resolve via scope)
    scope: Scope | None = None              # ai.protocol.Scope — mandatory
    action: str = ""                        # declared action name
    tool: str = ""                          # declared tool name
    params: dict[str, Any] = field(default_factory=dict)
    objects: list[str] = field(default_factory=list)
    requires_confirmation: bool = True      # fail-closed default: confirm by default
    confirmation_token: str | None = None
    idempotency_key: str | None = None

    # PDP inputs
    process_state: dict[str, Any] | None = None
    autonomy: str = "human_only"
    budget: dict[str, Any] | None = None

    # revision check (stage 10)
    expected_revision: Any = None           # value, or dict {object: revision}

    # grant check (stage 8, P3-06 business approval)
    requires_grant: bool = False            # fail-closed: False by default
    capability: str = ""                    # capability the effect falls under
    process_version: str = ""               # pins the process definition version
    capability_version: str = ""            # pins the capability version
    object_revisions: dict[str, Any] = field(default_factory=dict)  # {object_id: revision}
    evidence_digest: str = ""               # pins the evidence digest
    object_id: str = ""                     # generic object identity (testable standalone)
    object_type: str = ""                   # generic object kind
    process_instance: str = ""              # future FK → ProcessInstance (UUID string)

    # guard inputs (folded GuardChain)
    requested_org_units: list[str] | None = None
    requested_modules: list[str] | None = None
    table_names: list[str] | None = None

    # metadata
    instance_id: str = ""
    run_id: str | None = None
    host_user_id: str | None = None


@dataclass
class Outcome:
    """The confirmed outcome of a host action.

    ``status`` ∈ "executed" | "confirmed" | "refused" | "deferred" | "failed".
    """

    status: str = "refused"
    result: Any = None
    confirmation_token: str | None = None
    error: str | None = None
    event_ids: list[str] = field(default_factory=list)
    decision: Decision | None = None
    reason: str = ""
    policy_version: str | None = None
    stages: list[str] = field(default_factory=list)   # ordered stages that ran

    def to_action_outcome(self) -> ActionOutcome:
        """Bridge to the engine-facing ``ActionOutcome`` TypedDict shape."""
        return ActionOutcome(
            status=self.status,
            result=self.result,
            confirmation_token=self.confirmation_token,
            error=self.error,
            event_ids=self.event_ids,
        )


@dataclass
class BudgetVerdict:
    """Result of the folded ``budget_hook`` / ``rate_limit_hook`` stage."""

    allowed: bool = True
    reason: str = ""
    warn: str = ""
    flags: list[str] = field(default_factory=list)


# ── Type aliases for injectable decision callables ────────────────────────

Executor = Callable[[Command], Awaitable[Any]]
IdentityResolver = Callable[[Command], Awaitable[str]]
ParamsValidator = Callable[[dict[str, Any]], Awaitable[None]]
EligibilityChecker = Callable[[Command], Awaitable[bool]]
BudgetChecker = Callable[[Command], Awaitable[BudgetVerdict]]
RevisionResolver = Callable[[list[str]], Awaitable[Mapping[str, Any] | None]]
GrantResolver = Callable[[Command], Awaitable[Mapping[str, Any] | None]]
# Enqueues a durable human-approval task when a grant-required capability has no
# active grant yet. Returns the created task id, or ``None`` to fall back to the
# fail-closed refusal. Host-side seam (RULE_20 / ADR-0007) — engine never calls it.
TaskEnqueuer = Callable[[Command], Awaitable[str | None]]
Verifier = Callable[[Command, Any], Awaitable[None]]


# ── Default (fail-closed, offline) implementations ─────────────────────────

class _DefaultDenyPDP:
    """Default PDP: absence of a permit is a refuse (P2-07 default deny)."""

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
        return {
            "decision": Decision.REFUSE,
            "reason": "default deny: no PDP configured",
            "policy_version": "default",
        }


async def _default_identity(command: Command) -> str:
    if command.principal:
        return command.principal
    if command.scope is not None and command.scope.user_identifier:
        return command.scope.user_identifier
    raise ValueError("no principal and no scope.user_identifier")


async def _no_executor(command: Command) -> Any:
    raise RuntimeError("no executor configured for command boundary")


async def _noop_validator(params: dict[str, Any]) -> None:
    return None


async def _noop_verifier(command: Command, result: Any) -> None:
    return None


async def _default_revision(objects: list[str]) -> Mapping[str, Any] | None:
    return None  # cannot resolve → revision-constrained commands fail closed


async def _default_grant(command: Command) -> Mapping[str, Any] | None:
    return None  # no resolver configured → fail closed (never assume a grant)


async def _default_budget(command: Command) -> BudgetVerdict:
    budget = command.budget or {}
    if budget.get("budget_exceeded") or budget.get("exceeded"):
        return BudgetVerdict(
            allowed=False,
            reason="run token budget exceeded",
            flags=["budget_exceeded"],
        )
    remaining = budget.get("remaining")
    if remaining is not None and remaining < 500:
        return BudgetVerdict(
            allowed=True,
            warn=f"budget low: {remaining} tokens remaining",
            flags=["budget_low"],
        )
    return BudgetVerdict(allowed=True)


# ── The boundary ───────────────────────────────────────────────────────────

class CommandBoundary:
    """Routes every host effect through the 14 ordered, fail-closed stages.

    All decision inputs are injected; defaults are offline and fail-closed:
    default-deny PDP, empty tool catalog, no executor, no ledger.
    """

    def __init__(
        self,
        *,
        pdp: PolicyDecisionPoint | None = None,
        ledger: LedgerSink | None = None,
        event_bus: EventBus | None = None,
        process_registry: ProcessRegistry | None = None,
        executor: Executor | None = None,
        identity_resolver: IdentityResolver | None = None,
        tool_catalog: Mapping[str, Any] | None = None,
        params_validator: ParamsValidator | None = None,
        eligibility_checker: EligibilityChecker | None = None,
        budget_checker: BudgetChecker | None = None,
        revision_resolver: RevisionResolver | None = None,
        grant_resolver: GrantResolver | None = None,
        task_enqueuer: TaskEnqueuer | None = None,
        verifier: Verifier | None = None,
        idempotency_store: MutableMapping[str, Outcome] | None = None,
        redacted_tools: set[str] | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._pdp: PolicyDecisionPoint = pdp or _DefaultDenyPDP()
        self._ledger = ledger
        self._event_bus = event_bus
        self._process_registry = process_registry
        self._executor: Executor = executor or _no_executor
        self._identity_resolver: IdentityResolver = identity_resolver or _default_identity
        self._tool_catalog: Mapping[str, Any] = tool_catalog if tool_catalog is not None else {}
        self._params_validator: ParamsValidator = params_validator or _noop_validator
        self._eligibility_checker = eligibility_checker
        self._budget_checker: BudgetChecker = budget_checker or _default_budget
        self._revision_resolver: RevisionResolver = revision_resolver or _default_revision
        self._grant_resolver: GrantResolver = grant_resolver or _default_grant
        self._task_enqueuer: TaskEnqueuer | None = task_enqueuer
        self._verifier: Verifier = verifier or _noop_verifier
        self._idempotency_store: MutableMapping[str, Outcome] = (
            idempotency_store if idempotency_store is not None else {}
        )
        self._redacted_tools: set[str] = set(redacted_tools or ())
        self._clock = clock

    async def execute(self, command: Command) -> Outcome:
        """Run the 14 stages and return the fail-closed ``Outcome``."""
        stages: list[str] = []
        decision: Decision | None = None
        decision_reason = ""
        policy_version: str | None = None

        def refused(error: str) -> Outcome:
            return Outcome(status="refused", error=error, decision=decision,
                           reason=decision_reason, policy_version=policy_version,
                           stages=stages)

        def failed(error: str) -> Outcome:
            return Outcome(status="failed", error=error, decision=decision,
                           reason=decision_reason, policy_version=policy_version,
                           stages=stages)

        try:
            # ── Stage 1: identity ─────────────────────────────────────────
            stages.append("identity")
            try:
                principal = await self._identity_resolver(command)
            except Exception as exc:  # noqa: BLE001 — fail closed on identity
                return refused(f"identity: {exc}")

            # ── Stage 2: scope (ScopeGuard) ───────────────────────────────
            stages.append("scope")
            operation = command.action or command.tool or "command"
            try:
                ScopeGuard.validate(command.scope, operation)
            except ValueError as exc:
                return refused(str(exc))
            scope = command.scope  # narrowed: non-None after ScopeGuard

            # ── Stage 3: contract (declared) + AccessGuard ────────────────
            stages.append("contract")
            if not self._is_declared(command):
                return refused(
                    f"contract: tool/action '{command.tool or command.action}' "
                    f"is not declared in the tool catalog"
                )
            try:
                AccessGuard.validate(
                    scope, operation,
                    command.requested_org_units, command.requested_modules,
                )
            except PermissionError as exc:
                return refused(str(exc))

            # ── Stage 4: validate params + DataIsolationGuard ────────────
            stages.append("validate")
            try:
                await self._params_validator(command.params)
            except Exception as exc:  # noqa: BLE001 — invalid params refuse
                return refused(f"validate: {exc}")
            try:
                DataIsolationGuard.validate(scope, operation, command.table_names)
            except PermissionError as exc:
                return refused(str(exc))

            # ── Stage 5: state eligibility ────────────────────────────────
            stages.append("state_eligibility")
            try:
                if not await self._check_eligibility(command):
                    return refused(
                        "state_eligibility: action not allowed in the current process state"
                    )
            except Exception as exc:  # noqa: BLE001 — fail closed
                return refused(f"state_eligibility: {exc}")

            # ── Stage 6: PDP ──────────────────────────────────────────────
            stages.append("pdp")
            pdp_result = await self._decide(command, principal)
            decision = pdp_result.get("decision", Decision.REFUSE)
            decision_reason = pdp_result.get("reason", "")
            policy_version = pdp_result.get("policy_version")
            # C-F4a: an authorization *evaluation error* is an operational failure,
            # not a policy refusal — classify it as `failed` (still fail-closed: no
            # effect runs) so it is distinguishable from a default-deny in the
            # ledger, metrics, and user-facing copy.
            if pdp_result.get("evaluation_error"):
                return failed("authorization check could not be completed")
            if decision == Decision.REFUSE:
                return refused(decision_reason or "pdp: refused (default deny)")
            if decision == Decision.DEFER:
                return Outcome(status="deferred", error=decision_reason,
                               decision=decision, reason=decision_reason,
                               policy_version=policy_version, stages=stages)

            # ── Stage 7: consent / approval (consent_hook) ────────────────
            stages.append("consent")
            requires_confirmation = command.requires_confirmation or decision in (
                Decision.ALLOW_WITH_CONFIRMATION, Decision.ASK,
            )
            confirmed = bool(command.confirmation_token) or bool(
                command.params.get("_confirmed")
            )
            if requires_confirmation and not confirmed:
                return refused(
                    "consent: action requires confirmation but no confirmation_token "
                    "was supplied (fail-closed)"
                )

            # ── Stage 8: grant (business approval, P3-06) ───────────────
            # Strictly separate from authorization (stage 6 PDP) and consent
            # (stage 7): a PDP ALLOW does not waive the requirement for a
            # durable, human-minted ApprovalGrant when the capability declares
            # ``requires_grant``. Fail closed when no exact match exists.
            stages.append("grant")
            if self._command_requires_grant(command):
                if not command.capability:
                    command.capability = self._catalog_capability(command)
                try:
                    grant = await self._grant_resolver(command)
                except Exception as exc:  # noqa: BLE001 — fail closed on grant
                    return refused(f"grant: {exc}")
                if not grant:
                    if self._task_enqueuer is not None:
                        try:
                            task_id = await self._task_enqueuer(command)
                        except Exception as exc:  # noqa: BLE001 — fail closed
                            return refused(f"grant: inbox enqueue failed: {exc}")
                        if task_id:
                            return Outcome(
                                status="deferred",
                                result={"task_id": task_id},
                                error=(
                                    "grant: no active ApprovalGrant — "
                                    "deferred to human task inbox"
                                ),
                                decision=decision,
                                reason=decision_reason,
                                policy_version=policy_version,
                                stages=stages,
                            )
                    return refused(
                        "grant: no active, fully-matching ApprovalGrant (fail-closed)"
                    )

            # ── Stage 9: budget + rate-limit (budget_hook) ───────────────
            stages.append("budget")
            try:
                budget = await self._budget_checker(command)
            except Exception as exc:  # noqa: BLE001 — fail closed on budget
                return refused(f"budget: {exc}")
            if not budget.allowed:
                return refused(budget.reason or "budget: exceeded")

            # ── Stage 10: revision check ──────────────────────────────
            stages.append("revision")
            if command.expected_revision is not None:
                if not await self._revision_ok(command):
                    return refused("revision: object revision mismatch (fail-closed)")

            # ── Stage 11: execute (idempotent) ────────────────────────
            stages.append("execute")
            key = command.idempotency_key
            if key and key in self._idempotency_store:
                # Repeat of the same key is a no-op: replay the stored outcome.
                return self._idempotency_store[key]
            try:
                result = await self._executor(command)
            except Exception as exc:  # noqa: BLE001 — fail closed on execute
                return failed(f"execute: {exc}")

            # ── Stage 12: persist events (ledger / event port) ────────
            stages.append("persist_events")
            try:
                event_ids = await self._persist(
                    command, principal, result, decision, decision_reason,
                )
            except Exception as exc:  # noqa: BLE001 — fail-visible, not disruptive
                logger.warning("persist_events: %s", exc)
                event_ids = []

            # ── Stage 13: verify the effect (fail-closed) ────────────────
            stages.append("verify")
            try:
                await self._verifier(command, result)
            except Exception as exc:  # noqa: BLE001 — fail closed on verify
                return failed(f"verify: {exc}")

            # ── Stage 14: outcome (sanitize + redact, emit) ───────────
            stages.append("outcome")
            final_result = self._sanitize_result(scope, result, command.tool)
            status = "confirmed" if requires_confirmation else "executed"
            outcome = Outcome(
                status=status,
                result=final_result,
                confirmation_token=command.confirmation_token,
                event_ids=event_ids,
                decision=decision,
                reason=decision_reason,
                policy_version=policy_version,
                stages=stages,
            )
            if key:
                self._idempotency_store[key] = outcome
            return outcome

        except Exception as exc:  # noqa: BLE001 — top-level fail-closed net
            logger.exception("command boundary: unexpected failure")
            return failed(f"unexpected: {exc}")

    # ── Stage helpers ─────────────────────────────────────────────────────

    def _is_declared(self, command: Command) -> bool:
        return (command.tool in self._tool_catalog) or (
            command.action in self._tool_catalog
        )

    def _catalog_entry(self, command: Command) -> Any:
        """Return the tool-catalog entry for the command, if any.

        Uses membership (not truthiness) so a falsy-but-present entry (e.g. an
        empty ``dict`` declaration) is still returned.
        """
        if command.tool in self._tool_catalog:
            return self._tool_catalog[command.tool]
        if command.action in self._tool_catalog:
            return self._tool_catalog[command.action]
        return None

    def _command_requires_grant(self, command: Command) -> bool:
        """True when the command (or its declared catalog entry) needs a grant.

        Run-lifecycle actions (P3-11) are enforced absolutely: ``compensate``
        always requires a grant and ``cancel`` never does, regardless of what a
        caller or catalog entry might otherwise request — the two semantics
        must never be conflated.
        """
        action = command.action or command.tool
        lifecycle = LIFECYCLE_ACTIONS.get(action)
        if lifecycle is not None:
            return bool(lifecycle["requires_grant"])
        if command.requires_grant:
            return True
        entry = self._catalog_entry(command)
        if entry is None or isinstance(entry, bool):
            return False
        if hasattr(entry, "requires_grant"):
            return bool(entry.requires_grant)
        if isinstance(entry, Mapping):
            return bool(entry.get("requires_grant"))
        return False

    def _catalog_capability(self, command: Command) -> str:
        """Return the declared capability for the command's catalog entry."""
        action = command.action or command.tool
        lifecycle = LIFECYCLE_ACTIONS.get(action)
        if lifecycle is not None:
            return str(lifecycle["capability"])
        entry = self._catalog_entry(command)
        if entry is None or isinstance(entry, bool):
            return ""
        if hasattr(entry, "required_capability"):
            return entry.required_capability or ""
        if isinstance(entry, Mapping):
            return entry.get("required_capability") or ""
        return ""

    async def _decide(self, command: Command, principal: str) -> PolicyDecision:
        try:
            return await self._pdp.decide(
                principal=principal,
                action=command.action or command.tool,
                objects=command.objects,
                process_state=command.process_state,
                autonomy=command.autonomy,
                budget=command.budget,
                time=self._clock.utcnow() if self._clock else None,
            )
        except Exception:  # noqa: BLE001 — evaluation error → fail closed (P2-07)
            # C-F4a: an infra/evaluation error is an operational FAILURE, not a
            # policy denial. Stay fail-closed (REFUSE) but flag it so the boundary
            # classifies the outcome as `failed`, not `refused`, and ops can alert.
            logger.exception("pdp: evaluation error")
            return {
                "decision": Decision.REFUSE,
                "reason": "pdp: evaluation error (fail-closed)",
                "policy_version": None,
                "evaluation_error": True,
            }

    async def _check_eligibility(self, command: Command) -> bool:
        if self._eligibility_checker is not None:
            return bool(await self._eligibility_checker(command))
        state = command.process_state or {}
        if self._process_registry is not None and command.run_id:
            run = await self._process_registry.get_active_run(command.run_id)
            if run is not None:
                state = {**state, **(run.get("context") or {})}
        if state.get("blocked") or state.get("terminal"):
            return False
        return True

    async def _revision_ok(self, command: Command) -> bool:
        current = await self._revision_resolver(command.objects)
        if current is None:
            return False  # cannot resolve → fail closed
        expected = command.expected_revision
        if isinstance(expected, dict):
            return all(current.get(obj) == rev for obj, rev in expected.items())
        return all(current.get(obj) == expected for obj in command.objects)

    async def _persist(
        self,
        command: Command,
        principal: str,
        result: Any,
        decision: Decision | None,
        reason: str,
    ) -> list[str]:
        event_ids: list[str] = []
        if self._ledger is not None:
            row_id = await self._ledger.record_stage(
                turn_id=command.instance_id or "command",
                instance_id=command.instance_id or "command",
                conversation_id="",
                host_user_id=command.host_user_id
                or (command.scope.user_identifier if command.scope else None),
                stage="command_boundary",
                stage_index=0,
                payload={
                    "tool": command.tool,
                    "action": command.action,
                    "objects": command.objects,
                    "decision": decision.value if decision else None,
                    "result": result,
                },
                verdict="executed",
            )
            if row_id:
                event_ids.append(str(row_id))
        if self._event_bus is not None:
            await self._event_bus.publish(
                "command.executed",
                {
                    "tool": command.tool,
                    "action": command.action,
                    "principal": principal,
                    "objects": command.objects,
                    "decision": decision.value if decision else None,
                    "reason": reason,
                },
            )
        return event_ids

    def _sanitize_result(self, scope: Scope, result: Any, tool: str) -> Any:
        """Fold redaction_hook + MutationGuard/DataIsolationGuard response cleanup."""
        if tool in self._redacted_tools:
            return {"redacted": True, "message": "Confidential tool result redacted."}
        if not isinstance(result, dict):
            return result
        sanitized = DataIsolationGuard.sanitize_response(scope, result)
        sanitized = MutationGuard.sanitize_response(scope, sanitized)
        return sanitized


# ── Module-level entry point ───────────────────────────────────────────────

async def execute(
    command: Command, *, boundary: CommandBoundary | None = None
) -> Outcome:
    """Route one host effect through the 14-stage boundary."""
    if boundary is None:
        boundary = CommandBoundary()
    return await boundary.execute(command)


__all__ = [
    "STAGES",
    "LIFECYCLE_ACTIONS",
    "Command",
    "Outcome",
    "BudgetVerdict",
    "GrantResolver",
    "CommandBoundary",
    "execute",
]
