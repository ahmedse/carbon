# File: core/models.py
# Core business models for SaaS platform, using string references for ForeignKeys.

from django.db import models

class Project(models.Model):
    """
    A project within a tenant.
    """
    name = models.CharField(max_length=100)
    tenant = models.ForeignKey('accounts.Tenant', on_delete=models.CASCADE, related_name='projects')

    class Meta:
        unique_together = ('tenant', 'name')
        verbose_name = "Project"
        verbose_name_plural = "Projects"

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"

class Module(models.Model):
    """
    A module (sub-unit) within a project.
    """
    name = models.CharField(max_length=100)
    project = models.ForeignKey('core.Project', on_delete=models.CASCADE, related_name='modules')

    class Meta:
        unique_together = ('project', 'name')
        verbose_name = "Module"
        verbose_name_plural = "Modules"

    def __str__(self):
        return f"{self.name} ({self.project.name})"
    
class Feedback(models.Model):
    """
    User feedback for the system (suggestions, bug reports, etc).
    """
    name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    message = models.TextField()
    rating = models.PositiveSmallIntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = "Feedback"
        verbose_name_plural = "Feedback"

    def __str__(self):
        return f"Feedback from {self.name or 'Anonymous'} ({self.email or '-'})"