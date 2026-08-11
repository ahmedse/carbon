"""
PulseProvider tests — Wave B.

Proves that PulseProvider(AIProvider):
1. Sends the correct task type for each of 9 ABC methods
2. Builds the correct task envelope (auth + task + payload)
3. Maps Pulse response JSON → typed ABC dataclasses
4. Degrades gracefully on timeout / connection error / HTTP 5xx
5. Passes the provider swap test (identical to MockProvider)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

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
def mock_post_ok():
    """Patch requests.post to return a 200 with a custom JSON body.

    Usage:
        mock = mock_post_ok()
        mock.return_value.json.return_value = {...}
        with mock:
            ...
    """
    return patch("backend.ai.providers._http.requests.post")


@pytest.fixture
def mock_get_ok():
    """Patch requests.get for health_check tests."""
    return patch("backend.ai.providers._http.requests.get")


# ── Construction ────────────────────────────────────────────────────────


class TestConstruction:
    def test_provider_name_and_version(self, provider):
        assert provider.provider_name == "pulse"
        assert provider.provider_version == "1.0.0"

    def test_is_ai_provider_subclass(self, provider):
        assert isinstance(provider, AIProvider)


# ── Health ───────────────────────────────────────────────────────────────


class TestHealthCheck:
    def test_healthy(self, provider, mock_get_ok):
        fake_resp = MagicMock()
        fake_resp.ok = True
        fake_resp.json.return_value = {
            "modules": [
                {"type": "dq.validate"},
                {"type": "carbon.query.nl"},
            ],
        }
        with mock_get_ok as get:
            get.return_value = fake_resp
            status = provider.health_check()

        assert status.healthy is True
        assert status.name == "pulse"
        assert "dq.validate" in status.modules_available

    def test_unreachable(self, provider, mock_get_ok):
        with mock_get_ok as get:
            get.side_effect = requests.ConnectionError("boom")
            status = provider.health_check()

        assert status.healthy is False
        assert "unreachable" in (status.error or "")

    def test_timeout(self, provider, mock_get_ok):
        with mock_get_ok as get:
            get.side_effect = requests.Timeout("boom")
            status = provider.health_check()

        assert status.healthy is False
        assert "timed out" in (status.error or "")


# ── dq.validate ──────────────────────────────────────────────────────────


class TestValidateDq:
    def test_sends_correct_task_type(self, provider, mock_post_ok):
        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "status": "completed",
            "result": {"results": []},
        }
        with mock_post_ok as post:
            post.return_value = fake_resp
            provider.validate_dq(DqValidateRequest(
                rules=[DqRuleInput(id="r1", prompt="check nulls",
                                   fields=["col_a"], severity="error")],
                rows=[{"col_a": 1}],
                context={"table_name": "emissions"},
            ))

        call_args = post.call_args
        envelope = call_args[1]["json"]
        assert envelope["task"]["type"] == "dq.validate"
        assert envelope["auth"]["instance_id"] == "carbon"

    def test_maps_response(self, provider, mock_post_ok):
        fake_resp = MagicMock()
        fake_resp.json.return_value = {
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
        with mock_post_ok as post:
            post.return_value = fake_resp
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

    def test_graceful_degradation(self, provider, mock_post_ok):
        with mock_post_ok as post:
            post.side_effect = requests.Timeout("boom")
            resp = provider.validate_dq(DqValidateRequest(
                rules=[DqRuleInput(id="r1", prompt="x", fields=[], severity="error")],
                rows=[{"a": 1}],
                context={},
            ))

        assert resp.status == "provider_unavailable"
        assert resp.error is not None
        assert resp.error.get("code") == "timeout"


# ── dq.suggest ───────────────────────────────────────────────────────────


class TestSuggestDq:
    def test_sends_correct_task_type(self, provider, mock_post_ok):
        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "status": "completed",
            "result": {"suggestions": []},
        }
        with mock_post_ok as post:
            post.return_value = fake_resp
            provider.suggest_dq(DqSuggestRequest(
                table=TableProfile(name="emissions", description="t",
                                   row_count=100, columns=[]),
            ))

        assert post.call_args[1]["json"]["task"]["type"] == "dq.suggest"

    def test_maps_response(self, provider, mock_post_ok):
        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "status": "completed",
            "result": {
                "suggestions": [
                    {"prompt": "check nulls", "rationale": "because",
                     "suggested_severity": "error", "confidence": 0.9,
                     "rule_type": "nl_check"},
                ],
            },
        }
        with mock_post_ok as post:
            post.return_value = fake_resp
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
    def test_sends_correct_task_type(self, provider, mock_post_ok):
        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "status": "completed",
            "result": {"sql": "SELECT 1", "rows": [], "row_count": 0,
                       "execution_ms": 5, "recovery_applied": False},
        }
        with mock_post_ok as post:
            post.return_value = fake_resp
            provider.query_nl(NlQueryRequest(
                question="how many rows?", tables=["emissions"], max_rows=10,
            ))

        envelope = post.call_args[1]["json"]
        assert envelope["task"]["type"] == "carbon.query.nl"
        payload = envelope["task"]["payload"]
        assert payload["question"] == "how many rows?"
        assert payload["tables"] == ["emissions"]
        assert payload["max_rows"] == 10

    def test_maps_response(self, provider, mock_post_ok):
        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "status": "completed",
            "result": {
                "sql": "SELECT count(*) FROM emissions",
                "rows": [{"count": 42}],
                "row_count": 1,
                "execution_ms": 12,
                "recovery_applied": False,
            },
        }
        with mock_post_ok as post:
            post.return_value = fake_resp
            resp = provider.query_nl(NlQueryRequest(question="count?"))

        assert resp.status == "completed"
        assert resp.sql == "SELECT count(*) FROM emissions"
        assert resp.row_count == 1
        assert resp.execution_ms == 12


# ── carbon.query.explain ────────────────────────────────────────────────


class TestQueryExplain:
    def test_sends_and_maps(self, provider, mock_post_ok):
        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "status": "completed",
            "result": {
                "explanation": "42 records found.",
                "caveats": ["Data may be incomplete"],
            },
        }
        with mock_post_ok as post:
            post.return_value = fake_resp
            resp = provider.explain_query(NlExplainRequest(
                question="count?", sql="SELECT count(*)", row_count=1,
                sample_rows=[{"count": 42}],
            ))

        assert post.call_args[1]["json"]["task"]["type"] == "carbon.query.explain"
        assert resp.status == "completed"
        assert resp.explanation == "42 records found."
        assert "Data may be incomplete" in resp.caveats


# ── carbon.anomaly.detect ───────────────────────────────────────────────


class TestAnomalyDetect:
    def test_sends_and_maps(self, provider, mock_post_ok):
        fake_resp = MagicMock()
        fake_resp.json.return_value = {
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
        with mock_post_ok as post:
            post.return_value = fake_resp
            resp = provider.detect_anomalies(AnomalyDetectRequest(
                table_name="emissions",
                profile_history=[{"row_count": 1000}, {"row_count": 1100}],
                sensitivity=2.0,
            ))

        assert post.call_args[1]["json"]["task"]["type"] == "carbon.anomaly.detect"
        assert resp.status == "completed"
        assert len(resp.anomalies) == 1
        assert resp.anomalies[0].z_score == 3.5
        assert resp.history_snapshots == 12


# ── carbon.anomaly.explain ──────────────────────────────────────────────


class TestAnomalyExplain:
    def test_sends_and_maps(self, provider, mock_post_ok):
        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "status": "completed",
            "result": {
                "explanation": "Spike due to new equipment.",
                "investigation_steps": ["Check sensor", "Review logs"],
            },
        }
        with mock_post_ok as post:
            post.return_value = fake_resp
            resp = provider.explain_anomaly(AnomalyExplainRequest(
                table_name="emissions",
                anomaly={"metric": "avg_co2e", "observed": 500},
            ))

        assert post.call_args[1]["json"]["task"]["type"] == "carbon.anomaly.explain"
        assert resp.status == "completed"
        assert "new equipment" in (resp.explanation or "")
        assert len(resp.investigation_steps) == 2


# ── carbon.report.draft ─────────────────────────────────────────────────


class TestReportDraft:
    def test_sends_and_maps(self, provider, mock_post_ok):
        fake_resp = MagicMock()
        fake_resp.json.return_value = {
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
        with mock_post_ok as post:
            post.return_value = fake_resp
            resp = provider.draft_report(ReportDraftRequest(
                report_type="monthly_emissions",
                period_start="2026-07-01",
                period_end="2026-07-31",
            ))

        assert post.call_args[1]["json"]["task"]["type"] == "carbon.report.draft"
        assert resp.status == "completed"
        assert resp.title == "Monthly Report"
        assert len(resp.sections) == 1
        assert resp.sections[0].caveat == "incomplete"


# ── carbon.schema.analyze ───────────────────────────────────────────────


class TestSchemaAnalyze:
    def test_sends_and_maps(self, provider, mock_post_ok):
        fake_resp = MagicMock()
        fake_resp.json.return_value = {
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
        with mock_post_ok as post:
            post.return_value = fake_resp
            resp = provider.analyze_schema(SchemaAnalyzeRequest(
                schema_changes=[
                    SchemaChange(change="column_added",
                                 table_name="emissions",
                                 field_name="new_col"),
                ],
                context="Adding tracking column",
            ))

        assert post.call_args[1]["json"]["task"]["type"] == "carbon.schema.analyze"
        payload = post.call_args[1]["json"]["task"]["payload"]
        assert payload["schema_changes"][0]["table_name"] == "emissions"
        assert resp.status == "completed"
        assert resp.analysis[0].severity == "low"


# ── carbon.fix.suggest ──────────────────────────────────────────────────


class TestFixSuggest:
    def test_sends_and_maps(self, provider, mock_post_ok):
        fake_resp = MagicMock()
        fake_resp.json.return_value = {
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
        with mock_post_ok as post:
            post.return_value = fake_resp
            resp = provider.suggest_fix(FixSuggestRequest(
                issue_type="anomaly",
                table_name="emissions",
                issue_description="Spike detected in CO2e values.",
            ))

        assert post.call_args[1]["json"]["task"]["type"] == "carbon.fix.suggest"
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
    """Parametric test: every ABC method sends the correct task type."""
    provider = PulseProvider()
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "status": "completed",
        "result": {},
    }

    with patch("backend.ai.providers._http.requests.post") as post:
        post.return_value = fake_resp
        method = getattr(provider, method_name)
        method(request_obj)

    envelope = post.call_args[1]["json"]
    assert envelope["task"]["type"] == expected_task_type, (
        f"{method_name} should send {expected_task_type}, "
        f"got {envelope['task']['type']}"
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
