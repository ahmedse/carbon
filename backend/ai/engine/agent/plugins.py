"""Tool/Workflow plugin registry — Sprint 12 (``ARCH_AI_EXTENSIBILITY``).

A *plugin* is a well-defined, specific host process exposed to the agent as a
single named tool (:class:`ToolPlugin`) or a declared multi-step process
(:class:`WorkflowPlugin`).

Growth model: **add a plugin class + one ``register_plugin()`` call** — no edit
to ``tools.py``'s static lists, no new Django app.

    from ai.engine.agent.plugins import ToolPlugin, register_plugin

    class CreateDQRule(ToolPlugin):
        name = "create_dq_rule"
        description = "..."
        input_schema = {...}
        async def execute(self, args, *, ctx):
            ...

    register_plugin(CreateDQRule())

Plugins never import Django ORM/views directly (RULE_18, RULE_20): they go
through ``ctx.host_api`` (JWT-authed, host RBAC applies) or the engine stores
passed via ``ctx.db``. Mutating plugins default to ``requires_confirmation=True``
(RULE_21).

Import style: this module lives under ``ai/engine/agent/`` and uses the
``ai.engine.*`` namespace like its siblings (``tools.py``, ``executor.py``).
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("pulse.agent.plugins")

# OpenAI function-call tool names MUST match this pattern (dots/other chars
# cause a 400 on every chat turn that ships the full tool catalog). Enforced
# here so a bad name fails fast at registration instead of at the LLM call.
TOOL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


# ── ToolContext ────────────────────────────────────────────────────────────


@dataclass
class ToolContext:
    """Dependencies injected into a plugin's ``execute()``.

    Every field is optional — a plugin degrades gracefully (fail-visible, never
    a fabricated answer) when a dependency is unavailable, mirroring the
    engine's existing convention for ``knowledge_store``/``executor``.
    """

    instance_id: str = ""
    conversation_id: str = ""
    host_user_id: str | None = None
    instance_config: dict | None = None
    db: Any = None            # async Store session (ai.store)
    host_api: Any = None      # HostAPIExecutor (JWT-authed) when available


# Current turn's ToolContext, set by the runtime before tool dispatch.
_CURRENT_CONTEXT: ContextVar[ToolContext | None] = ContextVar(
    "carbon_tool_context", default=None
)


def set_tool_context(ctx: ToolContext | None) -> None:
    """Set the ToolContext for the current async context (context-local)."""
    _CURRENT_CONTEXT.set(ctx)


def get_tool_context() -> ToolContext:
    """Return the active ToolContext, or an empty one if none was set."""
    return _CURRENT_CONTEXT.get() or ToolContext()


# ── ToolPlugin ABC ─────────────────────────────────────────────────────────


class ToolPlugin(ABC):
    """A well-defined, specific host process exposed to the agent as one tool."""

    #: Unique tool name (must not collide with a static tool or another plugin).
    name: str = ""
    #: What the process does + when the agent should use it.
    description: str = ""
    #: JSON Schema for the tool arguments.
    input_schema: dict = {"type": "object", "properties": {}}
    #: Mutations default to requiring confirmation (RULE_21).
    requires_confirmation: bool = True
    #: Optional CBAC capability gate, e.g. ``"dq:manage_rules"``.
    capability: str | None = None
    #: Bind to a domain app for scope/data-isolation (RULE_20).
    app_identifier: str | None = None
    #: User-facing "I can …" sentence that feeds ``list_my_capabilities`` (F5).
    #: Falls back to ``description`` when empty (G-C: truthful by construction).
    capability_claim: str = ""
    #: Whether the tool is exposed to the chat S3 planner. Sensitive or
    #: agent-mode-only tools set False (G-C: registry-driven chat surface).
    chat_visible: bool = True

    @abstractmethod
    async def execute(self, args: dict, *, ctx: ToolContext) -> dict:
        """Run the process and return a result dict (or ``{"error": ...}``)."""

    def to_definition(self) -> dict:
        """Serialize to the OpenAI function-call shape the agent consumes."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    def make_executor(self):
        """Return an ``async def(args: dict) -> dict`` matching the engine's
        tool-dispatch convention (``get_tool_executors`` values are called with
        a single ``args`` dict)."""

        async def _executor(args: dict) -> dict:
            ctx = get_tool_context()
            try:
                return await self.execute(args or {}, ctx=ctx)
            except Exception as exc:  # fail-visible, never raise into the turn
                logger.exception("Plugin %s failed: %s", self.name, exc)
                return {"error": str(exc)}

        return _executor


class WorkflowPlugin(ToolPlugin):
    """A composite process: an ordered list of steps, each referencing a tool.

    The default ``execute`` runs ``self.steps`` through the live tool executors
    (``get_tool_executors``), previewing by default (``dry_run``) and stopping
    when a step returns ``requires_confirmation``. Subclasses may override
    ``execute`` for bespoke orchestration.
    """

    #: Ordered steps: ``{"tool": "call_host_api", "args": {...}}``.
    steps: list[dict] = []
    #: Default preview; a real write only runs after explicit confirmation.
    dry_run: bool = True

    async def execute(self, args: dict, *, ctx: ToolContext) -> dict:
        # Lazy import — avoids a circular import with tools.py at module load.
        from ai.engine.agent.tools import get_tool_executors

        executors = await get_tool_executors()
        results: list[dict] = []
        for index, step in enumerate(self.steps):
            tool_name = step.get("tool", "")
            step_args = dict(step.get("args") or {})
            step_args.update(args)  # runtime args override declared defaults
            executor_fn = executors.get(tool_name)
            if executor_fn is None:
                return {
                    "error": f"Workflow {self.name!r}: unknown step tool {tool_name!r} at index {index}",
                    "dry_run": self.dry_run,
                }
            result = await executor_fn(step_args)
            results.append({"step": index, "tool": tool_name, "result": result})
            if isinstance(result, dict) and result.get("requires_confirmation"):
                # Stop-and-ask: surface the pending execution to the user.
                return {
                    "requires_confirmation": True,
                    "dry_run": self.dry_run,
                    "step": index,
                    "tool": tool_name,
                    "pending": result,
                    "steps": results,
                }
        return {"dry_run": self.dry_run, "steps": results}


# ── Registry ───────────────────────────────────────────────────────────────


_PLUGINS: list[ToolPlugin] = []


def register_plugin(plugin: ToolPlugin) -> None:
    """Register a plugin instance. Idempotent by ``name`` (first wins)."""
    if not isinstance(plugin, ToolPlugin):
        raise TypeError(f"register_plugin() expects a ToolPlugin, got {type(plugin)!r}")
    if not plugin.name:
        raise ValueError("ToolPlugin must define a non-empty 'name'")
    if not TOOL_NAME_PATTERN.fullmatch(plugin.name):
        raise ValueError(
            f"ToolPlugin name {plugin.name!r} must match "
            f"^[a-zA-Z0-9_-]{{1,64}}$ (no dots/spaces); OpenAI rejects otherwise"
        )
    if any(p.name == plugin.name for p in _PLUGINS):
        logger.warning("Plugin %r already registered; ignoring duplicate", plugin.name)
        return
    _PLUGINS.append(plugin)
    logger.info("Registered plugin %r (app=%s, confirm=%s)", plugin.name, plugin.app_identifier, plugin.requires_confirmation)


def _builtin_plugins() -> list[ToolPlugin]:
    """Import + instantiate built-in plugin modules (lazy, avoids cycles)."""
    # Built-ins are registered via register_plugin() at import time below; the
    # function exists so future app-package plugins can plug in here.
    return []


def load_plugins() -> tuple[list[dict], dict[str, object]]:
    """Build (definitions, executors) for all registered plugins.

    Dedup is by name with first-registration-wins; the *static* tool names take
    precedence at the ``tools.py`` merge site, so a plugin colliding with a
    static tool is simply shadowed there.
    """
    plugins = list(_PLUGINS) + _builtin_plugins()
    definitions: list[dict] = []
    executors: dict[str, object] = {}
    seen: set[str] = set()
    for plugin in plugins:
        if plugin.name in seen:
            logger.warning("Skipping plugin %r: duplicate name", plugin.name)
            continue
        seen.add(plugin.name)
        definitions.append(plugin.to_definition())
        executors[plugin.name] = plugin.make_executor()
    return definitions, executors


def registered_plugins() -> list[ToolPlugin]:
    """Return the currently-registered plugin instances (read-only view)."""
    return list(_PLUGINS)


def is_confirmation_tool(tool_name: str) -> bool:
    """True when a registered plugin gates its write behind user confirmation
    (``requires_confirmation=True`` — RULE_21).

    The execute/loop layers use this capability fact to distinguish a
    genuinely-staged mutation (which MUST return ``requires_confirmation`` or
    ``error``) from a read-only tool. A confirmation tool that returns
    ``null``/empty output is a phantom success and must fail honestly.
    """
    for p in _PLUGINS:
        if p.name == tool_name:
            return bool(p.requires_confirmation)
    return False


def chat_tool_names() -> frozenset[str]:
    """Names of registered plugins exposed to the chat planner (``chat_visible``).

    This is the G-C "freeze the spine, grow the periphery" seam: adding a new
    chat tool is a plugin registration — never an edit to ``tools.py`` or
    ``runner.py``.
    """
    return frozenset(p.name for p in _PLUGINS if p.chat_visible)


def capability_claims() -> list[dict]:
    """Registry-derived capability manifest — truthful by construction (F5).

    Returns one entry per plugin: ``{name, claim, requires_confirmation, kind}``
    where ``claim`` is ``capability_claim`` (or ``description`` when unset).
    This feeds ``list_my_capabilities``.
    """
    claims: list[dict] = []
    for p in _PLUGINS:
        claim = (p.capability_claim or "").strip() or (p.description or "").strip()
        claims.append({
            "name": p.name,
            "claim": claim,
            "requires_confirmation": bool(p.requires_confirmation),
            "kind": "workflow" if isinstance(p, WorkflowPlugin) else "tool",
        })
    return claims
