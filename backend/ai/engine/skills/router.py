"""Skill router — matches user queries to skills via coverage declarations (GAP-6).

Domain-agnostic: matching is done against each skill's declared `covers` list
(topic slugs stored in skill.body JSON). If no skill covers the topic, the
caller falls through to FallbackHandler.
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger("pulse.skills.router")


class SkillRouter:
    """Routes queries to skills based on their coverage declarations."""

    def find_matching_skills(
        self,
        user_message: str,
        skills: list,
    ) -> list:
        """Return skills whose `covers` slugs match topics in user_message."""
        matched = []
        for skill in skills:
            contract = self._parse_contract(skill)
            if not contract:
                continue
            covers: list[str] = contract.get("covers", [])
            if any(self._slug_mentioned(slug, user_message) for slug in covers):
                matched.append(skill)
        return matched

    def get_terminology(self, skills: list) -> dict[str, str]:
        """Aggregate terminology maps from all provided skills.

        Later skills' entries override earlier ones on key conflicts.
        """
        result: dict[str, str] = {}
        for skill in skills:
            contract = self._parse_contract(skill)
            if contract:
                result.update(contract.get("terminology", {}))
        return result

    def _parse_contract(self, skill) -> dict | None:
        try:
            body = (
                json.loads(skill.body)
                if isinstance(skill.body, str)
                else skill.body
            )
            return body if isinstance(body, dict) else None
        except Exception:
            return None

    def _slug_mentioned(self, slug: str, user_message: str) -> bool:
        """Case-insensitive, word-boundary slug detection.

        Handles slugs with hyphens and underscores: "data-quality" matches
        "data quality", "data-quality", and "data_quality".
        """
        words = re.split(r"[_\-]", slug)
        combined = r"[\s_\-]+".join(re.escape(w) for w in words if w)
        return bool(re.search(rf"\b{combined}\b", user_message, re.IGNORECASE))
