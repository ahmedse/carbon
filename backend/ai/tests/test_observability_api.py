"""Pulse observability read API tests (TASKS-PULSE-VENDOR-FRONTEND-PHASE-B).

Tests:
  * inventory/ requires auth and returns all 14 panels (key/label/count/models)
  * data/<key>/ 404s on unknown panels, merges + tags rows for known ones
  * Instance.host_api_token never leaks (field excluded + JSON redaction)
  * archetypes/ lists the vendored engine bundles
  * inventory/ rejects write methods with 405 (structural read-only)
"""
import json

import pytest

from ai.models.core import Instance, LLMCallLog, Run
from ai.observability_api import PANEL_REGISTRY
from ai.tests.test_plans import _make_plan, _make_step

BASE = "/carbon-api/ai/pulse"


@pytest.fixture
def user(db):
    from accounts.models import User

    user = User.objects.create_user(username="ai-obs", password="secret123")
    user.is_superuser = True
    user.is_staff = True
    user.save()
    return user


@pytest.fixture
def auth_client(api_client, get_token_for_user, user):
    """DRF client authenticated with a real JWT (mirrors conftest pattern)."""
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")
    return api_client


@pytest.mark.django_db
def test_inventory_requires_auth(api_client):
    assert api_client.get(f"{BASE}/inventory/").status_code == 401
    assert api_client.get(f"{BASE}/data/knowledge/").status_code == 401
    assert api_client.get(f"{BASE}/archetypes/").status_code == 401


@pytest.mark.django_db
def test_inventory_returns_all_panels(auth_client):
    resp = auth_client.get(f"{BASE}/inventory/")
    assert resp.status_code == 200
    panels = resp.json()["panels"]
    assert len(panels) == 14
    assert {panel["key"] for panel in panels} == set(PANEL_REGISTRY.keys())
    for panel in panels:
        assert "key" in panel and "label" in panel
        assert "count" in panel and "models" in panel
        assert isinstance(panel["models"], list)


@pytest.mark.django_db
def test_data_unknown_panel_404(auth_client):
    resp = auth_client.get(f"{BASE}/data/nope/")
    assert resp.status_code == 404
    assert resp.json()["error"] == "unknown_panel"


@pytest.mark.django_db
def test_data_logs_merges_and_tags(auth_client):
    LLMCallLog.objects.create(
        instance_id="inst-1", conversation_id="conv-1", model="gpt-test"
    )
    resp = auth_client.get(f"{BASE}/data/logs/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["key"] == "logs"
    assert body["count"] >= 1
    assert body["results"]
    assert all("_type" in row for row in body["results"])
    assert any(
        row["_type"] == "LLMCallLog" and row["model"] == "gpt-test"
        for row in body["results"]
    )


@pytest.mark.django_db
def test_instance_token_redacted(auth_client):
    Instance.objects.create(
        name="inst-token",
        display_name="Token Instance",
        host_db_url="postgres://db",
        host_api_url="https://host",
        host_api_token="sekrit",
        config={"endpoint": "https://host", "api_token": "sekrit-json"},
    )
    resp = auth_client.get(f"{BASE}/data/mcp/")
    assert resp.status_code == 200
    rows = resp.json()["results"]
    assert rows
    row = rows[0]
    assert "host_api_token" not in row  # excluded at the serializer field level
    assert "sekrit" not in json.dumps(row)  # nothing leaked, incl. nested JSON


@pytest.mark.django_db
def test_archetypes_lists_bundles(auth_client):
    resp = auth_client.get(f"{BASE}/archetypes/")
    assert resp.status_code == 200
    bundles = resp.json()["bundles"]
    names = {bundle["name"] for bundle in bundles}
    assert {"devops-workspace", "test-lab", "twin-mind"} <= names
    assert all(bundle["kind"] == "bundle" for bundle in bundles)


@pytest.mark.django_db
def test_read_only_no_write_methods(auth_client):
    assert auth_client.post(f"{BASE}/inventory/", {}).status_code == 405
    assert auth_client.put(f"{BASE}/inventory/", {}).status_code == 405
    assert auth_client.delete(f"{BASE}/inventory/").status_code == 405


# ── Run rollups (Phase W4-E) ──────────────────────────────────────────────


@pytest.mark.django_db
def test_rollups_requires_auth(api_client):
    assert api_client.get(f"{BASE}/rollups/").status_code == 401


@pytest.mark.django_db
def test_rollups_totals_and_per_run_shape(auth_client, user):
    plan_a = _make_plan(user, status="completed")
    plan_b = _make_plan(user, status="running")
    _make_plan(user, status="paused")
    _make_plan(user, status="failed")

    Run.objects.filter(id=plan_a.id).update(
        total_llm_calls=5, total_latency_ms=123.0
    )
    Run.objects.filter(id=plan_b.id).update(
        total_llm_calls=7, total_latency_ms=45.0
    )

    _make_step(plan_a, step_index=0, status="completed")
    _make_step(plan_a, step_index=1, status="awaiting_approval", token="tok-1")
    _make_step(plan_b, step_index=0, status="awaiting_approval", token="tok-2")
    _make_step(plan_b, step_index=1, status="awaiting_approval", token="tok-3")

    resp = auth_client.get(f"{BASE}/rollups/")
    assert resp.status_code == 200
    body = resp.json()

    totals = body["totals"]
    assert totals["runs"] == 4
    assert totals["total_llm_calls"] == 12
    assert totals["confirmations_required"] == 3
    assert totals["total_latency_ms"] == 168.0
    assert totals["completed"] == 1
    assert totals["failed"] == 1
    assert totals["paused"] == 1
    assert totals["running"] == 1

    per_run = body["per_run"]
    assert len(per_run) == 4
    by_id = {row["run_id"]: row for row in per_run}
    row_a = by_id[plan_a.id]
    assert row_a["status"] == "completed"
    assert row_a["total_llm_calls"] == 5
    assert row_a["latency_ms"] == 123.0
    assert row_a["confirmations_required"] == 1
    assert row_a["step_count"] == 2
    assert "completed_at" in row_a


@pytest.mark.django_db
def test_rollups_ownership_scoping(
    api_client, create_user, create_scoped_role, get_token_for_user
):
    """An org-scoped admin (admins_group @ non-null org) only sees their own runs."""
    from mdm.models import OrgUnit

    org = OrgUnit.objects.create(
        name="Rollup Scope Org", slug="rollup-scope-org",
        code="SCOPE", org_type="division",
    )
    admin = create_user("rollup-scoped-admin")
    create_scoped_role(admin, "admins_group", org_unit=org, module=None)
    other = create_user("rollup-other")

    mine = _make_plan(admin, status="completed")
    _make_plan(other, status="running")

    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(admin)}"
    )
    resp = api_client.get(f"{BASE}/rollups/")
    assert resp.status_code == 200
    body = resp.json()

    run_ids = {row["run_id"] for row in body["per_run"]}
    assert mine.id in run_ids
    assert body["totals"]["runs"] == 1
