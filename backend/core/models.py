# core/models.py

from django.db import models

class Project(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Cycle(models.Model):
    name = models.CharField(max_length=100)
    project = models.ForeignKey(Project, related_name='cycles', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.project.name})"

class Module(models.Model):
    name = models.CharField(max_length=100)
    project = models.ForeignKey(Project, related_name='modules', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.project.name})"