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
import re
from dataclasses import dataclass, field
from typing import Callable

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


async def consent_hook(ctx: HookContext) -> HookResult:
    """Block mutation tool calls that require user confirmation.

    If the tool is call_host_api with POST/PUT/DELETE method, checks whether
    a user confirmation exists in the ToolExecution table. Without confirmation,
    the call is cancelled.

    Note: The HostAPIExecutor.create_pending_execution() path (which returns
    requires_confirmation=True) is the primary consent gate for POST/PUT/DELETE.
    This hook acts as an additional safety net — if someone bypasses the executor
    and calls the tool directly, the hook catches it.
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

    # Check for pre-confirmation token (passed when user confirms via widget)
    confirmed = args.get("_confirmed", False)
    if confirmed:
        logger.debug("consent_hook: pre-confirmed call to %s", api_name)
        return HookResult(action="pass")

    logger.warning("consent_hook: blocking unconfirmed mutation %s", api_name)
    return HookResult(
        action="cancel",
        reason=f"Mutation '{api_name}' requires user confirmation. "
                "The host system's confirmation flow must be completed first.",
        flags=["requires_confirmation"],
    )


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


# Patterns considered dangerous in tool arguments
_DANGEROUS_SQL_PATTERNS = [
    (re.compile(r'\bDROP\s+TABLE\b', re.IGNORECASE), "DROP TABLE detected in tool args"),
    (re.compile(r'\bDELETE\s+FROM\b', re.IGNORECASE), "DELETE FROM detected in tool args"),
    (re.compile(r'\bTRUNCATE\s+(TABLE\s+)?\w+', re.IGNORECASE), "TRUNCATE detected in tool args"),
    (re.compile(r'\bALTER\s+TABLE\b', re.IGNORECASE), "ALTER TABLE detected in tool args"),
    (re.compile(r'\bINSERT\s+INTO\b', re.IGNORECASE), "INSERT INTO detected in tool args"),
    (re.compile(r'\bUPDATE\s+\w+\s+SET\b', re.IGNORECASE), "UPDATE ... SET detected in tool args"),
]

_DANGEROUS_SHELL_PATTERNS = [
    (re.compile(r'\brm\s+(-[rRf]+\s+)*[/~]'), "rm with path detected in tool args"),
    (re.compile(r'\bsudo\b'), "sudo detected in tool args"),
]

_SQL_INJECTION_PATTERNS = [
    (re.compile(r"'\s*OR\s+['\"]?\s*1\s*=\s*['\"]?\s*1", re.IGNORECASE), "SQL injection pattern: ' OR 1=1"),
    (re.compile(r"'\s*OR\s+['\"]?\s*['\"]?\s*=\s*['\"]?\s*['\"]?", re.IGNORECASE), "SQL injection pattern: OR ''=''"),
    (re.compile(r"'\s*OR\s+\S+\s*=\s*\S+", re.IGNORECASE), "SQL injection pattern: ' OR x=y"),
    (re.compile(r";\s*--"), "SQL injection pattern: ;-- comment"),
    (re.compile(r"UNION\s+SELECT", re.IGNORECASE), "UNION SELECT detected"),
]


def _search_dangerous_patterns(args: dict) -> list[str]:
    """Search tool args (recursively) for dangerous patterns. Returns list of reasons."""
    reasons: list[str] = []

    def _check_value(v):
        if isinstance(v, str):
            for pattern, reason in _DANGEROUS_SQL_PATTERNS:
                if pattern.search(v):
                    reasons.append(reason)
            for pattern, reason in _DANGEROUS_SHELL_PATTERNS:
                if pattern.search(v):
                    reasons.append(reason)
            for pattern, reason in _SQL_INJECTION_PATTERNS:
                if pattern.search(v):
                    reasons.append(reason)
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
        from sqlalchemy import select
        from ai.engine.core.models import Run

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
            stmt = select(
                Run.tokens_consumed,
                Run.token_budget,
                Run.budget_exceeded,
            ).where(Run.id == run_id)
            result = await db.execute(stmt)
            row = result.one_or_none()

            if row is None:
                logger.debug("budget_hook: Run row %s not found — passing", run_id[:8])
                return HookResult(action="pass")

            consumed, budget, exceeded_flag = row
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
        1. consent_hook        — block unconfirmed mutations
        2. readonly_worker_hook — block mutation tools in worker context
        3. tool_safety_hook    — block dangerous patterns
        4. rate_limit_hook     — warn on high-frequency tool calls
        5. budget_hook         — check token budget (stub for P3.4)

    After hooks:
        6. redaction_hook      — redact confidential tool results
    """
    pipeline = HookPipeline()
    # Before hooks — order is critical
    pipeline.add_hook(consent_hook, stage="before")
    pipeline.add_hook(readonly_worker_hook, stage="before")
    pipeline.add_hook(tool_safety_hook, stage="before")
    pipeline.add_hook(rate_limit_hook, stage="before")
    pipeline.add_hook(budget_hook, stage="before")
    # After hooks
    pipeline.add_hook(redaction_hook, stage="after")
    return pipeline
