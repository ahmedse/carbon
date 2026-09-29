"""Pack-owned strings. The engine asks by key; the words stay in the pack.

``V`` returns the string from the pack bound for this turn, or ``""`` when
that pack has no such string. It never reads another pack.

``LV`` is the same lookup, resolved when the value is used. Module-level
``NAME = LV(key)`` stays bound to the turn instead of the import moment.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

import yaml

_active_pack: ContextVar[str] = ContextVar("pulse_pack_scope", default="")


def _safe_segment(instance_id: str) -> bool:
    if not isinstance(instance_id, str) or not instance_id:
        return False
    if instance_id in (".", ".."):
        return False
    if "/" in instance_id or "\\" in instance_id:
        return False
    return Path(instance_id).name == instance_id


def _pack_roots() -> list[Path]:
    """Repo layout (dev) and Docker mount (/domain_packs) both work."""
    here = Path(__file__).resolve()
    roots: list[Path] = []
    for candidate in (
        here.parents[3] / "domain_packs",  # monorepo: backend/ai/engine → repo
        Path("/domain_packs"),               # production compose bind-mount
        here.parents[2] / "domain_packs",  # fallback if packaged oddly
    ):
        if candidate.is_dir() and candidate not in roots:
            roots.append(candidate)
    return roots


def _string_rows(path: Path) -> dict[str, str]:
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(doc, dict):
        return {}
    return {str(key): value for key, value in doc.items() if isinstance(value, str)}


def _index_packs() -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for root in _pack_roots():
        for path in sorted(root.glob("*/vocab.yaml")):
            pack_id = path.parent.name
            if not _safe_segment(pack_id) or pack_id in indexed:
                continue
            indexed[pack_id] = _string_rows(path)
    return indexed


_PACKS = _index_packs()


def _resolve(key: str) -> str:
    pack_id = _active_pack.get()
    if not _safe_segment(pack_id):
        return ""
    return _PACKS.get(pack_id, {}).get(key, "")


def as_data(value: Any) -> Any:
    """Copy ``value`` with live pack strings turned into real strings.

    The model client and other JSON writers require ``str``. Call this at
    that boundary. Lookup still happens then, against the pack bound now.
    """
    if isinstance(value, _LiveText):
        return value._s()
    if isinstance(value, dict):
        return {
            key if isinstance(key, str) else as_data(key): as_data(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [as_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(as_data(item) for item in value)
    return value


def V(key: str) -> str:
    """String from the pack bound for this turn. Empty when it has no such key."""
    return _resolve(key)


def same_id(value: object, needle: object) -> bool:
    """True when both sides resolve to the same non-empty identifier."""
    left = str(value or "")
    right = str(needle or "")
    return bool(left) and bool(right) and left == right


def present_ids(*needles: object) -> frozenset[str]:
    """Ids that resolve for the pack bound now. Built at the call, not at import."""
    return frozenset(s for n in needles if (s := str(n or "")))


def present_id_list(*needles: object) -> tuple[str, ...]:
    """Same as present_ids, in call order. An empty needle is omitted."""
    return tuple(s for n in needles if (s := str(n or "")))


def row_for(rows: tuple, api: object):
    """First row whose identifier matches. An empty id selects nothing."""
    for name, row in rows:
        if same_id(api, name):
            return row
    return None


def copy_text(key: str, **fields: Any) -> str:
    """A sentence from the bound pack.

    A missing key is an empty string. An empty template is not formatted,
    so a caller cannot present a blank or a half-filled host sentence.
    """
    text = _resolve(key)
    if not text or not fields:
        return text
    return text.format(**fields)


class _LiveText:
    """A string that reads the pack bound at the moment it is used."""

    def _s(self) -> str:
        raise NotImplementedError

    def __str__(self) -> str:
        return self._s()

    def __repr__(self) -> str:
        return repr(self._s())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _LiveText):
            return self._s() == other._s()
        return self._s() == other

    def __hash__(self) -> int:
        return hash(self._s())

    def __bool__(self) -> bool:
        return bool(self._s())

    def __len__(self) -> int:
        return len(self._s())

    def __getitem__(self, item: Any) -> str:
        return self._s()[item]

    def __iter__(self):
        return iter(self._s())

    def __contains__(self, item: object) -> bool:
        return item in self._s()

    def __format__(self, spec: str) -> str:
        return format(self._s(), spec)

    def __add__(self, other: Any) -> _LiveText:
        return _LiveConcat((self, other))

    def __radd__(self, other: Any) -> _LiveText:
        return _LiveConcat((other, self))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._s(), name)


class _LiveStr(_LiveText):
    def __init__(self, key: str) -> None:
        self._key = key

    def _s(self) -> str:
        return _resolve(self._key)


class _LiveConcat(_LiveText):
    def __init__(self, parts: tuple[Any, ...]) -> None:
        self._parts = parts

    def _s(self) -> str:
        out: list[str] = []
        for part in self._parts:
            out.append(part._s() if isinstance(part, _LiveText) else str(part))
        return "".join(out)


def LV(key: str) -> _LiveStr:
    """Module-level binding. Resolves when the value is used, not at import."""
    return _LiveStr(key)


def _resolved_part(part: Any) -> str:
    return part._s() if isinstance(part, _LiveText) else str(part)


def _alt_piece(text: str) -> str:
    """Drop separator pipes left behind when a neighbor fragment is empty."""
    piece = text.strip()
    while piece.startswith("|"):
        piece = piece[1:].lstrip()
    while piece.endswith("|") and not piece.endswith("\\|"):
        piece = piece[:-1].rstrip()
    return piece


class _LivePattern:
    """A compiled pattern whose text is read from the pack bound at use."""

    def __init__(self, parts: tuple[Any, ...], flags: int = 0, *, alt: bool = False) -> None:
        self._parts = parts
        self._flags = flags
        self._alt = alt
        self._cache: dict[str, re.Pattern[str]] = {}

    def _text(self) -> str:
        if not self._alt:
            return "".join(_resolved_part(part) for part in self._parts)
        pieces = [_alt_piece(_resolved_part(part)) for part in self._parts]
        pieces = [piece for piece in pieces if piece]
        if not pieces:
            return ""
        return "(?:" + "|".join(pieces) + ")"

    def _compiled(self) -> re.Pattern[str]:
        pack_id = _active_pack.get()
        cached = self._cache.get(pack_id)
        if cached is not None:
            return cached
        text = self._text()
        compiled = re.compile(text if text else r"(?!)", self._flags)
        self._cache[pack_id] = compiled
        return compiled

    def __getattr__(self, name: str) -> Any:
        return getattr(self._compiled(), name)


def live_pattern(*parts: Any, flags: int = 0) -> _LivePattern:
    """Compile ``parts`` when the pattern is used, for the pack bound then."""
    return _LivePattern(parts, flags)


def live_alt(*parts: Any, flags: int = 0) -> _LivePattern:
    """Join pack fragments as alternatives.

    An empty fragment is omitted. A dangling pipe is stripped. When every
    fragment is empty, the pattern matches nothing.
    """
    return _LivePattern(parts, flags, alt=True)


@contextmanager
def bind_pack(instance_id: str):
    """Bind phrase tables and vocabulary to the pack that owns this turn."""
    token = _active_pack.set(instance_id if isinstance(instance_id, str) else "")
    try:
        yield
    finally:
        _active_pack.reset(token)
