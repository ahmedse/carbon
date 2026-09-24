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

# Known HR → ESS twin map for self-service retries on host 403 (PV2-2C).
_MY_API_TWINS: dict[str, str] = {
    "list_payslip_lines": "list_my_payslips",
    "list_leave_records": "list_my_leave",
    "list_leave_entitlements": "list_my_leave",
    "list_loans": "list_my_loans",
    "list_loan_installments": "list_my_loans",
    "list_attendance_permissions": "list_my_attendance_permissions",
    "list_attendance": "list_my_attendance",
    "get_leave_balance": "get_my_leave_balance",
}


def find_my_api_twin(api_name: str, catalog: list | None) -> str | None:
    """Return the ``*_my_*`` twin for ``api_name`` when present in ``catalog``."""
    name = (api_name or "").strip()
    if not name or "_my_" in name:
        return None
    names = {
        str(e.get("name") or "")
        for e in (catalog or [])
        if isinstance(e, dict) and e.get("name")
    }
    mapped = _MY_API_TWINS.get(name)
    if mapped and mapped in names:
        return mapped
    # Heuristic: list_foo_bar → list_my_foo_bar / list_my_foos
    for prefix in ("list_", "get_", "submit_"):
        if not name.startswith(prefix):
            continue
        rest = name[len(prefix):]
        candidates = [
            f"{prefix}my_{rest}",
            f"{prefix}my_{rest.rstrip('s')}",
        ]
        if rest.endswith("_lines"):
            candidates.append(f"{prefix}my_{rest[:-6]}s")
        if rest.endswith("_records"):
            candidates.append(f"{prefix}my_{rest[:-8]}")
        for cand in candidates:
            if cand in names:
                return cand
    return None


# Query fields models often put at the top level of a bare catalog call.
_CATALOG_QUERY_KEYS = frozenset({
    "dimension", "is_active", "page", "page_size", "limit", "offset",
    "search", "q", "ordering", "status", "employee_no", "date",
    "date_from", "date_to", "period", "year", "month",
})
_CATALOG_PATH_KEYS = frozenset({"id", "pk", "employee_id", "run_id"})
_CATALOG_KEEP_KEYS = frozenset({
    "api_name", "path_params", "query_params", "body", "explanation",
})


def coerce_bare_catalog_tool(
    tool_name: str,
    args: dict | None,
    instance_config: dict | None,
) -> tuple[str, dict]:
    """Rewrite a bare ``api_catalog`` name into ``call_host_api``.

    Draft LLMs often emit ``analyze_employees(dimension=…)`` because the
    prompt lists catalog endpoint names. Those names are not executor keys —
    only ``call_host_api`` is. Without this coerce, execute logs
    ``Unknown tool: analyze_employees`` and charts never get breakdown data.
    """
    name = (tool_name or "").strip()
    call_args = dict(args or {}) if isinstance(args, dict) else {}
    if not name or name == "call_host_api":
        return name or "unknown", call_args

    catalog = (instance_config or {}).get("api_catalog") or []
    names = {
        str(ep.get("name") or "")
        for ep in catalog
        if isinstance(ep, dict) and ep.get("name")
    }
    if name not in names:
        return name, call_args

    query = dict(call_args.get("query_params") or {})
    path = dict(call_args.get("path_params") or {})
    body = call_args.get("body")
    if not isinstance(body, dict):
        body = {} if body is None else {"value": body}

    for key, value in list(call_args.items()):
        if key in _CATALOG_KEEP_KEYS:
            continue
        if key in _CATALOG_QUERY_KEYS:
            query.setdefault(key, value)
            continue
        if key in _CATALOG_PATH_KEYS:
            path.setdefault(key, value)
            continue
        if key in {"executor", "instance_id", "conversation_id", "user_message"}:
            continue
        # Flat filters the model forgot to nest under query_params.
        query.setdefault(key, value)

    coerced = {
        "api_name": name,
        "explanation": str(
            call_args.get("explanation") or f"Live {name} lookup"
        ),
    }
    if query:
        coerced["query_params"] = query
    if path:
        coerced["path_params"] = path
    if body:
        coerced["body"] = body
    return "call_host_api", coerced


def own_records_403_message(lang: str, api_name: str = "") -> str:
    """Honest bilingual message when the host denies an org-wide read."""
    from ai.engine.cognition.turn.language import detect_reply_language

    # Allow callers to pass a user message as lang when they already detected.
    code = lang if lang in ("ar", "en") else detect_reply_language(lang or "")
    if code == "ar":
        return (
            "يمكنني فقط قراءة سجلاتك الخاصة — مثل قسائم راتبك عبر "
            "list_my_payslips، أو إجازاتك وقروضك الذاتية. "
            "لا أملك صلاحية قوائم الموارد البشرية على مستوى المؤسسة."
        )
    return (
        "I can only read your own records — for example your payslips via "
        "list_my_payslips, or your own leave and loans. "
        "I don't have access to organisation-wide HR lists."
    )


async def maybe_retry_my_twin_on_403(
    first: dict,
    *,
    args: dict,
    invoke,
    instance_config: dict | None,
    user_message: str = "",
) -> dict:
    """On host HTTP 403, retry once with the ``*_my_*`` twin when catalogued.

    Does not weaken consent / ADR-0046 — only catalogued twins, one hop.
    ``invoke`` is ``async (api_name: str) -> result_dict``.
    """
    api_name = str((args or {}).get("api_name") or (args or {}).get("api") or "")
    catalog = (instance_config or {}).get("api_catalog") or []
    twin = find_my_api_twin(api_name, catalog)
    flags = list(first.get("guardrail_flags") or [])
    from ai.engine.cognition.turn.language import detect_reply_language

    lang = detect_reply_language(user_message or "")
    if not twin:
        out = dict(first)
        out["error"] = own_records_403_message(lang, api_name)
        out["guardrail_flags"] = flags + ["host_403_no_twin"]
        return out

    try:
        repaired = await invoke(twin)
    except Exception as exc:  # noqa: BLE001
        logger.warning("403 twin-retry invoke failed: %s", exc)
        out = dict(first)
        out["error"] = own_records_403_message(lang, api_name)
        out["guardrail_flags"] = flags + ["host_403_twin_failed"]
        return out

    if isinstance(repaired, dict) and "status_code" in repaired:
        try:
            code = int(repaired.get("status_code"))
        except (TypeError, ValueError):
            code = None
        if code is not None and code >= 400:
            out = dict(first)
            out["error"] = own_records_403_message(lang, api_name)
            out["guardrail_flags"] = flags + ["host_403_twin_denied"]
            out["result"] = _safe_serialize(repaired)
            return out

    return {
        "tool_name": first.get("tool_name") or "call_host_api",
        "result": _safe_serialize(repaired),
        "error": None,
        "latency_ms": first.get("latency_ms") or 0,
        "guardrail_flags": flags + ["twin_retry", f"twin_retry:{api_name}->{twin}"],
        "tool_args": {**(args or {}), "api_name": twin},
    }


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
                                surface=ctx_defaults.get("surface", "chat"),
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
                        await progress_callback(_narrate_tool(
                            tool_name,
                            _parse_tool_args(tc),
                            surface=ctx_defaults.get("surface", "chat"),
                        ))
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


def _narrate_tool(
    tool_name: str,
    args: dict | None,
    *,
    surface: str = "chat",
) -> str:
    """Human, first-person narration of what the assistant is doing right now.

    Richer than "Running <tool>" so the thinking timeline reads like real
    self-talk (VS Code Copilot style). Never leak raw catalog ids to the user.

    On Chat surface, mutation tools are blocked (ADR-0046) — never say
    "Submitting…" for them; say we are preparing next steps instead.
    """
    from ai.engine.agent.chat_surface import (
        chat_mutation_narration,
        is_chat_surface,
        is_host_mutation_tool,
    )

    a = args or {}
    name = tool_name or "tool"
    if is_chat_surface(surface) and is_host_mutation_tool(name, a):
        api = (a.get("api_name") or a.get("api") or name or "").strip()
        return f"✍️ {chat_mutation_narration(api)}"

    if name == "resolve_entity":
        q = (a.get("query") or "").strip()
        return f"🔎 Searching every record for “{q}”…" if q else "🔎 Searching the records…"
    if name.startswith("call_host_api") or name in (
        "submit_my_leave", "create_leave_record", "submit_my_loan",
        "create_employee", "update_employee",
    ):
        api = (a.get("api_name") or a.get("api") or name or "").strip()
        method = str(a.get("method") or "").strip().upper()
        friendly = {
            "submit_my_leave": "Submitting your leave request",
            "create_leave_record": "Submitting a leave request",
            "get_my_leave_balance": "Checking your leave balance",
            "list_my_leave": "Listing your leave records",
            "submit_my_loan": "Submitting your loan request",
            "create_employee": "Creating an employee record",
            "update_employee": "Updating the employee record",
            "submit_my_attendance_permission": "Submitting an attendance permission",
        }.get(api)
        if friendly:
            return f"✍️ {friendly}…"
        if method in ("POST", "PUT", "PATCH", "DELETE") or api.startswith(
            ("submit_", "create_", "update_", "delete_")
        ):
            label = api.removeprefix("submit_").removeprefix("create_").removeprefix("update_")
            label = label.replace("_", " ").strip() or "your request"
            return f"✍️ Submitting {label}…"
        if api.startswith("list_"):
            return f"📇 Fetching {api.removeprefix('list_').replace('_', ' ')}…"
        if api.startswith("get_"):
            return f"📄 Looking up {api.removeprefix('get_').replace('_', ' ')}…"
        if api == "analyze_employees":
            dim = a.get("dimension") or (a.get("query_params") or {}).get("dimension")
            return f"📊 Analysing employees by {dim}…" if dim else "📊 Analysing the workforce…"
        return "📊 Checking your records…"
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
    return "Working on the next step…"


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
            "tool_args": {},
        }

    # Bare catalog names (analyze_employees, list_employees, …) are not
    # executor keys — rewrite to call_host_api before guardrails so Chat
    # mutation handoff and host routing see the real capability.
    ctx_defaults = hook_ctx_defaults or {}
    original_tool_name = tool_name
    tool_name, args = coerce_bare_catalog_tool(
        tool_name,
        args,
        ctx_defaults.get("instance_config"),
    )
    if tool_name != original_tool_name:
        logger.info(
            "Coerced bare catalog tool %s → call_host_api api=%s",
            original_tool_name,
            (args or {}).get("api_name"),
        )

    # ── P3.3: Before-hook pipeline ──────────────────────────────────────
    guardrail_flags: list[str] = []
    if hook_pipeline is not None:
        from ai.engine.agent.guardrails import HookContext
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
            surface=ctx_defaults.get("surface", "chat"),
            user_message=str(ctx_defaults.get("user_message") or ""),
            process_mode=str(ctx_defaults.get("process_mode") or ""),
        )

        try:
            before_result = await hook_pipeline.run_before(hook_ctx)
            if before_result.flags:
                guardrail_flags.extend(before_result.flags)

            if before_result.action == "cancel":
                elapsed = (time.monotonic() - t0) * 1000
                # ADR-0046: Chat mutation handoff is intentional — not a tool
                # failure. Emit a structured result so the turn can show
                # Agent/My CTAs without creating pending_exec.
                if "chat_no_host_mutation" in (before_result.flags or []):
                    handoff = before_result.payload
                    if not isinstance(handoff, dict):
                        from ai.engine.agent.chat_surface import (
                            build_chat_handoff_result,
                        )
                        handoff = build_chat_handoff_result(
                            tool_name, args,
                            user_message=str(ctx_defaults.get("user_message") or ""),
                        )
                    logger.info(
                        "Chat surface blocked host mutation tool=%s api=%s",
                        tool_name,
                        (args or {}).get("api_name", ""),
                    )
                    return {
                        "tool_name": tool_name,
                        "result": handoff,
                        "error": None,
                        "latency_ms": elapsed,
                        "guardrail_flags": guardrail_flags,
                        "tool_args": args,
                    }
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
                    "tool_args": args,
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
                "tool_args": args,
            }

        t_exec = time.monotonic()

        # ── Sprint 12: expose turn context to tool/workflow plugins ──────
        from ai.engine.agent.plugins import ToolContext, set_tool_context
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
        if _hook_defaults.get("user_message") and "user_message" not in _call_args:
            _call_args["user_message"] = _hook_defaults["user_message"]
        if _hook_defaults.get("instance_config") is not None and "instance_config" not in _call_args:
            _call_args["instance_config"] = _hook_defaults["instance_config"]
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

        async def _invoke(fn, call_args: dict):
            """Dispatch by signature — kwargs when accepted, else positional."""
            try:
                _sig = _inspect.signature(fn)
                _has_var_kw = any(
                    p.kind == _inspect.Parameter.VAR_KEYWORD
                    for p in _sig.parameters.values()
                )
                _all_named = bool(call_args) and all(
                    k in _sig.parameters for k in call_args
                )
            except (TypeError, ValueError):
                _has_var_kw, _all_named = False, False
            if _has_var_kw or _all_named:
                return await fn(**call_args)
            return await fn(call_args)

        result = await _invoke(executor_fn, _call_args)

        # ── Self-heal: one bounded, read-only repair hop ────────────────
        # A lookup that missed by a naming hair ("leave_balance" when the
        # live endpoint is "get_my_leave_balance") is retried once against
        # the capability that actually exists, instead of dead-ending on
        # "not found". Mutations are never repaired (RULE_21), and a repair
        # that also misses falls back to the original result so recovery
        # synthesis explains the real gap.
        _repair = None
        try:
            from ai.engine.cognition.turn.self_heal import (
                annotate_repair,
                is_repairable_miss,
                propose_repair,
            )

            _repair = propose_repair(
                tool_name, args, result,
                instance_config=_hook_defaults.get("instance_config")
                or getattr(executor_override, "instance_config", None),
            )
            if _repair is not None:
                _repair_fn = executors.get(_repair.tool_name)
                if _repair_fn is not None:
                    _repair_args = {
                        k: v for k, v in _call_args.items()
                        if k in ("executor", "instance_id", "conversation_id",
                                 "instance_config", "knowledge_store",
                                 "user_message")
                    }
                    _repair_args.update(_repair.tool_args)
                    _repaired = await _invoke(_repair_fn, _repair_args)
                    if is_repairable_miss(_repair.tool_name, _repaired):
                        logger.info(
                            "self-heal: %s → %s still missed; keeping the "
                            "original result",
                            tool_name, _repair.strategy,
                        )
                        _repair = None
                    else:
                        logger.info(
                            "self-heal: %s → %s via %s",
                            tool_name, _repair.tool_name, _repair.strategy,
                        )
                        result = annotate_repair(_repaired, _repair, tool_name)
                        guardrail_flags.append(f"self_heal:{_repair.strategy}")
                else:
                    _repair = None
        except Exception:  # noqa: BLE001 - self-heal must never break a turn
            logger.exception("self-heal hop failed; using the original result")
            _repair = None

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
                "tool_args": args,
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
                "tool_args": args,
            }

        # Promote host HTTP 4xx/5xx envelopes to top-level error so Chat
        # recovery synthesis (ADR-0021 failure branch) sees the outcome
        # detail — not a silent "success" with a non-2xx body.
        if isinstance(result, dict) and "status_code" in result:
            try:
                _code = int(result.get("status_code"))
            except (TypeError, ValueError):
                _code = None
            if (
                _code is not None
                and _code >= 400
                and not result.get("unauthorized")
            ):
                _data = result.get("data")
                _detail = ""
                if isinstance(_data, dict):
                    _detail = str(_data.get("detail") or "").strip()
                if not _detail:
                    _detail = str(result.get("detail") or "").strip()
                _msg = _detail or f"Host returned HTTP {_code}"
                logger.warning("Tool %s host HTTP %s: %s", tool_name, _code, _msg[:160])
                _err_payload = {
                    "tool_name": tool_name,
                    "result": _safe_serialize(result),
                    "error": _msg,
                    "latency_ms": elapsed,
                    "guardrail_flags": guardrail_flags,
                    "tool_args": args,
                }
                # PV2-2C: one honest twin-retry on 403 for call_host_api.
                if (
                    _code == 403
                    and tool_name == "call_host_api"
                    and isinstance(args, dict)
                    and (args.get("api_name") or args.get("api"))
                ):
                    _cfg = (hook_ctx_defaults or {}).get("instance_config") or {}
                    _user_msg = str(
                        (hook_ctx_defaults or {}).get("user_message") or ""
                    )

                    async def _invoke_twin(twin_name: str):
                        twin_args = {**args, "api_name": twin_name}
                        return await _invoke(executor_fn, {
                            **{
                                k: v for k, v in _call_args.items()
                                if k in (
                                    "executor", "instance_id", "conversation_id",
                                    "instance_config", "knowledge_store",
                                    "user_message",
                                )
                            },
                            **twin_args,
                        })

                    return await maybe_retry_my_twin_on_403(
                        _err_payload,
                        args=args,
                        invoke=_invoke_twin,
                        instance_config=_cfg,
                        user_message=_user_msg,
                    )
                return _err_payload

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
            "tool_args": args if isinstance(args, dict) else {},
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
    dump reads as an unintelligent engagement. Prefer a clear business refuse
    with a next step — never meta-copy about invention / fabrication.
    """
    if not completed_tools:
        return ""

    def _normalize(raw):
        """Return a dict/list from a result payload (JSON string or object).

        Also unwraps the host-executor envelope ``{"status_code": 200,
        "data": ...}`` and nests one level (``data: {"results": [...]}``).
        Preserves top-level authz signals so CBAC denies are not lost (B5).
        """
        authz_meta = {}
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, (dict, list)):
                    raw = parsed
            except (TypeError, ValueError):
                pass
        if isinstance(raw, dict) and "status_code" in raw and "data" in raw:
            for key in (
                "unauthorized", "capability", "message",
                "unauthorized_fields", "status_code",
            ):
                if key in raw and raw[key] is not None:
                    authz_meta[key] = raw[key]
            raw = raw.get("data")
            if authz_meta and isinstance(raw, dict):
                merged = dict(raw)
                for k, v in authz_meta.items():
                    merged.setdefault(k, v)
                raw = merged
            elif authz_meta and not isinstance(raw, dict):
                raw = {"data": raw, **authz_meta}
        if isinstance(raw, dict):
            for key in ("data", "results", "items", "rows"):
                if key in raw and isinstance(raw[key], list):
                    return raw[key]
        return raw

    # All-failed gate — single mutation-aware refuse (shared with ``_run_chat``).
    if all(isinstance(t, dict) and t.get("error") for t in completed_tools):
        from ai.engine_runtime import fail_reply_when_all_tools_failed
        return fail_reply_when_all_tools_failed(completed_tools)

    tool_summaries: list[str] = []
    for tool_result in completed_tools:
        tool_name = tool_result.get("tool_name", "unknown")
        raw_result = tool_result.get("result", {})
        if isinstance(raw_result, str):
            try:
                raw_result = json.loads(raw_result)
            except (TypeError, ValueError):
                pass
        if isinstance(raw_result, dict) and raw_result.get("unauthorized"):
            msg = raw_result.get("message") or "Not authorized for that lookup."
            tool_summaries.append(f"**{tool_name}**: {msg}")
            continue
        result_data = _normalize(tool_result.get("result", {}))
        if isinstance(result_data, dict) and result_data.get("unauthorized"):
            msg = result_data.get("message") or "Not authorized for that lookup."
            tool_summaries.append(f"**{tool_name}**: {msg}")
            continue
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
