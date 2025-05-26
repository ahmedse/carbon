# File: core/admin.py

from django.contrib import admin
from .models import Project, Cycle, Module

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'tenant')
    search_fields = ('name',)
    list_filter = ('tenant',)

@admin.register(Cycle)
class CycleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'project')
    search_fields = ('name',)
    list_filter = ('project',)

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'project')
    search_fields = ('name',)
    list_filter = ('project',)