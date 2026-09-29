"""ESS read copy and needles from the pack bound on this turn.

The engine does not own the words. A pack with no ess_read.yaml contributes
nothing. Import does not copy another pack's strings into these names.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from ai.engine.cognition.phrase_tables import T
from ai.engine.pack_vocab import _active_pack

_TUPLES = T("turn/ess_read_i18n.py::_TUPLES")
_SETS = T("turn/ess_read_i18n.py::_SETS")
_ROOT = Path(__file__).resolve().parents[5] / "domain_packs"
_CACHE: dict[str, dict] = {}


def _pack_doc() -> dict:
    """The bound pack's ess_read.yaml. Another pack's file is not read."""
    pack_id = _active_pack.get() or ""
    if not pack_id or pack_id in {".", ".."} or pack_id != Path(pack_id).name:
        return {}
    if pack_id in _CACHE:
        return _CACHE[pack_id]
    path = _ROOT / pack_id / "ess_read.yaml"
    doc: dict = {}
    if path.is_file():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            doc = loaded
    _CACHE[pack_id] = doc
    return doc


class _LiveSeq:
    """A needle list that resolves when it is used."""

    def __init__(self, key: str, factory) -> None:
        self._key = key
        self._factory = factory

    def _value(self):
        raw = _pack_doc().get(self._key) or ()
        return self._factory(raw)

    def __iter__(self):
        return iter(self._value())

    def __contains__(self, item: object) -> bool:
        return item in self._value()

    def __len__(self) -> int:
        return len(self._value())

    def __bool__(self) -> bool:
        return bool(self._value())

    def __eq__(self, other: object) -> bool:
        return self._value() == other

    def __getitem__(self, item):
        return self._value()[item]


class _Blank(dict):
    """A missing map matches nothing and yields no sentence."""

    def __getitem__(self, item):
        return ""

    def get(self, item, default=None):
        return default

    def __contains__(self, item: object) -> bool:
        return False


class _LiveMap:
    """A dict from the bound pack. A missing pack is an empty map."""

    def __init__(self, key: str, *, nested: bool = False) -> None:
        self._key = key
        self._nested = nested

    def _value(self) -> dict:
        raw = _pack_doc().get(self._key) or {}
        return raw if isinstance(raw, dict) else {}

    def __getitem__(self, item):
        value = self._value()
        if item in value:
            return value[item]
        if self._nested:
            return _Blank()
        return ""

    def get(self, item, default=None):
        return self._value().get(item, default)

    def __contains__(self, item: object) -> bool:
        return item in self._value()

    def __bool__(self) -> bool:
        return bool(self._value())


for _key in list(_TUPLES):
    globals()[_key] = _LiveSeq(_key, tuple)
for _key in list(_SETS):
    globals()[_key] = _LiveSeq(_key, frozenset)

HONEST_EMPTY = _LiveMap("HONEST_EMPTY", nested=True)
UNAUTHORIZED_TEXT = _LiveMap("UNAUTHORIZED_TEXT")
EMPTY_BALANCE_TEXT = _LiveMap("EMPTY_BALANCE_TEXT")
RENDER_SCOPE = _LiveMap("RENDER_SCOPE")
UNSUMMARIZED_FALLBACK = _LiveMap("UNSUMMARIZED_FALLBACK")
EMPTY_RENDER = _LiveMap("EMPTY_RENDER")


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    # Empty is not a match. A pack that lacks the needle must not hit every utterance.
    return any(n and str(n) in raw for n in needles)
