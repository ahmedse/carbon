"""Closed-topic check for the Moodle Ask door.

The groups live in the aast-med pack. A group matches only when every term
is present. This module is not imported by engine/.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_PACK = Path(__file__).resolve().parents[2] / "domain_packs" / "aast-med" / "refusals.yaml"


@lru_cache(maxsize=1)
def _kinds() -> tuple[dict[str, Any], ...]:
    data = yaml.safe_load(_PACK.read_text(encoding="utf-8")) or {}
    kinds = data.get("kinds") or []
    return tuple(kinds)


def classify(message: str, kinds: tuple[dict[str, Any], ...] | None = None) -> str | None:
    text = (message or "").casefold()
    if not text.strip():
        return None
    for kind in kinds if kinds is not None else _kinds():
        groups = kind.get("all_of_any") or []
        for group in groups:
            terms = [str(term).casefold() for term in group if str(term).strip()]
            if terms and all(term in text for term in terms):
                return str(kind.get("id") or "")
    return None


def answer_for(kind_id: str, kinds: tuple[dict[str, Any], ...] | None = None) -> str:
    for kind in kinds if kinds is not None else _kinds():
        if str(kind.get("id") or "") == kind_id:
            return str(kind.get("answer") or "").strip()
    return ""
