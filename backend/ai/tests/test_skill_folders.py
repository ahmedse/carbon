"""P4-03 guidance-skill folder loader + progressive-disclosure tests.

Offline — no LLM, no DB (``-m "not live"``).
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from ai.domain_skills import get_guidance_skills, pack_skills_dir
from ai.engine.knowledge.skill_folder import (
    load_skill_folders,
    parse_skill_folder,
    skill_body,
    skill_index_prompt,
    skill_references,
)
from ai.engine.llm.prompts import (
    RENDERING_CAPABILITIES,
    RENDERING_CAPABILITIES_SUMMARY,
    build_chat_prompt,
)


def _write_skill(root: Path, name: str, fm: str, body: str = "", refs: dict | None = None) -> Path:
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(f"---\n{fm}\n---\n{body}", encoding="utf-8")
    for ref_name, ref_body in (refs or {}).items():
        ref_dir = folder / "references"
        ref_dir.mkdir(parents=True, exist_ok=True)
        (ref_dir / f"{ref_name}.md").write_text(ref_body, encoding="utf-8")
    return folder


# ── 1. Frontmatter + body + references parsing ─────────────────────────────

def test_parse_skill_folder_parses_frontmatter_body_and_references():
    with tempfile.TemporaryDirectory() as tmp:
        folder = _write_skill(
            Path(tmp),
            "demo-skill",
            "name: demo-skill\n"
            "description: A demo guidance skill\n"
            "allowed-tools: [tool_a, tool_b]\n"
            "when_to_use: [trigger_1, trigger_2]\n",
            body="The body text.\nSecond line.",
            refs={"guide": "# Guide\n\nReference content."},
        )
        skill = parse_skill_folder(folder)
        assert skill is not None
        assert skill.name == "demo-skill"
        assert skill.description == "A demo guidance skill"
        assert skill.allowed_tools == ("tool_a", "tool_b")
        assert skill.when_to_use == ("trigger_1", "trigger_2")
        assert skill.body == "The body text.\nSecond line."
        assert skill.references == {"guide": "# Guide\n\nReference content."}


# ── 2. Malformed input never raises ────────────────────────────────────────

def test_parse_skill_folder_returns_none_on_malformed_input():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # Missing SKILL.md
        empty = root / "empty"
        empty.mkdir()
        assert parse_skill_folder(empty) is None

        # Missing opening frontmatter fence
        no_fence = root / "no-fence"
        no_fence.mkdir()
        (no_fence / "SKILL.md").write_text("no frontmatter here", encoding="utf-8")
        assert parse_skill_folder(no_fence) is None

        # Unterminated frontmatter
        unterminated = root / "unterminated"
        unterminated.mkdir()
        (unterminated / "SKILL.md").write_text("---\nname: x\n", encoding="utf-8")
        assert parse_skill_folder(unterminated) is None

        # Missing required name
        no_name = root / "no-name"
        no_name.mkdir()
        (no_name / "SKILL.md").write_text(
            "---\ndescription: no name\n---\nbody", encoding="utf-8"
        )
        assert parse_skill_folder(no_name) is None


# ── 3. Real pack loading, deterministic order ──────────────────────────────

def test_load_skill_folders_loads_real_carbon_skills():
    skills = load_skill_folders(pack_skills_dir("carbon"))
    names = {s.name for s in skills}
    assert {"rich-content-rendering", "domain-guidance", "tool-guidance"} <= names
    assert len(skills) >= 3
    # Deterministic order.
    assert [s.name for s in skills] == sorted(s.name for s in skills)
    # The host wrapper returns the same set (integration seam).
    assert {s.name for s in get_guidance_skills("carbon")} >= names


# ── 4. Compact index (token-budget win) ────────────────────────────────────

def test_skill_index_prompt_is_compact():
    skills = get_guidance_skills("carbon")
    index = skill_index_prompt(skills)
    # The index must be measurably shorter than the full rendering block.
    assert len(index) < len(RENDERING_CAPABILITIES) // 2
    assert "rich-content-rendering" in index
    # One line per skill — no worked examples leak into the index.
    assert index.count("\n") == len(skills) - 1


# ── 5. Progressive disclosure ──────────────────────────────────────────────

def test_progressive_disclosure_body_and_references_on_demand():
    skills = get_guidance_skills("carbon")

    body = skill_body("rich-content-rendering", skills)
    assert body  # full body returned on demand

    refs = skill_references("rich-content-rendering", skills)
    assert "formatting-examples" in refs
    assert "mermaid" in refs["formatting-examples"]
    assert "xychart-beta" in refs["formatting-examples"]

    # The worked examples are NOT in the always-on index.
    index = skill_index_prompt(skills)
    assert "xychart-beta" not in index


# ── 6. Always-on prompt uses summary, not the full block ───────────────────

def test_assembled_prompt_uses_summary_not_full_block():
    skills = get_guidance_skills("carbon")
    prompt = asyncio.run(
        build_chat_prompt(
            instance_name="Test",
            system_description="Data trust platform.",
            guidance_skills=skills,
        )
    )
    assert RENDERING_CAPABILITIES_SUMMARY in prompt
    assert RENDERING_CAPABILITIES not in prompt
    # The skills index (names + descriptions) is present.
    assert "rich-content-rendering" in prompt
    assert "domain-guidance" in prompt
    assert "tool-guidance" in prompt


# ── 7. Backward-compat: full block remains importable ──────────────────────

def test_rendering_capabilities_symbol_still_importable():
    assert "```mermaid" in RENDERING_CAPABILITIES
    assert "KaTeX" in RENDERING_CAPABILITIES
    assert "never say you cannot" in RENDERING_CAPABILITIES
