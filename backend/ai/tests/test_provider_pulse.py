"""
PulseProvider tests — Wave B (in-process, Phase 2).

Proves that PulseProvider(AIProvider):
1. Dispatches the correct task type for each ABC method
2. Builds the correct payload for each ABC method
3. Maps engine result dicts → typed ABC dataclasses
4. Degrades gracefully on engine error (provider_unavailable)
5. Passes the provider swap test (identical to MockProvider)

No HTTP — the engine is wired in-process via ``ai.engine_runtime``.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.ai.protocol import (
    AIProvider,
    AnomalyDetectRequest,
    AnomalyExplainRequest,
    DetectedAnomaly,
    DqRuleInput,
    DqSuggestRequest,
    DqSuggestion,
    DqValidateRequest,
    FixSuggestRequest,
    NlExplainRequest,
    NlQueryRequest,
    ReportDraftRequest,
    SchemaAnalyzeRequest,
    SchemaChange,
    TableProfile,
)
from backend.ai.providers.pulse import PulseProvider


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def provider() -> PulseProvider:
    return PulseProvider()


@pytest.fixture
def mock_dispatch():
    """Patch the in-process engine dispatch seam.

    Usage:
        mock = mock_dispatch()
        mock.return_value = {"status": "completed", "result": {...}}
        with mock as dispatch:
            ...
    """
    return patch("backend.ai.providers.pulse.dispatch_task")


@pytest.fixture
def mock_list_modules():
    """Patch the in-process module listing for health_check tests."""
    return patch("backend.ai.providers.pulse.list_modules")


def _task_type(dispatch) -> str:
    """Extract the task type from a dispatch mock (first positional arg)."""
    return dispatch.call_args.args[0]


def _payload(dispatch) -> dict:
    """Extract the payload from a dispatch mock (second positional arg)."""
    return dispatch.call_args.args[1]


# ── Construction ────────────────────────────────────────────────────────


class TestConstruction:
    def test_provider_name_and_version(self, provider):
        assert provider.provider_name == "pulse"
        assert provider.provider_version == "1.0.0"

    def test_is_ai_provider_subclass(self, provider):
        assert isinstance(provider, AIProvider)


# ── Health ───────────────────────────────────────────────────────────────


class TestHealthCheck:
    def test_healthy(self, provider, mock_list_modules):
        with mock_list_modules as list_modules:
            list_modules.return_value = {
                "modules": [
                    {"type": "dq.validate"},
                    {"type": "carbon.query.nl"},
                ],
            }
            status = provider.health_check()

        assert status.healthy is True
        assert status.name == "pulse"
        assert "dq.validate" in status.modules_available

    def test_reports_unhealthy_on_engine_error(self, provider, mock_list_modules):
        with mock_list_modules as list_modules:
            list_modules.return_value = {
                "modules": [],
                "error": {"code": "not_wired", "message": "engine offline"},
            }
            status = provider.health_check()

        assert status.healthy is False
        assert "not_wired" in (status.error or "")


# ── dq.validate ──────────────────────────────────────────────────────────


class TestValidateDq:
    def test_sends_correct_task_type(self, provider, mock_dispatch):
        with mock_dispatch as dispatch:
            dispatch.return_value = {
                "status": "completed",
                "result": {"results": []},
            }
            provider.validate_dq(DqValidateRequest(
                rules=[DqRuleInput(id="r1", prompt="check nulls",
                                   fields=["col_a"], severity="error")],
                rows=[{"col_a": 1}],
                context={"table_name": "emissions"},
            ))

        assert _task_type(dispatch) == "dq.validate"
        payload = _payload(dispatch)
        assert payload["rules"][0]["id"] == "r1"
        assert payload["rows"] == [{"col_a": 1}]
        assert payload["context"]["table_name"] == "emissions"

    def test_maps_response(self, provider, mock_dispatch):
        with mock_dispatch as dispatch:
            dispatch.return_value = {
                "status": "completed",
                "result": {
                    "results": [
                        {"rule_id": "r1", "status": "pass",
                         "passed": 1, "failed": 0, "total": 1,
                         "details": [{"row_id": 1, "passed": True,
                                      "explanation": "ok"}]},
                        {"rule_id": "r2", "status": "fail",
                         "passed": 0, "failed": 1, "total": 1,
                         "details": [{"row_id": 1, "passed": False,
                                      "explanation": "null found"}]},
                    ],
                },
            }
            resp = provider.validate_dq(DqValidateRequest(
                rules=[
                    DqRuleInput(id="r1", prompt="x", fields=[], severity="error"),
                    DqRuleInput(id="r2", prompt="y", fields=[], severity="error"),
                ],
                rows=[{"a": 1}],
                context={},
            ))

        assert resp.status == "completed"
        assert len(resp.results) == 2
        assert resp.results[0].status == "pass"
        assert resp.results[1].status == "fail"
        assert resp.results[1].failing_rows == [0]

    def test_graceful_degradation(self, provider, mock_dispatch):
        with mock_dispatch as dispatch:
            dispatch.return_value = {
                "status": "pulse_unavailable",
                "error": {"code": "not_wired", "message": "unavailable"},
            }
            resp = provider.validate_dq(DqValidateRequest(
                rules=[DqRuleInput(id="r1", prompt="x", fields=[], severity="error")],
                rows=[{"a": 1}],
                context={},
            ))

        assert resp.status == "provider_unavailable"
        assert resp.error is not None
        assert resp.error.get("code") == "not_wired"


# ── dq.suggest ───────────────────────────────────────────────────────────


class TestSuggestDq:
    def test_sends_correct_task_type(self, provider, mock_dispatch):
        with mock_dispatch as dispatch:
            dispatch.return_value = {
                "status": "completed",
                "result": {"suggestions": []},
            }
            provider.suggest_dq(DqSuggestRequest(
                table=TableProfile(name="emissions", description="t",
                                   row_count=100, columns=[]),
            ))

        assert _task_type(dispatch) == "dq.suggest"
        assert _payload(dispatch)["table"]["name"] == "emissions"

    def test_maps_response(self, provider, mock_dispatch):
        with mock_dispatch as dispatch:
            dispatch.return_value = {
                "status": "completed",
                "result": {
                    "suggestions": [
                        {"prompt": "check nulls", "rationale": "because",
                         "suggested_severity": "error", "confidence": 0.9,
                         "rule_type": "nl_check"},
                    ],
                },
            }
            resp = provider.suggest_dq(DqSuggestRequest(
                table=TableProfile(name="t", description="d",
                                   row_count=1, columns=[]),
            ))

        assert resp.status == "completed"
        assert len(resp.suggestions) == 1
        assert resp.suggestions[0].severity == "error"
        assert resp.suggestions[0].confidence == 0.9
        assert "prompt" in resp.suggestions[0].definition


# ── carbon.query.nl ─────────────────────────────────────────────────────


class TestQueryNl:
    def test_sends_correct_task_type(self, provider, mock_dispatch):
        with mock_dispatch as dispatch:
            dispatch.return_value = {
                "status": "completed",
                "result": {"sql": "SELECT 1", "rows": [], "row_count": 0,
                           "execution_ms": 5, "recovery_applied": False},
            }
            provider.query_nl(NlQueryRequest(
                question="how many rows?", tables=["emissions"], max_rows=10,
            ))

        assert _task_type(dispatch) == "carbon.query.nl"
        payload = _payload(dispatch)
        assert payload["question"] == "how many rows?"
        assert payload["tables"] == ["emissions"]
        assert payload["max_rows"] == 10

    def test_maps_response(self, provider, mock_dispatch):
        with mock_dispatch as dispatch:
            dispatch.return_value = {
                "status": "completed",
                "result": {
                    "sql": "SELECT count(*) FROM emissions",
                    "rows": [{"count": 42}],
                    "row_count": 1,
                    "execution_ms": 12,
                    "recovery_applied": False,
                },
            }
            resp = provider.query_nl(NlQueryRequest(question="count?"))

        assert resp.status == "completed"
        assert resp.sql == "SELECT count(*) FROM emissions"
        assert resp.row_count == 1
        assert resp.execution_ms == 12


# ── carbon.query.explain ────────────────────────────────────────────────


class TestQueryExplain:
    def test_sends_and_maps(self, provider, mock_dispatch):
        with mock_dispatch as dispatch:
            dispatch.return_value = {
                "status": "completed",
                "result": {
                    "explanation": "42 records found.",
                    "caveats": ["Data may be incomplete"],
                },
            }
            resp = provider.explain_query(NlExplainRequest(
                question="count?", sql="SELECT count(*)", row_count=1,
                sample_rows=[{"count": 42}],
            ))

        assert _task_type(dispatch) == "carbon.query.explain"
        assert resp.status == "completed"
        assert resp.explanation == "42 records found."
        assert "Data may be incomplete" in resp.caveats


# ── carbon.anomaly.detect ───────────────────────────────────────────────


class TestAnomalyDetect:
    def test_sends_and_maps(self, provider, mock_dispatch):
        with mock_dispatch as dispatch:
            dispatch.return_value = {
                "status": "completed",
                "result": {
                    "anomalies": [
                        {"metric": "avg_co2e", "expected_range": {"low": 100, "high": 200},
                         "observed": 500, "z_score": 3.5, "severity": "error",
                         "explanation": "Spike detected"},
                    ],
                    "table_name": "emissions",
                    "history_snapshots": 12,
                },
            }
            resp = provider.detect_anomalies(AnomalyDetectRequest(
                table_name="emissions",
                profile_history=[{"row_count": 1000}, {"row_count": 1100}],
                sensitivity=2.0,
            ))

        assert _task_type(dispatch) == "carbon.anomaly.detect"
        assert resp.status == "completed"
        assert len(resp.anomalies) == 1
        assert resp.anomalies[0].z_score == 3.5
        assert resp.history_snapshots == 12


# ── carbon.anomaly.explain ──────────────────────────────────────────────


class TestAnomalyExplain:
    def test_sends_and_maps(self, provider, mock_dispatch):
        with mock_dispatch as dispatch:
            dispatch.return_value = {
                "status": "completed",
                "result": {
                    "explanation": "Spike due to new equipment.",
                    "investigation_steps": ["Check sensor", "Review logs"],
                },
            }
            resp = provider.explain_anomaly(AnomalyExplainRequest(
                table_name="emissions",
                anomaly={"metric": "avg_co2e", "observed": 500},
            ))

        assert _task_type(dispatch) == "carbon.anomaly.explain"
        assert resp.status == "completed"
        assert "new equipment" in (resp.explanation or "")
        assert len(resp.investigation_steps) == 2


# ── carbon.report.draft ─────────────────────────────────────────────────


class TestReportDraft:
    def test_sends_and_maps(self, provider, mock_dispatch):
        with mock_dispatch as dispatch:
            dispatch.return_value = {
                "status": "completed",
                "result": {
                    "title": "Monthly Report",
                    "summary": "All good.",
                    "report_type": "monthly_emissions",
                    "period_start": "2026-07-01",
                    "period_end": "2026-07-31",
                    "generated_at": "2026-08-11T00:00:00Z",
                    "sections": [
                        {"title": "Overview", "narrative": "OK",
                         "sql": "SELECT 1", "data_table": [{"x": 1}],
                         "caveats": ["incomplete"]},
                    ],
                },
            }
            resp = provider.draft_report(ReportDraftRequest(
                report_type="monthly_emissions",
                period_start="2026-07-01",
                period_end="2026-07-31",
            ))

        assert _task_type(dispatch) == "carbon.report.draft"
        assert resp.status == "completed"
        assert resp.title == "Monthly Report"
        assert len(resp.sections) == 1
        assert resp.sections[0].caveat == "incomplete"


# ── carbon.schema.analyze ───────────────────────────────────────────────


class TestSchemaAnalyze:
    def test_sends_and_maps(self, provider, mock_dispatch):
        with mock_dispatch as dispatch:
            dispatch.return_value = {
                "status": "completed",
                "result": {
                    "analysis": [
                        {"change": "column_added",
                         "impact": "New column for tracking.",
                         "severity": "low",
                         "suggested_action": "Update dashboards."},
                    ],
                },
            }
            resp = provider.analyze_schema(SchemaAnalyzeRequest(
                schema_changes=[
                    SchemaChange(change="column_added",
                                 table_name="emissions",
                                 field_name="new_col"),
                ],
                context="Adding tracking column",
            ))

        assert _task_type(dispatch) == "carbon.schema.analyze"
        payload = _payload(dispatch)
        assert payload["schema_changes"][0]["table_name"] == "emissions"
        assert resp.status == "completed"
        assert resp.analysis[0].severity == "low"


# ── carbon.fix.suggest ──────────────────────────────────────────────────


class TestFixSuggest:
    def test_sends_and_maps(self, provider, mock_dispatch):
        with mock_dispatch as dispatch:
            dispatch.return_value = {
                "status": "completed",
                "result": {
                    "issue_type": "anomaly",
                    "table_name": "emissions",
                    "suggestions": [
                        {"description": "Check ETL pipeline.",
                         "confidence": 0.85,
                         "estimated_affected_rows": 10,
                         "requires_confirmation": True,
                         "suggested_action_type": "investigation"},
                    ],
                },
            }
            resp = provider.suggest_fix(FixSuggestRequest(
                issue_type="anomaly",
                table_name="emissions",
                issue_description="Spike detected in CO2e values.",
            ))

        assert _task_type(dispatch) == "carbon.fix.suggest"
        assert resp.status == "completed"
        assert resp.suggestions[0].confidence == 0.85
        assert resp.suggestions[0].requires_confirmation is True


# ── All 9 task types enumerated ─────────────────────────────────────────

TASK_TYPE_MAP = [
    ("validate_dq", DqValidateRequest(
        rules=[DqRuleInput(id="r1", prompt="x", fields=[], severity="error")],
        rows=[{"a": 1}], context={},
    ), "dq.validate"),
    ("suggest_dq", DqSuggestRequest(
        table=TableProfile(name="t", description="d", row_count=1, columns=[]),
    ), "dq.suggest"),
    ("query_nl", NlQueryRequest(question="q?"), "carbon.query.nl"),
    ("explain_query", NlExplainRequest(
        question="q?", sql="SELECT 1", row_count=1, sample_rows=[],
    ), "carbon.query.explain"),
    ("detect_anomalies", AnomalyDetectRequest(
        table_name="t", profile_history=[],
    ), "carbon.anomaly.detect"),
    ("explain_anomaly", AnomalyExplainRequest(
        table_name="t", anomaly={},
    ), "carbon.anomaly.explain"),
    ("draft_report", ReportDraftRequest(
        report_type="monthly", period_start="2026-01-01",
        period_end="2026-01-31",
    ), "carbon.report.draft"),
    ("analyze_schema", SchemaAnalyzeRequest(
        schema_changes=[SchemaChange(change="add", table_name="t")],
    ), "carbon.schema.analyze"),
    ("suggest_fix", FixSuggestRequest(
        issue_type="anomaly", table_name="t",
        issue_description="Spike detected.",
    ), "carbon.fix.suggest"),
]


@pytest.mark.parametrize("method_name,request_obj,expected_task_type", TASK_TYPE_MAP)
def test_all_nine_task_types(method_name, request_obj, expected_task_type):
    """Parametric test: every ABC method dispatches the correct task type."""
    provider = PulseProvider()

    with patch("backend.ai.providers.pulse.dispatch_task") as dispatch:
        dispatch.return_value = {"status": "completed", "result": {}}
        method = getattr(provider, method_name)
        method(request_obj)

    assert _task_type(dispatch) == expected_task_type, (
        f"{method_name} should dispatch {expected_task_type}, "
        f"got {_task_type(dispatch)}"
    )


# ── Provider swap test ──────────────────────────────────────────────────


def test_pulse_provider_satisfies_abc():
    """PulseProvider passes isinstance check and has all 12 members."""
    p = PulseProvider()
    assert isinstance(p, AIProvider)

    # All 12 abstract members must be callable
    assert callable(p.health_check)
    assert callable(p.validate_dq)
    assert callable(p.suggest_dq)
    assert callable(p.query_nl)
    assert callable(p.explain_query)
    assert callable(p.detect_anomalies)
    assert callable(p.explain_anomaly)
    assert callable(p.draft_report)
    assert callable(p.analyze_schema)
    assert callable(p.suggest_fix)
    assert hasattr(p, "provider_name")
    assert hasattr(p, "provider_version")
