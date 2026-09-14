"""Host-side resolver for guidance-skill folders (P4-03).

Locates the ``skills/`` directory for an instance/brand's domain pack and loads
guidance skills through the engine loader.  This module is host-side (it may
import Django settings to resolve the pack root) but delegates ALL parsing to
``ai.engine.knowledge.skill_folder`` — no domain vocabulary is duplicated here.

Fail-open by design: any resolution/parse error yields an empty list, so a
misconfigured pack can never break prompt assembly.
"""
from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings

from ai.engine.knowledge.skill_folder import (
    GuidanceSkill,
    load_skill_folders,
    skill_body,
    skill_references,
)

logger = logging.getLogger("pulse.domain_skills")

_skills_cache: dict[str, tuple[GuidanceSkill, ...]] = {}


def pack_skills_dir(instance_id: str = "carbon") -> Path:
    """Resolve the ``skills/`` directory for an instance's domain pack.

    The host maps ``instance_id`` → domain-pack directory; the engine stays
    brand-agnostic (it only ever sees a generic folder path).
    """
    return Path(settings.BASE_DIR).parent / "domain_packs" / instance_id / "skills"


def get_guidance_skills(instance_id: str = "carbon") -> list[GuidanceSkill]:
    """Load guidance skills for an instance (fail-open: empty list on error)."""
    if instance_id in _skills_cache:
        return list(_skills_cache[instance_id])

    try:
        loaded = tuple(load_skill_folders(pack_skills_dir(instance_id)))
    except Exception as exc:  # noqa: BLE001 - host seam must fail open
        logger.warning("guidance skills load failed for %s: %s", instance_id, exc)
        loaded = ()

    _skills_cache[instance_id] = loaded
    return list(loaded)


def get_skill_body(name: str, instance_id: str = "carbon") -> str:
    """Return a skill's full body on demand (progressive disclosure)."""
    return skill_body(name, get_guidance_skills(instance_id))


def get_skill_references(name: str, instance_id: str = "carbon") -> dict[str, str]:
    """Return a skill's references on demand (progressive disclosure)."""
    return skill_references(name, get_guidance_skills(instance_id))
