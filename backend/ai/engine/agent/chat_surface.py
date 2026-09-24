"""Chat surface write-intent handoff (ADR-0046 · RULE_35 · G2).

Chat is advisory: host mutations must not stage ``pending_exec``. When a
write tool is attempted (or a write intent is detected with no honest path),
emit structured handoff actions — Agent Tasks and/or My ESS — instead of a
Confirm card the Chat UI cannot honor.

User-facing strings never mention ADR/G2/host-mutation jargon (RULE_23).
"""
from __future__ import annotations

import re
from typing import Any

from ai.engine.text.word_match import (
    contains_any_phrase,
    has_any_word,
    has_arabic_script,
    has_word,
)

from ai.engine.agent.chat_surface_i18n import (
    ATTENDANCE_INTENT_AR,
    ESS_TOPIC_AR,
    ESS_WRITE_VERB_AR,
    LEAVE_INTENT_AR,
    LOAN_INTENT_AR,
    MANAGER_REVIEW_AR,
    FIELD_LABELS,
    PROFILE_CHANGE_AR,
    any_needle,
)

_FIELD_LABELS = FIELD_LABELS

#: Surfaces that may stage host mutations / DQ creates.
AGENT_SURFACES = frozenset({"agent", "plan"})

#: Tools that may stage in Chat (personal memory only).
CHAT_WRITE_ALLOWLIST = frozenset({
    "learn_fact",
    "forget_fact",
})

#: Maps host api_name → My route + Agent process dial + labels.
_API_HANDOFF: dict[str, dict[str, str]] = {
    "submit_my_leave": {
        "my_route": "/my/leave",
        "my_label_en": "Open My Leave",
        "my_label_ar": "فتح إجازاتي",
        "process": "leave.request.lifecycle",
        "agent_label_en": "Open in Agent",
        "agent_label_ar": "فتح الوكيل",
        "topic_en": "leave request",
        "topic_ar": "طلب إجازة",
    },
    "submit_my_loan": {
        "my_route": "/my/requests",
        "my_label_en": "Open My Requests",
        "my_label_ar": "فتح طلباتي",
        "process": "loan.request.lifecycle",
        "agent_label_en": "Open in Agent",
        "agent_label_ar": "فتح الوكيل",
        "topic_en": "loan request",
        "topic_ar": "طلب قرض",
    },
    "submit_my_attendance_permission": {
        "my_route": "/my/attendance",
        "my_label_en": "Open My Attendance",
        "my_label_ar": "فتح الحضور",
        "process": "attendance.permission.lifecycle",
        "agent_label_en": "Open in Agent",
        "agent_label_ar": "فتح الوكيل",
        "topic_en": "attendance permission",
        "topic_ar": "استئذان حضور",
    },
    "submit_my_profile_change": {
        "my_route": "/my/requests",
        "my_label_en": "Open My Requests",
        "my_label_ar": "فتح طلباتي",
        "process": "",
        "agent_label_en": "Open in Agent",
        "agent_label_ar": "فتح الوكيل",
        "topic_en": "profile change",
        "topic_ar": "تغيير البيانات",
        "my_only": "1",
    },
}

#: Manager wants to act on Team inbox (approve leave/loan/attendance) — host /team.
_REVIEW_VERBS = ("approve", "reject", "review")
_REVIEW_OBJECTS = ("leave", "loan", "request", "inbox", "attendance", "permission")
_REVIEW_PHRASES = ("team inbox", "approvals inbox", "approval inbox")


_PROFILE_CHANGE_PHRASES = (
    "profile change", "update my phone", "update my email", "update my address",
    "update my iban", "update my bank", "update phone", "update email",
    "update address", "update iban", "update bank",
)


def _leave_intent(text: str) -> bool:
    raw = text or ""
    return bool(
        has_any_word(raw, ("leave", "vacation"))
        or contains_any_phrase(raw, ("annual leave", "time off"))
        or any_needle(raw, LEAVE_INTENT_AR)
    )


def _loan_intent(text: str) -> bool:
    raw = text or ""
    return bool(has_word(raw, "loan") or any_needle(raw, LOAN_INTENT_AR))


def _attendance_intent(text: str) -> bool:
    raw = text or ""
    return bool(
        has_any_word(raw, ("attendance", "permission", "excuse"))
        or any_needle(raw, ATTENDANCE_INTENT_AR)
    )


def _manager_review_intent(text: str) -> bool:
    from ai.engine.text.word_match import contains_any_phrase, has_gapped_words

    raw = text or ""
    if contains_any_phrase(raw, _REVIEW_PHRASES) or any(
        has_gapped_words(raw, verb, _REVIEW_OBJECTS, max_gap=8) for verb in _REVIEW_VERBS
    ) or any(has_gapped_words(raw, obj, _REVIEW_VERBS, max_gap=8) for obj in _REVIEW_OBJECTS):
        return True
    if not any_needle(raw, MANAGER_REVIEW_AR):
        return False
    return any(
        tok in raw.casefold()
        for tok in ("leave", "loan", "request", "attendance", "permission", "inbox")
    ) or any(n in raw for n in ("إجاز", "اجاز", "طلب", "استئذان", "قرض"))


def _profile_change_intent(text: str) -> bool:
    raw = text or ""
    if contains_any_phrase(raw, _PROFILE_CHANGE_PHRASES):
        return True
    if not any_needle(raw, ("تغيير", "تحديث")):
        return False
    return any_needle(raw, PROFILE_CHANGE_AR)


#: Internal flag only — never shown in UI copy / caveats.
INTERNAL_REASON = "chat_no_host_mutation"


def is_chat_surface(surface: str | None) -> bool:
    """True when host mutations must not stage."""
    s = (surface or "chat").strip().lower()
    if s in AGENT_SURFACES:
        return False
    return True  # fail-closed: unspecified → treat as Chat


def detect_locale(text: str | None) -> str:
    """Return ``ar`` when the utterance is predominantly Arabic script."""
    return "ar" if has_arabic_script(text or "") else "en"


def is_host_mutation_tool(tool_name: str, tool_args: dict | None) -> bool:
    """True for tools that create host/system side effects (not memory)."""
    name = (tool_name or "").strip()
    if name in CHAT_WRITE_ALLOWLIST:
        return False
    if name in {
        "create_dq_rule",
        "propose_dq_rule",
        "save_dq_rule",
        "plan_task",
        "approve_plan",
        "edit_plan",
    }:
        return True
    if name != "call_host_api":
        lower = name.lower()
        return lower.startswith(("submit_", "create_", "update_", "delete_", "post_"))
    args = tool_args or {}
    method = str(args.get("_method") or args.get("method") or "").upper()
    if method in ("POST", "PUT", "DELETE", "PATCH"):
        return True
    if args.get("body"):
        return True
    api = str(args.get("api_name") or args.get("api") or "").strip().lower()
    return api.startswith(("submit_", "create_", "update_", "delete_", "post_", "put_", "patch_"))


def _ess_topic(text: str) -> bool:
    raw = text or ""
    cf = raw.casefold()
    return bool(
        has_any_word(raw, ("leave", "loan", "attendance", "vacation", "permission"))
        or "submit_my_leave" in cf
        or "submit_my_loan" in cf
        or "submit_my_attendance" in cf
        or any_needle(raw, ESS_TOPIC_AR)
    )


def is_ess_write_intent(message: str) -> bool:
    """True for leave/loan/attendance *submit* asks (not balance reads).

    Used to skip orchestrator fan-out (those turns belong to process_dial /
    Chat handoff) without blocking other mutation or analytics fan-outs.
    """
    try:
        from ai.engine.cognition.plan.process_dial import strip_pulse_mode_prefix
        text = strip_pulse_mode_prefix(message or "").strip()
    except Exception:  # noqa: BLE001
        text = (message or "").strip()
    if not text or not _ess_topic(text):
        return False
    from ai.engine.cognition.turn.handoff_agent import is_slot_status_ask
    if is_slot_status_ask(text):
        return False
    # Explicit apply/request verbs (EN + AR) — covers loan/attendance that
    # ``_is_mutation_request`` historically missed (leave-only regex).
    if re.search(
        r"\b(?:apply|request|submit|want|need)\b.{0,40}\b"
        r"(?:leave|loan|attendance|vacation|permission)\b"
        r"|\b(?:leave|loan|attendance|vacation|permission)\b.{0,40}\b"
        r"(?:apply|request|submit)\b",
        text,
        re.IGNORECASE | re.DOTALL,
    ):
        return True
    if any_needle(text, ESS_WRITE_VERB_AR) and any_needle(
        text, ("إجاز", "اجاز", "قرض", "استئذان")
    ):
        return True
    try:
        from ai.engine.cognition.turn.intent import _is_mutation_request
    except Exception:  # noqa: BLE001
        return False
    return bool(_is_mutation_request(text))


def handoff_spec_for_api(api_name: str | None) -> dict[str, str]:
    api = (api_name or "").strip().lower()
    if api in _API_HANDOFF:
        return dict(_API_HANDOFF[api])
    return {
        "my_route": "/my",
        "my_label_en": "Open My",
        "my_label_ar": "فتح تطبيقاتي",
        "process": "",
        "agent_label_en": "Open in Agent",
        "agent_label_ar": "فتح الوكيل",
        "topic_en": "change",
        "topic_ar": "هذا التغيير",
    }


def build_plan_mode_switch_handoff(*, user_message: str = "") -> dict[str, Any]:
    """Ask mode must not create tasks — steer the user to the Plan dial.

    Used when Chat cancels ``plan_task`` (or similar). No Agent Tasks panel,
    no My route — just Switch to Plan so the same thread can draft a plan.
    """
    locale = detect_locale(user_message)
    if locale == "ar":
        headline = "وضع السؤال لا يُنشئ مهاماً"
        prose = [
            "وضع السؤال للإجابات والنصح فقط. "
            "بدّل المفتاح إلى «خطّة» لصياغة خطة قابلة للمراجعة من هذه المحادثة.",
        ]
        label = "التبديل إلى خطّة"
        summary = "بدّل إلى وضع الخطّة"
    else:
        headline = "Ask mode does not create tasks"
        prose = [
            "Ask is answers and advice only. "
            "Switch the dial to Plan to draft a reviewable plan from this thread.",
        ]
        label = "Switch to Plan"
        summary = "Switch to Plan mode"
    envelope = {
        "version": 1,
        "headline": headline,
        "prose": prose,
        "tables": [],
        "figures": [],
        "caveats": [],
        "sources": [],
        "actions": [],
    }
    return {
        "action": "chat_handoff",
        "reason": INTERNAL_REASON,
        "api_name": "",
        "tool_name": "plan_task",
        "draft": {},
        "process_hint": "plan",
        "actions": [
            {
                "type": "open_panel",
                "panel": "plan",
                "plan_id": "",
                "label": label,
                "summary": summary,
                "process_hint": "plan",
            },
        ],
        "message": f"**{headline}**\n\n{prose[0]}",
        "summary": summary,
        "envelope": envelope,
        "locale": locale,
        "requires_confirmation": False,
        "pending_exec": False,
        "caveats": [],
    }


def build_chat_handoff_result(
    tool_name: str,
    tool_args: dict | None,
    *,
    reason: str = "",
    user_message: str = "",
) -> dict[str, Any]:
    """Tool-result shape for a cancelled Chat mutation (not an error)."""
    name = (tool_name or "").strip()
    # plan_task in Chat/Ask → switch to Plan dial; never invent Agent/My CTAs.
    if name in {"plan_task", "approve_plan", "edit_plan"}:
        return build_plan_mode_switch_handoff(user_message=user_message)

    args = tool_args or {}
    api = str(args.get("api_name") or args.get("api") or "").strip()
    body = args.get("body") if isinstance(args.get("body"), dict) else {}
    locale = detect_locale(user_message)
    spec = handoff_spec_for_api(api)
    actions = build_handoff_actions(spec, locale=locale)
    message = handoff_copy(spec, draft=body, locale=locale)
    envelope = build_handoff_envelope(spec, draft=body, locale=locale)
    summary = (
        "Prepared leave draft — handoff to Agent or My"
        if "leave" in (spec.get("topic_en") or "")
        else "Prepared draft — handoff to Agent or My"
    )
    if locale == "ar":
        summary = "تم تجهيز مسودة — انتقل إلى الوكيل أو تطبيقاتي"
    return {
        "action": "chat_handoff",
        # Internal only — never copy into caveats / thought UI.
        "reason": INTERNAL_REASON,
        "api_name": api,
        "tool_name": tool_name,
        "draft": body,
        "process_hint": spec.get("process") or "",
        "actions": actions,
        "message": message,
        "summary": summary,
        "envelope": envelope,
        "locale": locale,
        "requires_confirmation": False,
        "pending_exec": False,
        # Explicit empty so envelope synthesizers have nothing to quote.
        "caveats": [],
    }


def handoff_spec_for_intent(user_message: str) -> dict[str, str]:
    text = user_message or ""
    if _manager_review_intent(text):
        return {
            "my_route": "/team",
            "my_label_en": "Open Team inbox",
            "my_label_ar": "فتح صندوق الفريق",
            "process": "",
            "agent_label_en": "Open in Agent",
            "agent_label_ar": "فتح الوكيل",
            "topic_en": "team approval",
            "topic_ar": "اعتماد الفريق",
            "manager_only": "1",
        }
    if _profile_change_intent(text):
        return handoff_spec_for_api("submit_my_profile_change")
    if _leave_intent(text):
        return handoff_spec_for_api("submit_my_leave")
    if _loan_intent(text):
        return handoff_spec_for_api("submit_my_loan")
    if _attendance_intent(text):
        return handoff_spec_for_api("submit_my_attendance_permission")
    return handoff_spec_for_api(None)


def _label(spec: dict[str, str], key: str, locale: str) -> str:
    suffix = "ar" if locale == "ar" else "en"
    return (
        spec.get(f"{key}_{suffix}")
        or spec.get(f"{key}_en")
        or spec.get(key)
        or ""
    )


def build_handoff_actions(spec: dict[str, str], *, locale: str = "en") -> list[dict[str, Any]]:
    """Machine-readable CTAs — Agent first, then My (AIMessageBubble order).

    Manager Team-review and My-only profile intents skip Agent.
    """
    route = (spec.get("my_route") or "").strip()
    if spec.get("manager_only") or spec.get("my_only"):
        if not route:
            return []
        summary = (
            "Approve or reject in Team"
            if spec.get("manager_only")
            else "Submit in the host ESS app"
        )
        return [{
            "type": "navigate",
            "route": route,
            "label": _label(spec, "my_label", locale),
            "summary": summary,
        }]
    actions: list[dict[str, Any]] = [
        {
            "type": "open_panel",
            "panel": "tasks",
            "plan_id": "",
            "label": _label(spec, "agent_label", locale),
            "summary": (
                f"Run via Agent"
                + (f" ({spec['process']})" if spec.get("process") else "")
            ),
            "process_hint": spec.get("process") or "",
        },
    ]
    if route:
        actions.append({
            "type": "navigate",
            "route": route,
            "label": _label(spec, "my_label", locale),
            "summary": "Submit in the host ESS app",
        })
    return actions


def handoff_copy(
    spec: dict[str, str],
    *,
    draft: dict | None = None,
    locale: str = "en",
) -> str:
    """Deterministic Chat reply — one next step, no fake Confirm (RULE_23)."""
    topic = _label(spec, "topic", locale)
    my_label = _label(spec, "my_label", locale)
    if spec.get("manager_only"):
        if locale == "ar":
            return (
                "اعتماد الطلبات يتم في تطبيق الفريق (Team)، وليس من الدردشة أو الوكيل.\n\n"
                f"افتح «{my_label}» للمراجعة والموافقة أو الرفض."
            )
        return (
            "Approvals happen in the Team app — not in Chat or Agent.\n\n"
            f"Open {my_label} to review and Approve or Decline."
        )
    if spec.get("my_only"):
        if locale == "ar":
            return (
                f"تغيير الملف الشخصي يُقدَّم من تطبيقاتي فقط (وليس عبر الوكيل).\n\n"
                f"افتح «{my_label}» وقدّم طلب التغيير هناك."
            )
        return (
            f"Profile changes are submitted in My — not via Agent.\n\n"
            f"Open {my_label} and submit the change there."
        )
    if locale == "ar":
        lines = [
            f"يمكنني مساعدتك في تجهيز {topic}، لكن الدردشة لا تُرسل ولا تغيّر "
            "السجلات في النظام.",
            "",
            "لإتمام التغيير استخدم أحد المسارين:",
            "• **الوكيل (Agent)** — بدّل إلى وضع الوكيل وشغّل العملية المعتمدة "
            "(التأكيد عند التشغيل).",
            f"• **تطبيقاتي** — افتح «{my_label}» وقدّم الطلب هناك.",
        ]
    else:
        lines = [
            f"I can help you prepare a {topic}, but Chat does not submit or "
            "change records in the system.",
            "",
            "To make the change, use one of these paths:",
            "• **Agent** — switch to Agent and run the governed process "
            "(consent on Run).",
            f"• **My** — open {my_label} and submit there.",
        ]
    if isinstance(draft, dict) and draft:
        bits = []
        for key, value in list(draft.items())[:6]:
            if value in (None, "", [], {}):
                continue
            en_lab, ar_lab = FIELD_LABELS.get(
                key, (key.replace("_", " "), key.replace("_", " "))
            )
            lab = ar_lab if locale == "ar" else en_lab
            bits.append(f"{lab}: {value}")
        if bits:
            prefix = "تفاصيل المسودة (لم تُرسل): " if locale == "ar" else "Draft details (not submitted): "
            lines.extend(["", prefix + "; ".join(bits) + "."])
    return "\n".join(lines)


def build_handoff_envelope(
    spec: dict[str, str],
    *,
    draft: dict | None = None,
    locale: str = "en",
) -> dict[str, Any]:
    """Typed envelope for handoff — draft table, **empty caveats** (RULE_23)."""
    topic = _label(spec, "topic", locale)
    if locale == "ar":
        headline = f"لا يمكن تقديم {topic} مباشرة من الدردشة"
        prose = [
            "جهّزنا التفاصيل أدناه. للدردشة دور استشاري فقط — "
            "أكمل عبر الوكيل أو من تطبيقاتي.",
        ]
        table_title = "مسودة الطلب"
        col_field, col_value = "الحقل", "القيمة"
        source_tool = "draft"
    else:
        headline = f"This {topic} cannot be submitted from Chat"
        prose = [
            "The details below are prepared as a draft only. "
            "Use Agent or My to submit.",
        ]
        table_title = "Draft request"
        col_field, col_value = "Field", "Value"
        source_tool = "draft"

    tables: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    if isinstance(draft, dict) and draft:
        rows: list[list[str]] = []
        for key, value in draft.items():
            if value in (None, "", [], {}):
                continue
            if isinstance(value, (dict, list)):
                continue
            en_lab, ar_lab = FIELD_LABELS.get(
                key, (str(key).replace("_", " "), str(key).replace("_", " "))
            )
            rows.append([ar_lab if locale == "ar" else en_lab, str(value)])
        if rows:
            tables.append({
                "title": table_title,
                "columns": [col_field, col_value],
                "rows": rows,
            })
            sources.append({
                "tool": source_tool,
                "rows_returned": len(rows),
                "truncated": False,
                "resolved_at": None,
            })

    return {
        "headline": headline,
        "prose": prose,
        "tables": tables,
        "charts": [],
        "caveats": [],  # never ADR / G2 / host-mutation jargon
        "sources": sources,
    }


def synthesize_intent_handoff(
    user_message: str,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """When Chat write intent had no tool call — copy + CTAs + envelope."""
    locale = detect_locale(user_message)
    spec = handoff_spec_for_intent(user_message)
    return (
        handoff_copy(spec, locale=locale),
        build_handoff_actions(spec, locale=locale),
        build_handoff_envelope(spec, locale=locale),
    )


def chat_mutation_narration(api_name: str | None = None) -> str:
    """Honest progress line for Chat when a mutation tool is about to be blocked."""
    api = (api_name or "").strip().lower()
    if "leave" in api:
        return "Preparing next steps for your leave…"
    if "loan" in api:
        return "Preparing next steps for your loan…"
    if "attendance" in api:
        return "Preparing next steps for attendance…"
    return "Checking how to complete this request…"
