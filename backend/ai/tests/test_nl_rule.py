"""
Phase 8-A — nl_rule_test execution path (Execute Mode gate).

Proves ``dq.rule_test`` completes end-to-end through ``dispatch_task`` with a
stubbed LLM, and fails visible on LLM outage:

    dq.rule_test -> {"rule_preview": {...}, "test_summary": {...},
                     "violations": [...], "recommendation": "..."}

Fail-visible contract (mirrors test_dq_wiring.py):
- LLM outage           -> ``pulse_unavailable`` / ``llm_unavailable``.
- Unparseable LLM JSON -> ``pulse_unavailable``.
- Unsupported rule type (nl_check / anomaly_detect) -> ``pulse_unavailable``.

Nothing is written to DQ: the dry-run uses the pure ``dq.engine.evaluate``
against in-memory rows (``types.SimpleNamespace(values=..., id=...)``), so the
frontend (8-B) owns the "Save Rule" confirmation gate.
"""

from __future__ import annotations

import json
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


# ── Fixtures (mirror test_dq_wiring.py) ───────────────────────────────────


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
    return User.objects.create_user(username="nl-rule-worker", password="secret123")


@pytest.fixture
def table_graph(db, user):
    org = OrgUnit.objects.create(name="NL Org", slug="nl-org")
    module = Module.objects.create(name="NL Module", scope=1, org_unit=org)
    table = DataTable.objects.create(
        title="NL Table",
        name="nl_table",
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


def _payload(nl: str, rows: list, *, field_name: str = "email") -> dict:
    return {
        "table_id": 7,
        "table_name": "emissions",
        "schema": [{"name": field_name, "type": "string"}],
        "nl": nl,
        "rows": rows,
        "field_name": field_name,
    }


def _rule_verdict(
    rule_type: str,
    params: dict | None = None,
    *,
    field: str = "email",
    severity: str = "error",
    confidence: float = 0.9,
) -> str:
    return json.dumps(
        {
            "type": rule_type,
            "params": params or {},
            "severity": severity,
            "confidence": confidence,
            "field": field,
        }
    )


# ── dq.rule_test ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_nl_rule_test_parses_and_previews_not_null(django_store, cfg):
    """A not_null rule against mixed rows completes with a pass/fail preview."""
    from ai.engine_runtime import dispatch_task

    rows = [
        _row({"email": "a@b.c"}, 1),
        _row({"email": None}, 2),
        _row({"email": ""}, 3),
    ]
    payload = _payload("email must not be empty", rows)

    with _stub_llm(_rule_verdict("not_null")):
        data = dispatch_task("dq.rule_test", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    preview = result.get("rule_preview")
    assert preview is not None, data
    assert preview["type"] == "not_null", data
    assert preview["field"] == "email", data
    assert preview["severity"] == "error", data

    summary = result.get("test_summary") or {}
    assert summary["total_rows"] == 3, data
    assert summary["applicable_rows"] == 3, data
    assert summary["failed"] == 2, data
    assert summary["passed"] == 1, data
    assert summary["pass_rate"] == round(1 / 3, 4), data
    assert len(result.get("violations") or []) == 2, data

    detail = result.get("rows") or []
    assert len(detail) == 3, data
    for entry in detail:
        assert set(entry) == {"row_id", "actual", "expected", "passed"}, data
    assert sum(1 for e in detail if e["passed"]) == summary["passed"], data
    assert sum(1 for e in detail if not e["passed"]) == summary["failed"], data


@pytest.mark.django_db
def test_nl_rule_test_zero_row_table_passes(django_store, cfg):
    """A zero-row table yields no failures (nothing to violate)."""
    from ai.engine_runtime import dispatch_task

    payload = _payload("email must not be empty", [])

    with _stub_llm(_rule_verdict("not_null")):
        data = dispatch_task("dq.rule_test", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    summary = (data.get("result") or {}).get("test_summary") or {}
    assert summary["total_rows"] == 0, data
    assert summary["applicable_rows"] == 0, data
    assert summary["failed"] == 0, data
    assert (data.get("result") or {}).get("violations") == [], data


@pytest.mark.django_db
def test_nl_rule_test_all_fail_table_has_zero_pass(django_store, cfg):
    """Every row violating a range rule yields passed == 0."""
    from ai.engine_runtime import dispatch_task

    rows = [
        _row({"co2e_kg": -1.0}, 1),
        _row({"co2e_kg": -2.5}, 2),
        _row({"co2e_kg": -3.0}, 3),
    ]
    payload = _payload(
        "co2e_kg must be non-negative", rows, field_name="co2e_kg"
    )

    with _stub_llm(_rule_verdict("range", {"min": 0}, field="co2e_kg")):
        data = dispatch_task("dq.rule_test", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    summary = (data.get("result") or {}).get("test_summary") or {}
    assert summary["failed"] == 3, data
    assert summary["passed"] == 0, data
    assert summary["pass_rate"] == 0.0, data
    assert len((data.get("result") or {}).get("violations") or []) == 3, data


@pytest.mark.django_db
def test_nl_rule_test_returns_per_row_detail_for_threshold(django_store, cfg):
    """A threshold rule returns per-applicable-row actual/expected/passed."""
    from ai.engine_runtime import dispatch_task

    rows = [
        _row({"total_kwh": 100.0}, 1),
        _row({"total_kwh": 40.0}, 2),
        _row({"total_kwh": 80.0}, 3),
    ]
    payload = _payload(
        "total_kwh must be at least 50", rows, field_name="total_kwh"
    )

    with _stub_llm(
        _rule_verdict(
            "threshold", {"operator": "gte", "value": 50}, field="total_kwh"
        )
    ):
        data = dispatch_task("dq.rule_test", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    detail = (data.get("result") or {}).get("rows") or []
    assert len(detail) == 3, data
    by_id = {d["row_id"]: d for d in detail}
    assert by_id[1]["passed"] is True, data
    assert by_id[2]["passed"] is False, data
    assert by_id[3]["passed"] is True, data
    assert by_id[2]["actual"] == 40.0, data
    assert by_id[2]["expected"] == {"operator": "gte", "value": 50}, data


@pytest.mark.django_db
def test_nl_rule_test_llm_outage_is_fail_visible(django_store, cfg):
    """An LLM outage yields pulse_unavailable/llm_unavailable — no fake preview."""
    from ai.engine_runtime import dispatch_task

    rows = [_row({"email": "a@b.c"}, 1)]
    payload = _payload("email must not be empty", rows)

    with patch("ai.engine.llm.router.route_chat", side_effect=RuntimeError("no key")):
        data = dispatch_task("dq.rule_test", payload, instance_id="carbon")

    assert data.get("status") == "pulse_unavailable", data
    assert data.get("error", {}).get("code") == "llm_unavailable", data


@pytest.mark.django_db
def test_nl_rule_test_unparseable_llm_is_fail_visible(django_store, cfg):
    """An unparseable LLM response degrades to pulse_unavailable."""
    from ai.engine_runtime import dispatch_task

    rows = [_row({"email": "a@b.c"}, 1)]
    payload = _payload("email must not be empty", rows)

    with _stub_llm("this is not json"):
        data = dispatch_task("dq.rule_test", payload, instance_id="carbon")

    assert data.get("status") == "pulse_unavailable", data
    assert data.get("error", {}).get("code") == "llm_unavailable", data


@pytest.mark.django_db
def test_nl_rule_test_unsupported_rule_type_is_fail_visible(django_store, cfg):
    """nl_check/anomaly_detect are never dry-run; they degrade visibly."""
    from ai.engine_runtime import dispatch_task

    rows = [_row({"email": "a@b.c"}, 1)]
    payload = _payload("email looks valid", rows)

    with _stub_llm(_rule_verdict("nl_check", {"prompt": "email looks valid"})):
        data = dispatch_task("dq.rule_test", payload, instance_id="carbon")

    assert data.get("status") == "pulse_unavailable", data
    assert data.get("error", {}).get("code") == "llm_unavailable", data


@pytest.mark.django_db
def test_nl_rule_test_empty_nl_returns_no_preview(django_store, cfg):
    """No NL rule text -> completed with a null preview and no failures."""
    from ai.engine_runtime import dispatch_task

    rows = [_row({"email": "a@b.c"}, 1)]
    payload = _payload("", rows)

    data = dispatch_task("dq.rule_test", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert result.get("rule_preview") is None, data
    assert (result.get("test_summary") or {}).get("total_rows") == 1, data
    assert (result.get("test_summary") or {}).get("failed") == 0, data


# ── Routing: nl_rule_test conversation → _send_nl_rule_test_message ──────


@pytest.mark.django_db
def test_nl_rule_test_conversation_routes_to_handler(user, table_graph, django_store, cfg):
    """A nl_rule_test conversation dry-runs a rule and persists an nl_rule_test message."""
    table = table_graph["table"]
    DataRow.objects.create(data_table=table, values={"email": ""})

    conversation = AIConversation.objects.create(
        user=user,
        title="nl_rule_test",
        conversation_type="nl_rule_test",
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

    with _stub_llm(_rule_verdict("not_null")), patch(
        "ai.intelligence.build_scope",
        return_value=_scope_for(user, table_graph["module"].id),
    ):
        result = ci.send_message(user, str(conversation.id), "email must not be empty")

    assert result["assistant_message"]["metadata_json"]["type"] == "nl_rule_test", result
    preview = result["assistant_message"]["metadata_json"]["rule_preview"]
    assert preview["type"] == "not_null", result
    summary = result["assistant_message"]["metadata_json"]["test_summary"]
    assert summary["total_rows"] == 1, result
    assert summary["failed"] == 1, result
    assert result["conversation"]["status"] == "needs_input", result
