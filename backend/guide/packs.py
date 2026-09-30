"""Load ``domain_packs/<id>/guide/`` (structure) and its copy (text per language).

    guide.yaml        pack, version, probes (module path), lessons[]
    copy.<lang>.yaml  tracks, blockers, lessons.<ID>  (English is the fallback)

Text lives in the pack so a pack is self-contained and a copy edit needs no
frontend build. The UI chrome (buttons, labels) stays in the frontend i18n.
"""
from __future__ import annotations

import importlib
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from guide.registry import PLATFORM

PACKS_ROOT = Path(__file__).resolve().parents[2] / "domain_packs"
LANGUAGES = ("en", "ar")
FALLBACK = "en"


def pack_dir(pack_id: str) -> Path:
    return PACKS_ROOT / pack_id / "guide"


def has_pack(pack_id: str) -> bool:
    return (pack_dir(pack_id) / "guide.yaml").is_file()


def _mtime(*paths: Path) -> tuple[float, ...]:
    return tuple(path.stat().st_mtime if path.is_file() else 0.0 for path in paths)


@lru_cache(maxsize=32)
def _load_pack(pack_id: str, stamp: float) -> dict[str, Any]:
    """Structure of one pack. Imports the probe module the pack lists."""
    del stamp
    data = yaml.safe_load((pack_dir(pack_id) / "guide.yaml").read_text(encoding="utf-8")) or {}
    module = data.get("probes")
    if module:
        importlib.import_module(module)
    lessons = []
    for row in data.get("lessons") or []:
        lesson = dict(row)
        lesson["pack"] = pack_id
        lessons.append(lesson)
    return {"id": pack_id, "version": int(data.get("version") or 1), "probes": module, "lessons": lessons}


def load_pack(pack_id: str) -> dict[str, Any]:
    path = pack_dir(pack_id) / "guide.yaml"
    return _load_pack(pack_id, path.stat().st_mtime if path.is_file() else 0.0)


@lru_cache(maxsize=64)
def _copy(pack_id: str, lang: str, stamp: float) -> dict[str, Any]:
    del stamp
    path = pack_dir(pack_id) / f"copy.{lang}.yaml"
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for key, value in over.items():
        out[key] = _merge(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


def catalog_for(app_id: str) -> tuple[dict, ...]:
    """The app's lessons, plus any shared process lessons, in ``priority`` order."""
    rows = list(load_pack(PLATFORM)["lessons"]) if has_pack(PLATFORM) else []
    if app_id != PLATFORM and has_pack(app_id):
        rows += load_pack(app_id)["lessons"]
    rows.sort(key=lambda row: row["priority"])
    return tuple(rows)


def copy_for(app_id: str, lang: str) -> dict[str, Any]:
    """Copy for ``lang`` over the English fallback, platform under the app."""
    lang = lang if lang in LANGUAGES else FALLBACK
    merged: dict[str, Any] = {}
    for pack_id in (PLATFORM, app_id):
        if pack_id == PLATFORM and not has_pack(PLATFORM):
            continue
        if pack_id != PLATFORM and not has_pack(pack_id):
            continue
        for code in (FALLBACK,) + ((lang,) if lang != FALLBACK else ()):
            path = pack_dir(pack_id) / f"copy.{code}.yaml"
            merged = _merge(merged, _copy(pack_id, code, path.stat().st_mtime if path.is_file() else 0.0))
    return merged


def clear_cache() -> None:
    _load_pack.cache_clear()
    _copy.cache_clear()
