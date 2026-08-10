# dq/models.py — Data Trust Core: Data Quality & Profiling.
# domain-agnostic. MUST NOT import from emissions.
from django.db import models
from django.core.exceptions import ValidationError
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
RULE_LEVELS = [
    ('field_validation', 'Field Validation'),
    ('business_rule', 'Business Rule'),
]

DIMENSIONS = [
    ('completeness', 'Completeness'),
    ('validity', 'Validity'),
    ('accuracy', 'Accuracy'),
    ('consistency', 'Consistency'),
    ('timeliness', 'Timeliness'),
    ('uniqueness', 'Uniqueness'),
    ('integrity', 'Integrity'),
    ('reasonability', 'Reasonability'),
]


class RuleTag(models.Model):
    """Categorization tags for DQ rules (e.g. 'PII', 'financial', 'regulatory')."""
    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=7, default='#6366f1',
        help_text='Hex color for UI badge (e.g. #6366f1)')
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class DQRule(models.Model):
    """Standalone data quality rule. Assigned to fields via RuleFieldAssignment.

    Two levels:
      - field_validation: enforced at write time by the gate (Phase 2)
      - business_rule:    runs as jobs (Phase 3)

    definition is the source of truth (v1 JSON). name, rule_level, rule_type,
    severity, is_active, and dimension are denormalized from definition on save.
    """
    name = models.CharField(max_length=255)
    rule_level = models.CharField(max_length=20, choices=RULE_LEVELS, default='field_validation')
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES)
    params = models.JSONField(default=dict, blank=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='error')
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, help_text='What this rule checks and why')
    tags = models.ManyToManyField(RuleTag, blank=True, related_name='rules')
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_dq_rules'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # v2 fields — definition is the source of truth
    dimension = models.CharField(
        max_length=20, choices=DIMENSIONS, default='validity',
        help_text='DAMA DMBOK2 data quality dimension',
    )
    definition = models.JSONField(
        default=dict, blank=True,
        help_text='Full v1 rule definition JSON (source of truth)',
    )
    version = models.IntegerField(default=1, help_text='Monotonic rule version')
    archived = models.BooleanField(default=False, help_text='Soft-delete when results exist')

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        """Validate definition and sync denormalized columns before saving."""
        if self.definition:
            from .rule_schema import validate_definition
            errors = validate_definition(self.definition)
            if errors:
                raise ValidationError({'definition': errors})
            # Sync denormalized columns from definition
            d = self.definition
            self.name = d.get('name', self.name)
            self.rule_level = 'field' if d.get('level') == 'field' else \
                              'field_validation' if d.get('level') == 'field_validation' else \
                              'business_rule' if d.get('level') == 'business' else \
                              self.rule_level
            # Normalize level value — map 'field' → 'field_validation', 'business' → 'business_rule'
            level = d.get('level')
            if level == 'field':
                self.rule_level = 'field_validation'
            elif level == 'business':
                self.rule_level = 'business_rule'
            elif level in ('field_validation', 'business_rule'):
                self.rule_level = level
            self.rule_type = d.get('type', self.rule_type)
            self.severity = d.get('severity', self.severity)
            self.is_active = d.get('active', self.is_active)
            self.dimension = d.get('dimension', self.dimension)
            if d.get('description') and not self.description:
                self.description = d['description']
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name or f'{self.rule_type} ({self.get_rule_level_display()})'


class RuleFieldAssignment(models.Model):
    """M2M through table: which fields a DQ rule applies to.

    data_field may be NULL for table-level business rules
    (e.g. 'row count must be > 100').
    data_table is always set (denormalized for fast lookup).
    """
    rule = models.ForeignKey(DQRule, on_delete=models.CASCADE, related_name='field_assignments')
    data_field = models.ForeignKey(
        DataField, null=True, blank=True, on_delete=models.CASCADE, related_name='rule_assignments'
    )
    data_table = models.ForeignKey(
        DataTable, on_delete=models.CASCADE, related_name='rule_assignments'
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['rule', 'data_field'],
                condition=models.Q(data_field__isnull=False),
                name='unique_rule_field'
            ),
            models.UniqueConstraint(
                fields=['rule', 'data_table'],
                condition=models.Q(data_field__isnull=True),
                name='unique_rule_table'
            ),
        ]
        ordering = ['data_table__name', 'data_field__name']

    def __str__(self):
        target = self.data_field.name if self.data_field else f'Table:{self.data_table.name}'
        return f'{self.rule.name} → {target}'


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


class DQResult(models.Model):
    """Results of executing a DQ rule against a specific field/table."""
    rule = models.ForeignKey(DQRule, on_delete=models.CASCADE, related_name='results')
    data_field = models.ForeignKey(
        DataField, null=True, blank=True, on_delete=models.SET_NULL, related_name='dq_results'
    )
    run_at = models.DateTimeField(auto_now_add=True)
    passed = models.BooleanField(default=True)
    checked_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    sample_failures = models.JSONField(default=list, blank=True)
    score = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ['-run_at']
        indexes = [
            models.Index(fields=['rule', '-run_at']),
            models.Index(fields=['data_field', '-run_at']),
        ]


class DQProfileConfig(models.Model):
    """Phase 1.7: Singleton — configuration for automated profiling & freshness monitoring."""
    freshness_threshold_hours = models.PositiveIntegerField(default=24,
        help_text='Tables not profiled within this window are considered stale')
    volume_anomaly_pct = models.PositiveSmallIntegerField(default=25,
        help_text='Row count change % that triggers a volume anomaly alert (wired in DQ Phase 4)')

    class Meta:
        verbose_name = 'DQ Profile Config'

    def __str__(self):
        return 'DQ Profile Config'


# ── Phase 1.8: Freshness & Schema Monitoring ──────────────────────────────

class FreshnessCheck(models.Model):
    """Per-table freshness tracking — is data within the expected age window?"""
    data_table = models.ForeignKey(DataTable, on_delete=models.CASCADE, related_name='freshness_checks')
    expected_max_age_hours = models.PositiveIntegerField(default=24,
        help_text='Snapshot of the global threshold at check time; per-table thresholds not yet supported')
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
