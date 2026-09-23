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
    ASK = "ask"
    PLAN = "plan"

    @classmethod
    def parse(cls, value: str | None, message: str = "") -> "ProcessMode":
        raw = (value or "").strip().lower()
        if raw == cls.PLAN.value:
            return cls.PLAN
        if raw == cls.ASK.value:
            return cls.ASK
        # Backward-compatible replay of old stored/eval turns.
        if (message or "").lstrip().startswith("[Pulse mode: Plan."):
            return cls.PLAN
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
        from ai.engine.cognition.turn.report_clarify import (
            build_report_clarify,
            is_broad_report_ask,
        )

        mode = ProcessMode.parse(process_mode, message)
        text = strip_pulse_mode_prefix(message or "").strip()

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

        brief = plan_dial_process_brief(text, process_mode=mode.value)
        if brief:
            return RouteDecision(
                kind=RouteKind.PLAN_PROCESS,
                mode=mode,
                message=brief,
                committed=True,
                reason="governed_process_dial",
            )

        has_report_context = bool(last_results) or bool(
            getattr(state, "last_results", None)
        )
        if mode is ProcessMode.ASK and is_broad_report_ask(text) and not has_report_context:
            hit = build_report_clarify(text)
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
