from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    pass  # RBAC handled via RoleAssignment

class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=list)  # e.g. ["add_data", "view_dashboard"]

    def __str__(self):
        return self.name

class Context(models.Model):
    CONTEXT_TYPES = [
        ('global', 'Global'),
        ('project', 'Project'),
        ('cycle', 'Cycle'),
        ('module', 'Module'),
    ]
    type = models.CharField(max_length=10, choices=CONTEXT_TYPES)
    project = models.ForeignKey('core.Project', null=True, blank=True, on_delete=models.CASCADE)
    cycle = models.ForeignKey('core.Cycle', null=True, blank=True, on_delete=models.CASCADE)
    module = models.ForeignKey('core.Module', null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        parts = [self.type]
        if self.project: parts.append(f"Project:{self.project}")
        if self.cycle: parts.append(f"Cycle:{self.cycle}")
        if self.module: parts.append(f"Module:{self.module}")
        return ' / '.join(parts)

class RoleAssignment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='role_assignments')
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    context = models.ForeignKey(Context, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'role', 'context')

    def __str__(self):
        return f"{self.user} as {self.role} in {self.context}"