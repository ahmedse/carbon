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


def test_build_chat_prompt_renders_api_catalog_endpoints():
    # Regression: the chat path must name call_host_api endpoint names directly
    # in the system prompt — search_knowledge searches the knowledge graph, not
    # the catalog, so without this section the model recites generic factors
    # instead of calling the live emissions endpoints.
    api_catalog = [
        {
            "name": "list_emission_factors",
            "method": "GET",
            "description": "List active emission factors (kg CO2e per activity unit).",
            "requires_confirmation": False,
        },
        {
            "name": "get_chairman_overview",
            "method": "GET",
            "description": "Org-scoped carbon footprint headline + scope breakdown.",
            "requires_confirmation": False,
        },
    ]
    prompt = asyncio.run(
        build_chat_prompt(
            instance_name="AASTMT",
            system_description="Data trust platform.",
            api_catalog=api_catalog,
        )
    )
    assert "## Available Host API Endpoints" in prompt
    assert "list_emission_factors" in prompt
    assert "get_chairman_overview" in prompt
    assert "call_host_api" in prompt


def test_build_chat_prompt_injects_live_data_grounding_directive():
    # Regression: "tell me about emission factors HERE" must map to the live
    # endpoint, not a parametric lecture. The grounding directive is derived
    # from the catalog (ADR-0017) and maps each read domain to its endpoint.
    api_catalog = [
        {
            "name": "list_emission_factors",
            "method": "GET",
            "description": "List active emission factors.",
            "requires_confirmation": False,
        },
        {
            "name": "create_dq_rule",
            "method": "POST",
            "description": "Create a DQ rule.",
            "requires_confirmation": True,
        },
    ]
    prompt = asyncio.run(
        build_chat_prompt(
            instance_name="AASTMT",
            system_description="Data trust platform.",
            api_catalog=api_catalog,
        )
    )
    assert "## Live data grounding (non-negotiable)" in prompt
    assert "emission factors → `list_emission_factors`" in prompt
    assert "call_host_api" in prompt
    # Mutation endpoints are NOT live-data answer domains.
    assert "create_dq_rule → `create_dq_rule`" not in prompt


def test_endpoint_to_domain_phrase_strips_read_prefix():
    from ai.engine.llm.prompts import _endpoint_to_domain_phrase

    assert _endpoint_to_domain_phrase("list_emission_factors") == "emission factors"
    assert _endpoint_to_domain_phrase("get_calculation_summary") == "calculation summary"
    assert _endpoint_to_domain_phrase("list_gwp_gases") == "gwp gases"


def test_fast_respond_system_prompt_can_draw_diagrams():
    persona = {"domain_noun": "data quality operations", "audience": "platform users"}
    system = PulseAgent._fast_respond_system_prompt(
        platform="AASTMT · Data Trust Platform",
        persona=persona,
    )
    assert "```mermaid" in system
    assert "Never say you cannot draw a diagram" in system
