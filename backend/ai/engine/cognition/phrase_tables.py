"""Routing tables live in phrase_tables.yaml. The core asks by key.

Rows that name a host world live in that pack's ``phrases.yaml``. ``T`` returns
the pack row while :func:`bind_pack` is active for that turn, and the core row
otherwise. Module-level ``T(key)`` bindings stay live: a table that has a pack
overlay resolves on each use, so the turn's pack is the one that is read.
"""
from __future__ import annotations

import functools
import inspect
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from ai.engine.pack_vocab import _active_pack, bind_pack

_PACKS = Path(__file__).resolve().parents[4] / "domain_packs"


def _load_path(path: Path) -> dict[str, Any]:
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _load() -> dict[str, Any]:
    return _load_path(Path(__file__).resolve().parent / "phrase_tables.yaml")


def _safe_segment(instance_id: str) -> bool:
    if not isinstance(instance_id, str) or not instance_id:
        return False
    if instance_id in (".", ".."):
        return False
    if "/" in instance_id or "\\" in instance_id:
        return False
    return Path(instance_id).name == instance_id


def _phrase_file(instance_id: str) -> Path | None:
    """Pack phrase file, or None when the id is unsafe or the file is absent."""
    if not _safe_segment(instance_id):
        return None
    pack_dir = _PACKS / instance_id
    candidate = (pack_dir / "phrases.yaml").resolve()
    try:
        candidate.relative_to(pack_dir.resolve())
    except (ValueError, OSError):
        return None
    return candidate if candidate.is_file() else None


_DOC = _load()
_CACHE: dict[str, Any] = {}
_PACK_CACHE: dict[str, dict[str, Any]] = {}
_RESOLVE_CACHE: dict[tuple[str, str], Any] = {}


def _overlay_kinds() -> dict[str, str]:
    kinds: dict[str, str] = {}
    if not _PACKS.is_dir():
        return kinds
    for pack_dir in sorted(_PACKS.iterdir()):
        path = pack_dir / "phrases.yaml"
        if not path.is_file():
            continue
        for key, row in _load_path(path).items():
            if isinstance(row, dict) and isinstance(row.get("kind"), str):
                kinds.setdefault(key, row["kind"])
    return kinds


_OVERLAY_KIND = _overlay_kinds()


def _build(row: dict[str, Any]) -> Any:
    kind = row.get("kind")
    if kind == "str":
        return row["value"]
    if kind == "chars":
        return frozenset(row["value"])
    if kind == "tuple":
        return tuple(row["items"])
    if kind == "list":
        return list(row["items"])
    if kind == "set":
        return set(row["items"])
    if kind == "frozenset":
        return frozenset(row["items"])
    if kind == "dict":
        return dict(row["items"])
    raise KeyError(kind)


def _empty(kind: str) -> Any:
    if kind == "str":
        return ""
    if kind == "chars":
        return frozenset()
    if kind == "tuple":
        return ()
    if kind == "list":
        return []
    if kind == "set":
        return set()
    if kind == "frozenset":
        return frozenset()
    if kind == "dict":
        return {}
    return ()


def _pack_doc(instance_id: str) -> dict[str, Any]:
    if instance_id in _PACK_CACHE:
        return _PACK_CACHE[instance_id]
    path = _phrase_file(instance_id)
    doc = _load_path(path) if path is not None else {}
    _PACK_CACHE[instance_id] = doc
    return doc


def _resolve(key: str) -> Any:
    pack_id = _active_pack.get()
    cache_key = (pack_id, key)
    cached = _RESOLVE_CACHE.get(cache_key)
    if cached is not None or cache_key in _RESOLVE_CACHE:
        return cached
    if pack_id:
        row = _pack_doc(pack_id).get(key)
        if isinstance(row, dict):
            value = _build(row)
            _RESOLVE_CACHE[cache_key] = value
            return value
    row = _DOC.get(key)
    if isinstance(row, dict):
        value = _build(row)
    else:
        value = _empty(_OVERLAY_KIND.get(key, "tuple"))
    _RESOLVE_CACHE[cache_key] = value
    return value


class _LiveTable:
    """A phrase table that reads the pack bound on the current turn."""

    def __init__(self, key: str) -> None:
        self._key = key

    def _value(self) -> Any:
        return _resolve(self._key)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._value())

    def __contains__(self, item: object) -> bool:
        return item in self._value()

    def __len__(self) -> int:
        return len(self._value())

    def __getitem__(self, item: Any) -> Any:
        return self._value()[item]

    def __eq__(self, other: object) -> bool:
        return self._value() == other

    def __hash__(self) -> int:
        return hash(self._value())

    def __bool__(self) -> bool:
        return bool(self._value())

    def __add__(self, other: Any) -> Any:
        return self._value() + other

    def __radd__(self, other: Any) -> Any:
        return other + self._value()

    def __repr__(self) -> str:
        return repr(self._value())

    def __str__(self) -> str:
        return str(self._value())

    def __format__(self, spec: str) -> str:
        return format(self._value(), spec)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._value(), name)


def T(key: str) -> Any:
    if key in _OVERLAY_KIND:
        return _LiveTable(key)
    if key not in _CACHE:
        _CACHE[key] = _build(_DOC[key])
    return _CACHE[key]


def bound_to_pack(fn):
    """Run a coroutine with phrase tables bound to its ``instance_id`` argument."""

    sig = inspect.signature(fn)

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        bound = sig.bind_partial(*args, **kwargs)
        instance_id = bound.arguments.get("instance_id", "")
        with bind_pack(instance_id if isinstance(instance_id, str) else ""):
            return await fn(*args, **kwargs)

    return wrapper
