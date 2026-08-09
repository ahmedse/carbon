# File: accounts/models.py
# Production-ready RBAC models with scoped project/module roles.

from django.db import models
from django.contrib.auth.models import AbstractUser, Group
from django.core.exceptions import ValidationError
from django.utils import timezone

# --- USER ---

class User(AbstractUser):
    """
    Custom user model.
    """

    def __str__(self):
        return self.username

# --- SCOPED ROLE ASSIGNMENT ---

class ScopedRole(models.Model):
    """
    Assigns a role (Group) to a user for a specific org-unit/module scope.
    - If org_unit/module are null, role applies globally.
    - If org_unit is set and module is null: org-unit-level role.
    - If module is set: module-level role (org_unit optional).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="scoped_roles")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="scoped_roles")
    org_unit = models.ForeignKey(
        "mdm.OrgUnit", null=True, blank=True, on_delete=models.CASCADE, related_name="scoped_roles"
    )
    module = models.ForeignKey(
        "core.Module", null=True, blank=True, on_delete=models.CASCADE, related_name="scoped_roles"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "group", "org_unit", "module")
        verbose_name = "Scoped Role Assignment"
        verbose_name_plural = "Scoped Role Assignments"

    def __str__(self):
        scope = []
        if self.org_unit:
            scope.append(f"OrgUnit:{self.org_unit}")
        if self.module:
            scope.append(f"Module:{self.module}")
        return f"{self.user} as {self.group.name} in {'/'.join(scope) or 'global'}"

# --- AUDIT LOGGING ---

class RoleAssignmentAuditLog(models.Model):
    """
    Audit log for all scoped role assignments.
    """
    ACTIONS = (
        ("assigned", "Assigned"),
        ("removed", "Removed"),
        ("modified", "Modified"),
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="role_audit_logs")
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="role_audit_actions")
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True)
    org_unit = models.ForeignKey("mdm.OrgUnit", null=True, blank=True, on_delete=models.SET_NULL)
    module = models.ForeignKey("core.Module", null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=16, choices=ACTIONS)
    timestamp = models.DateTimeField(default=timezone.now)
    extra = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.timestamp}: {self.action} {self.group} for {self.user}"


class GroupMetadata(models.Model):
    """Extended metadata for Django Group role definitions."""

    CATEGORY_CHOICES = [
        ('platform', 'Platform'),
        ('app', 'App'),
    ]

    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='metadata')
    description = models.TextField(blank=True, default='')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='app')
    app_id = models.CharField(max_length=50, blank=True, default='')
    manifest_key = models.CharField(max_length=100, blank=True, default='')
    is_scoped = models.BooleanField(default=False)
    is_protected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Group Metadata'
        verbose_name_plural = 'Group Metadata'

    def __str__(self):
        return f"Metadata for {self.group.name}"


class PlatformAppConfig(models.Model):
    """Runtime configuration for a platform app declared in APP_REGISTRY.
    Controls enable/disable and display ordering at runtime without code changes.
    """

    app_id = models.CharField(max_length=50, unique=True, db_index=True)
    is_enabled = models.BooleanField(default=True, db_index=True)
    display_order = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Platform App Config"
        verbose_name_plural = "Platform App Configs"
        ordering = ["display_order", "app_id"]

    def __str__(self):
        status = "enabled" if self.is_enabled else "disabled"
        return f"{self.app_id} ({status})"


# --- SYSTEM ROLE NAMES (constants for code clarity) ---

SYSTEM_ROLES = {
    "admin": "admin",
    "audit": "audit",
    "dataowner": "dataowner",
}


# ── Phase 1.1: Enterprise Configuration Models ──────────────────────────────

class EmailConfig(models.Model):
    """Singleton — SMTP / Anymail email backend configuration.
    Admin-configurable — no .env edits or redeploy needed.
    """

    BACKEND_CHOICES = [
        ('anymail.backends.brevo.EmailBackend', 'Brevo (Sendinblue)'),
        ('anymail.backends.sendgrid.EmailBackend', 'SendGrid'),
        ('anymail.backends.mailgun.EmailBackend', 'Mailgun'),
        ('anymail.backends.amazon_ses.EmailBackend', 'Amazon SES'),
        ('anymail.backends.resend.EmailBackend', 'Resend'),
        ('django.core.mail.backends.smtp.EmailBackend', 'Generic SMTP'),
        ('django.core.mail.backends.console.EmailBackend', 'Console (dev only)'),
    ]

    backend = models.CharField(
        max_length=100, choices=BACKEND_CHOICES,
        default='django.core.mail.backends.console.EmailBackend',
        help_text='Email backend provider'
    )
    host = models.CharField(max_length=255, blank=True, default='', help_text='SMTP host')
    port = models.IntegerField(default=587, help_text='SMTP port (587 TLS, 465 SSL, 25)')
    username = models.CharField(max_length=255, blank=True, default='', help_text='SMTP username or API key')
    password = models.CharField(max_length=255, blank=True, default='', help_text='SMTP password or API key')
    use_tls = models.BooleanField(default=True, help_text='Use STARTTLS')
    use_ssl = models.BooleanField(default=False, help_text='Use SSL (port 465)')
    from_email = models.EmailField(max_length=255, default='noreply@carbon.clearturn.tech', help_text='Default From: address')
    from_name = models.CharField(max_length=100, blank=True, default='Carbon Data Trust', help_text='Display name for From: header')
    enabled = models.BooleanField(default=True, help_text='Enable outgoing email')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Email Configuration'
        verbose_name_plural = 'Email Configuration'

    def __str__(self):
        return f"Email Config ({'enabled' if self.enabled else 'disabled'})"

    def save(self, *args, **kwargs):
        """Enforce singleton — only one row allowed."""
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Return the singleton config, creating defaults if needed."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def as_django_settings(self) -> dict:
        """Return a dict suitable for assigning to Django's email settings."""
        return {
            'EMAIL_BACKEND': self.backend,
            'EMAIL_HOST': self.host,
            'EMAIL_PORT': self.port,
            'EMAIL_HOST_USER': self.username,
            'EMAIL_HOST_PASSWORD': self.password,
            'EMAIL_USE_TLS': self.use_tls,
            'EMAIL_USE_SSL': self.use_ssl,
            'DEFAULT_FROM_EMAIL': f'{self.from_name} <{self.from_email}>' if self.from_name else self.from_email,
            # Anymail API keys
            'ANYMAIL': {
                'SENDINBLUE_API_KEY': self.password if 'brevo' in self.backend else '',
                'SENDGRID_API_KEY': self.password if 'sendgrid' in self.backend else '',
                'MAILGUN_API_KEY': self.password if 'mailgun' in self.backend else '',
                'AMAZON_SES_ACCESS_KEY_ID': self.username if 'amazon_ses' in self.backend else '',
                'AMAZON_SES_SECRET_ACCESS_KEY': self.password if 'amazon_ses' in self.backend else '',
                'RESEND_API_KEY': self.password if 'resend' in self.backend else '',
            },
        }


class PasswordPolicy(models.Model):
    """Singleton — configurable password policy for the platform."""

    min_length = models.IntegerField(default=12, help_text='Minimum password length')
    require_uppercase = models.BooleanField(default=True, help_text='Require at least one uppercase letter')
    require_lowercase = models.BooleanField(default=True, help_text='Require at least one lowercase letter')
    require_number = models.BooleanField(default=True, help_text='Require at least one digit')
    require_special = models.BooleanField(default=True, help_text='Require at least one special character')
    max_age_days = models.IntegerField(default=90, help_text='Force password change after N days (0 = never)')
    prevent_reuse_n = models.IntegerField(default=5, help_text='Prevent reuse of last N passwords (0 = unlimited)')
    lockout_after_n = models.IntegerField(default=5, help_text='Lock account after N failed attempts (0 = never)')
    lockout_minutes = models.IntegerField(default=15, help_text='Auto-unlock after N minutes')
    password_reset_timeout_hours = models.IntegerField(default=24, help_text='Reset token expiry in hours')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Password Policy'
        verbose_name_plural = 'Password Policy'

    def __str__(self):
        return f"Password Policy (min {self.min_length} chars, {self.max_age_days}d expiry)"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ── Phase 1.2: DB Backup Configuration ────────────────────────────────────────

class BackupConfig(models.Model):
    """Singleton — automated DB backup configuration."""

    FREQUENCY_CHOICES = [
        ('daily', 'Daily (2 AM)'),
        ('twice_daily', 'Twice Daily (2 AM + 2 PM)'),
        ('hourly', 'Hourly'),
        ('manual', 'Manual Only'),
    ]
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='daily')
    retention_days = models.IntegerField(default=30, help_text='Auto-delete backups older than N days')
    s3_bucket = models.CharField(max_length=255, blank=True, default='', help_text='Optional S3 bucket for offsite storage')
    s3_path = models.CharField(max_length=255, blank=True, default='', help_text='S3 key prefix, e.g. carbon-backups/')
    enabled = models.BooleanField(default=True)
    last_backup_at = models.DateTimeField(null=True, blank=True)
    last_backup_size_bytes = models.BigIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Backup Configuration'
        verbose_name_plural = 'Backup Configuration'

    def __str__(self):
        return f"Backup ({self.frequency}, {self.retention_days}d retention)"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class BackupRecord(models.Model):
    """Log of each backup execution."""

    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('running', 'Running'),
    ]
    filename = models.CharField(max_length=255)
    size_bytes = models.BigIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    location = models.CharField(max_length=512, blank=True, default='', help_text='File path or S3 URI')
    error_message = models.TextField(blank=True, default='')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Backup Record'
        verbose_name_plural = 'Backup Records'
        ordering = ['-started_at']

    def __str__(self):
        return f"Backup {self.filename} ({self.status}) — {self.started_at:%Y-%m-%d %H:%M}"


# ── Phase 1.3: Log Configuration ──────────────────────────────────────────────

class LogConfig(models.Model):
    """Singleton — logging configuration."""

    LEVEL_CHOICES = [
        ('DEBUG', 'DEBUG'),
        ('INFO', 'INFO'),
        ('WARNING', 'WARNING'),
        ('ERROR', 'ERROR'),
    ]
    default_level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='INFO')
    retention_days = models.IntegerField(default=90, help_text='Auto-delete request logs older than N days')
    json_format = models.BooleanField(default=True, help_text='Use JSON structured logging')
    db_log_level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='ERROR', help_text='Min level for DB logging (prevents fillup)')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Log Configuration'
        verbose_name_plural = 'Log Configuration'

    def __str__(self):
        return f"Log Config ({self.default_level}, {self.retention_days}d retention)"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ── Phase 1.4: API Configuration ──────────────────────────────────────────────

class APIConfig(models.Model):
    """Singleton — DRF API configuration (pagination, versioning)."""

    page_size = models.IntegerField(default=50, help_text='Default items per page')
    max_page_size = models.IntegerField(default=200, help_text='Maximum allowed items per page')
    enable_pagination = models.BooleanField(default=True, help_text='Global pagination toggle')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'API Configuration'
        verbose_name_plural = 'API Configuration'

    def __str__(self):
        return f"API Config (page_size={self.page_size}, pagination={'on' if self.enable_pagination else 'off'})"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj