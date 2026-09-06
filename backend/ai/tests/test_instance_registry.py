"""Tests for brand -> instance/app resolution and Nibras isolation.

These lock in the scope/isolation contract added when Nibras (People &
Payroll) was introduced: every engine partition, default app, persona, and
host API catalog resolves from the active Django brand, and the Nibras
instance can never expose Carbon-domain endpoints or inject Carbon context.
"""

import pytest
from django.test import override_settings

from ai.instance_registry import (
    active_brand,
    default_app_for_instance,
    resolve_default_app_identifier,
    resolve_instance_id,
)


# ── Brand -> instance/app mapping ───────────────────────────────────────


@pytest.mark.parametrize(
    "brand,instance_id,app_identifier",
    [
        ("aastmt", "carbon", "carbon"),
        ("nibras", "nibras", "people"),
        ("medos", "medos", "medos"),
        ("tectona", "tectona", "healthy"),
    ],
)
def test_brand_maps_to_instance_and_default_app(brand, instance_id, app_identifier):
    with override_settings(DJANGO_BRAND=brand):
        assert active_brand() == brand
        assert resolve_instance_id() == instance_id
        assert resolve_default_app_identifier() == app_identifier


def test_unknown_brand_falls_back_to_carbon():
    with override_settings(DJANGO_BRAND="some-unknown-brand"):
        assert active_brand() == "aastmt"
        assert resolve_instance_id() == "carbon"
        assert resolve_default_app_identifier() == "carbon"


# ── Instance-scoped default app (independent of brand) ──────────────────


def test_default_app_for_instance_is_instance_scoped():
    # A Carbon-instance turn defaults to the carbon app even on a Nibras
    # deployment, and vice-versa — so a cross-instance dispatch can never
    # silently adopt the wrong domain.
    assert default_app_for_instance("carbon") == "carbon"
    assert default_app_for_instance("nibras") == "people"
    assert default_app_for_instance("medos") == "medos"
    assert default_app_for_instance("tectona") == "healthy"
    assert default_app_for_instance("unknown") == "carbon"


# ── Nibras instance config isolation ────────────────────────────────────


def test_nibras_instance_config_is_people_scoped_and_has_no_api_catalog():
    from ai.engine_runtime import _instance_config

    config = _instance_config("nibras", None)

    assert config["instance_id"] == "nibras"
    assert config["app_identifier"] == "people"
    assert "Nibras" in config["display_name"]
    # Advisory-only: the People domain owns no host data tools, so the
    # LLM-facing catalog must be empty (no Carbon/other-domain endpoints).
    assert config["api_catalog"] == []
    # domain_topics should cover payroll and people domain keywords.
    topics_str = " ".join(config["domain_topics"]).lower()
    assert "payroll" in topics_str
    assert "gosi" in topics_str
    # The persona explicitly guards against revealing Carbon-domain data.
    persona = config["persona"].lower()
    assert "carbon emissions" in persona
    assert "data quality" in persona


def test_carbon_instance_config_defaults_to_carbon_app_even_on_nibras_brand():
    from ai.engine_runtime import _instance_config

    # Even when the deployment brand is Nibras, an explicit Carbon-instance
    # config must default to the carbon app (never "people").
    with override_settings(DJANGO_BRAND="nibras"):
        config = _instance_config("carbon", None)
    assert config["instance_id"] == "carbon"
    assert config["app_identifier"] == "carbon"


def test_unknown_instance_falls_back_to_carbon_config():
    from ai.engine_runtime import _instance_config

    config = _instance_config("no-such-instance", None)
    # Falls back to the carbon config file, but keeps the requested id.
    assert config["instance_id"] == "no-such-instance"
    assert config["display_name"]
