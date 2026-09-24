"""ESS read copy and needles, loaded from each pack's ``ess_read.yaml``.

The engine does not own the words. ``any_needle`` is the only code here.
"""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T

from pathlib import Path

import yaml

_TUPLES = T("turn/ess_read_i18n.py::_TUPLES")
_SETS = T("turn/ess_read_i18n.py::_SETS")


def _load() -> dict:
    root = Path(__file__).resolve().parents[5] / "domain_packs"
    merged: dict = {}
    if not root.is_dir():
        return merged
    for path in sorted(root.glob("*/ess_read.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(doc, dict):
            merged.update(doc)
    return merged


_DOC = _load()


def _as_tuple(key: str) -> tuple[str, ...]:
    return tuple(_DOC.get(key) or ())


for _key in _TUPLES:
    globals()[_key] = _as_tuple(_key)
for _key in _SETS:
    globals()[_key] = frozenset(_DOC.get(_key) or ())

HONEST_EMPTY = _DOC.get("HONEST_EMPTY") or {}
UNAUTHORIZED_TEXT = _DOC.get("UNAUTHORIZED_TEXT") or {}
EMPTY_BALANCE_TEXT = _DOC.get("EMPTY_BALANCE_TEXT") or {}
RENDER_SCOPE = _DOC.get("RENDER_SCOPE") or {}
UNSUMMARIZED_FALLBACK = _DOC.get("UNSUMMARIZED_FALLBACK") or {}
EMPTY_RENDER = _DOC.get("EMPTY_RENDER") or {}


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
