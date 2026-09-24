"""Chat surface write-intent handoff (ADR-0046 · RULE_35 · G2).

Chat is advisory: host mutations must not stage ``pending_exec``. When a
write tool is attempted (or a write intent is detected with no honest path),
emit structured handoff actions — Agent Tasks and/or My ESS — instead of a
Confirm card the Chat UI cannot honor.

User-facing strings never mention ADR/G2/host-mutation jargon (RULE_23).
"""
from __future__ import annotations

from ai.engine.pack_vocab import V

import re
from typing import Any

from ai.engine.text.word_match import (
    contains_any_phrase,
    has_any_word,
    has_arabic_script,
    has_word,
)

from ai.engine.agent.surface import HandoffLoopError, Surface

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

#: Surfaces that may stage host mutations / DQ creates. Kept for callers that
#: still compare raw strings; :class:`Surface` is the real answer.
AGENT_SURFACES = frozenset({"agent", "plan"})

#: Tools that may stage in Chat (personal memory only).
CHAT_WRITE_ALLOWLIST = frozenset({
    "learn_fact",
    "forget_fact",
})

#: Tools that draft instead of commit. Allowed on the drafting Chat surface
#: (``chat.plan``), cancelled on the answering one (``chat.ask``).
CHAT_DRAFT_TOOLS = frozenset({"plan_task"})

#: Maps host api_name → My route + Agent process dial + labels.
_API_HANDOFF: dict[str, dict[str, str]] = {
    "submit_my_leave": {
        "my_route": V("t_my_leave"),
        "my_label_en": V("t_open_my_leave"),
        "my_label_ar": "فتح إجازاتي",
        "process": V("t_leave_request_lifecycle"),
        "agent_label_en": "Open in Agent",
        "agent_label_ar": "فتح الوكيل",
        "topic_en": V("t_leave_request_2"),
        "topic_ar": V("t_طلب_إجازة"),
    },
    "submit_my_loan": {
        "my_route": "/my/requests",
        "my_label_en": "Open My Requests",
        "my_label_ar": "فتح طلباتي",
        "process": V("t_loan_request_lifecycle"),
        "agent_label_en": "Open in Agent",
        "agent_label_ar": "فتح الوكيل",
        "topic_en": V("t_loan_request_2"),
        "topic_ar": V("t_طلب_قرض"),
    },
    "submit_my_attendance_permission": {
        "my_route": V("t_my_attendance"),
        "my_label_en": V("t_open_my_attendance"),
        "my_label_ar": "فتح الحضور",
        "process": V("t_attendance_permission_lifecycle"),
        "agent_label_en": "Open in Agent",
        "agent_label_ar": "فتح الوكيل",
        "topic_en": V("t_attendance_permission"),
        "topic_ar": V("t_استئذان_حضور"),
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

#: Manager wants to act on Team inbox (approve //) — host /team.
_REVIEW_VERBS = ("approve", "reject", "review")
_REVIEW_OBJECTS = (V("t_leave"), V("t_loan_2"), "request", "inbox", V("t_attendance"), "permission")
_REVIEW_PHRASES = ("team inbox", "approvals inbox", "approval inbox")


_PROFILE_CHANGE_PHRASES = (
    "profile change", "update my phone", "update my email", "update my address",
    "update my iban", "update my bank", "update phone", "update email",
    "update address", "update iban", "update bank",
)


def _leave_intent(text: str) -> bool:
    raw = text or ""
    return bool(
        has_any_word(raw, (V("t_leave"), V("t_vacation")))
        or contains_any_phrase(raw, (V("t_annual_leave"), "time off"))
        or any_needle(raw, LEAVE_INTENT_AR)
    )


def _loan_intent(text: str) -> bool:
    raw = text or ""
    return bool(has_word(raw, V("t_loan_2")) or any_needle(raw, LOAN_INTENT_AR))


def _attendance_intent(text: str) -> bool:
    raw = text or ""
    return bool(
        has_any_word(raw, (V("t_attendance"), "permission", "excuse"))
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
        for tok in (V("t_leave"), V("t_loan_2"), "request", V("t_attendance"), "permission", "inbox")
    ) or any(n in raw for n in ("إجاز", "اجاز", "طلب", "استئذان", V("t_قرض")))


def _profile_change_intent(text: str) -> bool:
    raw = text or ""
    if contains_any_phrase(raw, _PROFILE_CHANGE_PHRASES):
        return True
    if not any_needle(raw, ("تغيير", "تحديث")):
        return False
    return any_needle(raw, PROFILE_CHANGE_AR)


#: Internal flag only — never shown in UI copy / caveats.
INTERNAL_REASON = "chat_no_host_mutation"


def is_chat_surface(
    surface: str | Surface | None,
    process_mode: str | None = None,
) -> bool:
    """True when host mutations must not stage.

    Fail-closed through :meth:`Surface.resolve`: an unknown or missing surface
    is Chat. Pass ``process_mode`` so a Plan-dial turn resolves to
    ``chat.plan`` instead of being flattened into ``chat.ask`` — both are Chat,
    but only the first can name the dial honestly in the handoff copy.
    """
    return Surface.resolve(surface, process_mode=process_mode).is_chat


def detect_locale(text: str | None) -> str:
    """Return ``ar`` when the utterance is predominantly Arabic script."""
    return "ar" if has_arabic_script(text or "") else "en"


#: Which Pulse surface a CTA sends the user to. ``navigate`` CTAs open the host
#: ESS app (My / Team), which is never a Pulse surface, so they never loop.
_CTA_TARGET: dict[str, Surface] = {
    "tasks": Surface.AGENT_RUN,
    "plan": Surface.CHAT_PLAN,
}


def cta_target_surface(action: dict[str, Any] | None) -> Surface | None:
    """The Pulse surface a CTA would move the user to, if any."""
    act = action or {}
    if str(act.get("type") or "") != "open_panel":
        return None
    return _CTA_TARGET.get(str(act.get("panel") or ""))


def handoff_problems(
    surface: str | Surface | None,
    actions: list[dict[str, Any]] | None,
) -> list[str]:
    """Ways a handoff would embarrass us, given where the user actually is.

    Two failures matter. A handoff built on a surface that can already stage
    the write means the guardrail cancelled something it should have passed. A
    CTA pointing at the current surface tells the user to go where they are —
    the "Open in Agent while the dial reads Agent" bug. Both are plumbing
    regressions, so they are reported by identity rather than by copy review.
    """
    current = Surface.resolve(surface)
    problems: list[str] = []
    if current.may_host_mutate:
        problems.append(
            f"write handoff built on {current.value}, which may stage the write itself"
        )
    for action in actions or []:
        if cta_target_surface(action) is current:
            problems.append(
                f"CTA {action.get('label') or action.get('panel')!r} "
                f"points at {current.value}, the surface already in use"
            )
    return problems


def assert_handoff_is_honest(
    surface: str | Surface | None,
    actions: list[dict[str, Any]] | None,
) -> None:
    """Raise when a handoff advises the surface the user is already on."""
    problems = handoff_problems(surface, actions)
    if problems:
        raise HandoffLoopError("; ".join(problems))


def verify_handoff(
    surface: str | Surface | None,
    actions: list[dict[str, Any]] | None,
) -> bool:
    """Production form of :func:`assert_handoff_is_honest` — log, do not raise.

    ``build_handoff_actions`` already drops self-referential CTAs, so a problem
    here means the surface reaching the builder was wrong. Users get the
    degraded-but-honest copy; we get a loud log instead of a support ticket.
    """
    problems = handoff_problems(surface, actions)
    if problems:
        import logging

        logging.getLogger(__name__).error(
            "Handoff would loop on its own surface: %s", "; ".join(problems),
        )
        return False
    return True


def is_host_mutation_tool(
    tool_name: str,
    tool_args: dict | None,
    *,
    surface: str | Surface | None = None,
) -> bool:
    """True for tools that create host/system side effects (not memory).

    ``surface`` matters for drafting tools: ``plan_task`` produces a reviewable
    Tasks-panel plan and nothing runs until Approve, so it is a legitimate
    ``chat.plan`` call and a cancelled one on ``chat.ask``. Committing tools
    (``approve_plan`` / ``edit_plan``) stay blocked on every Chat surface.
    """
    name = (tool_name or "").strip()
    if name in CHAT_WRITE_ALLOWLIST:
        return False
    if name in CHAT_DRAFT_TOOLS:
        return Surface.resolve(surface) is not Surface.CHAT_PLAN
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
        has_any_word(raw, (V("t_leave"), V("t_loan_2"), V("t_attendance"), V("t_vacation"), "permission"))
        or "submit_my_leave" in cf
        or "submit_my_loan" in cf
        or "submit_my_attendance" in cf
        or any_needle(raw, ESS_TOPIC_AR)
    )


def is_ess_write_intent(message: str) -> bool:
    V("t_true_for_leave_loan_attendance_submit")
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
    # Explicit apply/request verbs (EN + AR) — covers / that
    # ``_is_mutation_request`` historically missed (-only regex).
    if re.search(
        r"\b(?:apply|request|submit|want|need)\b.{0,40}\b"
        + V("t_leave_loan_attendance_vacation_permission_b")
        + V("t_b_leave_loan_attendance_vacation_permission")
        + r"(?:apply|request|submit)\b",
        text,
        re.IGNORECASE | re.DOTALL,
    ):
        return True
    if any_needle(text, ESS_WRITE_VERB_AR) and any_needle(
        text, ("إجاز", "اجاز", V("t_قرض"), "استئذان")
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


def build_plan_mode_switch_handoff(
    *,
    user_message: str = "",
    surface: str | Surface | None = None,
) -> dict[str, Any]:
    """Ask mode must not create tasks — steer the user to the Plan dial.

    Used when Chat cancels ``plan_task`` (or similar). No Agent Tasks panel,
    no My route — just Switch to Plan so the same thread can draft a plan.

    On the Plan dial itself there is nothing to switch to, so the CTA becomes
    the Tasks panel: approving or editing a plan is Agent's job, not Plan's.
    """
    locale = detect_locale(user_message)
    already_plan = Surface.resolve(surface) is Surface.CHAT_PLAN
    if locale == "ar":
        if already_plan:
            headline = "اعتماد الخطط يتم في الوكيل"
            prose = [
                "وضع الخطّة يصيغ الخطة فقط. "
                "افتح لوحة المهام لمراجعتها واعتمادها وتشغيلها.",
            ]
            label, summary = "فتح الوكيل", "مراجعة الخطة في الوكيل"
        else:
            headline = "وضع السؤال لا يُنشئ مهاماً"
            prose = [
                "وضع السؤال للإجابات والنصح فقط. "
                "بدّل المفتاح إلى «خطّة» لصياغة خطة قابلة للمراجعة من هذه المحادثة.",
            ]
            label, summary = "التبديل إلى خطّة", "بدّل إلى وضع الخطّة"
    elif already_plan:
        headline = "Plans are approved in Agent"
        prose = [
            "Plan drafts the plan only. "
            "Open the Tasks panel to review, approve, and run it.",
        ]
        label, summary = "Open in Agent", "Review the plan in Agent"
    else:
        headline = "Ask mode does not create tasks"
        prose = [
            "Ask is answers and advice only. "
            "Switch the dial to Plan to draft a reviewable plan from this thread.",
        ]
        label, summary = "Switch to Plan", "Switch to Plan mode"
    panel = "tasks" if already_plan else "plan"
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
                "panel": panel,
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
    surface: str | Surface | None = None,
) -> dict[str, Any]:
    """Tool-result shape for a cancelled Chat mutation (not an error)."""
    name = (tool_name or "").strip()
    # plan_task in Chat/Ask → switch to Plan dial; never invent Agent/My CTAs.
    if name in {"plan_task", "approve_plan", "edit_plan"}:
        return build_plan_mode_switch_handoff(
            user_message=user_message, surface=surface,
        )

    args = tool_args or {}
    api = str(args.get("api_name") or args.get("api") or "").strip()
    body = args.get("body") if isinstance(args.get("body"), dict) else {}
    locale = detect_locale(user_message)
    spec = handoff_spec_for_api(api)
    actions = build_handoff_actions(spec, locale=locale, surface=surface)
    verify_handoff(surface, actions)
    message = handoff_copy(spec, draft=body, locale=locale, surface=surface)
    envelope = build_handoff_envelope(
        spec, draft=body, locale=locale, surface=surface,
    )
    summary = (
        V("t_prepared_leave_draft_handoff_to_agent")
        if V("t_leave") in (spec.get("topic_en") or "")
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
        # Self-describing: downstream copy (``_chat_handoff_note``) rebuilds the
        # message from this result and must not re-guess the dial.
        "surface": Surface.resolve(surface).value,
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


def build_handoff_actions(
    spec: dict[str, str],
    *,
    locale: str = "en",
    surface: str | Surface | None = None,
) -> list[dict[str, Any]]:
    """Machine-readable CTAs — Agent first, then My (AIMessageBubble order).

    Manager Team-review and My-only profile intents skip Agent. A CTA that
    would send the user to ``surface`` is dropped: offering the seat they are
    already sitting in is the bug this argument exists to prevent.
    """
    actions = _build_handoff_actions(spec, locale=locale)
    current = Surface.resolve(surface)
    return [a for a in actions if cta_target_surface(a) is not current]


def _build_handoff_actions(
    spec: dict[str, str], *, locale: str = "en",
) -> list[dict[str, Any]]:
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


#: Lead sentence per Chat surface. The dial the user can see is the dial we
#: name: telling a Plan-mode user that "Chat" cannot submit reads as a bug even
#: though the refusal is correct.
_NO_SUBMIT_LEAD: dict[Surface, tuple[str, str]] = {
    Surface.CHAT_ASK: (
        "I can help you prepare a {topic}, but Chat does not submit or "
        "change records in the system.",
        "يمكنني مساعدتك في تجهيز {topic}، لكن الدردشة لا تُرسل ولا تغيّر "
        "السجلات في النظام.",
    ),
    Surface.CHAT_PLAN: (
        "I can draft this {topic} here, but Plan only drafts — it does not "
        "submit or change records in the system.",
        "أستطيع صياغة {topic} هنا، لكن وضع الخطّة يصيغ فقط — "
        "ولا يُرسل ولا يغيّر السجلات في النظام.",
    ),
}


def no_submit_lead(
    topic: str, *, locale: str = "en", surface: str | Surface | None = None,
) -> str:
    """Honest first line for a refused write, named after the user's own dial."""
    current = Surface.resolve(surface)
    en, ar = _NO_SUBMIT_LEAD.get(current, _NO_SUBMIT_LEAD[Surface.CHAT_ASK])
    return (ar if locale == "ar" else en).format(topic=topic)


def handoff_copy(
    spec: dict[str, str],
    *,
    draft: dict | None = None,
    locale: str = "en",
    surface: str | Surface | None = None,
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
    lead = no_submit_lead(topic, locale=locale, surface=surface)
    if locale == "ar":
        lines = [
            lead,
            "",
            "لإتمام التغيير استخدم أحد المسارين:",
            "• **الوكيل (Agent)** — بدّل إلى وضع الوكيل وشغّل العملية المعتمدة "
            "(التأكيد عند التشغيل).",
            f"• **تطبيقاتي** — افتح «{my_label}» وقدّم الطلب هناك.",
        ]
    else:
        lines = [
            lead,
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
    surface: str | Surface | None = None,
) -> dict[str, Any]:
    """Typed envelope for handoff — draft table, **empty caveats** (RULE_23)."""
    topic = _label(spec, "topic", locale)
    dial = Surface.resolve(surface).dial_label(locale)
    if locale == "ar":
        headline = f"لا يمكن تقديم {topic} من وضع «{dial}»"
        prose = [
            f"جهّزنا التفاصيل أدناه. وضع «{dial}» لا يغيّر السجلات — "
            "أكمل عبر الوكيل أو من تطبيقاتي.",
        ]
        table_title = "مسودة الطلب"
        col_field, col_value = "الحقل", "القيمة"
        source_tool = "draft"
    else:
        headline = f"This {topic} cannot be submitted from {dial}"
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
    *,
    surface: str | Surface | None = None,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """When Chat write intent had no tool call — copy + CTAs + envelope."""
    locale = detect_locale(user_message)
    spec = handoff_spec_for_intent(user_message)
    actions = build_handoff_actions(spec, locale=locale, surface=surface)
    verify_handoff(surface, actions)
    return (
        handoff_copy(spec, locale=locale, surface=surface),
        actions,
        build_handoff_envelope(spec, locale=locale, surface=surface),
    )


def chat_mutation_narration(api_name: str | None = None) -> str:
    """Honest progress line for Chat when a mutation tool is about to be blocked."""
    api = (api_name or "").strip().lower()
    if V("t_leave") in api:
        return V("t_preparing_next_steps_for_your_leave")
    if V("t_loan_2") in api:
        return V("t_preparing_next_steps_for_your_loan")
    if V("t_attendance") in api:
        return V("t_preparing_next_steps_for_attendance")
    return "Checking how to complete this request…"
