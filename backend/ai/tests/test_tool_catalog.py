"""Pulse 0.3 (Phase E2) — domain tool catalog + CBAC filtering tests.

Covers the four invariants the E2 task pins:

  (a) every registered domain's ``get_tools()`` returns ``list[ToolDef]`` with
      valid ids/descriptions/capabilities/schemas;
  (b) ``get_tool_catalog`` filters out a tool whose ``required_capability`` the
      user lacks;
  (c) a ``"*"`` capability user sees every domain tool;
  (d) a ``required_capability=None`` tool is always included.
"""

import re
from io import StringIO

import pytest

from accounts.capabilities import ALL_CAPABILITIES
from ai.adapter.carbon import CarbonHostAdapter
from ai.adapter.types import ToolDef
from ai.domain_protocol import get_domain, list_domains


def _all_domain_tools() -> list[ToolDef]:
    """Unfiltered union of every registered domain's ``get_tools()``."""
    tools: list[ToolDef] = []
    for app_id in list_domains():
        tools.extend(get_domain(app_id)().get_tools())
    return tools


def test_every_domain_get_tools_returns_valid_tooldefs():
    """(a) Each registered domain's ``get_tools()`` is a valid ``list[ToolDef]``."""
    for app_id in list_domains():
        domain = get_domain(app_id)()
        tools = domain.get_tools()
        assert isinstance(tools, list), f"{app_id}.get_tools() must return a list"
        for tool in tools:
            assert isinstance(tool, ToolDef), f"{app_id} returned a non-ToolDef entry"
            assert tool.domain, f"{tool.id}: empty domain"
            assert re.match(rf"^{re.escape(tool.domain)}\..+$", tool.id), (
                f"{tool.id}: id must match ^{tool.domain}\\..+"
            )
            assert (tool.description or "").strip(), f"{tool.id}: empty description"
            assert (
                tool.required_capability is None
                or tool.required_capability in ALL_CAPABILITIES
            ), f"{tool.id}: unknown required_capability '{tool.required_capability}'"
            assert isinstance(tool.input_schema, dict) and tool.input_schema.get(
                "type"
            ) == "object", f"{tool.id}: input_schema must be a dict with type=object"
            assert isinstance(tool.is_mutation, bool), f"{tool.id}: is_mutation must be bool"


def test_get_tool_catalog_filters_forbidden_domain_tools(monkeypatch):
    """(b) A tool whose ``required_capability`` the user lacks is filtered out."""
    adapter = CarbonHostAdapter()
    monkeypatch.setattr(
        "accounts.capabilities.get_user_capabilities",
        lambda user: frozenset({"carbon:view_console"}),
    )
    catalog = adapter.get_tool_catalog(user=object(), scope=None)
    ids = {t.id for t in catalog.tools}

    # Allowed: requires carbon:view_console.
    assert "emissions.list_emission_factors" in ids
    assert "emissions.list_gwp_gases" in ids
    # Forbidden: requires carbon:view_calculations / dataschema:manage.
    assert "emissions.get_calculation_summary" not in ids
    assert "data_product.create_table" not in ids
    # The chat spine is never filtered.
    assert "search_knowledge" in ids


@pytest.mark.django_db
def test_star_capability_user_sees_all_domain_tools():
    """(c) A ``"*"`` (superuser) user sees every domain tool."""
    from accounts.models import User

    adapter = CarbonHostAdapter()
    superuser = User.objects.create_superuser(username="e2-star", password="secret123")
    catalog = adapter.get_tool_catalog(user=superuser, scope=None)
    catalog_ids = {t.id for t in catalog.tools}

    for tool in _all_domain_tools():
        assert tool.id in catalog_ids, f"missing {tool.id} for '*' user"


def test_none_capability_tool_is_always_included(monkeypatch):
    """(d) A ``required_capability=None`` tool is included even with no caps."""
    from ai.domain.emissions import EmissionsDomainAI

    adapter = CarbonHostAdapter()
    always_tool = ToolDef(
        id="emissions.always_available",
        description="Available regardless of the user's capabilities.",
        required_capability=None,
        is_mutation=False,
        domain="emissions",
        input_schema={"type": "object", "properties": {}},
    )
    monkeypatch.setattr(EmissionsDomainAI, "get_tools", lambda self: [always_tool])
    monkeypatch.setattr(
        "accounts.capabilities.get_user_capabilities",
        lambda user: frozenset(),
    )

    catalog = adapter.get_tool_catalog(user=object(), scope=None)
    ids = {t.id for t in catalog.tools}

    assert "emissions.always_available" in ids
    # The chat spine (also required_capability=None) stays present.
    assert "search_knowledge" in ids


def test_check_tool_catalog_command_reports_success():
    """The management command exits cleanly and prints the summary line."""
    from django.core.management import call_command

    out = StringIO()
    call_command("check_tool_catalog", stdout=out)
    assert "tools valid across" in out.getvalue()
