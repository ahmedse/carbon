"""
Phase 9-A — Investigate Mode (read-only pipeline).

Proves ``investigate`` completes end-to-end through ``dispatch_task`` with the
frozen metadata contract the 9-B frontend depends on:

    {"type": "investigation", "table_id", "table_name", "summary",
     "plan_steps": [...], "findings": [...],
     "counts": {"rules_run", "rules_failed", "anomalies", "kg_entities"}}

Read-only contract (RULE_21): the pipeline evaluates DQ via the pure
``dq.engine.evaluate`` loop and reads only the latest ``TableProfile`` — it
never calls ``run_dq`` or ``profile_table``.  An LLM outage degrades only the
narrative summary (synthesis step → ``llm_unavailable``) and never becomes
``pulse_unavailable``.
"""

from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from accounts.models import User
from ai.engine.core.config import get_settings
from ai.intelligence import CarbonIntelligence
from ai.models import AIConversation
from ai.store import reset_store
from ai.protocol import Scope
from core.models import Module
from dataschema.models import DataField, DataRow, DataTable
from mdm.models import OrgUnit


# ── Fixtures (mirror test_nl_rule.py) ───────────────────────────────────


def _fake_completion(content: str) -> types.SimpleNamespace:
    """Return an OpenAI-shaped completion whose content is *content*."""

    async def _create(**kw):
        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(content=content, tool_calls=None),
                    finish_reason="stop",
                )
            ],
            usage=types.SimpleNamespace(
                prompt_tokens=10, completion_tokens=4, total_tokens=14
            ),
        )

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=_create))
    )


@pytest.fixture
def django_store():
    """Use the Django backend so durable writes land in the test DB."""
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


@pytest.fixture
def cfg():
    """Clear the settings cache around each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _stub_llm(content: str):
    """Patch the LLM client to return *content* as the completion."""
    return patch(
        "ai.engine.llm.provider.get_llm_client",
        return_value=_fake_completion(content),
    )


@pytest.fixture
def user(db):
    return User.objects.create_user(username="investigate-worker", password="secret123")


@pytest.fixture
def table_graph(db, user):
    org = OrgUnit.objects.create(name="Inv Org", slug="inv-org")
    module = Module.objects.create(name="Inv Module", scope=1, org_unit=org)
    table = DataTable.objects.create(
        title="Inv Table",
        name="inv_table",
        module=module,
        created_by=user,
        updated_by=user,
    )
    field = DataField.objects.create(
        data_table=table,
        name="email",
        label="Email",
        type="string",
        created_by=user,
        updated_by=user,
    )
    return {"org": org, "module": module, "table": table, "field": field}


def _scope_for(user, module_id: int, *, app_identifier: str | None = None) -> Scope:
    return Scope(
        user_identifier=str(user.pk),
        org_unit_ids=["1"],
        module_ids=[str(module_id)],
        app_identifier=app_identifier,
    )


# ── Helpers ───────────────────────────────────────────────────────────────


def _row(values: dict, row_id: int) -> types.SimpleNamespace:
    """Stand-in for a DataRow: exposes ``.values`` (dict) and ``.id``."""
    return types.SimpleNamespace(values=values, id=row_id)


def _inv_payload(**overrides) -> dict:
    payload = {
        "table_id": 7,
        "table_name": "emissions",
        "schema": [{"name": "email", "label": "Email", "type": "string"}],
        "rows": [],
        "profile_summary": {},
        "rule_defs": [],
        "anomaly_payload": None,
        "kg_entries": [],
        "kg_tokens": 0,
    }
    payload.update(overrides)
    return payload


def _rule_def(
    rule_type: str,
    *,
    field: str = "email",
    severity: str = "error",
    params: dict | None = None,
    name: str = "email required",
) -> dict:
    return {
        "id": 1,
        "name": name,
        "type": rule_type,
        "severity": severity,
        "params": params or {},
        "field_name": field,
        "reference_set_id": None,
    }


# ── investigate (read-only pipeline) ─────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_investigate_empty_table_completes_with_five_done_steps(django_store, cfg):
    """A zero-row table yields 0 findings, 5 'done' plan steps, status completed."""
    from ai.engine_runtime import dispatch_task

    payload = _inv_payload()

    with _stub_llm('{"summary": "No issues found."}'):
        data = dispatch_task("investigate", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert result["table_id"] == 7, data
    assert result["table_name"] == "emissions", data
    assert result["findings"] == [], data
    assert result["counts"] == {
        "rules_run": 0,
        "rules_failed": 0,
        "anomalies": 0,
        "kg_entities": 0,
    }, data

    steps = result.get("plan_steps") or []
    assert len(steps) == 5, data
    assert [s["step"] for s in steps] == [1, 2, 3, 4, 5], data
    assert all(s["status"] == "done" for s in steps), data


@pytest.mark.django_db(transaction=True)
def test_investigate_failing_dq_rule_maps_severity(django_store, cfg):
    """A failing not_null rule yields a high-severity finding."""
    from ai.engine_runtime import dispatch_task

    payload = _inv_payload(
        rows=[_row({"email": ""}, 1), _row({"email": "a@b.c"}, 2)],
        rule_defs=[_rule_def("not_null", severity="error")],
    )

    with _stub_llm('{"summary": "One rule failed."}'):
        data = dispatch_task("investigate", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    counts = result.get("counts") or {}
    assert counts["rules_run"] == 1, data
    assert counts["rules_failed"] == 1, data

    findings = result.get("findings") or []
    assert len(findings) >= 1, data
    assert findings[0]["severity"] == "high", data
    assert findings[0]["entity_ref"] == "email", data
    assert "email required" in findings[0]["title"], data


@pytest.mark.django_db(transaction=True)
def test_investigate_warn_rule_maps_to_medium(django_store, cfg):
    """Severity mapping: DQ warn -> medium (frozen 9-B contract)."""
    from ai.engine_runtime import dispatch_task

    payload = _inv_payload(
        rows=[_row({"email": ""}, 1)],
        rule_defs=[_rule_def("not_null", severity="warn")],
    )

    with _stub_llm('{"summary": "One rule failed."}'):
        data = dispatch_task("investigate", payload, instance_id="carbon")

    findings = (data.get("result") or {}).get("findings") or []
    assert findings[0]["severity"] == "medium", data


@pytest.mark.django_db(transaction=True)
def test_investigate_anomaly_payload_produces_high_finding(django_store, cfg):
    """An anomaly-derived finding surfaces with a mapped severity."""
    from ai.engine_runtime import dispatch_task

    payload = _inv_payload(
        anomaly_payload={
            "table_name": "emissions",
            "profile_history": [],
            "sensitivity": 2.0,
            "volume_threshold_pct": 30.0,
        },
    )

    async def _canned_anomaly(instance_id, anomaly_payload, task_id):
        return {
            "status": "completed",
            "result": {
                "anomalies": [
                    {
                        "metric": "emissions.row_count",
                        "expected_range": {"low": 10, "high": 20},
                        "observed": 50,
                        "z_score": 4.0,
                        "severity": "error",
                        "explanation": "row_count spike",
                    }
                ],
                "history_snapshots": 3,
                "live_profile": {},
            },
        }

    with patch(
        "ai.engine_runtime._run_anomaly_detect",
        side_effect=_canned_anomaly,
    ), _stub_llm('{"summary": "One anomaly."}'):
        data = dispatch_task("investigate", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert (result.get("counts") or {}).get("anomalies") == 1, data
    findings = result.get("findings") or []
    assert len(findings) == 1, data
    assert findings[0]["severity"] == "high", data
    assert findings[0]["entity_ref"] == "emissions.row_count", data


@pytest.mark.django_db(transaction=True)
def test_investigate_insufficient_history_is_done_not_error(django_store, cfg):
    """anomaly_payload=None (insufficient history) → 'done' step, 0 anomalies."""
    from ai.engine_runtime import dispatch_task

    payload = _inv_payload(anomaly_payload=None)

    with _stub_llm('{"summary": "Nothing to report."}'):
        data = dispatch_task("investigate", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert (result.get("counts") or {}).get("anomalies") == 0, data
    steps = {s["step"]: s for s in (result.get("plan_steps") or [])}
    assert steps[3]["status"] == "done", data
    assert steps[3]["detail"] == "insufficient history", data


@pytest.mark.django_db(transaction=True)
def test_investigate_llm_outage_is_llm_unavailable_not_pulse_unavailable(django_store, cfg):
    """LLM outage degrades the summary only — findings remain, NOT pulse_unavailable."""
    from ai.engine_runtime import dispatch_task

    payload = _inv_payload(
        rows=[_row({"email": ""}, 1)],
        rule_defs=[_rule_def("not_null", severity="error")],
    )

    with patch("ai.engine.llm.router.route_chat", side_effect=RuntimeError("no key")):
        data = dispatch_task("investigate", payload, instance_id="carbon")

    assert data.get("status") == "completed", data  # NOT pulse_unavailable
    result = data.get("result") or {}

    # Deterministic findings still surfaced.
    assert len(result.get("findings") or []) >= 1, data
    assert (result.get("counts") or {}).get("rules_failed") == 1, data

    steps = {s["step"]: s for s in (result.get("plan_steps") or [])}
    assert steps[5]["status"] == "llm_unavailable", data
    assert "1 of 1 rule(s) failed" in result.get("summary", ""), data


# ── Routing: investigate conversation → _send_investigate_message ────────


@pytest.mark.django_db(transaction=True)
def test_investigate_conversation_routes_to_handler(user, table_graph, django_store, cfg):
    """An investigate conversation runs the read-only pipeline (not the staged placeholder)."""
    table = table_graph["table"]
    DataRow.objects.create(data_table=table, values={"email": "a@b.c"})

    conversation = AIConversation.objects.create(
        user=user,
        title="investigate",
        conversation_type="investigate",
        task_payload_json={
            "table_id": table.id,
            "module_id": table_graph["module"].id,
            "table_name": table.name,
        },
        scope_json={},
    )

    provider = MagicMock()
    provider.provider_name = "dummy"

    ci = CarbonIntelligence()
    ci._provider = provider

    with _stub_llm('{"summary": "No findings."}'), patch(
        "ai.intelligence.build_scope",
        return_value=_scope_for(user, table_graph["module"].id),
    ):
        result = ci.send_message(user, str(conversation.id), "investigate this table")

    meta = result["assistant_message"]["metadata_json"]
    assert meta["type"] == "investigation", result
    assert meta["table_id"] == table.id, result
    assert meta["findings"] == [], result
    assert meta["summary"] == "No findings.", result
    assert len(meta["plan_steps"]) == 5, result
    assert result["conversation"]["status"] == "completed", result
