"""Phase I1-B — MCP-over-HTTP server endpoint tests.

Covers:

1. discovery — one server per app (``emissions`` + ``data_product``) for a
   user with carbon + catalog + dataschema view caps.
2. CBAC scoping — ``carbon:view_console`` only → ``emissions`` with exactly 2
   tools; no carbon caps → no ``emissions`` server.
3. no-capability → 403.
4. mutation → pending execution (RULE_21), never executed directly.
5. read → live data.
6. audit — every call writes ``ai.mcp_tool_call`` with source=mcp_external.
7. unknown domain/tool → 404; malformed body → 400.
"""

from __future__ import annotations

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from ai.models import AuditLog, ToolExecution
from ai.store import reset_store
from emissions.models import EmissionFactor

CARBON_VIEW_CAPS = {
    "carbon:view_console",
    "carbon:view_reporting_periods",
    "carbon:view_calculations",
    "carbon:view_dashboard",
}
DATA_PRODUCT_VIEW_CAPS = {"catalog:view", "dataschema:view"}


@pytest.fixture
def user(db):
    return User.objects.create_user(username="mcp-user", password="secret123")


@pytest.fixture
def client():
    return APIClient()


def _grant(monkeypatch, *caps: str):
    """Stub capability resolution to exactly the given capability keys."""
    monkeypatch.setattr(
        "accounts.capabilities.get_user_capabilities",
        lambda user: frozenset(caps),
    )


def _discovery(client):
    return client.get(reverse("mcp-discovery"))


def _tools(client, app_identifier):
    return client.get(reverse("mcp-tools", kwargs={"app_identifier": app_identifier}))


def _call(client, app_identifier, tool, arguments=None):
    return client.post(
        reverse("mcp-tool-call", kwargs={"app_identifier": app_identifier}),
        {"tool": tool, "arguments": arguments or {}},
        format="json",
    )


# ── 1. Discovery ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_discovery_one_server_per_app(monkeypatch, user, client):
    _grant(monkeypatch, *(CARBON_VIEW_CAPS | DATA_PRODUCT_VIEW_CAPS))
    client.force_authenticate(user=user)

    resp = _discovery(client)
    assert resp.status_code == 200
    servers = {s["id"]: s for s in resp.data["servers"]}
    assert set(servers) == {"emissions", "data_product"}

    assert servers["emissions"]["app_identifier"] == "emissions"
    assert servers["emissions"]["name"] == "Carbon Footprint"
    assert servers["emissions"]["tools_url"] == reverse(
        "mcp-tools", kwargs={"app_identifier": "emissions"}
    )
    # description falls back to the system_prompt_extension (non-empty).
    assert servers["emissions"]["description"]

    assert servers["data_product"]["app_identifier"] == "data_product"
    assert servers["data_product"]["name"] == "Data Products"
    assert servers["data_product"]["tools_url"] == reverse(
        "mcp-tools", kwargs={"app_identifier": "data_product"}
    )
    assert servers["data_product"]["description"]


# ── 2. CBAC scoping ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_cbac_scoping_view_console_two_tools(monkeypatch, user, client):
    _grant(monkeypatch, "carbon:view_console")
    client.force_authenticate(user=user)

    resp = _tools(client, "emissions")
    assert resp.status_code == 200
    names = {t["name"] for t in resp.data["tools"]}
    assert names == {"emissions.list_emission_factors", "emissions.list_gwp_gases"}


@pytest.mark.django_db
def test_cbac_scoping_no_carbon_no_emissions_server(monkeypatch, user, client):
    _grant(monkeypatch, "catalog:view")
    client.force_authenticate(user=user)

    resp = _discovery(client)
    assert resp.status_code == 200
    assert "emissions" not in {s["id"] for s in resp.data["servers"]}


# ── 3. No capability → 403 ───────────────────────────────────────────────


@pytest.mark.django_db
def test_no_capability_forbidden(monkeypatch, user, client):
    _grant(monkeypatch)  # no capabilities at all
    client.force_authenticate(user=user)

    resp = _call(client, "data_product", "data_product.create_table")
    assert resp.status_code == 403


# ── 4. Mutation → pending execution (RULE_21) ────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_mutation_stages_pending_execution(monkeypatch, user, client):
    _grant(monkeypatch, "dataschema:manage")
    client.force_authenticate(user=user)

    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        resp = _call(
            client,
            "data_product",
            "data_product.create_table",
            {"title": "MCP Table"},
        )
        reset_store()

    assert resp.status_code == 200
    assert resp.data["requires_confirmation"] is True
    execution_id = resp.data["execution_id"]
    assert execution_id

    row = ToolExecution.objects.get(pk=execution_id)
    assert row.status == "pending_confirmation"
    assert row.tool_name == "mcp:data_product.create_table"
    assert row.host_user_id == str(user.pk)


# ── 5. Read returns live data ────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_read_returns_live_data(monkeypatch, user, client):
    _grant(monkeypatch, "carbon:view_console")
    EmissionFactor.objects.create(
        code="EG_TEST_MCP",
        name="MCP Grid Factor",
        category="electricity",
        scope=2,
        factor_value=0.5,
        factor_unit="kg CO2e",
        activity_unit="kWh",
        country="Egypt",
        source="test",
        tags=[],
        valid_from="2024-01-01",
        is_active=True,
    )
    client.force_authenticate(user=user)

    resp = _call(client, "emissions", "emissions.list_emission_factors")
    assert resp.status_code == 200
    assert "result" in resp.data

    result = resp.data["result"]
    assert result["status_code"] == 200
    codes = {f["code"] for f in result["data"]["results"]}
    assert "EG_TEST_MCP" in codes


# ── 6. Audit trail ───────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_audit_row_written(monkeypatch, user, client):
    _grant(monkeypatch, "carbon:view_console")
    client.force_authenticate(user=user)

    resp = _call(client, "emissions", "emissions.list_emission_factors")
    assert resp.status_code == 200

    rows = list(AuditLog.objects.filter(action="ai.mcp_tool_call"))
    assert len(rows) == 1
    assert rows[0].detail["source"] == "mcp_external"
    assert rows[0].detail["tool"] == "emissions.list_emission_factors"
    assert rows[0].detail["app_identifier"] == "emissions"


# ── 7. Unknown domain/tool → 404; malformed body → 400 ───────────────────


@pytest.mark.django_db
def test_unknown_domain_and_tool_404(monkeypatch, user, client):
    _grant(monkeypatch, "carbon:view_console")
    client.force_authenticate(user=user)

    assert _tools(client, "does_not_exist").status_code == 404
    assert _call(client, "emissions", "emissions.no_such_tool").status_code == 404
    assert _call(client, "does_not_exist", "does_not_exist.foo").status_code == 404


@pytest.mark.django_db
def test_malformed_body_400(monkeypatch, user, client):
    _grant(monkeypatch, "carbon:view_console")
    client.force_authenticate(user=user)

    url = reverse("mcp-tool-call", kwargs={"app_identifier": "emissions"})

    # Missing "tool" key.
    assert client.post(url, {"arguments": {}}, format="json").status_code == 400

    # Non-object body.
    assert client.post(url, [1, 2, 3], format="json").status_code == 400
