from django.conf import settings
from django.db import models


class InboundBatch(models.Model):
    KIND_TYPED = 'typed_object'
    KIND_PRODUCT = 'data_product'
    KIND_CHOICES = [
        (KIND_TYPED, 'Typed object'),
        (KIND_PRODUCT, 'Data product'),
    ]
    STATUS_DRAFT = 'draft'
    STATUS_MAPPED = 'mapped'
    STATUS_SMOKED = 'smoked'
    STATUS_COMMITTED = 'committed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_MAPPED, 'Mapped'),
        (STATUS_SMOKED, 'Smoked'),
        (STATUS_COMMITTED, 'Committed'),
        (STATUS_FAILED, 'Failed'),
    ]

    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    target_key = models.CharField(max_length=80)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    file = models.FileField(upload_to='inbound/%Y/%m/', blank=True, default='')
    original_filename = models.CharField(max_length=255, blank=True, default='')
    sha256 = models.CharField(max_length=64, blank=True, default='')
    encoding = models.CharField(max_length=32, blank=True, default='')
    delimiter = models.CharField(max_length=4, blank=True, default=',')
    headers = models.JSONField(default=list, blank=True)
    sample = models.JSONField(default=list, blank=True)
    row_count = models.IntegerField(null=True, blank=True)
    mapping = models.JSONField(default=dict, blank=True)
    smoke = models.JSONField(default=dict, blank=True)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='inbound_prepared',
    )
    committed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='inbound_committed',
    )
    prepared_at = models.DateTimeField(null=True, blank=True)
    committed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'Inbound {self.id} {self.target_key} ({self.status})'


class InboundCartridge(models.Model):
    """Declared load object. Smoke and commit stay in the app that registers the key."""

    key = models.CharField(max_length=80, unique=True)
    kind = models.CharField(max_length=20, choices=InboundBatch.KIND_CHOICES)
    label = models.CharField(max_length=160)
    label_ar = models.CharField(max_length=160, blank=True, default='')
    owner_app = models.CharField(max_length=40)
    fields = models.JSONField(default=list, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']

    def __str__(self):
        return self.key


class InboundTemplate(models.Model):
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20)
    target_key = models.CharField(max_length=80)
    mapping = models.JSONField(default=dict, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='inbound_templates',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('name', 'target_key')
        ordering = ['target_key', 'name']
