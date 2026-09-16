# mdm/admin.py
from django.contrib import admin
from .models import ReferenceSet, ReferenceValue, OrgUnit

admin.site.register(ReferenceSet)
admin.site.register(ReferenceValue)

@admin.register(OrgUnit)
class OrgUnitAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'code', 'org_type', 'parent', 'manager_employee_id', 'is_active']
    list_filter = ['org_type', 'is_active']
    search_fields = ['name', 'code']

    def get_queryset(self, request):
        """ADR-0028: prefer deployment-root subtree in admin lists."""
        qs = super().get_queryset(request)
        from mdm.services import get_deployment_org_unit_ids
        try:
            deployment_ids = get_deployment_org_unit_ids(include_self=True)
        except RuntimeError:
            return qs.none()
        if deployment_ids:
            return qs.filter(id__in=deployment_ids)
        return qs
