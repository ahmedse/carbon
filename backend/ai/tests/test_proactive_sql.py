"""P1-09 — proactive SQL injection hardening tests.

Covers the structured-predicate renderer, the fail-closed rejection of legacy
raw-string ``where`` clauses, parameterized execution of the host aggregation
helpers, and ``validate_sql`` routing in the context assembler.

All tests are offline and deterministic: no live Postgres connection is made
(``psycopg2.connect`` is monkeypatched where execution is exercised).
"""

from __future__ import annotations

import asyncio
import types

import pytest


# ── 1. _render_where: structured predicates ──────────────────────────────


def test_render_where_single_predicate_binds_value():
    from ai.engine.proactive.trigger_evaluator import _render_where

    sql, params = _render_where({"field": "asset_id", "op": "==", "value": "T-3"})

    assert sql == 'WHERE "asset_id" = %s'
    assert params == ["T-3"]


def test_render_where_list_is_anded_in_order():
    from ai.engine.proactive.trigger_evaluator import _render_where

    sql, params = _render_where([
        {"field": "asset_id", "op": "=", "value": "T-3"},
        {"field": "temp", "op": ">", "value": 100},
    ])

    assert sql == 'WHERE "asset_id" = %s AND "temp" > %s'
    assert params == ["T-3", 100]


def test_render_where_is_null_contributes_no_param():
    from ai.engine.proactive.trigger_evaluator import _render_where

    sql, params = _render_where({"field": "x", "op": "is_null"})

    assert sql == 'WHERE "x" IS NULL'
    assert params == []


def test_render_where_is_not_null_contributes_no_param():
    from ai.engine.proactive.trigger_evaluator import _render_where

    sql, params = _render_where({"field": "x", "op": "is_not_null"})

    assert sql == 'WHERE "x" IS NOT NULL'
    assert params == []


def test_render_where_like_does_not_add_wildcards():
    from ai.engine.proactive.trigger_evaluator import _render_where

    sql, params = _render_where({"field": "name", "op": "like", "value": "T-3%"})

    assert sql == 'WHERE "name" LIKE %s'
    assert params == ["T-3%"]


@pytest.mark.parametrize("empty", [None, [], {}])
def test_render_where_empty_inputs_return_no_fragment(empty):
    from ai.engine.proactive.trigger_evaluator import _render_where

    assert _render_where(empty) == ("", [])


# ── 2. _render_where: fail-closed on unsafe input ────────────────────────


@pytest.mark.parametrize("bad_predicate", [
    # op not allowlisted (injection attempt)
    {"field": "x", "op": "; DROP TABLE readings", "value": 1},
    {"field": "x", "op": "or 1=1", "value": 1},
    # missing / invalid field
    {"op": "=", "value": 1},
    {"field": "", "op": "=", "value": 1},
    {"field": None, "op": "=", "value": 1},
    # missing / invalid op
    {"field": "x"},
    {"field": "x", "op": None, "value": 1},
    # non-dict element inside a list
    "not-a-dict",
])
def test_render_where_rejects_unsafe_predicate(bad_predicate):
    from ai.engine.proactive.trigger_evaluator import _render_where

    with pytest.raises(ValueError):
        _render_where(bad_predicate)


@pytest.mark.parametrize("bad_input", ["asset_id = 'T-3'", 42, 3.14, ("a", "b")])
def test_render_where_rejects_non_dict_or_list_input(bad_input):
    from ai.engine.proactive.trigger_evaluator import _render_where

    with pytest.raises(ValueError):
        _render_where(bad_input)


# ── 3. validate_sql rejects DML / multi-statement ────────────────────────


@pytest.mark.parametrize("sql", [
    "SELECT 1; DROP TABLE x",
    "DELETE FROM t",
    "UPDATE t SET a = 1",
    "SELECT 1; SELECT 2",
])
def test_validate_sql_rejects_unsafe(sql):
    from ai.engine.core.exceptions import ToolExecutionError
    from ai.engine.core.sql_validator import validate_sql

    with pytest.raises(ToolExecutionError):
        validate_sql(sql)


def test_validate_sql_accepts_parameterized_select():
    from ai.engine.core.sql_validator import validate_sql

    validate_sql('SELECT AVG("temp") FROM "readings" WHERE "asset_id" = %s')


# ── 4. Legacy raw-string `where` is rejected (fail-closed) ───────────────


def test_evaluate_threshold_rejects_legacy_raw_where(monkeypatch):
    from ai.engine.proactive import trigger_evaluator

    called = []

    async def _fake_query(*args, **kwargs):
        called.append((args, kwargs))
        return 1.0

    monkeypatch.setattr(trigger_evaluator, "_query_aggregation", _fake_query)

    trigger = types.SimpleNamespace(id="trig-1", severity="warning", name="Legacy")
    condition = {
        "table": "readings",
        "column": "temp",
        "operator": ">",
        "value": 100.0,
        "where": "asset_id = 'T-3' OR 1=1",
        "aggregation": "latest",
    }

    result = asyncio.run(
        trigger_evaluator._evaluate_threshold(trigger, condition, [], "postgresql://x")
    )

    assert result.fired is False
    detail = result.detail.lower()
    assert "legacy" in detail
    assert "migrate" in detail
    # The raw fragment was never handed to the query helper.
    assert called == []


def test_evaluate_threshold_accepts_structured_where(monkeypatch):
    from ai.engine.proactive import trigger_evaluator

    captured = []

    async def _fake_query(host_db_url, table, column, aggregation, predicates=None):
        captured.append(predicates)
        return 150.0

    monkeypatch.setattr(trigger_evaluator, "_query_aggregation", _fake_query)

    trigger = types.SimpleNamespace(id="trig-2", severity="warning", name="Structured")
    condition = {
        "table": "readings",
        "column": "temp",
        "operator": ">",
        "value": 100.0,
        "where": {"field": "asset_id", "op": "==", "value": "T-3"},
        "aggregation": "latest",
    }

    result = asyncio.run(
        trigger_evaluator._evaluate_threshold(trigger, condition, [], "postgresql://x")
    )

    assert result.fired is True
    assert captured == [{"field": "asset_id", "op": "==", "value": "T-3"}]


# ── 5. _query_aggregation binds params + validates SQL ───────────────────


def _install_fake_psycopg2(monkeypatch, calls):
    """Patch psycopg2.connect with an in-memory connection/cursor recorder."""
    import psycopg2

    class _FakeCursor:
        def execute(self, sql, params=None):
            calls.append((sql, params))

        def fetchone(self):
            return (42.0,)

        def close(self):
            pass

    class _FakeConn:
        def set_session(self, **kwargs):
            pass

        def cursor(self):
            return _FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr(psycopg2, "connect", lambda url: _FakeConn())


def test_query_aggregation_binds_params_not_interpolates(monkeypatch):
    from ai.engine.core.sql_validator import validate_sql
    from ai.engine.proactive.trigger_evaluator import _query_aggregation

    calls = []
    _install_fake_psycopg2(monkeypatch, calls)

    result = asyncio.run(_query_aggregation(
        "postgresql://host/db",
        "readings",
        "temp",
        "avg",
        [{"field": "asset_id", "op": "==", "value": "T-3"}],
    ))

    assert result == 42.0

    selects = [(s, p) for s, p in calls if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 1
    sql, params = selects[0]

    # Value travels as a bound parameter, never as raw SQL text.
    assert params == ["T-3"]
    assert "T-3" not in sql
    assert "%s" in sql
    # The generated string is itself validator-clean.
    validate_sql(sql)


def test_query_aggregation_without_predicates_is_still_validated(monkeypatch):
    from ai.engine.core.sql_validator import validate_sql
    from ai.engine.proactive.trigger_evaluator import _query_aggregation

    calls = []
    _install_fake_psycopg2(monkeypatch, calls)

    # Mirrors the user_watches.py call shape (no where clause).
    result = asyncio.run(
        _query_aggregation("postgresql://host/db", "readings", "temp", "latest")
    )

    assert result == 42.0
    selects = [(s, p) for s, p in calls if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 1
    sql, params = selects[0]
    assert params == []
    assert "WHERE" not in sql
    validate_sql(sql)


def test_query_aggregation_rejects_bad_predicates_without_executing(monkeypatch):
    import psycopg2
    from ai.engine.proactive.trigger_evaluator import _query_aggregation

    connect_called = []

    def _boom(url):
        connect_called.append(url)
        raise AssertionError("connect must not be reached for unsafe predicates")

    monkeypatch.setattr(psycopg2, "connect", _boom)

    result = asyncio.run(_query_aggregation(
        "postgresql://host/db",
        "readings",
        "temp",
        "avg",
        {"field": "x", "op": "; DROP TABLE readings", "value": 1},
    ))

    assert result is None
    assert connect_called == []


def test_query_time_avg_parameterizes_interval(monkeypatch):
    from ai.engine.core.sql_validator import validate_sql
    from ai.engine.proactive.trigger_evaluator import _query_time_avg

    calls = []
    _install_fake_psycopg2(monkeypatch, calls)

    result = asyncio.run(
        _query_time_avg("postgresql://host/db", "unit_metrics", "heat_rate", "recorded_at", 7)
    )

    assert result == 42.0
    selects = [(s, p) for s, p in calls if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 1
    sql, params = selects[0]
    assert params == [7]
    assert "INTERVAL '7" not in sql  # window is not interpolated
    assert "INTERVAL '1 day' * %s" in sql
    validate_sql(sql)


# ── 6. context_assembler routes through validate_sql ─────────────────────


def test_context_queries_reject_non_select_without_executing(monkeypatch):
    import psycopg2
    from ai.engine.proactive.context_assembler import _execute_context_queries

    connect_called = []

    def _boom(url):
        connect_called.append(url)
        raise AssertionError("connect must not be reached for rejected SQL")

    monkeypatch.setattr(psycopg2, "connect", _boom)

    results = asyncio.run(_execute_context_queries(
        [
            {"sql": "DROP TABLE readings", "label": "drop"},
            {"sql": "SELECT 1; DROP TABLE readings", "label": "multi"},
            {"sql": "DELETE FROM readings", "label": "delete"},
        ],
        "postgresql://host/db",
    ))

    assert connect_called == []
    assert [r["label"] for r in results] == ["drop", "multi", "delete"]
    for item in results:
        assert item.get("error")
        assert "rows" not in item
