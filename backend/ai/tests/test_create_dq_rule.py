"""Sprint 12-C — reference ``create_dq_rule`` plugin tests.

Covers the §4 flow: structural validation, deterministic dry-run preview,
authentication gating, confirmation-staged write, and validation-failure stop.
"""
from __future__ import annotations

import asyncio

import pytest

import ai.engine.agent.plugins as plugins_mod
from ai.engine.agent.plugins import ToolContext, registered_plugins
from ai.plugins.create_dq_rule import (
    CreateDQRule,
    _evaluate,
    _validate_definition,
    build_definition,
)


@pytest.fixture(autouse=True)
def _reset_plugins():
    original = list(plugins_mod._PLUGINS)
    yield
    plugins_mod._PLUGINS[:] = original


class FakeExecution:
    def __init__(self, execution_id: str = "ex-1"):
        self.id = execution_id


class FakeHostAPI:
    """Stands in for HostAPIExecutor — records staged writes, never POSTs."""

    def __init__(self, user_token: str | None = "tok"):
        self.user_token = user_token
        self.staged: list[dict] = []

    async def create_pending_execution(self, **kwargs) -> FakeExecution:
        self.staged.append(kwargs)
        return FakeExecution()


def _run(args, *, host_api) -> dict:
    plugin = CreateDQRule()
    ctx = ToolContext(conversation_id="conv-1", host_api=host_api)
    return asyncio.run(plugin.execute(args, ctx=ctx))


# ── Registration ─────────────────────────────────────────────────────────


def test_create_dq_rule_is_registered_at_startup():
    names = {p.name for p in registered_plugins()}
    assert "create_dq_rule" in names


def test_create_dq_rule_metadata():
    from ai.plugins import register_builtin_plugins

    register_builtin_plugins()
    plugin = next(p for p in registered_plugins() if p.name == "create_dq_rule")
    assert plugin.requires_confirmation is True
    assert plugin.capability == "dq:manage_rules"
    assert plugin.app_identifier == "dq"


# ── Definition building + validation ─────────────────────────────────────


def test_build_definition_valid():
    definition, errors = build_definition({
        "name": "email not null",
        "rule_type": "not_null",
        "level": "field",
        "severity": "error",
    })
    assert errors == []
    assert definition["schema_version"] == 1
    assert definition["type"] == "not_null"
    assert definition["dimension"] == "validity"


def test_build_definition_invalid():
    definition, errors = build_definition({"name": "", "rule_type": "bogus"})
    assert errors
    fields = {e["field"] for e in errors}
    assert "name" in fields
    assert "type" in fields


def test_validate_definition_rejects_bad_regex():
    _, errors = build_definition({
        "name": "bad regex",
        "rule_type": "regex",
        "level": "field",
        "params": {"pattern": "([unclosed"},
    })
    assert any(e["field"] == "params.pattern" for e in errors)


def test_validate_definition_requires_nl_prompt():
    _, errors = build_definition({
        "name": "nl",
        "rule_type": "nl_check",
        "level": "business",
    })
    assert any(e["field"] == "params.prompt" for e in errors)


def test_validate_definition_rejects_operator_on_range():
    # range has no comparison operator; "positive number" must use threshold.
    _, errors = build_definition({
        "name": "validate positive number",
        "rule_type": "range",
        "level": "field",
        "params": {"min": 0, "operator": ">"},
    })
    assert any(e["field"] == "params.operator" for e in errors)


def test_build_definition_threshold_positive_number_is_valid():
    definition, errors = build_definition({
        "name": "validate positive number",
        "rule_type": "threshold",
        "level": "field",
        "params": {"operator": "gt", "value": 0},
    })
    assert errors == []
    assert definition["type"] == "threshold"
    assert definition["params"] == {"operator": "gt", "value": 0}


# ── Deterministic dry-run preview ────────────────────────────────────────


def test_evaluate_not_null_flags_missing():
    definition = {"type": "not_null", "params": {}}
    rows = [{"email": "a@b.c"}, {"email": None}, {"email": ""}]
    preview = _evaluate(definition, rows, "email")
    assert preview["passed"] is False
    assert preview["failed_rows"] == [1, 2]


def test_evaluate_allowed_values():
    definition = {"type": "allowed_values", "params": {"values": ["A", "B"]}}
    rows = [{"grade": "A"}, {"grade": "C"}, {"grade": "B"}]
    preview = _evaluate(definition, rows, "grade")
    assert preview["passed"] is False
    assert preview["failed_rows"] == [1]


def test_evaluate_unique_flags_duplicates():
    definition = {"type": "unique", "params": {}}
    rows = [{"id": 1}, {"id": 2}, {"id": 1}]
    preview = _evaluate(definition, rows, "id")
    assert preview["passed"] is False
    assert set(preview["failed_rows"]) == {0, 2}


# ── execute() gating + staged write ──────────────────────────────────────


def test_execute_requires_host_api():
    result = _run({"name": "x", "rule_type": "not_null", "level": "field"}, host_api=None)
    assert "error" in result
    assert "Host API executor" in result["error"]


def test_execute_requires_authenticated_session():
    host_api = FakeHostAPI(user_token=None)
    result = _run({"name": "x", "rule_type": "not_null", "level": "field"}, host_api=host_api)
    assert "error" in result
    assert "authenticated session" in result["error"]
    assert host_api.staged == []


def test_execute_invalid_rule_stops_before_write():
    host_api = FakeHostAPI()
    result = _run({"name": "", "rule_type": "bogus"}, host_api=host_api)
    assert result["requires_confirmation"] is False
    assert "error" in result
    assert result["validation"]["passed"] is False
    assert host_api.staged == []  # nothing staged


def test_create_dq_rule_with_invalid_rule_type_returns_error():
    """Regression (2026-08-27 phantom success): a hallucinated ``rule_type``
    (e.g. "general") must produce a non-null error/validation result — never a
    silent null that the runner marks "completed"."""
    host_api = FakeHostAPI()
    # Reproduce the exact hallucinated args from the phantom-success run.
    result = _run({
        "rule_type": "general",
        "validation_logic": "field is a number and positive",
    }, host_api=host_api)

    assert result is not None
    assert "error" in result or "validation" in result
    # The invalid rule_type (→ definition["type"]) must fail validation.
    assert result["validation"]["passed"] is False
    fields = {e["field"] for e in result["validation"]["errors"]}
    assert "type" in fields  # rule_type is mapped to definition.type
    # Nothing was staged — the phantom write must never happen.
    assert host_api.staged == []
    assert result["requires_confirmation"] is False


def test_execute_deterministic_rule_unbound_stages_confirmation():
    """A deterministic rule CAN be created unbound (a general rule the user
    binds later via bind_dq_rules). The host supports standalone authoring
    (empty field_assignments_write), so no data_table/data_field is required —
    the plugin stages the write instead of blocking it."""
    host_api = FakeHostAPI()
    result = _run({
        "name": "Validate Minimum String Length",
        "rule_type": "regex",
        "level": "field",
        "params": {"pattern": r".{3,}"},
    }, host_api=host_api)

    assert result is not None
    assert result["requires_confirmation"] is True
    assert "error" not in result
    assert host_api.staged
    body = host_api.staged[0]["body"]
    # Unbound: no field_assignments_write emitted (bind later).
    assert "field_assignments_write" not in body
    assert body["rule_type"] == "regex"
    assert body["definition"]["params"] == {"pattern": ".{3,}"}


def test_execute_dry_run_stages_confirmation_not_write():
    host_api = FakeHostAPI()
    result = _run({
        "name": "email not null",
        "rule_type": "not_null",
        "level": "field",
        "column": "email",
        "data_table": 5,
        "data_field": 7,
        "sample_rows": [{"email": "a@b.c"}, {"email": None}],
    }, host_api=host_api)

    assert result["requires_confirmation"] is True
    assert result["execution_id"] == "ex-1"
    assert result["proposed_rule"]["type"] == "not_null"
    assert result["validation"]["passed"] is False
    assert result["validation"]["failed_rows"] == [1]

    # The write is STAGED, never executed by the plugin.
    assert len(host_api.staged) == 1
    staged = host_api.staged[0]
    assert staged["method"] == "POST"
    assert staged["endpoint"] == "/carbon-api/dq/rules/"
    assert staged["tool_name"] == "create_dq_rule"
    body = staged["body"]
    assert body["rule_type"] == "not_null"
    assert body["rule_level"] == "field_validation"
    assert body["definition"]["schema_version"] == 1
    assert body["field_assignments_write"] == [{"data_table": 5, "data_field": 7}]
