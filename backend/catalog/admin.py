# catalog/admin.py
from django.contrib import admin
from .models import DataDomain, GlossaryTerm, Tag, AssetProfile, GovernanceEvent

admin.site.register(DataDomain)
admin.site.register(GlossaryTerm)
admin.site.register(Tag)
admin.site.register(AssetProfile)
admin.site.register(GovernanceEvent)
