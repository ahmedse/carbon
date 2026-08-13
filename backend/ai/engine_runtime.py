"""
In-process engine runtime — replaces the retired HTTP transport.

Phase 2 wires the vendored engine in-process: instead of POSTing tasks to the
external Pulse server over HTTP, Carbon calls this runtime directly.  It is
the in-process counterpart of Pulse's ``POST /instances/carbon/tasks`` and
``GET /instances/carbon/tasks/{id}`` endpoints.

Each task type will map to a concrete engine capability (KG query, turn
runner, LLM) in Phase 2b.  Until a task is wired, ``dispatch_task`` returns a
graceful ``pulse_unavailable`` result — fail-visible, never a fabricated
answer.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger("carbon.ai.engine_runtime")

# Task types the engine advertises (mirrors the retired Pulse task API).
MODULES: list[str] = [
    "dq.validate",
    "dq.suggest",
    "carbon.query.nl",
    "carbon.query.explain",
    "carbon.anomaly.detect",
    "carbon.anomaly.explain",
    "carbon.report.draft",
    "carbon.schema.analyze",
    "carbon.fix.suggest",
    "chat",
]


def _new_task_id() -> str:
    return f"inproc-{uuid.uuid4().hex[:16]}"


def _run_async(coro):
    """Run an async coroutine from a sync context.

    ``dispatch_task`` is sync (the AIProvider ABC is sync).  The vendored
    engine is async, so we bridge with ``asyncio.run``.  If we are already
    inside a running loop (rare — e.g. a caller awaiting a sync wrapper),
    run the coroutine on a worker thread to avoid nesting loops.
    """
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def _run_chat(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    """Run a single chat turn through the six-witness pipeline.

    This is the Phase 2b-1 proof path: the in-process engine's ``chat``
    task calls ``TurnPipelineRunner.run`` directly (no HTTP), writing
    durable ``TurnLedgerRow`` / ``LLMCallLog`` rows through the configured
    ``ai.store`` backend (DjangoStore in production).
    """
    from ai.engine.cognition.turn.runner import TurnPipelineRunner
    from ai.engine.core.database import get_session_factory

    message = payload.get("message") or ""
    conversation = payload.get("conversation_history") or {}
    conversation_id = (
        conversation.get("conversation_id")
        or f"conv-{uuid.uuid4().hex[:12]}"
    )
    history_messages = conversation.get("messages") or []

    factory = get_session_factory(instance_id)
    async with factory() as db:
        runner = TurnPipelineRunner(db=db)
        response, ledger = await runner.run(
            instance_id=instance_id,
            conversation_id=conversation_id,
            user_message=message,
            conversation_history=history_messages,
        )
        return {
            "status": "completed",
            "task_id": task_id,
            "result": {
                "content": response.text,
                "follow_up_questions": list(response.follow_ups or []),
                "execution_ms": int(ledger.total_latency_ms or 0),
            },
        }


def list_modules(instance_id: str = "carbon") -> dict[str, Any]:
    """Return the modules the in-process engine advertises."""
    return {"modules": [{"type": m} for m in MODULES]}


def dispatch_task(
    task_type: str,
    payload: dict[str, Any],
    *,
    instance_id: str = "carbon",
    timeout: int | None = None,
) -> dict[str, Any]:
    """Dispatch a task in-process.

    Returns a Pulse-shaped result dict::

        {"status": "completed"|"pending"|"failed"|"pulse_unavailable",
         "task_id": str,
         "result": {...} | "error": {"code": str, "message": str}}
    """
    if task_type not in MODULES:
        return {
            "status": "pulse_unavailable",
            "task_id": "",
            "error": {
                "code": "unknown_task",
                "message": f"Unknown task type: {task_type!r}",
            },
        }

    # Phase 2b-1: ``chat`` is wired end-to-end through the turn runner.
    # Fail-visible: any error returns ``pulse_unavailable`` — never a fake
    # answer.
    if task_type == "chat":
        task_id = _new_task_id()
        try:
            return _run_async(_run_chat(instance_id, payload, task_id))
        except Exception as exc:  # noqa: BLE001 - fail-visible contract
            logger.exception("chat dispatch failed for instance=%s", instance_id)
            return {
                "status": "pulse_unavailable",
                "task_id": task_id,
                "error": {
                    "code": "engine_error",
                    "message": f"chat failed: {exc}",
                },
            }

    # The remaining 8 task types are not yet wired (Phase 2b-2/2b-3).
    # Report them as unavailable rather than fabricating a result.
    return {
        "status": "pulse_unavailable",
        "task_id": _new_task_id(),
        "error": {
            "code": "not_wired",
            "message": (
                f"Task {task_type!r} is not yet wired to the in-process "
                "engine (Phase 2b)."
            ),
        },
    }


def get_task(task_id: str, *, timeout: int | None = None) -> dict[str, Any]:
    """Retrieve an in-process task's status."""
    return {
        "status": "pulse_unavailable",
        "error": {
            "code": "not_found",
            "message": f"No in-process task with id {task_id!r}",
        },
    }


__all__ = ["MODULES", "list_modules", "dispatch_task", "get_task"]
