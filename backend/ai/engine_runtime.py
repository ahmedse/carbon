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

    # Phase 2b wires each task to a concrete engine capability.  Until then,
    # report the task as unavailable rather than fabricating a result.
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
