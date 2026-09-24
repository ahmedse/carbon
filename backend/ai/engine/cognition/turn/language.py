"""Reply-language detection for deterministic templates (EN / AR).

Deterministic runner templates (refusal, …) must answer in the user's
language. "Any Arabic character" is too eager — a single module name typed in
Arabic inside an English sentence is still English — so this uses the share of
Arabic letters among all letters. Digits, punctuation and Arabic-Indic numerals
are ignored.
"""
from __future__ import annotations

def _is_ar_letter(ch: str) -> bool:
    o = ord(ch)
    return (
        0x0621 <= o <= 0x064A
        or 0x0671 <= o <= 0x06D3
        or 0x06FA <= o <= 0x06FF
        or 0x0750 <= o <= 0x077F
    )

# ≥ this share of Arabic letters → reply in Arabic.
_AR_RATIO_THRESHOLD = 0.4


def arabic_ratio(text: str) -> float:
    """Share of Arabic letters among Arabic + Latin letters (0.0 when none)."""
    ar = sum(1 for ch in (text or "") if _is_ar_letter(ch))
    lat = sum(1 for ch in (text or "") if ch.isascii() and ch.isalpha())
    total = ar + lat
    return ar / total if total else 0.0


def detect_reply_language(text: str) -> str:
    """Return ``"ar"`` or ``"en"`` for the language a reply should use."""
    return "ar" if arabic_ratio(text) >= _AR_RATIO_THRESHOLD else "en"
