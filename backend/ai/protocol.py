"""
Carbon AI Intelligence — Protocol (Wave A)

THE CONTRACT. Zero imports from any web framework, HTTP library, or provider.
Pure ABCs and dataclasses.

Any AI backend (cloud-hosted, on-prem, local LLM) implements
AIProvider. CarbonIntelligence (Wave C) delegates to AIProvider.
Swap backends by changing AI_PROVIDER_CLASS in settings — zero
code changes anywhere else.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ── Scope ────────────────────────────────────────────────────────────────

@dataclass
class Scope:
    """User scope — injected into every AI call.

    AI CONTRACT §1: Every AI call MUST carry a Scope. No Scope, no call.
    AI CONTRACT §3: app_identifier enforces data isolation between domain apps.
    """

    org_unit_ids: list[str] = field(default_factory=list)  # ["*"] = all
    module_ids: list[str] = field(default_factory=list)     # Specific modules user can access
    is_read_only: bool = False        # True → provider must not suggest mutations
    is_superuser: bool = False        # True → full access
    user_identifier: str = ""         # For audit trail
    app_identifier: str | None = None  # Domain app scope (e.g. "emissions", "water")
                                       # None = platform-level call (e.g. health check)

    def to_dict(self) -> dict[str, Any]:
        """Serialize scope for audit trail logging (§7 of ai-contract.md)."""
        return {
            "org_unit_ids": self.org_unit_ids,
            "module_ids": self.module_ids,
            "is_read_only": self.is_read_only,
            "is_superuser": self.is_superuser,
            "user_identifier": self.user_identifier,
            "app_identifier": self.app_identifier,
        }


# ── Provider Status ─────────────────────────────────────────────────────

@dataclass
class ProviderStatus:
    name: str
    version: str
    healthy: bool
    modules_available: list[str] = field(default_factory=list)
    error: str | None = None
    latency_ms: int = 0


# ── Conversation Context (§10 multi-turn) ──────────────────────────────

@dataclass
class ConversationContext:
    """Multi-turn conversation history carried to every AI call.

    AI CONTRACT §10: Provider receives full conversation history
    in every request. Carbon owns conversation state; provider is stateless.
    """

    conversation_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    # Each message: {"role": "user"|"assistant"|"system", "content": "...", "timestamp": "..."}


# ── 1. DQ Validate ──────────────────────────────────────────────────────

@dataclass
class DqRuleInput:
    id: str
    prompt: str
    fields: list[str]
    severity: str  # "info" | "warn" | "error"


@dataclass
class DqValidateRequest:
    rules: list[DqRuleInput]
    rows: list[dict[str, Any]]
    context: dict[str, Any] = field(default_factory=dict)
    scope: Scope | None = None
    conversation: ConversationContext | None = None


@dataclass
class DqRuleResult:
    rule_id: str
    status: str  # "pass" | "fail" | "skipped_unavailable"
    failing_rows: list[int] | None = None
    explanation: str | None = None
    confidence: float | None = None


@dataclass
class DqValidateResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    results: list[DqRuleResult] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── 2. DQ Suggest ───────────────────────────────────────────────────────

@dataclass
class TableProfile:
    name: str
    description: str
    row_count: int
    columns: list[dict[str, Any]]


@dataclass
class DqSuggestRequest:
    table: TableProfile
    scope: Scope | None = None
    conversation: ConversationContext | None = None


@dataclass
class DqSuggestion:
    definition: dict[str, Any]  # Complete v1 rule definition
    rationale: str
    severity: str
    confidence: float
    dimension: str


@dataclass
class DqSuggestResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    suggestions: list[DqSuggestion] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── 3. NL Query ─────────────────────────────────────────────────────────

@dataclass
class NlQueryRequest:
    question: str
    tables: list[str] | None = None
    max_rows: int = 100
    scope: Scope | None = None
    conversation: ConversationContext | None = None
    domain_vocabulary: dict[str, str] | None = None


@dataclass
class NlQueryResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    sql: str | None = None
    rows: list[dict[str, Any]] | None = None
    row_count: int = 0
    execution_ms: int = 0
    recovery_applied: bool = False
    error: dict[str, str] | None = None


# ── 4. NL Query Explain ─────────────────────────────────────────────────

@dataclass
class NlExplainRequest:
    question: str
    sql: str
    row_count: int
    sample_rows: list[dict[str, Any]]
    scope: Scope | None = None


@dataclass
class NlExplainResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    explanation: str | None = None
    caveats: list[str] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── 5. Anomaly Detection ────────────────────────────────────────────────

@dataclass
class AnomalyDetectRequest:
    table_name: str
    profile_history: list[dict[str, Any]]
    sensitivity: float = 2.0
    volume_threshold_pct: float = 30.0
    scope: Scope | None = None
    conversation: ConversationContext | None = None


@dataclass
class DetectedAnomaly:
    metric: str
    expected_range: dict[str, float]
    observed: float
    z_score: float
    severity: str  # "error" | "warning"
    explanation: str | None = None


@dataclass
class AnomalyDetectResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    anomalies: list[DetectedAnomaly] = field(default_factory=list)
    history_snapshots: int = 0
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── 6. Anomaly Explain ──────────────────────────────────────────────────

@dataclass
class AnomalyExplainRequest:
    table_name: str
    anomaly: dict[str, Any]
    scope: Scope | None = None


@dataclass
class AnomalyExplainResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    explanation: str | None = None
    investigation_steps: list[str] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── 7. Report Draft ─────────────────────────────────────────────────────

@dataclass
class ReportDraftRequest:
    report_type: str
    period_start: str  # ISO date
    period_end: str    # ISO date
    scope: Scope | None = None


@dataclass
class ReportSection:
    title: str
    content: str  # Markdown
    sql: str | None = None
    data: list[dict[str, Any]] | None = None
    narrative: str | None = None
    caveat: str | None = None


@dataclass
class ReportDraftResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    title: str | None = None
    summary: str | None = None
    report_type: str = ""
    period_start: str = ""
    period_end: str = ""
    generated_at: str = ""
    sections: list[ReportSection] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── 8. Schema Analyze ───────────────────────────────────────────────────

@dataclass
class SchemaChange:
    change: str
    table_name: str
    field_name: str | None = None


@dataclass
class SchemaAnalyzeRequest:
    schema_changes: list[SchemaChange]
    context: str | None = None
    scope: Scope | None = None


@dataclass
class SchemaImpact:
    change: str
    impact: str
    severity: str  # "low" | "medium" | "high" | "critical"
    suggested_action: str


@dataclass
class SchemaAnalyzeResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    analysis: list[SchemaImpact] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── 9. Fix Suggest ──────────────────────────────────────────────────────

@dataclass
class FixSuggestRequest:
    issue_type: str
    table_name: str
    issue_description: str
    affected_rows: list[dict[str, Any]] | None = None
    profile: dict[str, Any] | None = None
    scope: Scope | None = None


@dataclass
class FixSuggestion:
    description: str
    confidence: float
    estimated_affected_rows: int
    requires_confirmation: bool  # ALWAYS True — never auto-fix
    suggested_action_type: str


@dataclass
class FixSuggestResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    issue_type: str = ""
    table_name: str = ""
    suggestions: list[FixSuggestion] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── 10. Chat (multi-turn workspace) ─────────────────────────────────────

@dataclass
class ChatRequest:
    """Generic chat message sent to AI provider.

    AI CONTRACT §10: Carries full conversation history for multi-turn context.
    """
    message: str
    conversation: ConversationContext | None = None
    scope: Scope | None = None


@dataclass
class ChatResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    content: str | None = None
    follow_up_questions: list[str] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── AIProvider ABC ──────────────────────────────────────────────────────

class AIProvider(ABC):
    """One abstract class. Twelve members. Each backend implements them."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def provider_version(self) -> str:
        ...

    @abstractmethod
    def health_check(self) -> ProviderStatus:
        ...

    @abstractmethod
    def validate_dq(self, request: DqValidateRequest) -> DqValidateResponse:
        ...

    @abstractmethod
    def suggest_dq(self, request: DqSuggestRequest) -> DqSuggestResponse:
        ...

    @abstractmethod
    def query_nl(self, request: NlQueryRequest) -> NlQueryResponse:
        ...

    @abstractmethod
    def explain_query(self, request: NlExplainRequest) -> NlExplainResponse:
        ...

    @abstractmethod
    def detect_anomalies(self, request: AnomalyDetectRequest) -> AnomalyDetectResponse:
        ...

    @abstractmethod
    def explain_anomaly(self, request: AnomalyExplainRequest) -> AnomalyExplainResponse:
        ...

    @abstractmethod
    def draft_report(self, request: ReportDraftRequest) -> ReportDraftResponse:
        ...

    @abstractmethod
    def analyze_schema(self, request: SchemaAnalyzeRequest) -> SchemaAnalyzeResponse:
        ...

    @abstractmethod
    def suggest_fix(self, request: FixSuggestRequest) -> FixSuggestResponse:
        ...

    @abstractmethod
    def chat(self, request: ChatRequest) -> ChatResponse:
        ...
