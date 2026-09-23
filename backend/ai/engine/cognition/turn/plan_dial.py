"""Plan dial + personal ESS brief → deterministic process-dial plan (0 draft LLM).

ADR-0047 deterministic-first: when the composer dial is **Plan** and the brief
is a personal loan / leave / attendance request (composite or not), the plan
spine is owned by the process dial (``process_dial.materialize_*``). The LLM
draft must not replace it with ad-hoc reads and an invented clarify such as
"what is your monthly salary?".

Also owns the *restyle* follow-up («in arabic and in more details please»,
«بالعربي وبالتفصيل»): re-render the previous assistant answer — no tools, no
new facts, one LLM rewrite — instead of restarting discovery.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from ai.engine.cognition.plan.process_dial import (
    is_composite_brief,
    is_personal_attendance_brief,
    is_personal_leave_brief,
    is_personal_loan_brief,
    is_plan_dial_turn,
    strip_pulse_mode_prefix,
)
from ai.engine.cognition.turn.navigation import detect_lang

logger = logging.getLogger("pulse.cognition.turn.plan_dial")

_TO_EASTERN = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

#: «in arabic», «more details», «بالعربي», «بالتفصيل», «shorter», «elaborate».
_RESTYLE_RE = re.compile(
    r"("
    r"\bin\s+(?:arabic|english)\b"
    r"|\b(?:more|extra|further)\s+details?\b"
    r"|\bin\s+(?:more|greater)\s+detail\b"
    r"|\b(?:elaborate|expand(?:\s+on\s+(?:that|this|it))?)\b"
    r"|\b(?:shorter|briefer|summari[sz]e\s+(?:that|this|it))\b"
    r"|\b(?:translate|say|repeat|write|explain)\s+(?:that|this|it)\b"
    r"|بالعرب|بالإنجليز|بالانجليز|بالتفصيل|أكثر\s+تفصيل|اكثر\s+تفصيل"
    r"|بتفصيل\s+أكثر|بتفصيل\s+اكثر|وضّح\s+أكثر|وضح\s+اكثر|أعد\s+الصياغة|اعد\s+الصياغة"
    r"|باختصار|مختصر"
    r")",
    re.IGNORECASE,
)

#: A restyle carries no new task content: no amounts, no ESS verbs.
_NEW_CONTENT_RE = re.compile(
    r"\d|[٠-٩]"
    r"|\b(?:submit|apply|request|loan|leave|attendance|salary|payroll|report)\b"
    r"|قرض|إجاز|اجاز|استئذان|راتب|رواتب|تقرير|قدّم|قدم|اطلب",
    re.IGNORECASE,
)


def plan_dial_process_brief(
    utterance: str,
    *,
    process_mode: str | None = None,
) -> str | None:
    """Return the bare brief when Plan dial + personal ESS process brief."""
    if not is_plan_dial_turn(utterance, process_mode):
        return None
    text = strip_pulse_mode_prefix(utterance).strip()
    if not text or len(text) > 1200:
        return None
    if is_restyle_request(text):
        return None
    # Read questions («كم رصيد إجازتي؟») are answers, not plans — even on Plan.
    from ai.engine.cognition.turn.handoff_agent import is_ess_write_utterance

    if not is_ess_write_utterance(text):
        return None
    if (
        is_personal_loan_brief(text)
        or is_personal_attendance_brief(text)
        or is_personal_leave_brief(text)
    ):
        return text
    return None


def is_restyle_request(utterance: str) -> bool:
    """True for «in arabic and in more details please»-style follow-ups."""
    text = strip_pulse_mode_prefix(utterance or "").strip()
    if not text or len(text) > 120:
        return False
    if not _RESTYLE_RE.search(text):
        return False
    return not _NEW_CONTENT_RE.search(text)


def restyle_target_lang(utterance: str) -> str:
    text = strip_pulse_mode_prefix(utterance or "")
    if re.search(r"\bin\s+arabic\b|بالعرب", text, re.IGNORECASE):
        return "ar"
    if re.search(r"\bin\s+english\b|بالإنجليز|بالانجليز", text, re.IGNORECASE):
        return "en"
    return "ar" if detect_lang(text) == "ar" else "en"


def restyle_wants_more_detail(utterance: str) -> bool:
    text = strip_pulse_mode_prefix(utterance or "")
    return bool(re.search(
        r"more\s+details?|in\s+(?:more|greater)\s+detail|elaborate|expand"
        r"|بالتفصيل|تفصيل|وضّح|وضح",
        text,
        re.IGNORECASE,
    ))


def last_assistant_answer(history: list[dict] | None) -> str:
    """Most recent non-empty assistant message, or ''."""
    for msg in reversed(history or []):
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        content = str(msg.get("content") or "").strip()
        if content:
            return content
    return ""


def build_restyle_messages(
    *,
    previous_answer: str,
    request: str,
    target_lang: str,
    more_detail: bool,
) -> list[dict]:
    """One rewrite instruction — same facts, no tools, no new questions."""
    lang_name = "Arabic" if target_lang == "ar" else "English"
    detail = (
        "Expand with more structure and explanation of each point"
        if more_detail else "Keep the same level of detail"
    )
    system = (
        "You rewrite an assistant answer for the same user. Rules:\n"
        f"- Output language: {lang_name} only.\n"
        f"- {detail}.\n"
        "- Keep every fact, number, name, step and condition exactly as in "
        "the original. Do NOT add new facts, numbers, options, or questions.\n"
        "- Do NOT ask what the topic is; the topic is the original answer.\n"
        "- Do NOT claim anything was submitted, created, or changed.\n"
        "- Markdown allowed (headings, bullets, numbered steps)."
    )
    user = (
        f"User request: {request}\n\n"
        "Original answer to rewrite:\n"
        "<<<\n"
        f"{previous_answer}\n"
        ">>>"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ── Plan answer rendering ──────────────────────────────────────────────────

_AR_STEP_BY_API = {
    "list_my_loans": "التحقق من قروضي الحالية (قراءة)",
    "get_my_leave_balance": "قراءة رصيد إجازتي (قراءة)",
    "list_my_leave": "قراءة إجازاتي (قراءة)",
    "list_my_attendance_permissions": "التحقق من استئذاناتي الحالية (قراءة)",
    "submit_my_loan": "تقديم طلب القرض",
    "submit_my_leave": "تقديم طلب الإجازة",
    "submit_my_attendance_permission": "تقديم طلب الاستئذان",
}
_EN_STEP_BY_API = {
    "list_my_loans": "Check my current loans (read)",
    "get_my_leave_balance": "Read my leave balance (read)",
    "list_my_leave": "Read my leave records (read)",
    "list_my_attendance_permissions": "Check my current attendance permissions (read)",
    "submit_my_loan": "Submit the loan request",
    "submit_my_leave": "Submit the leave request",
    "submit_my_attendance_permission": "Submit the attendance permission",
}
_AR_SLOT = {
    "principal": "المبلغ",
    "term_months": "المدة (شهر)",
    "loan_type": "نوع القرض",
    "start_date": "تاريخ البدء",
    "leave_type": "نوع الإجازة",
    "end_date": "تاريخ الانتهاء",
    "days": "الأيام",
    "permission_type": "نوع الاستئذان",
    "date": "التاريخ",
    "hours": "الساعات",
}
_EN_SLOT = {
    "principal": "amount",
    "term_months": "term (months)",
    "loan_type": "loan type",
    "start_date": "start date",
    "leave_type": "leave type",
    "end_date": "end date",
    "days": "days",
    "permission_type": "permission type",
    "date": "date",
    "hours": "hours",
}


def _eastern(value: Any) -> str:
    return str(value).translate(_TO_EASTERN)


def _step_line(step: dict, lang: str) -> str:
    args = step.get("tool_args") or {}
    api = str(args.get("api_name") or "")
    table = _AR_STEP_BY_API if lang == "ar" else _EN_STEP_BY_API
    label = table.get(api) or str(step.get("intent") or api or "-")
    body = args.get("body") if isinstance(args.get("body"), dict) else {}
    bound = {
        k: v for k, v in body.items()
        if v not in (None, "", 0) and k in (_AR_SLOT if lang == "ar" else _EN_SLOT)
    }
    if bound:
        names = _AR_SLOT if lang == "ar" else _EN_SLOT
        parts = []
        for k, v in bound.items():
            val = _eastern(v) if lang == "ar" else str(v)
            parts.append(f"{names[k]}: {val}")
        sep = "، " if lang == "ar" else ", "
        label += " — " + sep.join(parts)
    guard = args.get("_guard") if isinstance(args.get("_guard"), dict) else None
    if guard:
        label += (
            " — فقط إذا لم يكن لديّ قرض مفتوح (وإلا تتوقف الخطة)"
            if lang == "ar"
            else " — only if no open loan (otherwise the plan stops)"
        )
    return label


def _missing_slots(plan: dict) -> list[str]:
    for step in plan.get("steps") or []:
        args = step.get("tool_args") or {}
        api = str(args.get("api_name") or "")
        if not api.startswith("submit_"):
            continue
        body = args.get("body") if isinstance(args.get("body"), dict) else {}
        if api == "submit_my_loan":
            required = ("loan_type", "principal", "term_months", "start_date")
        elif api == "submit_my_leave":
            required = ("leave_type", "start_date", "end_date", "days")
        else:
            required = ("permission_type", "date", "hours")
        return [k for k in required if body.get(k) in (None, "")]
    return []


def render_plan_dial_answer(*, brief: str, plan: dict, lang: str) -> str:
    """Product copy for the drafted plan in the user's language (RULE_23)."""
    steps = [s for s in (plan.get("steps") or []) if isinstance(s, dict)]
    n = len(steps)
    plan_id = str(plan.get("id") or "")
    short_id = plan_id[:8]
    missing = _missing_slots(plan)
    composite = is_composite_brief(brief)

    if lang == "ar":
        lines = [
            f"**تمت صياغة الخطة {short_id}** — {_eastern(n)} خطوات، بانتظار موافقتك. "
            "لم يُنفَّذ أي شيء بعد.",
            "",
        ]
        for i, s in enumerate(steps, 1):
            lines.append(f"{_eastern(i)}. {_step_line(s, lang)}")
        lines.append("")
        if composite:
            lines.append(
                "**الشرط:** خطوة التقديم مربوطة بنتيجة القراءة — إذا ظهر قرض مفتوح "
                "تتوقف الخطة قبل التقديم."
            )
        if missing:
            names = "، ".join(_AR_SLOT.get(k, k) for k in missing)
            lines.append(f"**حقول تُستكمل عند الاعتماد:** {names} — لن أخترعها.")
        lines.append(
            "راجع الخطة واعتمدها من لوحة **المهام**؛ كل خطوة تقديم تطلب موافقتك "
            "قبل أن تصل إلى النظام، ثم تستمر المراجعة لدى مديرك في «فريقي»."
        )
        return "\n".join(lines)

    lines = [
        f"**Plan {short_id} drafted** — {n} steps, pending your approval. "
        "Nothing has run yet.",
        "",
    ]
    for i, s in enumerate(steps, 1):
        lines.append(f"{i}. {_step_line(s, lang)}")
    lines.append("")
    if composite:
        lines.append(
            "**Guard:** the submit step is tied to the read result — if an open "
            "loan shows up, the plan stops before submitting."
        )
    if missing:
        names = ", ".join(_EN_SLOT.get(k, k) for k in missing)
        lines.append(f"**Filled at approval:** {names} — I will not invent them.")
    lines.append(
        "Review and approve it in the **Tasks** panel; each submit step asks "
        "for your consent before it reaches the system, then your manager "
        "reviews in Team."
    )
    return "\n".join(lines)


def open_tasks_action(plan_id: str, lang: str) -> dict:
    return {
        "type": "open_panel",
        "panel": "tasks",
        "plan_id": str(plan_id or ""),
        "label": "افتح في المهام" if lang == "ar" else "Open in Tasks",
        "summary": (
            "راجع الخطة واعتمدها وشغّلها" if lang == "ar"
            else "Review, approve and run the plan"
        ),
    }
