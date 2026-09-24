"""
Guardrail hooks — executable interceptors on every tool call.

Hooks fire in a defined pipeline: before_tool_call hooks run first (can block),
then the tool executes, then after_tool_call hooks run (can redact).

Hook signature:
    async def hook(ctx: HookContext) -> HookResult

HookResult.action: "pass" | "warn" | "redirect" | "cancel" | "redact"

P3.3: Unified guardrail pipeline — replaces scattered consent, redaction,
rate-limiting, and safety checks with a single ordered hook chain.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Callable

from ai.engine.agent.surface import Surface
from ai.engine.core.config import get_settings
from ai.engine.core.exceptions import ToolExecutionError

logger = logging.getLogger("pulse.agent.guardrails")

# ── In-memory rate-limit tracker (per-process, not persisted) ─────────────
_rate_counter: dict[str, dict[str, int]] = {}  # run_id → {tool_name → count}


# ── Dataclasses ────────────────────────────────────────────────────────────


@dataclass
class HookContext:
    """Context passed to every guardrail hook."""
    tool_name: str
    tool_args: dict
    instance_id: str
    host_user_id: str | None = None
    run_id: str | None = None
    step_id: str | None = None
    agent_role: str = "orchestrator"  # which agent is making this call
    is_worker: bool = False           # True if called from a worker subagent
    db: object | None = None          # P3.4: optional async session for budget_hook
    instance_config: dict | None = None  # per-instance YAML config for guardrail overrides
    # ADR-0046 / RULE_35 — where this tool call runs. A ``Surface`` (or a
    # legacy name it resolves) decides whether a mutation may stage.
    # ``None`` means *unset*, not Chat: ``Surface.resolve`` consults
    # ``process_mode`` first and only then fails closed to ``chat.ask``.
    surface: "str | Surface | None" = None
    # Utterance for locale-aware handoff copy (optional).
    user_message: str = ""
    # Structured process dial from transport metadata (ask / plan / agent).
    process_mode: str = ""


@dataclass
class HookResult:
    """Result of a guardrail hook.

    action values:
        "pass"     — allow the call to proceed
        "warn"     — allow but log a flag
        "redirect" — modify the tool args before execution
        "cancel"   — block the call with a reason
        "redact"   — modify the result after execution
    """
    action: str                    # "pass" | "warn" | "redirect" | "cancel" | "redact"
    reason: str = ""               # human-readable explanation
    modified_args: dict | None = None  # set when action="redirect"
    modified_result: dict | None = None  # set when action="redact"
    flags: list[str] = field(default_factory=list)  # e.g. ["over_rate_limit", "unusual_args"]
    payload: dict | None = None    # structured handoff / cancel details (ADR-0046)

# ── Hook Pipeline ──────────────────────────────────────────────────────────


class HookPipeline:
    """Ordered pipeline of guardrail hooks.

    Usage::

        pipeline = HookPipeline()
        pipeline.add_hook(consent_hook, stage="before")
        pipeline.add_hook(rate_limit_hook, stage="before")
        pipeline.add_hook(redaction_hook, stage="after")

        # Before tool call
        result = await pipeline.run_before(ctx)
        if result.action == "cancel":
            raise ToolExecutionError(result.reason)
        if result.action == "redirect":
            args = result.modified_args  # use modified args

        # After tool call
        result = await pipeline.run_after(ctx, raw_result)
        if result.action == "redact":
            final_result = result.modified_result
    """

    def __init__(self):
        self._before_hooks: list[Callable] = []
        self._after_hooks: list[Callable] = []

    def add_hook(self, hook: Callable, stage: str = "before"):
        """Register a hook. stage: 'before' or 'after'."""
        if stage == "before":
            self._before_hooks.append(hook)
        elif stage == "after":
            self._after_hooks.append(hook)
        else:
            raise ValueError(f"Unknown hook stage: {stage!r} — must be 'before' or 'after'")

    async def run_before(self, ctx: HookContext) -> HookResult:
        """Run all before-hooks in order. First non-pass result wins (short-circuit)."""
        for hook in self._before_hooks:
            try:
                result = await hook(ctx)
            except Exception as exc:
                logger.exception("Before-hook %s crashed: %s", hook.__name__, exc)
                continue
            if result.action != "pass":
                logger.debug(
                    "Guardrail before-hook: %s → %s  tool=%s  reason=%s",
                    hook.__name__, result.action, ctx.tool_name, result.reason,
                )
                return result
        return HookResult(action="pass")

    async def run_after(self, ctx: HookContext, raw_result: dict) -> HookResult:
        """Run all after-hooks in order. Last redact wins (cumulative)."""
        final = HookResult(action="pass")
        for hook in self._after_hooks:
            try:
                # After-hooks receive the raw result for inspection
                # We pass it through ctx so hooks can access it
                ctx_with_result = HookContext(
                    tool_name=ctx.tool_name,
                    tool_args={**ctx.tool_args, "_raw_result": raw_result},
                    instance_id=ctx.instance_id,
                    host_user_id=ctx.host_user_id,
                    run_id=ctx.run_id,
                    step_id=ctx.step_id,
                    agent_role=ctx.agent_role,
                    is_worker=ctx.is_worker,
                    db=ctx.db,
                    instance_config=ctx.instance_config,
                    surface=ctx.surface,
                    user_message=ctx.user_message,
                    process_mode=ctx.process_mode,
                )
                result = await hook(ctx_with_result)
            except Exception as exc:
                logger.exception("After-hook %s crashed: %s", hook.__name__, exc)
                continue
            if result.action in ("redact", "warn"):
                final = result
                logger.debug(
                    "Guardrail after-hook: %s → %s  tool=%s",
                    hook.__name__, result.action, ctx.tool_name,
                )
        return final


# ── Built-in Hooks ─────────────────────────────────────────────────────────


async def chat_surface_hook(ctx: HookContext) -> HookResult:
    """ADR-0046 / G2 — Chat never stages host writes.

    On Chat surfaces, cancel host mutations / DQ creates before
    ``consent_hook`` / the executor can create ``pending_exec``. Memory
    (`learn_fact`) remains allowed. Agent surfaces pass through.

    ``plan_task`` on the Plan dial is not a special case: ``chat.plan`` is a
    drafting surface, so the tool is simply not a host mutation there. The
    surface is resolved once from ``surface`` + ``process_mode`` so the copy
    names the dial the user can actually see.

    The cancel carries a structured ``payload`` (``chat_handoff``) so the
    turn layer can emit Open-in-Agent / Open-My CTAs instead of a dead
    Confirm banner.
    """
    from ai.engine.agent.chat_surface import (
        build_chat_handoff_result,
        is_host_mutation_tool,
    )
    from ai.engine.agent.surface import Surface

    surface = Surface.resolve(
        ctx.surface,
        process_mode=ctx.process_mode,
        user_message=str(ctx.user_message or ""),
    )
    if surface.may_host_mutate:
        return HookResult(action="pass")

    tool = (ctx.tool_name or "").strip()
    if not is_host_mutation_tool(ctx.tool_name, ctx.tool_args, surface=surface):
        return HookResult(action="pass")

    # Payload carries internal reason + product copy; HookResult.reason is
    # L0 product text only (RULE_23 — never ADR/G2 jargon).
    handoff = build_chat_handoff_result(
        ctx.tool_name,
        ctx.tool_args,
        user_message=str(ctx.user_message or ""),
        surface=surface,
    )
    dial = surface.dial_label_en
    if tool in {"plan_task", "approve_plan", "edit_plan"}:
        reason = (
            "Plans are approved in Agent — open the Tasks panel."
            if surface is Surface.CHAT_PLAN
            else "Ask mode doesn’t create tasks — switch to Plan to draft one."
        )
    else:
        reason = (
            f"This change can’t be submitted in {dial} — use Agent or My."
        )
    return HookResult(
        action="cancel",
        reason=reason,
        flags=["chat_no_host_mutation"],
        payload=handoff,
    )


async def consent_hook(ctx: HookContext) -> HookResult:
    """Guard the consent BYPASS — never the propose→confirm path itself.

    On **Agent/plan** surfaces, ``HostAPIExecutor.create_pending_execution()``
    is the consent gate: a non-GET ``call_host_api`` STAGES a pending
    execution and returns ``requires_confirmation``. The tool call IS the
    proposal.

    On **Chat** surfaces, ``chat_surface_hook`` runs first and cancels host
    mutations before this hook — Chat must not stage (ADR-0046 / G2). Do not
    "fix" Chat by enabling Confirm for ``call_host_api``.

    What this hook still guards: a caller ASSERTING consent it does not have
    — ``_confirmed=True`` with no confirmation token or execution id —
    since that skips staging and executes for real. Worker subagents are
    handled separately by ``readonly_worker_hook``.
    """
    if ctx.tool_name != "call_host_api":
        return HookResult(action="pass")

    args = ctx.tool_args
    api_name = args.get("api_name", "")

    # Only check mutations — GET requests pass through
    # The method is derived from api_name via the executor catalog, so we
    # check args for mutation indicators (body present, or explicit method override)
    method = args.get("_method", "").upper()  # explicit override (rare)
    has_body = bool(args.get("body"))
    explanation = args.get("explanation", "")

    # If it looks like a mutation (has body or POST/PUT/DELETE pattner in explanation)
    is_likely_mutation = has_body or method in ("POST", "PUT", "DELETE", "PATCH")

    if not is_likely_mutation:
        return HookResult(action="pass")

    # Claimed consent must be backed by a token / staged execution id.
    if args.get("_confirmed"):
        token = args.get("_confirmation_token") or args.get("_execution_id")
        if token:
            logger.debug("consent_hook: confirmed call to %s", api_name)
            return HookResult(action="pass")
        logger.warning(
            "consent_hook: blocking unverified _confirmed on %s", api_name,
        )
        return HookResult(
            action="cancel",
            reason=(
                f"'{api_name}' was marked confirmed without a confirmation "
                "token. Nothing was submitted."
            ),
            flags=["unverified_confirmation"],
        )

    # Normal path: let it through to the executor, which stages a pending
    # execution instead of executing. Cancelling here is what left the user
    # with a mutation they could never approve.
    return HookResult(action="pass", flags=["stages_for_confirmation"])


# Worker-safe tool names (read-only operations)
_READONLY_TOOLS = frozenset({
    "search_knowledge",
    "get_entity_details",
    "query_knowledge_graph",
    "get_schema_info",
    "get_relationship_info",
    "get_table_profile",
})


async def readonly_worker_hook(ctx: HookContext) -> HookResult:
    """Block mutation tools when called from a worker subagent.

    Workers are for read-heavy, parallelizable work only (ADR-001).
    This includes blocking call_host_api when it looks like a mutation.
    """
    if not ctx.is_worker:
        return HookResult(action="pass")

    tool_name = ctx.tool_name

    # If it's explicitly a read-only tool, pass immediately
    if tool_name in _READONLY_TOOLS:
        return HookResult(action="pass")

    # call_host_api needs deeper inspection
    if tool_name == "call_host_api":
        args = ctx.tool_args
        has_body = bool(args.get("body"))
        method = args.get("_method", "").upper()
        is_mutation = has_body or method in ("POST", "PUT", "DELETE", "PATCH")

        if is_mutation:
            logger.warning(
                "readonly_worker_hook: worker attempted mutation %s",
                args.get("api_name", "?"),
            )
            return HookResult(
                action="cancel",
                reason=(
                    f"Workers are read-only (ADR-001). "
                    f"Tool '{tool_name}' with mutation args is not allowed in worker context."
                ),
                flags=["worker_mutation_blocked"],
            )

    # For any other non-readonly tool, allow it — the worker has a filtered tool set
    return HookResult(action="pass")


async def redaction_hook(ctx: HookContext) -> HookResult:
    """Redact results from confidential API endpoints after execution.

    Merges the global GUARDRAIL_REDACTED_TOOLS config with per-instance
    guardrail.redacted_tools from the instance YAML. Both are JSON lists.
    """
    settings = get_settings()

    # ── Global default ────────────────────────────────────────────────
    try:
        redacted_tools: list[str] = json.loads(settings.GUARDRAIL_REDACTED_TOOLS)
    except (json.JSONDecodeError, TypeError):
        logger.warning("redaction_hook: invalid GUARDRAIL_REDACTED_TOOLS JSON; skipping")
        return HookResult(action="pass")

    # ── Per-instance override (merged, not replaced) ──────────────────
    instance_cfg = ctx.instance_config or {}
    guardrail_cfg = instance_cfg.get("guardrail", {})
    instance_redacted = guardrail_cfg.get("redacted_tools", [])
    if isinstance(instance_redacted, list):
        redacted_tools = list(set(redacted_tools + instance_redacted))

    # ── Per-instance redaction message (config-driven) ─────────────────
    default_msg = (
        "This data contains proprietary details that cannot be shared directly. "
        "Direct the user to the relevant detail page in the platform's UI for "
        "visual analysis instead."
    )
    redaction_message = guardrail_cfg.get("redaction_message", default_msg)

    if ctx.tool_name not in redacted_tools:
        return HookResult(action="pass")

    # Check if the tool was actually called with the redacted api_name
    api_name = ctx.tool_args.get("api_name", "")
    if api_name in redacted_tools:
        logger.info("redaction_hook: redacting result for %s", api_name)
        return HookResult(
            action="redact",
            reason=f"Confidential tool '{api_name}' result redacted",
            modified_result={
                "redacted": True,
                "message": redaction_message,
            },
            flags=["redacted_confidential"],
        )

    return HookResult(action="pass")


async def rate_limit_hook(ctx: HookContext) -> HookResult:
    """Warn when a tool is called too many times in a single run.

    Tracks per-(run_id, tool_name) call counts in an in-memory dict.
    Threshold controlled by GUARDRAIL_MAX_TOOL_CALLS_PER_RUN config.
    """
    settings = get_settings()
    max_calls = settings.GUARDRAIL_MAX_TOOL_CALLS_PER_RUN

    run_id = ctx.run_id or "_no_run"
    tool_name = ctx.tool_name

    if run_id not in _rate_counter:
        _rate_counter[run_id] = {}

    count = _rate_counter[run_id].get(tool_name, 0) + 1
    _rate_counter[run_id][tool_name] = count

    if count > max_calls:
        logger.warning(
            "rate_limit_hook: tool=%s called %d times (limit=%d) in run=%s",
            tool_name, count, max_calls, run_id[:8],
        )
        return HookResult(
            action="warn",
            reason=f"Tool '{tool_name}' called {count} times (limit: {max_calls})",
            flags=["high_frequency", f"calls_{count}"],
        )

    return HookResult(action="pass")


def _search_dangerous_patterns(args: dict) -> list[str]:
    """Search tool args (recursively) for dangerous patterns. Returns list of reasons."""
    from ai.engine.core.danger_scan import scan_tool_args_danger

    reasons: list[str] = []

    def _check_value(v):
        if isinstance(v, str):
            reasons.extend(scan_tool_args_danger(v))
        elif isinstance(v, dict):
            for sv in v.values():
                _check_value(sv)
        elif isinstance(v, list):
            for item in v:
                _check_value(item)

    for value in args.values():
        _check_value(value)

    return reasons


async def tool_safety_hook(ctx: HookContext) -> HookResult:
    """Block known-dangerous operations in tool arguments.

    Checks for:
    - DROP TABLE, DELETE FROM, TRUNCATE, ALTER TABLE, INSERT INTO, UPDATE ... SET
    - rm -rf, sudo
    - SQL injection heuristics (' OR 1=1, '; --, UNION SELECT)
    """
    args = ctx.tool_args
    dangerous = _search_dangerous_patterns(args)

    if dangerous:
        logger.warning(
            "tool_safety_hook: BLOCKED tool=%s reasons=%s",
            ctx.tool_name, dangerous,
        )
        return HookResult(
            action="cancel",
            reason=f"Potentially destructive operation blocked: {'; '.join(dangerous)}",
            flags=["safety_blocked"] + [f"pattern:{r[:40]}" for r in dangerous],
        )

    return HookResult(action="pass")


async def budget_hook(ctx: HookContext) -> HookResult:
    """Check if the current run's token budget is exceeded (P3.4).

    Reads from the Run row in the DB: if budget_exceeded is already set,
    cancel the tool call. If remaining budget is critically low (<500 tokens),
    warn so the agent can produce a fallback.
    """
    settings = get_settings()

    if not settings.GUARDRAIL_BUDGET_ENFORCEMENT:
        return HookResult(action="pass")

    run_id = ctx.run_id
    if not run_id:
        logger.debug("budget_hook: no run_id in context — passing")
        return HookResult(action="pass")

    # Read current budget state from Run row
    try:
        from ai.engine.core.models import Run
        from ai.engine.core.query import first

        # Use the context's db session if available; otherwise get a fresh one
        if ctx.db is not None:
            db = ctx.db
            own_db = False
        else:
            from ai.engine.core.database import get_session_factory
            session_factory = get_session_factory()
            db = session_factory()
            own_db = True

        try:
            run = first(await db.select(Run, ("id", run_id)))

            if run is None:
                logger.debug("budget_hook: Run row %s not found — passing", run_id[:8])
                return HookResult(action="pass")

            consumed = run.tokens_consumed
            budget = run.token_budget
            exceeded_flag = run.budget_exceeded
            effective_budget = budget if budget is not None else settings.GUARDRAIL_MAX_TOKENS_PER_RUN

            if exceeded_flag:
                logger.warning(
                    "budget_hook: budget exceeded for run=%s consumed=%d budget=%d",
                    run_id[:8], consumed or 0, effective_budget,
                )
                return HookResult(
                    action="cancel",
                    reason="Run token budget exceeded",
                    flags=["budget_exceeded"],
                )

            remaining = effective_budget - (consumed or 0)
            if remaining < 500:
                logger.warning(
                    "budget_hook: budget critically low run=%s remaining=%d",
                    run_id[:8], remaining,
                )
                return HookResult(
                    action="warn",
                    reason=f"Budget low: {remaining} tokens remaining",
                    flags=["budget_low"],
                )

            logger.debug(
                "budget_hook: pass run=%s consumed=%d/%d remaining=%d",
                run_id[:8], consumed or 0, effective_budget, remaining,
            )
        finally:
            if own_db:
                await db.close()
    except Exception:
        logger.exception("budget_hook: failed to read Run row — passing")

    return HookResult(action="pass")


# ── Pipeline Factory ──────────────────────────────────────────────────────


def build_default_pipeline() -> HookPipeline:
    """Create the default hook pipeline with all built-in guards.

    Before hooks (execution order matters):
        1. chat_surface_hook    — Chat: no host mutation staging (ADR-0046)
        2. consent_hook         — block unverified consent bypass
        3. readonly_worker_hook — block mutation tools in worker context
        4. tool_safety_hook     — block dangerous patterns
        5. rate_limit_hook      — warn on high-frequency tool calls
        6. budget_hook          — check token budget (stub for P3.4)

    After hooks:
        7. redaction_hook       — redact confidential tool results
    """
    pipeline = HookPipeline()
    # Before hooks — order is critical
    pipeline.add_hook(chat_surface_hook, stage="before")
    pipeline.add_hook(consent_hook, stage="before")
    pipeline.add_hook(readonly_worker_hook, stage="before")
    pipeline.add_hook(tool_safety_hook, stage="before")
    pipeline.add_hook(rate_limit_hook, stage="before")
    pipeline.add_hook(budget_hook, stage="before")
    # After hooks
    pipeline.add_hook(redaction_hook, stage="after")
    return pipeline
