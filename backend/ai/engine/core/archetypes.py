"""P6.1 — Archetype bundle loader, validator, and template renderer.

An archetype is a directory under `archetypes/<name>/` containing:
- archetype.yaml         — metadata (name, version, description, icon_set, requires)
- instance.template.yaml — Jinja2 template rendered into instances/<name>/instance.yaml
- playbook/              — optional system prompt blocks
- domain/                — optional connector stubs
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml
from jinja2 import BaseLoader, Environment
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("pulse.core.archetypes")

# ── Resolve archetypes root relative to the pulse project root ──
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ARCHETYPES_ROOT = _PROJECT_ROOT / "archetypes"


# ── Data types ──────────────────────────────────────────────────────────────

@dataclass
class ArchetypeRequires:
    pulse_version: str = ">=0.3.0"
    auth_mode: str = "local"
    storage_mode: str = "standalone"


@dataclass
class ArchetypeMeta:
    name: str
    version: str
    description: str
    icon_set: str = "default"
    requires: ArchetypeRequires = field(default_factory=ArchetypeRequires)

    @property
    def dir_path(self) -> Path:
        return _ARCHETYPES_ROOT / self.name

    @property
    def template_path(self) -> Path:
        return self.dir_path / "instance.template.yaml"


# ── Pydantic model for instance config validation ───────────────────────────

class AuthConfig(BaseModel):
    mode: str = "host_delegated"  # local | host_delegated


class InstanceConfig(BaseModel):
    """Pydantic model for validating instance.yaml structure."""
    name: str
    display_name: str
    description: str = ""
    archetype: str | None = None
    standalone: bool = False
    domain: str = ""
    timezone: str = "UTC"
    languages: list[str] = ["en"]
    auth: AuthConfig = AuthConfig()
    persona: dict[str, str] | None = None
    navigation_routes: list[dict[str, str]] = []
    tools: dict[str, Any] | None = None


# ── Jinja2 environment (filesystem loader for archetype templates) ──────────

_jinja_env: Environment | None = None


def _get_jinja_env() -> Environment:
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(loader=BaseLoader(), autoescape=False)
    return _jinja_env


# ── Public API ──────────────────────────────────────────────────────────────

def list_archetypes() -> list[str]:
    """Discover all archetype directories under archetypes/.

    Returns:
        Sorted list of archetype names.
    """
    if not _ARCHETYPES_ROOT.exists():
        return []
    names: list[str] = []
    for p in _ARCHETYPES_ROOT.iterdir():
        if p.is_dir() and (p / "archetype.yaml").exists():
            names.append(p.name)
    return sorted(names)


def load_archetype(name: str) -> ArchetypeMeta:
    """Load an archetype by name.

    Args:
        name: Archetype directory name (e.g. "twin-mind").

    Returns:
        ArchetypeMeta with parsed metadata.

    Raises:
        FileNotFoundError: if the archetype directory or archetype.yaml is missing.
        ValueError: if archetype.yaml is malformed or missing required keys.
    """
    dir_path = _ARCHETYPES_ROOT / name
    if not dir_path.is_dir():
        raise FileNotFoundError(f"Archetype '{name}' not found at {dir_path}")

    yaml_path = dir_path / "archetype.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"archetype.yaml missing for archetype '{name}' at {yaml_path}")

    try:
        with open(yaml_path, "r") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {yaml_path}: {e}") from e

    if not isinstance(raw, dict):
        raise ValueError(f"archetype.yaml for '{name}' must be a mapping, got {type(raw).__name__}")

    for key in ("name", "version", "description"):
        if key not in raw:
            raise ValueError(f"archetype.yaml for '{name}' missing required key: {key!r}")

    requires_raw = raw.get("requires", {})
    if not isinstance(requires_raw, dict):
        requires_raw = {}

    return ArchetypeMeta(
        name=raw["name"],
        version=str(raw["version"]),
        description=raw["description"],
        icon_set=raw.get("icon_set", "default"),
        requires=ArchetypeRequires(
            pulse_version=requires_raw.get("pulse_version", ">=0.3.0"),
            auth_mode=requires_raw.get("auth_mode", "local"),
            storage_mode=requires_raw.get("storage_mode", "standalone"),
        ),
    )


def render_instance_config(
    archetype_name: str,
    instance_name: str,
    display_name: str = "",
    extra_vars: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Render an instance.template.yaml into a config dict.

    Args:
        archetype_name: Name of the archetype (e.g. "twin-mind").
        instance_name:  Name for the new instance.
        display_name:   Human-readable display name (defaults to instance_name).
        extra_vars:     Extra Jinja2 template variables.

    Returns:
        Parsed YAML dict ready to write to instances/<instance_name>/instance.yaml.

    Raises:
        FileNotFoundError: if the archetype or template is missing.
        ValueError: if template rendering fails.
    """
    meta = load_archetype(archetype_name)
    template_path = meta.dir_path / "instance.template.yaml"

    if not template_path.exists():
        raise FileNotFoundError(
            f"No instance.template.yaml for archetype '{archetype_name}' at {template_path}"
        )

    with open(template_path, "r") as f:
        template_str = f.read()

    env = _get_jinja_env()
    template = env.from_string(template_str)

    display = display_name or instance_name

    vars_dict: dict[str, Any] = {
        "instance_name": instance_name,
        "display_name": display,
        "description": f"{display} — a {meta.name} instance",
        "archetype_name": meta.name,
        "archetype_version": meta.version,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "timezone": "UTC",
        "languages": ["en"],
        "persona_tagline": "your personal knowledge, goals, and journal",
        "persona_audience": "an individual user",
    }
    if extra_vars:
        vars_dict.update(extra_vars)

    try:
        rendered = template.render(**vars_dict)
    except Exception as e:
        raise ValueError(f"Template rendering failed for archetype '{archetype_name}': {e}") from e

    try:
        config = yaml.safe_load(rendered)
    except yaml.YAMLError as e:
        raise ValueError(f"Rendered template is not valid YAML: {e}") from e

    if not isinstance(config, dict):
        raise ValueError(f"Rendered template produced {type(config).__name__}, expected dict")

    return config


def validate_instance_config(config: dict[str, Any]) -> list[str]:
    """Validate an instance config dict against the InstanceConfig model.

    Args:
        config: Parsed instance YAML dict.

    Returns:
        List of error messages (empty = valid).
    """
    errors: list[str] = []
    try:
        InstanceConfig.model_validate(config)
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(part) for part in err["loc"])
            msg = err.get("msg", "unknown error")
            errors.append(f"{loc}: {msg}")
    return errors


def validate_instance_config_or_raise(config: dict[str, Any]) -> None:
    """Validate and raise ValueError on first error."""
    errs = validate_instance_config(config)
    if errs:
        raise ValueError(errs[0])


def get_instance_config_path(instance_name: str) -> Path:
    """Return the path to an instance's YAML config file."""
    return _PROJECT_ROOT / "instances" / instance_name / "instance.yaml"


def load_instance_config(instance_name: str) -> dict[str, Any]:
    """Load and parse an existing instance's YAML config.

    Returns empty dict if not found.
    """
    path = get_instance_config_path(instance_name)
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}
