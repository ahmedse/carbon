from __future__ import annotations
from ai.engine.cognition.phrase_tables import T
from ai.engine.pack_vocab import V
V("t_agent_discovery_scope_router_gate_briefs")


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

_LEAVE_PERSONAL_PHRASES = T("scope_route.py::_LEAVE_PERSONAL_PHRASES")
_LEAVE_COMPLIANCE_PHRASES = T("scope_route.py::_LEAVE_COMPLIANCE_PHRASES")

_BARE_LEAVE_EN = T("scope_route.py::_BARE_LEAVE_EN")
_ADVISORY_PHRASES = T("scope_route.py::_ADVISORY_PHRASES")
_ABUSE_PHRASES = T("scope_route.py::_ABUSE_PHRASES")
_PLAN_SIGNAL_WORDS = T("scope_route.py::_PLAN_SIGNAL_WORDS")
_PLAN_SIGNAL_PHRASES = T("scope_route.py::_PLAN_SIGNAL_PHRASES")



def _leave_personal(text: str) -> bool:
    return contains_any_phrase(text, _LEAVE_PERSONAL_PHRASES) or leave_personal_ar(text)


def _leave_compliance(text: str) -> bool:
    raw = text or ""
    return bool(
        contains_any_phrase(raw, _LEAVE_COMPLIANCE_PHRASES)
        or has_any_word(raw, ("absenteeism",))
        or (contains_any_phrase(raw, ("board pack",)) and has_any_word(raw, (V("t_leave"),)))
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
            "label": V("t_create_a_leave_request_plan"),
            "hint": "Stay in Agent — draft a reviewable plan you can edit before approving",
            "primary": personal_primary,
        },
        {
            "id": "compliance_report",
            "label": V("t_plan_a_leave_compliance_report"),
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
            message=V("t_i_ll_treat_this_as_a"),
            recommended="compliance_report",
            plannable=True,
            cards=_leave_cards(personal_primary=False),
        )

    # Personal  → recommend  path (asymmetric vs compliance).
    #  /  must not fall into generic clarifying — they have
    # process dials (handled in plans_service.start_discovery short-circuit).
    if _leave_personal(raw) or _bare_leave(raw):
        # / briefs can contain " early" etc. — check first.
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
                V("t_that_sounds_like_a_personal_leave")
                + V("t_i_can_draft_a_reviewable_leave")
                + V("t_and_approve_or_plan_a_leave")
                + "Chat stays available if you only want advice."
            ),
            recommended="leave_request",
            plannable=False,
            handoff_target="chat",
            cards=_leave_cards(personal_primary=True),
        )

    #  /  without  words — still plannable for dial short-circuit.
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
