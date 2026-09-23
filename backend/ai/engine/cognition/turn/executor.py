"""Turn executor (L3) — one Arbiter decision, one returned body.

Gates only stage a response. ``pick_staged`` returns the body that
matches ``Arbiter.decide``. A gate that fired but lost does not speak.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class StagedExit:
    decision: str
    gate: str
    response: Any


def pick_staged(
    signals: Iterable[Any] | None,
    staged: list[StagedExit],
) -> StagedExit | None:
    """Return the staged body for the Arbiter winner, or None to continue."""
    if not staged:
        return None
    from ai.engine.cognition.turn.arbiter import Arbiter

    winner = Arbiter().decide(signals).value
    for item in staged:
        if item.decision == winner:
            return item
    return None
