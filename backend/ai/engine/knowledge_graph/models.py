"""
Knowledge Graph models as stdlib dataclasses (single-ORM, P2-05).

Mirrors ``ai.models.knowledge_graph``. See ``ai.engine.core.models`` for the
dataclass conventions: every field carries a default so partial construction
matches the retired SQLAlchemy behaviour, and ``Optional`` means "unset at the
engine layer" rather than "nullable at the DB layer".
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


def _kg_uuid() -> str:
    return str(uuid.uuid4())


NODE_TYPES = frozenset({
    "ENTITY",
    "ATTRIBUTE",
    "WORKFLOW",
    "WORKFLOW_STEP",
    "BUSINESS_RULE",
    "API_ENDPOINT",
    "CONCEPT",
    "MODULE",
})

RELATIONSHIP_TYPES = frozenset({
    "CONTAINS",
    "HAS_ATTRIBUTE",
    "FEEDS_INTO",
    "TRIGGERS",
    "DEPENDS_ON",
    "VALIDATES",
    "TRANSITIONS_TO",
    "CALLS",
    "IMPLEMENTS",
    "RELATED_TO",
})

SOURCE_TYPES = frozenset({
    "SCHEMA",
    "CODE",
    "DOCS",
    "INTERACTION",
    "OBSERVATION",
    "EXPERT",
})


@dataclass
class KnowledgeNode:
    id: str = field(default_factory=_kg_uuid)
    instance_id: Optional[str] = None
    node_type: Optional[str] = None
    name: Optional[str] = None
    description: str = ""
    properties: str = "{}"
    source: str = "SCHEMA"
    confidence: float = 0.8
    verified: bool = False
    verification_date: Optional[datetime] = None
    module_id: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    access_count: int = 0


@dataclass
class KnowledgeEdge:
    id: str = field(default_factory=_kg_uuid)
    instance_id: Optional[str] = None
    source_node_id: Optional[str] = None
    target_node_id: Optional[str] = None
    relationship: Optional[str] = None
    properties: str = "{}"
    confidence: float = 1.0
    source: str = "SCHEMA"
    weight: float = 1.0
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class KgQueryFeedback:
    id: str = field(default_factory=_kg_uuid)
    instance_id: Optional[str] = None
    question: str = ""
    sql_final: str = ""
    succeeded: bool = False
    retry_count: int = 0
    error_category: str = ""
    duration_ms: int = 0
    row_count: int = 0
    shape: str = ""
    created_at: Optional[datetime] = None


@dataclass
class KgCacheEntry:
    id: str = field(default_factory=_kg_uuid)
    instance_id: Optional[str] = None
    cache_layer: Optional[str] = None
    cache_key: Optional[str] = None
    utterance: str = ""
    sql_executed: str = ""
    result_json: Optional[str] = None
    table_tags: str = "[]"
    hit_count: int = 0
    ttl_seconds: Optional[int] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class KgRecoveryLog:
    id: str = field(default_factory=_kg_uuid)
    instance_id: Optional[str] = None
    question: str = ""
    error_type: str = ""
    recovery_type: str = ""
    original_sql: str = ""
    repaired_sql: str = ""
    succeeded: bool = False
    correction_description: str = ""
    retry_count: int = 0
    created_at: Optional[datetime] = None


# ══════════════════════════════════════════════════════════════════════════════
# Stage 11 — Feedback Loop & Continuous Learning
# ══════════════════════════════════════════════════════════════════════════════

SIGNAL_TYPES = frozenset({
    "explicit_positive",
    "explicit_negative",
    "correction",
    "rephrase",
    "contradiction",
    "abandonment",
    "export",
})

REVIEW_STATUSES = frozenset({"pending", "approved", "rejected"})

LEARNING_CHANNELS = frozenset({
    "synonym",
    "golden_pair",
    "prompt_tune",
    "fine_tune",
})


@dataclass
class KgFeedbackRecord:
    id: str = field(default_factory=_kg_uuid)
    instance_id: Optional[str] = None
    conversation_id: Optional[str] = None
    message_id: str = ""
    signal_type: Optional[str] = None
    user_id: str = ""
    original_utterance: str = ""
    resolved_utterance: str = ""
    generated_sql: str = ""
    corrected_sql: Optional[str] = None
    user_comment: Optional[str] = None
    quality_score: float = 0.7
    created_at: Optional[datetime] = None


@dataclass
class KgGoldenPair:
    id: str = field(default_factory=_kg_uuid)
    instance_id: Optional[str] = None
    question: Optional[str] = None
    sql: Optional[str] = None
    source_feedback_id: Optional[str] = None
    review_status: str = "pending"
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    tags: str = "[]"
    created_at: Optional[datetime] = None


@dataclass
class KgReviewItem:
    id: str = field(default_factory=_kg_uuid)
    instance_id: Optional[str] = None
    category: Optional[str] = None
    title: Optional[str] = None
    description: str = ""
    evidence_json: str = "[]"
    frequency: int = 1
    status: str = "pending"
    resolution: Optional[str] = None
    reviewed_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class KgQualityScore:
    id: str = field(default_factory=_kg_uuid)
    instance_id: Optional[str] = None
    dimension: Optional[str] = None
    dimension_value: str = "all"
    date: Optional[str] = None
    score: Optional[float] = None
    sample_count: int = 0
    created_at: Optional[datetime] = None


# ══════════════════════════════════════════════════════════════════════════════
# Stage 12 — Multi-Step Query Planning
# ══════════════════════════════════════════════════════════════════════════════

PLAN_STATUSES = frozenset({"planned", "running", "completed", "failed", "cancelled"})


@dataclass
class KgQueryPlan:
    id: str = field(default_factory=_kg_uuid)
    instance_id: Optional[str] = None
    conversation_id: Optional[str] = None
    original_utterance: Optional[str] = None
    pattern: str = "custom"
    step_count: int = 0
    status: str = "planned"
    synthesis_instruction: str = ""
    result_summary: Optional[str] = None
    total_duration_ms: int = 0
    total_llm_calls: int = 0
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class KgPlanStep:
    id: str = field(default_factory=_kg_uuid)
    plan_id: Optional[str] = None
    step_order: Optional[int] = None
    intent: Optional[str] = None
    depends_on: str = "[]"
    generated_sql: Optional[str] = None
    result_json: Optional[str] = None
    branch_condition: Optional[str] = None
    status: str = "pending"
    error_message: Optional[str] = None
    duration_ms: int = 0
    created_at: Optional[datetime] = None


# ══════════════════════════════════════════════════════════════════════════════
# Bootstrap Loop — Domain Pack
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class KgDomainPack:
    id: str = field(default_factory=_kg_uuid)
    instance_id: Optional[str] = None
    version: Optional[int] = None
    status: str = "active"
    trigger: str = "manual"
    pack_json: Optional[str] = None
    changelog_json: str = "[]"
    created_at: Optional[datetime] = None


@dataclass
class KgBootstrapRun:
    id: str = field(default_factory=_kg_uuid)
    instance_id: Optional[str] = None
    trigger: Optional[str] = None
    crawlers_run: str = "[]"
    domain_pack_id: Optional[str] = None
    previous_pack_id: Optional[str] = None
    status: str = "running"
    error_message: Optional[str] = None
    duration_ms: int = 0
    created_at: Optional[datetime] = None


# ══════════════════════════════════════════════════════════════════════════════
# Stage 13 — Proactive Intelligence
# ══════════════════════════════════════════════════════════════════════════════

TRIGGER_CATEGORIES = frozenset({"threshold", "trend", "correlation"})
TRIGGER_SEVERITIES = frozenset({"info", "warning", "critical"})
INSIGHT_DELIVERY_CHANNELS = frozenset({"websocket", "digest", "banner", "notification_panel"})
PROACTIVE_INSIGHT_TYPES = frozenset({
    "threshold_alert", "trend_alert", "correlation_alert",
    "daily_briefing", "anomaly_narrative", "forecast_deviation",
    "performance_drift", "optimization_opportunity",
})
INSIGHT_DISPOSITIONS = frozenset({
    "pending", "delivered", "read", "acted_on",
    "dismissed_known", "dismissed_irrelevant", "dismissed_false_positive",
    "expired",
})


@dataclass
class KgProactiveTrigger:
    id: str = field(default_factory=_kg_uuid)
    instance_id: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    severity: str = "info"
    enabled: bool = True
    condition_json: Optional[str] = None
    data_sources_json: str = "[]"
    context_queries_json: str = "[]"
    recommended_actions_json: str = "[]"
    recipients_json: str = "[]"
    cooldown_seconds: int = 3600
    last_fired_at: Optional[datetime] = None
    fire_count: int = 0
    source: str = "manual"
    created_at: Optional[datetime] = None


@dataclass
class KgProactiveInsight:
    id: str = field(default_factory=_kg_uuid)
    instance_id: Optional[str] = None
    visibility: str = "shared"
    trigger_id: Optional[str] = None
    insight_type: Optional[str] = None
    severity: str = "info"
    title: Optional[str] = None
    narrative: Optional[str] = None
    context_json: str = "{}"
    recommended_actions_json: str = "[]"
    disposition: str = "pending"
    dismissed_reason: Optional[str] = None
    group_id: Optional[str] = None
    delivery_channel: str = "websocket"
    delivered_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
