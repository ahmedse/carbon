# File: core/models.py

from django.db import models

class Project(models.Model):
    """
    Represents a project entity belonging to a tenant.
    """
    name = models.CharField(max_length=100, unique=True)
    tenant = models.ForeignKey('accounts.Tenant', on_delete=models.CASCADE, related_name='projects')

    def __str__(self):
        return self.name

class Cycle(models.Model):
    """
    Represents a cycle within a project.
    """
    name = models.CharField(max_length=100)
    project = models.ForeignKey(Project, related_name='cycles', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.project.name})"

class Module(models.Model):
    """
    Represents a module within a project.
    """
    name = models.CharField(max_length=100)
    project = models.ForeignKey(Project, related_name='modules', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.project.name})"