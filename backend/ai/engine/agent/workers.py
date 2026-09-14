"""
P3.2: Worker fan-out — isolated contexts, artifact refs, parallel execution.

Workers are read-only agents dispatched by the orchestrator. Each worker
gets an isolated context (no access to conversation history or other
workers' state) and returns a lightweight artifact reference — not a full
agent trace. This keeps fan-out cheap and parallel-safe.

Architecture (ADR-001):
- Workers are declared in the AgentRegistry + AgentHandoff table.
- Only agents with an explicit handoff edge from the orchestrator are valid workers.
- Workers NEVER have delegate_to_workers in their tool set.
- Workers are time-boxed via asyncio.wait_for (AGENT_WORKER_TIMEOUT_SEC).
- Results are synthesized by the orchestrator via synthesize_worker_results.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ai.engine.core.config import get_settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger("pulse.agent.workers")


# ── Data types ───────────────────────────────────────────────────────────────


@dataclass
class WorkerTask:
    """A single sub-task dispatched to a worker agent."""

    agent_role: str
    task: str
    context_hints: dict | None = None


@dataclass
class WorkerArtifact:
    """Lightweight artifact reference returned by a worker.

    Contains only the summary/detail — not the full agent trace — to keep
    fan-out cheap and avoid context bloat in the orchestrator."""

    worker_role: str
    worker_id: str
    summary: str
    detail: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    error: str | None = None
    # P2-06c: guardrail outcomes observed while executing worker tool calls
    # (e.g. ["worker_tool_blocked", "blocked:call_host_api"]). Empty when the
    # worker made no tool calls or every call passed the boundary.
    guardrail_flags: list[str] = field(default_factory=list)


@dataclass
class FanOutResult:
    """Aggregate result from a delegate_to_workers call."""

    artifacts: list[WorkerArtifact] = field(default_factory=list)
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    worker_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def succeeded_count(self) -> int:
        return sum(1 for a in self.artifacts if a.error is None)

    @property
    def artifact_refs(self) -> list[dict]:
        """Return artifact refs in the format expected by synthesize_worker_results."""
        return [
            {
                "worker_role": a.worker_role,
                "worker_id": a.worker_id,
                "summary": a.summary,
                "detail": a.detail,
            }
            for a in self.artifacts
            if a.error is None
        ]


# ── Worker pool ──────────────────────────────────────────────────────────────


class WorkerPool:
    """Manages parallel worker execution with isolated contexts.

    Each worker runs in its own short-lived LLM session. Workers are
    read-only and return artifact references — never full traces.
    """

    def __init__(
        self,
        llm_client,
        db,
        instance_id: str,
        conversation_id: str,
        *,
        executor=None,
        instance_config: dict | None = None,
        knowledge_store=None,
    ):
        self._llm_client = llm_client
        self._db = db
        self._instance_id = instance_id
        self._conversation_id = conversation_id
        self._settings = get_settings()
        # P2-06c: the host executor provides the command-boundary seam
        # (``execute_worker_tools_via_boundary``) so a worker's tool calls are
        # routed through the 13-stage boundary instead of being dropped.
        self._executor = executor
        self._instance_config = instance_config or {}
        self._knowledge_store = knowledge_store

    async def fan_out(
        self,
        tasks: list[WorkerTask],
        *,
        agent_registry,  # AgentRegistry
        orchestrator_id: str,
        system_prompt: str = "",
        worker_budgets: list[int] | None = None,  # P3.4: per-worker token budgets
    ) -> FanOutResult:
        """Execute worker tasks in parallel with isolated contexts.

        Args:
            tasks: List of WorkerTask to execute in parallel.
            agent_registry: The AgentRegistry instance for handoff validation.
            orchestrator_id: The orchestrator agent's ID (for handoff validation).
            system_prompt: Base system prompt to seed worker contexts.

        Returns:
            FanOutResult with artifact refs, tokens, latency.
        """
        settings = self._settings
        max_workers = settings.AGENT_MAX_WORKERS
        timeout = settings.AGENT_WORKER_TIMEOUT_SEC

        if len(tasks) > max_workers:
            logger.warning(
                "Fan-out capped: %d tasks requested, max %d — truncating",
                len(tasks), max_workers,
            )
            tasks = tasks[:max_workers]

        if not tasks:
            return FanOutResult()

        logger.info(
            "Fan-out started: instance=%s workers=%d timeout=%ds",
            self._instance_id, len(tasks), timeout,
        )

        t0 = time.monotonic()

        # Run all workers in parallel with individual timeouts
        coros = [
            self._run_worker(
                task, agent_registry, orchestrator_id, system_prompt,
                budget=worker_budgets[i] if worker_budgets and i < len(worker_budgets) else None,
            )
            for i, task in enumerate(tasks)
        ]
        results: list[WorkerArtifact | None] = await asyncio.gather(*coros, return_exceptions=False)

        total_latency = (time.monotonic() - t0) * 1000
        artifacts = [r for r in results if r is not None]
        total_tokens = sum(a.tokens_used for a in artifacts)
        worker_ids = [a.worker_id for a in artifacts]
        errors = [a.error for a in artifacts if a.error]

        logger.info(
            "Fan-out complete: instance=%s workers=%d succeeded=%d failed=%d tokens=%d latency=%.0fms",
            self._instance_id, len(tasks), len(artifacts) - len(errors),
            len(errors), total_tokens, total_latency,
        )

        return FanOutResult(
            artifacts=artifacts,
            total_tokens=total_tokens,
            total_latency_ms=total_latency,
            worker_ids=worker_ids,
            errors=errors,
        )

    async def _run_worker(
        self,
        task: WorkerTask,
        agent_registry,
        orchestrator_id: str,
        system_prompt: str,
        budget: int | None = None,  # P3.4: per-worker token budget
    ) -> WorkerArtifact | None:
        """Run a single worker with isolated context and timeout.

        Returns a WorkerArtifact or None if the worker could not be dispatched.
        """
        settings = self._settings
        timeout = settings.AGENT_WORKER_TIMEOUT_SEC

        # Validate handoff edge
        workers = await agent_registry.get_workers_for(orchestrator_id)
        matching = [(agent, handoff) for agent, handoff in workers
                     if agent.role == task.agent_role and agent.is_active]

        if not matching:
            logger.warning(
                "Fan-out: no valid handoff orchestrator → %s (or agent inactive)",
                task.agent_role,
            )
            return WorkerArtifact(
                worker_role=task.agent_role,
                worker_id="",
                summary="",
                detail="",
                error=f"No valid handoff to role '{task.agent_role}'",
            )

        worker_agent, _handoff = matching[0]
        worker_id = worker_agent.id

        # P1-07: a stable, deterministic run id for this worker's tool calls.
        # Used both as the tool-event broadcast run id and as ``run_id`` in the
        # HookContext (rate-limit/budget hooks key off it).
        _worker_run_id = "worker-" + hashlib.sha1(
            f"{self._conversation_id}|{worker_id}|{task.agent_role}|{task.task}".encode()
        ).hexdigest()[:16]

        logger.debug(
            "Fan-out worker start: role=%s agent_id=%s guardrail=active is_worker=True",
            task.agent_role, worker_id[:8],
        )

        # Build isolated context — no conversation history, only task + hints
        worker_messages: list[dict] = []
        if system_prompt:
            worker_messages.append({"role": "system", "content": system_prompt})

        # Add context hints as a system message
        context_parts = [f"Task: {task.task}"]
        if task.context_hints:
            context_parts.append("Context hints:")
            for k, v in task.context_hints.items():
                context_parts.append(f"  {k}: {v}")
        worker_messages.append({"role": "system", "content": "\n".join(context_parts)})

        worker_messages.append({"role": "user", "content": task.task})

        # Get the worker's tool set — strip delegate_to_workers + synthesize_worker_results
        worker_tool_names = _resolve_tool_set(worker_agent)
        worker_tool_names = [
            t for t in worker_tool_names
            if t not in ("delegate_to_workers", "synthesize_worker_results")
        ]

        # Resolve full tool definitions from STATIC_TOOL_DEFINITIONS
        from ai.engine.agent.tools import STATIC_TOOL_DEFINITIONS
        worker_tools = [
            td for td in STATIC_TOOL_DEFINITIONS
            if td.get("function", {}).get("name") in worker_tool_names
        ]

        t0 = time.monotonic()
        try:
            from ai.engine.llm.router import route_chat

            # P3.4: Budget check — if no budget remains, skip the LLM call
            sub_budget_consumed = 0
            budget_exceeded = False
            if budget is not None and budget <= 0:
                logger.warning(
                    "Fan-out worker budget exhausted before call: role=%s",
                    task.agent_role,
                )
                return WorkerArtifact(
                    worker_role=task.agent_role,
                    worker_id=worker_id,
                    summary="",
                    detail="",
                    error=f"Worker budget exhausted ({budget} tokens allocated)",
                    tokens_used=0,
                    latency_ms=0.0,
                )

            response = await asyncio.wait_for(
                route_chat(
                    task="chat",
                    instance_id=self._instance_id,
                    conversation_id=self._conversation_id,
                    messages=worker_messages,
                    tools=worker_tools if worker_tools else None,
                    db=self._db,
                ),
                timeout=timeout,
            )

            content = response.get("content") or ""
            tokens = response.get("input_tokens", 0) + response.get("output_tokens", 0)
            sub_budget_consumed = tokens

            # ── P2-06c: execute the worker's tool calls THROUGH the boundary ──
            # The worker no longer builds a hook pipeline; instead the engine
            # delegates to the host executor's command-boundary seam, which
            # builds a ``Command`` per tool call and routes it through the
            # 13-stage boundary. A mutation is refused at the consent stage
            # (executor never runs); a read executes via the boundary closure.
            guardrail_flags: list[str] = []
            blocked_reasons: list[str] = []
            artifact_error: str | None = None
            tool_calls = response.get("tool_calls") or []

            if tool_calls:
                completed_tools = await asyncio.wait_for(
                    self._execute_worker_tools(
                        task=task,
                        tool_calls=tool_calls,
                        worker_run_id=_worker_run_id,
                    ),
                    timeout=timeout,
                )
                guardrail_flags, blocked_reasons = _collect_guardrail_outcome(completed_tools)

                tool_text = _render_worker_tool_results(completed_tools)
                if tool_text:
                    content = f"{content}\n\n{tool_text}" if content.strip() else tool_text

                # Only mark the whole artifact failed when the worker produced
                # NO usable tool result. A partial success keeps error=None but
                # still carries the block in ``guardrail_flags``.
                successful_tools = [t for t in completed_tools if not t.get("error")]
                if blocked_reasons and not successful_tools:
                    artifact_error = (
                        "Worker tool call(s) blocked by guardrail: "
                        + " | ".join(blocked_reasons)
                    )

            latency = (time.monotonic() - t0) * 1000

            # P3.4: Check if worker exceeded its budget
            if budget is not None:
                remaining = budget - tokens
                if remaining <= 0:
                    budget_exceeded = True
                    logger.warning(
                        "Fan-out worker budget exceeded: role=%s budget=%d used=%d",
                        task.agent_role, budget, tokens,
                    )

            # Build artifact reference — summary is first 200 chars of content
            summary = content[:200].strip()
            detail = content[:2000] if len(content) > 200 else content

            logger.debug(
                "Fan-out worker done: role=%s latency=%.0fms tokens=%d budget=%s blocked=%d",
                task.agent_role, latency, tokens,
                f"exceeded" if budget_exceeded else "ok",
                len(blocked_reasons),
            )

            return WorkerArtifact(
                worker_role=task.agent_role,
                worker_id=worker_id,
                summary=summary,
                detail=detail,
                tokens_used=tokens,
                latency_ms=latency,
                error=artifact_error,
                guardrail_flags=guardrail_flags,
            )

        except asyncio.TimeoutError:
            latency = (time.monotonic() - t0) * 1000
            logger.warning(
                "Fan-out worker timeout: role=%s timeout=%ds",
                task.agent_role, timeout,
            )
            return WorkerArtifact(
                worker_role=task.agent_role,
                worker_id=worker_id,
                summary="",
                detail="",
                error=f"Worker timed out after {timeout}s",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = (time.monotonic() - t0) * 1000
            logger.exception(
                "Fan-out worker error: role=%s error=%s",
                task.agent_role, exc,
            )
            return WorkerArtifact(
                worker_role=task.agent_role,
                worker_id=worker_id,
                summary="",
                detail="",
                error=str(exc),
                latency_ms=latency,
            )

    async def _execute_worker_tools(
        self,
        *,
        task: WorkerTask,
        tool_calls: list[dict],
        worker_run_id: str,
    ) -> list[dict]:
        """Run a worker's tool calls through the host command-boundary seam.

        The engine never imports the boundary — it delegates to the host
        executor's ``execute_worker_tools_via_boundary`` seam, which builds a
        ``Command`` per tool call and routes it through the 13-stage boundary.
        A worker mutation is refused at the consent stage (the boundary
        executor never runs); a read executes via the boundary closure. When
        no boundary seam is available the calls fail closed.
        """
        if (
            self._executor is None
            or not callable(getattr(self._executor, "execute_worker_tools_via_boundary", None))
        ):
            logger.error(
                "Fan-out worker boundary seam unavailable — blocking %d tool call(s)",
                len(tool_calls),
            )
            blocked: list[dict] = []
            for tc in tool_calls:
                name = tc.get("function", {}).get("name", "unknown")
                blocked.append({
                    "tool_name": name,
                    "tool_call_id": tc.get("id", ""),
                    "result": None,
                    "error": "worker tool execution unavailable (no boundary seam)",
                    "guardrail_flags": ["worker_tool_blocked", f"blocked:{name}"],
                })
            return blocked

        return await self._executor.execute_worker_tools_via_boundary(
            tool_calls=tool_calls,
            instance_id=self._instance_id,
            conversation_id=self._conversation_id,
            run_id=worker_run_id,
            host_user_id=getattr(self._executor, "host_user_id", None),
            knowledge_store=self._knowledge_store,
        )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _resolve_tool_set(agent) -> list[str]:
    """Resolve the tool set for an agent from its tool_set_json column.

    Returns a list of tool names. If tool_set_json is empty, returns the
    full STATIC_TOOL_DEFINITIONS tool names (minus orchestration tools).
    """
    import json

    if agent.tool_set_json:
        try:
            return json.loads(agent.tool_set_json)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "Invalid tool_set_json for agent %s — using empty tool set",
                agent.id[:8] if agent.id else "?",
            )
            return []

    # Default: all tools except orchestration
    from ai.engine.agent.tools import STATIC_TOOL_DEFINITIONS
    excluded = {"delegate_to_workers", "synthesize_worker_results"}
    return [
        td["function"]["name"] for td in STATIC_TOOL_DEFINITIONS
        if td["function"]["name"] not in excluded
    ]


# P1-07: ExecuteWitness prefixes every hook-cancelled tool result with this
# marker (see ``execute._execute_single_tool``). We key off it to classify a
# worker's tool result as a guardrail block rather than an ordinary error.
_GUARDRAIL_CANCEL_PREFIX = "Tool cancelled by guardrail:"


def _collect_guardrail_outcome(
    completed_tools: list[dict],
) -> tuple[list[str], list[str]]:
    """Extract guardrail flags + block reasons from executed worker tools.

    Returns ``(flags, blocked_reasons)`` where ``flags`` is de-duplicated and
    ``blocked_reasons`` holds the human-readable reason for each blocked call
    (a boundary refusal carrying ``worker_tool_blocked``, or a legacy hook
    cancellation). Non-guardrail tool errors are deliberately not treated as
    blocks.
    """
    flags: list[str] = []
    blocked_reasons: list[str] = []
    for tr in completed_tools:
        tr_flags = tr.get("guardrail_flags") or []
        flags.extend(tr_flags)
        err = tr.get("error") or ""
        if "worker_tool_blocked" in tr_flags or err.startswith(_GUARDRAIL_CANCEL_PREFIX):
            name = tr.get("tool_name", "tool")
            flags.append("worker_tool_blocked")
            flags.append(f"blocked:{name}")
            blocked_reasons.append(err)

    seen: set[str] = set()
    deduped = [f for f in flags if not (f in seen or seen.add(f))]
    return deduped, blocked_reasons


def _render_worker_tool_results(completed_tools: list[dict]) -> str:
    """Render executed worker tool results into a compact text block.

    Successful results and boundary/hook blocks and errors are both included
    so the ``WorkerArtifact`` reflects real read-only work — and, just as
    importantly, surfaces the fact that a mutation was blocked instead of
    swallowing it.
    """
    parts: list[str] = []
    for tr in completed_tools:
        name = tr.get("tool_name", "tool")
        if tr.get("error"):
            parts.append(f"[tool:{name}] blocked/failed — {tr['error']}")
        else:
            parts.append(f"[tool:{name}] {tr.get('result')}")
    return "\n".join(parts)
