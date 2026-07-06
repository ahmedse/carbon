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
    scope = models.PositiveSmallIntegerField(choices=SCOPE_CHOICES, default=1)
    org_unit = models.ForeignKey(
        'mdm.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL, related_name='modules'
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