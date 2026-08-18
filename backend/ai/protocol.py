"""
Carbon AI Intelligence — Protocol (Wave A)

THE CONTRACT. Zero imports from any web framework, HTTP library, or provider.
Pure ABCs and dataclasses.

Any AI backend (cloud-hosted, on-prem, local LLM) implements
AIProvider. CarbonIntelligence (Wave C) delegates to AIProvider.
The in-process engine adapter (providers/pulse.py) is the single,
contained seam — there is no runtime provider swapping (Phase 2).
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


# ── Workspace Context (§11 user situation) ────────────────────────────

@dataclass
class WorkspaceContext:
    """Structured description of what the user is currently doing.

    Sent by the frontend when opening the AI workspace tab.
    Never inferred — always explicitly serialized by the source workspace.

    AI CONTRACT §11.4: NEVER used for security decisions — that is Scope's job.
    AI CONTRACT §11.5: ``form_state`` must be sanitized before sending.
    """

    workspace: str                      # "dq" | "catalog" | "emissions" | "dataschema" | ...
    current_view: str = ""              # page or tab name, e.g. "rule_list", "table_detail"
    entity_type: str | None = None      # "table" | "rule" | "calculation" | "asset" | ...
    entity_id: str | None = None        # PK or slug of the focused entity
    entity_name: str | None = None      # human-readable name
    form_state: dict | None = None      # partial form data if user was filling a form (SANITIZED — §11.5)
    recent_actions: list[str] = field(default_factory=list)  # last 3-5 user actions
    mentions: list[dict[str, Any]] = field(default_factory=list)  # sanitized entity references
    intent_signal: str | None = None    # "create" | "edit" | "debug" | "explore" | None
    app_identifier: str | None = None   # domain app scope (mirrors Scope.app_identifier)

    def to_prompt_prefix(self) -> str:
        """Render a compact system-prompt prefix describing the user's situation."""
        if not self.workspace:
            return ""
        parts = [f"User is in the {self.workspace} workspace"]
        if self.current_view:
            parts.append(f"viewing {self.current_view}")
        if self.entity_type and self.entity_name:
            parts.append(f"on {self.entity_type} '{self.entity_name}'")
        elif self.entity_type:
            parts.append(f"on a {self.entity_type}")
        if self.intent_signal:
            parts.append(f"with intent '{self.intent_signal}'")
        if self.recent_actions:
            parts.append(f"recent actions: {', '.join(self.recent_actions[:3])}")
        mention_summary = _mention_summary(self.mentions)
        if mention_summary:
            parts.append(mention_summary)
        return ". ".join(parts) + "."

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "WorkspaceContext | None":
        if not data or not isinstance(data, dict) or not data.get("workspace"):
            return None
        known = {
            "workspace", "current_view", "entity_type", "entity_id",
            "entity_name", "form_state", "recent_actions",
            "mentions", "intent_signal", "app_identifier",
        }
        payload = {k: v for k, v in data.items() if k in known}
        payload["mentions"] = _sanitize_mentions(payload.get("mentions"))
        return cls(**payload)

def _sanitize_mentions(mentions: Any) -> list[dict[str, Any]]:
    """Return a compact, JSON-safe mention list."""
    if not isinstance(mentions, list):
        return []

    normalized: list[dict[str, Any]] = []
    allowed_keys = {
        "kind",
        "id",
        "name",
        "label",
        "type",
        "rule_type",
        "module_id",
        "table_id",
        "org_unit_id",
    }

    for mention in mentions:
        if not isinstance(mention, dict):
            continue

        kind = mention.get("kind") or mention.get("entity_kind") or mention.get("entity_type")
        identifier = mention.get("id") or mention.get("entity_id")
        if identifier is None:
            continue

        cleaned: dict[str, Any] = {"id": identifier}
        if kind:
            cleaned["kind"] = kind
        for key in allowed_keys - {"kind", "id"}:
            value = mention.get(key)
            if value is not None:
                cleaned[key] = value
        normalized.append(cleaned)

    return normalized


def _mention_summary(mentions: list[dict[str, Any]], limit: int = 3) -> str:
    parts: list[str] = []
    for mention in mentions[:limit]:
        kind = str(mention.get("kind") or "mention").strip()
        label = (
            mention.get("name")
            or mention.get("label")
            or mention.get("rule_type")
            or mention.get("type")
            or mention.get("id")
        )
        if label is None:
            continue
        parts.append(f"{kind} {label}")

    if not parts:
        return ""

    suffix = ""
    remaining = len(mentions) - len(parts)
    if remaining > 0:
        suffix = f" (+{remaining} more)"
    return f"mentions: {', '.join(parts)}{suffix}"

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
    model: str | None = None
    # Phase 22-A — optional per-user chat sampling temperature (0.0-2.0).
    # Resolved by CarbonIntelligence from the user profile (or a per-message
    # override); None lets the engine keep its built-in default.
    temperature: float | None = None


@dataclass
class ChatResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    content: str | None = None
    follow_up_questions: list[str] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0
    # Machine-readable tool outcomes (Sprint "fly to rule detail"):
    #  * actions — navigate-style actions derived from executed tools, e.g.
    #    [{"type": "navigate", "route": "/dq/rules/1271", "label": ..., "summary": ...}]
    #  * pending_actions — staged, confirmation-gated proposals awaiting the
    #    user, e.g. [{"execution_id": ..., "tool": "create_dq_rule", ...}]
    actions: list[dict] = field(default_factory=list)
    pending_actions: list[dict] = field(default_factory=list)


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
