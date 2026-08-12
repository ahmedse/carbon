"""
SQLAlchemy ORM models for all Pulse tables.
SQLAlchemy 2.0 style with Mapped type hints.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from ai.engine.core.clock import utcnow

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, Text, UniqueConstraint, and_, func, or_
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def generate_uuid() -> str:
    return str(uuid.uuid4())


def _apply_tenancy_filter(stmt, model_class, instance_id: str, host_user_id: str | None):
    """Apply the standard (instance_id, host_user_id, visibility) triplet filter.

    Visibility semantics:
      - 'global':  accessible regardless of user (cross-instance system data)
      - 'shared':  accessible to all authenticated users of this instance
      - 'private': accessible only to the owner (host_user_id)

    When host_user_id is None (anonymous session), only 'global' and 'shared'
    rows are returned — 'private' rows are never exposed.

    Usage::
        stmt = _apply_tenancy_filter(
            select(MemoryLongTerm), MemoryLongTerm, instance_id, host_user_id
        )
    """
    if host_user_id:
        vis_filter = or_(
            model_class.visibility == "global",
            model_class.visibility == "shared",
            and_(
                model_class.visibility == "private",
                model_class.host_user_id == host_user_id,
            ),
        )
    else:
        vis_filter = or_(
            model_class.visibility == "global",
            model_class.visibility == "shared",
        )
    return stmt.where(model_class.instance_id == instance_id, vis_filter)


class Base(DeclarativeBase):
    pass


class Instance(Base):
    __tablename__ = "instances"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    host_db_url: Mapped[str] = mapped_column(Text, nullable=False)
    host_api_url: Mapped[str] = mapped_column(Text, nullable=False)
    host_api_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="active")
    config: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_instance_id", "instance_id"),
        Index("ix_conversations_user_identifier", "user_identifier"),
        Index("ix_conversations_host_user_id", "host_user_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    user_identifier: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    host_user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # PR-2: tenancy
    visibility: Mapped[str] = mapped_column(Text, nullable=False, default="private")  # PR-2: tenancy
    page_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # user-editable session title
    mode: Mapped[str] = mapped_column(Text, default="normal")  # normal | deep
    archived: Mapped[bool] = mapped_column(Boolean, default=False)  # soft-archive
    compaction_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # BE-02-3: rolling conversation summary
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_timestamp", "timestamp"),
        Index("ix_messages_host_user_id", "host_user_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    conversation_id: Mapped[str] = mapped_column(Text, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)  # user/assistant/system/tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    host_user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # PR-2: tenancy
    visibility: Mapped[str] = mapped_column(Text, nullable=False, default="private")  # PR-2: tenancy
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MemoryLongTerm(Base):
    __tablename__ = "memory_long_term"
    __table_args__ = (
        Index("ix_memory_lt_instance_id", "instance_id"),
        Index("ix_memory_lt_category", "category"),
        Index("ix_memory_lt_instance_category", "instance_id", "category"),
        Index("ix_memory_lt_host_user_id", "host_user_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    decay_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # PR-14: when decay becomes active
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    host_user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # PR-2: tenancy
    visibility: Mapped[str] = mapped_column(Text, nullable=False, default="private")  # PR-2: tenancy
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # BE-02-2: temporal validity start
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)    # BE-02-2: temporal validity end (None=open)
    superseded_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)        # BE-02-2: UUID of replacement fact
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_used: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    use_count: Mapped[int] = mapped_column(Integer, default=0)


class MemoryEpisodic(Base):
    __tablename__ = "memory_episodic"
    __table_args__ = (
        Index("ix_memory_ep_instance_id", "instance_id"),
        Index("ix_memory_ep_host_user_id", "host_user_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    causal_chain: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    caused_by_episode_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # PR-13: causal chain linking
    relevance_score: Mapped[float] = mapped_column(Float, default=1.0)  # PR-13: decay score 1.0→0.0
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # PR-13: LRU decay marker
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    host_user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # PR-2: tenancy
    visibility: Mapped[str] = mapped_column(Text, nullable=False, default="private")  # PR-2: tenancy
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    learned_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeEntity(Base):
    __tablename__ = "knowledge_entities"
    __table_args__ = (
        Index("ix_ke_instance_id", "instance_id"),
        Index("ix_ke_instance_name", "instance_id", "name"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    schema_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    semantic_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    relationships: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    last_introspected: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SystemSnapshot(Base):
    __tablename__ = "system_snapshots"
    __table_args__ = (
        Index("ix_snapshots_instance_id", "instance_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    snapshot_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    diff_from_previous: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_instance_id", "instance_id"),
        Index("ix_notifications_acknowledged", "acknowledged"),
        Index("ix_notifications_host_user_id", "host_user_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    host_user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # PR-2: tenancy
    visibility: Mapped[str] = mapped_column(Text, nullable=False, default="shared")  # PR-2: tenancy (notifications default shared)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        Index("ix_feedback_message_id", "message_id"),
        Index("ix_feedback_host_user_id", "host_user_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    message_id: Mapped[str] = mapped_column(Text, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    correction_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    host_user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # PR-2: tenancy
    visibility: Mapped[str] = mapped_column(Text, nullable=False, default="private")  # PR-2: tenancy
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserKey(Base):
    """Pulse API keys — tie a host user's identity to a long-lived key used by the widget.

    Flow:
      1. User POSTs their Host JWT → Pulse validates it → returns a plsk_… key.
      2. Widget stores the key in localStorage('pulse_key').
      3. On every WS connect the widget sends pulse_key in the init frame.
      4. Chat resolves the key → attaches user identity + host token to the session.
    """
    __tablename__ = "user_keys"
    __table_args__ = (
        Index("ix_user_keys_instance_id", "instance_id"),
        Index("ix_user_keys_key_hash", "key_hash"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    username: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    roles_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # JSON list of role names
    key_prefix: Mapped[str] = mapped_column(Text, nullable=False)            # first 16 chars — safe to display
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True) # SHA-256 of the full key
    host_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # Host Bearer JWT — refreshable
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Insight(Base):
    """Synthesized wisdom — patterns and conclusions derived from memories, episodes, and snapshots."""
    __tablename__ = "insights"
    __table_args__ = (
        Index("ix_insights_instance_id", "instance_id"),
        Index("ix_insights_type", "insight_type"),
        Index("ix_insights_host_user_id", "host_user_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    insight_type: Mapped[str] = mapped_column(Text, nullable=False)  # pattern | trend | anomaly | recommendation
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON: source IDs/data
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    host_user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # PR-2: tenancy (None = instance-wide)
    visibility: Mapped[str] = mapped_column(Text, nullable=False, default="shared")  # PR-2: tenancy (insights default shared)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    superseded_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # ID of newer insight


class ToolExecution(Base):
    __tablename__ = "tool_executions"
    __table_args__ = (
        Index("ix_tool_exec_conversation_id", "conversation_id"),
        Index("ix_tool_exec_host_user_id", "host_user_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    conversation_id: Mapped[str] = mapped_column(Text, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    input_params: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    status: Mapped[str] = mapped_column(Text, default="pending_confirmation")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    host_user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # PR-2: tenancy
    visibility: Mapped[str] = mapped_column(Text, nullable=False, default="private")  # PR-2: tenancy
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class LLMCallLog(Base):
    __tablename__ = "llm_call_logs"
    __table_args__ = (
        Index("ix_llm_logs_instance_id", "instance_id"),
        Index("ix_llm_logs_conversation_id", "conversation_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[str] = mapped_column(Text, nullable=False)  # no FK — logging table, accepts synthetic IDs (e.g. draft-*)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    llm_calls: Mapped[int] = mapped_column(Integer, default=1)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)  # estimated USD cost
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ConversationContextRecord(Base):
    """
    Persists the multi-turn ConversationSession for each conversation.
    One row per conversation_id; session state stored as a JSON blob.
    Created/updated by knowledge_graph.session_store.
    """
    __tablename__ = "conversation_context_records"
    __table_args__ = (
        Index("ix_ccr_instance_id", "instance_id"),
    )

    conversation_id: Mapped[str] = mapped_column(Text, ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    session_json: Mapped[str] = mapped_column(Text, nullable=False)   # JSON-serialised ConversationSession
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AuditLog(Base):
    """Persistent audit trail for Studio admin access to per-user data.

    actor_type:
        'studio_admin' — authenticated Studio user accessing instance data
        'host_user'    — future: host-user self-service actions
    action examples:
        'read_notifications', 'read_memories', 'read_episodes', 'patch_settings'
    detail:
        JSON string — key names for settings changes; None for reads.
        MUST NOT contain secret values.
    """
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_instance_id", "instance_id"),
        Index("ix_audit_log_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)  # 'studio_admin' | 'host_user'
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string; NO secret values
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class OpsRun(Base):
    """Provenance ledger for an autonomous ops-workflow run.

    One row per ``ingest → validate → infer → ops_output`` invocation (including
    dry-runs). Captures everything needed to reproduce and audit the run: which
    file/columns went in, the date range, the model/version used, where the
    output landed, and the per-step status trail.
    """
    __tablename__ = "ops_runs"
    __table_args__ = (
        Index("ix_ops_runs_instance_id", "instance_id"),
        Index("ix_ops_runs_host_user_id", "host_user_id"),
        Index("ix_ops_runs_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    workflow: Mapped[str] = mapped_column(Text, nullable=False)              # workflow name from instance config
    status: Mapped[str] = mapped_column(Text, default="running")            # running | needs_input | completed | failed
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    # Inputs / provenance
    csv_filename: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # sha256 of source CSV bytes
    dataset_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # host dataset id/name
    engine_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # host engine id/name
    rows_ingested: Mapped[int] = mapped_column(Integer, default=0)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0)
    date_start: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date_end: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Detail blobs (JSON strings)
    steps_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)        # per-step status trail
    provenance_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # column map, file/external split, config snapshot
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Tenancy
    host_user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(Text, nullable=False, default="private")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class CsvUpload(Base):
    """Server-side staging for an uploaded CSV awaiting ingestion.

    The chat upload endpoint stores the full file here (untruncated) and hands the
    agent only a short pointer containing ``id``. The ops workflow resolves the
    full content by id, so large files are never injected into the LLM context.
    Rows are tenancy-scoped and pruned by age.
    """
    __tablename__ = "csv_uploads"
    __table_args__ = (
        Index("ix_csv_uploads_instance_id", "instance_id"),
        Index("ix_csv_uploads_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    host_user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    filename: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)   # full CSV text
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class VectorEmbedding(Base):
    """Generic vector embedding store — replaces ChromaDB when VECTOR_BACKEND=pgvector.

    The embedding column stores a JSON-serialized list of floats. On PostgreSQL
    with the pgvector extension, similarity search uses ``embedding::vector <=>
    query::vector``. On SQLite, the column is inert text — vector search is not
    available without ChromaDB.
    """
    __tablename__ = "vector_embeddings"
    __table_args__ = (
        Index("ix_vec_collection", "collection"),
        Index("ix_vec_instance_id", "instance_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    collection: Mapped[str] = mapped_column(Text, nullable=False)  # e.g. "knowledge", "memory", "episodes", "kg_nodes"
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    document: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON-serialized float list
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TurnLedgerRow(Base):
    """One row per stage per turn in the six-witness cognition pipeline.

    Six rows per turn (S1–S6), each recording one witness's output.
    This table is the source of truth for "what happened in this turn."
    """
    __tablename__ = "turn_ledger"
    __table_args__ = (
        Index("ix_turn_ledger_turn_id", "turn_id"),
        Index("ix_turn_ledger_instance_id", "instance_id"),
        Index("ix_turn_ledger_conversation_id", "conversation_id"),
        Index("ix_turn_ledger_stage", "turn_id", "stage_index"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    turn_id: Mapped[str] = mapped_column(Text, nullable=False)
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    host_user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conversation_id: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False)     # salience | retrieval | draft | critic | execution | final
    stage_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 0–5
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON-serialized witness output
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verdict: Mapped[Optional[str]] = mapped_column(Text, nullable=True)     # pass | pass_with_flag | rewrite | veto
    flags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of flag strings
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ═══════════════════════════════════════════════════════════════════════════════
# P1.1 — Durable multi-step run persistence (TASK-BE-01-1)
# ═══════════════════════════════════════════════════════════════════════════════

class Run(Base):
    """One row per multi-step agentic run — supersedes TurnLedgerRow for execution.

    Persists the in-memory Plan into durable rows so runs survive restarts,
    can be cancelled mid-flight, and resumed from the last completed step.
    """
    __tablename__ = "runs"
    __table_args__ = (
        Index("ix_runs_instance_id", "instance_id"),
        Index("ix_runs_conversation_id", "conversation_id"),
        Index("ix_runs_host_user_id", "host_user_id"),
        Index("ix_runs_status", "status"),
        Index("ix_runs_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[str] = mapped_column(Text, nullable=False)
    host_user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending")  # pending | running | paused | completed | failed | cancelled
    plan_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON-serialized Plan
    final_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    total_latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    working_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # BE-02-3: JSON array of agent artifacts
    # P3.4 — Per-run token budgets
    token_budget: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # cap for this run
    tokens_consumed: Mapped[int] = mapped_column(Integer, default=0)  # running total
    fan_out_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # why N workers
    worker_budgets_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON: {agent_id: budget}
    budget_exceeded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class RunStep(Base):
    """One row per step within a Run — checkpoint for cancel/resume."""
    __tablename__ = "run_steps"
    __table_args__ = (
        Index("ix_run_steps_run_id", "run_id"),
        Index("ix_run_steps_status", "status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(Text, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    intent: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_args_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    depends_on_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of step_index ints
    status: Mapped[str] = mapped_column(Text, default="pending")  # pending | running | awaiting_approval | completed | failed | skipped
    draft_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    critic_verdict: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    critic_flags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_output_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confirmation_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
# P4.1 — Append-only trajectory store (TASK-BE-04-1)
# ═══════════════════════════════════════════════════════════════════════════════

class Trajectory(Base):
    """One row per completed run — denormalized summary for offline learning.

    Written AFTER the run completes (status = completed/failed/cancelled).
    Never updated — append-only. This is the raw material for the consolidation sweep.
    """
    __tablename__ = "trajectory"
    __table_args__ = (
        Index("ix_traj_instance_id", "instance_id"),
        Index("ix_traj_host_user_id", "host_user_id"),
        Index("ix_traj_created_at", "created_at"),
        Index("ix_traj_processed", "consolidation_round"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(Text, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    host_user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conversation_id: Mapped[str] = mapped_column(Text, nullable=False)

    # Task
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    task_intent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # LLM-classified: data_query | diagnostic | how_to | clarification | action

    # Plan + execution
    plan_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON-serialized plan steps
    tool_calls_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # [{tool_name, args_summary, success, latency_ms, output_size}]
    stages_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # [{stage, verdict, latency_ms, tokens_used}] from turn_ledger

    # Outcome
    status: Mapped[str] = mapped_column(Text, nullable=False, default="completed")  # completed | failed | cancelled
    final_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # thumbs_up | thumbs_down | accepted | clarified | cancelled
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Skill candidates discovered (if any)
    skill_candidates_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Processing state for consolidation sweep
    consolidation_round: Mapped[int] = mapped_column(Integer, default=0)
    extracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
# P3.1 — Agent registry + declared handoff topology (TASK-BE-03-1)
# ═══════════════════════════════════════════════════════════════════════════════

AGENT_ROLES = frozenset({
    "orchestrator",      # top-level: decomposes tasks, spawns workers, synthesizes
    "researcher",        # read-only: searches knowledge, queries host, returns findings
    "planner",           # decomposes complex questions into multi-step plans
    "critic",            # reviews outputs for safety, grounding, tenancy violations
    "domain_specialist", # instance-specific expert (e.g., "power_grid_analyst")
})


class Agent(Base):
    """An agent is a role, not a process — a DB-backed catalog of who can do what.

    Handoffs between agents are declared edges in `AgentHandoff`; there is no
    free-form agent-to-agent chat (ADR-001: declared topology only).
    """
    __tablename__ = "agents"
    __table_args__ = (
        Index("ix_agents_instance_id", "instance_id"),
        Index("ix_agents_role", "role"),
        UniqueConstraint("instance_id", "name", name="uq_agent_instance_name"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)  # unique within instance
    role: Mapped[str] = mapped_column(Text, nullable=False)  # AGENT_ROLES value
    tool_set_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of tool names
    playbook_blocks_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of block keys
    model_override: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # None = use instance default
    max_turns: Mapped[int] = mapped_column(Integer, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AgentHandoff(Base):
    """A declared handoff edge: from_agent_id → to_agent_id.

    No undeclared handoffs — `can_handoff` only returns True for explicit edges.
    """
    __tablename__ = "agent_handoffs"
    __table_args__ = (
        Index("ix_agent_handoffs_from_agent_id", "from_agent_id"),
        Index("ix_agent_handoffs_to_agent_id", "to_agent_id"),
        UniqueConstraint("from_agent_id", "to_agent_id", name="uq_handoff_pair"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    from_agent_id: Mapped[str] = mapped_column(Text, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    to_agent_id: Mapped[str] = mapped_column(Text, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # why this handoff exists
    max_parallel: Mapped[int] = mapped_column(Integer, default=1)  # how many concurrent workers of this type
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 5 — Typed ontology graph (PR-16)
# ═══════════════════════════════════════════════════════════════════════════════

KG_NODE_TYPES = frozenset({
    "entity",
    "attribute",
    "process",
    "rule",
    "metric",
    "role",
    "api_endpoint",
    "workflow",
    "glossary_term",
})

KG_EDGE_TYPES = frozenset({
    "has_attribute",
    "foreign_key_to",
    "derives_from",
    "governs",
    "triggers",
    "depends_on",
    "is_a",
    "instance_of",
    "mentions",
    "contradicts",
    "related_to",
})

KG_SOURCE_TYPES = frozenset({
    "schema",
    "code",
    "docs",
    "interaction",
    "observation",
    "expert",
})

KG_PROVENANCE_SOURCE_TYPES = frozenset({
    "schema_table",
    "schema_column",
    "api_endpoint",
    "code_module",
    "docs_page",
    "user_input",
})


class KgNode(Base):
    """Typed ontology node — instance-shared (no host_user_id)."""
    __tablename__ = "kg_node"
    __table_args__ = (
        Index("ix_kn_type", "instance_id", "type"),
        Index("ix_kn_canonical", "canonical_ref"),
        CheckConstraint(
            f"type IN ({', '.join(repr(t) for t in sorted(KG_NODE_TYPES))})",
            name="ck_kn_type",
        ),
        CheckConstraint(
            f"source IN ({', '.join(repr(t) for t in sorted(KG_SOURCE_TYPES))})",
            name="ck_kn_source",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(
        Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    properties: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # vector placeholder
    source: Mapped[str] = mapped_column(Text, nullable=False, default="observation")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class KgEdge(Base):
    """Typed directed edge connecting two ontology nodes."""
    __tablename__ = "kg_edge"
    __table_args__ = (
        Index("ix_ke_src_type", "source_node_id", "edge_type"),
        Index("ix_ke_tgt_type", "target_node_id", "edge_type"),
        CheckConstraint(
            f"edge_type IN ({', '.join(repr(t) for t in sorted(KG_EDGE_TYPES))})",
            name="ck_ke_edge_type",
        ),
        CheckConstraint(
            f"source IN ({', '.join(repr(t) for t in sorted(KG_SOURCE_TYPES))})",
            name="ck_ke_source",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(
        Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False
    )
    source_node_id: Mapped[str] = mapped_column(
        Text, ForeignKey("kg_node.id", ondelete="CASCADE"), nullable=False
    )
    target_node_id: Mapped[str] = mapped_column(
        Text, ForeignKey("kg_node.id", ondelete="CASCADE"), nullable=False
    )
    edge_type: Mapped[str] = mapped_column(Text, nullable=False)
    properties: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="observation")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KgProvenance(Base):
    """Tracks the origin of a kg_node — one row per node."""
    __tablename__ = "kg_provenance"
    __table_args__ = (
        CheckConstraint(
            f"source_type IN ({', '.join(repr(t) for t in sorted(KG_PROVENANCE_SOURCE_TYPES))})",
            name="ck_kp_source_type",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    node_id: Mapped[str] = mapped_column(
        Text, ForeignKey("kg_node.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    extraction_batch: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 6 — Procedural memory: Skill model (PR-18)
# ═══════════════════════════════════════════════════════════════════════════════

SKILL_KINDS = frozenset({
    "sql_macro",
    "api_call",
    "prompt_template",
    "multi_step_plan",
    "code_snippet",
    "tool_preset",
    "procedure",
    "heuristic",
    "resolution",
})

SKILL_STATUSES = frozenset({
    "draft",
    "user_approved",
    "instance_promoted",
    "deprecated",
})


class Skill(Base):
    """Reusable procedural skill — per-user ownership, promote to instance-global.

    Tenancy: author_user_id is the creator. Access is status-driven:
      - draft / user_approved → author only
      - instance_promoted → all users of the instance
    """
    __tablename__ = "skill"
    __table_args__ = (
        Index("ix_skill_kind", "instance_id", "kind"),
        Index("ix_skill_status", "instance_id", "status"),
        Index("ix_skill_author", "instance_id", "author_user_id"),
        CheckConstraint(
            f"kind IN ({', '.join(repr(t) for t in sorted(SKILL_KINDS))})",
            name="ck_skill_kind",
        ),
        CheckConstraint(
            f"status IN ({', '.join(repr(t) for t in sorted(SKILL_STATUSES))})",
            name="ck_skill_status",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(
        Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    signature: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # JSON: input/output type schema
    body: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # JSON: the actual skill payload
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    author_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    promoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    promoted_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    last_executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    preconditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provenance_run_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gate_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SkillAdmissionLog(Base):
    """One row per admission-gate evaluation of a Skill.

    Records which critics passed/rejected the skill.  Written by
    ``skills/gate.py:admit_skill()``.
    """
    __tablename__ = "skill_admission_log"
    __table_args__ = (
        Index("ix_skill_admission_log_skill_id", "skill_id"),
        Index("ix_skill_admission_log_instance_id", "instance_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    skill_id: Mapped[str] = mapped_column(
        Text, ForeignKey("skill.id", ondelete="CASCADE"), nullable=False
    )
    instance_id: Mapped[str] = mapped_column(
        Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False
    )
    structural_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    harmlessness_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    consistency_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    marginal_gain_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    structural_flags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    harmlessness_flags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    consistency_flags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    marginal_gain_details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verdict: Mapped[str] = mapped_column(Text, nullable=False)  # "admitted" | "rejected"
    rejected_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # which critic
    admitted_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # "auto" | "admin:{user_id}"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
# Prompt Self-Improvement (BE-01)
# ═══════════════════════════════════════════════════════════════════════════════

class PromptVersion(Base):
    """One version of a synthesized/optimized system prompt for an instance."""

    __tablename__ = "prompt_versions"
    __table_args__ = (
        Index("ix_prompt_versions_instance_id", "instance_id"),
        Index("ix_prompt_versions_active", "instance_id", "is_active"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(
        Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text(16), nullable=False)
    synthesized_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    improvement_round: Mapped[int] = mapped_column(Integer, default=0)
    parent_version_id: Mapped[Optional[str]] = mapped_column(
        Text, ForeignKey("prompt_versions.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PromptEval(Base):
    """Evaluation result for a single query against a prompt version."""

    __tablename__ = "prompt_evals"
    __table_args__ = (
        Index("ix_prompt_evals_version_id", "prompt_version_id"),
        Index("ix_prompt_evals_instance_id", "instance_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    prompt_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("prompt_versions.id", ondelete="CASCADE"), nullable=False
    )
    instance_id: Mapped[str] = mapped_column(
        Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_calls_made: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON
    tool_calls_expected: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    task_completion: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    user_feedback: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # -1/0/+1
    eval_source: Mapped[str] = mapped_column(Text, nullable=False, default="auto")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ═══════════════════════════════════════════════════════════════════════════════
# Playbook Block System (BE-02-1)
# ═══════════════════════════════════════════════════════════════════════════════

BLOCK_KINDS = {
    "persona",
    "scope_boundary",
    "domain_rule",
    "tool_heuristic",
    "lesson",
    "compliance",
    "tone_voice",
}


class PlaybookBlock(Base):
    """Versioned, individually-editable block of the system prompt playbook.

    Each block is a typed, versioned chunk of the system prompt. Assembly
    is handled by ``llm.playbook.PlaybookAssembler``, which loads active
    blocks ordered by priority within each block_type group.
    """

    __tablename__ = "playbook_blocks"
    __table_args__ = (
        Index("ix_playbook_instance_type", "instance_id", "block_type"),
        Index("ix_playbook_instance_active", "instance_id", "is_active"),
        CheckConstraint(
            f"block_type IN ({', '.join(repr(t) for t in sorted(BLOCK_KINDS))})",
            name="ck_playbook_block_type",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(
        Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False
    )
    block_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    provenance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class TaskExecution(Base):
    """Append-only audit log — one row per POST /tasks invocation.

    Written by ``api/tasks.py:create_task`` on every task call.
    """

    __tablename__ = "task_executions"
    __table_args__ = (
        Index("ix_task_executions_instance_id", "instance_id"),
        Index("ix_task_executions_task_type", "task_type"),
        Index("ix_task_executions_created_at", "created_at"),
        Index("ix_task_executions_status", "status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(
        Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False
    )
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    external_task_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # completed | failed | pulse_unavailable
    request_payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    response_payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PulseUser(Base):
    """Local Pulse-native user for standalone instances (auth.mode: local).

    Independent of host-delegated auth — these users exist only within Pulse
    and are scoped to a single instance.
    """

    __tablename__ = "pulse_users"
    __table_args__ = (
        Index("ix_pulse_users_instance_id", "instance_id"),
        UniqueConstraint("instance_id", "username", name="uq_pulse_users_instance_username"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    instance_id: Mapped[str] = mapped_column(
        Text, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False
    )
    username: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
