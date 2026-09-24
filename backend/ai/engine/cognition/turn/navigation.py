from __future__ import annotations
from ai.engine.cognition.phrase_tables import T
from ai.engine.pack_vocab import V
V("t_bilingual_en_ar_navigation_grounding_navigation")


import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

from ai.engine.cognition.turn.navigation_i18n import (
    HOW_WHERE_AR,
    NAV_VERB_AR,
    PLACE_TOPIC_AR,
    SELF_READ_POSSESSIVE_AR,
    SELF_READ_POSSESSIVE_EN,
    any_needle,
)
from ai.engine.text.word_match import has_any_word, has_arabic_script

# Arabic diacritics / tashkeel to strip (harakat + other combining marks are
# removed separately via unicodedata.combining).
_AR_TASHKEEL = T("turn/navigation.py::_AR_TASHKEEL")

# Orthographic folding — the cheapest, safe normalisations that make
# "الموظفون" / ""-style variance and hamza variants match consistently.
_AR_FOLD: tuple[tuple[str, str], ...] = (
    ("أ", "ا"), ("إ", "ا"), ("آ", "ا"),
    ("ة", "ه"), ("ى", "ي"), ("ؤ", "ء"), ("ئ", "ء"),
)

# Arabic tokens must share this many leading characters to count as a fuzzy
# match (catches case-ending variance like الموظفون ↔ , but keeps
# الراتب vs الرواتب distinct).
_AR_FUZZY_PREFIX_MIN = 5


# ── Types ─────────────────────────────────────────────────────────────────────

@dataclass
class NavigationTarget:
    """A single declared, static navigation destination."""
    name: str            # stable id (e.g. "people_home")
    route: str           # in-app route (e.g. "/people")
    kind: str            # "app" | "page"
    label: str           # display label (English preferred)
    labels: list[str] = field(default_factory=list)  # normalised en+ar aliases


@dataclass
class NavigationResolution:
    """Outcome of the resolver."""
    action: str = "none"          # "navigate" | "disambiguate" | "none"
    targets: list[NavigationTarget] = field(default_factory=list)
    lang: str = ""                # "en" | "ar" | "" (undetected)
    matched: str = ""             # the alias that matched (debug)


# ── Normalisation ─────────────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    """Canonicalise a string for alias matching (bilingual)."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    # Drop combining diacritics (Latin accents, Arabic harakat) and explicit
    # tashkeel code points.
    text = "".join(
        ch for ch in text
        if ch not in _AR_TASHKEEL and not unicodedata.combining(ch)
    )
    for src, dst in _AR_FOLD:
        text = text.replace(src, dst)
    text = text.replace("\u0640", "")  # kashida (tatweel)
    text = text.lower()
    return " ".join(text.split())


def detect_lang(text: str) -> str:
    """Return "ar" if the message contains Arabic script, else "en"."""
    return "ar" if _AR_SEARCH(text) else "en"


def _AR_SEARCH(text: str) -> bool:
    return has_arabic_script(text or "")


# ── Target loading ────────────────────────────────────────────────────────────

def load_targets(instance_config: dict | None) -> list[NavigationTarget]:
    """Read static navigation targets (``app`` / ``page``) from instance config.

    Entity-detail targets (with ``{id}`` in the path) are intentionally skipped:
    they require a resolver + id and remain on the tool/open_entity path.
    """
    routes = (instance_config or {}).get("navigation_routes") or []
    targets: list[NavigationTarget] = []
    for route in routes:
        if not isinstance(route, dict):
            continue
        kind = route.get("type") or route.get("kind") or "page"
        if kind not in ("app", "page"):
            continue
        name = route.get("name") or ""
        path = route.get("path") or ""
        if not name or not path or "{" in path:
            continue

        labels_cfg = route.get("labels") or {}
        en_labels = list(labels_cfg.get("en") or [])
        ar_labels = list(labels_cfg.get("ar") or [])
        if not en_labels and not ar_labels:
            fallback = route.get("label") or name.replace("_", " ").strip()
            en_labels = [fallback]

        label = route.get("label") or (en_labels[0] if en_labels else ar_labels[0])
        # Include the display label itself so an LLM emitting the exact label
        # ("People & ") still grounds correctly.
        combined = [normalize_text(l) for l in en_labels + ar_labels + [label]]
        combined = [l for l in combined if l]
        if not combined:
            continue

        targets.append(NavigationTarget(
            name=name,
            route=path,
            kind=kind,
            label=label,
            labels=combined,
        ))
    return targets


# ── Matching ──────────────────────────────────────────────────────────────────

def _label_hit(label: str, message: str) -> int:
    """Return a specificity score (>0) if ``label`` matches ``message``."""
    if not label:
        return 0
    # Short English labels ("home", "my", "hr") must be whole tokens so
    # "take-home" and "my project" do not navigate.
    if not _AR_SEARCH(label) and len(label) < 5:
        if label in message.split():
            return len(label)
        return 0
    # Tier 1 — exact substring (handles "people" in "people app", and the
    # exact Arabic form).
    if label in message:
        return len(label)
    # Tier 2 — Arabic fuzzy: a message token and this label share a common
    # prefix ≥ _AR_FUZZY_PREFIX_MIN (case-ending variance). English stays
    # strict to avoid "pay" matching "" and the like.
    if _AR_SEARCH(label):
        msg_tokens = message.split()
        label_tokens = label.split()
        best = 0
        for lt in label_tokens:
            if len(lt) < _AR_FUZZY_PREFIX_MIN:
                continue
            for mt in msg_tokens:
                if len(mt) < _AR_FUZZY_PREFIX_MIN:
                    continue
                common = _common_prefix_len(lt, mt)
                if common >= _AR_FUZZY_PREFIX_MIN and common > best:
                    best = common
        if best:
            return best
    return 0


def _common_prefix_len(a: str, b: str) -> int:
    n = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        n += 1
    return n


# An explicit "app" noun (English "app"/"application" or Arabic "تطبيق") boosts
# ``type: app`` home targets over same-named sub-pages, so "تطبيق "
# (the People *app*) resolves to /people rather than the  page.
_APP_NOUN_BOOST = 1000
# Minimum score gap for the top target to win outright; below this, the
# resolver offers candidates instead of guessing.
_DISAMBIGUATION_GAP = 3


def _has_app_noun(norm: str) -> bool:
    return bool(
        has_any_word(norm, ("app", "application", "module"))
        or any(a in norm for a in ("تطبيق", "ابليكيشن"))
    )


def _match_targets(
    targets: Iterable[NavigationTarget], message: str,
) -> list[tuple[NavigationTarget, int]]:
    norm = normalize_text(message)
    app_noun = _has_app_noun(norm)
    scored: list[tuple[NavigationTarget, int]] = []
    for target in targets:
        best = 0
        for label in target.labels:
            score = _label_hit(label, norm)
            if score > best:
                best = score
        if best:
            if app_noun and target.kind == "app":
                best += _APP_NOUN_BOOST
            scored.append((target, best))
    # Rank by specificity (longest match / boost) descending, then stable by
    # route so the winner and the runner-up are deterministic.
    scored.sort(key=lambda item: (-item[1], item[0].route))
    return scored


def _dedupe_by_route_scored(
    scored: list[tuple[NavigationTarget, int]],
) -> list[tuple[NavigationTarget, int]]:
    seen: set[str] = set()
    out: list[tuple[NavigationTarget, int]] = []
    for target, score in scored:
        if target.route in seen:
            continue
        seen.add(target.route)
        out.append((target, score))
    return out


# ── Public resolver ───────────────────────────────────────────────────────────

def ground_navigation(
    concept: str, instance_config: dict | None,
) -> NavigationResolution:
    """Map a target *concept* to the instance's enumerated navigation routes.

    This is the GROUNDING layer — it takes a concept string (from the LLM
    intent classifier, or a deterministic verb-strip) and resolves it to real,
    declared routes. It never invents a destination and never trusts a raw
    route from the LLM. No verb-gate here: the caller has already decided the
    user wants to navigate.

    Returns a ``NavigationResolution`` whose ``action`` is one of:
      * "navigate"      — exactly one target; propose it and let the user confirm.
      * "disambiguate"  — multiple near-equal targets; offer candidates.
      * "none"          — no declared target matched; fall through.
    """
    if not concept:
        return NavigationResolution()

    targets = load_targets(instance_config)
    if not targets:
        return NavigationResolution()

    scored = _match_targets(targets, concept)
    if not scored:
        return NavigationResolution()

    distinct = _dedupe_by_route_scored(scored)
    lang = detect_lang(concept)

    top_score = distinct[0][1]
    if len(distinct) == 1 or (top_score - distinct[1][1]) >= _DISAMBIGUATION_GAP:
        winner = [distinct[0][0]]
        return NavigationResolution(
            action="navigate", targets=winner, lang=lang,
            matched=winner[0].name,
        )
    return NavigationResolution(
        action="disambiguate",
        targets=[t for t, _s in distinct],
        lang=lang,
        matched=",".join(t.name for t, _s in distinct),
    )


# ── Interrogative guard (fast path only) ──────────────────────────────────────
# A question that merely names a module ("When will next month's  be
# processed?", «هل ستتم الموافقة عليه؟») is not a navigation command. The raw
# fast path grounds the whole utterance, so it needs this guard; the LLM-intent
# path (``ground_navigation`` on a chosen concept) does not.

_QUESTION_WORDS_EN = T("turn/navigation.py::_QUESTION_WORDS_EN")
# Normalised forms (see ``normalize_text``): hamza/alef folded.
_QUESTION_WORDS_AR = T("turn/navigation.py::_QUESTION_WORDS_AR")
_NAV_VERB_WORDS = T("turn/navigation.py::_NAV_VERB_WORDS")
_NAV_VERB_PHRASES = T("turn/navigation.py::_NAV_VERB_PHRASES")
_HOW_HEADS = T("turn/navigation.py::_HOW_HEADS")
_HOW_VERBS = T("turn/navigation.py::_HOW_VERBS")
_WHERE_HEADS = T("turn/navigation.py::_WHERE_HEADS")
_WHERE_TAILS = T("turn/navigation.py::_WHERE_TAILS")
_PLACE_TOPICS = T("turn/navigation.py::_PLACE_TOPICS")


def _has_nav_verb_en(text: str) -> bool:
    from ai.engine.text.word_match import contains_any_phrase, has_any_word

    return has_any_word(text, _NAV_VERB_WORDS) or contains_any_phrase(text, _NAV_VERB_PHRASES)


def _how_where_ui_en(text: str) -> bool:
    cf = (text or "").casefold()
    for head, tails in ((_HOW_HEADS, _HOW_VERBS), (_WHERE_HEADS, _WHERE_TAILS)):
        for prefix in head:
            pos = cf.find(prefix)
            if pos < 0:
                continue
            rest = cf[pos + len(prefix):].split()
            if rest and rest[0] in tails:
                return True
    return False


def _place_topic_token(text: str) -> str:
    from ai.engine.text.word_match import has_word

    for word in _PLACE_TOPICS:
        if has_word(text, word):
            return word
    return ""
_INTERROGATIVE_MIN_TOKENS = 3


def _has_nav_verb(norm: str) -> bool:
    return bool(
        _has_nav_verb_en(norm)
        or any(f" {v}" in norm or norm.startswith(v) for v in NAV_VERB_AR)
    )


def is_interrogative_non_command(message: str) -> bool:
    V("t_true_when_message_is_a_question")
    raw = (message or "").strip()
    if not raw:
        return False
    norm = normalize_text(raw)
    tokens = re.findall(r"[\w']+", norm)
    if len(tokens) <= _INTERROGATIVE_MIN_TOKENS:
        return False
    first = tokens[0]
    interrogative = (
        raw.endswith(("?", "؟"))
        or first in _QUESTION_WORDS_EN
        or first in _QUESTION_WORDS_AR
    )
    if not interrogative:
        return False
    return not _has_nav_verb(norm)


def is_first_person_self_read(message: str) -> bool:
    """True when the utterance asks for the caller's own ESS data, not a UI hop."""
    raw = (message or "").strip()
    if not raw:
        return False
    norm = normalize_text(raw)
    if any_needle(raw, SELF_READ_POSSESSIVE_AR):
        return True
    tokens = norm.split()
    if "mine" in tokens:
        return True
    if " my " in f" {norm} ":
        return True
    return any_needle(raw, SELF_READ_POSSESSIVE_EN)


def resolve_navigation(
    message: str, instance_config: dict | None,
) -> NavigationResolution:
    V("t_deterministic_zero_token_fast_path_used")
    # How/where UI ("where can I find my  balance?") still grounds the
    # place noun. Bare ESS topic reads («عن الإجازات», "my ", "my
    # " without a nav verb) must answer from host APIs — not open UI.
    if is_how_where_ui(message):
        topic = place_topic(message)
        if topic:
            return ground_navigation(topic, instance_config)
        return NavigationResolution(lang=detect_lang(message or ""))
    if is_first_person_self_read(message):
        return NavigationResolution(lang=detect_lang(message or ""))
    try:
        from ai.engine.cognition.turn.ess_read import should_skip_module_nav

        if should_skip_module_nav(message) and not _has_nav_verb(
            normalize_text(message or "")
        ):
            return NavigationResolution(lang=detect_lang(message or ""))
    except Exception:  # noqa: BLE001 — never block nav on import/edge failure
        pass
    if is_interrogative_non_command(message):
        return NavigationResolution(lang=detect_lang(message or ""))
    return ground_navigation(message or "", instance_config)


def is_how_where_ui(message: str) -> bool:
    """True for how-do-I / where-can-I-find UI questions (C8 FAQ, 0 LLM)."""
    raw = (message or "").strip()
    return bool(
        raw
        and (_how_where_ui_en(raw) or any_needle(raw, HOW_WHERE_AR))
    )


def place_topic(message: str) -> str:
    """Extract a declared place noun from a how/where UI ask."""
    raw = message or ""
    token = _place_topic_token(raw)
    if not token:
        for needle in PLACE_TOPIC_AR:
            if needle in raw:
                token = needle
                break
    if not token:
        return ""
    aliases = {
        V("t_loan_2"): V("t_loans"),
        V("t_payslip_2"): V("t_payslips"),
        "notification": "notifications",
        V("t_قرض"): V("t_loans"),
        V("t_قروض"): V("t_loans"),
        V("t_إجازة"): V("t_leave"),
        V("t_اجازة"): V("t_leave"),
        V("t_راتب"): V("t_payroll"),
        V("t_رواتب"): V("t_payroll"),
        "قسيمة": V("t_payslips"),
        V("t_حضور"): V("t_attendance"),
        "رئيسية": "home",
        "إشعار": "notifications",
    }
    return aliases.get(token, token)
