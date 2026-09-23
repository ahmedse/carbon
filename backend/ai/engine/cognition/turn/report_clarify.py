"""Broad payroll/salary report asks — clarify before dumping data.

Ask mode must not invent a full report from a vague brief. One short
question with closed options; then run tools for the chosen angle.

Continuity (ADR-0047 ConversationState): never re-ask the same clarify when
this thread already has payroll/salary results, a prior clarify, or a scoped
follow-up (charts / all aspects / …).
"""
from __future__ import annotations

import re
from typing import Any

from ai.engine.cognition.plan.process_dial import strip_pulse_mode_prefix
from ai.engine.cognition.turn.navigation import detect_lang

#: Vague "give me a full report" without an angle / audience.
_BROAD_REPORT_RE = re.compile(
    r"("
    r"\b(?:full|complete|comprehensive|detailed|entire|overall)\b.{0,40}\b"
    r"(?:report|overview|summary|pack)\b"
    r"|\b(?:report|overview|summary|pack)\b.{0,40}\b"
    r"(?:salary|salaries|payroll|compensation|pay)\b"
    r"|\b(?:salary|salaries|payroll|compensation)\b.{0,24}\b"
    r"(?:report|overview|summary)\b"
    r"|تقرير\s*(?:كامل|شامل|مفصل)?\s*(?:عن\s+)?(?:ال)?(?:رواتب|راتب|مسير|الأجور)"
    r"|(?:رواتب|راتب).{0,24}تقرير"
    r")",
    re.IGNORECASE | re.DOTALL,
)

#: Already scoped — do not re-ask.
#: Note: ``charts?`` not ``chart`` — "with charts" must count as scoped.
_SCOPED_RE = re.compile(
    r"("
    r"\b(?:board|executive|hr\s+lead|finance|manager|committee)\b"
    r"|\b(?:distribution|breakdown|bands?|tiers?|histogram)\b"
    r"|\b(?:charts?|graphs?|visuals?|viz)\b"
    r"|\b(?:gosi|pifss|deduction|variance|committed|draft|failed)\b"
    r"|\b(?:by\s+(?:band|tier|nationality|gender|dept|department|org|grade))\b"
    r"|\b(?:word|excel|pdf|pptx|export|pack)\b"
    r"|مجلس|إدارة|توزيع|شرائح|تأمينات|استقطاع|حسب|رسوم|مخططات"
    r")",
    re.IGNORECASE,
)

#: User reply that picks an option from the clarify list (or all of them).
_ASPECT_PICK_RE = re.compile(
    r"("
    r"\b(?:distribution|bands?|tiers?|pay\s*mix)\b"
    r"|\b(?:run\s*health|committed|draft|failed|payroll\s*runs?)\b"
    r"|\b(?:gosi|pifss|deduction)\b"
    r"|\b(?:board|executive|high[\s-]?level|summary)\b"
    r"|\b(?:all\s+(?:of\s+)?(?:the\s+)?(?:4|four|aspects?|options?|above|them))\b"
    r"|\b(?:both|everything|each\s+(?:aspect|one))\b"
    r"|توزيع|شرائح|مسيرات|ملتزم|مسودة|فشل|تأمينات|مجلس|ملخص"
    r"|كل\s*(?:ال)?(?:أربعة|الجوانب|الخيارات|ما\s*سبق)"
    r")",
    re.IGNORECASE,
)

#: Bare "1" / "2" / "option 3" after a numbered clarify menu.
_NUMBERED_PICK_RE = re.compile(
    r"^\s*(?:option\s*)?([1-5]|both)\s*[.)]?\s*$",
    re.IGNORECASE,
)

#: Expand numbered picks into scoped tool briefs (salary report menu).
_SALARY_ASPECT_BY_NUM = {
    "1": "Pay distribution by band with charts and tiers",
    "2": "Payroll run health committed draft failed",
    "3": "Deductions and GOSI overview",
    "4": "Board-ready salary summary high level no row dumps",
    "5": "Board-ready salary summary high level no row dumps",
    "both": "all four salary report aspects with charts",
}

#: Expand numbered picks from the headcount/org topic menu (LLM variant).
_TOPIC_ASPECT_BY_NUM = {
    "1": (
        "Headcount and organization structure — active employees by "
        "department, role, and employment type with charts"
    ),
    "2": (
        "Payroll and compensation — salary ranges, gross pay, deductions, "
        "net pay trends with charts"
    ),
    "3": "Leave and attendance balances usage patterns with charts",
    "4": "GOSI and statutory employer employee contributions compliance",
    "5": "Payroll run status draft computed validated committed failed",
    "both": (
        "Headcount and organization structure with charts — departments, "
        "roles, employment type"
    ),
}

_TOPIC_MENU_RE = re.compile(
    r"Headcount\s*&\s*Organization|Payroll\s*&\s*Compensation"
    r"|What's the main topic|I'd like to focus this report",
    re.IGNORECASE,
)

#: Prior assistant clarify — match even after entity-chip mutation of "it".
_PRIOR_CLARIFY_RE = re.compile(
    r"("
    r"what should .{0,80} focus on"
    r"|على ماذا تريد التركيز"
    r"|Happy to help with a salary report"
    r"|بكل سرور أساعد في تقرير الرواتب"
    r")",
    re.IGNORECASE,
)

#: Thread already answered a salary/payroll report (continuity).
_PRIOR_REPORT_ANSWER_RE = re.compile(
    r"("
    r"Payroll Run Status|payslip line|active employees"
    r"|Headcount by|salary band|pay distribution"
    r"|Committed.+(?:Draft|Failed)|GOSI|PIFSS"
    r")",
    re.IGNORECASE,
)

#: Digests that mean we already fetched payroll/salary context this thread.
_PAYROLL_DIGEST_RE = re.compile(
    r"("
    r"list_payroll_runs|list_payslip_lines|analyze_employees"
    r"|aggregate_entity.*headcount|payslip|payroll"
    r"|metric=headcount"
    r")",
    re.IGNORECASE,
)

# Avoid pronoun "it" — entity annotator casefolds OrgUnit "IT" onto "it".
_CLARIFY = {
    "en": (
        "Happy to help with a salary report — what should **this report** focus on?\n\n"
        "- **Pay distribution by band** (charts + tiers)\n"
        "- **Payroll run health** (committed / draft / failed)\n"
        "- **Deductions & GOSI** overview\n"
        "- **Board-ready summary** (high level, no row dumps)\n"
        "- Something else — tell me the **audience** and the **angle**"
    ),
    "ar": (
        "بكل سرور أساعد في تقرير الرواتب — على ماذا تريد التركيز؟\n\n"
        "- **توزيع الرواتب حسب الشرائح** (رسوم بيانية)\n"
        "- **صحة مسيرات الرواتب** (معتمد / مسودة / فاشل)\n"
        "- **الاستقطاعات والتأمينات (GOSI)**\n"
        "- **ملخص لمجلس الإدارة** (مستوى عالٍ بدون جداول صفوف)\n"
        "- أمر آخر — حدّد **الجمهور** و**الزاوية**"
    ),
}


def is_broad_report_ask(utterance: str) -> bool:
    """True when the brief wants a report but has no aspect/audience yet."""
    text = strip_pulse_mode_prefix(utterance or "").strip()
    if not text or len(text) > 280:
        return False
    if not _BROAD_REPORT_RE.search(text):
        return False
    if _SCOPED_RE.search(text):
        return False
    return True


def looks_like_report_aspect_reply(utterance: str) -> bool:
    """True when the user is answering the report-clarify options."""
    text = strip_pulse_mode_prefix(utterance or "").strip()
    if not text or len(text) > 200:
        return False
    return bool(_ASPECT_PICK_RE.search(text))


def expand_numbered_report_pick(
    utterance: str,
    *,
    history: list[dict] | None = None,
) -> str | None:
    """Map bare ``1``/``2``/… after a report menu to a scoped brief.

    Transcript bug: user answered ``1`` after a topic menu and got a bare
    headcount scalar. Expand so the normal tool pipeline runs the aspect.
    """
    text = strip_pulse_mode_prefix(utterance or "").strip()
    m = _NUMBERED_PICK_RE.match(text)
    if not m:
        return None
    if not _history_has_clarify(history) and not _history_has_topic_menu(history):
        return None
    key = m.group(1).lower()
    if _history_has_topic_menu(history):
        return _TOPIC_ASPECT_BY_NUM.get(key)
    return _SALARY_ASPECT_BY_NUM.get(key)


def _history_has_topic_menu(history: list[dict] | None) -> bool:
    for msg in history or []:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        if _TOPIC_MENU_RE.search(str(msg.get("content") or "")):
            return True
    return False


def _history_has_clarify(history: list[dict] | None) -> bool:
    for msg in history or []:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        if _PRIOR_CLARIFY_RE.search(str(msg.get("content") or "")):
            return True
    return False


def _history_has_report_answer(history: list[dict] | None) -> bool:
    for msg in history or []:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        content = str(msg.get("content") or "")
        if _PRIOR_CLARIFY_RE.search(content):
            continue
        if _PRIOR_REPORT_ANSWER_RE.search(content):
            return True
    return False


def _last_results_have_payroll(last_results: list[dict] | None) -> bool:
    for row in last_results or []:
        if not isinstance(row, dict):
            continue
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("tool", "api", "digest", "ref")
        )
        if _PAYROLL_DIGEST_RE.search(blob):
            return True
    return False


def build_report_clarify(utterance: str) -> dict[str, Any]:
    lang = "ar" if detect_lang(utterance or "") == "ar" else "en"
    return {
        "decision": "clarify",
        "text": _CLARIFY[lang],
        "gate": "report_clarify",
    }


def try_report_clarify(
    utterance: str,
    *,
    history: list[dict] | None = None,
    last_results: list[dict] | None = None,
) -> dict[str, Any] | None:
    """0-LLM: broad report → one clarify; never re-ask when context exists.

    Numbered picks after a menu are expanded by the caller via
    :func:`expand_numbered_report_pick` — this gate only returns clarify
    or ``None`` (pass-through).
    """
    text = strip_pulse_mode_prefix(utterance or "").strip()
    if not text:
        return None

    # Numbered pick after clarify/topic menu → pass through (caller expands).
    if expand_numbered_report_pick(text, history=history):
        return None

    # Aspect / "all 4" / charts follow-up → normal pipeline (tools + visuals).
    if looks_like_report_aspect_reply(text) or _SCOPED_RE.search(text):
        return None

    # Continuity: already clarified, already answered, or still have digests.
    if _history_has_clarify(history):
        return None
    if _history_has_topic_menu(history):
        return None
    if _history_has_report_answer(history):
        return None
    if _last_results_have_payroll(last_results):
        return None

    if is_broad_report_ask(text):
        return build_report_clarify(text)
    return None
