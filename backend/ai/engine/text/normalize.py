"""Shared utterance normalization. The only routing-adjacent home for Arabic folds.

Hamza, alef maqsura, taa marbuta, diacritics, and Arabic-Indic digits.
Callers that used to special-case those forms should call ``normalize_text``
once. Do not add intent regexes here.
"""
from __future__ import annotations

_FOLDS = str.maketrans(
    {
        "\u0623": "\u0627",
        "\u0625": "\u0627",
        "\u0622": "\u0627",
        "\u0649": "\u064A",
        "\u0629": "\u0647",
        "\u0624": "\u0648",
        "\u0626": "\u064A",
        "\u0660": "0",
        "\u0661": "1",
        "\u0662": "2",
        "\u0663": "3",
        "\u0664": "4",
        "\u0665": "5",
        "\u0666": "6",
        "\u0667": "7",
        "\u0668": "8",
        "\u0669": "9",
    }
)

def _strip_diacritics(text: str) -> str:
    out: list[str] = []
    for ch in text:
        o = ord(ch)
        if 0x0610 <= o <= 0x061A or 0x064B <= o <= 0x065F or ch == "\u0640":
            continue
        if 0x0670 <= o <= 0x06ED:
            continue
        out.append(ch)
    return "".join(out)


def normalize_text(text: str | None) -> str:
    """Fold Arabic orthography and digits. Empty in → empty out."""
    raw = (text or "").strip()
    if not raw:
        return ""
    folded = raw.translate(_FOLDS)
    folded = _strip_diacritics(folded)
    folded = " ".join(folded.split())
    return folded.strip()
