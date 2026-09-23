"""ESS self-read contract — balance vs history (ADR-0047 host identity).

Hard rule for Chat/Agent self-service reads:

  Self topic (leave / loan / payslip) → one canonical HOST GET →
  restate host fields only → never invent zeros from an empty sibling list.

| Domain  | Balance / entitlement API     | History / records API   |
|---------|-------------------------------|-------------------------|
| leave   | get_my_leave_balance          | list_my_leave           |
| loan    | (eligibility via list/detail) | list_my_loans           |
| payslip | list_my_payslips (lines)      | list_my_payslips        |

Empty ``list_my_leave`` means *no leave requests*, not *zero remaining days*.
Empty ``list_my_loans`` means *no loans*, not invented installment figures.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ai.engine.cognition.plan.process_dial import strip_pulse_mode_prefix
from ai.engine.cognition.turn.navigation import detect_lang

# ── Canonical APIs ──────────────────────────────────────────────────────────

LEAVE_BALANCE_API = "get_my_leave_balance"
LEAVE_HISTORY_API = "list_my_leave"
LOAN_HISTORY_API = "list_my_loans"
PAYSLIP_API = "list_my_payslips"

BALANCE_APIS = frozenset({LEAVE_BALANCE_API, PAYSLIP_API})
HISTORY_APIS = frozenset({LEAVE_HISTORY_API, LOAN_HISTORY_API, PAYSLIP_API})

# ── Topic detectors (EN + AR, hamza-tolerant) ───────────────────────────────

_LEAVE_TOPIC_RE = re.compile(
    r"("
    r"\bleaves?\b|\bvacation\b|\bpto\b|\btime[\s-]?off\b|"
    r"leave\s+balance|remaining\s+leave|leave\s+remaining|"
    r"how\s+much\s+leave|annual\s+leave|leave\s+entitlement|"
    # Arabic stem إجاز/اجاز + typo tolerance (الاجازلت, الإجازات, …)
    r"رصيد\s*ال?[اأإ]?جاز\w{0,4}|"
    r"[اأإ]?جاز\w{0,4}\s*متبقي|"
    r"ال?[اأإ]?جاز\w{0,4}\s*المتبقي|"
    r"[اأإ]?جاز\w{0,4}ي|"
    r"عن\s*ال?[اأإ]?جاز\w{0,4}|"
    r"ال?[اأإ]?جاز\w{0,4}"
    r")",
    re.IGNORECASE,
)

_LEAVE_ZERO_CLAIM_RE = re.compile(
    r"("
    r"رصيد\s*(?:ال)?(?:إ|ا)?جاز\w{0,4}\s*(?:المتبقي)?\s*:?\s*0|"
    r"(?:المتبقي|المستخدمة?|المعلقة?)\s*:?\s*0\s*يوم|"
    r"remaining\s*(?:leave\s*)?(?:balance\s*)?[:=]?\s*0|"
    r"(?:used|pending)\s*[:=]?\s*0\s*day"
    r")",
    re.IGNORECASE,
)

_COMPREHENSIVE_PICK_RE = re.compile(
    r"("
    r"\b(?:comprehensive|full\s+report|all\s+(?:of\s+)?(?:it|them)|everything)\b|"
    r"تقرير\s*شامل|شامل|كل\s*(?:شي|شيء)|التفاصيل\s*كلها"
    r")",
    re.IGNORECASE,
)

_LEAVE_HISTORY_RE = re.compile(
    r"("
    r"\bleave\s+(?:requests?|history|records?|applications?)\b|"
    r"\bmy\s+leave\s+(?:requests?|history)\b|"
    r"طلبات?\s*ال?[اإ]جاز|سجل\s*ال?[اإ]جاز|إجازاتي\s*السابق"
    r")",
    re.IGNORECASE,
)

_LOAN_TOPIC_RE = re.compile(
    r"("
    r"\bloans?\b|\binstallment\b|"
    r"قرض|قروض|سلف[ةه]?|أقساط"
    r")",
    re.IGNORECASE,
)

_LOAN_SELF_RE = re.compile(
    r"(?i)("
    r"\bmy\s+loans?\b|"
    r"قروضي|سلفتي|أقساطي|"
    r"ما\s*(?:هي|هو)?\s*قروضي"
    r")"
)

_PAYSLIP_TOPIC_RE = re.compile(
    r"("
    r"\bpayslips?\b|\bnet\s+pay\b|\btake[\s-]?home\b|"
    r"\blast\s+(?:month'?s?\s+)?(?:pay|salary|payslip)\b|"
    r"قسيمة|قسائم|صافي\s*ال?راتب|راتبي\s*(?:الشهر|الأخير)?"
    r")",
    re.IGNORECASE,
)

_NAMED_EMP_RE = re.compile(
    r"(?i)("
    r"\bemp[_\s-]?\d+\b|"
    r"\bemployee\s*(?:no\.?|number|#|:)?\s*\d+|"
    r"\bfor\s+(?!me\b)[\w\u0600-\u06FF]|"
    r"'s\s+(?:leave|annual|sick|balance|loan|payslip)"
    r")",
)

_HONEST_EMPTY = {
    "en": {
        "leave_history": (
            "You have no leave requests on record yet. "
            "That is not the same as a zero leave balance — "
            "ask for your leave balance if you want remaining days by type."
        ),
        "loan_history": (
            "You have no loans on record. "
            "I will not invent installment or balance figures."
        ),
        "payslip": (
            "No committed payslip lines were found for you for that period. "
            "I will not invent net-pay figures."
        ),
    },
    "ar": {
        "leave_history": (
            "لا توجد طلبات إجازة مسجّلة حتى الآن. "
            "هذا ليس معناه أن رصيد الإجازات صفر — "
            "اطلب رصيد الإجازات إن أردت الأيام المتبقية حسب النوع."
        ),
        "loan_history": (
            "لا توجد قروض مسجّلة لك. "
            "لن أخترع أرقام أقساط أو أرصدة."
        ),
        "payslip": (
            "لا توجد بنود قسيمة راتب معتمدة لهذه الفترة. "
            "لن أخترع أرقام صافي الراتب."
        ),
    },
}


def _norm(text: str) -> str:
    return strip_pulse_mode_prefix(text or "").strip()


def is_named_employee_ask(text: str | None) -> bool:
    return bool(_NAMED_EMP_RE.search(_norm(text or "")))


def leave_topic_asked(text: str | None) -> bool:
    return bool(_LEAVE_TOPIC_RE.search(_norm(text or "")))


def leave_history_asked(text: str | None) -> bool:
    return bool(_LEAVE_HISTORY_RE.search(_norm(text or "")))


def loan_topic_asked(text: str | None) -> bool:
    return bool(_LOAN_TOPIC_RE.search(_norm(text or "")))


def loan_history_asked(text: str | None) -> bool:
    """True for first-person loan list asks (not 'what types of loans')."""
    return bool(_LOAN_SELF_RE.search(_norm(text or "")))


def payslip_topic_asked(text: str | None) -> bool:
    return bool(_PAYSLIP_TOPIC_RE.search(_norm(text or "")))


def preferred_self_api(text: str | None) -> str | None:
    """Canonical host API for a self ESS read ask."""
    t = _norm(text or "")
    if not t or is_named_employee_ask(t):
        return None
    # History before balance — «طلبات الإجازة» must not become get_my_leave_balance.
    if leave_history_asked(t):
        return LEAVE_HISTORY_API
    if leave_topic_asked(t):
        return LEAVE_BALANCE_API
    if loan_history_asked(t):
        return LOAN_HISTORY_API
    if payslip_topic_asked(t):
        return PAYSLIP_API
    return None


def ess_self_read_topic(text: str | None) -> str | None:
    """Return ``leave`` | ``loan`` | ``payslip`` for self-service topic asks.

    Nav skip uses broader loan_topic so «قروض؟» does not open UI; preferred
    API still requires first-person for loans.
    """
    t = _norm(text or "")
    if not t or is_named_employee_ask(t):
        return None
    if leave_history_asked(t) or leave_topic_asked(t):
        return "leave"
    if loan_history_asked(t) or loan_topic_asked(t):
        return "loan"
    if payslip_topic_asked(t):
        return "payslip"
    return None


_BARE_PLACE_RE = re.compile(
    r"^(?:"
    r"leave|leaves|loan|loans|payroll|payslips?|attendance|home|"
    r"إجازة|اجازة|إجازات|اجازات|قرض|قروض|رواتب|راتب|قسائم|قسيمة|حضور"
    r")\s*[?؟!]*$",
    re.IGNORECASE,
)


def is_bare_place_noun(text: str | None) -> bool:
    """True for terse destination nouns («leave», «قروض») — still navigate."""
    return bool(_BARE_PLACE_RE.match(_norm(text or "")))


def should_skip_module_nav(text: str | None) -> bool:
    """True when the utterance is an ESS data read, not a UI destination."""
    t = _norm(text or "")
    if not t or is_bare_place_noun(t):
        return False
    return preferred_self_api(t) is not None or (
        leave_topic_asked(t) and not is_named_employee_ask(t)
    )


def preferred_admin_leave_api(text: str | None) -> str | None:
    """Named-employee leave remaining → entitlements list."""
    t = _norm(text or "")
    if not leave_topic_asked(t) or not is_named_employee_ask(t):
        return None
    return "list_leave_entitlements"


def leave_zero_claim_in_text(text: str | None) -> bool:
    """True when copy invents remaining/used/pending = 0 days."""
    return bool(_LEAVE_ZERO_CLAIM_RE.search(text or ""))


def last_results_have_leave_balance(last_results: list | None) -> bool:
    for row in last_results or []:
        if not isinstance(row, dict):
            continue
        blob = f"{row.get('api') or ''} {row.get('digest') or ''} {row.get('tool') or ''}"
        if LEAVE_BALANCE_API in blob:
            return True
    return False


def last_results_only_empty_leave_history(last_results: list | None) -> bool:
    """True when thread saw empty list_my_leave and never get_my_leave_balance."""
    saw_empty_history = False
    for row in last_results or []:
        if not isinstance(row, dict):
            continue
        blob = f"{row.get('api') or ''} {row.get('digest') or ''}"
        if LEAVE_BALANCE_API in blob:
            return False
        if LEAVE_HISTORY_API in blob and (
            "count=0" in blob or "results=[]" in blob or "No leave" in blob
        ):
            saw_empty_history = True
    return saw_empty_history


def leave_in_recent_history(history: list | None) -> bool:
    for msg in reversed(history or []):
        if not isinstance(msg, dict):
            continue
        content = str(msg.get("content") or "")
        if leave_topic_asked(content):
            return True
    return False


def tool_calls_include_api(tool_calls: list | None, api_name: str) -> bool:
    import json as _json

    needle = str(api_name or "").strip()
    if not needle:
        return False
    for tc in tool_calls or []:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
        name = str(fn.get("name") or tc.get("name") or "")
        args_raw = fn.get("arguments") if fn else tc.get("arguments")
        args: Any = args_raw
        if isinstance(args_raw, str):
            try:
                args = _json.loads(args_raw)
            except (TypeError, ValueError):
                args = {}
        if not isinstance(args, dict):
            args = {}
        api = str(args.get("api_name") or args.get("name") or args.get("api") or "")
        blob = f"{name} {api} {args_raw}"
        if needle in blob:
            return True
    return False


def leave_balance_force_needed(
    user_message: str | None,
    *,
    history: list | None = None,
    tool_calls: list | None = None,
    last_results: list | None = None,
) -> bool:
    """Chat must call get_my_leave_balance — never invent 0 from empty requests."""
    t = _norm(user_message or "")
    if not t or is_named_employee_ask(t) or leave_history_asked(t):
        return False
    wants_balance = preferred_self_api(t) == LEAVE_BALANCE_API or leave_topic_asked(t)
    if not wants_balance:
        # «تقرير شامل» after a salary+leave brief still needs balance rows.
        if _COMPREHENSIVE_PICK_RE.search(t) and leave_in_recent_history(history):
            wants_balance = True
    if not wants_balance:
        return False
    if tool_calls_include_api(tool_calls, LEAVE_BALANCE_API):
        return False
    if last_results_have_leave_balance(last_results):
        return False
    return True


def build_leave_balance_tool_call(turn_id: str = "") -> dict[str, Any]:
    """Injected call_host_api for Chat leave-balance force (weather twin)."""
    import json as _json

    suffix = (turn_id or "ess")[:8]
    return {
        "id": f"call_leave_bal_{suffix}",
        "function": {
            "name": "call_host_api",
            "arguments": _json.dumps({
                "api_name": LEAVE_BALANCE_API,
                "explanation": "Fetch self leave entitlements/remaining by type",
            }),
        },
    }


def _unwrap(raw: Any) -> Any:
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return raw
    if isinstance(data, dict) and "status_code" in data and "data" in data:
        data = data["data"]
    return data


def _api_name(item: dict) -> str:
    args = item.get("tool_args") if isinstance(item.get("tool_args"), dict) else {}
    for key in ("api_name", "name", "api"):
        val = args.get(key)
        if val:
            return str(val).strip()
    blob = f"{item.get('tool_name') or ''} {args}"
    for name in (
        LEAVE_HISTORY_API,
        LEAVE_BALANCE_API,
        LOAN_HISTORY_API,
        PAYSLIP_API,
    ):
        if name in blob:
            return name
    return ""


def _payload_empty_list(data: Any) -> bool:
    if isinstance(data, list):
        return len(data) == 0
    if not isinstance(data, dict):
        return False
    if data.get("unauthorized"):
        return False
    for key in ("results", "items", "rows"):
        if key in data and isinstance(data[key], list):
            return len(data[key]) == 0
    try:
        if data.get("count") is not None and int(data["count"]) == 0:
            return True
    except (TypeError, ValueError):
        pass
    return False


def empty_history_misread(
    completed_tools: list | None,
    *,
    user_message: str,
) -> dict[str, Any] | None:
    """When history list is empty but user asked balance/topic — honest reply.

    Returns ``{decision, text, gate}`` for 0-LLM surface, or None.
    """
    topic = ess_self_read_topic(user_message)
    if not topic:
        return None
    # Balance ask + empty leave *records* → do not invent zero remaining.
    want_balance = topic == "leave" and not leave_history_asked(user_message)
    lang = "ar" if detect_lang(user_message or "") == "ar" else "en"
    for item in completed_tools or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        api = _api_name(item)
        data = _unwrap(item.get("result"))
        if not _payload_empty_list(data):
            continue
        if api == LEAVE_HISTORY_API and (want_balance or topic == "leave"):
            # Empty records must never become "remaining = 0".
            if want_balance:
                return {
                    "decision": "answer",
                    "text": _HONEST_EMPTY[lang]["leave_history"],
                    "gate": "ess_empty_leave_history",
                    "prefer_api": LEAVE_BALANCE_API,
                }
            return {
                "decision": "answer",
                "text": _HONEST_EMPTY[lang]["leave_history"],
                "gate": "ess_empty_leave_history",
            }
        if api == LOAN_HISTORY_API and topic == "loan":
            return {
                "decision": "answer",
                "text": _HONEST_EMPTY[lang]["loan_history"],
                "gate": "ess_empty_loan_history",
            }
        if api == PAYSLIP_API and topic == "payslip":
            return {
                "decision": "answer",
                "text": _HONEST_EMPTY[lang]["payslip"],
                "gate": "ess_empty_payslip",
            }
    return None


def guidance_block(*, audience: str = "ess") -> str:
    """Prompt fragment — balance API first; never invent from empty history."""
    return (
        "ESS SELF-READ CONTRACT (mandatory):\n"
        f"- Leave balance / «عن الإجازات» / رصيد → `{LEAVE_BALANCE_API}` "
        f"(entitled/used/pending/remaining by type). "
        f"`{LEAVE_HISTORY_API}` is leave REQUESTS only — empty requests ≠ zero balance.\n"
        f"- Loan list / قروضي → `{LOAN_HISTORY_API}`; never invent installments.\n"
        f"- Payslip / net pay / قسيمة → `{PAYSLIP_API}`; empty → say empty, never invent.\n"
        "- Never invent remaining/used/pending = 0 from an empty history list.\n"
        "- Do not offer to open Leave/Loans UI unless the user asked to navigate."
    )
