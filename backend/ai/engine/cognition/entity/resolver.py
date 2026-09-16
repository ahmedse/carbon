"""ECF-2 — Generic entity resolver.

resolve(descriptor, query, *, fetch_fn) → ResolveResult

The algorithm is domain-neutral. All entity-specific knowledge comes from the
EntityDescriptor (ADR-0032). The `fetch_fn` injectable keeps the engine
database-free (RULE_20).

Scoring tiers (descending priority):
  1. Identifier exact match  (employee_no, civil_id, id)
  2. Name field exact         (normalised substring match, weight-boosted)
  3. Name field fuzzy         (character n-gram similarity, Arabic-aware)
  4. Transliteration bridge   (Arabic↔Latin approximate)

resolve() always populates `searched_total` so the caller can produce an
honest grounded-none ("searched 530 of 530, none found") instead of a bare
"not found" — which is the contract violation that caused the real failures.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Callable

from ai.engine.cognition.entity.registry import EntityDescriptor, SearchField
from ai.engine.cognition.turn.navigation import normalize_text, detect_lang

# Inject: callable(model_path, filters, fields, limit) → list[dict]
FetchFn = Callable[[str, dict, list[str], int], list[dict]]

# Minimum n-gram similarity to enter the candidate list.
_FUZZY_THRESHOLD = 0.35
# Similarity gap for outright match vs disambiguation.
_MATCH_GAP = 0.18
# Minimum score for a top candidate to be returned at all.
_MIN_SCORE = 0.38
# Floor below which we stop even *suggesting* — anything above this but below
# _MIN_SCORE becomes a "did you mean" hint instead of a hard refusal.
_SUGGEST_THRESHOLD = 0.25


@dataclass
class ResolveResult:
    action: str = "none"                           # "match" | "disambiguate" | "none"
    record: dict | None = None
    candidates: list[dict] = field(default_factory=list)
    suggestions: list[dict] = field(default_factory=list)  # "did you mean" near-misses
    searched_total: int = 0                        # always set — "searched N of N"
    lang: str = "en"
    query_normalized: str = ""
    matched_field: str = ""


# ── Normalisation helpers ─────────────────────────────────────────────────────

_AR_TRANSLITERATION: list[tuple[str, str]] = [
    # common Arabic → Latin mappings (approximate, good enough for soft match)
    ("ا", "a"), ("ب", "b"), ("ت", "t"), ("ث", "th"), ("ج", "j"),
    ("ح", "h"), ("خ", "kh"), ("د", "d"), ("ذ", "th"), ("ر", "r"),
    ("ز", "z"), ("س", "s"), ("ش", "sh"), ("ص", "s"), ("ض", "d"),
    ("ط", "t"), ("ظ", "z"), ("ع", "a"), ("غ", "gh"), ("ف", "f"),
    ("ق", "q"), ("ك", "k"), ("ل", "l"), ("م", "m"), ("ن", "n"),
    ("ه", "h"), ("و", "w"), ("ي", "y"), ("ء", ""),
]


def _transliterate_ar_to_latin(text: str) -> str:
    for ar, lat in _AR_TRANSLITERATION:
        text = text.replace(ar, lat)
    return text


_VOWELS = set("aeiou")


def _consonant_skeleton(s: str) -> str:
    """Drop vowels — Arabic omits short vowels, English writes them, so the
    consonant skeleton is the reliable cross-script comparison key
    (سلمان→'slmn', 'salman'→'slmn')."""
    return "".join(ch for ch in s if ch.isalnum() and ch not in _VOWELS)


def _token_skeleton_sim(a: str, b: str) -> float:
    """Similarity of two consonant skeletons (exact/prefix/ngram).

    A prefix match is only "strong" when the shared consonant prefix is
    substantial (>= 3 consonants). A 2-consonant prefix (e.g. "ry" vs "ryn")
    is too ambiguous for cross-script names, so it is demoted and can never
    count as a confident match — this was the "رينا" → "Rey Sullano Salva"
    false positive.
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a.startswith(b) or b.startswith(a):
        return 0.9 if min(len(a), len(b)) >= 3 else 0.6
    return max(_ngram_similarity(a, b, 2), _ngram_similarity(a, b, 3))


def _cross_script_score(query_latin: str, stored_norm: str) -> float:
    """Fraction of query name-tokens whose consonant skeleton matches a stored
    token. Handles Arabic query → English-stored names, subset name parts, and
    unwritten short vowels. Two strongly-matched distinctive tokens is high
    confidence even if other tokens don't match (a longer, more specific query
    must never score worse than a shorter one)."""
    q_tokens = [_consonant_skeleton(t) for t in query_latin.split() if len(t) >= 2]
    s_tokens = [_consonant_skeleton(t) for t in stored_norm.split() if len(t) >= 2]
    q_tokens = [t for t in q_tokens if len(t) >= 2]
    s_tokens = [t for t in s_tokens if len(t) >= 2]
    if not q_tokens or not s_tokens:
        return 0.0
    matched = 0.0
    strong = 0
    for qt in q_tokens:
        best = max((_token_skeleton_sim(qt, st) for st in s_tokens), default=0.0)
        if best >= 0.7:
            matched += best
        if best >= 0.85:
            strong += 1
    coverage = matched / len(q_tokens)
    # Two+ strongly-matched distinctive name parts = confident identification.
    if strong >= 2:
        return max(coverage, 0.75)
    return coverage


def _ngram_similarity(a: str, b: str, n: int = 2) -> float:
    """Character n-gram Dice coefficient — fast, language-agnostic."""
    if not a or not b:
        return 0.0
    def ngrams(s: str) -> set[str]:
        return {s[i:i+n] for i in range(len(s) - n + 1)} if len(s) >= n else {s}
    sa, sb = ngrams(a), ngrams(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return 2 * len(sa & sb) / (len(sa) + len(sb))


def _score_value(query_norm: str, stored_norm: str, weight: float, lang: str) -> float:
    """Score a single (query, stored_value) pair."""
    if not query_norm or not stored_norm:
        return 0.0

    # Tier 1: exact match after normalization
    if query_norm == stored_norm:
        return weight * 1.0

    # Tier 2: substring containment (query inside stored or vice versa)
    if query_norm in stored_norm or stored_norm in query_norm:
        overlap = len(min(query_norm, stored_norm, key=len))
        base = overlap / max(len(query_norm), len(stored_norm))
        return weight * base * 0.85

    # Tier 3: n-gram similarity
    sim = max(
        _ngram_similarity(query_norm, stored_norm, n=2),
        _ngram_similarity(query_norm, stored_norm, n=3),
    )
    if sim >= _FUZZY_THRESHOLD:
        return weight * sim * 0.7

    # Tier 4: transliteration bridge (Arabic ↔ Latin)
    if lang == "ar":
        latin_query = _transliterate_ar_to_latin(query_norm)
        sim_t = max(
            _ngram_similarity(latin_query, stored_norm, 2),
            _ngram_similarity(latin_query, stored_norm, 3),
        )
        # Consonant-skeleton token match — the reliable cross-script signal
        # (handles Arabic query vs English-stored names, unwritten vowels).
        cross = _cross_script_score(latin_query, stored_norm)
        best_cross = max(sim_t, cross)
        if best_cross >= 0.5:
            return weight * best_cross * 0.75
        if sim_t >= _FUZZY_THRESHOLD:
            return weight * sim_t * 0.55

    return 0.0


# ── Identifier resolution (highest priority) ─────────────────────────────────

def _try_identifier_match(
    descriptor: EntityDescriptor,
    query: str,
    fetch_fn: FetchFn,
) -> dict | None:
    """Try each declared identifier as an exact lookup. Returns a record or None."""
    query_stripped = query.strip()
    for id_field in descriptor.identifiers:
        try:
            results = fetch_fn(
                descriptor.model,
                {id_field: query_stripped},
                [],   # all fields
                2,    # need 2 to detect duplicates
            )
            if results:
                return results[0]
        except Exception:  # noqa: BLE001 — identifier miss is normal, not fatal
            pass
    return None


# ── Main resolver ─────────────────────────────────────────────────────────────

def resolve(
    descriptor: EntityDescriptor,
    query: str,
    *,
    fetch_fn: FetchFn,
    scope_ids: list | None = None,
) -> ResolveResult:
    """Resolve *query* against the entity described by *descriptor*.

    *fetch_fn* is injected by the host layer (host_executor) — the engine
    never touches Django ORM directly.

    *scope_ids* is the list of org-unit ids for RULE_12 scoping; None = global
    admin / all visible.

    Returns a ResolveResult where:
      action="match"        — single unambiguous record found
      action="disambiguate" — multiple near-equal candidates
      action="none"         — searched all records, none qualify
                              searched_total is always populated.
    """
    if not query or not descriptor:
        return ResolveResult(action="none")

    lang = detect_lang(query)
    query_norm = normalize_text(query)

    # ── Phase 1: Identifier exact match ──────────────────────────────────────
    exact = _try_identifier_match(descriptor, query.strip(), fetch_fn)
    if exact:
        total = _count_all(descriptor, fetch_fn, scope_ids)
        return ResolveResult(
            action="match",
            record=exact,
            searched_total=total,
            lang=lang,
            query_normalized=query_norm,
            matched_field="identifier",
        )

    # ── Phase 2: Name-field scan across ALL records ───────────────────────────
    # This is the core fix: never cap at 100 rows for existence checks.
    # Scan ALL declared search fields regardless of query language — a person's
    # name may be stored in English even when the query is Arabic (and vice
    # versa). Language only steers scoring (transliteration), not field choice.
    search_fields = descriptor.search_fields

    # Fetch all records with relevant fields (complete scan, never capped)
    fields_needed = list({sf.field for sf in search_fields})
    scope_filter: dict = {}
    if scope_ids is not None and descriptor.scope_lookup:
        scope_filter[descriptor.scope_lookup] = scope_ids

    all_records = fetch_fn(descriptor.model, scope_filter, fields_needed + ["id", "employee_no"], limit=0)
    searched_total = len(all_records)

    scored: list[tuple[dict, float, str]] = []  # (record, score, matched_field)
    suggested: list[tuple[dict, float, str]] = []  # near-misses for "did you mean"
    for record in all_records:
        best_score = 0.0
        best_field = ""
        for sf in search_fields:
            stored_raw = record.get(sf.field, "")
            if not stored_raw:
                continue
            stored_norm = normalize_text(str(stored_raw))
            score = _score_value(query_norm, stored_norm, sf.weight, lang)
            if score > best_score:
                best_score = score
                best_field = sf.field
        if best_score >= _MIN_SCORE:
            scored.append((record, best_score, best_field))
        elif best_score >= _SUGGEST_THRESHOLD:
            suggested.append((record, best_score, best_field))

    scored.sort(key=lambda x: -x[1])
    suggested.sort(key=lambda x: -x[1])

    if not scored:
        return ResolveResult(
            action="none",
            suggestions=[r for r, _, _ in suggested[:5]],
            searched_total=searched_total,
            lang=lang,
            query_normalized=query_norm,
        )

    top_score = scored[0][1]
    top_record, _, top_field = scored[0]

    # Single unambiguous match: top score >= threshold AND gap from runner-up is large
    if len(scored) == 1 or (top_score - scored[1][1]) >= _MATCH_GAP:
        return ResolveResult(
            action="match",
            record=top_record,
            searched_total=searched_total,
            lang=lang,
            query_normalized=query_norm,
            matched_field=top_field,
        )

    # Multiple near-equal candidates → disambiguation
    candidates = [r for r, _, _ in scored[:5]]
    return ResolveResult(
        action="disambiguate",
        candidates=candidates,
        searched_total=searched_total,
        lang=lang,
        query_normalized=query_norm,
        matched_field=top_field,
    )


def _count_all(
    descriptor: EntityDescriptor,
    fetch_fn: FetchFn,
    scope_ids: list | None,
) -> int:
    """Return the total population count for context (identifier match path)."""
    scope_filter: dict = {}
    if scope_ids is not None and descriptor.scope_lookup:
        scope_filter[descriptor.scope_lookup] = scope_ids
    try:
        return len(fetch_fn(descriptor.model, scope_filter, ["id"], 0))
    except Exception:  # noqa: BLE001
        return 0
