"""Water domain (GRI 303 vocabulary) tests.

Covers:
  - water domain registration + lookup via ai.domain_protocol
  - WaterDomainAI DomainContext shape (knowledge + config)
  - prompt-prefix injection for the water app_identifier
  - no-crash paths for unknown/unregistered domains
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ai.domain.water import WaterDomainAI
from ai.domain_protocol import (
    get_domain,
    has_domain,
    list_domains,
    register_domain,
)
from ai.intelligence import CarbonIntelligence
from backend.ai.protocol import ChatResponse, Scope


# ── Registration & lookup ─────────────────────────────────────────────────


def test_water_domain_registered():
    assert has_domain("water") is True


def test_get_domain_returns_water_class():
    assert get_domain("water") is WaterDomainAI


def test_list_domains_includes_water():
    assert "water" in list_domains()


def test_duplicate_water_registration_raises():
    with pytest.raises(ValueError):
        register_domain("water", WaterDomainAI)


# ── DomainContext content ─────────────────────────────────────────────────


def test_app_identifier_and_display_name():
    assert WaterDomainAI.app_identifier == "water"
    assert WaterDomainAI.app_display_name == "Water Management"


def test_domain_context_knowledge_shape():
    ctx = WaterDomainAI().get_domain_context()
    knowledge = ctx.domain_knowledge
    assert knowledge["protocol"] == "GRI 303: Water and Effluents 2018"
    assert set(knowledge["scopes"].keys()) == {
        "withdrawal",
        "consumption",
        "discharge",
        "recycled",
    }
    assert knowledge["units"] == ["m3", "liters", "ML"]


def test_domain_context_config_shape():
    ctx = WaterDomainAI().get_domain_context()
    config = ctx.domain_config
    assert config["default_unit"] == "m3"
    assert config["key_tables"] == ["monthly_water", "monthly_chilled_water"]
    assert config["measurement_methods"] == [
        "metered",
        "estimated",
        "vendor-invoice",
    ]


# ── Prompt injection ──────────────────────────────────────────────────────


def _make_ci() -> CarbonIntelligence:
    ci = CarbonIntelligence()
    ci._provider = MagicMock()
    ci._provider.provider_name = "dummy"
    ci._provider.chat.return_value = ChatResponse(
        status="completed", content="ok"
    )
    return ci


def test_prepend_domain_context_water():
    ci = _make_ci()
    result = ci._prepend_domain_context(
        Scope(app_identifier="water"), "hello"
    )
    assert result.startswith("[Domain: water]")
    assert "GRI 303: Water and Effluents 2018" in result
    assert result.endswith("hello")


def test_domain_context_prompt_prefix_renderer():
    from ai.intelligence import _domain_context_prompt_prefix

    ctx = WaterDomainAI().get_domain_context()
    prefix = _domain_context_prompt_prefix(ctx)
    assert prefix.startswith("[Domain: water]")
    assert "withdrawal" in prefix
    assert "Units: m3, liters, ML" in prefix
    assert "default_unit: m3" in prefix
    assert "measurement_methods: metered, estimated, vendor-invoice" in prefix
