"""W-3 — wait node timers / until-guards (pure, RULE_20).

A ``wait`` node holds the graph until either:

* ``duration_ms`` elapses (``meta.wait_ms`` / ``meta.duration_ms`` / ``timeout_ms``), or
* an optional ``until`` guard becomes true (``meta.until`` / ``meta.until_guard``).

Immediate waits (no duration, no until) satisfy instantly — preserves the
previous auto-advance behaviour for empty wait gateways.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai.engine.workflow.graph import WorkflowNode
from ai.engine.workflow.guards import GuardError, eval_guard

__all__ = [
    "WaitDecision",
    "wait_duration_ms",
    "wait_until_guard",
    "evaluate_wait",
]

# Soft ceiling so a misconfigured wait cannot stall a run forever in-process.
_MAX_SLEEP_MS = 300_000  # 5 minutes


@dataclass(frozen=True)
class WaitDecision:
    """Outcome of evaluating a wait node at a point in time."""

    satisfied: bool
    sleep_ms: int
    reason: str  # immediate | duration | until | pending


def wait_duration_ms(node: WorkflowNode | None) -> int:
    """Return configured wait duration in ms (0 = none)."""
    if node is None:
        return 0
    meta = node.meta or {}
    for key in ("wait_ms", "duration_ms", "delay_ms"):
        raw = meta.get(key)
        if raw is not None:
            try:
                return max(0, int(raw))
            except (TypeError, ValueError):
                return 0
    if node.timeout_ms is not None:
        try:
            return max(0, int(node.timeout_ms))
        except (TypeError, ValueError):
            return 0
    return 0


def wait_until_guard(node: WorkflowNode | None) -> str | None:
    """Optional until-condition expression (same grammar as edge guards)."""
    if node is None:
        return None
    meta = node.meta or {}
    raw = meta.get("until") or meta.get("until_guard")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def evaluate_wait(
    node: WorkflowNode,
    context: dict[str, Any] | None = None,
    *,
    elapsed_ms: int = 0,
) -> WaitDecision:
    """Decide whether a wait node may complete.

    Parameters
    ----------
    elapsed_ms
        Wall time already spent waiting (host tracks started_at).
    """
    duration = wait_duration_ms(node)
    until = wait_until_guard(node)
    ctx = context or {}
    elapsed = max(0, int(elapsed_ms or 0))

    # Until-guard wins when true (early wake).
    if until:
        try:
            if eval_guard(until, ctx):
                return WaitDecision(True, 0, "until")
        except GuardError:
            pass

    if duration <= 0 and not until:
        return WaitDecision(True, 0, "immediate")

    if duration > 0 and elapsed >= duration:
        return WaitDecision(True, 0, "duration")

    if duration > 0:
        remaining = min(duration - elapsed, _MAX_SLEEP_MS)
        return WaitDecision(False, remaining, "pending")

    # until-only and not yet true — host may poll; no sleep mandated.
    return WaitDecision(False, 0, "pending")
