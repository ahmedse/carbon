# connections/models.py — Data source and consuming system connections
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
import hashlib
import secrets

User = get_user_model()


class DataSource(models.Model):
    """
    A data source: where data comes from.
    Types: Excel/CSV, Database, REST API, MDM, IoT, Manual Entry.
    """
    SOURCE_TYPES = [
        ('excel', 'Excel / CSV'),
        ('database', 'Database'),
        ('api', 'REST API'),
        ('mdm', 'MDM System'),
        ('iot', 'IoT / Sensor'),
        ('manual', 'Manual Entry'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
    ]

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    description = models.TextField(blank=True)
    connection_config = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    domain = models.ForeignKey(
        'catalog.DataDomain', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='data_sources'
    )
    owner = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='owned_sources'
    )
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.source_type})"


class ConsumingConnection(models.Model):
    """
    A consuming system: where data goes (Pulse, Power BI, Tableau, webhooks, API clients).
    Manages API keys for external access.
    """
    SYSTEM_TYPES = [
        ('pulse', 'Pulse AI'),
        ('powerbi', 'Power BI'),
        ('tableau', 'Tableau'),
        ('api_key', 'API Client'),
        ('webhook', 'Webhook'),
    ]

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    system_type = models.CharField(max_length=20, choices=SYSTEM_TYPES)
    description = models.TextField(blank=True)
    api_key_hash = models.CharField(max_length=64, blank=True, db_index=True)
    api_key_salt = models.CharField(max_length=32, blank=True)
    scopes = models.JSONField(default=list, blank=True, help_text="List of DataTable IDs or domain slugs")
    is_active = models.BooleanField(default=True)
    owner = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='owned_connections'
    )
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.system_type})"

    def generate_api_key(self):
        """Generate a new API key, hash it, and return the plaintext (shown once)."""
        key = secrets.token_urlsafe(48)
        salt = secrets.token_hex(16)
        key_hash = hashlib.sha256((key + salt).encode()).hexdigest()
        self.api_key_hash = key_hash
        self.api_key_salt = salt
        self.save()
        return key

    def verify_api_key(self, plaintext_key):
        """Verify a plaintext API key against the stored hash."""
        if not plaintext_key or not self.api_key_hash or not self.api_key_salt:
            return False
        computed_hash = hashlib.sha256((plaintext_key + self.api_key_salt).encode()).hexdigest()
        return computed_hash == self.api_key_hash
