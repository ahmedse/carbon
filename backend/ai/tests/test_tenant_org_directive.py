"""Tenant-org grounding — kill the GOFSCO/AASTMT clarification loop.

When the user asks about the whole organisation / "the company" / "data in
the system", Chat must ground on ``tenant_org`` from instance.yaml instead of
asking "What specifically would you like to know…?" in a loop.
"""

from __future__ import annotations

import asyncio

from ai.engine.llm.prompts import _build_tenant_org_directive, build_chat_prompt


def test_tenant_org_directive_names_aliases_and_forbids_clarify_loop():
    directive = _build_tenant_org_directive(
        {
            "tenant_org": {
                "name": "GOFSCO — Gas & Oil Field Services Company",
                "short_name": "GOFSCO",
                "aliases": ["GOFSCO", "gofsco"],
                "summary": "Kuwait oilfield services People & Payroll spine.",
            }
        }
    )
    assert "Tenant organisation" in directive
    assert "GOFSCO" in directive
    assert "clarifying questions in a loop" in directive
    assert "aggregate_entity" in directive
    assert "data in the system" in directive


def test_tenant_org_directive_empty_without_config():
    assert _build_tenant_org_directive(None) == ""
    assert _build_tenant_org_directive({}) == ""
    assert _build_tenant_org_directive({"tenant_org": {}}) == ""


def test_build_chat_prompt_includes_tenant_org_section():
    prompt = asyncio.run(
        build_chat_prompt(
            instance_name="Nibras — People & Payroll",
            system_description="People & Payroll for GOFSCO.",
            instance_config={
                "persona": "You are the Nibras assistant.",
                "tenant_org": {
                    "name": "GOFSCO — Gas & Oil Field Services Company",
                    "short_name": "GOFSCO",
                    "aliases": ["GOFSCO"],
                },
                "api_catalog": [
                    {
                        "name": "list_employees",
                        "method": "GET",
                        "description": "List employees",
                    }
                ],
            },
        )
    )
    assert "## Tenant organisation (non-negotiable)" in prompt
    assert "GOFSCO" in prompt
    assert "do NOT ask clarifying questions in a loop" in prompt
