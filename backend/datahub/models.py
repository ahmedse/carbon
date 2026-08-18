"""
datahub/models.py — Phase P1: Dataset Hub (the trust core).

Governed, versioned data products. Governance METADATA only — the rows
themselves stay in ``dataschema.DataTable/DataRow`` (never duplicated here).

Dependency direction: datahub imports catalog / dataschema / dq / connections /
mdm / core / accounts. None of those apps ever import datahub.
"""
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models

from dataschema.models import DataTable
from catalog.models import DataDomain, CLASSIFICATION_CHOICES
from connections.models import DataSource
from core.models import Module

User = get_user_model()

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
    tags = models.ManyToManyField('catalog.Tag', blank=True, related_name='datasets')
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
