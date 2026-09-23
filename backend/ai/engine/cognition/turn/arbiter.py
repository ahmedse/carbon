"""TurnDecision Arbiter (PV2-4A / 4B · ADR-0047 §4.1).

``PULSE_ARBITER=on`` (default after 4B): the recorded turn decision is
``Arbiter.decide``. ``shadow`` logs the comparison and keeps the legacy
label. ``legacy`` is the kill switch: no compare, caller decision stands.

Pre-S2 gates stage a body. ``pick_staged`` returns the Arbiter winner.
A loser that also fired does not speak. Precedence includes each gate's
signal so a one-gate exit agrees with its body.
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Iterable

logger = logging.getLogger("pulse.cognition.turn.arbiter")

# Documented precedence (first match wins).
_PRECEDENCE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("refuse", ("off_limits", "topic_guard")),
    ("memory_confirm", ("pending_confirm",)),
    ("process_brief", ("process_brief_early", "process_brief")),
    ("handoff_agent", ("chat_handoff",)),
    ("navigate", ("nav_fast_path", "nav_ground")),
    ("clarify", ("deixis", "chat_clarify")),
    ("tool_answer", ("weather_force", "tools_executed")),
    ("answer", ()),
)


class TurnDecision(str, Enum):
    REFUSE = "refuse"
    NAVIGATE = "navigate"
    CLARIFY = "clarify"
    HANDOFF_AGENT = "handoff_agent"
    ANSWER = "answer"
    TOOL_ANSWER = "tool_answer"
    MEMORY_CONFIRM = "memory_confirm"
    PROCESS_BRIEF = "process_brief"

    @classmethod
    def from_value(cls, value: str | None) -> "TurnDecision":
        raw = (value or "").strip() or "answer"
        for member in cls:
            if member.value == raw:
                return member
        return cls.ANSWER


def _fired_gates(signals: Iterable[Any] | None) -> set[str]:
    out: set[str] = set()
    for item in signals or []:
        if not isinstance(item, dict):
            continue
        if not item.get("fired"):
            continue
        gate = str(item.get("gate") or "").strip()
        if gate:
            out.add(gate)
    return out


class Arbiter:
    """Pure signal → TurnDecision. No I/O. No host imports."""

    def decide(self, signals: Iterable[Any] | None) -> TurnDecision:
        fired = _fired_gates(signals)
        for decision, gates in _PRECEDENCE:
            if not gates:
                continue
            if fired.intersection(gates):
                return TurnDecision.from_value(decision)
        return TurnDecision.ANSWER


def shadow_compare(legacy: str, signals: Iterable[Any] | None) -> dict:
    """Compare legacy decision to Arbiter. Never changes the executed path."""
    arbiter = Arbiter().decide(signals)
    legacy_norm = TurnDecision.from_value(legacy)
    agree = arbiter == legacy_norm
    payload = {
        "legacy": legacy_norm.value,
        "arbiter": arbiter.value,
        "agree": agree,
        "fired": sorted(_fired_gates(signals)),
    }
    logger.info(
        "[arbiter-shadow] legacy=%s arbiter=%s agree=%s fired=%s",
        payload["legacy"],
        payload["arbiter"],
        payload["agree"],
        payload["fired"],
    )
    return payload
