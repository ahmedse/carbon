"""ContextPack building blocks (PV2-2C IdentityBlock; PV2-2A extends).

Engine-only: no Django / host imports. Audience values arrive via
``user_info["audience"]`` from the host.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

VALID_AUDIENCES = frozenset({"ess", "hr", "admin"})
DEFAULT_AUDIENCE = ("hr",)
MY_AUDIENCE = ("ess", "hr")


def entry_audience(entry: dict | None) -> tuple[str, ...]:
    """Resolve the audience tags for one catalog / nav entry.

    Unmarked → ``hr``. Names containing ``_my_`` → ``ess`` + ``hr``.
    Explicit ``audience:`` lists are normalised to the valid enum.
    """
    if not isinstance(entry, dict):
        return DEFAULT_AUDIENCE
    raw = entry.get("audience")
    if isinstance(raw, str):
        raw = [raw]
    if isinstance(raw, (list, tuple)) and raw:
        tags = tuple(
            t for t in (str(x).strip().lower() for x in raw) if t in VALID_AUDIENCES
        )
        if tags:
            return tags
    name = str(entry.get("name") or "")
    if "_my_" in name:
        return MY_AUDIENCE
    # Navigation routes are self-service + HR.
    if entry.get("type") in ("app", "route", "nav") or str(
        entry.get("path") or ""
    ).startswith("/my"):
        return MY_AUDIENCE
    return DEFAULT_AUDIENCE


def filter_catalog_by_audience(
    catalog: list[dict] | None,
    audience: Iterable[str] | None,
) -> list[dict]:
    """Keep catalog entries whose audience intersects ``audience``."""
    user_aud = {
        str(a).strip().lower()
        for a in (audience or ())
        if str(a).strip().lower() in VALID_AUDIENCES
    } or {"ess"}
    out: list[dict] = []
    for entry in catalog or []:
        if not isinstance(entry, dict):
            continue
        if set(entry_audience(entry)) & user_aud:
            out.append(entry)
    return out


def normalize_catalog_audiences(catalog: list[dict] | None) -> list[dict]:
    """Return a copy of catalog with explicit ``audience`` on every entry."""
    out: list[dict] = []
    for entry in catalog or []:
        if not isinstance(entry, dict):
            continue
        copy = dict(entry)
        copy["audience"] = list(entry_audience(entry))
        out.append(copy)
    return out


def validate_catalog_audiences(catalog: list[dict] | None) -> list[str]:
    """Return error strings for invalid ``audience`` tags (empty = ok)."""
    errors: list[str] = []
    for i, entry in enumerate(catalog or []):
        if not isinstance(entry, dict):
            continue
        raw = entry.get("audience")
        if raw is None:
            continue
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, (list, tuple)):
            errors.append(
                f"api_catalog[{i}].audience: must be a list, got {type(raw).__name__}"
            )
            continue
        for tag in raw:
            t = str(tag).strip().lower()
            if t not in VALID_AUDIENCES:
                name = entry.get("name") or i
                errors.append(
                    f"api_catalog[{name}].audience: invalid tag {tag!r} "
                    f"(expected one of {sorted(VALID_AUDIENCES)})"
                )
    return errors


@dataclass
class IdentityBlock:
    """Shared persona + one audience-specific guidance block (PV2-2C).

    PV2-2A will extend this into a full ContextPack; keep the surface small.
    """

    persona: str = ""
    audience: frozenset[str] | set[str] | list[str] | tuple[str, ...] = field(
        default_factory=lambda: {"ess"}
    )
    guidance: dict[str, str] = field(default_factory=dict)

    def _guidance_key(self) -> str:
        aud = {
            str(a).strip().lower()
            for a in (self.audience or ())
            if str(a).strip()
        }
        g = self.guidance or {}
        if "admin" in aud and (g.get("admin") or "").strip():
            return "admin"
        if "hr" in aud and (g.get("hr") or "").strip():
            return "hr"
        if (g.get("ess") or "").strip():
            return "ess"
        for key in ("admin", "hr", "ess"):
            if (g.get(key) or "").strip():
                return key
        return "ess"

    def render(self) -> str:
        parts: list[str] = []
        persona = (self.persona or "").strip()
        if persona:
            parts.append(persona)
        key = self._guidance_key()
        block = (self.guidance or {}).get(key) or ""
        block = block.strip()
        if block:
            parts.append(block)
        return "\n\n".join(parts)


def compose_persona_for_audience(
    instance_config: dict[str, Any] | None,
    audience: Iterable[str] | None,
) -> str:
    """Render IdentityBlock from instance.yaml ``persona`` + ``guidance_by_audience``."""
    cfg = instance_config or {}
    persona = cfg.get("persona") or ""
    if isinstance(persona, dict):
        # Archetype templates sometimes store structured persona; flatten.
        persona = (
            persona.get("text")
            or persona.get("body")
            or " ".join(str(v) for v in persona.values() if v)
        )
    guidance = cfg.get("guidance_by_audience") or {}
    if not isinstance(guidance, dict):
        guidance = {}
    return IdentityBlock(
        persona=str(persona or ""),
        audience=list(audience or ["ess"]),
        guidance={str(k): str(v or "") for k, v in guidance.items()},
    ).render()
