"""Assistant rendering-capability instructions (Phase 4).

The frontend renders assistant markdown richly (tables, syntax-highlighted
code, live mermaid diagrams, KaTeX math, figure captions).  The model must be
told it CAN draw diagrams and format content — otherwise it answers "I cannot
create visual diagrams" even though the platform renders them.

These tests lock the instruction into every system-prompt path:
  * playbook/fallback assembly (build_chat_prompt, instance_id=None path)
  * standalone _fallback_prompt (no PlaybookBlocks)
  * _fast_respond conversational system prompt
"""
import asyncio

from ai.engine.agent.reasoning import PulseAgent
from ai.engine.llm.playbook import _fallback_prompt
from ai.engine.llm.prompts import RENDERING_CAPABILITIES, build_chat_prompt


def test_rendering_capabilities_block_mentions_diagrams():
    assert "mermaid" in RENDERING_CAPABILITIES
    assert "```mermaid" in RENDERING_CAPABILITIES
    assert "never say you cannot" in RENDERING_CAPABILITIES
    assert "**Tables**" in RENDERING_CAPABILITIES
    assert "KaTeX" in RENDERING_CAPABILITIES


def test_fallback_prompt_includes_rendering_block():
    prompt = _fallback_prompt({"instance_name": "AASTMT"})
    assert "## Rich content rendering" in prompt
    assert "```mermaid" in prompt
    # Identity rules survive — the rendering block is additive.
    assert "## Identity & Role" in prompt


def test_build_chat_prompt_includes_rendering_block():
    prompt = asyncio.run(
        build_chat_prompt(
            instance_name="AASTMT",
            system_description="Data trust platform.",
        )
    )
    assert "## Rich content rendering" in prompt
    assert "```mermaid" in prompt
    assert "flowchart LR" in prompt


def test_build_chat_prompt_rendering_block_survives_access_inventory():
    # Even with a per-user access inventory, the rendering block stays present.
    instance_config = {
        "display_name": "AASTMT · Data Trust Platform",
        "user_access": {
            "platform_name": "AASTMT · Data Trust Platform",
            "access_level": "view-only",
            "platform_wide": False,
            "is_read_only": True,
            "apps": [],
            "capabilities": [],
            "modules": [],
            "routes": [],
        },
    }
    prompt = asyncio.run(
        build_chat_prompt(
            instance_name="AASTMT",
            system_description="Data trust platform.",
            instance_config=instance_config,
        )
    )
    assert "## Your Access (strict inventory)" in prompt
    assert "## Rich content rendering" in prompt
    assert "```mermaid" in prompt


def test_fast_respond_system_prompt_can_draw_diagrams():
    persona = {"domain_noun": "data quality operations", "audience": "platform users"}
    system = PulseAgent._fast_respond_system_prompt(
        platform="AASTMT · Data Trust Platform",
        persona=persona,
    )
    assert "```mermaid" in system
    assert "Never say you cannot draw a diagram" in system
