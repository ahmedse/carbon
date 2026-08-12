"""
KnowledgeNode and KnowledgeEdge — SQLAlchemy 2.0 ORM models for the Knowledge Graph.

These form the graph structure stored in SQLite. Styled after core/models.py.
Tables are registered automatically with the shared Base, so init_db() picks them up.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ai.engine.core.models import Base


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


class KnowledgeNode(Base):
    """
    A node in the knowledge graph. Represents a schema entity, attribute,
    workflow step, business rule, API endpoint, concept, or module.
    """

    __tablename__ = "knowledge_nodes"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_kg_uuid)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    node_type: Mapped[str] = mapped_column(Text, nullable=False)          # one of NODE_TYPES
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    properties: Mapped[str] = mapped_column(Text, nullable=False, default="{}")   # JSON
    source: Mapped[str] = mapped_column(Text, nullable=False, default="SCHEMA")   # one of SOURCE_TYPES
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    module_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)         # soft FK to another KnowledgeNode of type MODULE
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # BE-02-2: temporal validity start
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)    # BE-02-2: temporal validity end (None=open)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    last_accessed: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    access_count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("ix_kn_instance_type", "instance_id", "node_type"),
        Index("ix_kn_source", "source"),
        Index("ix_kn_module_id", "module_id"),
    )


class KnowledgeEdge(Base):
    """
    A directed edge in the knowledge graph. Represents a typed relationship
    between two KnowledgeNodes.
    """

    __tablename__ = "knowledge_edges"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_kg_uuid)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_node_id: Mapped[str] = mapped_column(Text, nullable=False)     # "from" node
    target_node_id: Mapped[str] = mapped_column(Text, nullable=False)     # "to" node
    relationship: Mapped[str] = mapped_column(Text, nullable=False)       # one of RELATIONSHIP_TYPES
    properties: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # JSON
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="SCHEMA")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="When this edge became valid")
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="When this edge expired (NULL = still valid)")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # Critical for traversal — queried on every hop
        Index("ix_ke_source_rel", "source_node_id", "relationship"),
        Index("ix_ke_target_rel", "target_node_id", "relationship"),
        # Bi-temporal validity index for as-of queries
        Index("ix_ke_validity", "source_node_id", "relationship", "valid_from", "valid_to"),
    )


class KgQueryFeedback(Base):
    """
    Per-query execution feedback record.
    Stores SQL attempts, retry counts, error categories, and success status
    for learning from query failures (Stage 5).
    """

    __tablename__ = "kg_query_feedback"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_kg_uuid)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sql_final: Mapped[str] = mapped_column(Text, nullable=False, default="")
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_category: Mapped[str] = mapped_column(Text, nullable=False, default="")   # ErrorCategory.value
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    shape: Mapped[str] = mapped_column(Text, nullable=False, default="")            # ShapeType.value
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_kqf_instance_id", "instance_id"),
        Index("ix_kqf_succeeded", "succeeded"),
    )


class KgCacheEntry(Base):
    """
    Multi-layer query result cache — Stage 9.

    Three layers share this table:
      query        — SQL hash → ExecutionResult JSON
      semantic     — utterance hash → SynthesizedAnswer JSON
      materialized — pre-computed rollup SQL → ExecutionResult JSON

    cache_key is SHA-256 of the normalized SQL (layers 1 & 3) or
    normalized utterance + "|" + user_role (layer 2).

    table_tags is a JSON list of table names extracted from the SQL so that
    cache entries can be invalidated when a specific table is updated.
    """

    __tablename__ = "kg_cache_entries"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_kg_uuid)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    cache_layer: Mapped[str] = mapped_column(Text, nullable=False)         # "query" | "semantic" | "materialized"
    cache_key: Mapped[str] = mapped_column(Text, nullable=False)           # SHA-256 hex
    utterance: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sql_executed: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result_json: Mapped[str] = mapped_column(Text, nullable=False)         # serialised answer
    table_tags: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_kce_key_instance", "cache_key", "instance_id"),
        Index("ix_kce_instance_layer", "instance_id", "cache_layer"),
        Index("ix_kce_expires", "expires_at"),
    )


class KgRecoveryLog(Base):
    """
    Audit trail for error-recovery pipeline attempts — Stage 10.

    One row is written per utterance where any recovery path was triggered:
    empty-result probe, timeout simplification, SQL-repair exhaustion, or
    implausibility sanity-CTE rewrite.
    """

    __tablename__ = "kg_recovery_log"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_kg_uuid)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error_type: Mapped[str] = mapped_column(Text, nullable=False, default="")    # e.g. "empty_result", "timeout"
    recovery_type: Mapped[str] = mapped_column(Text, nullable=False, default="")  # e.g. "fuzzy_match", "timeout_simplify"
    original_sql: Mapped[str] = mapped_column(Text, nullable=False, default="")
    repaired_sql: Mapped[str] = mapped_column(Text, nullable=False, default="")
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    correction_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_krl_instance_id", "instance_id"),
        Index("ix_krl_error_type", "error_type"),
        Index("ix_krl_succeeded", "succeeded"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Stage 11 — Feedback Loop & Continuous Learning
# ══════════════════════════════════════════════════════════════════════════════

SIGNAL_TYPES = frozenset({
    "explicit_positive",    # thumbs up
    "explicit_negative",    # thumbs down
    "correction",           # user supplied corrected SQL
    "rephrase",             # same question rephrased immediately
    "contradiction",        # follow-up that contradicts prior result
    "abandonment",          # session abandoned within one turn
    "export",               # user copied / exported result
})

REVIEW_STATUSES = frozenset({"pending", "approved", "rejected"})

LEARNING_CHANNELS = frozenset({
    "synonym",      # terminology / synonym update
    "golden_pair",  # NL→SQL example pair
    "prompt_tune",  # prompt revision
    "fine_tune",    # model fine-tuning batch
})


class KgFeedbackRecord(Base):
    """
    Every feedback signal — explicit or implicit — for a single turn.
    One row per signal (a turn may generate multiple signals).
    """
    __tablename__ = "kg_feedback_records"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_kg_uuid)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_id: Mapped[str] = mapped_column(Text, nullable=False)
    message_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    signal_type: Mapped[str] = mapped_column(Text, nullable=False)          # one of SIGNAL_TYPES
    user_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    original_utterance: Mapped[str] = mapped_column(Text, nullable=False, default="")
    resolved_utterance: Mapped[str] = mapped_column(Text, nullable=False, default="")
    generated_sql: Mapped[str] = mapped_column(Text, nullable=False, default="")
    corrected_sql: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quality_score: Mapped[float] = mapped_column(Float, default=0.7)        # 0.0–1.0
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_kfr_instance_id", "instance_id"),
        Index("ix_kfr_signal_type", "signal_type"),
        Index("ix_kfr_conversation_id", "conversation_id"),
        Index("ix_kfr_created_at", "created_at"),
    )


class KgGoldenPair(Base):
    """
    Curated (natural-language question → correct SQL) example pair.
    Fed into the few-shot prompt bank after human review.
    """
    __tablename__ = "kg_golden_pairs"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_kg_uuid)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    sql: Mapped[str] = mapped_column(Text, nullable=False)
    source_feedback_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    reviewed_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    tags: Mapped[str] = mapped_column(Text, nullable=False, default="[]")    # JSON list
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_kgp_instance_id", "instance_id"),
        Index("ix_kgp_review_status", "review_status"),
    )


class KgReviewItem(Base):
    """
    Human-in-the-loop review queue item.
    Groups related feedback signals for a data team member to validate
    before changes propagate into the learning channels.
    """
    __tablename__ = "kg_review_items"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_kg_uuid)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)              # learning channel name
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON: feedback IDs + snippets
    frequency: Mapped[int] = mapped_column(Integer, default=1)               # how many users reported
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")  # pending | approved | rejected
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_kri_instance_status", "instance_id", "status"),
        Index("ix_kri_category", "category"),
    )


class KgQualityScore(Base):
    """
    Aggregated quality score snapshot — one row per (instance, dimension, date).
    Used for drift detection and the quality heat map.
    """
    __tablename__ = "kg_quality_scores"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_kg_uuid)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    dimension: Mapped[str] = mapped_column(Text, nullable=False)             # "overall" | query_type | domain | role
    dimension_value: Mapped[str] = mapped_column(Text, nullable=False, default="all")
    date: Mapped[str] = mapped_column(Text, nullable=False)                  # YYYY-MM-DD
    score: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_kqs_instance_dim_date", "instance_id", "dimension", "date"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Stage 12 — Multi-Step Query Planning
# ══════════════════════════════════════════════════════════════════════════════

PLAN_STATUSES = frozenset({"planned", "running", "completed", "failed", "cancelled"})


class KgQueryPlan(Base):
    """
    A multi-step query plan produced for complex questions.
    Contains the DAG of steps and the synthesis instruction.
    """
    __tablename__ = "kg_query_plans"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_kg_uuid)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_id: Mapped[str] = mapped_column(Text, nullable=False)
    original_utterance: Mapped[str] = mapped_column(Text, nullable=False)
    pattern: Mapped[str] = mapped_column(Text, nullable=False, default="custom")  # root_cause | forecast_eval | comparative | threshold | what_if | custom
    step_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="planned")
    synthesis_instruction: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # JSON: final synthesis
    total_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    total_llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_kqp_instance_id", "instance_id"),
        Index("ix_kqp_conversation_id", "conversation_id"),
        Index("ix_kqp_status", "status"),
    )


class KgPlanStep(Base):
    """
    A single step within a multi-step query plan.
    Steps form a DAG via depends_on (JSON list of step IDs).
    """
    __tablename__ = "kg_plan_steps"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_kg_uuid)
    plan_id: Mapped[str] = mapped_column(Text, nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)         # execution order (0-based)
    intent: Mapped[str] = mapped_column(Text, nullable=False)                # NL description of step goal
    depends_on: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list of step IDs
    generated_sql: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # ExecutionResult summary
    branch_condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")  # pending | running | completed | failed | skipped
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_kps_plan_id", "plan_id"),
        Index("ix_kps_status", "status"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Bootstrap Loop — Domain Pack
# ══════════════════════════════════════════════════════════════════════════════

class KgDomainPack(Base):
    """
    Versioned domain pack — the central configuration artifact that all
    query-engine stages read from. Each version is a full snapshot of
    domain knowledge produced by the synthesis agent.
    """
    __tablename__ = "kg_domain_packs"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_kg_uuid)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")  # active | superseded | rolled_back
    trigger: Mapped[str] = mapped_column(Text, nullable=False, default="manual")  # manual | schema_migration | code_deploy | api_change | feedback | scheduled
    pack_json: Mapped[str] = mapped_column(Text, nullable=False)                  # full domain pack JSON
    changelog_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON: list of changes
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_kdp_instance_version", "instance_id", "version", unique=True),
        Index("ix_kdp_instance_status", "instance_id", "status"),
    )


class KgBootstrapRun(Base):
    """
    Audit trail for each bootstrap execution (initial or re-bootstrap).
    Records which crawlers ran, what triggered the run, and the resulting
    domain pack version.
    """
    __tablename__ = "kg_bootstrap_runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_kg_uuid)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    crawlers_run: Mapped[str] = mapped_column(Text, nullable=False, default="[]")        # JSON list
    domain_pack_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)           # resulting pack
    previous_pack_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")         # running | completed | failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_kbr_instance_id", "instance_id"),
        Index("ix_kbr_status", "status"),
    )


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


class KgProactiveTrigger(Base):
    """
    A proactive trigger definition — defines a condition the system watches for.
    Seeded from domain pack + manual configuration.
    """
    __tablename__ = "kg_proactive_triggers"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_kg_uuid)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)            # threshold | trend | correlation
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False, default="info")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    condition_json: Mapped[str] = mapped_column(Text, nullable=False)      # JSON: evaluation expression
    data_sources_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON: table/column refs
    context_queries_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON: PlanStep specs
    recommended_actions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    recipients_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")   # JSON: role/user refs
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    last_fired_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fire_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="manual")  # manual | domain_pack | learned
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_kpt_instance_id", "instance_id"),
        Index("ix_kpt_category", "category"),
        Index("ix_kpt_enabled", "enabled"),
    )


class KgProactiveInsight(Base):
    """
    A generated proactive insight — the result of a trigger firing or
    scheduled insight generation (daily briefing, anomaly narrative, etc.).
    """
    __tablename__ = "kg_proactive_insights"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_kg_uuid)
    instance_id: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # NULL for scheduled insights
    insight_type: Mapped[str] = mapped_column(Text, nullable=False)          # threshold_alert, daily_briefing, etc.
    severity: Mapped[str] = mapped_column(Text, nullable=False, default="info")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)             # full context-assembled narrative
    context_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # assembled context data
    recommended_actions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    disposition: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    dismissed_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    group_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)     # dedup grouping key
    delivery_channel: Mapped[str] = mapped_column(Text, nullable=False, default="websocket")
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_kpi_instance_id", "instance_id"),
        Index("ix_kpi_trigger_id", "trigger_id"),
        Index("ix_kpi_type", "insight_type"),
        Index("ix_kpi_disposition", "disposition"),
        Index("ix_kpi_severity", "severity"),
        Index("ix_kpi_group_id", "group_id"),
        Index("ix_kpi_expires_at", "expires_at"),
    )
