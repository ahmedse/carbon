from django.contrib import admin

from gradevance.models import (
    AnalysisRun,
    Assignment,
    AssignmentProfileRecord,
    Course,
    ExpertEdit,
    Proposal,
    ReviewItem,
    Submission,
)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "discipline", "created_at")
    search_fields = ("code", "name")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "mode", "status", "profile_pack_id", "profile_version", "created_at")
    list_filter = ("mode", "status")
    search_fields = ("title", "profile_pack_id")


@admin.register(AssignmentProfileRecord)
class AssignmentProfileRecordAdmin(admin.ModelAdmin):
    list_display = ("pack_id", "version", "name", "discipline", "genre", "status")
    list_filter = ("discipline", "status")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "assignment", "word_count", "status", "created_at")
    list_filter = ("status",)


@admin.register(AnalysisRun)
class AnalysisRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "profile_pack_id",
        "status",
        "gate_decision",
        "mean_confidence",
        "released",
        "created_at",
    )
    list_filter = ("status", "gate_decision", "released")


@admin.register(ReviewItem)
class ReviewItemAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "status", "priority", "reason", "created_at")
    list_filter = ("status",)


@admin.register(ExpertEdit)
class ExpertEditAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "edit_kind", "editor", "created_at")
    list_filter = ("edit_kind",)
    readonly_fields = ("before", "after", "created_at")


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "status", "created_at")
    list_filter = ("kind", "status")
