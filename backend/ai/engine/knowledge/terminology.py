"""Canonical terminology map injector for skill playbooks (GAP-5).

Each skill declares a terminology map (human prose → platform term) in its
body JSON. At draft time, this map is injected into the system prompt so the
LLM uses consistent platform vocabulary.

Domain-agnostic: the resolver knows nothing about the terms themselves; it
just formats the map into a system-prompt section.
"""
from __future__ import annotations


class TerminologyResolver:
    """Injects a skill's canonical terminology map into the system prompt."""

    def inject(self, system_prompt: str, terminology: dict[str, str]) -> str:
        """Append a CANONICAL TERMINOLOGY section to system_prompt.

        terminology: {"human phrase": "platform_term", ...}
        Returns the prompt unchanged if terminology is empty.
        """
        if not terminology:
            return system_prompt

        lines = ["", "CANONICAL TERMINOLOGY — use these exact platform terms:"]
        for human, platform in terminology.items():
            lines.append(f'- Use "{platform}" (not "{human}")')
        return system_prompt + "\n".join(lines)
