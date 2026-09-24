"""W-5 — bounded self-heal proposals for ``observe`` nodes (ADR-0034).

Pure RULE_20 helpers: no Django / no LLM. The host journals the proposal
and injects repaired steps into ReActLoop. Mutations in the repaired
remainder still hit RULE_21 consent when executed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

__all__ = ["HealProposal", "propose_heal", "DEFAULT_MAX_HEALS"]

DEFAULT_MAX_HEALS = 1


@dataclass
class HealProposal:
    """Repaired remainder after a caught failure."""
    summary: str
    new_steps: list[Any] = field(default_factory=list)  # PlanStep-like
    gap_step_ids: list[int] = field(default_factory=list)
    journal_payload: dict = field(default_factory=dict)


def propose_heal(
    *,
    goal: str,
    failed_step: Any,
    failed_error: str | None,
    remaining_steps: Sequence[Any],
    next_step_id: int,
    max_new_steps: int = 6,
) -> HealProposal:
    """Build a repaired remainder that continues without the failed step.

    Strategy (deterministic, no LLM):
      1. Emit one non-mutation recovery step documenting the gap.
      2. Re-queue remaining steps with ``depends_on`` scrubbed of the failed
         step id so the graph can progress.
      3. Cap how many remaining steps are re-queued.
    """
    failed_id = int(getattr(failed_step, "step_id", -1))
    failed_intent = getattr(failed_step, "intent", "") or f"step {failed_id}"
    err = (failed_error or "unknown error")[:240]

    # Late import keeps this module free of planner circular imports at load.
    from ai.engine.cognition.plan.planner import PlanStep

    recovery = PlanStep(
        step_id=next_step_id,
        intent=(
            f"Recover after gap: '{failed_intent}' failed ({err}). "
            f"Continue toward: {goal[:200]}"
        ),
        tool_name=None,
        tool_args={},
        depends_on=[],
        is_mutation=False,
        agent_role="orchestrator",
    )

    repaired: list[Any] = [recovery]
    for step in list(remaining_steps)[: max(0, max_new_steps - 1)]:
        deps = list(getattr(step, "depends_on", None) or [])
        # A mutation must keep its dependency on the failed read so the
        # consent gate stays closed until that read is repaired.
        if not bool(getattr(step, "is_mutation", False)):
            deps = [d for d in deps if d != failed_id]
        # Recovery becomes an optional predecessor so ordering stays sensible.
        if recovery.step_id not in deps:
            deps = [recovery.step_id] + list(deps)
        repaired.append(
            PlanStep(
                step_id=int(getattr(step, "step_id")),
                intent=getattr(step, "intent", "") or "",
                tool_name=getattr(step, "tool_name", None),
                tool_args=dict(getattr(step, "tool_args", None) or {}),
                depends_on=deps,
                is_mutation=bool(getattr(step, "is_mutation", False)),
                agent_role=getattr(step, "agent_role", None) or "orchestrator",
                instructions=getattr(step, "instructions", None),
            )
        )

    summary = (
        f"Healed after step {failed_id} failed; "
        f"{len(repaired) - 1} remaining step(s) re-queued without that dependency."
    )
    payload = {
        "failed_step_id": failed_id,
        "failed_intent": failed_intent,
        "error": err,
        "recovery_step_id": recovery.step_id,
        "requeued_step_ids": [
            int(getattr(s, "step_id")) for s in repaired[1:]
        ],
        "summary": summary,
    }
    return HealProposal(
        summary=summary,
        new_steps=repaired,
        gap_step_ids=[failed_id],
        journal_payload=payload,
    )
