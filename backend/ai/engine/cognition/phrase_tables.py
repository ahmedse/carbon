"""Routing tables live in phrase_tables.yaml. The core asks by key."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

def _load() -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "phrase_tables.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return doc if isinstance(doc, dict) else {}


_DOC = _load()
_CACHE: dict[str, Any] = {}


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


def T(key: str) -> Any:
    if key not in _CACHE:
        _CACHE[key] = _build(_DOC[key])
    return _CACHE[key]
