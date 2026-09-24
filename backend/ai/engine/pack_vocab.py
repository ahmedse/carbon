"""Pack-owned strings. The engine asks by key; the words stay in the pack."""
from __future__ import annotations

from pathlib import Path

import yaml

def _load() -> dict[str, str]:
    root = Path(__file__).resolve().parents[3] / "domain_packs"
    merged: dict[str, str] = {}
    if not root.is_dir():
        return merged
    for path in sorted(root.glob("*/vocab.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(doc, dict):
            for key, value in doc.items():
                if isinstance(value, str):
                    merged[str(key)] = value
    return merged


_DOC = _load()


def V(key: str) -> str:
    return _DOC[key]
