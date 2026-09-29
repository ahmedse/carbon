"""ESS self-read contract — balance vs history (ADR-0047 host identity).

Hard rule for Chat/Agent self-service reads across ESS domains:

  Exactly one matched domain → one canonical HOST GET →
  restate host fields only → never invent zeros from an empty sibling list.

  Zero or multiple matched domains → do not bind (clarify / multi-tool /
  normal spine). Domain twins live in ``ESS_SELF_DOMAINS`` — add a domain
  there; do not special-case pairs in the binder.

Empty history list ≠ zero entitlement/balance for that domain.
"""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T

from ai.engine.host_ids import (
    ID_EMPTY_LEAVE_HISTORY,
    ID_EMPTY_LOAN_HISTORY,
    ID_EMPTY_PAYSLIP,
    ID_GET_MY_LEAVE_BALANCE,
    ID_GET_MY_PROFILE,
    ID_LEAVE_HISTORY,
    ID_LIST_LEAVE_ENTITLEMENTS,
    ID_LIST_MY_ATTENDANCE,
    ID_LIST_MY_LEAVE,
    ID_LIST_MY_LOANS,
    ID_LIST_MY_PAYSLIPS,
    ID_LOAN_HISTORY,
    ID_NO_BALANCE,
)
from ai.engine.pack_vocab import LV, V, copy_text, live_alt, live_pattern, present_ids, same_id

import json
import re
from dataclasses import dataclass
from typing import Any, Pattern

from ai.engine.cognition.plan.process_dial import strip_pulse_mode_prefix
from ai.engine.cognition.turn.ess_read_i18n import (
    ASPECT_FOLLOWUP_NEEDLES,
    ATTENDANCE_AR_TOKENS,
    BARE_PLACE_AR,
    COMPREHENSIVE_NEEDLES,
    EMPTY_BALANCE_TEXT,
    EMPTY_RENDER,
    HONEST_EMPTY,
    LEAVE_HISTORY_AR,
    LEAVE_TOPIC_AR,
    LEAVE_ZERO_CLAIM_AR,
    LOAN_SELF_AR,
    LOAN_TOPIC_AR,
    NAMED_EMP_AR,
    PAYSLIP_TOPIC_AR,
    UNAUTHORIZED_TEXT,
    any_needle,
)
from ai.engine.cognition.turn.navigation import detect_lang
from ai.engine.text.word_match import contains_any_phrase, has_any_word

# ── Canonical APIs ──────────────────────────────────────────────────────────

LEAVE_BALANCE_API = ID_GET_MY_LEAVE_BALANCE
LEAVE_HISTORY_API = ID_LIST_MY_LEAVE
LOAN_HISTORY_API = ID_LIST_MY_LOANS
PAYSLIP_API = ID_LIST_MY_PAYSLIPS
ATTENDANCE_API = ID_LIST_MY_ATTENDANCE


def balance_apis() -> frozenset[str]:
    return present_ids(LEAVE_BALANCE_API, PAYSLIP_API)


def history_apis() -> frozenset[str]:
    return present_ids(
        LEAVE_HISTORY_API, LOAN_HISTORY_API, PAYSLIP_API, ATTENDANCE_API,
    )

# ── Topic detectors (EN + AR, hamza-tolerant) ───────────────────────────────

_LEAVE_TOPIC_RE = live_alt(
    LV("t_rx_leave_topic_en"),
    LV("t_leave_s_balance_remaining_s_leave"),
    LV("t_how_s_much_s_leave_annual"),
    flags=re.IGNORECASE,
)

_LEAVE_HISTORY_RE = live_alt(
    LV("t_rx_leave_history_en"),
    LV("t_bmy_s_previous_s_leave_b"),
    LV("t_bmy_s_leave_s_requests_history"),
    LV("t_b_previous_past_s_leave_b"),
    LV("t_blist_s_my_s_leave_b"),
    flags=re.IGNORECASE,
)

_PAYSLIP_TOPIC_RE = live_alt(
    LV("t_rx_payslip_topic_en"),
    LV("t_blast_s_month_s_s_pay"),
    LV("t_bmy_s_salary_b_bsalary_b"),
    flags=re.IGNORECASE,
)

_NAMED_EMP_RE = live_alt(
    LV("t_rx_emp_id"),
    r"\bfor\s+(?!me\b)\w+",
    LV("t_s_s_leave_annual_sick_balance_2"),
    r"\bdoes\s+[A-Z][\w'-]+",
    flags=re.IGNORECASE,
)

_LEAVE_ZERO_CLAIM_RE = live_alt(
    LV("t_remaining_s_leave_s_balance_s"),
    LV("t_rx_leave_zero_en"),
    flags=re.IGNORECASE,
)

_PROPER_NAME_STOP = T("turn/ess_read.py::_PROPER_NAME_STOP")


def empty_render_text(key: str | None, language: str = "en") -> str | None:
    """Fixed sentence for a catalog empty_render key. None if the key is unknown."""
    row = EMPTY_RENDER.get(str(key or "").strip())
    if not row:
        return None
    lang = "ar" if str(language or "en").casefold().startswith("ar") else "en"
    return row[lang]


@dataclass(frozen=True)
class EssSelfDomain:
    """One ESS self-read twin (balance vs history).

    Register new domains here — binder logic stays domain-agnostic.
    """

    id: str
    balance_api: str | None
    history_api: str | None
    topic_re: Pattern[str] | None = None
    history_re: Pattern[str] | None = None
    #: When set, preferred bind requires a first-person hit (e.g.  FAQ).
    self_re: Pattern[str] | None = None
    topic_words: tuple[str, ...] = ()
    self_phrases: tuple[str, ...] = ()
    topic_needles: tuple[str, ...] = ()
    history_needles: tuple[str, ...] = ()
    self_needles: tuple[str, ...] = ()
    honesty_key: str = LV("t_payslip_2")

    def topic_match(self, text: str) -> bool:
        if self.id == V("t_attendance"):
            return _attendance_topic(text)
        raw = text or ""
        if self.topic_re is not None and self.topic_re.search(raw):
            return True
        if self.topic_words and has_any_word(raw, self.topic_words):
            return True
        return any_needle(raw, self.topic_needles)

    def history_match(self, text: str) -> bool:
        raw = text or ""
        if self.history_re and self.history_re.search(raw):
            return True
        return any_needle(raw, self.history_needles)

    def self_match(self, text: str) -> bool:
        if self.self_re is None and not self.self_needles:
            return True
        raw = text or ""
        if self.self_re and self.self_re.search(raw):
            return True
        if self.self_phrases and contains_any_phrase(raw, self.self_phrases):
            return True
        return any_needle(raw, self.self_needles)

    def preferred_api(self, text: str) -> str | None:
        forms = _forms(text)
        if any(self.history_match(form) for form in forms) and self.history_api:
            return self.history_api
        if (self.self_re is not None or self.self_phrases) and not any(
            self.self_match(form) for form in forms
        ):
            return None
        if self.balance_api:
            return self.balance_api
        return self.history_api


#: Instance-local catalog. Add  /  / … as twins without binder ifs.
ESS_SELF_DOMAINS: tuple[EssSelfDomain, ...] = (
    EssSelfDomain(
        id=LV("t_leave"),
        balance_api=LEAVE_BALANCE_API,
        history_api=LEAVE_HISTORY_API,
        topic_re=_LEAVE_TOPIC_RE,
        history_re=_LEAVE_HISTORY_RE,
        topic_needles=LEAVE_TOPIC_AR,
        history_needles=LEAVE_HISTORY_AR,
        honesty_key=ID_LEAVE_HISTORY,
    ),
    EssSelfDomain(
        id=LV("t_loan_2"),
        balance_api=None,
        history_api=LOAN_HISTORY_API,
        topic_words=(
            LV("t_loan_2"), LV("t_loans"),
            LV("t_rx_w_installment"), LV("t_rx_w_installments"),
            LV("t_rx_w_advance"), LV("t_rx_w_advances"),
        ),
        self_phrases=(
            LV("t_my_loan"), LV("t_my_loans"),
            LV("t_rx_w_my_advance"), LV("t_rx_w_my_advances"),
            LV("t_rx_w_my_installment"), LV("t_rx_w_my_installments"),
        ),
        topic_needles=LOAN_TOPIC_AR,
        self_needles=LOAN_SELF_AR,
        honesty_key=ID_LOAN_HISTORY,
    ),
    EssSelfDomain(
        id=LV("t_payslip_2"),
        balance_api=PAYSLIP_API,
        history_api=PAYSLIP_API,
        topic_re=_PAYSLIP_TOPIC_RE,
        topic_needles=PAYSLIP_TOPIC_AR,
        honesty_key=LV("t_payslip_2"),
    ),
    EssSelfDomain(
        id=LV("t_attendance"),
        balance_api=ATTENDANCE_API,
        history_api=ATTENDANCE_API,
        # topic_re unused — topic_match uses _attendance_topic (no new compile).
        topic_re=_PAYSLIP_TOPIC_RE,
        honesty_key=LV("t_attendance"),
    ),
)

def _domain_by_id(domain_id: str):
    """Match a domain id against the pack bound now. Ids are live strings."""
    want = str(domain_id or "").strip()
    for domain in ESS_SELF_DOMAINS:
        if str(domain.id) == want:
            return domain
    return None


def _norm(text: str) -> str:
    return strip_pulse_mode_prefix(text or "").strip()


def _forms(text: str | None) -> tuple[str, ...]:
    """Raw utterance plus the shared Arabic fold. Match either; do not replace."""
    from ai.engine.text.normalize import normalize_text

    raw = _norm(text or "")
    if not raw:
        return ()
    folded = normalize_text(raw)
    if folded == raw:
        return (raw,)
    return (raw, folded)


def is_named_employee_ask(text: str | None) -> bool:
    raw = _norm(text or "")
    if _NAMED_EMP_RE.search(raw) or any_needle(raw, NAMED_EMP_AR):
        return True
    nouns = {
        str(n) for n in (
            V("t_leave"), V("t_rx_w_annual"), V("t_rx_w_sick"), V("t_rx_w_balance"),
            V("t_loan_2"), V("t_payslip_2"), V("t_loans"),
        ) if n
    }
    tokens = raw.split()
    for i, tok in enumerate(tokens):
        clean = tok.strip(".,?؟!'\"")
        if clean in _PROPER_NAME_STOP:
            continue
        if (
            len(clean) >= 3
            and clean[0].isupper()
            and clean[1:].islower()
            and any(t.casefold() in nouns for t in tokens[i + 1 : i + 4])
        ):
            return True
    return False


def _attendance_topic(text: str) -> bool:
    low = (text or "").casefold()
    if any(n and str(n) in low for n in (
        V("t_attendance"),
        V("t_rx_w_clock_in"), V("t_rx_w_clock_in_h"),
        V("t_rx_w_check_in"), V("t_rx_w_check_in_h"),
    )):
        return True
    hour, month = V("t_rx_w_hour"), V("t_rx_w_month")
    if hour and month and hour in low and month in low:
        return True
    return any(tok and str(tok) in (text or "") for tok in ATTENDANCE_AR_TOKENS)


def _is_aspect_followup(text: str) -> bool:
    low = (text or "").casefold().strip()
    raw = (text or "").strip()
    for needle in ASPECT_FOLLOWUP_NEEDLES:
        if needle.casefold() in low or needle in raw:
            return True
    return False


def _is_comprehensive_pick(text: str) -> bool:
    low = (text or "").casefold()
    raw = text or ""
    return any(n in low or n in raw for n in COMPREHENSIVE_NEEDLES)


def get_self_domain(domain_id: str) -> EssSelfDomain | None:
    return _domain_by_id(str(domain_id or ""))


def domain_topic_asked(domain_id: str, text: str | None) -> bool:
    d = get_self_domain(domain_id)
    return bool(d and any(d.topic_match(form) for form in _forms(text)))


def domain_history_asked(domain_id: str, text: str | None) -> bool:
    d = get_self_domain(domain_id)
    return bool(d and any(d.history_match(form) for form in _forms(text)))


def matching_self_domains(text: str | None) -> list[EssSelfDomain]:
    """Domains whose topic detector hits ``text`` (order = catalog order)."""
    forms = _forms(text)
    if not forms:
        return []
    return [
        d for d in ESS_SELF_DOMAINS if any(d.topic_match(form) for form in forms)
    ]


def preferred_self_api(text: str | None) -> str | None:
    """Canonical host API when exactly one ESS domain matches."""
    t = _norm(text or "")
    if not t or is_named_employee_ask(t):
        return None
    # Catalog contract: first-person  / راتبي is get_my_profile
    # (CBAC may deny). Explicit  / قسيمة stays on list_my_payslips.
    from ai.engine.agent.tools import (
        first_person_compensation_ask,
        payslip_specific_ask,
    )

    if first_person_compensation_ask(t) and not payslip_specific_ask(t):
        return str(ID_GET_MY_PROFILE)
    domains = matching_self_domains(t)
    if len(domains) != 1:
        return None
    return domains[0].preferred_api(t)


def ess_self_read_topic(text: str | None) -> str | None:
    """Return domain id when exactly one domain matches; else None."""
    t = _norm(text or "")
    if not t or is_named_employee_ask(t):
        return None
    hits = matching_self_domains(t)
    if len(hits) == 1:
        return hits[0].id
    return None


_BARE_PLACE_EN = T("turn/ess_read.py::_BARE_PLACE_EN")


def is_bare_place_noun(text: str | None) -> bool:
    V("t_true_for_terse_destination_nouns_leave")
    stripped = _norm(text or "").strip("?؟!").casefold()
    if stripped in {word.casefold() for word in _BARE_PLACE_EN}:
        return True
    return stripped in {word.casefold() for word in BARE_PLACE_AR}


def should_skip_module_nav(text: str | None) -> bool:
    """True when the utterance is an ESS data read, not a UI destination."""
    t = _norm(text or "")
    if not t or is_bare_place_noun(t):
        return False
    if preferred_self_api(t) is not None:
        return True
    # Single-domain topic read even when preferred is None ( FAQ).
    domains = matching_self_domains(t)
    return len(domains) == 1 and not is_named_employee_ask(t)


def domains_in_recent_history(history: list | None) -> list[EssSelfDomain]:
    """Unique domains mentioned in recent turns (catalog order)."""
    seen: set[str] = set()
    ordered: list[EssSelfDomain] = []
    for msg in reversed(history or []):
        if not isinstance(msg, dict):
            continue
        content = str(msg.get("content") or "")
        for d in matching_self_domains(content):
            if d.id not in seen:
                seen.add(d.id)
                ordered.append(d)
        if len(ordered) >= len(ESS_SELF_DOMAINS):
            break
    # Preserve catalog order for stability.
    return [d for d in ESS_SELF_DOMAINS if d.id in seen]


def bound_ess_self_api(
    text: str | None,
    *,
    history: list | None = None,
    prior_api: str | None = None,
) -> str | None:
    V("t_api_for_a_chat_bound_ess")
    t = _norm(text or "")
    if not t or is_named_employee_ask(t):
        return None
    from ai.engine.cognition.turn.handoff_agent import is_slot_status_ask
    from ai.engine.cognition.turn.zero_llm import is_calendar_not_balance

    if is_calendar_not_balance(t) or is_slot_status_ask(t):
        return None

    domains = matching_self_domains(t)
    if len(domains) > 1:
        return None
    if len(domains) == 1:
        # P2: a fresh read is routed by the catalog. topic_re stays on the
        # legacy kill switch only. Follow-ups with no domain word still bind
        # from history below.
        from ai.engine.cognition.turn.understand import understand_mode

        if understand_mode() == "v21":
            return None
        return domains[0].preferred_api(t)

    # No domain in this utterance — aspect follow-up against thread focus.
    from ai.engine.cognition.turn.understand import understand_mode

    if understand_mode() == "v21":
        # P9 + P10: the previous tool is on state. Language needles do not choose it.
        api = str(prior_api or "").strip()
        known = {
            name
            for domain in ESS_SELF_DOMAINS
            for name in (domain.balance_api, domain.history_api)
            if name
        }
        if api not in known:
            return None
        words = [w for w in t.split() if w]
        if 2 <= len(words) <= 6:
            return api
        if _is_aspect_followup(t) or _is_comprehensive_pick(t):
            return api
        return None
    if not (_is_aspect_followup(t) or _is_comprehensive_pick(t)):
        return None
    prior = domains_in_recent_history(history)
    if len(prior) != 1:
        return None
    d = prior[0]
    return d.balance_api or d.history_api


def build_ess_self_tool_call(api_name: str, turn_id: str = "") -> dict[str, Any]:
    """Injected ``call_host_api`` for a bound ESS self-read."""
    import json as _json

    suffix = (turn_id or "ess")[:8]
    api = str(api_name or "").strip()
    return {
        "id": f"call_ess_{suffix}",
        "function": {
            "name": "call_host_api",
            "arguments": _json.dumps({
                "api_name": api,
                "explanation": f"Bound ESS self-read: {api}",
            }),
        },
    }


def answer_bound_ess_tools(
    completed_tools: list | None,
    *,
    api_name: str,
    user_message: str,
    unread_text: bool = True,
    catalog_entry: dict | None = None,
    fields: list[str] | None = None,
) -> str:
    """0-LLM restatement or honesty from completed bound tools.

    ``unread_text=False`` returns "" for a read no restater covers, so the
    caller can render the rows instead of claiming the read failed.
    """
    from ai.engine.cognition.plan.export_bind import render_bound_catalog_read

    lang = "ar" if detect_lang(user_message or "") == "ar" else "en"
    api = str(api_name or "").strip()
    for item in completed_tools or []:
        if not isinstance(item, dict):
            continue
        if item.get("error"):
            continue
        data = _unwrap(item.get("result"))
        if isinstance(data, dict) and data.get("unauthorized"):
            return UNAUTHORIZED_TEXT[lang]
        empty = empty_history_misread([item], user_message=user_message)
        if empty is not None and api in history_apis() and api not in balance_apis():
            return str(empty.get("text") or "")
        restated = render_bound_catalog_read(
            item, api, lang, catalog_entry=catalog_entry, fields=fields,
        )
        if restated:
            from ai.engine.cognition.turn.grounding import ungrounded_numbers

            bad = ungrounded_numbers(restated, [data])
            if bad:
                # Prefer catalog empty honesty over a numeral that never appeared.
                for d in ESS_SELF_DOMAINS:
                    if same_id(api, d.history_api) and d.honesty_key in HONEST_EMPTY[lang]:
                        return HONEST_EMPTY[lang][d.honesty_key]
                return empty_render_text(str(ID_NO_BALANCE), lang) or restated
            return restated
    if api == LEAVE_BALANCE_API:
        return EMPTY_BALANCE_TEXT[lang]
    for d in ESS_SELF_DOMAINS:
        if api in {d.balance_api, d.history_api}:
            return HONEST_EMPTY[lang][d.honesty_key]
    if not unread_text:
        return ""
    return (
        "لم أتمكن من قراءة البيانات من النظام."
        if lang == "ar"
        else "Could not read that data from the host."
    )


def preferred_admin_leave_api(text: str | None) -> str | None:
    V("t_named_employee_leave_remaining_entitlements_list")
    t = _norm(text or "")
    if not domain_topic_asked(V("t_leave"), t) or not is_named_employee_ask(t):
        return None
    return str(ID_LIST_LEAVE_ENTITLEMENTS)


def leave_zero_claim_in_text(text: str | None) -> bool:
    """True when copy invents remaining/used/pending = 0 days."""
    raw = text or ""
    return bool(
        _LEAVE_ZERO_CLAIM_RE.search(raw) or any_needle(raw, LEAVE_ZERO_CLAIM_AR)
    )


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
    """When history list is empty but user asked balance/topic — honest reply."""
    topic = ess_self_read_topic(user_message)
    if not topic:
        # Still honesty when tools are empty history for a known twin.
        pass
    want_balance = topic == V("t_leave") and not domain_history_asked(V("t_leave"), user_message)
    lang = "ar" if detect_lang(user_message or "") == "ar" else "en"
    for item in completed_tools or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        api = _api_name(item)
        data = _unwrap(item.get("result"))
        if not _payload_empty_list(data):
            continue
        if api == LEAVE_HISTORY_API and (want_balance or topic == V("t_leave") or topic is None):
            return {
                "decision": "answer",
                "text": HONEST_EMPTY[lang][str(ID_LEAVE_HISTORY)],
                "gate": str(ID_EMPTY_LEAVE_HISTORY),
                "prefer_api": LEAVE_BALANCE_API,
            }
        if api == LOAN_HISTORY_API and (topic == V("t_loan_2") or topic is None):
            return {
                "decision": "answer",
                "text": HONEST_EMPTY[lang][str(ID_LOAN_HISTORY)],
                "gate": str(ID_EMPTY_LOAN_HISTORY),
            }
        if api == PAYSLIP_API and (topic == V("t_payslip_2") or topic is None):
            return {
                "decision": "answer",
                "text": HONEST_EMPTY[lang][V("t_payslip_2")],
                "gate": str(ID_EMPTY_PAYSLIP),
            }
    return None


def guidance_block(*, audience: str = "ess") -> str:
    """Prompt fragment — balance API first; never invent from empty history."""
    host = copy_text(
        "t_rx_copy_ess_guidance",
        slot_a=V("t_leave_2"),
        slot_b=V("t_leave"),
        slot_c=V("t_loan"),
        slot_d=V("t_payslip"),
        balance_api=LEAVE_BALANCE_API,
        history_api=LEAVE_HISTORY_API,
        loan_api=LOAN_HISTORY_API,
        payslip_api=PAYSLIP_API,
    )
    generic = (
        "- Never invent remaining/used/pending = 0 from an empty history list.\n"
        + V("t_do_not_offer_to_open_leave")
    )
    if not host:
        return generic
    return "ESS SELF-READ CONTRACT (mandatory):\n" + host + generic
