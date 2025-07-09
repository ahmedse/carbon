# File: accounts/models.py
# Production-ready multi-tenant RBAC models for SaaS with scoped project/module roles.

from django.db import models
from django.contrib.auth.models import AbstractUser, Group
from django.core.exceptions import ValidationError
from django.utils import timezone

# --- TENANT ---

class Tenant(models.Model):
    """
    Each customer organization in the SaaS system.
    """
    name = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# --- USER ---

class User(AbstractUser):
    """
    Custom user model linked to a tenant.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, default=0, related_name="users")

    def __str__(self):
        return f"{self.username} ({self.tenant.name})"

# --- SCOPED ROLE ASSIGNMENT ---

class ScopedRole(models.Model):
    """
    Assigns a role (Group) to a user for a specific tenant/project/module scope.
    - If project/module are null, role applies at tenant level.
    - If project is set and module is null: project-level role.
    - If module is set: module-level role (project auto-inferred).
    Enforces tenant isolation.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="scoped_roles")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="scoped_roles")  # Role
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="scoped_roles")
    project = models.ForeignKey(
        "core.Project", null=True, blank=True, on_delete=models.CASCADE, related_name="scoped_roles"
    )
    module = models.ForeignKey(
        "core.Module", null=True, blank=True, on_delete=models.CASCADE, related_name="scoped_roles"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "group", "tenant", "project", "module")
        verbose_name = "Scoped Role Assignment"
        verbose_name_plural = "Scoped Role Assignments"

    def __str__(self):
        scope = []
        if self.project:
            scope.append(f"Project:{self.project}")
        if self.module:
            scope.append(f"Module:{self.module}")
        return f"{self.user} as {self.group.name} in {'/'.join(scope) or self.tenant.name}"

    def clean(self):
        # Enforce tenant consistency
        if self.project and self.project.tenant_id != self.tenant_id:
            raise ValidationError("Project must belong to the same tenant as the assignment.")
        if self.module and self.module.project.tenant_id != self.tenant_id:
            raise ValidationError("Module must belong to the same tenant as the assignment.")

# --- AUDIT LOGGING ---

class RoleAssignmentAuditLog(models.Model):
    """
    Audit log for all scoped role assignments.
    """
    ACTIONS = (
        ("assigned", "Assigned"),
        ("removed", "Removed"),
        ("modified", "Modified"),
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="role_audit_logs")
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="role_audit_actions")
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True)
    project = models.ForeignKey("core.Project", null=True, blank=True, on_delete=models.SET_NULL)
    module = models.ForeignKey("core.Module", null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=16, choices=ACTIONS)
    timestamp = models.DateTimeField(default=timezone.now)
    extra = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.timestamp}: {self.action} {self.group} for {self.user} ({self.tenant})"

# --- SYSTEM ROLE NAMES (constants for code clarity) ---

SYSTEM_ROLES = {
    "admin": "admin",
    "audit": "audit",
    "dataowner": "dataowner",
}