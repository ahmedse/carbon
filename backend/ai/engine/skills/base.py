"""SkillContract — base Pydantic model all skills implement (GAP-6).

Declares what topics the skill covers, what prerequisites it needs,
what it produces, and a canonical terminology map.

The host app populates this in the skill's body JSON. The intelligence
core reads it without knowing what any specific term means.
"""
from __future__ import annotations

from pydantic import BaseModel


class SkillContract(BaseModel):
    """Metadata contract for any skill — domain-agnostic declarations."""

    covers: list[str] = []             # topic slugs this skill handles
    requires: list[str] = []           # prerequisite context slugs needed
    produces: list[str] = []           # output type slugs generated
    terminology: dict[str, str] = {}   # human_phrase → platform_term


def parse_contract(body_json: dict) -> SkillContract:
    """Parse a SkillContract from a skill's body JSON (best-effort, no raises)."""
    return SkillContract(
        covers=body_json.get("covers", []),
        requires=body_json.get("requires", []),
        produces=body_json.get("produces", []),
        terminology=body_json.get("terminology", {}),
    )
