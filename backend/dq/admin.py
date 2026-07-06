# dq/admin.py
from django.contrib import admin
from .models import TableProfile, FieldProfile, DQRule, DQResult

admin.site.register(TableProfile)
admin.site.register(FieldProfile)
admin.site.register(DQRule)
admin.site.register(DQResult)
