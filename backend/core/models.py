# File: core/models.py
# Purpose: Defines the core domain models: Project, Cycle, and Module.

from django.db import models

class Project(models.Model):
    """
    Represents a project entity.
    """
    name = models.CharField(max_length=100)

    def __str__(self):
        """
        Returns the project's name.
        """
        return self.name

class Cycle(models.Model):
    """
    Represents a cycle within a project.
    """
    name = models.CharField(max_length=100)
    project = models.ForeignKey(Project, related_name='cycles', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        """
        Returns the cycle's name and its associated project's name.
        """
        return f"{self.name} ({self.project.name})"

class Module(models.Model):
    """
    Represents a module within a project.
    """
    name = models.CharField(max_length=100)
    project = models.ForeignKey(Project, related_name='modules', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        """
        Returns the module's name and its associated project's name.
        """
        return f"{self.name} ({self.project.name})"