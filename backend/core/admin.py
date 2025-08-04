# File: core/admin.py
# Django admin registration for core app models.

from django.contrib import admin
from .models import Project, Module
from .models import Feedback

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'tenant']
    search_fields = ['name']

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'project', 'scope']
    search_fields = ['name']

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'email', 'rating', 'submitted_at']
    search_fields = ['name', 'email', 'message']
    list_filter = ['rating', 'submitted_at']