"""Platform bind / jail: identity, no carbon fallback, app filter, containment."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

from ai.models.control_state import (
    CONTAINMENT_FULL_STOP,
    CONTAINMENT_TOOL_FREEZE,
    get_or_create_control_state,
)
from ai.platform_bind import (
    PULSE_OFF_NO_PACK,
    PULSE_OFF_STOPPED,
    TOOL_FREEZE_HOST,
    allowed_apps,
    bind_health,
    has_domain_pack,
    pack_id_for_brand,
    redis_db_from_url,
    turn_gate,
)


User = get_user_model()


def test_has_domain_pack_known_and_missing():
    assert has_domain_pack("nibras") is True
    assert has_domain_pack("carbon") is True
    assert has_domain_pack("medos") is False
    assert has_domain_pack("tectona") is False
    assert has_domain_pack("no-such-instance") is False


def test_redis_db_from_url():
    assert redis_db_from_url("redis://localhost:6379/1") == 1
    assert redis_db_from_url("redis://localhost:6379/0") == 0


@pytest.mark.django_db
def test_medos_and_tectona_do_not_load_carbon_tools():
    from ai.engine_runtime import _instance_config

    for instance_id in ("medos", "tectona", "unknown-pack"):
        config = _instance_config(instance_id, None)
        names = {e.get("name") for e in (config.get("api_catalog") or [])}
        assert config.get("pulse_off") is True
        assert names == set()
        assert "list_emission_factors" not in names
        assert "list_employees" not in names


@pytest.mark.django_db
@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_nibras_catalog_has_no_carbon_names():
    from ai.engine_runtime import _instance_config

    names = {e.get("name") for e in (_instance_config("nibras", None).get("api_catalog") or [])}
    assert "list_emission_factors" not in names
    assert "get_chairman_overview" not in names
    assert "list_dq_rules" not in names


def test_nibras_catalog_rows_declare_app():
    from ai.engine.core.archetypes import load_instance_config

    cfg = load_instance_config("nibras")
    catalog = cfg.get("api_catalog") or []
    assert catalog
    assert all(e.get("app") for e in catalog)
    by_name = {e["name"]: e["app"] for e in catalog}
    assert by_name["get_my_profile"] == "my"
    assert by_name["list_my_direct_reports"] == "team"
    assert by_name["list_employees"] == "people"
    assert by_name["list_payroll_runs"] == "people"


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_people_pulse_off_drops_host_rows():
    from ai.engine_runtime import _instance_config
    from ai.models.app_enablement import PulseAppEnablement

    PulseAppEnablement.objects.create(
        instance_id="nibras", app_slug="people", enabled=False
    )
    config = _instance_config("nibras", None)
    names = {e["name"] for e in config["api_catalog"]}
    assert "list_employees" not in names
    assert "list_payroll_runs" not in names
    assert "get_my_profile" not in names


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_my_off_keeps_hr_rows():
    from ai.engine_runtime import _instance_config
    from ai.models.app_enablement import PulseAppEnablement

    PulseAppEnablement.objects.create(instance_id="nibras", app_slug="my", enabled=False)
    config = _instance_config("nibras", None)
    names = {e["name"] for e in config["api_catalog"]}
    assert "get_my_profile" not in names
    assert "list_my_leave" not in names
    assert "list_employees" in names
    assert "list_payroll_runs" in names


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_full_stop_refuses_chat_without_model():
    from ai.engine_runtime import dispatch_task

    state = get_or_create_control_state("nibras")
    state.containment_level = CONTAINMENT_FULL_STOP
    state.save()
    data = dispatch_task("chat", {"message": "hello"}, instance_id="nibras")
    assert data["status"] == "completed"
    assert data["result"]["llm_calls"] == 0
    assert data["result"]["content"] == PULSE_OFF_STOPPED


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_missing_pack_refuses_with_pulse_off_sentence():
    from ai.engine_runtime import dispatch_task

    data = dispatch_task("chat", {"message": "hello"}, instance_id="medos")
    assert data["result"]["llm_calls"] == 0
    assert data["result"]["content"] == PULSE_OFF_NO_PACK


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_tool_freeze_blocks_host_call():
    from ai.host_executor import CarbonHostExecutor

    state = get_or_create_control_state("nibras")
    state.containment_level = CONTAINMENT_TOOL_FREEZE
    state.save()
    executor = CarbonHostExecutor(
        db=None,
        instance_config={
            "tool_freeze": True,
            "api_catalog": [{"name": "list_employees", "app": "people"}],
        },
        host_user_id="1",
    )
    result = __import__("asyncio").run(
        executor.call_api_direct("GET", "/carbon-api/people/employees/")
    )
    assert result["error"] == TOOL_FREEZE_HOST


@pytest.mark.django_db
def test_bind_health_reports_process_brand():
    payload = bind_health()
    assert "process_brand" in payload
    assert "files_brand" in payload
    assert "pack" in payload
    assert "files_match_process" in payload
    assert payload["pack"] == pack_id_for_brand(payload["process_brand"])
    assert payload["jwt_instance"] == payload["pack"]


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="aastmt")
def test_jwt_and_health_use_pack_id_not_brand_slug(monkeypatch):
    monkeypatch.setenv("PULSE_INSTANCE_ID", "aastmt")
    from accounts.services import PulseService
    from ai.engine.core.config import get_settings

    get_settings.cache_clear()
    assert PulseService.PULSE_INSTANCE_ID == "carbon"
    payload = bind_health()
    assert payload["pack"] == "carbon"
    assert payload["jwt_instance"] == "carbon"
    assert payload["process_brand"] == "aastmt"
    assert get_settings().PULSE_INSTANCE_ID == "aastmt"


def test_get_settings_pack_id_follows_env_without_cache_clear(monkeypatch):
    from ai.engine.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("PULSE_INSTANCE_ID", "nibras")
    assert get_settings().PULSE_INSTANCE_ID == "nibras"
    monkeypatch.setenv("PULSE_INSTANCE_ID", "carbon")
    assert get_settings().PULSE_INSTANCE_ID == "carbon"
    get_settings.cache_clear()


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_people_off_executor_refuses_filtered_names():
    from ai.engine_runtime import _instance_config
    from ai.host_executor import CarbonHostExecutor
    from ai.models.app_enablement import PulseAppEnablement

    PulseAppEnablement.objects.create(
        instance_id="nibras", app_slug="people", enabled=False
    )
    cfg = _instance_config("nibras", None)
    names = {e["name"] for e in cfg["api_catalog"]}
    assert names == set()
    executor = CarbonHostExecutor(db=None, instance_config=cfg, host_user_id="1")
    result = __import__("asyncio").run(
        executor.execute_host_api_via_boundary(
            effect=None,
            api_name="list_employees",
            method="GET",
            path="/carbon-api/people/employees/",
        )
    )
    assert result["status"] == "refused"
    assert "list_employees" in result["error"]


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_nibras_executor_refuses_carbon_catalog_name():
    from ai.engine_runtime import _instance_config
    from ai.host_executor import CarbonHostExecutor

    cfg = _instance_config("nibras", None)
    executor = CarbonHostExecutor(db=None, instance_config=cfg, host_user_id="1")
    result = __import__("asyncio").run(
        executor.execute_host_api_via_boundary(
            effect=None,
            api_name="list_emission_factors",
            method="GET",
            path="/carbon-api/emissions/factors/",
        )
    )
    assert result["status"] == "refused"
    assert "list_emission_factors" in result["error"]


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="aastmt")
def test_carbon_executor_refuses_people_catalog_name():
    from ai.engine_runtime import _instance_config
    from ai.host_executor import CarbonHostExecutor

    cfg = _instance_config("carbon", None)
    executor = CarbonHostExecutor(db=None, instance_config=cfg, host_user_id="1")
    result = __import__("asyncio").run(
        executor.execute_host_api_via_boundary(
            effect=None,
            api_name="list_employees",
            method="GET",
            path="/carbon-api/people/employees/",
        )
    )
    assert result["status"] == "refused"
    assert "list_employees" in result["error"]


@pytest.mark.django_db
def test_bind_api_view_console_cannot_patch():
    user = User.objects.create_user(username="viewer", password="x")
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.patch(
        "/carbon-api/ai/pulse/control/bind/",
        {"pulse_enabled": False},
        format="json",
    )
    assert resp.status_code in (403, 401)


@pytest.mark.django_db
def test_bind_api_manage_can_toggle(admin_client_factory=None):
    user = User.objects.create_superuser(
        username="bind_admin", email="bind@example.com", password="x"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    get = client.get("/carbon-api/ai/pulse/control/bind/")
    assert get.status_code == 200
    body = get.json()
    assert "health" in body
    assert "apps" in body
    assert "extra_pack_apps" in body
    assert "pulse_enabled" in body
    assert "DJANGO_BRAND" not in str(body.get("apps"))
    assert "moodle" not in {row["slug"] for row in body["apps"]}
    extra = body["extra_pack_apps"]
    assert any(g.get("pack") == "aast-med" for g in extra)
    med_apps = next(g["apps"] for g in extra if g.get("pack") == "aast-med")
    assert "moodle" in {row["slug"] for row in med_apps}
    resp = client.patch(
        "/carbon-api/ai/pulse/control/bind/",
        {"pulse_enabled": False},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["pulse_enabled"] is False
    gate = turn_gate(body["health"]["pack"])
    assert gate.refuse_before_model is True


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_allowed_apps_intersection_defaults_on():
    apps = allowed_apps(
        "nibras",
        catalog=[
            {"name": "list_employees", "app": "people"},
            {"name": "get_my_profile", "app": "my"},
        ],
        brand="nibras",
    )
    assert "people" in apps
    assert "my" in apps


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="aastmt")
def test_carbon_catalog_has_no_moodle_rows():
    from ai.engine_runtime import _instance_config

    config = _instance_config("carbon", None)
    catalog = config.get("api_catalog") or []
    paths = " ".join(str(e.get("path") or "") for e in catalog)
    names = {e.get("name") for e in catalog}
    apps = {e.get("app") for e in catalog}
    assert "moodle://" not in paths
    assert "moodle" not in apps
    assert "get_course" not in names
    assert "list_course_sections" not in names
    assert config["instance_id"] == "carbon"
    assert config["app_identifier"] == "carbon"


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="aastmt")
def test_aast_med_catalog_has_no_carbon_people_dq_emissions_names():
    from ai.engine_runtime import _instance_config

    config = _instance_config("aast-med", None)
    names = {e.get("name") for e in (config.get("api_catalog") or [])}
    paths = " ".join(str(e.get("path") or "") for e in (config.get("api_catalog") or []))
    assert config["instance_id"] == "aast-med"
    assert config["app_identifier"] == "moodle"
    assert config.get("inventory") == ""
    assert "list_employees" not in names
    assert "list_dq_rules" not in names
    assert "list_emission_factors" not in names
    assert "get_chairman_overview" not in names
    assert "moodle://" in paths
    assert names <= {"get_course", "list_course_sections"}


_LEFTOVER_PAGE = (
    "Moodle audience: staff.\n"
    "Open course NMD3101: priniciples of infection (NMD3101) id=25.\n"
    "Cite only these sections. If a fact is not listed, say it is not in this course."
)


@override_settings(DJANGO_BRAND="aastmt")
def test_moodle_provider_binds_aast_med_only_on_embed_host():
    from ai.protocol import ChatRequest, Scope
    from ai.providers.pulse import PulseProvider

    provider = PulseProvider()
    leftover = {"app_identifier": "moodle", "page_context": _LEFTOVER_PAGE}
    assert provider._instance_for(leftover) == "carbon"
    assert provider._instance_for({"app_identifier": "moodle"}) == "carbon"
    assert provider._instance_for({}) == "carbon"
    assert provider._instance_for({"app_identifier": "carbon"}) == "carbon"
    assert provider._instance_for({
        "app_identifier": "moodle",
        "host_user_id": "moodle:7",
        "page_context": _LEFTOVER_PAGE,
    }) == "aast-med"
    assert provider._instance_for({
        "app_identifier": "moodle",
        "host_user_id": "moodle-7",
    }) == "aast-med"

    dropped = provider._chat_payload(ChatRequest(
        message="are you expert in carbon emissions?",
        scope=Scope(app_identifier="moodle"),
        page_context=_LEFTOVER_PAGE,
    ))
    assert dropped.get("app_identifier") != "moodle"
    assert not dropped.get("page_context")
    assert provider._instance_for(dropped) == "carbon"

    embed = provider._chat_payload(ChatRequest(
        message="hi",
        scope=Scope(app_identifier="moodle", user_identifier="moodle-7"),
        page_context=_LEFTOVER_PAGE,
    ))
    assert embed["app_identifier"] == "moodle"
    assert embed["page_context"] == _LEFTOVER_PAGE
    assert provider._instance_for(embed) == "aast-med"


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="aastmt")
def test_moodle_embed_user_pk_binds_aast_med_carbon_pk_does_not():
    from ai.providers.pulse import PulseProvider

    embed = User.objects.create_user(username="moodle-7", password="x")
    carbon = User.objects.create_user(username="ahmed_bind", password="x")
    provider = PulseProvider()
    assert provider._instance_for({
        "app_identifier": "moodle",
        "host_user_id": str(embed.pk),
        "page_context": _LEFTOVER_PAGE,
    }) == "aast-med"
    assert provider._instance_for({
        "app_identifier": "moodle",
        "host_user_id": str(carbon.pk),
        "page_context": _LEFTOVER_PAGE,
    }) == "carbon"


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_nibras_pulse_never_binds_moodle_pack_or_page_block():
    from ai.engine_runtime import _instance_config, _sanitize_host_page_context
    from ai.moodle_host import conversation_app_for_user, page_context_for_user
    from ai.providers.pulse import PulseProvider

    leftover = _LEFTOVER_PAGE
    provider = PulseProvider()
    assert provider._instance_for({}) == "nibras"
    assert provider._instance_for({"app_identifier": "moodle"}) == "nibras"
    assert provider._instance_for({
        "app_identifier": "moodle",
        "page_context": leftover,
        "host_user_id": "moodle:7",
    }) == "nibras"
    config = _instance_config("nibras", None)
    persona = str(config.get("persona") or "")
    assert "Moodle page" not in persona
    assert "page block" not in persona.casefold()
    assert "assistant on this Moodle" not in persona
    assert "This is not in this course" not in persona
    assert _sanitize_host_page_context("nibras", leftover) == ""
    assert _sanitize_host_page_context("aast-med", leftover) == leftover
    carbon_user = type("U", (), {"username": "ahmed"})()
    assert conversation_app_for_user(carbon_user, "moodle") is None
    assert page_context_for_user(carbon_user, leftover, leftover) == ""
    embed_user = type("U", (), {"username": "moodle-7"})()
    assert conversation_app_for_user(embed_user, "moodle") == "moodle"
    assert page_context_for_user(embed_user, leftover, "") == leftover
    guard = _instance_config("nibras", None)
    from ai.engine_runtime import _check_topic_guard

    refusal = _check_topic_guard(guard, "are you expert in carbon emissions?")
    assert refusal
    assert "Moodle" not in refusal
    assert "page block" not in refusal.casefold()
    assert "Moodle page" not in refusal
    assert "This is not in this course" not in refusal
    assert "Nibras People & Payroll assistant" in refusal


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="aastmt")
def test_extra_packs_do_not_fold_moodle_into_carbon_bind_apps():
    from ai.engine.core.archetypes import load_instance_config
    from ai.platform_bind import bind_apps_payload, extra_packs_for_brand

    assert extra_packs_for_brand("aastmt") == ("aast-med",)
    assert extra_packs_for_brand("nibras") == ()
    carbon = bind_apps_payload("carbon", load_instance_config("carbon").get("api_catalog") or [])
    medicine = bind_apps_payload(
        "aast-med", load_instance_config("aast-med").get("api_catalog") or []
    )
    assert "moodle" not in {row["slug"] for row in carbon}
    assert "moodle" in {row["slug"] for row in medicine}
    assert "carbon" not in {row["slug"] for row in medicine}


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="aastmt")
def test_allowed_apps_does_not_grant_moodle_to_carbon():
    apps = allowed_apps(
        "carbon",
        catalog=[
            {"name": "list_emission_factors", "app": "carbon"},
            {"name": "get_course", "app": "moodle"},
        ],
        brand="aastmt",
    )
    assert "carbon" in apps
    assert "moodle" not in apps
