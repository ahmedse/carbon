"""Fixed MedMentor how-to answers for the Moodle Ask door.

The asks live in the aast-med pack. A group matches only when every term
is present. Answers never read names from the host snapshot. This module
is not imported by engine/.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_PACK = Path(__file__).resolve().parents[2] / "domain_packs" / "aast-med" / "onboarding_asks.yaml"


@lru_cache(maxsize=1)
def _asks() -> tuple[dict[str, Any], ...]:
    data = yaml.safe_load(_PACK.read_text(encoding="utf-8")) or {}
    asks = data.get("asks") or []
    return tuple(asks)


def answer(
    message: str,
    snapshot: dict[str, Any] | None = None,
    asks: tuple[dict[str, Any], ...] | None = None,
) -> str | None:
    """Return the fixed how-to sentence, or None. Snapshot is ignored."""
    del snapshot  # how-to text must not cite the host page
    text = (message or "").casefold()
    if not text.strip():
        return None
    for ask in asks if asks is not None else _asks():
        groups = ask.get("all_of_any") or []
        for group in groups:
            terms = [str(term).casefold() for term in group if str(term).strip()]
            if terms and all(term in text for term in terms):
                fixed = str(ask.get("answer") or "").strip()
                return fixed or None
    return None
