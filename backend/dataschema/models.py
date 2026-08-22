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
    is_locked = models.BooleanField(
        default=False,
        help_text="When locked, prevents accidental deletion or modification (admin override available)"
    )
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
    reference_set = models.ForeignKey('mdm.ReferenceSet', null=True, blank=True, on_delete=models.SET_NULL, related_name='bound_fields')
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
    dq_flags = models.JSONField(default=list, blank=True)
    # Content hash (sha256 of canonical JSON of normalized values) used by the
    # ingest watermark to skip already-materialized rows on incremental re-runs.
    row_hash = models.CharField(max_length=64, db_index=True, blank=True, default='')

    class Meta:
        indexes = [
            models.Index(fields=['data_table', 'id'],         name='datarow_table_id_idx'),
            models.Index(fields=['data_table', 'created_at'], name='datarow_table_time_idx'),
        ]
        # fillfactor=100 is applied via migration 0007 ALTER TABLE — no dead-tuple headroom needed

    _MUTABLE_FIELDS = frozenset({'is_archived', 'dq_flags', 'version', 'updated_at', 'updated_by_id'})

    def save(self, *args, **kwargs):
        # Append-only trust layer: only the mutable bookkeeping fields may be
        # updated. Inserts (including explicit-PK inserts via create(id=...))
        # are always allowed.
        if self.pk is not None and not kwargs.get('force_insert'):
            allowed = self._MUTABLE_FIELDS
            update_fields = set(kwargs.get('update_fields') or [])
            if not update_fields:
                from django.db import IntegrityError
                raise IntegrityError(
                    "DataRow is append-only — do not update; insert a new row."
                )
            bad = update_fields - allowed
            if bad:
                from django.db import IntegrityError
                raise IntegrityError(f"DataRow fields are immutable: {bad}")
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

class TableRelation(models.Model):
   """
   Explicit representation of a relationship between two DataTables.
   Tracks lineage, foreign keys, and lookup references for the schema manager UI.
   """
   RELATION_TYPES = [
       ('one_to_many', 'One → Many'),
       ('many_to_many', 'Many → Many'),
       ('lookup', 'Lookup'),
   ]
   from_table = models.ForeignKey(
       DataTable, on_delete=models.CASCADE, related_name='outgoing_relations'
   )
   from_field = models.ForeignKey(
       DataField, null=True, blank=True, on_delete=models.SET_NULL,
       related_name='outgoing_relations',
       help_text="The FK column on from_table (optional)"
   )
   to_table = models.ForeignKey(
       DataTable, on_delete=models.CASCADE, related_name='incoming_relations'
   )
   to_field = models.ForeignKey(
       DataField, null=True, blank=True, on_delete=models.SET_NULL,
       related_name='incoming_relations',
       help_text="The PK/target column on to_table (optional)"
   )
   relation_type = models.CharField(
       max_length=20, choices=RELATION_TYPES, default='one_to_many'
   )
   label = models.CharField(max_length=120, blank=True)
   description = models.TextField(blank=True)
   created_by = models.ForeignKey(
       User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_relations'
   )
   created_at = models.DateTimeField(auto_now_add=True)
   updated_at = models.DateTimeField(auto_now=True)

   class Meta:
       unique_together = [('from_table', 'to_table', 'from_field', 'to_field')]
       ordering = ['-created_at']

   def __str__(self):
       return f"{self.from_table.title} → {self.to_table.title} ({self.relation_type})"