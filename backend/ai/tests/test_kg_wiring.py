"""
Phase 2b-2 — KG/analytics task wiring proof.

Proves the in-process engine's seven knowledge-graph / analytics task types are
wired end-to-end through ``dispatch_task``:

    carbon.query.nl        carbon.query.explain
    carbon.schema.analyze  carbon.anomaly.detect
    carbon.anomaly.explain carbon.report.draft
    carbon.fix.suggest

Every one returns ``status="completed"``.  No HTTP.  Fail-visible: a handler
that raises returns ``pulse_unavailable`` with ``code="engine_error"``.

The LLM is stubbed (``get_llm_client``) because the dev environment has no
``LLM_API_KEY``; deterministic fallbacks cover every handler when the LLM is
unavailable, so nothing is ever fabricated.
"""

from __future__ import annotations

import types
from unittest.mock import patch

import pytest
from django.test import override_settings

from ai.engine.core.config import get_settings
from ai.store import reset_store


KG_TASKS = (
    "carbon.query.nl",
    "carbon.query.explain",
    "carbon.schema.analyze",
    "carbon.anomaly.detect",
    "carbon.anomaly.explain",
    "carbon.report.draft",
    "carbon.fix.suggest",
)


# ── Fixtures ─────────────────────────────────────────────────────────────


def _fake_completion(*args, **kwargs) -> types.SimpleNamespace:
    async def _create(**kw):
        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(
                        content="This is a stubbed chat reply.",
                        tool_calls=None,
                    ),
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


@pytest.fixture
def stub_llm():
    with patch("ai.engine.llm.provider.get_llm_client") as mock:
        mock.return_value = _fake_completion()
        yield mock


# ── Completed-path tests ─────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_query_nl_returns_completed(django_store, cfg, stub_llm):
    from ai.engine_runtime import dispatch_task
    from ai.models.knowledge_graph import KgQueryFeedback
    from ai.engine.knowledge_graph.engine import ExecutionResult

    payload = {
        "question": "total co2e this quarter",
        "tables": ["emissions"],
        "max_rows": 10,
    }

    async def _fake_execute(self, sql):
        return ExecutionResult(
            success=True,
            rows=[{"total": 42}],
            row_count=1,
            duration_ms=3,
            sql_executed=sql,
        )

    with patch("ai.engine.knowledge_graph.engine.ExecutionEngine.execute",
               new=_fake_execute):
        data = dispatch_task("carbon.query.nl", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert result.get("sql"), data  # deterministic SQL (no SQL in stub reply)
    assert result.get("rows") == [{"total": 42}]
    assert result.get("row_count") == 1
    assert result.get("execution_ms", -1) >= 0

    # Durable feedback write proof (DjangoStore -> test DB).
    assert KgQueryFeedback.objects.count() >= 1


@pytest.mark.django_db(transaction=True)
def test_query_nl_execution_failure_is_fail_visible(django_store, cfg, stub_llm):
    from ai.engine_runtime import dispatch_task
    from ai.engine.knowledge_graph.engine import (
        ErrorCategory,
        ExecutionError,
        ExecutionResult,
    )

    async def _fail(self, sql):
        return ExecutionResult(
            success=False,
            sql_executed=sql,
            error=ExecutionError(
                category=ErrorCategory.TABLE_NOT_FOUND,
                message='relation "emissions" does not exist',
            ),
        )

    with patch("ai.engine.knowledge_graph.engine.ExecutionEngine.execute",
               new=_fail):
        data = dispatch_task(
            "carbon.query.nl",
            {"question": "hi", "tables": ["emissions"]},
            instance_id="carbon",
        )

    assert data.get("status") == "pulse_unavailable", data
    assert data.get("error", {}).get("code") == "engine_error", data


@pytest.mark.django_db(transaction=True)
def test_query_explain_returns_completed(django_store, cfg, stub_llm):
    from ai.engine_runtime import dispatch_task

    payload = {"sql": "SELECT * FROM emissions LIMIT 5", "question": "what is this?"}
    data = dispatch_task("carbon.query.explain", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert result.get("explanation"), data
    assert isinstance(result.get("caveats"), list)


@pytest.mark.django_db(transaction=True)
def test_schema_analyze_returns_completed(django_store, cfg):
    from ai.engine_runtime import dispatch_task

    payload = {
        "schema_changes": [
            {"change": "drop column co2e_kg", "table_name": "emissions",
             "field_name": "co2e_kg"},
        ],
        "context": {},
    }
    data = dispatch_task("carbon.schema.analyze", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    analysis = (data.get("result") or {}).get("analysis")
    assert isinstance(analysis, list) and analysis, data
    row = analysis[0]
    for key in ("change", "impact", "severity", "suggested_action"):
        assert key in row, (key, data)
    assert row["severity"] == "high"  # dropping a column is destructive


@pytest.mark.django_db(transaction=True)
def test_anomaly_detect_returns_completed(django_store, cfg):
    from ai.engine_runtime import dispatch_task

    def snap(rc, comp):
        return {
            "at": "2026-01-01T00:00:00Z", "row_count": rc,
            "completeness_pct": comp, "null_counts": {},
        }

    payload = {
        "table_name": "emissions",
        "profile_history": [snap(1000, 98.0), snap(1050, 97.5), snap(2100, 97.0)],
        "sensitivity": 2.0,
        "volume_threshold_pct": 30.0,
    }
    data = dispatch_task("carbon.anomaly.detect", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert result.get("history_snapshots") == 3, data
    anomalies = result.get("anomalies")
    assert isinstance(anomalies, list) and anomalies, data
    for a in anomalies:
        for key in ("metric", "expected_range", "observed", "z_score",
                    "severity", "explanation"):
            assert key in a, (key, data)


@pytest.mark.django_db(transaction=True)
def test_anomaly_detect_live_profile_grounds_real_row_count(django_store, cfg):
    """G1 — live host-DB profile is attempted (fallback to Django default DB)
    and a large live/snapshot deviation is flagged with ``.row_count.live``."""
    from ai.engine_runtime import dispatch_task
    from ai.engine.knowledge_graph.data_profiler import TableProfile

    def snap(rc, comp):
        return {
            "at": "2026-01-01T00:00:00Z", "row_count": rc,
            "completeness_pct": comp, "null_counts": {},
        }

    async def _fake_profile(self, table_name, columns=None, sample_size=None,
                            max_cardinality=None):
        return TableProfile(
            table_name=table_name,
            row_count=5000,
            columns=[],
            profiled_at="2026-01-02T00:00:00Z",
        )

    payload = {
        "table_name": "emissions",
        "profile_history": [snap(1000, 98.0), snap(1050, 97.5), snap(1100, 97.0)],
        "sensitivity": 2.0,
        "volume_threshold_pct": 30.0,
    }

    with patch(
        "ai.engine.knowledge_graph.data_profiler.DataProfiler.profile_table",
        new=_fake_profile,
    ):
        data = dispatch_task("carbon.anomaly.detect", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    live = result.get("live_profile")
    assert live, data
    assert live["row_count"] == 5000, data
    assert live["table_name"] == "emissions", data
    # Live count 5000 vs latest snapshot 1100 → >30% deviation → flagged.
    live_metrics = [a["metric"] for a in result.get("anomalies", [])]
    assert "emissions.row_count.live" in live_metrics, data


@pytest.mark.django_db(transaction=True)
def test_anomaly_explain_returns_completed(django_store, cfg, stub_llm):
    from ai.engine_runtime import dispatch_task

    payload = {
        "table_name": "emissions",
        "anomaly": {"metric": "emissions.row_count", "observed": 2100},
    }
    data = dispatch_task("carbon.anomaly.explain", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert result.get("explanation"), data
    assert isinstance(result.get("investigation_steps"), list)


@pytest.mark.django_db(transaction=True)
def test_report_draft_returns_completed(django_store, cfg, stub_llm):
    from ai.engine_runtime import dispatch_task

    payload = {"report_type": "emissions_summary", "period_start": "2026-01-01",
               "period_end": "2026-06-30", "metrics": {}}
    data = dispatch_task("carbon.report.draft", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert result.get("title"), data
    assert result.get("report_type") == "emissions_summary", data
    sections = result.get("sections")
    assert isinstance(sections, list) and sections, data
    assert sections[0].get("narrative") or sections[0].get("content"), data


@pytest.mark.django_db(transaction=True)
def test_report_draft_includes_host_metrics(django_store, cfg, stub_llm):
    """G2 — report.draft pulls live pg_stat_user_tables volume and exposes it
    as a second "Data Volume (Live)" section plus a host_metrics key."""
    from ai.engine_runtime import dispatch_task
    from ai.engine.knowledge_graph.engine import ExecutionResult

    async def _fake_execute(self, sql):
        return ExecutionResult(
            success=True,
            rows=[
                {"table_name": "emissions_activity", "row_count": 1234},
                {"table_name": "emissions_factors", "row_count": 56},
            ],
            row_count=2,
            duration_ms=2,
            sql_executed=sql,
        )

    payload = {"report_type": "emissions_summary", "period_start": "2026-01-01",
               "period_end": "2026-06-30", "metrics": {}}

    with patch("ai.engine.knowledge_graph.engine.ExecutionEngine.execute",
               new=_fake_execute):
        data = dispatch_task("carbon.report.draft", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    host_metrics = result.get("host_metrics")
    assert host_metrics, data
    assert host_metrics.get("total_tables") == 2, data
    assert host_metrics["tables"][0]["table_name"] == "emissions_activity", data

    sections = result.get("sections")
    titles = [s.get("title") for s in sections]
    assert "Summary" in titles, data
    assert "Data Volume (Live)" in titles, data
    volume_section = next(s for s in sections if s.get("title") == "Data Volume (Live)")
    assert volume_section.get("data_table") == host_metrics, data


@pytest.mark.django_db(transaction=True)
def test_fix_suggest_returns_completed(django_store, cfg, stub_llm):
    from ai.engine_runtime import dispatch_task

    payload = {"issue_type": "null_values", "table_name": "emissions",
               "issue_description": "co2e_kg has 42 nulls", "affected_rows": 42}
    data = dispatch_task("carbon.fix.suggest", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert result.get("issue_type") == "null_values", data
    assert result.get("table_name") == "emissions", data
    suggestions = result.get("suggestions")
    assert isinstance(suggestions, list) and suggestions, data
    for key in ("description", "confidence", "suggested_action_type"):
        assert key in suggestions[0], (key, data)


# ── Fail-visible + deterministic-fallback tests ──────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("task_type", KG_TASKS)
def test_kg_dispatch_is_fail_visible(django_store, cfg, monkeypatch, task_type):
    """A raising handler surfaces pulse_unavailable (never a fabricated win)."""
    import ai.engine_runtime as rt

    async def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setitem(rt._TASK_HANDLERS, task_type, _boom)
    data = rt.dispatch_task(task_type, {}, instance_id="carbon")

    assert data.get("status") == "pulse_unavailable", (task_type, data)
    assert data.get("error", {}).get("code") == "engine_error", (task_type, data)


@pytest.mark.django_db(transaction=True)
def test_query_nl_engine_error_is_fail_visible(django_store, cfg, stub_llm):
    """A genuine engine error (host-DB failure) is surfaced, not swallowed."""
    from ai.engine_runtime import dispatch_task

    with patch("ai.engine.knowledge_graph.engine.ExecutionEngine.execute",
               side_effect=RuntimeError("host db down")):
        data = dispatch_task(
            "carbon.query.nl",
            {"question": "hi", "tables": ["emissions"]},
            instance_id="carbon",
        )

    assert data.get("status") == "pulse_unavailable", data
    assert data.get("error", {}).get("code") == "engine_error", data


@pytest.mark.django_db(transaction=True)
def test_llm_unavailable_degrades_to_deterministic(django_store, cfg):
    """With no LLM, the explain handler still completes via its deterministic
    fallback — nothing is fabricated and nothing raises."""
    from ai.engine_runtime import dispatch_task

    with patch("ai.engine.llm.router.route_chat", side_effect=RuntimeError("no key")):
        data = dispatch_task(
            "carbon.query.explain",
            {"sql": "SELECT * FROM emissions", "question": "what is this?"},
            instance_id="carbon",
        )

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert result.get("explanation"), data
    assert isinstance(result.get("caveats"), list)
