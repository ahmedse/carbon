# Skills

This directory holds **guidance skill folders** per the Agent Skills spec
(P4-03). Each folder is a `SKILL.md` with `---`-delimited YAML frontmatter
(metadata) followed by a Markdown body, plus optional `references/*.md` files
loaded on demand.

## Format

A guidance skill folder contains:

- `SKILL.md` — frontmatter + body. Required frontmatter keys: `name`,
  `description`. Optional keys: `allowed-tools` (a list, metadata-only in this
  phase — enforcement is P4-04), `when_to_use` (trigger slugs).
- `references/*.md` — longer worked examples / prose, keyed by stem, loaded
  only on demand (progressive disclosure).

The engine parses these via `backend/ai/engine/knowledge/skill_folder.py`
(domain-agnostic, stdlib-only). The host resolves this directory via
`backend/ai/domain_skills.py` (`get_guidance_skills("carbon")`).

## Progressive disclosure

The always-on system prompt carries only a compact index (one line per skill:
`- <name>: <description>`) plus the compact `RENDERING_CAPABILITIES_SUMMARY`.
Full bodies and references are fetched on demand via `skill_body(...)` /
`skill_references(...)`.

## Skills present

| Skill | Description | Migrated from |
|-------|-------------|---------------|
| `rich-content-rendering` | How to format replies with tables, code, mermaid diagrams, KaTeX math, and figures | `ai.engine.llm.prompts.RENDERING_CAPABILITIES` (full worked examples moved to `references/formatting-examples.md`) |
| `domain-guidance` | Core domain rules and scope boundaries | the "Lead with the answer / Ground every claim / time-aware / confirmation / access scope / redirect" bullets from `ai.engine.llm.playbook._fallback_prompt` |
| `tool-guidance` | When/how to use `call_host_api` and `search_knowledge` for live data | the tool-heuristic + live-data grounding guidance from `ai.engine.llm.prompts._build_grounding_directive` (full aggregation rules in `references/live-data-grounding.md`) |
