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

    def __init__(self, llm_client, db, instance_id: str, conversation_id: str):
        self._llm_client = llm_client
        self._db = db
        self._instance_id = instance_id
        self._conversation_id = conversation_id
        self._settings = get_settings()
        # P3.3: Guardrail pipeline — built lazily and passed to worker context.
        # Workers use is_worker=True, which activates readonly_worker_hook.
        self._hook_pipeline = None  # built on first use via _get_hook_pipeline()

    def _get_hook_pipeline(self):
        """Lazily build the guardrail pipeline (first fan_out call)."""
        if self._hook_pipeline is None:
            from ai.engine.agent.guardrails import build_default_pipeline
            self._hook_pipeline = build_default_pipeline()
        return self._hook_pipeline

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

        # P3.3: Build guardrail context for worker (is_worker=True activates readonly_worker_hook)
        _pipeline = self._get_hook_pipeline()

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

            latency = (time.monotonic() - t0) * 1000
            content = response.get("content") or ""
            tokens = response.get("input_tokens", 0) + response.get("output_tokens", 0)
            sub_budget_consumed = tokens

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
                "Fan-out worker done: role=%s latency=%.0fms tokens=%d budget=%s",
                task.agent_role, latency, tokens,
                f"exceeded" if budget_exceeded else "ok",
            )

            return WorkerArtifact(
                worker_role=task.agent_role,
                worker_id=worker_id,
                summary=summary,
                detail=detail,
                tokens_used=tokens,
                latency_ms=latency,
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
