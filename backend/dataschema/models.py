# File: dataschema/models.py

from django.db import models
from django.contrib.auth import get_user_model
from core.models import Module
import re

User = get_user_model()

def normalize_name(value):
    """Normalize a string to snake_case, lowercase, no leading/trailing spaces."""
    if not value:
        return ""
    value = value.strip().lower()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^a-z0-9_]", "", value)  # Remove non-alphanum/underscores
    return value

class DataTable(models.Model):
    """
    Represents a dynamic table ("sheet"/"form") within a module.
    """
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='data_tables')
    version = models.PositiveIntegerField(default=1)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_data_tables')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_data_tables')

    def __str__(self):
        return f"{self.title} (Module: {self.module})"

class DataField(models.Model):
    FIELD_TYPES = [
        ('string', 'String'),
        ('text', 'Text (Multiline)'),
        ('number', 'Number'),
        ('date', 'Date'),
        ('boolean', 'Boolean'),
        ('select', 'Single Select'),
        ('multiselect', 'Multi Select'),
        ('file', 'File'),
        ('reference', 'Reference (Future)'),
    ]

    data_table = models.ForeignKey(DataTable, on_delete=models.CASCADE, related_name='fields')
    name = models.CharField(max_length=50)
    label = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=FIELD_TYPES)
    default_value = models.JSONField(blank=True, null=True, help_text="Default value for the field")
    order = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    required = models.BooleanField(default=False)
    options = models.JSONField(blank=True, null=True, help_text="For select/multiselect: list of option dicts")
    validation = models.JSONField(blank=True, null=True, help_text="Flexible JSON validation rules")
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    reference_table = models.ForeignKey(DataTable, null=True, blank=True, on_delete=models.SET_NULL, related_name='referenced_by_fields')  # For reference fields (future)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_fields')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_fields')
    
    class Meta:
        ordering = ['order', 'id']
        unique_together = (("data_table", "name"),)  # Ensure uniqueness within table

    def save(self, *args, **kwargs):
        if not self.name and self.label:
            self.name = normalize_name(self.label)
        else:
            self.name = normalize_name(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.label} ({self.type}) in {self.data_table.title}"

class DataRow(models.Model):
    """
    Represents a single row of data, storing values as JSON.
    """
    data_table = models.ForeignKey(DataTable, on_delete=models.CASCADE, related_name='rows')
    values = models.JSONField(help_text="Field values as {field_name: value}")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_rows')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_rows')
    is_archived = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)

    def save(self, *args, **kwargs):
        # --- THIS IS THE FIX: ---
        if self.values and isinstance(self.values, dict):
            self.values = {k.lower(): v for k, v in self.values.items()}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Row {self.id} in {self.data_table.title}"

class SchemaChangeLog(models.Model):
    """
    Logs all changes to tables/fields (schema), for audit/version/history.
    """
    ACTIONS = [
        ('add', 'Add'),
        ('edit', 'Edit'),
        ('delete', 'Delete'),
        ('archive', 'Archive'),
        ('restore', 'Restore'),
    ]
    data_table = models.ForeignKey(DataTable, on_delete=models.SET_NULL, null=True, blank=True, related_name='schema_logs')
    data_field = models.ForeignKey(DataField, on_delete=models.SET_NULL, null=True, blank=True, related_name='schema_logs')
    action = models.CharField(max_length=10, choices=ACTIONS)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text="Optional reason/comment")

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        target = self.data_field or self.data_table
        return f"{self.action} on {target} by {self.user} at {self.timestamp}"