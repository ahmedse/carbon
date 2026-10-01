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
    pack_id_for_brand,
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


def test_pack_id_for_brand_uses_pack_not_slug():
    assert pack_id_for_brand("aastmt") == "carbon"
    assert pack_id_for_brand("nibras") == "nibras"
    assert pack_id_for_brand("eduos") == "eduos"


def test_aastmt_default_pack_is_carbon_not_aast_med():
    with override_settings(DJANGO_BRAND="aastmt"):
        assert resolve_instance_id() == "carbon"
        assert resolve_default_app_identifier() == "carbon"
        assert pack_id_for_brand("aastmt") == "carbon"


def test_aast_med_is_not_a_brand():
    with override_settings(DJANGO_BRAND="aast-med"):
        assert active_brand() == "aastmt"
        assert resolve_instance_id() == "carbon"


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
    assert default_app_for_instance("aast-med") == "moodle"
    assert default_app_for_instance("unknown") == "carbon"


# ── Nibras instance config isolation ────────────────────────────────────


def test_nibras_instance_config_is_people_scoped_and_has_no_api_catalog():
    from ai.engine_runtime import _instance_config

    config = _instance_config("nibras", None)

    assert config["instance_id"] == "nibras"
    assert config["app_identifier"] == "people"
    assert "Nibras" in config["display_name"]
    # Grounded-reads: People domain exposes read-only host endpoints.
    catalog_names = {e["name"] for e in config["api_catalog"]}
    assert "list_employees" in catalog_names
    assert "list_payroll_runs" in catalog_names
    assert "list_payslip_lines" in catalog_names
    # Mutations are present but gated behind confirmation.
    mutations = {e["name"] for e in config["api_catalog"] if e.get("requires_confirmation")}
    assert "commit_payroll_run" in mutations
    # No Carbon-domain endpoints must leak into this catalog.
    assert not any("emission" in n or "dq_rule" in n or "chairman" in n for n in catalog_names)
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


def test_unknown_instance_does_not_load_carbon_config():
    from ai.engine_runtime import _instance_config

    config = _instance_config("no-such-instance", None)
    assert config["instance_id"] == "no-such-instance"
    assert config.get("pulse_off") is True
    assert config.get("api_catalog") == []
    names = {e.get("name") for e in (config.get("api_catalog") or [])}
    assert "list_emission_factors" not in names
    assert "get_chairman_overview" not in names
