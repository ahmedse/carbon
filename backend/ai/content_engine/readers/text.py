"""Plain-text family: txt / md / json / csv.

Text is copied verbatim (only intra-line whitespace is normalised), so
sentence boundaries survive. JSON leaves are stringified and kept with their
key path so structure is not lost. Every unit here is citable.
"""

from __future__ import annotations

import json
from pathlib import Path

_KIND = {
    ".txt": "txt",
    ".text": "txt",
    ".md": "md",
    ".markdown": "md",
    ".json": "json",
    ".csv": "csv",
}


def _result(units: list[dict], status: str, error: str | None) -> dict:
    return {"units": units, "status": status, "reader": "text", "error": error}


def _unit(text: str, kind: str, locator: str = "n/a") -> dict:
    return {
        "text": text,
        "kind": kind,
        "source_ref": "",
        "locator": locator,
        "citable": True,
        "course": None,
        "activity_ref": None,
        "status": "ok",
    }


def read(path: str, mime: str | None = None) -> dict:
    suffix = Path(path).suffix.lower()
    kind = _KIND.get(suffix, "txt")
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        return _result([], "unreadable", f"{type(exc).__name__}: {exc}")
    if not raw.strip():
        return _result([], "empty", "no_text")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", "replace")

    if kind == "json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return _result([], "unreadable", f"json_decode: {exc.msg}")
        text = _flatten_json(data)

    text = _tidy(text)
    if not text:
        return _result([], "empty", "no_text")
    return _result([_unit(text, kind)], "ok", None)


def _tidy(text: str) -> str:
    """Normalise spaces inside a line while keeping line breaks as boundaries."""
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _flatten_json(value, prefix: str = "") -> str:
    lines: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            label = f"{prefix}.{key}" if prefix else str(key)
            lines.append(_flatten_json(child, label))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            lines.append(_flatten_json(child, f"{prefix}[{index}]"))
    else:
        lines.append(f"{prefix}: {value}")
    return "\n".join(line for line in lines if line)
