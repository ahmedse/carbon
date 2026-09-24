"""Agent discovery scope router — gate briefs/replies before planning.

Deterministic (no LLM): classifies Operator text so Agent discovery does not
over-help (force-fit leave → DQ, trivia → Carbon quiz). Chat remains the
advisor surface; Agent remains the planner.

Classes:
  PLAN_CLEAR   — in-scope outcome; discovery/LLM may proceed
  PLAN_AMBIG   — could be plan or transaction; show recommended cards
  ADVISORY     — Q&A / trivia → handoff Chat
  TRANSACTION  — personal leave / HR action → recommend leave path
  DIGRESSION   — mid-discovery topic switch (same as ADVISORY/TRANSACTION)
  ABUSE        — jailbreak / injection style → calm refuse
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai.engine.cognition.scope_route_i18n import (
    advisory_ar,
    bare_leave_ar,
    leave_compliance_ar,
    leave_personal_ar,
    plan_signal_ar,
)
from ai.engine.text.word_match import contains_any_phrase, has_any_word

_LEAVE_PERSONAL_PHRASES = (
    "i want leave", "i want annual leave", "i want time off", "i want timeoff",
    "i want vacation", "i want pto", "i want holiday",
    "i need leave", "i need annual leave", "i need time off", "i need vacation",
    "i need pto", "i need holiday",
    "i request leave", "i request annual leave", "i request time off",
    "i request vacation", "i request pto", "i request holiday",
    "requesting leave", "requesting annual leave", "requesting time off",
    "requesting vacation", "request leave", "request annual leave",
    "apply for leave", "apply for annual leave", "apply for time off",
    "apply for vacation", "apply for pto", "apply for holiday",
    "take leave", "take annual leave", "take time off", "take vacation",
    "take pto", "take holiday",
    "reporting an absence", "reporting absence", "report an absence", "report absence",
)
_LEAVE_COMPLIANCE_PHRASES = (
    "leave compliance", "leave risk", "leave variance", "leave report",
    "leave pack", "leave board", "absence rate",
)

_BARE_LEAVE_EN = frozenset({"leave", "time off", "time-off", "vacation", "pto"})
_ADVISORY_PHRASES = (
    "who is", "who are", "who was", "who were", "what is", "tell me about",
)
_ABUSE_PHRASES = (
    "ignore previous instructions", "ignore all previous instructions",
    "ignore prior instructions", "ignore all prior instructions",
    "jailbreak", "dan mode", "system prompt", "do anything now",
)
_PLAN_SIGNAL_WORDS = (
    "plan", "prepare", "build", "create", "export", "summarize", "analyse",
    "analyze", "report",
)
_PLAN_SIGNAL_PHRASES = ("board pack", "data quality", "dq rule")

PLANNABLE = frozenset({"PLAN_CLEAR", "PLAN_AMBIG"})


def _leave_personal(text: str) -> bool:
    return contains_any_phrase(text, _LEAVE_PERSONAL_PHRASES) or leave_personal_ar(text)


def _leave_compliance(text: str) -> bool:
    raw = text or ""
    return bool(
        contains_any_phrase(raw, _LEAVE_COMPLIANCE_PHRASES)
        or has_any_word(raw, ("absenteeism",))
        or (contains_any_phrase(raw, ("board pack",)) and has_any_word(raw, ("leave",)))
        or leave_compliance_ar(raw)
    )


def _bare_leave(text: str) -> bool:
    stripped = (text or "").strip().strip(".!?").casefold()
    return stripped in {w.casefold() for w in _BARE_LEAVE_EN} or bare_leave_ar(text)


def _advisory(text: str) -> bool:
    return contains_any_phrase(text, _ADVISORY_PHRASES) or advisory_ar(text)


def _plan_signal(text: str) -> bool:
    return (
        has_any_word(text, _PLAN_SIGNAL_WORDS)
        or contains_any_phrase(text, _PLAN_SIGNAL_PHRASES)
        or plan_signal_ar(text)
    )


@dataclass
class ScopeRoute:
    cls: str
    message: str
    recommended: str | None = None
    cards: list[dict[str, Any]] = field(default_factory=list)
    handoff_target: str | None = None  # chat | people | none
    plannable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "class": self.cls,
            "message": self.message,
            "recommended": self.recommended,
            "cards": self.cards,
            "handoff_target": self.handoff_target,
            "plannable": self.plannable,
        }


def _leave_cards(*, personal_primary: bool) -> list[dict[str, Any]]:
    return [
        {
            "id": "leave_request",
            "label": "Create a leave-request plan",
            "hint": "Stay in Agent — draft a reviewable plan you can edit before approving",
            "primary": personal_primary,
        },
        {
            "id": "compliance_report",
            "label": "Plan a leave-compliance report",
            "hint": "Agent will draft a reviewable board-pack plan",
            "primary": not personal_primary,
        },
        {
            "id": "handoff_chat",
            "label": "Ask in Chat instead",
            "hint": "Advice only — nothing is planned or changed",
            "primary": False,
        },
    ]


def scope_route(text: str, *, stage: str = "brief") -> ScopeRoute:
    """Classify *text* for Agent discovery (*stage* = brief|reply)."""
    raw = (text or "").strip()
    if not raw:
        return ScopeRoute(
            cls="PLAN_AMBIG",
            message="Describe the outcome you want Pulse to plan.",
            plannable=False,
            cards=[],
        )

    if contains_any_phrase(raw, _ABUSE_PHRASES):
        return ScopeRoute(
            cls="ABUSE",
            message=(
                "I can't help with that request. "
                "If you have a platform outcome to plan — a report, data-quality "
                "rule, or board pack — describe it in plain language."
            ),
            plannable=False,
            handoff_target="none",
        )

    if _leave_compliance(raw):
        return ScopeRoute(
            cls="PLAN_CLEAR",
            message="I'll treat this as a leave-compliance / board-pack plan.",
            recommended="compliance_report",
            plannable=True,
            cards=_leave_cards(personal_primary=False),
        )

    # Personal leave → recommend leave path (asymmetric vs compliance).
    # Loan / attendance must not fall into generic clarifying — they have
    # process dials (handled in plans_service.start_discovery short-circuit).
    if _leave_personal(raw) or _bare_leave(raw):
        # Loan/attendance briefs can contain "leave early" etc. — check first.
        from ai.engine.cognition.plan.process_dial import (
            is_personal_attendance_brief,
            is_personal_loan_brief,
        )

        if is_personal_loan_brief(raw) or is_personal_attendance_brief(raw):
            return ScopeRoute(
                cls="PLAN_CLEAR",
                message="",
                plannable=True,
            )
        personal = bool(_leave_personal(raw)) or bool(_bare_leave(raw))
        return ScopeRoute(
            cls="TRANSACTION" if personal else "PLAN_AMBIG",
            message=(
                "That sounds like a personal leave request. "
                "I can draft a reviewable leave-request plan here for you to edit "
                "and approve — or plan a leave-compliance board pack instead. "
                "Chat stays available if you only want advice."
            ),
            recommended="leave_request",
            plannable=False,
            handoff_target="chat",
            cards=_leave_cards(personal_primary=True),
        )

    # Loan / attendance without leave words — still plannable for dial short-circuit.
    try:
        from ai.engine.cognition.plan.process_dial import (
            is_personal_attendance_brief,
            is_personal_loan_brief,
        )

        if is_personal_loan_brief(raw) or is_personal_attendance_brief(raw):
            return ScopeRoute(
                cls="PLAN_CLEAR",
                message="",
                plannable=True,
            )
    except Exception:  # noqa: BLE001
        pass

    if _advisory(raw) and not _plan_signal(raw):
        return ScopeRoute(
            cls="ADVISORY" if stage == "brief" else "DIGRESSION",
            message=(
                "That's a question for Chat (advice only), not an Agent plan. "
                "Switch to Chat, or describe a concrete outcome to plan "
                "(for example a report or data-quality rule)."
            ),
            recommended="handoff_chat",
            plannable=False,
            handoff_target="chat",
            cards=[
                {
                    "id": "handoff_chat",
                    "label": "Switch to Chat",
                    "hint": "Answers and advice — nothing is created or changed",
                    "primary": True,
                },
                {
                    "id": "rewrite_brief",
                    "label": "Rewrite as a plan brief",
                    "hint": "Describe the outcome you want Agent to plan",
                    "primary": False,
                },
            ],
        )

    return ScopeRoute(
        cls="PLAN_CLEAR",
        message="",
        plannable=True,
    )


def status_for_route(route: ScopeRoute) -> str:
    """API ``status`` string for a non-plannable route."""
    if route.cls == "ABUSE":
        return "refused"
    if route.cls in ("ADVISORY", "DIGRESSION"):
        return "handoff_chat"
    if route.cls == "TRANSACTION":
        return "recommended"
    if route.cls == "PLAN_AMBIG" and not route.plannable:
        return "recommended"
    return "needs_input"
