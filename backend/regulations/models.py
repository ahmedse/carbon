# regulations/models.py
# Regulations Audit Engine — domain-agnostic compliance tracking.
# Three tiers: RegulationScheme → Obligation → [AuditProgram → AuditRun → AuditFinding]
# Temporal: every finding is stamped with run.run_date (point-in-time).
# Multi-domain: domain apps (people, finance, …) plug in via the evaluator registry.
# MUST NOT import from domain apps — dependency direction is always inward.
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

SEVERITY = [
    ('critical', 'Critical'),
    ('major', 'Major'),
    ('minor', 'Minor'),
    ('info', 'Info'),
]

SCOPE_TYPES = [
    ('company',      'Company'),
    ('org_unit',     'Org Unit'),
    ('koc_contract', 'KOC Contract'),
    ('employee',     'Employee'),
    ('position',     'Position'),
    ('custom',       'Custom'),
]

RUN_STATUSES = [
    ('pending',  'Pending'),
    ('running',  'Running'),
    ('complete', 'Complete'),
    ('error',    'Error'),
]

FINDING_RESULTS = [
    ('compliant',     'Compliant'),
    ('non_compliant', 'Non-Compliant'),
    ('partial',       'Partial'),
    ('na',            'Not Applicable'),
    ('error',         'Evaluator Error'),
]

REMEDIATION_STATUSES = [
    ('open',          'Open'),
    ('in_progress',   'In Progress'),
    ('resolved',      'Resolved'),
    ('accepted_risk', 'Accepted Risk'),
]


class RegulationScheme(models.Model):
    """A regulatory or policy framework (e.g. KOC Kuwaitization, Kuwait Labour Law, IFRS 16)."""
    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=200)
    authority = models.CharField(
        max_length=200, blank=True,
        help_text='Issuing authority (e.g. KOC, Ministry of Labour, IASB)',
    )
    version = models.CharField(max_length=40, blank=True, help_text='Revision / year')
    effective_from = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.authority})"


class Obligation(models.Model):
    """One specific requirement within a RegulationScheme.

    formula_type maps to a registered evaluator in regulations.registry.
    formula_params is the evaluator-specific configuration (JSON).
    scope_type declares the granularity of evaluation (one finding per scope instance).
    """
    scheme = models.ForeignKey(RegulationScheme, on_delete=models.PROTECT, related_name='obligations')
    code = models.CharField(max_length=80, help_text='Short code unique within the scheme')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    scope_type = models.CharField(max_length=20, choices=SCOPE_TYPES, default='company')
    formula_type = models.CharField(
        max_length=80,
        help_text='Key into evaluator registry (registered by domain apps)',
    )
    formula_params = models.JSONField(
        default=dict, blank=True,
        help_text='Evaluator-specific parameters (e.g. quota thresholds, reference codes)',
    )
    severity = models.CharField(max_length=10, choices=SEVERITY, default='major')
    citation = models.CharField(max_length=500, blank=True, help_text='Source article / section')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('scheme', 'code')
        ordering = ['scheme', 'code']

    def __str__(self):
        return f"{self.scheme.slug}/{self.code}"


class AuditProgram(models.Model):
    """A named collection of Obligations to evaluate together.

    One program can span multiple schemes. Programs are the unit of scheduling.
    """
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    obligations = models.ManyToManyField(Obligation, blank=True, related_name='programs')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class AuditRun(models.Model):
    """One execution of an AuditProgram. Produces AuditFindings.

    run_date is the point-in-time being assessed (can be backdated).
    run_at is when the evaluation was actually executed.
    """
    program = models.ForeignKey(AuditProgram, on_delete=models.PROTECT, related_name='runs')
    run_date = models.DateField(help_text='Assessment date (the "as of" date for findings)')
    run_at = models.DateTimeField(auto_now_add=True)
    run_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='audit_runs',
        help_text='Null = automated/scheduled run',
    )
    status = models.CharField(max_length=10, choices=RUN_STATUSES, default='pending', db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    summary = models.JSONField(
        default=dict, blank=True,
        help_text='Aggregate stats: {total, compliant, non_compliant, partial, error}',
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-run_date', '-run_at']

    def __str__(self):
        return f"{self.program.name} @ {self.run_date} [{self.status}]"


class AuditFinding(models.Model):
    """Result of evaluating one Obligation against one scope instance in an AuditRun.

    scope_type + scope_id identify the evaluated entity.
    scope_label is denormalized for display without DB lookups.
    computed_value stores the raw evaluator output (actual, expected, delta, detail).
    """
    run = models.ForeignKey(AuditRun, on_delete=models.CASCADE, related_name='findings')
    obligation = models.ForeignKey(Obligation, on_delete=models.PROTECT, related_name='findings')
    scope_type = models.CharField(max_length=20, choices=SCOPE_TYPES)
    scope_id = models.PositiveIntegerField(help_text='PK of the evaluated entity')
    scope_label = models.CharField(max_length=255, blank=True, help_text='Denormalized display name')
    result = models.CharField(max_length=15, choices=FINDING_RESULTS, db_index=True)
    computed_value = models.JSONField(
        default=dict,
        help_text='Evaluator output: {actual, expected, delta, detail, …}',
    )
    severity = models.CharField(max_length=10, choices=SEVERITY)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['run', 'obligation', 'scope_type', 'scope_id']
        indexes = [
            models.Index(fields=['run', 'result']),
            models.Index(fields=['obligation', 'result']),
        ]

    def __str__(self):
        return f"{self.obligation.code} | {self.scope_label} → {self.result}"

    @property
    def is_deficient(self):
        return self.result in ('non_compliant', 'partial', 'error')


class RemediationPlan(models.Model):
    """Tracked remediation for a non-compliant AuditFinding.

    One plan per finding (OneToOne). Resolution is recorded in resolution_notes.
    """
    finding = models.OneToOneField(AuditFinding, on_delete=models.CASCADE, related_name='remediation')
    owner = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='remediation_plans',
    )
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=REMEDIATION_STATUSES, default='open', db_index=True)
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date', 'status']

    def __str__(self):
        return f"Remediation: {self.finding} [{self.status}]"
