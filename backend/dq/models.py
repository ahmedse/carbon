# dq/models.py — Data Trust Core: Data Quality & Profiling.
# domain-agnostic. MUST NOT import from emissions.
from django.db import models
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.contrib.auth import get_user_model
from dataschema.models import DataTable, DataField

User = get_user_model()

# Phase 24 (Phase A): the rule vocabulary is externalized to dq/catalog.py
# (data, not code). Re-exported here for backward compatibility — existing
# call sites do `from dq.models import RULE_TYPES`, `DIMENSIONS`, etc.
from .catalog import (  # noqa: E402
    RULE_TYPE_CHOICES as RULE_TYPES,
    RULE_LEVEL_CHOICES as RULE_LEVELS,
    DIMENSIONS,
    SEVERITY_CHOICES,
)

# Phase 3 — Jobs: everything beyond the write-time gate is an explicit,
# user-started job with a followable lifecycle (see TASK-DQ-CORE-P3-JOBS).
JOB_TYPES = [
    ('rule_run', 'Rule Run'),
    ('profile', 'Profile'),
    ('freshness', 'Freshness'),
    ('schema', 'Schema'),
    ('nl_check', 'NL Check'),
    ('suggest', 'Suggest'),
    ('anomaly', 'Anomaly'),  # Phase 4 — Pulse anomaly.detect job
]
JOB_STATUSES = [
    ('queued', 'Queued'),
    ('running', 'Running'),
    ('done', 'Done'),
    ('failed', 'Failed'),
    ('canceled', 'Canceled'),
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


class ModelRuleAssignment(models.Model):
    """Typed-model twin of ``RuleFieldAssignment`` (ADR 0025).

    Binds a ``DQRule`` to a concrete field on a Django model, referenced by a
    ``model_label`` string (e.g. ``people.Employee``) rather than a
    ContentType/GenericForeignKey — this repo avoids generic FKs. The model is
    resolved lazily via ``apps.get_model()`` in ``clean()`` so ``dq`` never
    imports a hosted app (RULE_3).

    ``field_name`` is blank for model/row-level rules.
    """
    rule = models.ForeignKey(DQRule, on_delete=models.CASCADE, related_name='model_assignments')
    model_label = models.CharField(
        max_length=255, help_text="Django app+model label, e.g. 'people.Employee'"
    )
    field_name = models.CharField(
        max_length=255, blank=True,
        help_text='Concrete field on the model; blank = model/row-level rule'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('rule', 'model_label', 'field_name')
        ordering = ['model_label', 'field_name']

    def clean(self):
        from django.apps import apps

        parts = self.model_label.split('.')
        if len(parts) != 2:
            raise ValidationError({
                'model_label': (
                    f"Invalid model_label {self.model_label!r} — "
                    "expected 'app_label.ModelName'."
                ),
            })

        try:
            model = apps.get_model(*parts)
        except LookupError:
            model = None

        if model is None:
            raise ValidationError({
                'model_label': f"Unknown model {self.model_label!r}.",
            })

        if self.field_name:
            try:
                field = model._meta.get_field(self.field_name)
            except FieldDoesNotExist:
                raise ValidationError({
                    'field_name': (
                        f"Unknown field {self.field_name!r} on {self.model_label}."
                    ),
                })
            # `ManyToManyField.concrete` is True in Django, so the M2M flag is
            # the reliable rejector here; a scalar column is required for
            # engine.evaluate to project a single value per row.
            if field.many_to_many or not field.concrete:
                raise ValidationError({
                    'field_name': (
                        f"Field {self.field_name!r} is not a concrete scalar "
                        f"field on {self.model_label}."
                    ),
                })

    def __str__(self):
        return f"{self.rule.name} → {self.model_label}.{self.field_name or '*'}"


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
    """Results of executing a DQ rule against a specific field/table.

    Phase 4 (fail-visible, design decision #1): `passed` is nullable and
    `status` distinguishes a real failure from a rule that could not be
    evaluated because Pulse was unavailable (`skipped_unavailable`). Skipped
    results are excluded from score denominators so scores honestly show the
    gap instead of silently auto-passing.
    """
    RESULT_STATUSES = [
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('skipped_unavailable', 'Skipped — Pulse Unavailable'),
    ]

    rule = models.ForeignKey(DQRule, on_delete=models.CASCADE, related_name='results')
    data_field = models.ForeignKey(
        DataField, null=True, blank=True, on_delete=models.SET_NULL, related_name='dq_results'
    )
    run_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=RESULT_STATUSES, default='passed',
        help_text='passed|failed|skipped_unavailable (fail-visible, Phase 4)',
    )
    passed = models.BooleanField(
        null=True, blank=True, default=None,
        help_text='True/False verdict; null when the rule could not be evaluated '
                  '(status=skipped_unavailable — Pulse down, Phase 4 fail-visible)',
    )
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


# ── Phase 3: DQ Jobs ───────────────────────────────────────────────────────

class DQJob(models.Model):
    """An explicit, user-started DQ job with a followable lifecycle.

    Deterministic jobs (rule_run, profile, freshness, schema) execute inline
    during POST /dq/jobs/ (no Celery/Redis/daemon — design decision #1).
    Pulse jobs (nl_check, suggest) are submitted to Pulse; `refresh()` polls
    the task from GET /dq/jobs/{id}/ until a terminal state.

    Every completed job still writes normal DQResult rows, so history, trends
    and catalog rollups keep working unchanged.
    """
    job_type = models.CharField(max_length=20, choices=JOB_TYPES)
    status = models.CharField(max_length=10, choices=JOB_STATUSES, default='queued')
    rule = models.ForeignKey(
        DQRule, null=True, blank=True, on_delete=models.SET_NULL, related_name='jobs'
    )
    data_table = models.ForeignKey(
        DataTable, null=True, blank=True, on_delete=models.SET_NULL, related_name='dq_jobs'
    )
    payload = models.JSONField(default=dict, blank=True,
        help_text='Job inputs (e.g. prompt, unavailable_streak for Pulse jobs)')
    result = models.JSONField(default=dict, blank=True,
        help_text='Job summary (counts for rule runs, profile summary, Pulse result)')
    pulse_task_id = models.CharField(max_length=64, blank=True, default='',
        help_text='Pulse task id for nl_check/suggest jobs (polled via GET /tasks/{id})')
    progress = models.PositiveSmallIntegerField(default=0, help_text='0–100')
    error = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='dq_jobs'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'job_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'{self.job_type} #{self.pk} — {self.status}'


# ── Phase 4: Pulse plugins — suggestions & anomaly detection ──────────────
# (TASK-DQ-CORE-P4-PULSE — suggestions are data: pending → accepted/rejected;
# anomalies are stored facts from the anomaly.detect task; both are Carbon-side
# only — no Pulse-side code ships in this repo.)

class DQSuggestion(models.Model):
    """An AI-suggested DQ rule (from a completed dq.suggest Pulse task).

    Suggestions are DATA, not actions: they land as `pending` rows, are
    reviewed by humans, and only become real DQRules when explicitly accepted.
    Nothing auto-creates rules.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    data_table = models.ForeignKey(
        DataTable, on_delete=models.CASCADE, related_name='dq_suggestions'
    )
    payload = models.JSONField(
        help_text='Complete v1 rule definition (rule_schema) — becomes the DQRule on accept'
    )
    rationale = models.TextField(blank=True, default='',
        help_text='Why Pulse suggested this rule (Pulse-written explanation)')
    confidence = models.FloatField(null=True, blank=True,
        help_text='Pulse confidence in the suggestion (0–1)')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    reject_reason = models.TextField(blank=True, default='')
    job = models.ForeignKey(
        DQJob, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='suggestions', help_text='dq.suggest job that produced this suggestion'
    )
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='created_dq_suggestions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['data_table', '-created_at']),
        ]

    def __str__(self):
        name = ''
        if isinstance(self.payload, dict):
            name = self.payload.get('name', '')
        return f'{name or self.data_table.name} suggestion #{self.pk} — {self.status}'


class DQAnomaly(models.Model):
    """A detected anomaly from the anomaly.detect Pulse task (Phase 4).

    Pulse is statistical-first (z-score/IQR/seasonal baseline) and returns
    expected/observed/score/explanation; LLMs only write `explanation`.
    """
    data_table = models.ForeignKey(
        DataTable, on_delete=models.CASCADE, related_name='dq_anomalies'
    )
    metric = models.CharField(max_length=255,
        help_text='e.g. row_count, null_pct:<field>, sum(kwh)')
    group_key = models.JSONField(null=True, blank=True,
        help_text='e.g. {"building": "alamein"} — when the anomaly is scoped to a group')
    expected_range = models.JSONField(default=dict, blank=True,
        help_text='{"low": ..., "high": ...} expected baseline from Pulse')
    observed = models.FloatField(help_text='Observed value that triggered the anomaly')
    score = models.FloatField(default=0.0,
        help_text='Deviation magnitude (e.g. z-score / std-devs from baseline)')
    explanation = models.TextField(blank=True, default='',
        help_text='Pulse-written human explanation (LLM writes this only)')
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='warn')
    job = models.ForeignKey(
        DQJob, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='anomalies', help_text='anomaly job that produced this anomaly'
    )
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['data_table', '-detected_at']),
            models.Index(fields=['severity', '-detected_at']),
        ]

    def __str__(self):
        return f'{self.data_table.name}: {self.metric} {self.observed} @ {self.detected_at:%Y-%m-%d %H:%M}'
