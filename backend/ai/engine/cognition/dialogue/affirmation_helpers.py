"""Char-level helpers for affirmation normalization (no pre-compiled patterns)."""
from __future__ import annotations

_EDGE_PUNCT = frozenset(".,;!?\"'\u060C\u061B\u2026\u00AB\u00BB")


def strip_tashkeel(text: str) -> str:
    out: list[str] = []
    for ch in text:
        o = ord(ch)
        if 0x0610 <= o <= 0x061A or 0x064B <= o <= 0x0652 or ch == "\u0640":
            continue
        if 0x0670 <= o <= 0x06ED:
            continue
        out.append(ch)
    return "".join(out)


def strip_edge_punct(text: str) -> str:
    start = 0
    end = len(text)
    while start < end and (text[start].isspace() or text[start] in _EDGE_PUNCT):
        start += 1
    while end > start and (text[end - 1].isspace() or text[end - 1] in _EDGE_PUNCT):
        end -= 1
    return text[start:end]


def tokenize(text: str) -> list[str]:
    words: list[str] = []
    current: list[str] = []
    for ch in text:
        if ch.isspace() or ch in _EDGE_PUNCT:
            if current:
                words.append("".join(current))
                current = []
            continue
        current.append(ch)
    if current:
        words.append("".join(current))
    return words
