"""Resilience: period aliases + JSONField coerce (false-complete / id invent)."""
from __future__ import annotations

import pytest

from ai.engine.agent.period_alias import item_matches_period, parse_period_alias
from ai.engine.cognition.plan.loop import _coerce_json_field


@pytest.mark.parametrize(
    "token,expected",
    [
        ("demo-oct-2026", (2026, 10)),
        ("oct-2026", (2026, 10)),
        ("October-2026", (2026, 10)),
        ("2026-10", (2026, 10)),
        ("2026/10", (2026, 10)),
        ("not-a-period", None),
        ("", None),
    ],
)
def test_parse_period_alias(token, expected):
    assert parse_period_alias(token) == expected


def test_item_matches_period():
    assert item_matches_period({"period_start": "2026-10-01"}, 2026, 10) is True
    assert item_matches_period({"period_start": "2026-09-01"}, 2026, 10) is False


def test_coerce_json_field_accepts_dict_and_string():
    assert _coerce_json_field({"a": 1}, default={}) == {"a": 1}
    assert _coerce_json_field('{"a": 1}', default={}) == {"a": 1}
    assert _coerce_json_field(None, default=[]) == []
    assert _coerce_json_field("", default=[]) == []


@pytest.mark.asyncio
async def test_resolve_slug_payroll_period_alias():
    """Invented demo-oct-2026 must resolve to the Oct-2026 payroll run id."""
    from ai.engine.agent.tools import _resolve_slug_to_id

    class _Ex:
        instance_config = {
            "tools": {
                "slug_resolution": [
                    {
                        "detail_endpoint": "compute_payroll_run",
                        "list_endpoint": "list_payroll_runs",
                        "match_fields": ["period_start"],
                    }
                ]
            }
        }

        def get_catalog_entry(self, name):
            if name == "list_payroll_runs":
                return {"path": "/carbon-api/people/payroll-runs/", "method": "GET"}
            return None

        async def call_api_direct(self, method, path):
            return {
                "status_code": 200,
                "data": {
                    "results": [
                        {"id": 42, "period_start": "2026-10-01", "status": "draft"},
                        {"id": 7, "period_start": "2026-09-01", "status": "committed"},
                    ]
                },
            }

    out = await _resolve_slug_to_id(
        _Ex(), "compute_payroll_run", {"id": "demo-oct-2026"},
    )
    assert out["id"] == 42


@pytest.mark.asyncio
async def test_call_host_api_self_heals_invented_id_and_retries():
    """On Field 'id' expected a number — resolve alias and retry once.

    Simulates first list miss (no period match) so the invented id reaches
    the host, then a second list hit during self-heal rewrites the path.
    """
    from ai.engine.agent import tools as tools_mod

    calls: list[str] = []
    list_hits = {"n": 0}

    class _Ex:
        instance_config = {"tools": {"slug_resolution": [
            {
                "detail_endpoint": "get_payroll_run",
                "list_endpoint": "list_payroll_runs",
                "match_fields": ["period_start"],
            }
        ]}}
        host_user_id = "1"
        user_token = "test-token"

        def get_catalog_entry(self, name):
            if name == "get_payroll_run":
                return {
                    "method": "GET",
                    "path": "/carbon-api/people/payroll-runs/{id}/",
                }
            if name == "list_payroll_runs":
                return {"method": "GET", "path": "/carbon-api/people/payroll-runs/"}
            return None

        def requires_confirmation(self, api_name):
            return False

        async def call_api_direct(self, method, path, params=None, body=None):
            calls.append(path)
            if path.rstrip("/").endswith("payroll-runs"):
                list_hits["n"] += 1
                if list_hits["n"] == 1:
                    return {"status_code": 200, "data": {"results": []}}
                return {
                    "status_code": 200,
                    "data": {
                        "results": [
                            {"id": 42, "period_start": "2026-10-01", "status": "draft"},
                        ]
                    },
                }
            if "demo-oct-2026" in path:
                raise Exception(
                    "People API call failed: Field 'id' expected a number "
                    "but got 'demo-oct-2026'."
                )
            if "/42/" in path:
                return {"status_code": 200, "data": {"id": 42, "status": "draft"}}
            return {"status_code": 404, "data": {"detail": "missing"}}

    class _Settings:
        API_DISCIPLINE_ENABLED = False

    monkey = pytest.MonkeyPatch()
    monkey.setattr(tools_mod, "get_settings", lambda: _Settings())
    try:
        out = await tools_mod.execute_call_host_api(
            api_name="get_payroll_run",
            explanation="fetch october run",
            path_params={"id": "demo-oct-2026"},
            executor=_Ex(),
            conversation_id="c1",
            instance_id="nibras",
        )
    finally:
        monkey.undo()

    assert not out.get("error"), out
    assert any("demo-oct-2026" in c for c in calls), calls
    assert any("/42/" in c for c in calls), calls
    assert list_hits["n"] >= 2


def test_hollow_web_research_detected():
    from ai.engine.cognition.plan.loop import _hollow_tool_message

    msg = _hollow_tool_message({
        "tool_name": "web_research",
        "result": {
            "query": "GOSI rates",
            "results": [],
            "message": "No results were returned from the keyless web sources.",
        },
    })
    assert msg and "No results" in msg
    assert _hollow_tool_message({
        "tool_name": "web_research",
        "result": {"results": [{"title": "x", "url": "https://x"}]},
    }) is None
