"""Load a versioned regulation pack from disk.

The comparison the publish gate applies is generic. Statute numbers stay in
the pack files. A missing version fails closed.
"""

from __future__ import annotations

from pathlib import Path

import yaml


class PackMissing(Exception):
    """The cited pack version is not a file the publish gate can read."""

    def __init__(self, pack, version):
        self.pack = pack
        self.version = version
        super().__init__(f"regulation pack {pack} version {version} is missing")


def pack_root() -> Path:
    return Path(__file__).resolve().parents[2] / "regulation_packs"


def _safe_segment(value) -> str:
    text = str(value or "")
    if not text or text in {".", ".."} or "/" in text or "\\" in text:
        raise PackMissing(value, "")
    return text


def load_pack(pack, version) -> dict:
    """Return the parsed pack. Raises PackMissing when the version is absent."""
    try:
        pack_name = _safe_segment(pack)
        version_name = _safe_segment(version)
    except PackMissing:
        raise PackMissing(pack, version) from None
    path = pack_root() / pack_name / f"{version_name}.yaml"
    if not path.is_file():
        raise PackMissing(pack, version)
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict) or str(loaded.get("version")) != str(version):
        raise PackMissing(pack, version)
    return loaded
