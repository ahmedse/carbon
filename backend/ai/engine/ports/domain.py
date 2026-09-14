"""DomainPack port — the engine's pluggable, read-only domain knowledge source.

The Pulse engine is domain-agnostic: everything that makes a deployment
*brand-specific* — its vocabulary, its tool/API catalog, its processes, its
skills, its trigger/metric configuration, and its prompt templates — lives in a
*domain pack* and reaches the engine only through this port.  The engine
consumes these plain ``dict`` / ``list[dict]`` projections; it never imports a
host module or hardcodes any brand.

A domain pack is a directory of YAML files.  :func:`load_domain_pack` reads it
purely (stdlib + PyYAML) into an in-memory :class:`DomainPack`.  The host
resolves brand → directory and passes the path in; the loader resolves no
absolute repo path and imports nothing Django-specific.  With no pack (or a
missing/empty directory) the engine receives :class:`NeutralDomainPack` and
behaves exactly as it does pack-less.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

try:  # PyYAML ships in backend/requirements.txt; degrade gracefully if absent.
    import yaml
except ImportError:  # pragma: no cover - exercised only without PyYAML
    yaml = None


class DomainPack(Protocol):
    """Pluggable, read-only domain knowledge consumed by the engine.

    A domain pack is the only channel through which brand-specific knowledge
    reaches the engine (RULE_20 / ADR-0007).  Every accessor is read-only and
    returns a plain ``dict`` / ``list[dict]`` projection — never a host object.
    """

    def vocabulary(self) -> dict:
        """Return the domain vocabulary (concepts, terms, dimensions, …)."""
        ...

    def api_catalog(self) -> dict:
        """Return the tool/API catalog (tools + default source type, …)."""
        ...

    def processes(self) -> list[dict]:
        """Return process definitions (ProcessDefinition projections)."""
        ...

    def skills(self) -> list[dict]:
        """Return skill projections (Agent Skills spec)."""
        ...

    def triggers(self) -> dict:
        """Return trigger/metric configuration (metrics + deviations)."""
        ...

    def prompts(self) -> dict:
        """Return prompt templates, keyed by name."""
        ...


class NeutralDomainPack:
    """Fallback "no pack loaded" implementation returning empty collections.

    The engine boots against this when no domain pack directory is configured
    or present, so it behaves identically to running pack-less.  It satisfies
    :class:`DomainPack` structurally without holding any data.
    """

    def vocabulary(self) -> dict:
        return {}

    def api_catalog(self) -> dict:
        return {}

    def processes(self) -> list[dict]:
        return []

    def skills(self) -> list[dict]:
        return []

    def triggers(self) -> dict:
        return {}

    def prompts(self) -> dict:
        return {}


class _InMemoryDomainPack:
    """In-memory :class:`DomainPack` populated by :func:`load_domain_pack`."""

    def __init__(
        self,
        vocabulary: dict[str, Any],
        api_catalog: dict[str, Any],
        processes: list[dict[str, Any]],
        skills: list[dict[str, Any]],
        triggers: dict[str, Any],
        prompts: dict[str, Any],
    ) -> None:
        self._vocabulary = vocabulary
        self._api_catalog = api_catalog
        self._processes = processes
        self._skills = skills
        self._triggers = triggers
        self._prompts = prompts

    def vocabulary(self) -> dict:
        return self._vocabulary

    def api_catalog(self) -> dict:
        return self._api_catalog

    def processes(self) -> list[dict]:
        return self._processes

    def skills(self) -> list[dict]:
        return self._skills

    def triggers(self) -> dict:
        return self._triggers

    def prompts(self) -> dict:
        return self._prompts


def load_domain_pack(pack_dir: str | Path | None) -> DomainPack:
    """Load a domain pack directory (vocabulary.yaml, api_catalog.yaml,
    triggers.yaml, processes/, skills/, prompts/). Missing/empty dir →
    NeutralDomainPack. Uses PyYAML; never raises on missing files.

    Pure and portable: it reads YAML with PyYAML into an in-memory
    :class:`DomainPack`, hardcodes no brand, imports nothing Django-specific,
    and resolves no absolute repo path.  The host resolves brand → directory
    and passes the path in; ``pack_dir=None`` yields :class:`NeutralDomainPack`.
    """
    if not pack_dir:
        return NeutralDomainPack()

    root = Path(pack_dir)
    if not root.is_dir() or yaml is None:
        return NeutralDomainPack()

    return _InMemoryDomainPack(
        vocabulary=_read_yaml_mapping(root / "vocabulary.yaml"),
        api_catalog=_read_yaml_mapping(root / "api_catalog.yaml"),
        processes=_read_yaml_sequence_dir(root / "processes"),
        skills=_read_skill_dir(root / "skills"),
        triggers=_read_yaml_mapping(root / "triggers.yaml"),
        prompts=_read_yaml_mapping_dir(root / "prompts"),
    )


def _load_yaml(path: Path) -> Any:
    """Parse a YAML file, returning ``None`` on any failure.

    Covers a missing/unreadable file, empty content, and invalid YAML so the
    loader never raises on missing or malformed content.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.strip():
        return None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def _read_yaml_mapping(path: Path) -> dict:
    """Read a single YAML file as a mapping; ``{}`` on failure."""
    data = _load_yaml(path)
    return data if isinstance(data, dict) else {}


def _read_yaml_sequence_dir(dir_path: Path) -> list[dict]:
    """Read every ``*.yaml`` / ``*.yml`` file in a directory as a list of dicts."""
    if not dir_path.is_dir():
        return []
    items: list[dict] = []
    for path in _yaml_files(dir_path):
        _extend_mappings(items, _load_yaml(path))
    return items


def _read_skill_dir(dir_path: Path) -> list[dict]:
    """Read skill folders, loading ``skill.yaml`` / ``skill.yml`` from each.

    Skill folders follow the Agent Skills spec; loose ``*.yaml`` / ``*.yml``
    files directly under the directory are also accepted.
    """
    if not dir_path.is_dir():
        return []
    items: list[dict] = []
    for child in sorted(dir_path.iterdir(), key=lambda p: p.name):
        if child.is_dir():
            skill_file = child / "skill.yaml"
            if not skill_file.is_file():
                skill_file = child / "skill.yml"
            data = _load_yaml(skill_file) if skill_file.is_file() else None
        elif child.suffix in (".yaml", ".yml"):
            data = _load_yaml(child)
        else:
            continue
        _extend_mappings(items, data)
    return items


def _read_yaml_mapping_dir(dir_path: Path) -> dict:
    """Read each ``*.yaml`` / ``*.yml`` file in a directory, keyed by stem."""
    if not dir_path.is_dir():
        return {}
    result: dict[str, Any] = {}
    for path in _yaml_files(dir_path):
        data = _load_yaml(path)
        if isinstance(data, (dict, list)):
            result[path.stem] = data
    return result


def _yaml_files(dir_path: Path) -> list[Path]:
    """Return sorted ``*.yaml`` / ``*.yml`` files directly under ``dir_path``."""
    return sorted(
        list(dir_path.glob("*.yaml")) + list(dir_path.glob("*.yml")),
        key=lambda p: p.name,
    )


def _extend_mappings(items: list[dict], data: Any) -> None:
    """Append a mapping, or each mapping of a list, to ``items``."""
    if isinstance(data, dict):
        items.append(data)
    elif isinstance(data, list):
        items.extend(item for item in data if isinstance(item, dict))
