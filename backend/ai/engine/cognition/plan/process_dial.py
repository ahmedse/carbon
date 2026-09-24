from __future__ import annotations
from ai.engine.cognition.phrase_tables import T
from ai.engine.pack_vocab import V
V("t_process_dial_plan_materialization_hybrid_agent")


import logging
import re
from datetime import date
from typing import Any

from ai.engine.cognition.plan.process_dial_i18n import (
    ATTENDANCE_BRIEF_AR,
    COMPOSITE_CONDITIONAL_AR,
    COMPOSITE_PARALLEL_AR,
    COMPOSITE_READ_WRITE_AR,
    LOAN_BRIEF_AR,
    any_needle,
)

logger = logging.getLogger("pulse.cognition.plan.process_dial")

PROCESS_LEAVE = V("t_leave_request_lifecycle")
PROCESS_LEAVE_VERSION = "1.1"
PROCESS_LOAN = V("t_loan_request_lifecycle")
PROCESS_LOAN_VERSION = "1.1"
PROCESS_ATTENDANCE = V("t_attendance_permission_lifecycle")
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

def _loan_brief(text: str) -> bool:
    from ai.engine.text.word_match import has_word

    raw = text or ""
    return bool(has_word(raw, V("t_loan_2")) or any_needle(raw, LOAN_BRIEF_AR))


def _attendance_brief(text: str) -> bool:
    from ai.engine.text.word_match import contains_any_phrase, has_any_word

    raw = text or ""
    return bool(
        has_any_word(raw, ("permission",))
        or contains_any_phrase(
            raw, (V("t_attendance_permission"), "short hours", V("t_early_leave")),
        )
        or any_needle(raw, ATTENDANCE_BRIEF_AR)
    )


_PULSE_PLAN_PREFIX = "[Pulse mode: Plan."

# A brief with a condition, a branch, or two things to do at once is a plan,
# not a form. The single-write slot-filler must never hijack it with
# "which  type?" — the planner drafts the DAG and asks inside it.
_COMPOSITE_CONDITIONAL = re.compile(
    r"\bif\b[^.\?\u061F!\n]{0,160}\b(?:then|stop|otherwise|else|don'?t|do\s+not|only)\b"
    r"|\b(?:otherwise|unless|else\s+stop)\b",
    re.IGNORECASE,
)
_COMPOSITE_PARALLEL_PHRASES = T("plan/process_dial.py::_COMPOSITE_PARALLEL_PHRASES")
# "Check X, then submit Y" — a read that gates a write is a two-step plan.
_COMPOSITE_READ_THEN_WRITE = re.compile(
    r"\b(?:check|review|verify|look\s+at|confirm|see)\b[^.\?\?!\n]{0,160}"
    r"\b(?:then|before|after\s+that|and\s+only\s+then)\b[^.\?\?!\n]{0,160}"
    r"\b(?:submit|apply|request|file|raise)\b",
    re.IGNORECASE,
)
def _composite_conditional(text: str) -> bool:
    raw = text or ""
    if _COMPOSITE_CONDITIONAL.search(raw):
        return True
    if not any_needle(raw, COMPOSITE_CONDITIONAL_AR):
        return False
    return any(n in raw for n in COMPOSITE_CONDITIONAL_AR[-8:])


def _composite_parallel(text: str) -> bool:
    from ai.engine.text.word_match import contains_any_phrase

    raw = text or ""
    return bool(
        contains_any_phrase(raw, _COMPOSITE_PARALLEL_PHRASES)
        or any_needle(raw, COMPOSITE_PARALLEL_AR)
    )


def _composite_read_then_write(text: str) -> bool:
    raw = text or ""
    if _COMPOSITE_READ_THEN_WRITE.search(raw):
        return True
    read_needles = COMPOSITE_READ_WRITE_AR[:6]
    gate_needles = COMPOSITE_READ_WRITE_AR[6:11]
    write_needles = COMPOSITE_READ_WRITE_AR[11:]
    return (
        any_needle(raw, read_needles)
        and any_needle(raw, gate_needles)
        and any_needle(raw, write_needles)
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
    """True when the resolved surface is the Chat Plan dial.

    ``Surface.resolve`` reads the structured dial first and only falls back to
    the retired ``[Pulse mode: …]`` prefix when replaying old transcripts.
    """
    from ai.engine.agent.surface import Surface

    return Surface.resolve(
        process_mode=process_mode, user_message=utterance or "",
    ) is Surface.CHAT_PLAN


def is_composite_brief(utterance: str) -> bool:
    V("t_true_when_the_brief_has_a")
    text = strip_pulse_mode_prefix(utterance)
    if not text:
        return False
    return bool(
        _composite_conditional(text)
        or _composite_parallel(text)
        or _composite_read_then_write(text)
    )


def is_personal_leave_brief(utterance: str) -> bool:
    V("t_true_when_agent_should_materialize_the")
    from ai.engine.cognition.scope_route import (
        _bare_leave,
        _leave_compliance,
        _leave_personal,
    )

    text = (utterance or "").strip()
    if not text:
        return False
    # More specific ESS dials win.
    if is_personal_loan_brief(text) or is_personal_attendance_brief(text):
        return False
    if _leave_compliance(text):
        return False
    if _leave_personal(text) or _bare_leave(text):
        return True
    return bool(
        re.search(
            r"\b(?:i\s+(?:want|need|request)|i'?d\s+like)\b.{0,48}\b"
            + V("t_annual_s_leave_vacation_pto_time"),
            text,
            re.IGNORECASE | re.DOTALL,
        )
    )


def is_personal_loan_brief(utterance: str) -> bool:
    V("t_true_when_agent_should_materialize_the_2")
    text = (utterance or "").strip()
    if not text:
        return False
    if not _loan_brief(text):
        return False
    if re.search(
        V("t_b_all_s_loans_loan_s")
        + V("t_قروض_s_الموظفين"),
        text,
        re.IGNORECASE,
    ):
        return False
    return True


def is_personal_attendance_brief(utterance: str) -> bool:
    V("t_true_when_agent_should_materialize_attendance")
    text = (utterance or "").strip()
    if not text:
        return False
    if is_personal_loan_brief(text):
        return False
    if not _attendance_brief(text):
        return False
    # Bare "permission" without /استئذان context is too weak.
    if re.search(r"\bpermission\b", text, re.I) and not re.search(
        V("t_b_attendance_hours_early_short_medical")
        + V("t_استئذان_حضور_ساعة"),
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
    V("t_build_a_reviewable_plan_from_leave")
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
        "capability": V("t_leave_request_submit"),
    }

    balance_step = PlanStep(
        step_id=0,
        intent=V("t_check_leave_balance_before_submitting"),
        tool_name="call_host_api",
        tool_args={
            "api_name": "get_my_leave_balance",
            "explanation": V("t_read_remaining_entitlement_before_the_leave"),
            "_process": {
                **process_meta,
                "process_step": "prepare",
                "capability": V("t_leave_request_submit"),
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
            V("t_submit_personal_leave_via_leave_request")
            + "Manager review continues in Team after you Approve here."
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
        V("t_leave_request_follows_process_dial_leave")
        + "Pulse runs balance check then submit (consent). "
        "After you Approve submit, the request waits for your manager in Team "
        + V("t_team_track_status_in_my_leave")
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
                goal=V("t_stage_leave_request_submit_for_consent"),
                strategy="sequential",
                step_ids=[1],
            ),
        ],
    )
    logger.info(
        V("t_process_dial_leave_plan_grounded_s"),
        grounded,
        missing,
        sorted(body.keys()),
    )
    return plan


def brief_requests_loan_submit(utterance: str) -> bool:
    V("t_true_when_the_brief_asks_to")
    text = strip_pulse_mode_prefix(utterance or "")
    if not text or not _loan_brief(text):
        return False
    if _composite_conditional(text) or _composite_read_then_write(text):
        return True
    if any_needle(text, (
        V("t_أريد_قرض"), V("t_اريد_قرض"), V("t_تقديم_قرض"), V("t_طلب_قرض"), "قدّم طلب", "قدم طلب",
    )):
        return True
    return bool(re.search(
        r"\b(?:i\s+(?:want|need)|i'?d\s+like|apply|submit|request|file|raise)\b"
        r".{0,64}\bloan\b",
        text,
        re.IGNORECASE | re.DOTALL,
    ))


def _materialize_loan_read_plan(brief: str):
    V("t_review_only_plan_list_loans_and")
    from ai.engine.cognition.plan.planner import Plan, PlanPhase, PlanStep

    wants_leave = bool(re.search(
        V("t_b_leave_vacation_pto_b_إجاز"),
        brief or "",
        re.IGNORECASE,
    ))
    steps = [
        PlanStep(
            step_id=0,
            intent=V("t_check_existing_loans_read_only_no"),
            tool_name="call_host_api",
            tool_args={
                "api_name": "list_my_loans",
                "explanation": V("t_the_brief_asked_to_review_loans"),
            },
            depends_on=[],
            is_mutation=False,
            agent_role="orchestrator",
        ),
    ]
    if wants_leave:
        steps.append(PlanStep(
            step_id=1,
            intent=V("t_read_leave_balance_read_only"),
            tool_name="call_host_api",
            tool_args={
                "api_name": "get_my_leave_balance",
                "explanation": "Parallel read the brief asked for; no write.",
            },
            depends_on=[],
            is_mutation=False,
            agent_role="orchestrator",
        ))
    step_ids = [s.step_id for s in steps]
    return Plan(
        pattern="ess_read",
        steps=steps,
        synthesis_instruction=(
            V("t_read_only_plan_list_the_employee")
            + (V("t_and_leave_balance") if wants_leave else "")
            + V("t_do_not_submit_a_loan_nothing")
        ),
        source="process_dial",
        skill_name=PROCESS_LOAN,
        needs_confirmation=True,
        phases=[
            PlanPhase(
                phase_id=0,
                name="Review",
                goal=V("t_read_loans_and_leave_no_submit"),
                strategy="parallel" if wants_leave else "sequential",
                step_ids=step_ids,
            ),
        ],
    )


def materialize_loan_request_plan(
    utterance: str,
    *,
    today: date | None = None,
):
    V("t_build_a_reviewable_plan_from_loan")
    from ai.engine.cognition.plan.planner import Plan, PlanPhase, PlanStep
    from ai.write_slots import fill_write_body

    brief = (utterance or "").strip()
    if not brief_requests_loan_submit(brief):
        return _materialize_loan_read_plan(brief)
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
        "capability": V("t_loan_request_submit"),
    }

    # Composite brief: «راجع قروضي ورصيد إجازتي في الوقت نفسه. إذا كان لدي 
    # مفتوح توقف، إذا لا قدّم…» — the guard and the parallel read are part of
    # the plan the user asked for. Never ask "what is your ?" instead.
    composite = is_composite_brief(brief)
    wants_leave_read = composite and bool(
        re.search(V("t_b_leave_vacation_pto_b_إجاز"), brief, re.IGNORECASE)
    )
    guard_no_open_loan = composite and _composite_conditional(brief)

    list_step = PlanStep(
        step_id=0,
        intent=V("t_check_existing_loans_before_submitting"),
        tool_name="call_host_api",
        tool_args={
            "api_name": "list_my_loans",
            "explanation": V("t_read_current_loans_before_staging_a"),
            "_process": {
                **process_meta,
                "process_step": "prepare",
                "capability": V("t_loan_request_submit"),
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
            intent=V("t_read_leave_balance_requested_alongside_the"),
            tool_name="call_host_api",
            tool_args={
                "api_name": "get_my_leave_balance",
                "explanation": "Parallel read the brief asked for; no write.",
                "_process": {
                    **process_meta,
                    "process_step": "prepare",
                    "capability": V("t_loan_request_submit"),
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
            V("t_submit_personal_loan_via_loan_request")
            + "Manager then finance review continues in Team after you Approve here."
        ),
        "_process": process_meta,
    }
    submit_intent = _loan_submit_intent(brief, body)
    if guard_no_open_loan:
        submit_args["_guard"] = {
            "source_step": 0,
            "condition": "no_open_loans",
            "on_fail": "stop",
            "text": V("t_only_if_step_0_shows_no"),
        }
        submit_intent += V("t_only_if_no_open_loan_stop")
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
        V("t_loan_request_follows_process_dial_loan")
        + V("t_pulse_lists_existing_loans_then_stages")
        + "After you Approve, Team runs manager then finance review — "
        "Pulse does not approve. Track status in My Requests."
    )
    if guard_no_open_loan:
        synthesis += (
            V("t_guard_the_submit_step_runs_only")
            + V("t_open_loan_otherwise_the_plan_stops")
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
                    V("t_list_existing_loans_and_read_leave")
                    if wants_leave_read else V("t_list_existing_loans")
                ),
                strategy="parallel" if wants_leave_read else "sequential",
                step_ids=list(prepare_ids),
            ),
            PlanPhase(
                phase_id=1,
                name="Submit",
                goal=V("t_stage_loan_request_submit_for_consent"),
                strategy="sequential",
                step_ids=[submit_id],
            ),
        ],
    )
    logger.info(
        V("t_process_dial_loan_plan_grounded_s")
        + "composite=%s guard=%s leave_read=%s",
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
    V("t_build_a_reviewable_plan_from_attendance")
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
        "capability": V("t_attendance_permission_submit"),
    }

    list_step = PlanStep(
        step_id=0,
        intent=V("t_check_existing_attendance_permissions"),
        tool_name="call_host_api",
        tool_args={
            "api_name": "list_my_attendance_permissions",
            "explanation": "Read current permissions before staging a new one.",
            "_process": {
                **process_meta,
                "process_step": "prepare",
                "capability": V("t_attendance_permission_submit"),
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
            V("t_submit_personal_attendance_permission_via")
            + V("t_attendance_permission_lifecycle_submit")
            + "Manager review continues in Team after you Approve here."
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
        V("t_attendance_permission_follows_process_dial")
        + V("t_attendance_permission_lifecycle_pulse_lists_exis")
        + "then stages submit (consent). After you Approve, your manager "
        + V("t_reviews_in_team_team_track_status")
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
                goal=V("t_stage_attendance_permission_submit_for_consent"),
                strategy="sequential",
                step_ids=[1],
            ),
        ],
    )
    logger.info(
        V("t_process_dial_attendance_plan_grounded_s"),
        grounded,
        missing,
        sorted(body.keys()),
    )
    return plan


def _leave_submit_intent(brief: str, body: dict[str, Any]) -> str:
    """Human intent line — product language, no engine jargon."""
    parts = [V("t_submit_leave_request")]
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
    parts = [V("t_submit_loan_request")]
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
    parts = [V("t_submit_attendance_permission")]
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
