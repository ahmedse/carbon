"""
Virtual schema management for multi-tenant, modular, RBAC-controlled data tables.
"""
import re
from django.db import models
from django.contrib.auth import get_user_model
from core.models import Module

User = get_user_model()

def normalize_name(value):
    """
    Normalize a string: lowercase, replace spaces/non-alphanumeric with underscores.
    """
    if not value:
        return ""
    value = value.strip().lower()
    value = re.sub(r"\s+", "_", value)           # spaces to underscores
    value = re.sub(r"[^a-z0-9_]", "_", value)    # non-alphanum to underscores
    value = re.sub(r"_+", "_", value)            # collapse multiple underscores
    value = value.strip("_")
    return value

class DataTable(models.Model):
    title = models.CharField(max_length=255)
    name = models.SlugField(max_length=64)
    description = models.TextField(blank=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='data_tables')
    version = models.PositiveIntegerField(default=1)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_data_tables')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_data_tables')

    def save(self, *args, **kwargs):
        # Standardize the table name
        self.name = normalize_name(self.name or self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.module})"

    class Meta:
        unique_together = ("module", "name")

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
    default_value = models.JSONField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    required = models.BooleanField(default=False)
    options = models.JSONField(blank=True, null=True)
    validation = models.JSONField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    reference_table = models.ForeignKey(DataTable, null=True, blank=True, on_delete=models.SET_NULL, related_name='referenced_by_fields')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_fields')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_fields')

    def save(self, *args, **kwargs):
        # Standardize the field name
        self.name = normalize_name(self.name or self.label)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['order', 'id']
        unique_together = (("data_table", "name"),)


    def __str__(self):
        return f"{self.label} ({self.type}) in {self.data_table.title}"

class DataRow(models.Model):
    data_table = models.ForeignKey(DataTable, on_delete=models.CASCADE, related_name='rows')
    values = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_rows')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_rows')
    is_archived = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)

    def save(self, *args, **kwargs):
        if self.values and isinstance(self.values, dict):
            self.values = {k.lower(): v for k, v in self.values.items()}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Row {self.id} in {self.data_table.title}"

class SchemaChangeLog(models.Model):
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
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        target = self.data_field or self.data_table
        return f"{self.action} on {target} by {self.user} at {self.timestamp}"