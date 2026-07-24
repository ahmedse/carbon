# File: accounts/models.py
# Production-ready RBAC models with scoped project/module roles.

from django.db import models
from django.contrib.auth.models import AbstractUser, Group
from django.core.exceptions import ValidationError
from django.utils import timezone

# --- USER ---

class User(AbstractUser):
    """
    Custom user model.
    """

    def __str__(self):
        return self.username

# --- SCOPED ROLE ASSIGNMENT ---

class ScopedRole(models.Model):
    """
    Assigns a role (Group) to a user for a specific org-unit/module scope.
    - If org_unit/module are null, role applies globally.
    - If org_unit is set and module is null: org-unit-level role.
    - If module is set: module-level role (org_unit optional).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="scoped_roles")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="scoped_roles")
    org_unit = models.ForeignKey(
        "mdm.OrgUnit", null=True, blank=True, on_delete=models.CASCADE, related_name="scoped_roles"
    )
    module = models.ForeignKey(
        "core.Module", null=True, blank=True, on_delete=models.CASCADE, related_name="scoped_roles"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "group", "org_unit", "module")
        verbose_name = "Scoped Role Assignment"
        verbose_name_plural = "Scoped Role Assignments"

    def __str__(self):
        scope = []
        if self.org_unit:
            scope.append(f"OrgUnit:{self.org_unit}")
        if self.module:
            scope.append(f"Module:{self.module}")
        return f"{self.user} as {self.group.name} in {'/'.join(scope) or 'global'}"

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
    org_unit = models.ForeignKey("mdm.OrgUnit", null=True, blank=True, on_delete=models.SET_NULL)
    module = models.ForeignKey("core.Module", null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=16, choices=ACTIONS)
    timestamp = models.DateTimeField(default=timezone.now)
    extra = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.timestamp}: {self.action} {self.group} for {self.user}"


class GroupMetadata(models.Model):
    """Extended metadata for Django Group role definitions."""

    CATEGORY_CHOICES = [
        ('platform', 'Platform'),
        ('app', 'App'),
    ]

    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='metadata')
    description = models.TextField(blank=True, default='')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='app')
    app_id = models.CharField(max_length=50, blank=True, default='')
    manifest_key = models.CharField(max_length=100, blank=True, default='')
    is_scoped = models.BooleanField(default=False)
    is_protected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Group Metadata'
        verbose_name_plural = 'Group Metadata'

    def __str__(self):
        return f"Metadata for {self.group.name}"


# --- SYSTEM ROLE NAMES (constants for code clarity) ---

SYSTEM_ROLES = {
    "admin": "admin",
    "audit": "audit",
    "dataowner": "dataowner",
}