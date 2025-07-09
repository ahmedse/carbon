# File: core/admin.py
# Django admin registration for core app models.

from django.contrib import admin
from .models import Project, Module

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'tenant']
    search_fields = ['name']

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'project']
    search_fields = ['name']