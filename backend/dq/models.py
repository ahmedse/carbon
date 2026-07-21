# dq/models.py — Data Trust Core: Data Quality & Profiling.
# domain-agnostic. MUST NOT import from emissions.
from django.db import models
from django.contrib.auth import get_user_model
from dataschema.models import DataTable, DataField

User = get_user_model()

RULE_TYPES = [
    ('not_null', 'Not Null'), ('unique', 'Unique'),
    ('allowed_values', 'Allowed Values'), ('range', 'Range'), ('regex', 'Regex'),
    ('reference_integrity', 'Reference Integrity'),
]
SEVERITY_CHOICES = [('info', 'Info'), ('warn', 'Warn'), ('error', 'Error')]
SCOPE_CHOICES = [('table', 'Table'), ('field', 'Field')]


class TableProfile(models.Model):
    data_table = models.ForeignKey(DataTable, on_delete=models.CASCADE, related_name='dq_table_profiles')
    row_count = models.PositiveIntegerField(default=0)
    completeness_pct = models.FloatField(default=0)
    profiled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-profiled_at']


class FieldProfile(models.Model):
    data_field = models.ForeignKey(DataField, on_delete=models.CASCADE, related_name='dq_field_profiles')
    row_count = models.PositiveIntegerField(default=0)
    null_count = models.PositiveIntegerField(default=0)
    distinct_count = models.PositiveIntegerField(default=0)
    completeness_pct = models.FloatField(default=0)
    uniqueness_pct = models.FloatField(default=0)
    min_value = models.CharField(max_length=255, blank=True)
    max_value = models.CharField(max_length=255, blank=True)
    mean_value = models.FloatField(null=True, blank=True)
    top_values = models.JSONField(default=list, blank=True)
    profiled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-profiled_at']


class DQRule(models.Model):
    """Data quality rule with scope (table or field level)."""
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default='field')
    name = models.CharField(max_length=255, default='')  # Rule name for display
    data_table = models.ForeignKey(
        DataTable, null=True, blank=True, on_delete=models.CASCADE, related_name='dq_rules'
    )
    data_field = models.ForeignKey(
        DataField, null=True, blank=True, on_delete=models.CASCADE, related_name='dq_rules'
    )
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES)
    params = models.JSONField(default=dict, blank=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='error')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_dq_rules'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name or f"{self.rule_type} on {self.data_field or self.data_table}"


class DQResult(models.Model):
    """Results of executing a DQ rule."""
    rule = models.ForeignKey(DQRule, on_delete=models.CASCADE, related_name='results')
    run_at = models.DateTimeField(auto_now_add=True)
    passed = models.BooleanField(default=True)
    checked_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    sample_failures = models.JSONField(default=list, blank=True)
    score = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ['-run_at']
