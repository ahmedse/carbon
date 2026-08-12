"""Django models for the 15 vendored knowledge-graph tables.

These mirror ``ai/engine/knowledge_graph/models.py`` 1:1. All 15 live in the
single ``app_label="ai"`` namespace and inherit :class:`AppScopeMixin`.
"""

from django.db import models

from .base import AppScopeMixin, generate_uuid


class KnowledgeNode(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    node_type = models.TextField(db_index=True)
    name = models.TextField()
    description = models.TextField(default="")
    properties = models.JSONField(default=dict)
    source = models.TextField(default="SCHEMA")
    confidence = models.FloatField(default=0.8)
    verified = models.BooleanField(default=False)
    verification_date = models.DateTimeField(null=True, blank=True)
    module_id = models.TextField(null=True, blank=True, db_index=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_accessed = models.DateTimeField(null=True, blank=True)
    access_count = models.IntegerField(default=0)

    class Meta:
        app_label = "ai"


class KnowledgeEdge(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    source_node_id = models.TextField(db_index=True)
    target_node_id = models.TextField(db_index=True)
    relationship = models.TextField()
    properties = models.JSONField(default=dict)
    confidence = models.FloatField(default=1.0)
    source = models.TextField(default="SCHEMA")
    weight = models.FloatField(default=1.0)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"


class KgQueryFeedback(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    question = models.TextField(default="")
    sql_final = models.TextField(default="")
    succeeded = models.BooleanField(default=False)
    retry_count = models.IntegerField(default=0)
    error_category = models.TextField(default="")
    duration_ms = models.IntegerField(default=0)
    row_count = models.IntegerField(default=0)
    shape = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class KgCacheEntry(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    cache_layer = models.TextField()
    cache_key = models.TextField()
    utterance = models.TextField(default="")
    sql_executed = models.TextField(default="")
    result_json = models.JSONField()
    table_tags = models.JSONField(default=list)
    hit_count = models.IntegerField(default=0)
    ttl_seconds = models.IntegerField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class KgRecoveryLog(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    question = models.TextField(default="")
    error_type = models.TextField(default="")
    recovery_type = models.TextField(default="")
    original_sql = models.TextField(default="")
    repaired_sql = models.TextField(default="")
    succeeded = models.BooleanField(default=False)
    correction_description = models.TextField(default="")
    retry_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class KgFeedbackRecord(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    conversation_id = models.TextField(db_index=True)
    message_id = models.TextField(default="")
    signal_type = models.TextField(db_index=True)
    user_id = models.TextField(default="")
    original_utterance = models.TextField(default="")
    resolved_utterance = models.TextField(default="")
    generated_sql = models.TextField(default="")
    corrected_sql = models.TextField(null=True, blank=True)
    user_comment = models.TextField(null=True, blank=True)
    quality_score = models.FloatField(default=0.7)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class KgGoldenPair(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    question = models.TextField()
    sql = models.TextField()
    source_feedback_id = models.TextField(null=True, blank=True)
    review_status = models.TextField(default="pending")
    reviewed_by = models.TextField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    tags = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class KgReviewItem(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    category = models.TextField()
    title = models.TextField()
    description = models.TextField(default="")
    evidence_json = models.JSONField(default=list)
    frequency = models.IntegerField(default=1)
    status = models.TextField(default="pending")
    resolution = models.TextField(null=True, blank=True)
    reviewed_by = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"


class KgQualityScore(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    dimension = models.TextField()
    dimension_value = models.TextField(default="all")
    date = models.TextField()
    score = models.FloatField()
    sample_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class KgQueryPlan(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    conversation_id = models.TextField(db_index=True)
    original_utterance = models.TextField()
    pattern = models.TextField(default="custom")
    step_count = models.IntegerField(default=0)
    status = models.TextField(default="planned")
    synthesis_instruction = models.TextField(default="")
    result_summary = models.JSONField(null=True, blank=True)
    total_duration_ms = models.IntegerField(default=0)
    total_llm_calls = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "ai"


class KgPlanStep(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    plan_id = models.TextField(db_index=True)
    step_order = models.IntegerField()
    intent = models.TextField()
    depends_on = models.JSONField(default=list)
    generated_sql = models.TextField(null=True, blank=True)
    result_json = models.JSONField(null=True, blank=True)
    branch_condition = models.TextField(null=True, blank=True)
    status = models.TextField(default="pending")
    error_message = models.TextField(null=True, blank=True)
    duration_ms = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class KgDomainPack(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    version = models.IntegerField()
    status = models.TextField(default="active")
    trigger = models.TextField(default="manual")
    pack_json = models.JSONField()
    changelog_json = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"
        constraints = [
            models.UniqueConstraint(fields=["instance_id", "version"], name="uq_kdp_instance_version"),
        ]


class KgBootstrapRun(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    trigger = models.TextField()
    crawlers_run = models.JSONField(default=list)
    domain_pack_id = models.TextField(null=True, blank=True)
    previous_pack_id = models.TextField(null=True, blank=True)
    status = models.TextField(default="running")
    error_message = models.TextField(null=True, blank=True)
    duration_ms = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class KgProactiveTrigger(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    name = models.TextField()
    category = models.TextField(db_index=True)
    description = models.TextField()
    severity = models.TextField(default="info")
    enabled = models.BooleanField(default=True)
    condition_json = models.JSONField()
    data_sources_json = models.JSONField(default=list)
    context_queries_json = models.JSONField(default=list)
    recommended_actions_json = models.JSONField(default=list)
    recipients_json = models.JSONField(default=list)
    cooldown_seconds = models.IntegerField(default=3600)
    last_fired_at = models.DateTimeField(null=True, blank=True)
    fire_count = models.IntegerField(default=0)
    source = models.TextField(default="manual")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"


class KgProactiveInsight(AppScopeMixin):
    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    trigger_id = models.TextField(null=True, blank=True, db_index=True)
    insight_type = models.TextField(db_index=True)
    severity = models.TextField(default="info")
    title = models.TextField()
    narrative = models.TextField()
    context_json = models.JSONField(default=dict)
    recommended_actions_json = models.JSONField(default=list)
    disposition = models.TextField(default="pending")
    dismissed_reason = models.TextField(null=True, blank=True)
    group_id = models.TextField(null=True, blank=True, db_index=True)
    delivery_channel = models.TextField(default="websocket")
    delivered_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"
