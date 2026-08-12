"""
Dataclass integrity tests — round-trips, defaults, type correctness.

14 tests proving the protocol contract holds. All self-contained —
no Django, no HTTP, no database.
"""

import dataclasses
import typing

from backend.ai.protocol import (
    ConversationContext,
    Scope, ProviderStatus,
    DqRuleInput, DqRuleResult, DqValidateRequest, DqValidateResponse,
    TableProfile, DqSuggestRequest, DqSuggestResponse, DqSuggestion,
    NlQueryRequest, NlQueryResponse,
    NlExplainRequest, NlExplainResponse,
    AnomalyDetectRequest, AnomalyDetectResponse, DetectedAnomaly,
    AnomalyExplainRequest, AnomalyExplainResponse,
    ReportDraftRequest, ReportDraftResponse, ReportSection,
    SchemaChange, SchemaAnalyzeRequest, SchemaAnalyzeResponse, SchemaImpact,
    FixSuggestRequest, FixSuggestResponse, FixSuggestion,
)


# ── Helpers ─────────────────────────────────────────────────────────────


def _assert_roundtrip(request_obj, cls):
    """Generic round-trip: asdict → reconstruct → type-check."""
    d = dataclasses.asdict(request_obj)
    reconstructed = cls(**d)
    assert isinstance(reconstructed, cls)
    return reconstructed


# ── Test 1: Scope defaults ──────────────────────────────────────────────


def test_scope_defaults():
    """Scope instantiates with all defaults correctly."""
    s = Scope()
    assert s.org_unit_ids == []
    assert s.module_ids == []
    assert s.is_read_only is False
    assert s.is_superuser is False
    assert s.user_identifier == ""


# ── Test 2: ProviderStatus round-trip ───────────────────────────────────


def test_provider_status_roundtrip():
    status = ProviderStatus(
        name="test", version="1.0", healthy=True,
        modules_available=["m1", "m2"],
    )
    r = _assert_roundtrip(status, ProviderStatus)
    assert r.name == "test"
    assert r.modules_available == ["m1", "m2"]


# ── Test 3: DQ Validate round-trip ─────────────────────────────────────


def test_dq_validate_roundtrip():
    """DqValidateRequest → asdict → reconstruct → assert equality."""
    request = DqValidateRequest(
        rules=[
            DqRuleInput(id="r1", prompt="Check not null", fields=["col_a"], severity="error"),
        ],
        rows=[{"col_a": 1, "col_b": "x"}, {"col_a": None, "col_b": "y"}],
        context={"source": "test"},
        scope=None,
    )
    d = dataclasses.asdict(request)
    reconstructed = DqValidateRequest(**d)
    # Nested dataclasses become dicts after asdict → ** reconstruction
    assert reconstructed.rules[0]["id"] == "r1"
    assert reconstructed.rows[1]["col_b"] == "y"
    assert reconstructed.context["source"] == "test"


# ── Test 4: DQ Suggest round-trip ──────────────────────────────────────


def test_dq_suggest_roundtrip():
    """DqSuggestRequest round-trip including nested TableProfile."""
    request = DqSuggestRequest(
        table=TableProfile(
            name="emissions", description="Carbon emissions data",
            row_count=5000, columns=[{"name": "co2e_kg", "type": "float"}],
        ),
        conversation=ConversationContext(
            conversation_id="conv-1",
            messages=[{"role": "user", "content": "suggest rules"}],
        ),
    )
    d = dataclasses.asdict(request)
    reconstructed = DqSuggestRequest(**d)
    # Nested TableProfile becomes dict after asdict → **
    assert reconstructed.table["name"] == "emissions"
    assert reconstructed.table["row_count"] == 5000
    assert reconstructed.conversation["conversation_id"] == "conv-1"


# ── Test 5: NL Query round-trip ────────────────────────────────────────


def test_nl_query_roundtrip():
    """NlQueryRequest with domain_vocabulary round-trip."""
    request = NlQueryRequest(
        question="Show total emissions by month",
        tables=["emissions"],
        conversation=ConversationContext(
            conversation_id="conv-2",
            messages=[{"role": "user", "content": "show totals"}],
        ),
        domain_vocabulary={"emissions": "Carbon emission records"},
    )
    r = _assert_roundtrip(request, NlQueryRequest)
    assert r.question == "Show total emissions by month"
    assert r.domain_vocabulary["emissions"] == "Carbon emission records"
    assert r.conversation["conversation_id"] == "conv-2"


# ── Test 6: NL Explain round-trip ──────────────────────────────────────


def test_nl_explain_roundtrip():
    request = NlExplainRequest(
        question="Show emissions",
        sql="SELECT * FROM emissions",
        row_count=42,
        sample_rows=[{"co2e_kg": 100}, {"co2e_kg": 200}],
    )
    r = _assert_roundtrip(request, NlExplainRequest)
    assert r.sql == "SELECT * FROM emissions"
    assert r.row_count == 42


# ── Test 7: Anomaly Detect round-trip ──────────────────────────────────


def test_anomaly_detect_roundtrip():
    """AnomalyDetectRequest round-trip including profile_history."""
    request = AnomalyDetectRequest(
        table_name="emissions",
        profile_history=[{"avg_co2e": 250.0}, {"avg_co2e": 260.0}],
        sensitivity=2.5,
        volume_threshold_pct=25.0,
        conversation=ConversationContext(
            conversation_id="conv-3",
            messages=[{"role": "assistant", "content": "prior anomaly"}],
        ),
    )
    r = _assert_roundtrip(request, AnomalyDetectRequest)
    assert r.table_name == "emissions"
    assert r.sensitivity == 2.5
    assert r.volume_threshold_pct == 25.0
    assert r.conversation["conversation_id"] == "conv-3"


# ── Test 8: Anomaly Explain round-trip ─────────────────────────────────


def test_anomaly_explain_roundtrip():
    request = AnomalyExplainRequest(
        table_name="emissions",
        anomaly={"metric": "avg_co2e", "z_score": 3.5},
    )
    r = _assert_roundtrip(request, AnomalyExplainRequest)
    assert r.anomaly["z_score"] == 3.5


# ── Test 9: Report Draft round-trip ────────────────────────────────────


def test_report_draft_roundtrip():
    """ReportDraftRequest → ReportDraftResponse round-trip including nested ReportSection."""
    request = ReportDraftRequest(
        report_type="monthly_emissions",
        period_start="2026-08-01",
        period_end="2026-08-31",
    )
    r = _assert_roundtrip(request, ReportDraftRequest)
    assert r.report_type == "monthly_emissions"

    response = ReportDraftResponse(
        status="completed",
        title="Test Report",
        summary="Test summary",
        sections=[ReportSection(
            title="S1", content="Markdown content",
            sql="SELECT 1", data=[{"k": "v"}],
            narrative="Narrative text", caveat="Sample only",
        )],
    )
    d = dataclasses.asdict(response)
    rr = ReportDraftResponse(**d)
    # Nested ReportSection becomes dict after asdict → **
    assert rr.sections[0]["title"] == "S1"
    assert rr.sections[0]["narrative"] == "Narrative text"


# ── Test 10: Schema Analyze round-trip ──────────────────────────────────


def test_schema_analyze_roundtrip():
    """SchemaAnalyzeRequest → SchemaAnalyzeResponse round-trip including nested SchemaImpact."""
    request = SchemaAnalyzeRequest(
        schema_changes=[SchemaChange(change="column_added", table_name="emissions", field_name="new_col")],
        context="Adding column for new regulation",
    )
    r = _assert_roundtrip(request, SchemaAnalyzeRequest)
    # SchemaChange becomes dict; field_name is accessible via dict key
    assert r.schema_changes[0]["field_name"] == "new_col"

    response = SchemaAnalyzeResponse(
        status="completed",
        analysis=[SchemaImpact(
            change="column_added", impact="New column requires schema migration",
            severity="medium", suggested_action="Run migrations carefully",
        )],
    )
    d = dataclasses.asdict(response)
    rr = SchemaAnalyzeResponse(**d)
    assert rr.analysis[0]["severity"] == "medium"


# ── Test 11: Fix Suggest round-trip ─────────────────────────────────────


def test_fix_suggest_roundtrip():
    """FixSuggestRequest → FixSuggestResponse round-trip."""
    request = FixSuggestRequest(
        issue_type="anomaly",
        table_name="emissions",
        issue_description="co2e_kg spike detected",
        affected_rows=[{"id": 1}, {"id": 2}],
        profile={"total_rows": 5000},
    )
    r = _assert_roundtrip(request, FixSuggestRequest)
    assert r.issue_type == "anomaly"
    assert r.profile["total_rows"] == 5000
    assert r.affected_rows is not None

    response = FixSuggestResponse(
        status="completed",
        issue_type="anomaly",
        table_name="emissions",
        suggestions=[FixSuggestion(
            description="Investigate source",
            confidence=0.9,
            estimated_affected_rows=5,
            requires_confirmation=True,
            suggested_action_type="investigation",
        )],
    )
    d = dataclasses.asdict(response)
    rr = FixSuggestResponse(**d)
    # Nested FixSuggestion becomes dict after asdict → **
    assert rr.suggestions[0]["requires_confirmation"] is True


# ── Test 12: All responses have status field ────────────────────────────


def test_all_responses_have_status_field():
    """Every *Response dataclass has status: str."""
    responses = [
        DqValidateResponse(status="completed"),
        DqSuggestResponse(status="completed"),
        NlQueryResponse(status="completed"),
        NlExplainResponse(status="completed"),
        AnomalyDetectResponse(status="completed"),
        AnomalyExplainResponse(status="completed"),
        ReportDraftResponse(status="completed"),
        SchemaAnalyzeResponse(status="completed"),
        FixSuggestResponse(status="completed"),
    ]
    for resp in responses:
        assert hasattr(resp, "status"), f"{type(resp).__name__} missing 'status'"
        assert isinstance(resp.status, str), f"{type(resp).__name__}.status is not str"
        assert resp.status == "completed"


# ── Test 13: FixSuggestion.requires_confirmation always True ────────────


def test_fix_suggest_requires_confirmation():
    """FixSuggestion.requires_confirmation must be True — no auto-fix."""
    suggestion = FixSuggestion(
        description="Test fix",
        confidence=0.95,
        estimated_affected_rows=10,
        requires_confirmation=True,
        suggested_action_type="fix",
    )
    assert suggestion.requires_confirmation is True

    # Verify it's a bool field (not optional); use get_type_hints for PEP 563
    hints = typing.get_type_hints(FixSuggestion)
    assert hints["requires_confirmation"] is bool


# ── Test 14: All Response error defaults to None ────────────────────────


def test_response_error_defaults_to_none():
    """All *Response.error defaults to None."""
    responses = [
        DqValidateResponse(status="completed"),
        DqSuggestResponse(status="completed"),
        NlQueryResponse(status="completed"),
        NlExplainResponse(status="completed"),
        AnomalyDetectResponse(status="completed"),
        AnomalyExplainResponse(status="completed"),
        ReportDraftResponse(status="completed"),
        SchemaAnalyzeResponse(status="completed"),
        FixSuggestResponse(status="completed"),
    ]
    for resp in responses:
        assert resp.error is None, f"{type(resp).__name__}.error should default to None, got {resp.error}"
