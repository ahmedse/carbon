"""Load assurance packs from YAML directories. Stdlib + PyYAML only."""

from __future__ import annotations

from pathlib import Path

import yaml

from assurance.model import CATALOGUE, Pack, Rule

_REQUIRED = (
    "id",
    "journey",
    "meaning",
    "source",
    "owner",
    "failure",
    "validation",
    "implementation",
    "confidence",
    "catalogue",
    "residual",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def pack_dir(root: Path, pack_id: str) -> Path:
    if pack_id == "platform":
        return root / "assurance" / "platform"
    return root / "domain_packs" / pack_id / "assurance"


def load_pack(directory: Path) -> Pack:
    manifest_path = directory / "pack.yaml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"No assurance pack at {directory}")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    pack_id = str(manifest["id"])
    blocking = set(manifest.get("blocks_release") or [])
    rules: list[Rule] = []
    rules_dir = directory / "rules"
    if rules_dir.is_dir():
        for path in sorted(rules_dir.glob("*.yaml")):
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            rules.append(_rule(raw, pack_id, path.name, blocking))
    return Pack(
        id=pack_id,
        title=str(manifest.get("title") or pack_id),
        brand=str(manifest.get("brand") or "*"),
        rules=tuple(rules),
    )


def load_brand(root: Path, pack_id: str, *, with_platform: bool = True) -> list[Pack]:
    """Load one brand pack. Platform rides along unless the brand is platform."""
    packs = [load_pack(pack_dir(root, pack_id))]
    if with_platform and pack_id != "platform":
        packs.append(load_pack(pack_dir(root, "platform")))
    return packs


def _rule(raw: dict, pack_id: str, filename: str, blocking: set[str]) -> Rule:
    missing = [key for key in _REQUIRED if key not in raw]
    if missing:
        raise ValueError(f"{filename} missing {', '.join(missing)}")
    catalogue = str(raw["catalogue"])
    if catalogue not in CATALOGUE:
        raise ValueError(f"{filename} catalogue {catalogue!r} is not allowed")
    rule_id = str(raw["id"])
    return Rule(
        id=rule_id,
        pack=pack_id,
        journey=str(raw["journey"]),
        meaning=str(raw["meaning"]),
        source=str(raw["source"]),
        owner=str(raw["owner"]),
        failure=str(raw["failure"]),
        validation=str(raw["validation"]),
        implementation=str(raw["implementation"]),
        confidence=str(raw["confidence"]),
        catalogue=catalogue,
        residual=str(raw["residual"]),
        blocks_release=rule_id in blocking,
    )
