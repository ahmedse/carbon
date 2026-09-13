from django.contrib import admin
from .models import RegulationScheme, Obligation, AuditProgram, AuditRun, AuditFinding, RemediationPlan


@admin.register(RegulationScheme)
class RegulationSchemeAdmin(admin.ModelAdmin):
    list_display = ['name', 'authority', 'version', 'effective_from', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'authority']


@admin.register(Obligation)
class ObligationAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'scheme', 'scope_type', 'formula_type', 'severity', 'is_active']
    list_filter = ['scheme', 'scope_type', 'severity', 'is_active']
    search_fields = ['code', 'name']


@admin.register(AuditProgram)
class AuditProgramAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    filter_horizontal = ['obligations']


class AuditFindingInline(admin.TabularInline):
    model = AuditFinding
    extra = 0
    readonly_fields = ['obligation', 'scope_type', 'scope_id', 'scope_label', 'result', 'severity', 'computed_value']
    can_delete = False


@admin.register(AuditRun)
class AuditRunAdmin(admin.ModelAdmin):
    list_display = ['program', 'run_date', 'status', 'run_by', 'run_at', 'completed_at']
    list_filter = ['status', 'program']
    readonly_fields = ['run_at', 'completed_at', 'summary']
    inlines = [AuditFindingInline]


@admin.register(AuditFinding)
class AuditFindingAdmin(admin.ModelAdmin):
    list_display = ['obligation', 'scope_label', 'result', 'severity', 'run']
    list_filter = ['result', 'severity', 'obligation__scheme']
    search_fields = ['scope_label', 'obligation__code']


@admin.register(RemediationPlan)
class RemediationPlanAdmin(admin.ModelAdmin):
    list_display = ['finding', 'status', 'owner', 'due_date', 'updated_at']
    list_filter = ['status']
