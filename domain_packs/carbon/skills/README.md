# Skills — DEFERRED(F1a)

**Status (PEC-7A / PULSE-CANONICAL §12):** filesystem guidance packs are **not**
injected on the live chat path. Prompt config is ``instance.yaml`` only.
Do not re-wire via ``guidance_skills=`` without an ADR.

Host loader ``backend/ai/domain_skills.py`` was removed. Packs remain on disk
as reference content that may be folded into ``instance.yaml`` later.

## Format

A guidance skill folder contains:

- `SKILL.md` — frontmatter + body. Required frontmatter keys: `name`,
  `description`. Optional keys: `allowed-tools`, `when_to_use`.
- `references/*.md` — longer worked examples / prose, keyed by stem.

Parser (offline only): `backend/ai/engine/knowledge/skill_folder.py`.

## Skills present

| Skill | Description | Migrated from |
|-------|-------------|---------------|
| `rich-content-rendering` | How to format replies with tables, code, mermaid diagrams, KaTeX math, and figures | `RENDERING_CAPABILITIES` worked examples |
| `domain-guidance` | Core domain rules and scope boundaries | former `_fallback_prompt` bullets |
| `tool-guidance` | When/how to use `call_host_api` and `search_knowledge` for live data | live-data grounding guidance |
