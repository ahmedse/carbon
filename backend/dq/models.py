# dq/models.py — Data Trust Core: Data Quality & Profiling.
# domain-agnostic. MUST NOT import from emissions.
from django.db import models
from django.contrib.auth import get_user_model
from dataschema.models import DataTable, DataField

User = get_user_model()

RULE_TYPES = [
    ('not_null', 'Not Null'), ('unique', 'Unique'),
    ('allowed_values', 'Allowed Values'), ('range', 'Range'), ('regex', 'Regex'),
    ('reference_integrity', 'Reference Integrity'), ('threshold', 'Threshold'),
    ('nl_check', 'NL Check'),
]
SEVERITY_CHOICES = [('info', 'Info'), ('warn', 'Warn'), ('error', 'Error')]
SCOPE_CHOICES = [('table', 'Table'), ('field', 'Field')]


class TableProfile(models.Model):
    data_table = models.ForeignKey(DataTable, on_delete=models.CASCADE, related_name='dq_table_profiles')
    row_count = models.PositiveIntegerField(default=0)
    completeness_pct = models.FloatField(default=0)
    # Per-column summary stats (JSON — keys are field names)
    null_counts = models.JSONField(default=dict, blank=True,
        help_text='{field_name: null_count} per column')
    distinct_counts = models.JSONField(default=dict, blank=True,
        help_text='{field_name: distinct_count} per column')
    min_values = models.JSONField(default=dict, blank=True,
        help_text='{field_name: min_value} per column')
    max_values = models.JSONField(default=dict, blank=True,
        help_text='{field_name: max_value} per column')
    mean_values = models.JSONField(default=dict, blank=True,
        help_text='{field_name: mean_value} per column (numeric only)')
    profiled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-profiled_at']
        indexes = [
            models.Index(fields=['data_table', '-profiled_at']),
        ]


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


class DQProfileConfig(models.Model):
    """Phase 1.7: Singleton — configuration for automated profiling & freshness monitoring."""
    auto_profile_enabled = models.BooleanField(default=False,
        help_text='When enabled, new/modified tables are profiled automatically')
    freshness_threshold_hours = models.PositiveIntegerField(default=24,
        help_text='Tables not profiled within this window are considered stale')
    volume_anomaly_pct = models.PositiveSmallIntegerField(default=25,
        help_text='Row count change % that triggers a volume anomaly alert')
    sample_size = models.PositiveIntegerField(default=1000,
        help_text='Max rows sampled for top_values/distribution analysis')

    class Meta:
        verbose_name = 'DQ Profile Config'

    def __str__(self):
        return 'DQ Profile Config'


# ── Phase 1.8: Freshness & Schema Monitoring ──────────────────────────────

class FreshnessCheck(models.Model):
    """Per-table freshness tracking — is data within the expected age window?"""
    data_table = models.ForeignKey(DataTable, on_delete=models.CASCADE, related_name='freshness_checks')
    expected_max_age_hours = models.PositiveIntegerField(default=24,
        help_text='Maximum age of data before it is considered stale')
    last_data_timestamp = models.DateTimeField(null=True, blank=True,
        help_text='Timestamp of the newest row in this table')
    is_fresh = models.BooleanField(default=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-checked_at']
        indexes = [
            models.Index(fields=['data_table', '-checked_at']),
            models.Index(fields=['is_fresh', '-checked_at']),
        ]

    def __str__(self):
        status = 'fresh' if self.is_fresh else 'stale'
        return f'{self.data_table.name} — {status} @ {self.checked_at:%Y-%m-%d %H:%M}'


class SchemaSnapshot(models.Model):
    """Snapshot of a table's column schema at a point in time."""
    data_table = models.ForeignKey(DataTable, on_delete=models.CASCADE, related_name='schema_snapshots')
    column_schema = models.JSONField(
        help_text='{field_name: {type, is_nullable, position}} per column'
    )
    row_count = models.PositiveIntegerField(default=0)
    snapshot_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-snapshot_at']
        indexes = [
            models.Index(fields=['data_table', '-snapshot_at']),
        ]

    def __str__(self):
        cols = len(self.column_schema) if isinstance(self.column_schema, dict) else 0
        return f'{self.data_table.name} — {cols} columns @ {self.snapshot_at:%Y-%m-%d %H:%M}'


class SchemaChange(models.Model):
    """Detected change between two schema snapshots."""
    CHANGE_TYPES = [
        ('added', 'Column Added'),
        ('dropped', 'Column Dropped'),
        ('modified', 'Column Modified'),
    ]

    data_table = models.ForeignKey(DataTable, on_delete=models.CASCADE, related_name='schema_changes')
    snapshot_from = models.ForeignKey(
        SchemaSnapshot, on_delete=models.SET_NULL, null=True, blank=True, related_name='changes_from'
    )
    snapshot_to = models.ForeignKey(
        SchemaSnapshot, on_delete=models.SET_NULL, null=True, blank=True, related_name='changes_to'
    )
    change_type = models.CharField(max_length=10, choices=CHANGE_TYPES)
    field_name = models.CharField(max_length=255)
    old_definition = models.JSONField(null=True, blank=True,
        help_text='Old column definition (or None if added)')
    new_definition = models.JSONField(null=True, blank=True,
        help_text='New column definition (or None if dropped)')
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['data_table', '-detected_at']),
            models.Index(fields=['change_type', '-detected_at']),
        ]

    def __str__(self):
        return f'{self.data_table.name}: {self.get_change_type_display()} {self.field_name} @ {self.detected_at:%Y-%m-%d %H:%M}'
