"""S5 — Execute witness (real parallel tool dispatch).

S3 produces tool_calls; S5 executes them. Independent calls run in parallel
via asyncio.gather. Results are streamed to the widget as they complete.

Wave 8A: Broadcasts tool.started/completed/failed events to the studio
event stream so the ActivityFeed can show what the agent *did*.
"""
import asyncio
import json
import logging
import time

from ai.engine.cognition.turn.witnesses import ExecutionResult

logger = logging.getLogger("pulse.cognition.turn.execute")

# Lazy import — avoids circular dependency with notifier
broadcast_run_event = None


class ExecuteWitness:
    """Parallel tool dispatch + streaming. Executes tool calls from S3 draft."""

    def __init__(self, executor=None, hook_pipeline=None, hook_ctx_defaults: dict | None = None, run_id: str = "", instance_id: str = ""):
        self.executor = executor  # optional override for host API executor
        self.hook_pipeline = hook_pipeline  # P3.3: guardrail hook pipeline
        self.hook_ctx_defaults = hook_ctx_defaults or {}  # P3.3: default HookContext fields
        self.run_id = run_id  # Wave 8A: for tool event broadcasting
        self.instance_id = instance_id  # Wave 8A: for scoped studio broadcast

    async def execute(
        self,
        text: str = "",
        tool_calls: list[dict] | None = None,
        stream_callback=None,
        progress_callback=None,
        agent_role: str | None = None,
        is_worker: bool | None = None,
    ) -> ExecutionResult:
        """Execute tool calls from S3 draft, streaming text as it completes.

        Args:
            text: Final response text from draft/critic (for streaming to widget).
            tool_calls: Tool calls from S3 draft result. None or empty list = text-only.
            stream_callback: Async fn(delta: str) — called for each text chunk.
            progress_callback: Async fn(message: str) — called for progress updates.
            agent_role: Optional per-call agent role override (threaded into HookContext).
            is_worker: Optional per-call worker flag override (threaded into HookContext).
        """
        ctx_defaults = dict(self.hook_ctx_defaults or {})
        if agent_role is not None:
            ctx_defaults["agent_role"] = agent_role
        if is_worker is not None:
            ctx_defaults["is_worker"] = is_worker

        t0 = time.monotonic()
        per_tool_latency_ms: dict[str, float] = {}
        completed_tools: list[dict] = []
        tool_calls = tool_calls or []

        # ── Parallel dispatch of independent tool calls ──────────────────
        if tool_calls:
            independent, dependent = _split_by_dependencies(tool_calls)

            # Execute independent calls in parallel with asyncio.gather
            if independent:
                if progress_callback:
                    try:
                        await progress_callback(f"Running {len(independent)} tool(s)…")
                    except Exception:
                        pass

                # Wave 8A: broadcast tool.started for each independent tool
                await _broadcast_tool_events("tool.started", independent, self.run_id, self.instance_id)

                results = await asyncio.gather(*[
                    _execute_single_tool(tc, self.executor, self.hook_pipeline, ctx_defaults)
                    for tc in independent
                ], return_exceptions=True)

                for tc, result in zip(independent, results):
                    tool_name = tc.get("function", {}).get("name", "unknown")
                    tc_id = tc.get("id", "")
                    if isinstance(result, Exception) or (isinstance(result, dict) and result.get("error")):
                        error_msg = str(result) if isinstance(result, Exception) else result.get("error", "")
                        logger.warning("Tool %s failed: %s", tool_name, error_msg)
                        completed_tools.append({
                            "tool_name": tool_name,
                            "tool_call_id": tc_id,
                            "result": None,
                            "error": error_msg,
                        })
                        # Wave 8A: broadcast tool.failed
                        await _broadcast_single_tool_event("tool.failed", self.run_id, self.instance_id, tool_name, tc_id, error=error_msg)
                    else:
                        completed_tools.append(result)
                        if isinstance(result, dict):
                            if "latency_ms" in result:
                                per_tool_latency_ms[tool_name] = result["latency_ms"]
                            if "tool_call_id" not in result:
                                result["tool_call_id"] = tc_id
                        # Wave 8A: broadcast tool.completed
                        await _broadcast_single_tool_event("tool.completed", self.run_id, self.instance_id, tool_name, tc_id,
                            result=_safe_summary(result) if isinstance(result, dict) else str(result)[:500])

            # Execute dependent calls sequentially
            for tc in dependent:
                tool_name = tc.get("function", {}).get("name", "unknown")
                tc_id = tc.get("id", "")
                if progress_callback:
                    try:
                        await progress_callback(f"Running {tool_name}…")
                    except Exception:
                        pass

                # Wave 8A: broadcast tool.started
                await _broadcast_single_tool_event("tool.started", self.run_id, self.instance_id, tool_name, tc_id)

                result = await _execute_single_tool(tc, self.executor, self.hook_pipeline, ctx_defaults)
                if isinstance(result, dict) and "tool_call_id" not in result:
                    result["tool_call_id"] = tc_id
                completed_tools.append(result)
                if isinstance(result, dict) and "latency_ms" in result:
                    per_tool_latency_ms[tool_name] = result["latency_ms"]

                # Wave 8A: broadcast tool.completed or tool.failed
                if isinstance(result, dict) and result.get("error"):
                    await _broadcast_single_tool_event("tool.failed", self.run_id, self.instance_id, tool_name, tc_id, error=result["error"])
                else:
                    await _broadcast_single_tool_event("tool.completed", self.run_id, self.instance_id, tool_name, tc_id,
                        result=_safe_summary(result) if isinstance(result, dict) else "")

        # ── Stream text to widget ────────────────────────────────────────
        streamed = False
        if stream_callback and text:
            if progress_callback:
                try:
                    await progress_callback("Composing response…")
                except Exception:
                    pass
            _pos = 0
            while _pos < len(text):
                _end = min(_pos + 80, len(text))
                try:
                    await stream_callback(text[_pos:_end])
                except Exception:
                    break
                _pos = _end
            streamed = True

        elapsed = (time.monotonic() - t0) * 1000
        logger.info(
            "ExecuteWitness: tools=%d completed=%d streamed=%s latency=%.0fms",
            len(tool_calls), len(completed_tools), streamed, elapsed,
        )

        return ExecutionResult(
            completed_tools=completed_tools,
            streamed=streamed,
            execution_latency_ms=elapsed,
            per_tool_latency_ms=per_tool_latency_ms,
        )


def _split_by_dependencies(tool_calls: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split tool calls into independent (parallel-safe) and dependent (sequential).

    A tool call is dependent if it has a 'depends_on' field referencing
    another tool call's result. Independent calls can run in parallel.
    """
    independent: list[dict] = []
    dependent: list[dict] = []
    for tc in tool_calls:
        if tc.get("depends_on"):
            dependent.append(tc)
        else:
            independent.append(tc)
    return independent, dependent


async def _execute_single_tool(
    tool_call: dict,
    executor_override=None,
    hook_pipeline=None,           # P3.3: HookPipeline | None
    hook_ctx_defaults: dict | None = None,  # P3.3: default HookContext fields
) -> dict:
    """Execute a single tool call and return a result dict.

    P3.3: Runs guardrail before/after hooks around the tool call when
    hook_pipeline is provided. Before-hooks can cancel or redirect; after-hooks
    can redact the result.

    Returns dict with keys: tool_name, result, error, latency_ms, guardrail_flags.
    """
    from ai.engine.agent.tools import get_tool_executors

    func_data = tool_call.get("function", {})
    tool_name = func_data.get("name", "unknown")
    args_str = func_data.get("arguments", "{}")

    t0 = time.monotonic()
    try:
        args = json.loads(args_str) if isinstance(args_str, str) else args_str
    except json.JSONDecodeError:
        elapsed = (time.monotonic() - t0) * 1000
        logger.warning("Tool %s: invalid JSON args: %s", tool_name, args_str[:100])
        return {
            "tool_name": tool_name,
            "result": None,
            "error": f"Invalid JSON arguments: {args_str[:100]}",
            "latency_ms": elapsed,
        }

    # ── P3.3: Before-hook pipeline ──────────────────────────────────────
    guardrail_flags: list[str] = []
    if hook_pipeline is not None:
        from ai.engine.agent.guardrails import HookContext
        ctx_defaults = hook_ctx_defaults or {}
        hook_ctx = HookContext(
            tool_name=tool_name,
            tool_args=args,
            instance_id=ctx_defaults.get("instance_id", ""),
            host_user_id=ctx_defaults.get("host_user_id"),
            run_id=ctx_defaults.get("run_id"),
            step_id=ctx_defaults.get("step_id"),
            agent_role=ctx_defaults.get("agent_role", "orchestrator"),
            is_worker=ctx_defaults.get("is_worker", False),
            instance_config=ctx_defaults.get("instance_config"),
        )

        try:
            before_result = await hook_pipeline.run_before(hook_ctx)
            if before_result.flags:
                guardrail_flags.extend(before_result.flags)

            if before_result.action == "cancel":
                elapsed = (time.monotonic() - t0) * 1000
                logger.warning(
                    "Guardrail cancelled tool=%s reason=%s",
                    tool_name, before_result.reason,
                )
                return {
                    "tool_name": tool_name,
                    "result": None,
                    "error": f"Tool cancelled by guardrail: {before_result.reason}",
                    "latency_ms": elapsed,
                    "guardrail_flags": guardrail_flags,
                }

            if before_result.action == "redirect" and before_result.modified_args:
                logger.debug(
                    "Guardrail redirected tool=%s", tool_name,
                )
                args = before_result.modified_args

        except Exception as exc:
            logger.exception("Before-hook pipeline error for tool=%s: %s", tool_name, exc)

    # ── Execute the tool ─────────────────────────────────────────────────
    try:
        executors = await get_tool_executors()
        executor_fn = executors.get(tool_name)
        if executor_fn is None:
            elapsed = (time.monotonic() - t0) * 1000
            logger.warning("Tool %s: no executor found", tool_name)
            return {
                "tool_name": tool_name,
                "result": None,
                "error": f"Unknown tool: {tool_name}",
                "latency_ms": elapsed,
            }

        t_exec = time.monotonic()

        # ── Sprint 12: expose turn context to tool/workflow plugins ──────
        from ai.engine.agent.plugins import ToolContext, set_tool_context
        ctx_defaults = hook_ctx_defaults or {}
        set_tool_context(ToolContext(
            instance_id=ctx_defaults.get("instance_id", ""),
            conversation_id=ctx_defaults.get("conversation_id", ""),
            host_user_id=ctx_defaults.get("host_user_id"),
            instance_config=ctx_defaults.get("instance_config"),
            host_api=executor_override,
        ))

        # ── Dispatch convention (heterogeneous executors) ────────────────
        # Plugins (make_executor) and MCP executors take the args dict
        # positionally; static tools declare named params (query, skill_name,
        # api_name, ...). Calling `executor_fn(args)` positionally bound the
        # whole dict to the first named param and crashed static tools
        # (e.g. invoke_skill: 'dict' object has no attribute 'strip').
        # Dispatch by signature: kwargs when the function accepts them,
        # positional otherwise.
        import inspect as _inspect

        _call_args = dict(args) if isinstance(args, dict) else {}
        # Inject turn context for static tools that need it (call_host_api,
        # invoke_skill, ...) — mirror engine_runtime._run_action_stream so a
        # plan step can actually reach the host executor and instance.
        _hook_defaults = hook_ctx_defaults or {}
        if executor_override is not None and "executor" not in _call_args:
            _call_args["executor"] = executor_override
        if _hook_defaults.get("instance_id") and "instance_id" not in _call_args:
            _call_args["instance_id"] = _hook_defaults["instance_id"]
        if _hook_defaults.get("conversation_id") and "conversation_id" not in _call_args:
            _call_args["conversation_id"] = _hook_defaults["conversation_id"]
        try:
            _sig = _inspect.signature(executor_fn)
            _has_var_kw = any(
                p.kind == _inspect.Parameter.VAR_KEYWORD
                for p in _sig.parameters.values()
            )
            _all_named = bool(_call_args) and all(
                k in _sig.parameters for k in _call_args
            )
        except (TypeError, ValueError):
            _has_var_kw, _all_named = False, False

        if _has_var_kw or _all_named:
            result = await executor_fn(**_call_args)
        else:
            result = await executor_fn(_call_args)
        elapsed = (time.monotonic() - t_exec) * 1000

        # ── P3.3: After-hook pipeline ───────────────────────────────────
        if hook_pipeline is not None:
            try:
                after_result = await hook_pipeline.run_after(hook_ctx, result)
                if after_result.flags:
                    guardrail_flags.extend(after_result.flags)
                if after_result.action == "redact" and after_result.modified_result:
                    result = after_result.modified_result
                    logger.debug("Guardrail redacted result for tool=%s", tool_name)
            except Exception as exc:
                logger.exception("After-hook pipeline error for tool=%s: %s", tool_name, exc)

        # ── Nested tool-error promotion ───────────────────────────────────
        # Heterogeneous executors may return {"error": ...} as their RESULT
        # (e.g. invoke_skill's "No skill named X found — try draft_skill
        # first."). Without this lift the wrapper's top-level "error" stays
        # None, the failure is serialized into ``result``, and loop.py's
        # tool-error propagation misses it — the step persists "completed"
        # with a silent failure. Promote inner dict errors so loop.py marks
        # the step failed honestly.
        if isinstance(result, dict) and result.get("error"):
            _inner_err = result["error"]
            logger.warning(
                "Tool %s returned error result: %s", tool_name, _inner_err,
            )
            return {
                "tool_name": tool_name,
                "result": _safe_serialize(result),
                "error": str(_inner_err),
                "latency_ms": elapsed,
                "guardrail_flags": guardrail_flags,
            }

        result_str = _safe_serialize(result)

        logger.debug("Tool executed: %s args=%s latency=%.0fms", tool_name, str(args)[:100], elapsed)
        return {
            "tool_name": tool_name,
            "result": result_str,
            "error": None,
            "latency_ms": elapsed,
            "guardrail_flags": guardrail_flags,
        }
    except Exception as e:
        elapsed = (time.monotonic() - t0) * 1000
        logger.warning("Tool %s error: %s", tool_name, e)
        return {
            "tool_name": tool_name,
            "result": None,
            "error": str(e),
            "latency_ms": elapsed,
        }


def _safe_serialize(value) -> str:
    """Serialize a tool result to a JSON-safe string."""
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return str(value)


def _safe_summary(result: dict) -> str:
    """Return a short string summary of a tool result for event broadcast."""
    try:
        s = json.dumps(result.get("result", result), default=str)
        return s[:500]
    except (TypeError, ValueError):
        return str(result)[:500]


async def _broadcast_tool_events(event_type: str, tool_calls: list[dict], run_id: str, instance_id: str):
    """Broadcast tool.started events for a batch of tool calls."""
    global broadcast_run_event
    if broadcast_run_event is None:
        from ai.engine.cognition.notifier import broadcast_run_event as _bre
        broadcast_run_event = _bre
    if broadcast_run_event is None or not run_id:
        return

    for tc in tool_calls:
        fn = tc.get("function", {})
        tool_name = fn.get("name", "unknown")
        tc_id = tc.get("id", "")
        args_str = fn.get("arguments", "{}")
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError:
            args = {"raw": args_str[:200]}
        try:
            await broadcast_run_event(instance_id, event_type, {
                "run_id": run_id,
                "tool_name": tool_name,
                "tool_call_id": tc_id,
                "args": args,
            })
        except Exception:
            pass


async def _broadcast_single_tool_event(
    event_type: str, run_id: str, instance_id: str, tool_name: str, tool_call_id: str,
    result: str = "", error: str = "",
):
    """Broadcast a single tool.started/completed/failed event."""
    global broadcast_run_event
    if broadcast_run_event is None:
        from ai.engine.cognition.notifier import broadcast_run_event as _bre
        broadcast_run_event = _bre
    if broadcast_run_event is None or not run_id:
        return

    payload: dict = {
        "run_id": run_id,
        "tool_name": tool_name,
        "tool_call_id": tool_call_id,
    }
    if result:
        payload["result_summary"] = result
    if error:
        payload["error"] = error

    try:
        await broadcast_run_event(instance_id, event_type, payload)
    except Exception:
        pass
