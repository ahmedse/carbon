# File: accounts/models.py
# Purpose: Defines database models for the RBAC (Role-Based Access Control) system.
#
# Models:
# - User: Custom user model extending AbstractUser.
# - Role: Represents a named role with a set of permissions.
# - Context: Represents a scope (global, project, cycle, module) for RBAC assignments.
# - RoleAssignment: Assignment of a role to a user within a context.

from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """
    Custom user model for the application.
    Role-based access control is managed via RoleAssignment.
    """
    pass

class Role(models.Model):
    """
    Represents a role with a name, optional description, and a list of permissions.
    """
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=list)  # e.g. ["add_data", "view_dashboard"]

    def __str__(self):
        """Return the string representation of the role."""
        return self.name

class Context(models.Model):
    """
    Represents a context for RBAC assignments, such as global, project, cycle, or module.
    """
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
        """
        Return a detailed string representation of the context, including related objects.
        """
        parts = [self.type]
        if self.project: parts.append(f"Project:{self.project}")
        if self.cycle: parts.append(f"Cycle:{self.cycle}")
        if self.module: parts.append(f"Module:{self.module}")
        return ' / '.join(parts)

class RoleAssignment(models.Model):
    """
    Associates a user with a role within a specific context.
    Ensures unique assignment per user, role, and context.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='role_assignments')
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    context = models.ForeignKey(Context, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'role', 'context')

    def __str__(self):
        """Return a readable description of the role assignment."""
        return f"{self.user} as {self.role} in {self.context}"