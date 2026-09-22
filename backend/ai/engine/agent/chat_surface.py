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
}

_LEAVE_INTENT = re.compile(
    r"\b(?:leave|vacation|annual\s+leave|time\s+off)\b"
    r"|إجاز|اجاز|عارضة|عارده|سنوي",
    re.IGNORECASE,
)
_LOAN_INTENT = re.compile(r"\bloan\b|قرض", re.IGNORECASE)
_ATTENDANCE_INTENT = re.compile(
    r"\b(?:attendance|permission|excuse)\b|استئذان|حضور",
    re.IGNORECASE,
)
#: Manager wants to act on Team inbox (approve leave/loan) — host /team, not Pulse.
_MANAGER_REVIEW_INTENT = re.compile(
    r"(?:\b(?:approve|reject|review)\b.{0,40}\b(?:leave|loan|request|inbox)\b)"
    r"|(?:\b(?:leave|loan|request)\b.{0,40}\b(?:approve|reject|review)\b)"
    r"|(?:\bteam\s+inbox\b|\bapprovals?\s+inbox\b)"
    r"|موافق على|اعتماد\s*(?:ال)?(?:إجاز|اجاز|طلب)|رفض\s*(?:ال)?(?:إجاز|اجاز)",
    re.IGNORECASE | re.DOTALL,
)
_ARABIC_SCRIPT = re.compile(r"[\u0600-\u06FF]")

#: Internal flag only — never shown in UI copy / caveats.
INTERNAL_REASON = "chat_no_host_mutation"

_FIELD_LABELS = {
    "leave_type": ("Leave type", "نوع الإجازة"),
    "start_date": ("Start date", "تاريخ البداية"),
    "end_date": ("End date", "تاريخ النهاية"),
    "days": ("Days", "الأيام"),
    "reason": ("Reason", "السبب"),
    "loan_type": ("Loan type", "نوع القرض"),
    "principal": ("Principal", "المبلغ"),
    "term_months": ("Term (months)", "المدة (أشهر)"),
    "interest_rate": ("Interest rate", "الفائدة"),
    "permission_type": ("Permission type", "نوع الاستئذان"),
    "hours": ("Hours", "الساعات"),
}


def is_chat_surface(surface: str | None) -> bool:
    """True when host mutations must not stage."""
    s = (surface or "chat").strip().lower()
    if s in AGENT_SURFACES:
        return False
    return True  # fail-closed: unspecified → treat as Chat


def detect_locale(text: str | None) -> str:
    """Return ``ar`` when the utterance is predominantly Arabic script."""
    return "ar" if _ARABIC_SCRIPT.search(text or "") else "en"


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


_ESS_TOPIC_RE = re.compile(
    r"\b(?:leave|loan|attendance|vacation|permission)\b"
    r"|إجاز|اجاز|قرض|استئذان"
    r"|submit_my_(?:leave|loan|attendance)"
    r"|تقديم\s*(?:ال)?(?:طلب\s*)?(?:إجاز|اجاز)",
    re.IGNORECASE,
)


def is_ess_write_intent(message: str) -> bool:
    """True for leave/loan/attendance *submit* asks (not balance reads).

    Used to skip orchestrator fan-out (those turns belong to process_dial /
    Chat handoff) without blocking other mutation or analytics fan-outs.
    """
    text = (message or "").strip()
    if not text or not _ESS_TOPIC_RE.search(text):
        return False
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
        "topic_en": "this change",
        "topic_ar": "هذا التغيير",
    }


def handoff_spec_for_intent(user_message: str) -> dict[str, str]:
    text = user_message or ""
    if _MANAGER_REVIEW_INTENT.search(text):
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
    if _LEAVE_INTENT.search(text):
        return handoff_spec_for_api("submit_my_leave")
    if _LOAN_INTENT.search(text):
        return handoff_spec_for_api("submit_my_loan")
    if _ATTENDANCE_INTENT.search(text):
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

    Manager Team-review intents skip Agent (host SoD lives on /team).
    """
    route = (spec.get("my_route") or "").strip()
    if spec.get("manager_only"):
        if not route:
            return []
        return [{
            "type": "navigate",
            "route": route,
            "label": _label(spec, "my_label", locale),
            "summary": "Approve or reject in Team",
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
            en_lab, ar_lab = _FIELD_LABELS.get(
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
            en_lab, ar_lab = _FIELD_LABELS.get(
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


def build_chat_handoff_result(
    tool_name: str,
    tool_args: dict | None,
    *,
    reason: str = "",
    user_message: str = "",
) -> dict[str, Any]:
    """Tool-result shape for a cancelled Chat mutation (not an error)."""
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
