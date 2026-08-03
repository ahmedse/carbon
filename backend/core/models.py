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