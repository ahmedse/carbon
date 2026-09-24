"""Typed, deterministic routing before any draft LLM runs.

The router owns *what kind of turn this is*.  It does not execute tools or
render an answer.  Downstream witnesses may implement the committed route, but
must not reinterpret it from assistant prose or a synthetic user-message
prefix.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProcessMode(str, Enum):
    """Dial position the composer sent. All three seats are representable.

    ``AGENT`` exists so an Agent-originated turn can say so in transport
    metadata instead of arriving as ``ask`` and being told it is Chat.
    """

    ASK = "ask"
    PLAN = "plan"
    AGENT = "agent"

    @classmethod
    def parse(cls, value: str | None, message: str = "") -> "ProcessMode":
        raw = (value or "").strip().lower()
        for mode in cls:
            if raw == mode.value:
                return mode
        # Backward-compatible replay of old stored/eval turns.
        if (message or "").lstrip().startswith("[Pulse mode: Plan."):
            return cls.PLAN
        if (message or "").lstrip().startswith("[Pulse mode: Agent."):
            return cls.AGENT
        return cls.ASK


class RouteKind(str, Enum):
    NORMAL = "normal"
    REPORT_CLARIFY = "report_clarify"
    PLAN_PROCESS = "plan_process"
    RESTYLE = "restyle"
    FOLLOWUP = "followup"


@dataclass(frozen=True)
class OpenQuestion:
    """Structured question state; labels are presentation, values are routing."""

    kind: str
    prompt: str
    options: tuple[dict[str, str], ...] = ()
    slot: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "prompt": self.prompt,
            "options": [dict(item) for item in self.options],
            "slot": self.slot,
        }


@dataclass(frozen=True)
class RouteDecision:
    kind: RouteKind
    mode: ProcessMode
    message: str
    committed: bool = False
    reason: str = ""
    open_question: OpenQuestion | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    confirm: dict[str, Any] | None = None  # I2: confirm payload for open_question.confirm


_REPORT_OPTIONS = (
    {
        "id": "1",
        "label": "Pay distribution by band",
        "value": "Pay distribution by band with charts and tiers",
    },
    {
        "id": "2",
        "label": "Payroll run health",
        "value": "Payroll run health committed draft failed",
    },
    {
        "id": "3",
        "label": "Deductions & GOSI",
        "value": "Deductions and GOSI overview",
    },
    {
        "id": "4",
        "label": "Board-ready summary",
        "value": "Board-ready salary summary high level no row dumps",
    },
)


def _resolve_open_question(message: str, state: Any) -> str | None:
    question = getattr(state, "open_question", None) or {}
    options = question.get("options")
    if not isinstance(options, list) or not options:
        return None
    text = (message or "").strip()
    normalized = text.rstrip(".)").strip().lower()
    for item in options:
        if not isinstance(item, dict):
            continue
        aliases = {
            str(item.get("id") or "").strip().lower(),
            str(item.get("label") or "").strip().lower(),
        }
        aliases.update(
            str(v).strip().lower()
            for v in (item.get("aliases") or [])
            if str(v).strip()
        )
        if normalized in aliases:
            return str(item.get("value") or item.get("label") or "").strip() or None
    if normalized in {"all", "all 4", "all four", "all aspects", "كل الجوانب"}:
        values = [
            str(item.get("value") or "").strip()
            for item in options
            if isinstance(item, dict) and item.get("value")
        ]
        return "; ".join(values) if values else None
    return None


class TurnRouter:
    """Pure message + mode + ConversationState → one typed route."""

    def decide(
        self,
        *,
        message: str,
        process_mode: str | None,
        state: Any = None,
        history: list[dict] | None = None,
        last_results: list[dict] | None = None,
    ) -> RouteDecision:
        from ai.engine.cognition.plan.process_dial import strip_pulse_mode_prefix
        from ai.engine.cognition.turn.plan_dial import (
            is_restyle_request,
            plan_dial_process_brief,
        )
        from ai.engine.cognition.turn.plan_status import is_plan_status_utterance
        from ai.engine.cognition.turn.report_clarify import (
            try_report_clarify,
        )

        mode = ProcessMode.parse(process_mode, message)
        text = strip_pulse_mode_prefix(message or "").strip()

        # I2: Affirmation to pending open_question.confirm is a FOLLOWUP (deterministic).
        # Check this BEFORE other routes to ensure we never ask the same question twice.
        from ai.engine.cognition.state_store import resolve_against_state
        confirm_payload = resolve_against_state(text, state) if state else None
        if confirm_payload:
            return RouteDecision(
                kind=RouteKind.FOLLOWUP,
                mode=mode,
                message=text,
                committed=True,
                reason="open_question_confirm",
                confirm=confirm_payload,
            )

        resolved = _resolve_open_question(text, state)
        if resolved:
            return RouteDecision(
                kind=RouteKind.FOLLOWUP,
                mode=mode,
                message=resolved,
                reason="open_question_option",
            )

        if is_restyle_request(text) and history:
            return RouteDecision(
                kind=RouteKind.RESTYLE,
                mode=mode,
                message=text,
                committed=True,
                reason="restyle_previous_answer",
            )

        # Recall/status questions about an already-created plan are reads, not
        # new process briefs. Leave them uncommitted for the deterministic
        # plan-status witness.
        if is_plan_status_utterance(text):
            return RouteDecision(
                kind=RouteKind.NORMAL,
                mode=mode,
                message=text,
                reason="plan_status",
            )

        brief = plan_dial_process_brief(text, process_mode=mode.value)
        if brief:
            return RouteDecision(
                kind=RouteKind.PLAN_PROCESS,
                mode=mode,
                message=brief,
                committed=True,
                reason="governed_process_dial",
            )

        report_results = (
            last_results
            if last_results is not None
            else getattr(state, "last_results", None)
        )
        hit = (
            try_report_clarify(
                text,
                history=history,
                last_results=report_results,
            )
            if mode is ProcessMode.ASK
            else None
        )
        if hit is not None:
            question = OpenQuestion(
                kind="report_focus",
                prompt=str(hit.get("text") or ""),
                options=_REPORT_OPTIONS,
                slot="report_focus",
            )
            return RouteDecision(
                kind=RouteKind.REPORT_CLARIFY,
                mode=mode,
                message=text,
                committed=True,
                reason="broad_report",
                open_question=question,
            )

        return RouteDecision(
            kind=RouteKind.NORMAL,
            mode=mode,
            message=text,
        )
