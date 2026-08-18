from django.contrib import admin

from .models import AppActivation, AppManifest


@admin.register(AppManifest)
class AppManifestAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'version', 'is_system', 'is_active', 'updated_at')
    list_filter = ('is_system', 'is_active')
    search_fields = ('name', 'slug', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(AppActivation)
class AppActivationAdmin(admin.ModelAdmin):
    list_display = ('app', 'is_active', 'activated_at', 'deactivated_at')
    list_filter = ('is_active',)
    search_fields = ('app__name', 'app__slug')
