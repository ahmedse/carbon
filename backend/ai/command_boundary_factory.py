"""Production wiring for :class:`ai.command_boundary.CommandBoundary` (P2-06b).

Assembles the real host components — the default ``PDP``, the Django ledger
adapter, the static tool catalog, and a scope/principal identity resolver —
around the fail-closed boundary core built in P2-06a.  The per-tool host-effect
closure (``executor``) and any overrides are injected by the caller.

Host-side module: it MAY import Django, ``ai.pdp``, ``ai.adapters``,
``ai.command_boundary`` and ``ai.protocol``.  It MUST NOT be imported by
anything under ``ai.engine/`` except, lazily, by ``ai.engine.agent.tools``
(the single host dependency that tool is allowed — RULE_20 / ADR-0007).
"""

from __future__ import annotations

from typing import Any, Mapping

from ai.adapters.ledger import DjangoLedgerAdapter
from ai.command_boundary import Command, CommandBoundary
from ai.engine.ports import Clock
from ai.grant import resolve_grant
from ai.pdp import PDP
from ai.task_inbox import enqueue_inbox_task

# Static tool names the engine declares.  Kept as literal names here — NOT
# imported from ``ai.engine.agent.tools`` — so this module loads with no
# engine cycle (the engine stays portable).  ``call_host_api`` is the tool this
# factory is primarily wired for (P2-06b); the rest mirror
# ``STATIC_TOOL_EXECUTORS`` so stage 3 (contract) passes for any built-in tool.
_STATIC_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "call_host_api",
        "search_knowledge",
        "get_entity_details",
        "inspect_case",
        "navigate_to",
        "open_entity",
        "learn_fact",
        "forget_fact",
        "ask_clarification",
        "run_ops_workflow",
        "draft_skill",
        "invoke_skill",
        # P3-11 run-lifecycle actions: declared so stage 3 (contract) passes.
        "cancel",
        "compensate",
    }
)

# P3-11 — declaration shape for run-lifecycle actions. ``cancel`` needs no
# grant; ``compensate`` carries its own capability + ``requires_grant`` so the
# boundary's grant stage (stage 8) gates it independently of ``cancel``.
_LIFECYCLE_TOOL_DECLARATIONS: dict[str, dict[str, Any]] = {
    "cancel": {"requires_grant": False, "required_capability": "run.cancel"},
    "compensate": {"requires_grant": True, "required_capability": "run.compensate"},
}


async def _identity_resolver(command: Command) -> str:
    """Mirror the boundary's default identity resolution (module-private there).

    ``command.principal`` wins; otherwise fall back to
    ``command.scope.user_identifier``; otherwise fail so stage 1 refuses.
    """
    if command.principal:
        return command.principal
    if command.scope is not None and command.scope.user_identifier:
        return command.scope.user_identifier
    raise ValueError("no principal and no scope.user_identifier")


def get_command_boundary(
    db,
    *,
    executor=None,
    tool_catalog: Mapping[str, Any] | None = None,
    pdp=None,
    ledger=None,
    grant_resolver=None,
    clock: Clock | None = None,
) -> CommandBoundary:
    """Build a wired, fail-closed command boundary.

    ``db`` is only used to construct the real ``DjangoLedgerAdapter`` when no
    ``ledger`` override is supplied; pass ``ledger=...`` in tests to avoid any
    database access.  ``tool_catalog`` defaults to the static tool names;
    ``pdp`` defaults to the real ``PDP()`` (default-deny + the permit policies
    declared in ``ai.pdp.DEFAULT_POLICIES``).
    """
    if pdp is None:
        pdp = PDP()
    if ledger is None:
        ledger = DjangoLedgerAdapter(db)
    if tool_catalog is None:
        tool_catalog = {
            name: _LIFECYCLE_TOOL_DECLARATIONS.get(name, True)
            for name in _STATIC_TOOL_NAMES
        }

    return CommandBoundary(
        pdp=pdp,
        ledger=ledger,
        executor=executor,
        identity_resolver=_identity_resolver,
        tool_catalog=tool_catalog,
        grant_resolver=grant_resolver if grant_resolver is not None else resolve_grant,
        # Human-task-inbox seam (P3-09): a grant-required capability with no
        # active grant is deferred to a durable approval task instead of a bare
        # refusal.  Returns the task id, or refuses if enqueueing fails.
        task_enqueuer=enqueue_inbox_task,
        clock=clock,
    )
