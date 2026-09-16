"""Guidance-skill folder loader — DEFERRED(F1a).

PULSE-CANONICAL §12: filesystem ``domain_packs/*/skills`` guidance is NOT
injected on the live chat path. Host wiring (``ai.domain_skills``) was removed
in PEC-7A. This module remains as a stdlib-only parser for offline/tests and
possible future ADR-backed use; do not re-wire into ``build_chat_prompt``
without an ADR.

A "guidance skill" is a folder containing a ``SKILL.md`` with ``---``-delimited
YAML frontmatter followed by a Markdown body, plus optional ``references/*.md``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("pulse.knowledge.skill_folder")

_FRONTMATTER_FENCE = "---"


@dataclass(frozen=True)
class GuidanceSkill:
    """A parsed guidance skill: metadata + body + on-demand references."""

    name: str
    description: str
    allowed_tools: tuple[str, ...]
    when_to_use: tuple[str, ...]
    body: str
    references: dict[str, str] = field(default_factory=dict)


# ── Tiny frontmatter parser (stdlib-only; no PyYAML dependency) ──────────────

def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _parse_list(value: str) -> tuple[str, ...]:
    """Parse a ``[a, b, c]`` (or bare comma) list into a tuple of strings."""
    value = value.strip()
    if value in ("", "[]", "null", "~"):
        return ()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    items = (part.strip() for part in value.split(","))
    return tuple(_strip_quotes(part) for part in items if part)


def _as_tuple(value) -> tuple[str, ...]:
    """Normalize a frontmatter value (scalar or list) to a tuple of strings."""
    if value is None:
        return ()
    if isinstance(value, (tuple, list)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return _parse_list(str(value))


def _first_key(metadata: dict, *keys: str):
    """Return the first present key's value, else ``None``."""
    for key in keys:
        if key in metadata:
            return metadata[key]
    return None


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split leading ``---``-delimited frontmatter from the body.

    Returns ``(metadata, body)``.  Raises ``ValueError`` on malformed input.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        raise ValueError("SKILL.md must begin with a --- frontmatter fence")

    end: int | None = None
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_FENCE:
            end = index
            break
    if end is None:
        raise ValueError("unterminated frontmatter (missing closing ---)")

    metadata: dict = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"invalid frontmatter line: {line!r}")
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            metadata[key] = _parse_list(value)
        else:
            metadata[key] = _strip_quotes(value)

    body = "\n".join(lines[end + 1:]).strip()
    return metadata, body


def _load_references(path: Path) -> dict[str, str]:
    """Load every ``*.md`` under ``<folder>/references/`` keyed by stem."""
    references: dict[str, str] = {}
    refs_dir = path / "references"
    if not refs_dir.is_dir():
        return references
    for md_file in sorted(refs_dir.glob("*.md")):
        try:
            references[md_file.stem] = md_file.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning(
                "skill folder %s: cannot read reference %s: %s",
                path, md_file.name, exc,
            )
    return references


def parse_skill_folder(path: Path) -> GuidanceSkill | None:
    """Parse ``<folder>/SKILL.md`` (frontmatter + body + references).

    Returns ``None`` (and logs) on missing or malformed input — never raises.
    """
    skill_md = path / "SKILL.md"
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("skill folder %s: cannot read SKILL.md: %s", path, exc)
        return None

    try:
        metadata, body = _split_frontmatter(text)
    except ValueError as exc:
        logger.warning("skill folder %s: %s", path, exc)
        return None

    name = metadata.get("name")
    if not isinstance(name, str) or not name.strip():
        logger.warning("skill folder %s: missing or empty 'name'", path)
        return None

    description = metadata.get("description")
    if not isinstance(description, str):
        description = ""

    return GuidanceSkill(
        name=name.strip(),
        description=description.strip(),
        allowed_tools=_as_tuple(_first_key(metadata, "allowed-tools", "allowed_tools")),
        when_to_use=_as_tuple(_first_key(metadata, "when_to_use", "when-to-use")),
        body=body,
        references=_load_references(path),
    )


def load_skill_folders(root: Path) -> list[GuidanceSkill]:
    """Load every immediate subfolder of ``root`` containing a ``SKILL.md``.

    Sorted by name for determinism.  Never raises — returns ``[]`` on any I/O
    or parse failure (each malformed folder is skipped individually).
    """
    if not root.is_dir():
        return []
    try:
        entries = sorted(root.iterdir(), key=lambda p: p.name)
    except OSError as exc:
        logger.warning("skill folders root %s: cannot list: %s", root, exc)
        return []

    skills: list[GuidanceSkill] = []
    for entry in entries:
        if not entry.is_dir():
            continue
        if not (entry / "SKILL.md").is_file():
            continue
        skill = parse_skill_folder(entry)
        if skill is not None:
            skills.append(skill)

    skills.sort(key=lambda s: s.name)
    return skills


def get_skill(name: str, skills: list[GuidanceSkill]) -> GuidanceSkill | None:
    """Look up a skill by name (progressive-disclosure on-demand access)."""
    for skill in skills:
        if skill.name == name:
            return skill
    return None


def skill_index_prompt(skills: list[GuidanceSkill]) -> str:
    """Render a compact one-line-per-skill index for the always-on prompt."""
    ordered = sorted(skills, key=lambda s: s.name)
    return "\n".join(f"- {s.name}: {s.description}" for s in ordered)


def skill_body(name: str, skills: list[GuidanceSkill]) -> str:
    """Return the full body for ``name`` on demand (empty string if absent)."""
    skill = get_skill(name, skills)
    return skill.body if skill is not None else ""


def skill_references(name: str, skills: list[GuidanceSkill]) -> dict[str, str]:
    """Return the references for ``name`` on demand (empty dict if absent)."""
    skill = get_skill(name, skills)
    return skill.references if skill is not None else {}
