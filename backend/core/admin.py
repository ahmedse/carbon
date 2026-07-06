# File: core/admin.py
# Django admin registration for core app models.

from django.contrib import admin
from .models import Module, Feedback


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'scope', 'org_unit']
    search_fields = ['name']


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'email', 'rating', 'submitted_at']
    search_fields = ['name', 'email', 'message']
    list_filter = ['rating', 'submitted_at']