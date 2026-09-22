"""Process-dial plan materialization — hybrid Agent task creation (Path B).

Contract
--------
* **Process dial owns the DAG spine** — which steps exist, consent, capabilities.
  Personal leave/loan never LLM-invent a random submit topology.
* **Deterministic slot fill owns codes/dates/amounts** — ``fill_write_body`` from
  the brief.
* **LLM is residual intelligence** — not used for leave/loan spines today;
  consent UI still asks only truly missing governed fields.
* **Host Plane A owns review** — lifecycle review/activate/verify stay
  Correspondence / Team SoD. Pulse Run covers the AI-runnable prefix only.

See ADR-0045 (planes), ADR-0046 (Chat handoff), QA PA-030 / E-LV-* / E-LN-*.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

logger = logging.getLogger("pulse.cognition.plan.process_dial")

PROCESS_LEAVE = "leave.request.lifecycle"
PROCESS_LEAVE_VERSION = "1.0"
PROCESS_LOAN = "loan.request.lifecycle"
PROCESS_LOAN_VERSION = "1.0"

_LEAVE_SLOTS: list[dict[str, Any]] = [
    {"field": "leave_type", "governed": True, "required": True},
    {"field": "start_date", "type": "date", "future": True, "required": True},
    {"field": "end_date", "type": "date", "future": True, "required": True},
    {"field": "days", "type": "days", "required": True},
]

_LOAN_SLOTS: list[dict[str, Any]] = [
    {"field": "loan_type", "governed": True, "required": True},
    {"field": "principal", "type": "amount", "required": True},
    {"field": "term_months", "type": "months", "required": True},
    {"field": "interest_rate", "type": "rate", "required": False},
    {"field": "start_date", "type": "date", "future": True, "required": True},
]

_LOAN_BRIEF = re.compile(
    r"\bloan\b|قرض|قروضي|أريد\s*قرض|اريد\s*قرض|تقديم\s*قرض",
    re.IGNORECASE,
)


def is_personal_leave_brief(utterance: str) -> bool:
    """True when Agent should materialize the leave process dial (not LLM DAG)."""
    from ai.engine.cognition.scope_route import (
        _BARE_LEAVE,
        _LEAVE_COMPLIANCE,
        _LEAVE_PERSONAL,
    )

    text = (utterance or "").strip()
    if not text:
        return False
    # Loan wins over leave when both words appear.
    if is_personal_loan_brief(text):
        return False
    if _LEAVE_COMPLIANCE.search(text):
        return False
    if _LEAVE_PERSONAL.search(text) or _BARE_LEAVE.search(text):
        return True
    return bool(
        re.search(
            r"\b(?:i\s+(?:want|need|request)|i'?d\s+like)\b.{0,48}\b"
            r"(?:annual\s+)?(?:leave|vacation|pto|time\s*off)\b",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    )


def is_personal_loan_brief(utterance: str) -> bool:
    """True when Agent should materialize the loan process dial (not LLM DAG)."""
    text = (utterance or "").strip()
    if not text:
        return False
    if not _LOAN_BRIEF.search(text):
        return False
    if re.search(
        r"\b(?:all\s+loans|loan\s+portfolio|board\s+pack|compliance)\b"
        r"|قروض\s*الموظفين",
        text,
        re.IGNORECASE,
    ):
        return False
    return True


def materialize_leave_request_plan(
    utterance: str,
    *,
    today: date | None = None,
):
    """Build a reviewable Plan from ``leave.request.lifecycle`` + brief slots."""
    from ai.engine.cognition.plan.planner import Plan, PlanPhase, PlanStep
    from ai.write_slots import fill_write_body

    brief = (utterance or "").strip()
    body = fill_write_body(
        {},
        slots=_LEAVE_SLOTS,
        text=brief,
        today=today or date.today(),
    )

    process_meta = {
        "process_id": PROCESS_LEAVE,
        "process_version": PROCESS_LEAVE_VERSION,
        "process_step": "submit",
        "capability": "leave.request.submit",
    }

    balance_step = PlanStep(
        step_id=0,
        intent="Check leave balance before submitting",
        tool_name="call_host_api",
        tool_args={
            "api_name": "get_my_leave_balance",
            "explanation": "Read remaining entitlement before the leave submit.",
            "_process": {
                **process_meta,
                "process_step": "prepare",
                "capability": "leave.request.submit",
                "role": "observe",
            },
        },
        depends_on=[],
        is_mutation=False,
        agent_role="orchestrator",
    )

    submit_args: dict[str, Any] = {
        "api_name": "submit_my_leave",
        "body": body,
        "explanation": (
            "Submit personal leave via leave.request.lifecycle (submit). "
            "Manager review continues in Team after you Approve here."
        ),
        "_process": process_meta,
    }
    submit_step = PlanStep(
        step_id=1,
        intent=_leave_submit_intent(brief, body),
        tool_name="call_host_api",
        tool_args=submit_args,
        depends_on=[0],
        is_mutation=True,
        agent_role="orchestrator",
    )

    grounded = [
        k for k in ("leave_type", "start_date", "end_date", "days")
        if body.get(k) not in (None, "")
    ]
    missing = [
        k for k in ("leave_type", "start_date", "end_date", "days")
        if k not in grounded
    ]

    synthesis = (
        "Leave request follows process dial leave.request.lifecycle: "
        "Pulse runs balance check then submit (consent). "
        "After you Approve submit, the request waits for your manager in Team "
        "(/team). Track status in My Leave — Pulse does not approve for them."
    )
    if missing:
        synthesis += (
            f" Ungrounded slots for consent: {', '.join(missing)} "
            "(operator fills on Approve; do not invent codes)."
        )

    plan = Plan(
        pattern="leave_request",
        steps=[balance_step, submit_step],
        synthesis_instruction=synthesis,
        source="process_dial",
        skill_name=PROCESS_LEAVE,
        needs_confirmation=True,
        phases=[
            PlanPhase(
                phase_id=0,
                name="Prepare",
                goal="Confirm entitlement",
                strategy="sequential",
                step_ids=[0],
            ),
            PlanPhase(
                phase_id=1,
                name="Submit",
                goal="Stage leave.request.submit for consent",
                strategy="sequential",
                step_ids=[1],
            ),
        ],
    )
    logger.info(
        "process_dial leave plan: grounded=%s missing=%s body_keys=%s",
        grounded,
        missing,
        sorted(body.keys()),
    )
    return plan


def materialize_loan_request_plan(
    utterance: str,
    *,
    today: date | None = None,
):
    """Build a reviewable Plan from ``loan.request.lifecycle`` + brief slots.

    Host review is manager then finance (Team) — Pulse only stages submit.
    """
    from ai.engine.cognition.plan.planner import Plan, PlanPhase, PlanStep
    from ai.write_slots import fill_write_body

    brief = (utterance or "").strip()
    body = fill_write_body(
        {},
        slots=_LOAN_SLOTS,
        text=brief,
        today=today or date.today(),
    )
    if body.get("interest_rate") in (None, ""):
        body["interest_rate"] = 0

    process_meta = {
        "process_id": PROCESS_LOAN,
        "process_version": PROCESS_LOAN_VERSION,
        "process_step": "submit",
        "capability": "loan.request.submit",
    }

    list_step = PlanStep(
        step_id=0,
        intent="Check existing loans before submitting",
        tool_name="call_host_api",
        tool_args={
            "api_name": "list_my_loans",
            "explanation": "Read current loans before staging a new request.",
            "_process": {
                **process_meta,
                "process_step": "prepare",
                "capability": "loan.request.submit",
                "role": "observe",
            },
        },
        depends_on=[],
        is_mutation=False,
        agent_role="orchestrator",
    )

    submit_args: dict[str, Any] = {
        "api_name": "submit_my_loan",
        "body": body,
        "explanation": (
            "Submit personal loan via loan.request.lifecycle (submit). "
            "Manager then finance review continues in Team after you Approve here."
        ),
        "_process": process_meta,
    }
    submit_step = PlanStep(
        step_id=1,
        intent=_loan_submit_intent(brief, body),
        tool_name="call_host_api",
        tool_args=submit_args,
        depends_on=[0],
        is_mutation=True,
        agent_role="orchestrator",
    )

    required = ("loan_type", "principal", "term_months", "start_date")
    grounded = [k for k in required if body.get(k) not in (None, "")]
    missing = [k for k in required if k not in grounded]

    synthesis = (
        "Loan request follows process dial loan.request.lifecycle: "
        "Pulse lists existing loans then stages submit (consent). "
        "After you Approve, Team runs manager then finance review — "
        "Pulse does not approve. Track status in My Requests."
    )
    if missing:
        synthesis += (
            f" Ungrounded slots for consent: {', '.join(missing)} "
            "(operator fills on Approve; do not invent codes)."
        )

    plan = Plan(
        pattern="loan_request",
        steps=[list_step, submit_step],
        synthesis_instruction=synthesis,
        source="process_dial",
        skill_name=PROCESS_LOAN,
        needs_confirmation=True,
        phases=[
            PlanPhase(
                phase_id=0,
                name="Prepare",
                goal="List existing loans",
                strategy="sequential",
                step_ids=[0],
            ),
            PlanPhase(
                phase_id=1,
                name="Submit",
                goal="Stage loan.request.submit for consent",
                strategy="sequential",
                step_ids=[1],
            ),
        ],
    )
    logger.info(
        "process_dial loan plan: grounded=%s missing=%s body_keys=%s",
        grounded,
        missing,
        sorted(body.keys()),
    )
    return plan


def _leave_submit_intent(brief: str, body: dict[str, Any]) -> str:
    """Human intent line — product language, no engine jargon."""
    parts = ["Submit leave request"]
    lt = body.get("leave_type")
    if lt:
        parts.append(f"({lt})")
    start = body.get("start_date")
    end = body.get("end_date")
    days = body.get("days")
    if start and end and start == end:
        parts.append(f"on {start}")
    elif start and end:
        parts.append(f"{start} → {end}")
    if days not in (None, ""):
        parts.append(f"· {days} day(s)")
    if len(parts) == 1 and brief:
        snippet = re.sub(r"\s+", " ", brief).strip()[:80]
        parts.append(f"— {snippet}")
    return " ".join(parts)


def _loan_submit_intent(brief: str, body: dict[str, Any]) -> str:
    parts = ["Submit loan request"]
    lt = body.get("loan_type")
    if lt:
        parts.append(f"({lt})")
    principal = body.get("principal")
    if principal not in (None, ""):
        parts.append(f"· {principal}")
    term = body.get("term_months")
    if term not in (None, ""):
        parts.append(f"· {term} mo")
    start = body.get("start_date")
    if start:
        parts.append(f"from {start}")
    if len(parts) == 1 and brief:
        snippet = re.sub(r"\s+", " ", brief).strip()[:80]
        parts.append(f"— {snippet}")
    return " ".join(parts)


# Back-compat alias used by older imports/tests.
_submit_intent = _leave_submit_intent
