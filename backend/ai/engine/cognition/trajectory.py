"""P4.1 — Write denormalized trajectory rows from completed runs.

Every time a run completes (via TurnPipelineRunner), this module writes
one append-only row to the ``trajectory`` table.  The consolidation sweep
(P4.2) reads these rows for offline analysis.
"""

import json
import logging
import re

from ai.engine.core.models import Trajectory, Run, RunStep, TurnLedgerRow
from ai.store import first

logger = logging.getLogger("pulse.cognition.trajectory")

# ── Regex classifier for task_intent (no LLM — fast, deterministic) ────────

_INTENT_RULES: list[tuple[str, re.Pattern]] = [
    ("data_query", re.compile(
        r"\b(how many|count|list|show|display|what (are|is)|find|search|fetch|get|retrieve)\b",
        re.IGNORECASE,
    )),
    ("diagnostic", re.compile(
        r"\b(why|error|fail|broken|wrong|issue|problem|debug|trace|bug)\b",
        re.IGNORECASE,
    )),
    ("how_to", re.compile(
        r"\b(how (do|can|to|should)|steps|guide|tutorial|explain|walkthrough)\b",
        re.IGNORECASE,
    )),
    ("action", re.compile(
        r"\b(create|delete|update|change|modify|trigger|run|execute|start|stop|approve|reject)\b",
        re.IGNORECASE,
    )),
]


def _classify_intent(user_message: str) -> str:
    """Classify the user's task intent using regex rules. Returns the best match or 'clarification'."""
    for intent_name, pattern in _INTENT_RULES:
        if pattern.search(user_message):
            return intent_name
    return "clarification"


def _summarize_tool_args(args: dict | None, max_len: int = 80) -> str | None:
    """Truncated JSON serialisation of tool args for trajectory storage."""
    if not args:
        return None
    try:
        s = json.dumps(args, default=str)
        return s if len(s) <= max_len else s[:max_len - 3] + "..."
    except Exception:
        return None


async def write_trajectory(run_id: str, db) -> Trajectory | None:
    """Read Run + RunStep + TurnLedgerRow rows and write one Trajectory row.

    Idempotent: if a trajectory row already exists for this run_id, skips.

    Returns the Trajectory row or None if skipped/error.
    """
    # ── Idempotency check ──────────────────────────────────────────────────
    existing = first(await db.select(Trajectory, {"run_id": run_id}))
    if existing is not None:
        logger.debug("Trajectory already exists for run %s — skipping", run_id[:8])
        return None

    # ── Read Run row ───────────────────────────────────────────────────────
    run = first(await db.select(Run, {"id": run_id}))
    if run is None:
        logger.warning("Trajectory: run %s not found — skipping", run_id[:8])
        return None

    # ── Read RunStep rows ──────────────────────────────────────────────────
    steps = sorted(
        await db.select(RunStep, {"run_id": run_id}),
        key=lambda s: s.step_index,
    )

    # ── Read TurnLedgerRow rows ────────────────────────────────────────────
    ledger_rows = sorted(
        await db.select(TurnLedgerRow, {"turn_id": run_id}),
        key=lambda lr: lr.stage_index,
    )

    # ── Build tool_calls_json ──────────────────────────────────────────────
    tool_calls = []
    for step in steps:
        success = step.status == "completed" and step.error is None
        tool_calls.append({
            "tool_name": step.tool_name or "unknown",
            "args_summary": _summarize_tool_args(
                json.loads(step.tool_args_json) if step.tool_args_json else None
            ),
            "success": success,
            "latency_ms": step.latency_ms,
            "output_size": len(step.tool_output_json) if step.tool_output_json else 0,
        })

    # ── Build stages_json ──────────────────────────────────────────────────
    stages = []
    for lr in ledger_rows:
        stages.append({
            "stage": lr.stage,
            "verdict": lr.verdict or "pass",
            "latency_ms": lr.latency_ms,
            "tokens_used": lr.tokens_used or 0,
        })

    # ── Classify intent ────────────────────────────────────────────────────
    task_intent = _classify_intent(run.user_message)

    # ── Build total_latency from ledger rows ───────────────────────────────
    total_latency = None
    if ledger_rows:
        # Sum of all stage latencies
        total_latency = sum(
            lr.latency_ms for lr in ledger_rows if lr.latency_ms is not None
        )

    # ── Insert Trajectory row ──────────────────────────────────────────────
    trajectory = Trajectory(
        run_id=run_id,
        instance_id=run.instance_id,
        host_user_id=run.host_user_id,
        conversation_id=run.conversation_id,
        user_message=run.user_message,
        task_intent=task_intent,
        plan_json=run.plan_json,
        tool_calls_json=json.dumps(tool_calls) if tool_calls else None,
        stages_json=json.dumps(stages) if stages else None,
        status=run.status if run.status in ("completed", "failed", "cancelled") else "completed",
        final_response=run.final_response[:2000] if run.final_response else None,
        user_feedback=None,  # populated later via API
        total_tokens=run.total_tokens,
        total_latency_ms=total_latency,
        skill_candidates_json=None,  # populated by consolidation sweep
        consolidation_round=0,
        extracted_at=None,
    )

    db.add(trajectory)
    try:
        await db.flush()
        logger.debug("Trajectory written for run %s intent=%s status=%s",
                       run_id[:8], task_intent, trajectory.status)
    except Exception as exc:
        logger.warning("Trajectory: flush failed for run %s — %s", run_id[:8], exc)
        return None

    return trajectory
