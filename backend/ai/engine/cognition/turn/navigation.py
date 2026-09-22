"""Bilingual (EN + AR) navigation GROUNDING.

Navigation is a first-class intent, but *comprehension* of it belongs to the
LLM intent classifier (``intent.py``): only the LLM can tell an actual request
to navigate ("take me to the people app") from a question or complaint that
merely mentions a place ("why are you designed to show all employees' leaves?",
"مش بسألك روح مكان"). A keyword/verb matcher cannot — it fires on any sentence
that happens to contain a verb + a place noun, including negations and
meta-questions.

So this module does NOT decide *whether* the user wants to navigate. It only
*grounds* a target concept the LLM already chose against the instance's
*declared* navigation targets (see ``navigation_routes`` in ``instance.yaml``).
This is the anti-hallucination guard: it never invents a destination and never
trusts a raw route from the LLM — it maps a concept to a real, enumerated route.

Design:
  1. Unicode normalisation — NFKC, strip tashkeel/diacritics, fold Arabic
     orthographic variants (أإآ→ا · ة→ه · ى→ي · ؤ/ئ→ء) and kashida.
  2. Alias matching      — each target declares its own en/ar synonyms.
  3. Graceful ambiguity  — multiple matches return candidates, never a dead-end.
  4. No match            — returns ``none`` and the normal pipeline proceeds.

Entry point: :func:`ground_navigation` — a pure function of
``(concept, instance_config)``, no LLM, no I/O, deterministic.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

_AR_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")

# Arabic diacritics / tashkeel to strip (harakat + other combining marks are
# removed separately via unicodedata.combining).
_AR_TASHKEEL: frozenset[str] = frozenset(
    "\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652\u0670\u0640"
    "\u0653\u0654\u0655\u0657\u0658"
)

# Orthographic folding — the cheapest, safe normalisations that make
# "الموظفون" / "الموظفين"-style variance and hamza variants match consistently.
_AR_FOLD: tuple[tuple[str, str], ...] = (
    ("أ", "ا"), ("إ", "ا"), ("آ", "ا"),
    ("ة", "ه"), ("ى", "ي"), ("ؤ", "ء"), ("ئ", "ء"),
)

# Arabic tokens must share this many leading characters to count as a fuzzy
# match (catches case-ending variance like الموظفون ↔ الموظفين, but keeps
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
    return bool(_AR_SCRIPT_RE.search(text or ""))


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
        # ("People & Payroll") still grounds correctly.
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
    # Tier 1 — exact substring (handles "people" in "people app", and the
    # exact Arabic form).
    if label in message:
        return len(label)
    # Tier 2 — Arabic fuzzy: a message token and this label share a common
    # prefix ≥ _AR_FUZZY_PREFIX_MIN (case-ending variance). English stays
    # strict to avoid "pay" matching "payroll" and the like.
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
# ``type: app`` home targets over same-named sub-pages, so "تطبيق الموظفين"
# (the People *app*) resolves to /people rather than the employees page.
_APP_NOUN_EN_RE = re.compile(r"\bapp\b|\bapplication\b|\bmodule\b")
_APP_NOUN_BOOST = 1000
# Minimum score gap for the top target to win outright; below this, the
# resolver offers candidates instead of guessing.
_DISAMBIGUATION_GAP = 3


def _has_app_noun(norm: str) -> bool:
    return bool(_APP_NOUN_EN_RE.search(norm)) or any(
        a in norm for a in ("تطبيق", "ابليكيشن")
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
# A question that merely names a module ("When will next month's payroll be
# processed?", «هل ستتم الموافقة عليه؟») is not a navigation command. The raw
# fast path grounds the whole utterance, so it needs this guard; the LLM-intent
# path (``ground_navigation`` on a chosen concept) does not.

_QUESTION_WORDS_EN: frozenset[str] = frozenset({
    "when", "how", "why", "what", "is", "will", "can", "does",
})
# Normalised forms (see ``normalize_text``): hamza/alef folded.
_QUESTION_WORDS_AR: frozenset[str] = frozenset({
    "متي", "هل", "كيف", "لماذا", "ما", "ماذا",
})
_NAV_VERB_EN_RE = re.compile(
    r"\b(?:open|go\s+to|goto|navigate\s+to|take\s+me\s+to|show\s+me)\b"
)
# Normalised Arabic imperative/request stems: افتح / اذهب / أرني (→ ارني) /
# روح / ودّيني (→ وديني).
_NAV_VERB_AR_RE = re.compile(
    r"(?:^|\s)(?:و|ف)?(?:افتح|تفتح|اذهب|تذهب|ارني|روح|وديني|خذني)"
)
_INTERROGATIVE_MIN_TOKENS = 3


def _has_nav_verb(norm: str) -> bool:
    return bool(_NAV_VERB_EN_RE.search(norm) or _NAV_VERB_AR_RE.search(norm))


def is_interrogative_non_command(message: str) -> bool:
    """True when ``message`` is a question (> 3 tokens) without a nav verb.

    Interrogative = ends with ``?``/``؟`` or starts with an EN/AR question word.
    Pure noun phrases ("payroll", "الرواتب") and explicit commands
    ("Can you open payroll?") are not affected.
    """
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


def resolve_navigation(
    message: str, instance_config: dict | None,
) -> NavigationResolution:
    """Deterministic zero-token fast path used by the turn runner.

    Grounds the raw user message against declared routes. Same contract as
    :func:`ground_navigation` — never invents destinations. Questions that
    merely mention a module noun return ``none`` (the normal pipeline answers).
    """
    if is_interrogative_non_command(message):
        return NavigationResolution(lang=detect_lang(message or ""))
    return ground_navigation(message or "", instance_config)
