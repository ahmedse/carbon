"""Django admin registration for AI Workspace models."""

from django.contrib import admin

from .models import (
    AcceptanceReport,
    AIConversation,
    AIMessage,
    ApprovalGrant,
    AutonomyOverride,
    Capability,
    HumanTask,
    LearningOutcome,
    ProcessDefinition,
    ProcessInterview,
)


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "conversation_type", "status", "title", "created_at")
    list_filter = ("conversation_type", "status")
    search_fields = ("title", "user__username")
    readonly_fields = ("id", "created_at", "updated_at", "scope_json")


@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "role", "created_at")
    list_filter = ("role",)
    readonly_fields = ("id", "created_at")


@admin.register(AcceptanceReport)
class AcceptanceReportAdmin(admin.ModelAdmin):
    """Read-only list view for Flight Director acceptance reports."""

    list_display = ("id", "run", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = (
        "id",
        "run",
        "status",
        "report_json",
        "metrics_json",
        "narrative",
        "created_at",
    )


@admin.register(LearningOutcome)
class LearningOutcomeAdmin(admin.ModelAdmin):
    """Read-only list view for Flight Director learning outcomes."""

    list_display = ("id", "run", "pattern", "target", "status", "created_at")
    list_filter = ("status", "target")
    readonly_fields = (
        "id",
        "run",
        "pattern",
        "target",
        "payload_json",
        "status",
        "applied_at",
        "created_at",
    )


@admin.register(ApprovalGrant)
class ApprovalGrantAdmin(admin.ModelAdmin):
    """Read-only list view for durable business approvals (P3-06)."""

    list_display = (
        "id",
        "capability",
        "process_version",
        "status",
        "granted_by",
        "expires_at",
        "created_at",
    )
    list_filter = ("status", "capability")
    search_fields = ("id", "capability", "granted_by", "process_instance", "object_id")
    readonly_fields = (
        "id",
        "process_instance",
        "object_id",
        "object_type",
        "process_version",
        "capability",
        "capability_version",
        "canonical_args",
        "object_revisions",
        "evidence_digest",
        "effect_limits",
        "expires_at",
        "status",
        "granted_by",
        "created_at",
        "revoked_at",
    )


@admin.register(Capability)
class CapabilityAdmin(admin.ModelAdmin):
    """Read-only list view for durable capability contracts (P3-01)."""

    list_display = (
        "capability_id",
        "kind",
        "owner",
        "requires_confirmation",
        "version",
        "updated_at",
    )
    list_filter = ("kind", "requires_confirmation")
    search_fields = ("capability_id", "business_name", "purpose", "host_action")
    readonly_fields = (
        "id",
        "capability_id",
        "business_name",
        "purpose",
        "kind",
        "inputs",
        "preconditions",
        "permissions",
        "effects",
        "side_effects",
        "approval_requirements",
        "requires_confirmation",
        "idempotency",
        "verification",
        "failure_semantics",
        "recovery",
        "owner",
        "version",
        "host_action",
        "created_at",
        "updated_at",
    )


@admin.register(ProcessInterview)
class ProcessInterviewAdmin(admin.ModelAdmin):
    """Read-only list view for process-owner interview provenance (P3-04)."""

    list_display = ("process_id", "status", "signed_by", "signed_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("process_id", "signed_by")
    readonly_fields = (
        "id",
        "process_id",
        "questions",
        "answers",
        "status",
        "signed_by",
        "signed_at",
        "signature_digest",
        "created_at",
        "updated_at",
    )


@admin.register(AutonomyOverride)
class AutonomyOverrideAdmin(admin.ModelAdmin):
    """Read-only list view for the autonomy dial overrides (P3-05a)."""

    list_display = ("process_id", "step_id", "org_unit", "autonomy", "set_by", "updated_at")
    list_filter = ("autonomy",)
    search_fields = ("process_id", "step_id", "org_unit", "set_by")
    readonly_fields = (
        "id",
        "process_id",
        "step_id",
        "org_unit",
        "autonomy",
        "set_by",
        "created_at",
        "updated_at",
    )


@admin.register(ProcessDefinition)
class ProcessDefinitionAdmin(admin.ModelAdmin):
    """Read-only list view for governed process definitions (P3-03)."""

    list_display = ("process_id", "version", "owner", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("process_id", "owner")
    readonly_fields = (
        "id",
        "process_id",
        "version",
        "owner",
        "status",
        "definition",
        "created_at",
        "updated_at",
    )


@admin.register(HumanTask)
class HumanTaskAdmin(admin.ModelAdmin):
    """Read-only list view for the durable human task inbox (P3-09)."""

    list_display = (
        "id",
        "capability",
        "required_authority",
        "status",
        "expires_at",
        "created_at",
    )
    list_filter = ("status", "required_authority", "capability")
    search_fields = ("id", "capability", "consequence", "grant_id")
    readonly_fields = (
        "id",
        "run_id",
        "step_id",
        "process_instance",
        "capability",
        "process_version",
        "capability_version",
        "canonical_args",
        "object_id",
        "object_type",
        "effect_limits",
        "consequence",
        "objects_revisions_json",
        "before_json",
        "after_json",
        "evidence_json",
        "evidence_digest",
        "reversibility",
        "required_authority",
        "expires_at",
        "alternatives_json",
        "status",
        "grant_id",
        "decided_by",
        "decided_at",
        "decline_reason",
        "created_at",
        "updated_at",
    )