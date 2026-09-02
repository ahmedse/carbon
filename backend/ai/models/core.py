"""Django models for the 34 vendored engine core tables.

These mirror ``ai/engine/core/models.py`` 1:1 (Text→TextField, DateTime→
DateTimeField, JSON-string→JSONField, Float→FloatField, Boolean→BooleanField,
Integer→IntegerField). All 34 models live in the single ``app_label="ai"``
namespace and inherit :class:`AppScopeMixin` for CBAC partitioning.

Cross-table references are kept as plain string columns (mirroring the
engine's string-UUID references) — no Django ``ForeignKey`` is introduced, so
the migration namespace stays simple and the layer stays relocatable.
"""

from django.db import models

from .base import AppScopeMixin, generate_uuid


class Instance(AppScopeMixin):
    """A Pulse instance. Single-tenant in Carbon (app_identifier="carbon")."""

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    name = models.TextField(unique=True)
    display_name = models.TextField()
    host_db_url = models.TextField()
    host_api_url = models.TextField()
    host_api_token = models.TextField(null=True, blank=True)
    status = models.TextField(default="active")
    config = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"


class Conversation(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    user_identifier = models.TextField(null=True, blank=True)
    page_context = models.TextField(null=True, blank=True)
    title = models.TextField(null=True, blank=True)
    mode = models.TextField(default="normal")
    archived = models.BooleanField(default=False)
    compaction_summary = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "ai"


class Message(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    conversation_id = models.TextField(db_index=True)
    role = models.TextField()
    content = models.TextField()
    metadata_json = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class MemoryLongTerm(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    category = models.TextField(db_index=True)
    content = models.TextField()
    source = models.TextField(null=True, blank=True)
    confidence = models.FloatField(default=1.0)
    decay_at = models.DateTimeField(null=True, blank=True)
    archived = models.BooleanField(default=False)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    superseded_by = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now_add=True)
    use_count = models.IntegerField(default=0)
    memory_type = models.CharField(max_length=20, null=True, blank=True, db_index=True)

    class Meta:
        app_label = "ai"


class MemoryEpisodic(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    event_type = models.TextField()
    summary = models.TextField()
    details = models.JSONField(null=True, blank=True)
    causal_chain = models.TextField(null=True, blank=True)
    caused_by_episode_id = models.TextField(null=True, blank=True)
    relevance_score = models.FloatField(default=1.0)
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    archived = models.BooleanField(default=False)
    occurred_at = models.DateTimeField()
    learned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class KnowledgeEntity(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    entity_type = models.TextField()
    name = models.TextField()
    schema_json = models.JSONField(null=True, blank=True)
    semantic_description = models.TextField(null=True, blank=True)
    relationships = models.JSONField(null=True, blank=True)
    last_introspected = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class SystemSnapshot(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    snapshot_data = models.JSONField(null=True, blank=True)
    diff_from_previous = models.JSONField(null=True, blank=True)
    summary = models.TextField(null=True, blank=True)
    taken_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class Notification(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    severity = models.TextField()
    title = models.TextField()
    body = models.TextField(null=True, blank=True)
    visibility = models.CharField(max_length=16, default="shared")
    acknowledged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class Feedback(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    message_id = models.TextField(db_index=True)
    rating = models.IntegerField()
    correction_text = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class UserKey(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    username = models.TextField()
    display_name = models.TextField(null=True, blank=True)
    email = models.TextField(null=True, blank=True)
    roles_json = models.JSONField(null=True, blank=True)
    key_prefix = models.TextField()
    key_hash = models.TextField(unique=True)
    host_token = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "ai"


class Insight(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    insight_type = models.TextField(db_index=True)
    title = models.TextField()
    content = models.TextField()
    evidence = models.JSONField(null=True, blank=True)
    confidence = models.FloatField(default=0.7)
    archived = models.BooleanField(default=False)
    visibility = models.CharField(max_length=16, default="shared")
    created_at = models.DateTimeField(auto_now_add=True)
    superseded_by = models.TextField(null=True, blank=True)

    class Meta:
        app_label = "ai"


class ToolExecution(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    conversation_id = models.TextField(db_index=True)
    tool_name = models.TextField()
    input_params = models.JSONField(null=True, blank=True)
    output = models.JSONField(null=True, blank=True)
    status = models.TextField(default="pending_confirmation")
    confirmed_by_user = models.BooleanField(default=False)
    executed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "ai"


class LLMCallLog(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    conversation_id = models.TextField(db_index=True)
    model = models.TextField()
    llm_calls = models.IntegerField(default=1)
    total_tokens = models.IntegerField(default=0)
    cost_usd = models.FloatField(default=0.0)
    duration_ms = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class ConversationContextRecord(AppScopeMixin):
    conversation_id = models.CharField(max_length=36, primary_key=True)
    instance_id = models.TextField(db_index=True)
    session_json = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"


class AuditLog(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(null=True, blank=True, db_index=True)
    actor = models.TextField()
    actor_type = models.TextField()
    action = models.TextField()
    target = models.TextField(null=True, blank=True)
    detail = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class OpsRun(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    workflow = models.TextField()
    status = models.TextField(default="running")
    dry_run = models.BooleanField(default=False)
    csv_filename = models.TextField(null=True, blank=True)
    input_hash = models.TextField(null=True, blank=True)
    dataset_ref = models.TextField(null=True, blank=True)
    engine_ref = models.TextField(null=True, blank=True)
    rows_ingested = models.IntegerField(default=0)
    rows_skipped = models.IntegerField(default=0)
    date_start = models.TextField(null=True, blank=True)
    date_end = models.TextField(null=True, blank=True)
    model_version = models.TextField(null=True, blank=True)
    output_location = models.TextField(null=True, blank=True)
    steps_json = models.JSONField(null=True, blank=True)
    provenance_json = models.JSONField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "ai"


class CsvUpload(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    conversation_id = models.TextField(null=True, blank=True)
    filename = models.TextField(null=True, blank=True)
    content = models.TextField()
    row_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class VectorEmbedding(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    collection = models.TextField(db_index=True)
    instance_id = models.TextField(db_index=True)
    document = models.TextField()
    metadata_json = models.JSONField(null=True, blank=True)
    embedding_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class TurnLedgerRow(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    turn_id = models.TextField(db_index=True)
    instance_id = models.TextField(db_index=True)
    conversation_id = models.TextField(db_index=True)
    stage = models.TextField()
    stage_index = models.IntegerField()
    payload_json = models.JSONField(null=True, blank=True)
    latency_ms = models.FloatField(null=True, blank=True)
    tokens_used = models.IntegerField(null=True, blank=True)
    model_used = models.TextField(null=True, blank=True)
    verdict = models.TextField(null=True, blank=True)
    flags_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class Run(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    conversation_id = models.TextField(db_index=True)
    user_message = models.TextField()
    status = models.TextField(default="pending")
    plan_json = models.JSONField(null=True, blank=True)
    final_response = models.TextField(null=True, blank=True)
    total_tokens = models.IntegerField(default=0)
    total_llm_calls = models.IntegerField(default=0)
    total_latency_ms = models.FloatField(null=True, blank=True)
    working_notes = models.JSONField(null=True, blank=True)
    token_budget = models.IntegerField(null=True, blank=True)
    tokens_consumed = models.IntegerField(default=0)
    fan_out_justification = models.TextField(null=True, blank=True)
    worker_budgets_json = models.JSONField(null=True, blank=True)
    budget_exceeded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "ai"


class RunStep(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    run_id = models.TextField(db_index=True)
    step_index = models.IntegerField()
    intent = models.TextField()
    tool_name = models.TextField(null=True, blank=True)
    tool_args_json = models.JSONField(null=True, blank=True)
    depends_on_json = models.JSONField(null=True, blank=True)
    status = models.TextField(default="pending")
    draft_text = models.TextField(null=True, blank=True)
    critic_verdict = models.TextField(null=True, blank=True)
    critic_flags_json = models.JSONField(null=True, blank=True)
    tool_output_json = models.JSONField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    latency_ms = models.FloatField(null=True, blank=True)
    confirmation_token = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"


class RunArtifact(models.Model):
    """A durable file produced by a plan step (W5-C).

    First-class artifact delivery: steps that generate Word/Excel/CSV/JSON
    files persist them here and expose a download link. Scoped via
    ``run.host_user_id`` (CBAC) — no ``AppScopeMixin`` of its own, matching
    the plans ownership boundary (RULE_20: no upward imports).
    """

    run = models.ForeignKey(
        Run, on_delete=models.CASCADE, related_name="artifacts"
    )
    step_index = models.IntegerField(null=True)
    name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    file = models.FileField(upload_to="ai_artifacts/%Y/%m/")
    size_bytes = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"
        ordering = ["created_at"]


class PlanTemplate(AppScopeMixin):
    """Reusable plan template (Gap #3) — a promoted, named ``plan_json``.

    A template is NOT an execution ledger row: it captures a plan's
    ``plan_json`` (steps/phases/synthesis) plus a user-facing name and
    description. Instantiating a template clones it into a fresh ``Run``
    (``pending_approval``) via the same clone path as ``fork_plan``.
    """

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    name = models.TextField()
    description = models.TextField(null=True, blank=True)
    plan_json = models.JSONField(null=True, blank=True)
    source_plan_id = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"


class RunSchedule(models.Model):
    """Scheduled plan materialization (F-29 / W6-E).

    Recurring ``cron_expr`` (standard 5-field cron, evaluated with
    apscheduler's ``CronTrigger``) or a one-off ``run_at``. The
    ``run_due_schedules`` management command materializes each due schedule
    into a fresh ``pending_approval`` Run (RULE_21 — nothing executes without
    approval), deduped via ``next_run_at``/``last_run_at`` so repeated or
    concurrent invocations never double-fire. Schedules are private to their
    owner (``host_user_id``, CBAC), mirroring ``PlanTemplate``.
    """

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    host_user_id = models.CharField(
        max_length=255, null=True, blank=True, db_index=True
    )
    name = models.TextField()
    description = models.TextField(null=True, blank=True)
    template = models.ForeignKey(
        "ai.PlanTemplate",
        on_delete=models.CASCADE,
        related_name="schedules",
        null=True,
        blank=True,
    )
    plan_json = models.JSONField(null=True, blank=True)  # snapshot fallback
    cron_expr = models.TextField(null=True, blank=True)
    run_at = models.DateTimeField(null=True, blank=True)
    enabled = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"
        ordering = ["next_run_at"]


class Trajectory(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    run_id = models.TextField(db_index=True)
    instance_id = models.TextField(db_index=True)
    conversation_id = models.TextField(db_index=True)
    user_message = models.TextField()
    task_intent = models.TextField(null=True, blank=True)
    plan_json = models.JSONField(null=True, blank=True)
    tool_calls_json = models.JSONField(null=True, blank=True)
    stages_json = models.JSONField(null=True, blank=True)
    status = models.TextField(default="completed")
    final_response = models.TextField(null=True, blank=True)
    user_feedback = models.TextField(null=True, blank=True)
    total_tokens = models.IntegerField(default=0)
    total_latency_ms = models.FloatField(null=True, blank=True)
    skill_candidates_json = models.JSONField(null=True, blank=True)
    consolidation_round = models.IntegerField(default=0)
    extracted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class Agent(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    name = models.TextField()
    role = models.TextField(db_index=True)
    tool_set_json = models.JSONField(null=True, blank=True)
    playbook_blocks_json = models.JSONField(null=True, blank=True)
    model_override = models.TextField(null=True, blank=True)
    max_turns = models.IntegerField(default=3)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"
        constraints = [
            models.UniqueConstraint(fields=["instance_id", "name"], name="uq_agent_instance_name"),
        ]


class AgentHandoff(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    from_agent_id = models.TextField(db_index=True)
    to_agent_id = models.TextField(db_index=True)
    description = models.TextField(null=True, blank=True)
    max_parallel = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"
        constraints = [
            models.UniqueConstraint(fields=["from_agent_id", "to_agent_id"], name="uq_handoff_pair"),
        ]


class KgNode(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    type = models.TextField(db_index=True)
    name = models.TextField()
    canonical_ref = models.TextField(null=True, blank=True)
    properties = models.JSONField(default=dict)
    embedding = models.JSONField(null=True, blank=True)
    source = models.TextField(default="observation")
    confidence = models.FloatField(default=1.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"


class KgEdge(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    source_node_id = models.TextField(db_index=True)
    target_node_id = models.TextField(db_index=True)
    edge_type = models.TextField()
    properties = models.JSONField(default=dict)
    confidence = models.FloatField(default=1.0)
    source = models.TextField(default="observation")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class KgProvenance(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    node_id = models.TextField(unique=True)
    source_type = models.TextField()
    source_ref = models.TextField()
    extracted_at = models.DateTimeField(auto_now_add=True)
    extraction_batch = models.TextField(null=True, blank=True)

    class Meta:
        app_label = "ai"


class Skill(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    name = models.TextField()
    description = models.TextField(default="")
    signature = models.JSONField(default=dict)
    body = models.JSONField(default=dict)
    kind = models.TextField(db_index=True)
    status = models.TextField(default="draft")
    author_user_id = models.TextField()
    promoted_at = models.DateTimeField(null=True, blank=True)
    promoted_by = models.TextField(null=True, blank=True)
    usage_count = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)
    avg_latency_ms = models.FloatField(default=0.0)
    last_executed_at = models.DateTimeField(null=True, blank=True)
    preconditions = models.TextField(null=True, blank=True)
    provenance_run_ids = models.TextField(null=True, blank=True)
    gate_status = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"


class SkillAdmissionLog(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    skill_id = models.TextField(db_index=True)
    instance_id = models.TextField(db_index=True)
    structural_passed = models.BooleanField(default=False)
    harmlessness_passed = models.BooleanField(default=False)
    consistency_passed = models.BooleanField(default=False)
    marginal_gain_passed = models.BooleanField(default=False)
    structural_flags_json = models.JSONField(null=True, blank=True)
    harmlessness_flags_json = models.JSONField(null=True, blank=True)
    consistency_flags_json = models.JSONField(null=True, blank=True)
    marginal_gain_details_json = models.JSONField(null=True, blank=True)
    verdict = models.TextField()
    rejected_by = models.TextField(null=True, blank=True)
    admitted_by = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class PromptVersion(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    prompt_text = models.TextField()
    content_hash = models.CharField(max_length=16)
    synthesized_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    score = models.FloatField(null=True, blank=True)
    improvement_round = models.IntegerField(default=0)
    parent_version_id = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class PromptEval(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    prompt_version_id = models.TextField(db_index=True)
    instance_id = models.TextField(db_index=True)
    conversation_id = models.TextField(null=True, blank=True)
    query_text = models.TextField()
    response_text = models.TextField(null=True, blank=True)
    tool_calls_made = models.JSONField(default=list)
    tool_calls_expected = models.JSONField(null=True, blank=True)
    task_completion = models.BooleanField(null=True, blank=True)
    relevance_score = models.FloatField(null=True, blank=True)
    user_feedback = models.IntegerField(null=True, blank=True)
    eval_source = models.TextField(default="auto")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class PlaybookBlock(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    block_type = models.TextField(db_index=True)
    title = models.TextField(default="")
    content = models.TextField()
    version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)
    provenance = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"


class TaskExecution(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    task_type = models.TextField(db_index=True)
    external_task_id = models.TextField()
    status = models.TextField(db_index=True)
    request_payload = models.JSONField()
    response_payload = models.JSONField()
    error_message = models.TextField(null=True, blank=True)
    execution_ms = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class PulseUser(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    username = models.TextField()
    password_hash = models.TextField()
    display_name = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "ai"
        constraints = [
            models.UniqueConstraint(fields=["instance_id", "username"], name="uq_pulse_users_instance_username"),
        ]


class CognitionSweepRun(AppScopeMixin):
    """Phase D — durable per-task sweep-run ledger for the cognition scheduler.

    One row per scheduled task name, upserted by ``loop._tracked`` after each
    run so the Pulse admin surface can report sweep status without inspecting
    the in-process scheduler state.
    """

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    task_name = models.TextField(db_index=True)
    last_run = models.DateTimeField(null=True, blank=True)
    last_status = models.TextField(default="pending")
    last_duration_ms = models.IntegerField(default=0)
    run_count = models.IntegerField(default=0)
    last_error = models.TextField(null=True, blank=True)

    class Meta:
        app_label = "ai"


class AcceptanceReport(AppScopeMixin):
    """Flight Director closure — one row per finalized run (Phase 25-A).

    Written by ``FlightDirector.finalize_report`` after run acceptance
    checks: per-requirement verdicts (``report_json``), aggregate run
    metrics (``metrics_json``), and the run's ``final_response`` narrative.
    """

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    run = models.ForeignKey(
        Run, on_delete=models.CASCADE, related_name="acceptance_reports"
    )
    status = models.TextField(default="met")  # met | partial | missed
    report_json = models.JSONField(default=dict)
    metrics_json = models.JSONField(default=dict)
    narrative = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"
        ordering = ["-created_at"]

    def __str__(self):
        return f"AcceptanceReport {self.id} ({self.status})"


class LearningOutcome(AppScopeMixin):
    """Flight Director outcome→learning mapping (Phase 25-A).

    One row per deterministic learning pattern detected from a run's
    acceptance report; deduped per (``run``, ``pattern``) so each pattern is
    recorded at most once per run. Target: ``playbook`` | ``prompts``.
    """

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    run = models.ForeignKey(Run, on_delete=models.CASCADE)
    pattern = models.TextField()
    target = models.TextField(default="playbook")
    payload_json = models.JSONField(default=dict)
    status = models.TextField(default="queued")  # queued | applied | skipped
    applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "pattern"],
                name="uq_learningoutcome_run_pattern",
            ),
        ]

    def __str__(self):
        return f"LearningOutcome {self.pattern} ({self.status})"
