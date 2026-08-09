# File: core/models.py
from django.db import models


class Module(models.Model):
    """
    Top-level organisational unit for data collection (Scope 1/2/3).
    """
    SCOPE_CHOICES = [
        (1, 'Scope 1'),
        (2, 'Scope 2'),
        (3, 'Scope 3'),
    ]
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    scope = models.PositiveSmallIntegerField(choices=SCOPE_CHOICES, default=1)
    org_unit = models.ForeignKey(
        'mdm.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL, related_name='modules'
    )
    is_locked = models.BooleanField(
        default=False,
        help_text="When locked, prevents accidental deletion or modification (admin override available)"
    )

    class Meta:
        verbose_name = "Module"
        verbose_name_plural = "Modules"

    def __str__(self):
        return f"{self.name} (Scope {self.scope})"


class Feedback(models.Model):
    name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    message = models.TextField()
    rating = models.PositiveSmallIntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = "Feedback"

    def __str__(self):
        return f"Feedback from {self.name or 'Anonymous'}"


class Notification(models.Model):
    """In-app notification for lifecycle events (submit/verify/reject/batch_complete)."""
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='notifications'
    )
    verb = models.CharField(max_length=50, help_text="e.g. submitted, verified, rejected, batch_complete")
    message = models.TextField(help_text="Human-readable notification body")
    link = models.CharField(max_length=500, blank=True, default='', help_text="Optional URL to related resource")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'read_at']),
        ]

    def __str__(self):
        return f"[{self.verb}] {self.message[:80]}"


# ── Phase 1.3: Request Log (DB-stored) ────────────────────────────────────────

class RequestLog(models.Model):
    """Persisted request log for admin viewing. Only ERROR+ by default."""

    LEVEL_CHOICES = [
        ('DEBUG', 'DEBUG'),
        ('INFO', 'INFO'),
        ('WARNING', 'WARNING'),
        ('ERROR', 'ERROR'),
    ]
    correlation_id = models.CharField(max_length=36, db_index=True)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='INFO', db_index=True)
    method = models.CharField(max_length=10)  # GET, POST, etc.
    path = models.CharField(max_length=512)
    user = models.CharField(max_length=150, blank=True, default='anonymous')
    user_id = models.IntegerField(null=True, blank=True)
    status_code = models.IntegerField(null=True, blank=True, db_index=True)
    duration_ms = models.FloatField(null=True, blank=True)
    remote_addr = models.GenericIPAddressField(null=True, blank=True)
    slow_request = models.BooleanField(default=False, db_index=True)
    timestamp = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name = 'Request Log'
        verbose_name_plural = 'Request Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['level', '-timestamp']),
            models.Index(fields=['status_code', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M:%S} [{self.level}] {self.method} {self.path} → {self.status_code}"