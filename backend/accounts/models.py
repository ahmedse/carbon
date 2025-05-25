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
from django.db.models import Q, signals
from django.dispatch import receiver

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

    def eligible_users_for_role(self, role_name):
        """
        Returns a queryset of users eligible for a given role in this context.
        This includes direct assignments at this context and parent contexts.
        """
        # Find the role object
        try:
            role = Role.objects.get(name=role_name)
        except Role.DoesNotExist:
            return User.objects.none()

        # Build Q objects for parent contexts based on context type
        q = Q(role=role, context=self)
        if self.type == 'module':
            if self.cycle:
                q |= Q(role=role, context__type='cycle', context__cycle=self.cycle)
            if self.project:
                q |= Q(role=role, context__type='project', context__project=self.project)
            q |= Q(role=role, context__type='global')
        elif self.type == 'cycle':
            if self.project:
                q |= Q(role=role, context__type='project', context__project=self.project)
            q |= Q(role=role, context__type='global')
        elif self.type == 'project':
            q |= Q(role=role, context__type='global')
        elif self.type == 'global':
            pass  # only itself

        # Collect users from matching RoleAssignments
        user_ids = RoleAssignment.objects.filter(q).values_list('user_id', flat=True).distinct()
        return User.objects.filter(id__in=user_ids)

    def list_role_assignments(self):
        """
        Returns a queryset of all role assignments in this context.
        """
        return RoleAssignment.objects.filter(context=self)

    def list_roles(self):
        """
        Returns all roles assigned in this context.
        """
        return Role.objects.filter(roleassignment__context=self).distinct()

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

# --- Optional: Signals for assignment integrity ---

@receiver(signals.post_delete, sender=RoleAssignment)
def cleanup_empty_contexts(sender, instance, **kwargs):
    """
    Optionally delete a context if it has no assignments and is not referenced elsewhere.
    Adjust this behavior to fit your data retention policy.
    """
    context = instance.context
    # Only delete if context is not global and has no remaining assignments
    if context.type != 'global' and not RoleAssignment.objects.filter(context=context).exists():
        # If you want to ensure the context isn't referenced elsewhere, check related models as needed.
        context.delete()