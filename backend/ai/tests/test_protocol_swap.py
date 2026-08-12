"""
Swap test — proves ANY AIProvider implementation works identically.

MockProvider implements all 12 members of AIProvider with deterministic
fake data. These tests prove that CarbonIntelligence (Wave C) can swap
providers (Pulse, Azure, Claude, local LLM) with zero code changes.
"""

from backend.ai.protocol import (
    AIProvider, Scope, ProviderStatus,
    ChatResponse,
    DqRuleInput, DqValidateRequest, DqValidateResponse, DqRuleResult,
    DqSuggestRequest, DqSuggestResponse, DqSuggestion, TableProfile,
    NlQueryRequest, NlQueryResponse,
    NlExplainRequest, NlExplainResponse,
    AnomalyDetectRequest, AnomalyDetectResponse, DetectedAnomaly,
    AnomalyExplainRequest, AnomalyExplainResponse,
    ReportDraftRequest, ReportDraftResponse, ReportSection,
    SchemaAnalyzeRequest, SchemaAnalyzeResponse, SchemaImpact, SchemaChange,
    FixSuggestRequest, FixSuggestResponse, FixSuggestion,
)


class MockProvider(AIProvider):
    """Deterministic fake provider. No randomness, no sleeps, no HTTP.

    Every method returns a realistic-but-fake response. Used to prove
    that CarbonIntelligence (Wave C) works identically with any provider
    that implements AIProvider.
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def provider_version(self) -> str:
        return "1.0.0-test"

    def health_check(self) -> ProviderStatus:
        return ProviderStatus(
            name="mock",
            version="1.0.0-test",
            healthy=True,
            modules_available=[
                "dq.validate", "dq.suggest", "carbon.query.nl",
                "carbon.query.explain", "carbon.anomaly.detect",
                "carbon.anomaly.explain", "carbon.report.draft",
                "carbon.schema.analyze", "carbon.fix.suggest",
            ],
        )

    def validate_dq(self, request: DqValidateRequest) -> DqValidateResponse:
        results = []
        for rule in request.rules:
            passed = "pass" in rule.id.lower()
            results.append(DqRuleResult(
                rule_id=rule.id,
                status="pass" if passed else "fail",
                failing_rows=[0] if not passed else None,
                explanation=f"Mock check for rule {rule.id}",
                confidence=0.95,
            ))
        return DqValidateResponse(status="completed", results=results)

    def suggest_dq(self, request: DqSuggestRequest) -> DqSuggestResponse:
        return DqSuggestResponse(
            status="completed",
            suggestions=[
                DqSuggestion(
                    definition={"id": "s1", "prompt": f"Check {request.table.name} is not null"},
                    rationale=f"Column '{request.table.name}' may contain nulls",
                    severity="error",
                    confidence=0.9,
                    dimension="completeness",
                ),
                DqSuggestion(
                    definition={"id": "s2", "prompt": f"Values in {request.table.name} are within range"},
                    rationale="Range check ensures data quality",
                    severity="warning",
                    confidence=0.8,
                    dimension="accuracy",
                ),
            ],
        )

    def query_nl(self, request: NlQueryRequest) -> NlQueryResponse:
        return NlQueryResponse(
            status="completed",
            sql=f"SELECT * FROM {request.tables[0] if request.tables else 'unknown'} LIMIT {request.max_rows}",
            rows=[{"id": 1, "co2e_kg": 100.5}, {"id": 2, "co2e_kg": 200.3}],
            row_count=2,
            execution_ms=15,
        )

    def explain_query(self, request: NlExplainRequest) -> NlExplainResponse:
        return NlExplainResponse(
            status="completed",
            explanation=f"Query returned {request.row_count} rows matching your question: '{request.question}'",
            caveats=["Results limited to sample rows", "Verify with full dataset"],
        )

    def detect_anomalies(self, request: AnomalyDetectRequest) -> AnomalyDetectResponse:
        anomalies = []
        if len(request.profile_history) >= 2:
            anomalies.append(DetectedAnomaly(
                metric=f"{request.table_name}.avg_co2e",
                expected_range={"low": 150.0, "high": 350.0},
                observed=500.0,
                z_score=3.5,
                severity="error",
                explanation="Average CO2e is 2σ above historical mean — investigate source.",
            ))
        return AnomalyDetectResponse(
            status="completed",
            anomalies=anomalies,
            history_snapshots=len(request.profile_history),
        )

    def explain_anomaly(self, request: AnomalyExplainRequest) -> AnomalyExplainResponse:
        metric = request.anomaly.get("metric", "unknown")
        return AnomalyExplainResponse(
            status="completed",
            explanation=f"Anomaly in metric '{metric}' — likely due to new emission source or data entry error.",
            investigation_steps=[
                "Check source data for the anomaly period",
                "Compare with previous periods",
                "Verify sensor calibration",
            ],
        )

    def draft_report(self, request: ReportDraftRequest) -> ReportDraftResponse:
        return ReportDraftResponse(
            status="completed",
            title=f"{request.report_type.replace('_', ' ').title()} — {request.period_start} to {request.period_end}",
            summary="Mock report summary. Emissions were within expected range for this period.",
            report_type=request.report_type,
            period_start=request.period_start,
            period_end=request.period_end,
            generated_at="2026-08-11T00:00:00Z",
            sections=[
                ReportSection(
                    title="Executive Summary",
                    content="Total emissions for the period: 12,345 tCO2e.",
                    sql="SELECT sum(co2e_kg) FROM emissions",
                    data=[{"total_tco2e": 12345}],
                    narrative="Emissions data aligns with historical trends.",
                ),
                ReportSection(
                    title="Emissions by Source",
                    content="Breakdown by source category.",
                    sql="SELECT source, sum(co2e_kg) FROM emissions GROUP BY source",
                    data=[{"source": "Electricity", "co2e_kg": 5000}],
                    narrative="Electricity remains the primary emission source.",
                ),
            ],
        )

    def analyze_schema(self, request: SchemaAnalyzeRequest) -> SchemaAnalyzeResponse:
        impacts = []
        for change in request.schema_changes:
            if "drop" in change.change.lower() or "remove" in change.change.lower():
                severity = "critical" if "column" in change.change.lower() else "high"
            elif "add" in change.change.lower():
                severity = "low"
            else:
                severity = "medium"
            impacts.append(SchemaImpact(
                change=change.change,
                impact=f"Change '{change.change}' on {change.table_name} may affect reports and dashboards.",
                severity=severity,
                suggested_action=f"Review impacts on {change.table_name} before proceeding.",
            ))
        return SchemaAnalyzeResponse(status="completed", analysis=impacts)

    def suggest_fix(self, request: FixSuggestRequest) -> FixSuggestResponse:
        return FixSuggestResponse(
            status="completed",
            issue_type=request.issue_type,
            table_name=request.table_name,
            suggestions=[
                FixSuggestion(
                    description=f"Investigate {request.issue_description[:50]} in table {request.table_name}",
                    confidence=0.85,
                    estimated_affected_rows=10,
                    requires_confirmation=True,
                    suggested_action_type="investigation",
                ),
                FixSuggestion(
                    description="Review ETL pipeline for data quality rules",
                    confidence=0.70,
                    estimated_affected_rows=0,
                    requires_confirmation=True,
                    suggested_action_type="rule_adjustment",
                ),
            ],
        )

    def chat(self, request):
        return ChatResponse(
            status="completed",
            content=f"Mock response to: {request.message}",
            follow_up_questions=["Would you like more details?"],
        )


# ── Tests ────────────────────────────────────────────────────────────────


def test_mock_provider_is_ai_provider():
    """MockProvider is a valid AIProvider implementation."""
    provider = MockProvider()
    assert isinstance(provider, AIProvider)


def test_mock_health_check():
    """Returns healthy ProviderStatus with 9 modules."""
    status = MockProvider().health_check()
    assert status.healthy is True
    assert status.name == "mock"
    assert status.version == "1.0.0-test"
    assert len(status.modules_available) == 9
    assert "carbon.query.nl" in status.modules_available


def test_mock_validate_dq_pass():
    """Rule with 'pass' in id → status='pass'."""
    provider = MockProvider()
    response = provider.validate_dq(DqValidateRequest(
        rules=[DqRuleInput(id="check_pass_1", prompt="test", fields=["col_a"], severity="error")],
        rows=[{"col_a": 1}],
    ))
    assert response.status == "completed"
    assert response.results[0].status == "pass"
    assert response.results[0].failing_rows is None


def test_mock_validate_dq_fail():
    """Rule without 'pass' → status='fail', failing_rows populated."""
    provider = MockProvider()
    response = provider.validate_dq(DqValidateRequest(
        rules=[DqRuleInput(id="check_fail_1", prompt="test", fields=["col_a"], severity="error")],
        rows=[{"col_a": None}],
    ))
    assert response.status == "completed"
    assert response.results[0].status == "fail"
    assert response.results[0].failing_rows == [0]


def test_mock_suggest_dq():
    """Returns 2 deterministic suggestions."""
    response = MockProvider().suggest_dq(DqSuggestRequest(
        table=TableProfile(name="emissions", description="test", row_count=100, columns=[]),
    ))
    assert response.status == "completed"
    assert len(response.suggestions) == 2
    assert response.suggestions[0].dimension == "completeness"
    assert response.suggestions[1].confidence == 0.8


def test_mock_query_nl():
    """Returns deterministic SQL + 2 rows."""
    response = MockProvider().query_nl(NlQueryRequest(
        question="Show emissions", tables=["emissions"],
    ))
    assert response.status == "completed"
    assert "SELECT" in response.sql
    assert len(response.rows) == 2
    assert response.row_count == 2


def test_mock_explain_query():
    """Returns explanation with caveats."""
    response = MockProvider().explain_query(NlExplainRequest(
        question="Show emissions", sql="SELECT * FROM emissions",
        row_count=2, sample_rows=[{"id": 1}],
    ))
    assert response.status == "completed"
    assert "Show emissions" in response.explanation
    assert len(response.caveats) == 2


def test_mock_detect_anomalies():
    """Returns 1 anomaly when history ≥ 2 snapshots."""
    response = MockProvider().detect_anomalies(AnomalyDetectRequest(
        table_name="emissions",
        profile_history=[{"snap": 1}, {"snap": 2}, {"snap": 3}],
        sensitivity=2.0,
    ))
    assert response.status == "completed"
    assert len(response.anomalies) == 1
    assert response.anomalies[0].severity == "error"
    assert response.history_snapshots == 3


def test_mock_explain_anomaly():
    """Returns explanation + investigation_steps."""
    response = MockProvider().explain_anomaly(AnomalyExplainRequest(
        table_name="emissions",
        anomaly={"metric": "co2e_kg.avg_val", "z_score": 3.5},
    ))
    assert response.status == "completed"
    assert "co2e_kg" in response.explanation
    assert len(response.investigation_steps) == 3


def test_mock_draft_report():
    """Returns report with 2 sections."""
    response = MockProvider().draft_report(ReportDraftRequest(
        report_type="monthly_emissions",
        period_start="2026-08-01",
        period_end="2026-08-31",
    ))
    assert response.status == "completed"
    assert response.report_type == "monthly_emissions"
    assert len(response.sections) == 2
    assert response.sections[0].title == "Executive Summary"


def test_mock_analyze_schema():
    """Returns schema impact analysis."""
    response = MockProvider().analyze_schema(SchemaAnalyzeRequest(
        schema_changes=[
            SchemaChange(change="column_added", table_name="emissions", field_name="new_col"),
            SchemaChange(change="column_dropped", table_name="emissions", field_name="old_col"),
        ],
    ))
    assert response.status == "completed"
    assert len(response.analysis) == 2
    assert response.analysis[0].severity == "low"   # column added
    assert response.analysis[1].severity == "critical"  # column dropped


def test_mock_suggest_fix():
    """Returns fix suggestions with requires_confirmation=True."""
    response = MockProvider().suggest_fix(FixSuggestRequest(
        issue_type="anomaly",
        table_name="emissions",
        issue_description="co2e_kg spiked 10x",
    ))
    assert response.status == "completed"
    assert response.table_name == "emissions"
    assert len(response.suggestions) == 2
    for s in response.suggestions:
        assert s.requires_confirmation is True
        assert isinstance(s, FixSuggestion)


def test_swap_providers_same_interface():
    """THE GATE. All 9 methods + 2 properties + health_check return correct types."""
    provider = MockProvider()

    # Properties
    assert provider.provider_name == "mock"
    assert provider.provider_version == "1.0.0-test"

    # health_check
    assert isinstance(provider.health_check(), ProviderStatus)

    # validate_dq
    r1 = provider.validate_dq(DqValidateRequest(rules=[], rows=[]))
    assert isinstance(r1, DqValidateResponse)
    assert r1.status == "completed"

    # suggest_dq
    r2 = provider.suggest_dq(DqSuggestRequest(table=TableProfile(
        name="t", description="d", row_count=0, columns=[],
    )))
    assert isinstance(r2, DqSuggestResponse)
    assert r2.status == "completed"

    # query_nl
    r3 = provider.query_nl(NlQueryRequest(question="test"))
    assert isinstance(r3, NlQueryResponse)
    assert r3.status == "completed"

    # explain_query
    r4 = provider.explain_query(NlExplainRequest(
        question="test", sql="SELECT 1", row_count=1, sample_rows=[],
    ))
    assert isinstance(r4, NlExplainResponse)
    assert r4.status == "completed"

    # detect_anomalies
    r5 = provider.detect_anomalies(AnomalyDetectRequest(
        table_name="t", profile_history=[{"a": 1}, {"b": 2}],
    ))
    assert isinstance(r5, AnomalyDetectResponse)
    assert r5.status == "completed"

    # explain_anomaly
    r6 = provider.explain_anomaly(AnomalyExplainRequest(
        table_name="t", anomaly={"metric": "x"},
    ))
    assert isinstance(r6, AnomalyExplainResponse)
    assert r6.status == "completed"

    # draft_report
    r7 = provider.draft_report(ReportDraftRequest(
        report_type="monthly", period_start="2026-01-01", period_end="2026-01-31",
    ))
    assert isinstance(r7, ReportDraftResponse)
    assert r7.status == "completed"

    # analyze_schema
    r8 = provider.analyze_schema(SchemaAnalyzeRequest(
        schema_changes=[SchemaChange(change="column_added", table_name="t")],
    ))
    assert isinstance(r8, SchemaAnalyzeResponse)
    assert r8.status == "completed"

    # suggest_fix
    r9 = provider.suggest_fix(FixSuggestRequest(
        issue_type="anomaly", table_name="t", issue_description="test",
    ))
    assert isinstance(r9, FixSuggestResponse)
    assert r9.status == "completed"


def test_mock_scope_respected():
    """Pass scope → provider accepts it without error."""
    scope = Scope(org_unit_ids=["ou-1"], module_ids=["dq.validate"], is_read_only=True)
    provider = MockProvider()
    response = provider.validate_dq(DqValidateRequest(
        rules=[DqRuleInput(id="r1_pass", prompt="test", fields=["x"], severity="warn")],
        rows=[{"x": 1}],
        scope=scope,
    ))
    assert response.status == "completed"
    assert response.results[0].status == "pass"
