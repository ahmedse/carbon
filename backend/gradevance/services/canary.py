"""Canary activation — never silently regrade a released cohort (RULE_32)."""
from __future__ import annotations

from dataclasses import dataclass

from gradevance.services.reliability import passes_reliability_gate


@dataclass
class CanaryResult:
    allowed: bool
    reason: str
    reliability: dict | None = None


def evaluate_canary(
    *,
    expert_labels: list,
    engine_labels: list,
    minimum_kappa: float = 0.6,
    held_out_n: int = 0,
    min_held_out: int = 5,
) -> CanaryResult:
    """Gate pack activation. Activation applies to *new* runs only."""
    if held_out_n < min_held_out:
        return CanaryResult(
            allowed=False,
            reason=f"held_out_n={held_out_n} below minimum {min_held_out}",
        )
    rel = passes_reliability_gate(expert_labels, engine_labels, minimum=minimum_kappa)
    if not rel["passed"]:
        return CanaryResult(
            allowed=False,
            reason=f"κ={rel['value']} below gate {minimum_kappa}",
            reliability=rel,
        )
    return CanaryResult(
        allowed=True,
        reason="Canary passed — activate for new runs only; no cohort rewrite.",
        reliability=rel,
    )
