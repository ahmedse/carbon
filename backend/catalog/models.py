# catalog/models.py — Data Trust Core: Catalog & Governance.
# domain-agnostic. MUST NOT import from emissions.
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models

from connections.models import DataSource
from core.models import Module
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


# ════════════════════════════════════════════════════════════════════════════
# Dataset Hub (Phase P1C — adopted from the former datahub app).
# Governed, versioned data products. Governance METADATA only — the rows
# themselves stay in ``dataschema.DataTable/DataRow`` (never duplicated here).
# ════════════════════════════════════════════════════════════════════════════

LIFECYCLE_STATES = [
    ('draft', 'Draft'),
    ('active', 'Active'),
    ('deprecated', 'Deprecated'),
    ('archived', 'Archived'),
]

VERSION_STATUSES = [
    ('pending', 'Pending DQ Review'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]


class Dataset(models.Model):
    """Governed, versioned semantic data product.

    A Dataset is a named collection of data (backed by DataTable(s) in
    dataschema) with full governance: domain, classification, owner, module
    scope (CBAC anchor), lifecycle state, and a current approved version
    pointer.

    The ``module`` FK is the primary CBAC scope anchor. ScopedRole(module=X)
    controls access to all Datasets with module=X. Explicit
    ``DatasetAccessPolicy`` rows override module-level scoping per dataset.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    domain = models.ForeignKey(
        DataDomain, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='datasets',
    )
    module = models.ForeignKey(
        Module, on_delete=models.PROTECT, related_name='datasets',
        help_text='CBAC scope anchor — controls which ScopedRole grants access.',
    )
    classification = models.CharField(
        max_length=20, choices=CLASSIFICATION_CHOICES, default='internal',
    )
    owner = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='owned_datasets',
    )
    steward = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='stewarded_datasets',
        help_text='Data steward accountable for this data product (advisory).',
    )
    source = models.ForeignKey(
        DataSource, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='datasets',
        help_text='Origin connection (ERP, CSV, API). Null = manually entered.',
    )
    # Pointer to the latest approved version — updated on approval only.
    current_version = models.OneToOneField(
        'DatasetVersion', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='current_for_dataset',
    )
    status = models.CharField(max_length=20, choices=LIFECYCLE_STATES, default='draft')
    tags = models.ManyToManyField('Tag', blank=True, related_name='datasets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='created_datasets',
    )

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class DatasetVersion(models.Model):
    """Immutable snapshot of a Dataset at a point in time.

    Once status='approved', the version is frozen. New data = new version.
    The data itself lives in dataschema.DataTable/DataRow (existing storage).
    This model is governance metadata only.

    Lineage stored as: {"source": {"type": "erp_snapshot"/"csv_upload"/"api",
    "ref": "<id or filename>"}, "upstream_version_ids": ["<uuid>", ...],
    "transforms": [{"name": "...", "params": {...}}]}
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()  # auto-incremented per dataset
    # The actual storage: rows live in dataschema.DataRow linked to this DataTable
    data_table = models.ForeignKey(
        DataTable, on_delete=models.PROTECT, related_name='dataset_versions',
        help_text='The DataTable holding the rows for this version.',
    )
    row_count = models.BigIntegerField(null=True, blank=True)
    # Schema at version creation time: {field_name: {type, required, ...}}
    schema_snapshot = models.JSONField(default=dict)
    # Health: 0.0-1.0 composite, and per-dimension breakdown
    health_score = models.FloatField(null=True, blank=True)
    health_detail = models.JSONField(
        default=dict,
        help_text='{"completeness": 0.98, "validity": 0.95, "freshness": 1.0}',
    )
    # DQ link: which DQ job produced this health score
    dq_job_id = models.CharField(max_length=200, blank=True)
    # Provenance
    lineage = models.JSONField(default=dict)
    # Approval
    status = models.CharField(max_length=20, choices=VERSION_STATUSES, default='pending')
    approved_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='approved_dataset_versions',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='created_dataset_versions',
    )

    class Meta:
        unique_together = ('dataset', 'version_number')
        ordering = ['-version_number']

    def __str__(self):
        return f"{self.dataset.name} v{self.version_number} ({self.status})"

    @property
    def tables(self):
        """All DataTables in this version (members first, legacy fallback)."""
        member_tables = [m.data_table for m in self.members.all()]
        if member_tables:
            return member_tables
        return [self.data_table] if self.data_table_id else []


class DatasetVersionMember(models.Model):
    """One table inside a multi-table DatasetVersion (the data-product composition)."""
    version = models.ForeignKey(
        'DatasetVersion', on_delete=models.CASCADE, related_name='members')
    data_table = models.ForeignKey(
        'dataschema.DataTable', on_delete=models.PROTECT,
        related_name='dataset_version_members')
    order = models.PositiveIntegerField(default=0)
    label = models.CharField(
        max_length=120, blank=True,
        help_text='Semantic name within the product, e.g. "orders", "customers".')
    row_count = models.IntegerField(default=0)
    schema_snapshot = models.JSONField(default=dict, blank=True)
    health_score = models.FloatField(null=True, blank=True)
    health_detail = models.JSONField(default=dict, blank=True)
    dq_job_id = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ['order', 'id']
        unique_together = [('version', 'data_table')]
        verbose_name = 'dataset version member'
        verbose_name_plural = 'dataset version members'

    def __str__(self):
        return f"{self.version} :: {self.data_table_id or self.label or self.order}"


class DataContract(models.Model):
    """Formal promise on a Dataset — what downstream apps depend on.

    A contract is a binding SLA. If any version violates it, a
    DataContractViolation is created. Apps should check contract health before
    consuming a new version.
    """
    dataset = models.OneToOneField(Dataset, on_delete=models.CASCADE,
                                   related_name='contract')
    # Schema promise: list of required field names
    required_fields = models.JSONField(
        default=list,
        help_text='Field names that must always be present.',
    )
    # Quality SLAs: minimum acceptable scores per dimension
    min_completeness = models.FloatField(null=True, blank=True)  # e.g. 0.95
    min_validity = models.FloatField(null=True, blank=True)
    min_health_score = models.FloatField(null=True, blank=True)  # overall
    # Freshness SLA: maximum acceptable age in hours
    freshness_hours = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='If set, a version older than this many hours triggers a freshness violation.',
    )
    # Downstream apps that depend on this contract (informational)
    consumer_apps = models.JSONField(
        default=list,
        help_text='App slugs (from AppManifest) that consume this dataset.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"Contract for {self.dataset.name}"


class DataContractViolation(models.Model):
    """Recorded when a DataContract check fails for a DatasetVersion."""
    VIOLATION_TYPES = [
        ('schema', 'Schema — missing required field'),
        ('quality', 'Quality — score below minimum SLA'),
        ('freshness', 'Freshness — version too old'),
    ]
    contract = models.ForeignKey(DataContract, on_delete=models.CASCADE,
                                 related_name='violations')
    dataset_version = models.ForeignKey(DatasetVersion, on_delete=models.CASCADE,
                                        related_name='contract_violations')
    violation_type = models.CharField(max_length=20, choices=VIOLATION_TYPES)
    detail = models.JSONField(default=dict)  # {field, expected, actual} etc.
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ['-detected_at']

    def __str__(self):
        return f"{self.violation_type} violation on {self.dataset_version}"


class DatasetAccessPolicy(models.Model):
    """Per-dataset access override. Takes precedence over module-level ScopedRole.

    Exactly one of user/group must be non-null (enforced in clean()).
    """
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE,
                                related_name='access_policies')
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE,
                             related_name='dataset_policies')
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.CASCADE,
                              related_name='dataset_policies')
    can_view = models.BooleanField(default=True)
    can_ingest = models.BooleanField(default=False)
    can_approve = models.BooleanField(default=False)
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='granted_dataset_policies')
    granted_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    def clean(self):
        if (self.user is None) == (self.group is None):
            raise ValidationError('Exactly one of user or group must be set.')

    def __str__(self):
        subject = self.user or self.group
        return f"Access policy for {self.dataset} → {subject}"


class LineageEdge(models.Model):
    """Data lineage graph: directed edge from source_table to target_table.
    
    Models table-level and (optionally) column-level data lineage.
    Supports multiple edge types (transform, copy, aggregate, dependency).
    """
    class EdgeType(models.TextChoices):
        TRANSFORM = 'transform', 'Transform'
        COPY = 'copy', 'Copy'
        AGGREGATE = 'aggregate', 'Aggregate'
        DEPENDENCY = 'dependency', 'Dependency'

    source_table = models.ForeignKey(
        'dataschema.DataTable',
        on_delete=models.CASCADE,
        related_name='lineage_outgoing',
        help_text='Source table in the lineage relationship'
    )
    target_table = models.ForeignKey(
        'dataschema.DataTable',
        on_delete=models.CASCADE,
        related_name='lineage_incoming',
        help_text='Target (destination) table in the lineage relationship'
    )
    # Column lineage (optional — P2 feature)
    source_field = models.ForeignKey(
        'dataschema.DataField',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='lineage_outgoing',
        help_text='Optional: specific source column'
    )
    target_field = models.ForeignKey(
        'dataschema.DataField',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='lineage_incoming',
        help_text='Optional: specific target column'
    )
    edge_type = models.CharField(
        max_length=20,
        choices=EdgeType.choices,
        default=EdgeType.DEPENDENCY
    )
    transform_description = models.TextField(
        blank=True,
        help_text='Human-readable description of the transformation (e.g., "SUM(amount) grouped by date")'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('source_table', 'target_table', 'edge_type')]
        indexes = [
            models.Index(fields=['source_table']),
            models.Index(fields=['target_table']),
        ]

    def __str__(self):
        return f"{self.source_table} --[{self.edge_type}]--> {self.target_table}"
