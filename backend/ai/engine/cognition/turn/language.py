"""Reply-language detection for deterministic templates (EN / AR).

Deterministic runner templates (refusal, …) must answer in the user's
language. "Any Arabic character" is too eager — a single module name typed in
Arabic inside an English sentence is still English — so this uses the share of
Arabic letters among all letters. Digits, punctuation and Arabic-Indic numerals
are ignored.
"""
from __future__ import annotations

import re

_AR_LETTER_RE = re.compile(r"[\u0621-\u064A\u0671-\u06D3\u06FA-\u06FF\u0750-\u077F]")
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")

# ≥ this share of Arabic letters → reply in Arabic.
_AR_RATIO_THRESHOLD = 0.4


def arabic_ratio(text: str) -> float:
    """Share of Arabic letters among Arabic + Latin letters (0.0 when none)."""
    ar = len(_AR_LETTER_RE.findall(text or ""))
    lat = len(_LATIN_LETTER_RE.findall(text or ""))
    total = ar + lat
    return ar / total if total else 0.0


def detect_reply_language(text: str) -> str:
    """Return ``"ar"`` or ``"en"`` for the language a reply should use."""
    return "ar" if arabic_ratio(text) >= _AR_RATIO_THRESHOLD else "en"
