"""
Pulse engine durable-state models as stdlib dataclasses (single-ORM, P2-05).

The engine mirrors the canonical Django ORM models (``ai.models.core`` and
``ai.models.knowledge_graph``) as plain ``@dataclass`` value objects so the
engine stays ORM-agnostic. The Django store (``ai.store``) maps these to/from
Django instances by attribute name.

Every field carries a default so partial construction matches the retired
SQLAlchemy behaviour: unset columns read back as ``None`` until the store
persists the object and back-fills server-side defaults. ``Optional`` therefore
means "may be unset at the engine layer", not "nullable at the DB layer".
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ai.engine.core.clock import utcnow  # noqa: F401  (re-exported for callers)


def generate_uuid() -> str:
    """Return a stringified UUID4."""
    return str(uuid.uuid4())


@dataclass
class Instance:
    id: str = field(default_factory=generate_uuid)
    name: Optional[str] = None
    display_name: Optional[str] = None
    host_db_url: Optional[str] = None
    host_api_url: Optional[str] = None
    host_api_token: Optional[str] = None
    status: str = "active"
    config: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Conversation:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    user_identifier: Optional[str] = None
    host_user_id: Optional[str] = None
    visibility: str = "private"
    page_context: Optional[str] = None
    title: Optional[str] = None
    mode: str = "normal"
    archived: bool = False
    compaction_summary: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


@dataclass
class Message:
    id: str = field(default_factory=generate_uuid)
    conversation_id: Optional[str] = None
    role: Optional[str] = None
    content: Optional[str] = None
    metadata_json: Optional[str] = None
    host_user_id: Optional[str] = None
    visibility: str = "private"
    timestamp: Optional[datetime] = None


@dataclass
class MemoryLongTerm:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    category: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None
    confidence: float = 1.0
    decay_at: Optional[datetime] = None
    archived: bool = False
    host_user_id: Optional[str] = None
    visibility: str = "private"
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    superseded_by: Optional[str] = None
    created_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    use_count: int = 0


@dataclass
class MemoryEpisodic:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    event_type: Optional[str] = None
    summary: Optional[str] = None
    details: Optional[str] = None
    causal_chain: Optional[str] = None
    caused_by_episode_id: Optional[str] = None
    relevance_score: float = 1.0
    last_accessed_at: Optional[datetime] = None
    archived: bool = False
    host_user_id: Optional[str] = None
    visibility: str = "private"
    occurred_at: Optional[datetime] = None
    learned_at: Optional[datetime] = None


@dataclass
class KnowledgeEntity:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    entity_type: Optional[str] = None
    name: Optional[str] = None
    schema_json: Optional[str] = None
    semantic_description: Optional[str] = None
    relationships: Optional[str] = None
    last_introspected: Optional[datetime] = None


@dataclass
class SystemSnapshot:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    snapshot_data: Optional[str] = None
    diff_from_previous: Optional[str] = None
    summary: Optional[str] = None
    taken_at: Optional[datetime] = None


@dataclass
class Notification:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    severity: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    host_user_id: Optional[str] = None
    visibility: str = "shared"
    acknowledged: bool = False
    created_at: Optional[datetime] = None


@dataclass
class Feedback:
    id: str = field(default_factory=generate_uuid)
    message_id: Optional[str] = None
    rating: Optional[int] = None
    correction_text: Optional[str] = None
    host_user_id: Optional[str] = None
    visibility: str = "private"
    created_at: Optional[datetime] = None


@dataclass
class UserKey:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    email: Optional[str] = None
    roles_json: Optional[str] = None
    key_prefix: Optional[str] = None
    key_hash: Optional[str] = None
    host_token: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None


@dataclass
class Insight:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    insight_type: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    evidence: Optional[str] = None
    confidence: float = 0.7
    archived: bool = False
    host_user_id: Optional[str] = None
    visibility: str = "shared"
    created_at: Optional[datetime] = None
    superseded_by: Optional[str] = None


@dataclass
class ToolExecution:
    id: str = field(default_factory=generate_uuid)
    conversation_id: Optional[str] = None
    tool_name: Optional[str] = None
    input_params: Optional[str] = None
    output: Optional[str] = None
    status: str = "pending_confirmation"
    confirmed_by_user: bool = False
    host_user_id: Optional[str] = None
    visibility: str = "private"
    executed_at: Optional[datetime] = None


@dataclass
class LLMCallLog:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    conversation_id: Optional[str] = None
    model: Optional[str] = None
    llm_calls: int = 1
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    created_at: Optional[datetime] = None


@dataclass
class ConversationContextRecord:
    conversation_id: Optional[str] = None
    instance_id: Optional[str] = None
    session_json: Optional[str] = None
    updated_at: Optional[datetime] = None


@dataclass
class AuditLog:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    actor: Optional[str] = None
    actor_type: Optional[str] = None
    action: Optional[str] = None
    target: Optional[str] = None
    detail: Optional[str] = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class OpsRun:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    workflow: Optional[str] = None
    status: str = "running"
    dry_run: bool = False
    csv_filename: Optional[str] = None
    input_hash: Optional[str] = None
    dataset_ref: Optional[str] = None
    engine_ref: Optional[str] = None
    rows_ingested: int = 0
    rows_skipped: int = 0
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    model_version: Optional[str] = None
    output_location: Optional[str] = None
    steps_json: Optional[str] = None
    provenance_json: Optional[str] = None
    error: Optional[str] = None
    host_user_id: Optional[str] = None
    visibility: str = "private"
    created_at: datetime = field(default_factory=utcnow)
    completed_at: Optional[datetime] = None


@dataclass
class CsvUpload:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    conversation_id: Optional[str] = None
    host_user_id: Optional[str] = None
    filename: Optional[str] = None
    content: Optional[str] = None
    row_count: int = 0
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class VectorEmbedding:
    id: str = field(default_factory=generate_uuid)
    collection: Optional[str] = None
    instance_id: Optional[str] = None
    document: Optional[str] = None
    metadata_json: Optional[str] = None
    embedding_json: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class TurnLedgerRow:
    id: str = field(default_factory=generate_uuid)
    turn_id: Optional[str] = None
    instance_id: Optional[str] = None
    host_user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    stage: Optional[str] = None
    stage_index: Optional[int] = None
    payload_json: Optional[str] = None
    latency_ms: Optional[float] = None
    tokens_used: Optional[int] = None
    model_used: Optional[str] = None
    verdict: Optional[str] = None
    flags_json: Optional[str] = None
    created_at: Optional[datetime] = None


# ═══════════════════════════════════════════════════════════════════════════════
# P1.1 — Durable multi-step run persistence (TASK-BE-01-1)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Run:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    conversation_id: Optional[str] = None
    host_user_id: Optional[str] = None
    user_message: Optional[str] = None
    status: str = "pending"
    plan_json: Optional[str] = None
    final_response: Optional[str] = None
    total_tokens: int = 0
    total_llm_calls: int = 0
    total_latency_ms: Optional[float] = None
    working_notes: Optional[str] = None
    token_budget: Optional[int] = None
    tokens_consumed: int = 0
    fan_out_justification: Optional[str] = None
    worker_budgets_json: Optional[str] = None
    budget_exceeded: bool = False
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    completed_at: Optional[datetime] = None


@dataclass
class RunStep:
    id: str = field(default_factory=generate_uuid)
    run_id: Optional[str] = None
    step_index: Optional[int] = None
    intent: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args_json: Optional[str] = None
    depends_on_json: Optional[str] = None
    status: str = "pending"
    draft_text: Optional[str] = None
    critic_verdict: Optional[str] = None
    critic_flags_json: Optional[str] = None
    tool_output_json: Optional[str] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None
    confirmation_token: Optional[str] = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
# P4.1 — Append-only trajectory store (TASK-BE-04-1)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Trajectory:
    id: str = field(default_factory=generate_uuid)
    run_id: Optional[str] = None
    instance_id: Optional[str] = None
    host_user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    user_message: Optional[str] = None
    task_intent: Optional[str] = None
    plan_json: Optional[str] = None
    tool_calls_json: Optional[str] = None
    stages_json: Optional[str] = None
    status: str = "completed"
    final_response: Optional[str] = None
    user_feedback: Optional[str] = None
    total_tokens: int = 0
    total_latency_ms: Optional[float] = None
    skill_candidates_json: Optional[str] = None
    consolidation_round: int = 0
    extracted_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
# P3.1 — Agent registry + declared handoff topology (TASK-BE-03-1)
# ═══════════════════════════════════════════════════════════════════════════════

AGENT_ROLES = frozenset({
    "orchestrator",
    "researcher",
    "planner",
    "critic",
    "domain_specialist",
})


@dataclass
class Agent:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    tool_set_json: Optional[str] = None
    playbook_blocks_json: Optional[str] = None
    model_override: Optional[str] = None
    max_turns: int = 3
    is_active: bool = True
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass
class AgentHandoff:
    id: str = field(default_factory=generate_uuid)
    from_agent_id: Optional[str] = None
    to_agent_id: Optional[str] = None
    description: Optional[str] = None
    max_parallel: int = 1
    created_at: datetime = field(default_factory=utcnow)


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


@dataclass
class KgNode:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    type: Optional[str] = None
    name: Optional[str] = None
    canonical_ref: Optional[str] = None
    properties: str = "{}"
    embedding: Optional[str] = None
    source: str = "observation"
    confidence: float = 1.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class KgEdge:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    source_node_id: Optional[str] = None
    target_node_id: Optional[str] = None
    edge_type: Optional[str] = None
    properties: str = "{}"
    confidence: float = 1.0
    source: str = "observation"
    created_at: Optional[datetime] = None


@dataclass
class KgProvenance:
    id: str = field(default_factory=generate_uuid)
    node_id: Optional[str] = None
    source_type: Optional[str] = None
    source_ref: Optional[str] = None
    extracted_at: Optional[datetime] = None
    extraction_batch: Optional[str] = None


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


@dataclass
class Skill:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    name: Optional[str] = None
    description: str = ""
    signature: str = "{}"
    body: str = "{}"
    kind: Optional[str] = None
    status: str = "draft"
    author_user_id: Optional[str] = None
    promoted_at: Optional[datetime] = None
    promoted_by: Optional[str] = None
    usage_count: int = 0
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    last_executed_at: Optional[datetime] = None
    preconditions: Optional[str] = None
    provenance_run_ids: Optional[str] = None
    gate_status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class SkillAdmissionLog:
    id: str = field(default_factory=generate_uuid)
    skill_id: Optional[str] = None
    instance_id: Optional[str] = None
    structural_passed: bool = False
    harmlessness_passed: bool = False
    consistency_passed: bool = False
    marginal_gain_passed: bool = False
    structural_flags_json: Optional[str] = None
    harmlessness_flags_json: Optional[str] = None
    consistency_flags_json: Optional[str] = None
    marginal_gain_details_json: Optional[str] = None
    verdict: Optional[str] = None
    rejected_by: Optional[str] = None
    admitted_by: Optional[str] = None
    created_at: datetime = field(default_factory=utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
# Prompt Self-Improvement (BE-01)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PromptVersion:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    prompt_text: Optional[str] = None
    content_hash: Optional[str] = None
    synthesized_at: Optional[datetime] = None
    is_active: bool = True
    score: Optional[float] = None
    improvement_round: int = 0
    parent_version_id: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class PromptEval:
    id: str = field(default_factory=generate_uuid)
    prompt_version_id: Optional[str] = None
    instance_id: Optional[str] = None
    conversation_id: Optional[str] = None
    query_text: Optional[str] = None
    response_text: Optional[str] = None
    tool_calls_made: str = "[]"
    tool_calls_expected: Optional[str] = None
    task_completion: Optional[bool] = None
    relevance_score: Optional[float] = None
    user_feedback: Optional[int] = None
    eval_source: str = "auto"
    created_at: Optional[datetime] = None


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


@dataclass
class PlaybookBlock:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    block_type: Optional[str] = None
    title: str = ""
    content: Optional[str] = None
    version: int = 1
    is_active: bool = True
    priority: int = 0
    provenance: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class TaskExecution:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    task_type: Optional[str] = None
    external_task_id: Optional[str] = None
    status: Optional[str] = None
    request_payload: Optional[str] = None
    response_payload: Optional[str] = None
    error_message: Optional[str] = None
    execution_ms: int = 0
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class PulseUser:
    id: str = field(default_factory=generate_uuid)
    instance_id: Optional[str] = None
    username: Optional[str] = None
    password_hash: Optional[str] = None
    display_name: Optional[str] = None
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
