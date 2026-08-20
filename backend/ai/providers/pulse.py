"""
PulseProvider — the in-process AIProvider backed by the vendored engine.

Wave B. Bridges Carbon's AIProvider ABC (ai/protocol.py) to the in-process
engine runtime (ai/engine_runtime.py). Each ABC method maps to a task type.
No HTTP transport — the engine is wired in-process (Phase 2).
"""

from __future__ import annotations

import logging
from typing import Any

from backend.ai.protocol import (
    AIProvider,
    AnomalyDetectRequest,
    AnomalyDetectResponse,
    AnomalyExplainRequest,
    AnomalyExplainResponse,
    ChatRequest,
    ChatResponse,
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
from backend.ai.engine_runtime import (
    dispatch_action_stream,
    dispatch_task,
    dispatch_task_stream,
    list_modules,
)

logger = logging.getLogger("carbon.ai.pulse_provider")

# ── Task type constants ─────────────────────────────────────────────────

T_DQ_VALIDATE = "dq.validate"
T_DQ_SUGGEST = "dq.suggest"
T_CHAT = "chat"
T_NL_QUERY = "carbon.query.nl"
T_NL_EXPLAIN = "carbon.query.explain"
T_ANOMALY_DETECT = "carbon.anomaly.detect"
T_ANOMALY_EXPLAIN = "carbon.anomaly.explain"
T_REPORT_DRAFT = "carbon.report.draft"
T_SCHEMA_ANALYZE = "carbon.schema.analyze"
T_FIX_SUGGEST = "carbon.fix.suggest"


# ── Provider ─────────────────────────────────────────────────────────────

class PulseProvider(AIProvider):
    """Dispatches every AI capability to the in-process engine.

    Every method is sync (the ABC is sync), dispatching to the in-process
    engine runtime.  Graceful degradation on engine error returns the
    appropriate typed response with ``status="provider_unavailable"``.
    """

    def __init__(self) -> None:
        self._instance_id = "carbon"

    # ── properties ────────────────────────────────────────────────────

    @property
    def provider_name(self) -> str:
        return "pulse"

    @property
    def provider_version(self) -> str:
        return "1.0.0"

    # ── health ────────────────────────────────────────────────────────

    def health_check(self) -> ProviderStatus:
        """Report the in-process engine's advertised modules."""
        data = list_modules(instance_id=self._instance_id)
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
        payload: dict[str, Any] = {
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
        # Include conversation history for multi-turn context (§10)
        if request.conversation is not None:
            payload["conversation_history"] = {
                "conversation_id": request.conversation.conversation_id,
                "messages": request.conversation.messages,
            }
        data = dispatch_task(T_DQ_VALIDATE, payload, timeout=30)

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
        if request.conversation is not None:
            payload["conversation_history"] = {
                "conversation_id": request.conversation.conversation_id,
                "messages": request.conversation.messages,
            }
        data = dispatch_task(T_DQ_SUGGEST, payload, timeout=90)

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
        if request.conversation is not None:
            payload["conversation_history"] = {
                "conversation_id": request.conversation.conversation_id,
                "messages": request.conversation.messages,
            }
        if request.domain_vocabulary:
            payload["domain_vocabulary"] = request.domain_vocabulary

        data = dispatch_task(T_NL_QUERY, payload, timeout=90)

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
        data = dispatch_task(T_NL_EXPLAIN, payload, timeout=60)

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
        if request.conversation is not None:
            payload["conversation_history"] = {
                "conversation_id": request.conversation.conversation_id,
                "messages": request.conversation.messages,
            }
        data = dispatch_task(T_ANOMALY_DETECT, payload, timeout=120)

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
        data = dispatch_task(T_ANOMALY_EXPLAIN, payload, timeout=60)

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
        data = dispatch_task(T_REPORT_DRAFT, payload, timeout=180)

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
        data = dispatch_task(T_SCHEMA_ANALYZE, payload, timeout=60)

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

        data = dispatch_task(T_FIX_SUGGEST, payload, timeout=90)

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

    # ── 10. chat (multi-turn workspace) ───────────────────────────────

    def _chat_payload(self, request: ChatRequest) -> dict[str, Any]:
        """Build the engine payload for a chat turn (shared by chat/chat_stream).

        Carries the authenticated user's identifier so the engine's in-process
        host executor stages + confirms mutations as that user.
        """
        payload: dict[str, Any] = {
            "message": request.message,
        }
        if request.model:
            payload["model"] = request.model
        # Phase 22-A — carry the user's default chat temperature (0.0-2.0)
        # when set; the engine keeps its built-in default otherwise.
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.scope is not None and request.scope.user_identifier:
            payload["host_user_id"] = str(request.scope.user_identifier)
        if request.conversation is not None:
            payload["conversation_history"] = {
                "conversation_id": request.conversation.conversation_id,
                "messages": request.conversation.messages,
            }
        return payload

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat message with full conversation history.

        AI CONTRACT §10: Conversations are multi-turn; Carbon sends
        full history on every request. Provider is stateless.
        """
        payload = self._chat_payload(request)

        data = dispatch_task(T_CHAT, payload, timeout=15)

        if data.get("status") == "completed":
            result = data.get("result") or {}
            return ChatResponse(
                status="completed",
                content=result.get("content"),
                follow_up_questions=result.get("follow_up_questions", []),
                execution_ms=result.get("execution_ms", 0),
                actions=result.get("actions") or [],
                pending_actions=result.get("pending_actions") or [],
            )

        return ChatResponse(
            status=_map_status(data.get("status")),
            error=data.get("error"),
        )

    def chat_stream(self, request: ChatRequest):
        """Stream a chat answer as ``(kind, value)`` tuples (SSE-ready).

        Builds the identical payload as :meth:`chat`, then yields from the
        in-process streaming dispatcher:

          ("chunk", delta)   — one text delta
          ("done", result)   — terminal success (same dict shape ``chat()`` reads)
          ("error", message) — terminal failure
        """
        payload = self._chat_payload(request)

        yield from dispatch_task_stream(T_CHAT, payload)


    def run_tool_stream(
        self,
        *,
        conversation_id: str,
        action_type: str,
        tool: str | None = None,
        agent: str | None = None,
        args: dict | None = None,
        verbosity: str = "concise",
        host_user_id: str | None = None,
    ):
        """Stream an agent/tool action run as ``(kind, value)`` tuples.

        Passthrough to the in-process action seam (``dispatch_action_stream``)
        — Sprint W1-A.  Yields:

          ("frame", frame)    — one clustered frame (turn_*/tool_*, design §2.5)
          ("done", result)    — terminal success ({"status": "completed"|"stopped"})
          ("error", message, {"error_kind": ...}) — terminal failure

        Cancellation is checked between steps against the generation registry
        (``GENERATIONS.cancel`` / ``is_cancelled``); a mid-run cancel yields a
        ``stopped`` ``turn_end`` frame — never ``error``.
        """
        payload = {
            "conversation_id": conversation_id,
            "action_type": action_type,
            "tool": tool,
            "agent": agent,
            "args": args or {},
            "verbosity": verbosity,
            "host_user_id": host_user_id,
        }
        yield from dispatch_action_stream(payload)


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
