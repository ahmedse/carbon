# connections/admin.py
from django import forms
from django.contrib import admin
from .models import DataSource, ConsumingConnection
from .services import MASK_VALUE


class MaskedConfigWidget(forms.Textarea):
    """Renders the stored config as '***' — never the real value."""

    def format_value(self, value):
        if value:
            return MASK_VALUE
        return ""


class MaskedConfigField(forms.JSONField):
    """JSON field that shows '***' for stored config and keeps the stored
    value unless the admin submits new JSON."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            'help_text',
            'Stored values are masked. Leave as-is (or blank) to keep the '
            'current config; paste new JSON to replace it entirely.',
        )
        super().__init__(*args, **kwargs)

    def clean(self, value):
        if value in (None, '', MASK_VALUE):
            return None  # sentinel -> keep stored config
        return super().clean(value)

    def has_changed(self, initial, data):
        if data in (None, '', MASK_VALUE):
            return False
        return super().has_changed(initial, data)


class DataSourceAdminForm(forms.ModelForm):
    connection_config = MaskedConfigField(widget=MaskedConfigWidget)

    class Meta:
        model = DataSource
        fields = '__all__'

    def save(self, commit=True):
        instance = super().save(commit=False)
        new_config = self.cleaned_data.get('connection_config')
        if new_config is None:
            # Field left masked/blank -> preserve the stored secret config
            new_config = instance.connection_config if instance.pk else {}
        instance.connection_config = new_config
        if commit:
            instance.save()
        return instance


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    form = DataSourceAdminForm
    list_display = ['name', 'source_type', 'status', 'owner', 'last_tested_at', 'updated_at']
    list_filter = ['source_type', 'status', 'created_at']
    search_fields = ['name', 'slug', 'description']
    readonly_fields = ['slug', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Info', {'fields': ('name', 'slug', 'source_type', 'description')}),
        ('Configuration', {'fields': ('connection_config', 'status')}),
        ('Metadata', {'fields': ('domain', 'owner')}),
        ('Testing', {'fields': ('last_tested_at', 'last_test_status')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(ConsumingConnection)
class ConsumingConnectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'system_type', 'is_active', 'owner', 'last_used_at', 'updated_at']
    list_filter = ['system_type', 'is_active', 'created_at']
    search_fields = ['name', 'slug', 'description']
    readonly_fields = ['slug', 'api_key_hash', 'api_key_salt', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Info', {'fields': ('name', 'slug', 'system_type', 'description')}),
        ('Configuration', {'fields': ('scopes', 'is_active')}),
        ('API Key', {'fields': ('api_key_hash', 'api_key_salt'), 'classes': ('collapse',)}),
        ('Metadata', {'fields': ('owner', 'last_used_at')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
