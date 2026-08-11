"""
PulseProvider — AIProvider that calls Pulse's POST /tasks endpoint.

Wave B. Bridges Carbon's AIProvider ABC (ai/protocol.py) to Pulse's
task API (POST /tasks). Each ABC method maps to a Pulse task type.

Swap backends by changing AI_PROVIDER_CLASS in settings. PulseProvider
is one implementation — any backend implementing AIProvider works.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from backend.ai.protocol import (
    AIProvider,
    AnomalyDetectRequest,
    AnomalyDetectResponse,
    AnomalyExplainRequest,
    AnomalyExplainResponse,
    DetectedAnomaly,
    DqRuleInput,
    DqRuleResult,
    DqSuggestRequest,
    DqSuggestResponse,
    DqSuggestion,
    DqValidateRequest,
    DqValidateResponse,
    FixSuggestRequest,
    FixSuggestResponse,
    FixSuggestion,
    NlExplainRequest,
    NlExplainResponse,
    NlQueryRequest,
    NlQueryResponse,
    ProviderStatus,
    ReportDraftRequest,
    ReportDraftResponse,
    ReportSection,
    SchemaAnalyzeRequest,
    SchemaAnalyzeResponse,
    SchemaChange,
    SchemaImpact,
    Scope,
    TableProfile,
)
from backend.ai.providers._http import get_modules, post_task

logger = logging.getLogger("carbon.ai.pulse_provider")

# ── Task type constants ─────────────────────────────────────────────────

T_DQ_VALIDATE = "dq.validate"
T_DQ_SUGGEST = "dq.suggest"
T_NL_QUERY = "carbon.query.nl"
T_NL_EXPLAIN = "carbon.query.explain"
T_ANOMALY_DETECT = "carbon.anomaly.detect"
T_ANOMALY_EXPLAIN = "carbon.anomaly.explain"
T_REPORT_DRAFT = "carbon.report.draft"
T_SCHEMA_ANALYZE = "carbon.schema.analyze"
T_FIX_SUGGEST = "carbon.fix.suggest"


# ── Provider ─────────────────────────────────────────────────────────────

class PulseProvider(AIProvider):
    """Calls Pulse's POST /tasks for every AI capability.

    Constructor reads AI_PROVIDER_URL and AI_PROVIDER_API_KEY from Django
    settings.  Every method is sync (the ABC is sync), using ``requests``
    under the hood.  Graceful degradation on timeout / connection error /
    HTTP 5xx returns the appropriate typed response with
    ``status="provider_unavailable"``.
    """

    def __init__(self) -> None:
        self._url = settings.AI_PROVIDER_URL.rstrip("/")
        self._key = settings.AI_PROVIDER_API_KEY

    # ── properties ────────────────────────────────────────────────────

    @property
    def provider_name(self) -> str:
        return "pulse"

    @property
    def provider_version(self) -> str:
        return "1.0.0"

    # ── health ────────────────────────────────────────────────────────

    def health_check(self) -> ProviderStatus:
        """Lightweight connectivity check via GET /tasks/modules (no-auth)."""
        data = get_modules(self._url, timeout=10, instance_id="carbon")
        error = data.get("error")

        if error:
            code = error.get("code", "unknown")
            message = error.get("message", "")
            return ProviderStatus(
                name="pulse",
                version=self.provider_version,
                healthy=False,
                error=f"{code}: {message}" if message else code,
            )

        mods = [m["type"] for m in data.get("modules", [])]
        return ProviderStatus(
            name="pulse",
            version=self.provider_version,
            healthy=True,
            modules_available=mods,
        )

    # ── 1. dq.validate ────────────────────────────────────────────────

    def validate_dq(self, request: DqValidateRequest) -> DqValidateResponse:
        payload = {
            "rules": [
                {
                    "id": r.id,
                    "prompt": r.prompt,
                    "fields": r.fields,
                    "severity": r.severity,
                }
                for r in request.rules
            ],
            "rows": request.rows,
            "context": request.context,
        }
        data = post_task(self._url, self._key, T_DQ_VALIDATE, payload, timeout=30)

        if data.get("status") == "completed":
            result = (data.get("result") or {})
            raw_results: list[dict] = result.get("results", [])
            mapped = [
                DqRuleResult(
                    rule_id=r.get("rule_id", ""),
                    status=r.get("status", "fail"),
                    failing_rows=_extract_failing_rows(r),
                    explanation=r.get("details", [{}])[0].get("explanation")
                    if r.get("details") else None,
                    confidence=0.9 if r.get("status") == "pass" else 0.7,
                )
                for r in raw_results
            ]
            return DqValidateResponse(status="completed", results=mapped)

        return DqValidateResponse(
            status=_map_status(data.get("status")),
            error=data.get("error"),
        )

    # ── 2. dq.suggest ─────────────────────────────────────────────────

    def suggest_dq(self, request: DqSuggestRequest) -> DqSuggestResponse:
        table = request.table
        payload = {
            "table": {
                "name": table.name,
                "description": table.description,
                "columns": table.columns,
                "row_count": table.row_count,
            },
        }
        data = post_task(self._url, self._key, T_DQ_SUGGEST, payload, timeout=90)

        if data.get("status") == "completed":
            result = (data.get("result") or {})
            raw: list[dict] = result.get("suggestions", [])
            mapped = [
                DqSuggestion(
                    definition={
                        "id": f"sug-{i}",
                        "prompt": s.get("prompt", ""),
                        "type": s.get("rule_type", "nl_check"),
                    },
                    rationale=s.get("rationale", ""),
                    severity=s.get("suggested_severity", "warning"),
                    confidence=float(s.get("confidence", 0.5)),
                    dimension="accuracy",
                )
                for i, s in enumerate(raw)
            ]
            return DqSuggestResponse(status="completed", suggestions=mapped)

        return DqSuggestResponse(
            status=_map_status(data.get("status")),
            error=data.get("error"),
        )

    # ── 3. carbon.query.nl ────────────────────────────────────────────

    def query_nl(self, request: NlQueryRequest) -> NlQueryResponse:
        payload: dict[str, Any] = {
            "question": request.question,
            "max_rows": request.max_rows,
        }
        if request.tables:
            payload["tables"] = request.tables
        if request.domain_vocabulary:
            payload["domain_vocabulary"] = request.domain_vocabulary

        data = post_task(self._url, self._key, T_NL_QUERY, payload, timeout=90)

        if data.get("status") == "completed":
            result = data.get("result") or {}
            return NlQueryResponse(
                status="completed",
                sql=result.get("sql"),
                rows=result.get("rows"),
                row_count=result.get("row_count", 0),
                execution_ms=result.get("execution_ms", 0),
                recovery_applied=result.get("recovery_applied", False),
            )

        return NlQueryResponse(
            status=_map_status(data.get("status")),
            error=data.get("error"),
        )

    # ── 4. carbon.query.explain ───────────────────────────────────────

    def explain_query(self, request: NlExplainRequest) -> NlExplainResponse:
        payload = {
            "question": request.question,
            "sql": request.sql,
            "row_count": request.row_count,
            "sample_rows": request.sample_rows,
        }
        data = post_task(self._url, self._key, T_NL_EXPLAIN, payload, timeout=60)

        if data.get("status") == "completed":
            result = data.get("result") or {}
            return NlExplainResponse(
                status="completed",
                explanation=result.get("explanation"),
                caveats=result.get("caveats", []),
            )

        return NlExplainResponse(
            status=_map_status(data.get("status")),
            error=data.get("error"),
        )

    # ── 5. carbon.anomaly.detect ──────────────────────────────────────

    def detect_anomalies(
        self, request: AnomalyDetectRequest
    ) -> AnomalyDetectResponse:
        payload = {
            "table_name": request.table_name,
            "profile_history": request.profile_history,
            "sensitivity": request.sensitivity,
            "volume_threshold_pct": request.volume_threshold_pct,
        }
        data = post_task(self._url, self._key, T_ANOMALY_DETECT, payload, timeout=120)

        if data.get("status") == "completed":
            result = data.get("result") or {}
            raw: list[dict] = result.get("anomalies", [])
            mapped = [
                DetectedAnomaly(
                    metric=a.get("metric", ""),
                    expected_range={
                        "low": a.get("expected_range", {}).get("low", 0),
                        "high": a.get("expected_range", {}).get("high", 0),
                    },
                    observed=float(a.get("observed", 0)),
                    z_score=float(a.get("z_score") or 0),
                    severity=a.get("severity", "warning"),
                    explanation=a.get("explanation"),
                )
                for a in raw
            ]
            return AnomalyDetectResponse(
                status="completed",
                anomalies=mapped,
                history_snapshots=result.get("history_snapshots", 0),
            )

        return AnomalyDetectResponse(
            status=_map_status(data.get("status")),
            error=data.get("error"),
        )

    # ── 6. carbon.anomaly.explain ─────────────────────────────────────

    def explain_anomaly(
        self, request: AnomalyExplainRequest
    ) -> AnomalyExplainResponse:
        payload = {
            "table_name": request.table_name,
            "anomaly": request.anomaly,
        }
        data = post_task(self._url, self._key, T_ANOMALY_EXPLAIN, payload, timeout=60)

        if data.get("status") == "completed":
            result = data.get("result") or {}
            return AnomalyExplainResponse(
                status="completed",
                explanation=result.get("explanation"),
                investigation_steps=result.get("investigation_steps", []),
            )

        return AnomalyExplainResponse(
            status=_map_status(data.get("status")),
            error=data.get("error"),
        )

    # ── 7. carbon.report.draft ────────────────────────────────────────

    def draft_report(
        self, request: ReportDraftRequest
    ) -> ReportDraftResponse:
        payload = {
            "report_type": request.report_type,
            "period_start": request.period_start,
            "period_end": request.period_end,
        }
        data = post_task(self._url, self._key, T_REPORT_DRAFT, payload, timeout=180)

        if data.get("status") == "completed":
            result = data.get("result") or {}
            raw_sections: list[dict] = result.get("sections", [])
            sections = [
                ReportSection(
                    title=s.get("title", ""),
                    content=s.get("narrative", s.get("content", "")),
                    sql=s.get("sql"),
                    data=s.get("data_table"),
                    narrative=s.get("narrative"),
                    caveat=(
                        s.get("caveats", [None])[0]
                        if s.get("caveats") else None
                    ),
                )
                for s in raw_sections
            ]
            return ReportDraftResponse(
                status="completed",
                title=result.get("title"),
                summary=result.get("summary"),
                report_type=result.get("report_type", request.report_type),
                period_start=result.get("period_start", request.period_start),
                period_end=result.get("period_end", request.period_end),
                generated_at=result.get("generated_at", ""),
                sections=sections,
            )

        return ReportDraftResponse(
            status=_map_status(data.get("status")),
            error=data.get("error"),
        )

    # ── 8. carbon.schema.analyze ──────────────────────────────────────

    def analyze_schema(
        self, request: SchemaAnalyzeRequest
    ) -> SchemaAnalyzeResponse:
        payload = {
            "schema_changes": [
                {
                    "change": c.change,
                    "table_name": c.table_name,
                    "field_name": c.field_name,
                }
                for c in request.schema_changes
            ],
            "context": request.context,
        }
        data = post_task(self._url, self._key, T_SCHEMA_ANALYZE, payload, timeout=60)

        if data.get("status") == "completed":
            result = data.get("result") or {}
            raw: list[dict] = result.get("analysis", [])
            mapped = [
                SchemaImpact(
                    change=a.get("change", ""),
                    impact=a.get("impact", ""),
                    severity=a.get("severity", "medium"),
                    suggested_action=a.get("suggested_action", ""),
                )
                for a in raw
            ]
            return SchemaAnalyzeResponse(status="completed", analysis=mapped)

        return SchemaAnalyzeResponse(
            status=_map_status(data.get("status")),
            error=data.get("error"),
        )

    # ── 9. carbon.fix.suggest ─────────────────────────────────────────

    def suggest_fix(
        self, request: FixSuggestRequest
    ) -> FixSuggestResponse:
        payload: dict[str, Any] = {
            "issue_type": request.issue_type,
            "table_name": request.table_name,
            "issue_description": request.issue_description,
        }
        if request.affected_rows is not None:
            payload["affected_rows"] = request.affected_rows
        if request.profile is not None:
            payload["profile"] = request.profile

        data = post_task(self._url, self._key, T_FIX_SUGGEST, payload, timeout=90)

        if data.get("status") == "completed":
            result = data.get("result") or {}
            raw: list[dict] = result.get("suggestions", [])
            mapped = [
                FixSuggestion(
                    description=s.get("description", ""),
                    confidence=float(s.get("confidence", 0.5)),
                    estimated_affected_rows=int(
                        s.get("estimated_affected_rows", 0)
                    ),
                    requires_confirmation=True,  # ALWAYS
                    suggested_action_type=s.get(
                        "suggested_action_type", "investigation"
                    ),
                )
                for s in raw
            ]
            return FixSuggestResponse(
                status="completed",
                issue_type=result.get("issue_type", request.issue_type),
                table_name=result.get("table_name", request.table_name),
                suggestions=mapped,
            )

        return FixSuggestResponse(
            status=_map_status(data.get("status")),
            error=data.get("error"),
        )


# ── helpers ──────────────────────────────────────────────────────────────

def _map_status(pulse_status: str | None) -> str:
    """Map Pulse response status → ABC protocol status."""
    if pulse_status == "pulse_unavailable":
        return "provider_unavailable"
    if pulse_status in ("completed", "failed"):
        return pulse_status
    return "provider_unavailable"


def _extract_failing_rows(result: dict) -> list[int] | None:
    """Extract row indices that failed from a Pulse result dict."""
    details: list[dict] = result.get("details", [])
    if not details:
        return None
    failing = [
        i for i, d in enumerate(details)
        if not d.get("passed", True)
    ]
    return failing if failing else None
