# catalog/models.py — Data Trust Core: Catalog & Governance.
# domain-agnostic. MUST NOT import from emissions.
from django.db import models
from django.contrib.auth import get_user_model
from dataschema.models import DataTable, DataField

User = get_user_model()

CLASSIFICATION_CHOICES = [
    ('public', 'Public'), ('internal', 'Internal'),
    ('confidential', 'Confidential'), ('pii', 'PII'), ('sensitive', 'Sensitive'),
]
QUALITY_STATUS_CHOICES = [
    ('unknown', 'Unknown'), ('passing', 'Passing'),
    ('warning', 'Warning'), ('failing', 'Failing'),
]
GLOSSARY_STATUS_CHOICES = [
    ('draft', 'Draft'), ('approved', 'Approved'), ('deprecated', 'Deprecated'),
]


class DataDomain(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='owned_domains')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class GlossaryTerm(models.Model):
    term = models.CharField(max_length=160, unique=True)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    definition = models.TextField(blank=True)
    domain = models.ForeignKey(DataDomain, null=True, blank=True, on_delete=models.SET_NULL, related_name='glossary_terms')
    synonyms = models.JSONField(default=list, blank=True)
    steward = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='stewarded_terms')
    status = models.CharField(max_length=20, choices=GLOSSARY_STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.term


class Tag(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    color = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.name


class AssetProfile(models.Model):
    """Catalog metadata for a single dataschema asset (a DataTable OR a DataField)."""
    data_table = models.ForeignKey(DataTable, null=True, blank=True, on_delete=models.CASCADE, related_name='catalog_profile')
    data_field = models.ForeignKey(DataField, null=True, blank=True, on_delete=models.CASCADE, related_name='catalog_profile')
    description = models.TextField(blank=True)
    domain = models.ForeignKey(DataDomain, null=True, blank=True, on_delete=models.SET_NULL, related_name='assets')
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='owned_assets')
    steward = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='stewarded_assets')
    classification = models.CharField(max_length=20, choices=CLASSIFICATION_CHOICES, default='internal')
    semantic_type = models.CharField(max_length=100, blank=True)
    glossary_term = models.ForeignKey(GlossaryTerm, null=True, blank=True, on_delete=models.SET_NULL, related_name='assets')
    tags = models.ManyToManyField(Tag, blank=True, related_name='assets')
    # quality_* are written by the future dq app; leave defaults this run.
    quality_status = models.CharField(max_length=20, choices=QUALITY_STATUS_CHOICES, default='unknown')
    quality_score = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='updated_assets')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['data_table'], condition=models.Q(data_table__isnull=False), name='uniq_assetprofile_table'),
            models.UniqueConstraint(fields=['data_field'], condition=models.Q(data_field__isnull=False), name='uniq_assetprofile_field'),
        ]

    def __str__(self):
        return f"AssetProfile({'field' if self.data_field_id else 'table'} #{self.data_field_id or self.data_table_id})"


class GovernanceEvent(models.Model):
    ACTIONS = [('create', 'Create'), ('update', 'Update'), ('delete', 'Delete')]
    asset = models.ForeignKey(AssetProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name='events')
    entity_type = models.CharField(max_length=40)
    entity_id = models.PositiveIntegerField(null=True, blank=True)
    action = models.CharField(max_length=10, choices=ACTIONS)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='governance_events')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} {self.entity_type}#{self.entity_id} @ {self.timestamp}"


class GovernancePolicy(models.Model):
    """
    Configurable governance policies for delete/update validation.
    Managed by admins, enforced by API. Scoped to domain/org/scope.
    """
    POLICY_TYPES = [
        ('module_delete', 'Module Delete Policy'),
        ('table_delete', 'Table Delete Policy'),
        ('module_update', 'Module Update Policy'),
        ('table_update', 'Table Update Policy'),
    ]
    
    SCOPE_CHOICES = [
        ('global', 'Global - All'),
        ('scope', 'Emission Scope'),
        ('org_unit', 'Organization Unit'),
        ('domain', 'Data Domain'),
    ]
    
    policy_type = models.CharField(max_length=40, choices=POLICY_TYPES)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    
    # Scoping
    scope_type = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='global')
    emission_scope = models.PositiveSmallIntegerField(
        null=True, blank=True,
        choices=[(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')],
        help_text="Apply only to modules in this emission scope"
    )
    org_unit = models.ForeignKey(
        'mdm.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL,
        help_text="Apply only to this organization unit"
    )
    domain = models.ForeignKey(
        DataDomain, null=True, blank=True, on_delete=models.SET_NULL,
        help_text="Apply only to assets in this data domain"
    )
    
    # Policy configuration
    config = models.JSONField(
        default=dict,
        help_text="Policy rules: check_row_count, max_rows, block_with_dependencies, etc."
    )
    error_message = models.TextField(
        default="This action is blocked by governance policy.",
        help_text="Custom error message shown to users when policy blocks an action"
    )
    remediation_steps = models.JSONField(
        default=list,
        help_text="List of steps user should take to resolve the issue"
    )
    
    # Metadata
    usage_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this policy has blocked an action"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='updated_policies')

    class Meta:
        verbose_name = "Governance Policy"
        verbose_name_plural = "Governance Policies"
        ordering = ['policy_type', 'scope_type']

    def __str__(self):
        scope_label = f" [{self.get_scope_type_display()}]" if self.scope_type != 'global' else ""
        status = 'enabled' if self.enabled else 'disabled'
        return f"{self.name}{scope_label} ({status})"
    
    def increment_usage(self):
        """Track policy enforcement"""
        self.usage_count += 1
        self.save(update_fields=['usage_count'])
