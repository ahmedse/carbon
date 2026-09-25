"""Pack-owned strings. The engine asks by key; the words stay in the pack."""
from __future__ import annotations

from pathlib import Path

import yaml


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


def _load() -> dict[str, str]:
    merged: dict[str, str] = {}
    for root in _pack_roots():
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
