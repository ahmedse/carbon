# mdm/admin.py
from django.contrib import admin
from .models import ReferenceSet, ReferenceValue, OrgUnit

admin.site.register(ReferenceSet)
admin.site.register(ReferenceValue)

@admin.register(OrgUnit)
class OrgUnitAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'code', 'org_type', 'parent', 'is_active']
    list_filter = ['org_type', 'is_active']
    search_fields = ['name', 'code']
