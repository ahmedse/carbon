"""Word/phrase detectors without pre-compiled patterns (ADR-0049 L7).

Use for simple EN routing where word boundaries matter but alternation regex
is unnecessary. Arabic literals stay in ``*_i18n`` needle tables.
"""
from __future__ import annotations


def casefold(text: str) -> str:
    return (text or "").casefold()


def contains_phrase(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    return phrase.casefold() in casefold(text)


def contains_any_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    cf = casefold(text)
    return any(p.casefold() in cf for p in phrases if p)


def has_word(text: str, word: str) -> bool:
    """Word-boundary match without a pre-compiled pattern."""
    if not word:
        return False
    w = word.casefold()
    lower = casefold(text)
    start = 0
    n = len(w)
    while True:
        pos = lower.find(w, start)
        if pos < 0:
            return False
        before_ok = pos == 0 or not lower[pos - 1].isalnum()
        after_pos = pos + n
        after_ok = after_pos >= len(lower) or not lower[after_pos].isalnum()
        if before_ok and after_ok:
            return True
        start = pos + 1


def has_any_word(text: str, words: tuple[str, ...]) -> bool:
    return any(has_word(text, w) for w in words if w)


def has_arabic_script(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" for ch in (text or ""))


def _tokens(text: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    for ch in casefold(text):
        if ch.isalnum() or ch in "'’":
            cur.append(ch)
        elif cur:
            out.append("".join(cur))
            cur = []
    if cur:
        out.append("".join(cur))
    return out


def has_gapped_words(
    text: str,
    head: str,
    tails: tuple[str, ...],
    *,
    max_gap: int = 3,
) -> bool:
    """``head`` followed by one of ``tails`` with at most ``max_gap`` words between.

    Replaces patterns like ``\\bno\\s+(?:\\w+\\s+){0,3}(?:data|records?)\\b``
    without a compiled regex: ``has_gapped_words("no carbon emissions data",
    "no", ("data",))`` is True.
    """
    toks = _tokens(text)
    head_cf = head.casefold()
    tail_set = {t.casefold() for t in tails if t}
    for i, tok in enumerate(toks):
        if tok != head_cf:
            continue
        for j in range(i + 1, min(i + 2 + max_gap, len(toks))):
            if toks[j] in tail_set:
                return True
    return False
