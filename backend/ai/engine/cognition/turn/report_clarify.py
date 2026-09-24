from __future__ import annotations
from ai.engine.cognition.phrase_tables import T
from ai.engine.pack_vocab import V
V("t_broad_payroll_salary_report_asks_clarify")


from typing import Any

from ai.engine.cognition.plan.process_dial import strip_pulse_mode_prefix
from ai.engine.text.word_match import contains_any_phrase, has_any_word, has_gapped_words
from ai.engine.cognition.turn.navigation import detect_lang
from ai.engine.cognition.turn.report_clarify_i18n import (
    ASPECT_PICK_AR,
    PRIOR_CLARIFY_AR,
    SCOPED_AR,
    any_needle,
    broad_report_ar,
)

#: Vague "give me a full report" without an angle / audience.
_BROAD_HEADS = T("turn/report_clarify.py::_BROAD_HEADS")
_BROAD_DOCS = T("turn/report_clarify.py::_BROAD_DOCS")
_BROAD_PAY = T("turn/report_clarify.py::_BROAD_PAY")
_BROAD_PAY_DOCS = T("turn/report_clarify.py::_BROAD_PAY_DOCS")


def _is_broad_report_en(text: str) -> bool:
    if any(has_gapped_words(text, head, _BROAD_DOCS, max_gap=6) for head in _BROAD_HEADS):
        return True
    if any(has_gapped_words(text, doc, _BROAD_PAY, max_gap=6) for doc in _BROAD_DOCS):
        return True
    return any(has_gapped_words(text, pay, _BROAD_PAY_DOCS, max_gap=4) for pay in (V("t_salary"), V("t_salaries"), V("t_payroll"), "compensation"))

#: Already scoped — do not re-ask.
#: Note: ``charts?`` not ``chart`` — "with charts" must count as scoped.
_SCOPED_WORDS = T("turn/report_clarify.py::_SCOPED_WORDS")
_SCOPED_PHRASES = T("turn/report_clarify.py::_SCOPED_PHRASES")


def _is_scoped_en(text: str) -> bool:
    return has_any_word(text, _SCOPED_WORDS) or contains_any_phrase(text, _SCOPED_PHRASES)

#: User reply that picks an option from the clarify list (or all of them).
_ASPECT_WORDS = T("turn/report_clarify.py::_ASPECT_WORDS")
_ASPECT_PHRASES = T("turn/report_clarify.py::_ASPECT_PHRASES")


def _is_aspect_pick_en(text: str) -> bool:
    return has_any_word(text, _ASPECT_WORDS) or contains_any_phrase(text, _ASPECT_PHRASES)


def _numbered_pick_key(text: str) -> str | None:
    raw = (text or "").strip().rstrip(".)").strip()
    folded = raw.casefold()
    if folded.startswith("option "):
        folded = folded[7:].strip().rstrip(".)").strip()
    if folded in {"1", "2", "3", "4", "5", "both"}:
        return folded
    return None

#: Expand numbered picks into scoped tool briefs ( report menu).
_SALARY_ASPECT_BY_NUM = T("turn/report_clarify.py::_SALARY_ASPECT_BY_NUM")

#: Expand numbered picks from the headcount/org topic menu (LLM variant).
_TOPIC_ASPECT_BY_NUM = T("turn/report_clarify.py::_TOPIC_ASPECT_BY_NUM")

_TOPIC_MENU_MARKERS = T("turn/report_clarify.py::_TOPIC_MENU_MARKERS")

#: Prior assistant clarify — match even after entity-chip mutation of "it".
_PRIOR_CLARIFY_MARKERS = T("turn/report_clarify.py::_PRIOR_CLARIFY_MARKERS")

#: Thread already answered a / report (continuity).
_PRIOR_REPORT_ANSWER_MARKERS = T("turn/report_clarify.py::_PRIOR_REPORT_ANSWER_MARKERS")

#: Digests that mean we already fetched / context this thread.
_PAYROLL_DIGEST_MARKERS = T("turn/report_clarify.py::_PAYROLL_DIGEST_MARKERS")

# Avoid pronoun "it" — entity annotator casefolds OrgUnit "IT" onto "it".
_CLARIFY = T("turn/report_clarify.py::_CLARIFY")


def is_broad_report_ask(utterance: str) -> bool:
    """True when the brief wants a report but has no aspect/audience yet."""
    text = strip_pulse_mode_prefix(utterance or "").strip()
    if not text or len(text) > 280:
        return False
    if not (_is_broad_report_en(text) or broad_report_ar(text)):
        return False
    if _is_scoped_en(text) or any_needle(text, SCOPED_AR):
        return False
    return True


def looks_like_report_aspect_reply(utterance: str) -> bool:
    """True when the user is answering the report-clarify options."""
    text = strip_pulse_mode_prefix(utterance or "").strip()
    if not text or len(text) > 200:
        return False
    return bool(_is_aspect_pick_en(text) or any_needle(text, ASPECT_PICK_AR))


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
    key = _numbered_pick_key(text)
    if not key:
        return None
    if not _history_has_clarify(history) and not _history_has_topic_menu(history):
        return None
    if _history_has_topic_menu(history):
        return _TOPIC_ASPECT_BY_NUM.get(key)
    return _SALARY_ASPECT_BY_NUM.get(key)


def _history_has_topic_menu(history: list[dict] | None) -> bool:
    for msg in history or []:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        if contains_any_phrase(str(msg.get("content") or ""), _TOPIC_MENU_MARKERS):
            return True
    return False


def _history_has_clarify(history: list[dict] | None) -> bool:
    for msg in history or []:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        content = str(msg.get("content") or "")
        if (
            contains_any_phrase(content, _PRIOR_CLARIFY_MARKERS)
            or any_needle(content, PRIOR_CLARIFY_AR)
        ):
            return True
    return False


def _history_has_report_answer(history: list[dict] | None) -> bool:
    for msg in history or []:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        content = str(msg.get("content") or "")
        if contains_any_phrase(content, _PRIOR_CLARIFY_MARKERS):
            continue
        if contains_any_phrase(content, _PRIOR_REPORT_ANSWER_MARKERS):
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
        if any(marker in blob.lower() for marker in _PAYROLL_DIGEST_MARKERS):
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
    open_question: dict | None = None,
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
    if looks_like_report_aspect_reply(text) or _is_scoped_en(text):
        return None

    oq = open_question if isinstance(open_question, dict) else {}
    if oq.get("slot") == "report_aspect" or (
        oq.get("text") and contains_any_phrase(str(oq.get("text") or ""), _PRIOR_CLARIFY_MARKERS)
    ):
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
