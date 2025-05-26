# File: accounts/models.py
# Purpose: Robust multi-tenant RBAC models for Carbon Platform, referencing core business models.

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import Q, signals
from django.dispatch import receiver

from core.models import Project, Module  # <-- Import only; do not redefine

# --- Tenant Model ---
class Tenant(models.Model):
    """
    Represents a customer (tenant) in the multi-tenant system.
    """
    name = models.CharField(max_length=128, unique=True)

    def __str__(self):
        return self.name

# --- User Model ---
class User(AbstractUser):
    """
    Custom user model for the application, linked to a tenant.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.username

# --- Role Model ---
class Role(models.Model):
    """
    Represents a role with a name, optional description, and a list of permissions.
    """
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=list)  # e.g. ["manage_project", "view_all_data"]

    def __str__(self):
        return self.name

# --- Context Model (project/module only) ---
class Context(models.Model):
    """
    Represents a context for RBAC assignments, either a project or a module.
    """
    CONTEXT_TYPES = [
        ('project', 'Project'),
        ('module', 'Module'),
    ]
    type = models.CharField(max_length=10, choices=CONTEXT_TYPES)
    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        parts = [self.type]
        if self.project: parts.append(f"Project:{self.project}")
        if self.module: parts.append(f"Module:{self.module}")
        return ' / '.join(parts)

    def eligible_users_for_role(self, role_name):
        try:
            role = Role.objects.get(name=role_name)
        except Role.DoesNotExist:
            return User.objects.none()
        q = Q(role=role, context=self)
        if self.type == 'module':
            if self.project:
                q |= Q(role=role, context__type='project', context__project=self.project)
        elif self.type == 'project':
            pass  # only itself
        user_ids = RoleAssignment.objects.filter(q).values_list('user_id', flat=True).distinct()
        return User.objects.filter(id__in=user_ids)

    def list_role_assignments(self):
        return RoleAssignment.objects.filter(context=self)

    def list_roles(self):
        return Role.objects.filter(roleassignment__context=self).distinct()

# --- RoleAssignment Model ---
class RoleAssignment(models.Model):
    """
    Associates a user with a role within a specific context (project/module).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='role_assignments')
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    context = models.ForeignKey(Context, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'role', 'context')

    def __str__(self):
        return f"{self.user} as {self.role} in {self.context}"

# --- Signals for cleanup (optional) ---
@receiver(signals.post_delete, sender=RoleAssignment)
def cleanup_empty_contexts(sender, instance, **kwargs):
    context = instance.context
    # Only delete if context has no remaining assignments
    if not RoleAssignment.objects.filter(context=context).exists():
        context.delete()