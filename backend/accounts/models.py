# File: accounts/models.py
# Production-ready RBAC models with scoped project/module roles.

from django.db import models
from django.contrib.auth.models import AbstractUser, Group
from django.core.exceptions import ValidationError
from django.utils import timezone

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# --- USER ---

class User(AbstractUser):
    """
    Custom user model.
    """

    class Language(models.TextChoices):
        ENGLISH = 'en', 'English'
        ARABIC = 'ar', 'العربية'

    # I18N-5: per-user UI language preference (ADR-0018). Defaults to English;
    # never auto-detected from the browser. Persisted server-side so the
    # preference survives across devices and is reconciled on login.
    language = models.CharField(
        max_length=10,
        choices=Language.choices,
        default=Language.ENGLISH,
        blank=False,
        help_text='UI language preference (en/ar).',
    )

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
    from_name = models.CharField(max_length=100, blank=True, default='AASTMT · Data Trust Platform', help_text='Display name for From: header')
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


# ── Phase 1.4b: General Platform Configuration ────────────────────────────────

class GeneralConfig(models.Model):
    """Singleton — general platform-wide settings, admin-configurable.

    Currently holds the display timezone. Storage remains UTC (USE_TZ); this
    drives how times are rendered for humans (schedule previews, admin
    timestamps, form defaults) without a code redeploy.
    """

    # Curated IANA zones relevant to AASTMT + common deployments. A value
    # outside this list is still accepted at the DB level; rendering falls
    # back gracefully to Django's default when a zone is unknown.
    TIMEZONE_CHOICES = [
        ('Africa/Cairo', 'Africa/Cairo (Egypt, UTC+2)'),
        ('UTC', 'UTC (Coordinated Universal Time)'),
        ('Europe/London', 'Europe/London (UTC+0/+1)'),
        ('Europe/Berlin', 'Europe/Berlin (CET, UTC+1/+2)'),
        ('Asia/Riyadh', 'Asia/Riyadh (UTC+3)'),
        ('Asia/Dubai', 'Asia/Dubai (UTC+4)'),
        ('America/New_York', 'America/New_York (UTC-5/-4)'),
    ]

    timezone = models.CharField(
        max_length=64,
        choices=TIMEZONE_CHOICES,
        default='Africa/Cairo',
        help_text='Display timezone for schedule previews and timestamps.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'General Configuration'
        verbose_name_plural = 'General Configuration'

    def __str__(self):
        return f"General Config (timezone={self.timezone})"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @classmethod
    def get_timezone(cls) -> ZoneInfo:
        """Return the configured display timezone as a ``ZoneInfo``.

        Falls back to Django's default timezone when the stored value is
        unknown or the singleton is unavailable (e.g. pre-migration).
        """
        try:
            return ZoneInfo(cls.load().timezone)
        except (ZoneInfoNotFoundError, KeyError, ValueError):
            from django.utils import timezone as _tz
            return _tz.get_default_timezone()


# ── Phase 1.6: Notification System ────────────────────────────────────────────


class UserAlert(models.Model):
    """Phase 1.6 — In-app user alert/notification with category routing."""

    class Category(models.TextChoices):
        SYSTEM = 'system', 'System'
        DQ_VIOLATION = 'dq_violation', 'DQ Violation'
        SECURITY = 'security', 'Security'
        WORKFLOW = 'workflow', 'Workflow'
        BACKUP = 'backup', 'Backup'
        IMPORT = 'import', 'Import'
        OTHER = 'other', 'Other'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='alerts')
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default='')
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.SYSTEM)
    link = models.CharField(max_length=512, blank=True, default='', help_text='Optional deep-link URL')
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return f"{self.category}: {self.title[:60]}"


class NotificationChannel(models.Model):
    """Per-user channel preferences."""

    class ChannelType(models.TextChoices):
        IN_APP = 'in_app', 'In-App Only'
        EMAIL = 'email', 'Email Only'
        BOTH = 'both', 'Both'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_channel')
    channel_type = models.CharField(max_length=10, choices=ChannelType.choices, default=ChannelType.IN_APP)
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} — {self.channel_type} {'(on)' if self.enabled else '(off)'}"


class NotificationRule(models.Model):
    """Admin-configured rule: when X happens, notify Y via Z."""

    class EventType(models.TextChoices):
        DQ_VIOLATION = 'dq_violation', 'DQ Violation'
        DQ_RULE_FAILURE = 'dq_rule_failure', 'DQ Rule Execution Failure'
        PASSWORD_RESET = 'password_reset', 'Password Reset Request'
        BACKUP_FAILURE = 'backup_failure', 'Backup Failure'
        BACKUP_SUCCESS = 'backup_success', 'Backup Success'
        IMPORT_COMPLETE = 'import_complete', 'Import Complete'
        IMPORT_FAILURE = 'import_failure', 'Import Failure'
        SYSTEM_ALERT = 'system_alert', 'System Alert'
        FRESHNESS_VIOLATION = 'freshness_violation', 'Data Freshness Violation'
        SCHEMA_CHANGE = 'schema_change', 'Schema Change Detected'

    class Severity(models.TextChoices):
        INFO = 'info', 'Info'
        WARNING = 'warning', 'Warning'
        ERROR = 'error', 'Error'
        CRITICAL = 'critical', 'Critical'

    class ChannelType(models.TextChoices):
        IN_APP = 'in_app', 'In-App'
        EMAIL = 'email', 'Email'
        BOTH = 'both', 'Both'

    event_type = models.CharField(max_length=32, choices=EventType.choices)
    min_severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.WARNING)
    channel = models.CharField(max_length=10, choices=ChannelType.choices, default=ChannelType.IN_APP)
    group_target = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True,
                                     help_text='Notify all users in this group')
    enabled = models.BooleanField(default=True)
    description = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['event_type', '-min_severity']

    def __str__(self):
        group = f"→ {self.group_target.name}" if self.group_target else "→ all"
        return f"{self.get_event_type_display()} ({self.min_severity}) {self.channel} {group}"


# ── Notification helper ───────────────────────────────────────────────────────

def notify_event(event_type, title, body, severity='warning', link='', category=None, user=None, group=None):
    """Create notifications for matching rules. Called by various app signals.
    
    When a specific user is provided (e.g., password reset), notification is created
    directly without checking NotificationRules. Rules gate broadcast events only.
    
    Args:
        event_type: One of NotificationRule.EventType values
        title, body: Notification content
        severity: One of NotificationRule.Severity values
        link: Optional deep-link URL
        category: Notification.Category override (auto-derived from event_type if None)
        user: Specific user to notify (used for password_reset, etc.)
        group: Django Group to notify (used for DQ violations, etc.)
    """
    from accounts.models import UserAlert, NotificationRule, NotificationChannel

    # Map event_type → UserAlert.Category
    category_map = {
        'dq_violation': UserAlert.Category.DQ_VIOLATION,
        'dq_rule_failure': UserAlert.Category.DQ_VIOLATION,
        'password_reset': UserAlert.Category.SECURITY,
        'backup_failure': UserAlert.Category.BACKUP,
        'backup_success': UserAlert.Category.BACKUP,
        'import_complete': UserAlert.Category.IMPORT,
        'import_failure': UserAlert.Category.IMPORT,
        'system_alert': UserAlert.Category.SYSTEM,
        'freshness_violation': UserAlert.Category.DQ_VIOLATION,
        'schema_change': UserAlert.Category.SYSTEM,
    }
    notif_category = category or category_map.get(event_type, UserAlert.Category.OTHER)

    # Find matching enabled rules
    rules = list(NotificationRule.objects.filter(
        enabled=True,
        event_type=event_type,
    ).select_related('group_target'))

    severity_rank = {s.value: i for i, s in enumerate(NotificationRule.Severity)}
    event_rank = severity_rank.get(severity, 1)
    rules = [r for r in rules if severity_rank.get(r.min_severity, 0) <= event_rank]

    if not rules:
        return  # No matching rules — no notifications needed

    # Determine target users
    if user:
        users = [user]
    elif group:
        users = list(group.user_set.all())
    else:
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        users = list(UserModel.objects.filter(is_active=True))

    # Also add users from rule.group_target
    for rule in rules:
        if rule.group_target:
            users.extend(rule.group_target.user_set.all())

    users = list(set(users))  # deduplicate

    # Create alerts for each user
    for u in users:
        _create_alert_for_user(u, title, body, notif_category, link)

    # TODO Phase 2: Send email notifications for rules with channel=email or both


def _create_alert_for_user(user, title, body, category, link):
    """Create a single UserAlert for a user, respecting their channel preferences."""
    from accounts.models import UserAlert, NotificationChannel
    
    try:
        channel_pref = user.notification_channel
        if not channel_pref.enabled:
            return
    except NotificationChannel.DoesNotExist:
        pass  # No preference set — default to allow
    
    UserAlert.objects.create(
        user=user,
        title=title,
        body=body,
        category=category,
        link=link,
    )