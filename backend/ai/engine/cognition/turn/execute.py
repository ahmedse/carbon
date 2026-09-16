"""S5 — Execute witness (real parallel tool dispatch).

S3 produces tool_calls; S5 executes them. Independent calls run in parallel
via asyncio.gather. Results are streamed to the widget as they complete.

Wave 8A: Broadcasts tool.started/completed/failed events to the studio
event stream so the ActivityFeed can show what the agent *did*.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable

from ai.engine.cognition.turn.witnesses import ExecutionResult
from ai.engine.core.resolution import payload_status
from ai.engine.ports.evidence import EvidenceStore

logger = logging.getLogger("pulse.cognition.turn.execute")

# Lazy import — avoids circular dependency with notifier
broadcast_run_event = None

# Host-injected adapter provider (constructed once in host code). The engine
# never imports ``ai.adapters``; callers wire it during bootstrap.
_evidence_store_provider: Callable[[], EvidenceStore] | None = None


def set_evidence_store_provider(provider: Callable[[], EvidenceStore]) -> None:
    """Inject the host's ``EvidenceStore`` adapter at bootstrap."""
    global _evidence_store_provider
    _evidence_store_provider = provider


def _resolve_evidence_store() -> EvidenceStore:
    if _evidence_store_provider is None:
        raise RuntimeError(
            "EvidenceStore adapter not injected; call "
            "ai.engine.cognition.turn.execute.set_evidence_store_provider() during bootstrap"
        )
    return _evidence_store_provider()

# W6-C: output-type marker keys promoted from a dict tool result to the
# wrapper's TOP level. plans_service._infer_output_type (frozen contract)
# infers a step's renderer kind from the top-level keys of the PERSISTED
# tool_output; dict results (e.g. export_document's {files, download_url})
# arrive nested inside the JSON-string ``result`` and would otherwise
# serialize as "text". Mirror the frozen vocabulary exactly.
_OUTPUT_TYPE_MARKER_KEYS = frozenset({
    # hints
    "_output_type", "output_type", "type", "render",
    # artifact markers
    "artifact", "artifacts", "file", "files", "file_path",
    "download_url", "path", "filename",
    # table / chart markers
    "headers", "rows", "columns", "series", "labels", "values", "x", "y",
})


class ExecuteWitness:
    """Parallel tool dispatch + streaming. Executes tool calls from S3 draft."""

    def __init__(self, executor=None, hook_pipeline=None, hook_ctx_defaults: dict | None = None, run_id: str = "", instance_id: str = "", knowledge_store=None, evidence_store: EvidenceStore | None = None):
        self.executor = executor  # optional override for host API executor
        self.hook_pipeline = hook_pipeline  # P3.3: guardrail hook pipeline
        self.hook_ctx_defaults = hook_ctx_defaults or {}  # P3.3: default HookContext fields
        self.run_id = run_id  # Wave 8A: for tool event broadcasting
        self.instance_id = instance_id  # Wave 8A: for scoped studio broadcast
        # S-PROC-01: knowledge store threaded into tool dispatch so
        # ``search_knowledge`` / ``get_entity_details`` ground answers in the
        # indexed process docs instead of returning "store not available".
        self.knowledge_store = knowledge_store
        # P2-03: evidence store threaded via the port seam so the host may
        # inject a mock/alternate adapter. When omitted, the host bootstrap
        # provider is consulted (fail-closed if none is wired).
        self.evidence_store = evidence_store

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
                    for tc in independent:
                        try:
                            await progress_callback(_narrate_tool(
                                tc.get("function", {}).get("name", "tool"),
                                _parse_tool_args(tc),
                            ))
                        except Exception:
                            pass

                # Wave 8A: broadcast tool.started for each independent tool
                await _broadcast_tool_events("tool.started", independent, self.run_id, self.instance_id)

                results = await asyncio.gather(*[
                    _execute_single_tool(tc, self.executor, self.hook_pipeline, ctx_defaults, self.knowledge_store)
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
                        await self._register_evidence(
                            tool_name=tool_name,
                            tool_args=_parse_tool_args(tc),
                            tool_result=result,
                        )
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
                        await progress_callback(_narrate_tool(tool_name, _parse_tool_args(tc)))
                    except Exception:
                        pass

                # Wave 8A: broadcast tool.started
                await _broadcast_single_tool_event("tool.started", self.run_id, self.instance_id, tool_name, tc_id)

                result = await _execute_single_tool(tc, self.executor, self.hook_pipeline, ctx_defaults, self.knowledge_store)
                if isinstance(result, dict) and "tool_call_id" not in result:
                    result["tool_call_id"] = tc_id
                completed_tools.append(result)
                if isinstance(result, dict) and not result.get("error"):
                    await self._register_evidence(
                        tool_name=tool_name,
                        tool_args=_parse_tool_args(tc),
                        tool_result=result,
                    )
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

    async def _register_evidence(
        self,
        *,
        tool_name: str,
        tool_args: dict,
        tool_result: dict,
    ) -> None:
        """Write an EvidenceRecord row for a successfully executed tool call.

        Silently no-ops on any error — evidence recording must never fail a turn.
        ``no_match`` and confirmation-gated tool results are not evidence.
        """
        import json as _json

        evidence_store = self.evidence_store
        if evidence_store is None:
            evidence_store = _resolve_evidence_store()

        try:
            raw = tool_result.get("result")
            # no_match is an escalation signal, never evidence of data.
            if payload_status(raw) == "no_match":
                return
            # Confirmation-gated tools (create_dq_rule, …) stage proposals,
            # which are not evidence.
            if _tool_requires_confirmation(tool_name):
                return
            if tool_result.get("error") or raw is None:
                return

            # Parse the JSON-string result back into structured content.
            content = raw
            if isinstance(raw, str):
                try:
                    content = _json.loads(raw)
                except (TypeError, ValueError):
                    content = {"raw": raw[:2000]}
            if not isinstance(content, (dict, list)):
                content = {"raw": str(content)[:2000]}

            source_map = {
                "web_research": "web_search",
                "search_knowledge": "knowledge_graph",
                "get_entity_details": "carbon_api",
                "call_host_api": "carbon_api",
            }
            source_type = source_map.get(tool_name, "carbon_api")
            args = tool_args or {}
            source_id = args.get("query") or args.get("endpoint") or tool_name

            ctx = self.hook_ctx_defaults or {}
            instance_id = ctx.get("instance_id") or self.instance_id or ""
            conversation_id = ctx.get("conversation_id") or ""
            host_user_id = ctx.get("host_user_id") or ""
            turn_id = ctx.get("run_id") or self.run_id or ""

            await evidence_store.record(
                instance_id=instance_id,
                conversation_id=conversation_id,
                turn_id=turn_id,
                host_user_id=host_user_id,
                source_type=source_type,
                source_identifier=str(source_id)[:500],
                query_description=_json.dumps(args, ensure_ascii=False, default=str)[:2000],
                content_json=content,
                coverage="unknown",
            )
        except Exception:
            logger.warning("EvidenceRecord write failed for %s", tool_name, exc_info=True)


def _parse_tool_args(tool_call: dict) -> dict:
    """Extract tool arguments from a tool-call dict (JSON string or object)."""
    args = tool_call.get("function", {}).get("arguments", "{}")
    if isinstance(args, str):
        try:
            return json.loads(args)
        except (json.JSONDecodeError, TypeError):
            return {}
    return args if isinstance(args, dict) else {}


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


def _narrate_tool(tool_name: str, args: dict | None) -> str:
    """Human, first-person narration of what the assistant is doing right now.

    Richer than "Running <tool>" so the thinking timeline reads like real
    self-talk (VS Code Copilot style).
    """
    a = args or {}
    name = tool_name or "tool"
    if name == "resolve_entity":
        q = (a.get("query") or "").strip()
        return f"🔎 Searching every record for “{q}”…" if q else "🔎 Searching the records…"
    if name.startswith("call_host_api"):
        api = (a.get("api_name") or a.get("api") or "").strip()
        if api == "analyze_employees":
            dim = a.get("dimension") or (a.get("query_params") or {}).get("dimension")
            return f"📊 Analysing employees by {dim}…" if dim else "📊 Analysing the workforce…"
        if api.startswith("list_"):
            return f"📇 Fetching {api.removeprefix('list_').replace('_', ' ')}…"
        if api.startswith("get_"):
            return f"📄 Looking up {api.removeprefix('get_').replace('_', ' ')}…"
        return f"📊 Querying live data{f' ({api})' if api else ''}…"
    if name == "search_knowledge":
        q = (a.get("query") or "").strip()
        return f"📚 Checking what I know about “{q}”…" if q else "📚 Checking what I know…"
    if name == "get_entity_details":
        return "🧩 Reading the entity's schema and meaning…"
    if name in ("navigate_to", "open_entity"):
        return "🧭 Preparing to open the right page…"
    if name in ("learn_fact", "forget_fact"):
        return "🧠 Preparing a memory update for your approval…"
    if name == "inspect_case":
        return "🔍 Inspecting the process case…"
    if name == "ask_clarification":
        return "🤔 Working out what to ask you…"
    return f"Running {name}…"


async def _execute_single_tool(
    tool_call: dict,
    executor_override=None,
    hook_pipeline=None,           # P3.3: HookPipeline | None
    hook_ctx_defaults: dict | None = None,  # P3.3: default HookContext fields
    knowledge_store=None,         # S-PROC-01: knowledge store for search/get_entity
) -> dict:
    """Execute a single tool call and return a result dict.

    P3.3: Runs guardrail before/after hooks around the tool call when
    hook_pipeline is provided. Before-hooks can cancel or redirect; after-hooks
    can redact the result.

    S-PROC-01 / S-TRACE-01: the resolved ``knowledge_store`` is injected into
    the tool args so ``search_knowledge`` / ``get_entity_details`` ground
    answers in indexed process docs. The parsed tool args are echoed back on
    the result dict as ``tool_args`` so the surfacing layer can render a
    step-by-step input/output trace.

    Returns dict with keys: tool_name, result, error, latency_ms,
    guardrail_flags, tool_args.
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
        # S-PROC-01: inject a knowledge store so ``search_knowledge`` /
        # ``get_entity_details`` ground answers in indexed process docs. Use
        # the threaded store when present; otherwise lazily build one from the
        # host executor's DB session so no dispatch path can silently return
        # "Knowledge store not available".
        _ks = knowledge_store
        if _ks is None and executor_override is not None:
            _db = getattr(executor_override, "db", None)
            if _db is not None:
                try:
                    from ai.engine.knowledge.store import KnowledgeStore
                    _ks = KnowledgeStore(_db)
                except Exception:  # noqa: BLE001 - never break a turn over store init
                    _ks = None
        if _ks is not None and "knowledge_store" not in _call_args:
            _call_args["knowledge_store"] = _ks
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

        # ── Null-output guard (mutation/confirmation tools) ──────────────
        # A confirmation-gated tool (create_dq_rule, learn_fact, …) that
        # returns None or an empty payload produced NO proposal and NO
        # execution. Serializing that to "null" and carrying on used to mark
        # the step "completed" — a phantom success (2026-08-27: the planner
        # hallucinated create_dq_rule args, the tool returned nothing, yet
        # critic/step/run all read "completed"). Fail honestly instead.
        if _is_null_tool_output(result) and _tool_requires_confirmation(tool_name):
            _msg = (
                f"{tool_name} returned no output "
                f"(expected a confirmation response)"
            )
            logger.warning("Tool %s returned null output; failing honestly", tool_name)
            return {
                "tool_name": tool_name,
                "result": None,
                "error": _msg,
                "latency_ms": elapsed,
                "guardrail_flags": guardrail_flags,
            }

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

        # ── W6-C: surface output-type markers at the wrapper top level ──
        # plans_service._infer_output_type reads the PERSISTED tool_output's
        # top-level keys (frozen contract — "fix the handoff, not
        # store_artifact/_infer_output_type itself"). Dict results are
        # JSON-strings nested under ``result``; promote the marker keys so
        # export-style plugins serialize as "artifact" (and table/chart
        # results as their real shape) instead of "text". Additive only —
        # key-based consumers (``_safe_summary``, ``_extract_tool_actions``)
        # read ``result``/``tool_name``/``error`` by name and are unaffected.
        _extra: dict = {}
        if isinstance(result, dict):
            _extra = {
                k: v for k, v in result.items()
                if k in _OUTPUT_TYPE_MARKER_KEYS
            }

        logger.debug("Tool executed: %s args=%s latency=%.0fms", tool_name, str(args)[:100], elapsed)
        return {
            "tool_name": tool_name,
            "result": result_str,
            "error": None,
            "latency_ms": elapsed,
            "guardrail_flags": guardrail_flags,
            "tool_args": args,  # S-TRACE-01: echo resolved input for the trace
            **_extra,
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


def _is_null_tool_output(value) -> bool:
    """True when a tool result carries no usable payload (null / empty / blank)."""
    if value is None:
        return True
    if isinstance(value, dict) and not value:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _tool_requires_confirmation(tool_name: str) -> bool:
    """True when a registered plugin tool gates its write behind confirmation.

    Lazy import avoids a circular dependency; a lookup failure is treated as
    read-only (fail-open for the guard — a read-only tool returning null is
    still handled by the nested-error promotion and loop.py).
    """
    try:
        from ai.engine.agent.plugins import is_confirmation_tool
        return is_confirmation_tool(tool_name)
    except Exception:  # noqa: BLE001 - guard must never raise into the turn
        return False


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


def _build_tool_result_summary(completed_tools: list[dict]) -> str:
    """Render a prose summary from executed tool results.

    Used when the LLM drafts a tool-only turn (calls tools but emits no prose
    text). Without this, the turn would be saved with empty content and appear
    as a blank/"removed" message in the UI (GAP-W8 regression).

    Handles the real pipeline shape (``result`` is a JSON string from
    ``_safe_serialize``) as well as raw dict results. Deterministic and
    side-effect free so it can be unit-tested directly.

    Gate (Chat QA A9 / M08): when **every** tool errored, do **not** wrap in
    "Here's what I found" + mutation language ("nothing was changed"). That
    dump reads as an unintelligent engagement. Use a read-safe calibration
    refuse instead — Chat is advisory; a failed lookup is not a write abort.
    """
    if not completed_tools:
        return ""

    def _normalize(raw):
        """Return a dict/list from a result payload (JSON string or object).

        Also unwraps the host-executor envelope ``{"status_code": 200,
        "data": ...}`` and nests one level (``data: {"results": [...]}``).
        """
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, (dict, list)):
                    raw = parsed
            except (TypeError, ValueError):
                pass
        if isinstance(raw, dict) and "status_code" in raw and "data" in raw:
            raw = raw.get("data")
        if isinstance(raw, dict):
            for key in ("data", "results", "items", "rows"):
                if key in raw and isinstance(raw[key], list):
                    return raw[key]
        return raw

    # All-failed gate — refuse calibration, never mutation-abort dump.
    if all(isinstance(t, dict) and t.get("error") for t in completed_tools):
        return (
            "I couldn't complete that lookup just now. "
            "Please try again in a moment — no answer was invented."
        )

    tool_summaries: list[str] = []
    for tool_result in completed_tools:
        tool_name = tool_result.get("tool_name", "unknown")
        result_data = _normalize(tool_result.get("result", {}))
        error = tool_result.get("error")
        # no_match is an escalation signal, never data — render an honest
        # clarification, never the raw `status=no_match, reason=..., hint=...`.
        if payload_status(tool_result.get("result")) == "no_match":
            hint = ""
            if isinstance(result_data, dict):
                hint = str(result_data.get("hint") or "").strip()
            if not hint:
                hint = "your request"
            tool_summaries.append(
                f'**{tool_name}**: I couldn\'t resolve "{hint}". Could you clarify what you meant?'
            )
        elif error:
            # RULE_23 (C-F4b): outcome only — never leak raw error / tool id.
            # Read-path wording: do not claim "nothing was changed" (mutation UX).
            tool_summaries.append(
                "One lookup step couldn't be completed."
            )
        elif isinstance(result_data, dict):
            items = list(result_data.items())[:10]
            list_payload = None
            for key in ("data", "results"):
                if key in result_data and isinstance(result_data[key], list):
                    list_payload = result_data[key]
                    break
            if list_payload is not None:
                row_count = len(list_payload)
                tool_summaries.append(f"**{tool_name}**: Retrieved {row_count} row(s)")
            elif items:
                brief = ", ".join(f"{k}={v}" for k, v in items[:3])
                tool_summaries.append(f"**{tool_name}**: {brief}...")
            else:
                tool_summaries.append(f"**{tool_name}**: (empty result)")
        elif isinstance(result_data, list):
            tool_summaries.append(f"**{tool_name}**: Retrieved {len(result_data)} row(s)")
        else:
            summary_text = str(result_data)[:200]
            tool_summaries.append(f"**{tool_name}**: {summary_text}")

    return "Here's what I found:\n\n" + "\n\n".join(tool_summaries)


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
