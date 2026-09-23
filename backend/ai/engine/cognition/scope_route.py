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

import re
from dataclasses import dataclass, field
from typing import Any

# Personal leave / time-off (transaction — not a board-pack plan by default)
_LEAVE_PERSONAL = re.compile(
    r"("
    r"\b(i\s+(want|need|request)|request(ing)?|apply\s+for|take)\s+"
    r"(annual\s+)?(leave|time\s*off|vacation|pto|holiday)\b"
    r"|\b(أريد|ابغى|أبغى|عايز|عاوز|اريد)\s*.{0,12}(إجازة|اجازة|اجازه)"
    r"|(إجازة|اجازة|اجازه)\s*(من فضلك|لو سمحت)?"
    r"|report(?:ing)?\s+(?:an\s+)?absence"
    r"|الإبلاغ عن غياب|الابلاغ عن غياب|أبلغ عن غياب|ابلغ عن غياب"
    r")",
    re.IGNORECASE | re.UNICODE,
)

# Org analytics / compliance pack (Agent-plannable)
_LEAVE_COMPLIANCE = re.compile(
    r"("
    r"leave\s+(compliance|risk|variance|report|pack|board)"
    r"|board\s+pack.*leave"
    r"|absenteeism|absence\s+rate"
    r"|(تقرير|مخاطر|امتثال).{0,20}(إجازة|اجازة)"
    r"|(إجازة|اجازة).{0,20}(تقرير|مخاطر|امتثال|أكتوبر|october)"
    r")",
    re.IGNORECASE | re.UNICODE,
)

_BARE_LEAVE = re.compile(
    r"^[\s]*(leave|time\s*off|vacation|pto|إجازة|اجازة|اجازه)[\s.!؟?]*$",
    re.IGNORECASE | re.UNICODE,
)

_ADVISORY = re.compile(
    r"("
    r"\bwho\s+(is|are|was|were)\b"
    r"|\bwhat\s+is\b"
    r"|من\s+هو|من\s+هي|من\s+هم"
    r"|\btell\s+me\s+about\b"
    r"|عرفني|اشرح\s+لي"
    r")",
    re.IGNORECASE | re.UNICODE,
)

_ABUSE = re.compile(
    r"("
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions"
    r"|jailbreak|dan\s+mode"
    r"|system\s+prompt"
    r"|do\s+anything\s+now"
    r")",
    re.IGNORECASE,
)

_PLAN_SIGNAL = re.compile(
    r"("
    r"\b(plan|prepare|build|create|export|summarize|analyse|analyze|report|board\s+pack)\b"
    r"|بيانات|تقرير|خطة|جودة\s+بيانات|data\s+quality|dq\s+rule"
    r")",
    re.IGNORECASE | re.UNICODE,
)

PLANNABLE = frozenset({"PLAN_CLEAR", "PLAN_AMBIG"})


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

    if _ABUSE.search(raw):
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

    if _LEAVE_COMPLIANCE.search(raw):
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
    if _LEAVE_PERSONAL.search(raw) or _BARE_LEAVE.search(raw):
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
        personal = bool(_LEAVE_PERSONAL.search(raw)) or bool(_BARE_LEAVE.search(raw))
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

    if _ADVISORY.search(raw) and not _PLAN_SIGNAL.search(raw):
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
