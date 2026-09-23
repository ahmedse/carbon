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
PROCESS_LEAVE_VERSION = "1.1"
PROCESS_LOAN = "loan.request.lifecycle"
PROCESS_LOAN_VERSION = "1.1"
PROCESS_ATTENDANCE = "attendance.permission.lifecycle"
PROCESS_ATTENDANCE_VERSION = "1.1"

# Dates: no ``future: true`` — host ESS owns backdate window
# (``leave_guards.MAX_BACKDATED_LEAVE_DAYS``). Agent must not invent dates.
_LEAVE_SLOTS: list[dict[str, Any]] = [
    {"field": "leave_type", "governed": True, "required": True},
    {"field": "start_date", "type": "date", "required": True},
    {"field": "end_date", "type": "date", "required": True},
    {"field": "days", "type": "days", "required": True},
]

_LOAN_SLOTS: list[dict[str, Any]] = [
    {"field": "loan_type", "governed": True, "required": True},
    {"field": "principal", "type": "amount", "required": True},
    {"field": "term_months", "type": "months", "required": True},
    {"field": "interest_rate", "type": "rate", "required": False},
    {"field": "start_date", "type": "date", "future": True, "required": True},
]

_ATTENDANCE_SLOTS: list[dict[str, Any]] = [
    {"field": "permission_type", "governed": True, "required": True},
    {"field": "date", "type": "date", "future": True, "required": True},
    {"field": "hours", "type": "hours", "required": True},
]

_LOAN_BRIEF = re.compile(
    r"\bloan\b|قرض|قروضي|أريد\s*قرض|اريد\s*قرض|تقديم\s*قرض",
    re.IGNORECASE,
)
_ATTENDANCE_BRIEF = re.compile(
    r"\b(?:attendance\s+permission|short\s+hours|early\s+leave|permission)\b"
    r"|استئذان|إذن\s*حضور|اذن\s*حضور|ساعات\s*قصيرة",
    re.IGNORECASE,
)


_PULSE_PLAN_PREFIX = "[Pulse mode: Plan."

# A brief with a condition, a branch, or two things to do at once is a plan,
# not a form. The single-write slot-filler must never hijack it with
# "which loan type?" — the planner drafts the DAG and asks inside it.
_COMPOSITE_CONDITIONAL = re.compile(
    r"\bif\b[^.؟?!\n]{0,160}\b(?:then|stop|otherwise|else|don'?t|do\s+not|only)\b"
    r"|\b(?:otherwise|unless|else\s+stop)\b"
    r"|(?:إذا|اذا|إن\s+كان|ان\s+كان|لو|في\s+حال)[^.؟?!\n]{0,160}"
    r"(?:توقف|وإلا|والا|فلا|لا\s+تقدّ?م|لا\s+تطلب|إذا\s+لا|اذا\s+لا|إن\s+لم|ان\s+لم)"
    r"|إذا\s+لا\b|اذا\s+لا\b|وإلا\b|والا\b|إن\s+لم\b|ان\s+لم\b",
    re.IGNORECASE,
)
_COMPOSITE_PARALLEL = re.compile(
    r"\b(?:at\s+the\s+same\s+time|in\s+parallel|simultaneously|side\s+by\s+side)\b"
    r"|في\s+الوقت\s+نفسه|في\s+نفس\s+الوقت|بالتوازي|بشكل\s+متوازٍ?",
    re.IGNORECASE,
)
# "Check X, then submit Y" — a read that gates a write is a two-step plan.
_COMPOSITE_READ_THEN_WRITE = re.compile(
    r"\b(?:check|review|verify|look\s+at|confirm|see)\b[^.؟?!\n]{0,160}"
    r"\b(?:then|before|after\s+that|and\s+only\s+then)\b[^.؟?!\n]{0,160}"
    r"\b(?:submit|apply|request|file|raise)\b"
    r"|(?:راجع|تحقق|افحص|تأكد|اطّلع|اطلع|شوف)[^.؟?!\n]{0,160}"
    r"(?:ثم|بعدها|وبعد\s+ذلك|قبل\s+أن|قبل\s+ان)[^.؟?!\n]{0,160}"
    r"(?:قدّم|قدم|اطلب|أرسل|ارسل)",
    re.IGNORECASE,
)


def strip_pulse_mode_prefix(utterance: str) -> str:
    """Drop the ``[Pulse mode: …]`` engine hint so lexical checks see the user's words."""
    text = (utterance or "").lstrip()
    if text.startswith("[Pulse mode:"):
        end = text.find("]")
        if end != -1:
            return text[end + 1:].lstrip()
    return text


def is_plan_dial_turn(
    utterance: str,
    process_mode: str | None = None,
) -> bool:
    """True when structured transport (or legacy prefix) says Plan."""
    if (process_mode or "").strip().lower() in {"ask", "plan"}:
        return (process_mode or "").strip().lower() == "plan"
    return (utterance or "").lstrip().startswith(_PULSE_PLAN_PREFIX)


def is_composite_brief(utterance: str) -> bool:
    """True when the brief has a condition, branch, parallel ask, or read→write gate.

    «راجع قروضي ورصيد إجازتي في الوقت نفسه. إذا كان لدي قرض مفتوح، توقف. إذا لا،
    قدّم طلب قرض» is a plan with a guard, not a loan form missing its type.
    A plain «أريد قرض طوارئ ٥٠٠٠ لمدة ١٢ شهراً» is not composite.
    """
    text = strip_pulse_mode_prefix(utterance)
    if not text:
        return False
    return bool(
        _COMPOSITE_CONDITIONAL.search(text)
        or _COMPOSITE_PARALLEL.search(text)
        or _COMPOSITE_READ_THEN_WRITE.search(text)
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
    # More specific ESS dials win.
    if is_personal_loan_brief(text) or is_personal_attendance_brief(text):
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


def is_personal_attendance_brief(utterance: str) -> bool:
    """True when Agent should materialize attendance permission dial."""
    text = (utterance or "").strip()
    if not text:
        return False
    if is_personal_loan_brief(text):
        return False
    if not _ATTENDANCE_BRIEF.search(text):
        return False
    # Bare "permission" without attendance/استئذان context is too weak.
    if re.search(r"\bpermission\b", text, re.I) and not re.search(
        r"\b(?:attendance|hours|early|short|medical|official|emergency)\b"
        r"|استئذان|حضور|ساعة",
        text,
        re.I,
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

    # Composite brief: «راجع قروضي ورصيد إجازتي في الوقت نفسه. إذا كان لدي قرض
    # مفتوح توقف، إذا لا قدّم…» — the guard and the parallel read are part of
    # the plan the user asked for. Never ask "what is your salary?" instead.
    composite = is_composite_brief(brief)
    wants_leave_read = composite and bool(
        re.search(r"\b(?:leave|vacation|pto)\b|إجاز|اجاز", brief, re.IGNORECASE)
    )
    guard_no_open_loan = composite and bool(_COMPOSITE_CONDITIONAL.search(brief))

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

    prepare_steps = [list_step]
    prepare_ids = [0]
    if wants_leave_read:
        prepare_steps.append(PlanStep(
            step_id=1,
            intent="Read leave balance (requested alongside the loan check)",
            tool_name="call_host_api",
            tool_args={
                "api_name": "get_my_leave_balance",
                "explanation": "Parallel read the brief asked for; no write.",
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
        ))
        prepare_ids.append(1)
    submit_id = len(prepare_steps)

    submit_args: dict[str, Any] = {
        "api_name": "submit_my_loan",
        "body": body,
        "explanation": (
            "Submit personal loan via loan.request.lifecycle (submit). "
            "Manager then finance review continues in Team after you Approve here."
        ),
        "_process": process_meta,
    }
    submit_intent = _loan_submit_intent(brief, body)
    if guard_no_open_loan:
        submit_args["_guard"] = {
            "source_step": 0,
            "condition": "no_open_loans",
            "on_fail": "stop",
            "text": "Only if step 0 shows no open loan — otherwise stop.",
        }
        submit_intent += " — only if no open loan (stop otherwise)"
    submit_step = PlanStep(
        step_id=submit_id,
        intent=submit_intent,
        tool_name="call_host_api",
        tool_args=submit_args,
        depends_on=list(prepare_ids),
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
    if guard_no_open_loan:
        synthesis += (
            " Guard: the submit step runs only when the loan check shows no "
            "open loan; otherwise the plan stops before submitting."
        )
    if missing:
        synthesis += (
            f" Ungrounded slots for consent: {', '.join(missing)} "
            "(operator fills on Approve; do not invent codes)."
        )

    plan = Plan(
        pattern="loan_request",
        steps=[*prepare_steps, submit_step],
        synthesis_instruction=synthesis,
        source="process_dial",
        skill_name=PROCESS_LOAN,
        needs_confirmation=True,
        phases=[
            PlanPhase(
                phase_id=0,
                name="Prepare",
                goal=(
                    "List existing loans and read leave balance"
                    if wants_leave_read else "List existing loans"
                ),
                strategy="parallel" if wants_leave_read else "sequential",
                step_ids=list(prepare_ids),
            ),
            PlanPhase(
                phase_id=1,
                name="Submit",
                goal="Stage loan.request.submit for consent",
                strategy="sequential",
                step_ids=[submit_id],
            ),
        ],
    )
    logger.info(
        "process_dial loan plan: grounded=%s missing=%s body_keys=%s "
        "composite=%s guard=%s leave_read=%s",
        grounded,
        missing,
        sorted(body.keys()),
        composite,
        guard_no_open_loan,
        wants_leave_read,
    )
    return plan


def materialize_attendance_permission_plan(
    utterance: str,
    *,
    today: date | None = None,
):
    """Build a reviewable Plan from ``attendance.permission.lifecycle``."""
    from ai.engine.cognition.plan.planner import Plan, PlanPhase, PlanStep
    from ai.write_slots import fill_write_body

    brief = (utterance or "").strip()
    body = fill_write_body(
        {},
        slots=_ATTENDANCE_SLOTS,
        text=brief,
        today=today or date.today(),
    )

    process_meta = {
        "process_id": PROCESS_ATTENDANCE,
        "process_version": PROCESS_ATTENDANCE_VERSION,
        "process_step": "submit",
        "capability": "attendance.permission.submit",
    }

    list_step = PlanStep(
        step_id=0,
        intent="Check existing attendance permissions",
        tool_name="call_host_api",
        tool_args={
            "api_name": "list_my_attendance_permissions",
            "explanation": "Read current permissions before staging a new one.",
            "_process": {
                **process_meta,
                "process_step": "prepare",
                "capability": "attendance.permission.submit",
                "role": "observe",
            },
        },
        depends_on=[],
        is_mutation=False,
        agent_role="orchestrator",
    )

    submit_args: dict[str, Any] = {
        "api_name": "submit_my_attendance_permission",
        "body": body,
        "explanation": (
            "Submit personal attendance permission via "
            "attendance.permission.lifecycle (submit). "
            "Manager review continues in Team after you Approve here."
        ),
        "_process": process_meta,
    }
    submit_step = PlanStep(
        step_id=1,
        intent=_attendance_submit_intent(brief, body),
        tool_name="call_host_api",
        tool_args=submit_args,
        depends_on=[0],
        is_mutation=True,
        agent_role="orchestrator",
    )

    required = ("permission_type", "date", "hours")
    grounded = [k for k in required if body.get(k) not in (None, "")]
    missing = [k for k in required if k not in grounded]

    synthesis = (
        "Attendance permission follows process dial "
        "attendance.permission.lifecycle: Pulse lists existing permissions "
        "then stages submit (consent). After you Approve, your manager "
        "reviews in Team (/team). Track status in My Attendance."
    )
    if missing:
        synthesis += (
            f" Ungrounded slots for consent: {', '.join(missing)} "
            "(operator fills on Approve; do not invent codes)."
        )

    plan = Plan(
        pattern="attendance_permission",
        steps=[list_step, submit_step],
        synthesis_instruction=synthesis,
        source="process_dial",
        skill_name=PROCESS_ATTENDANCE,
        needs_confirmation=True,
        phases=[
            PlanPhase(
                phase_id=0,
                name="Prepare",
                goal="List existing permissions",
                strategy="sequential",
                step_ids=[0],
            ),
            PlanPhase(
                phase_id=1,
                name="Submit",
                goal="Stage attendance.permission.submit for consent",
                strategy="sequential",
                step_ids=[1],
            ),
        ],
    )
    logger.info(
        "process_dial attendance plan: grounded=%s missing=%s body_keys=%s",
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


def _attendance_submit_intent(brief: str, body: dict[str, Any]) -> str:
    parts = ["Submit attendance permission"]
    pt = body.get("permission_type")
    if pt:
        parts.append(f"({pt})")
    day = body.get("date")
    if day:
        parts.append(f"on {day}")
    hours = body.get("hours")
    if hours not in (None, ""):
        parts.append(f"· {hours}h")
    if len(parts) == 1 and brief:
        snippet = re.sub(r"\s+", " ", brief).strip()[:80]
        parts.append(f"— {snippet}")
    return " ".join(parts)


# Back-compat alias used by older imports/tests.
_submit_intent = _leave_submit_intent
