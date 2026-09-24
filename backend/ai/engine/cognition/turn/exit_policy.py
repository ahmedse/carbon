"""Staged-exit policy (ADR-0049 Q4).

Spine exits (refuse / handoff / bound ESS) use :func:`stage_exit` in
``runner.py`` — the harness ``staged_exits`` meter counts those only.

Soft gates Decision will own after the flip use :func:`stage_soft_exit``;
they stay on the legacy path and are skipped when ``PULSE_UNDERSTAND=v21``.
"""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T

from typing import Any

# Soft gates Decision owns after the v21 flip. Kept on legacy until shadow.
V21_SUPERSEDED_GATES = T("turn/exit_policy.py::V21_SUPERSEDED_GATES")

# Always stage on v21 (Chat write handoff, bound ESS GET, refuse).
V21_KEEP_GATES = T("turn/exit_policy.py::V21_KEEP_GATES")


def may_stage(gate: str) -> bool:
    """False only when v21 is on and ``gate`` is superseded by Decision."""
    from ai.engine.cognition.turn.understand import understand_mode

    if understand_mode() != "v21":
        return True
    g = str(gate or "")
    if g in V21_KEEP_GATES:
        return True
    if g.startswith("chat_") and g != "chat_clarify":
        return True
    return g not in V21_SUPERSEDED_GATES


def _append(staged: list, decision: str, gate: str, response: Any) -> bool:
    if not may_stage(gate):
        return False
    from ai.engine.cognition.turn.executor import StagedExit

    staged.append(StagedExit(decision, gate, response))
    return True


def stage_exit(
    staged: list,
    decision: str,
    gate: str,
    response: Any,
) -> bool:
    """Spine exit (counted by harness ``staged_exits`` in runner)."""
    return _append(staged, decision, gate, response)


def stage_soft_exit(
    staged: list,
    decision: str,
    gate: str,
    response: Any,
) -> bool:
    """Legacy soft exit; skipped under v21. Not counted as spine staged_exits."""
    return _append(staged, decision, gate, response)
