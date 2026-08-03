# mdm/permissions.py
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.exceptions import PermissionDenied
from accounts.models import ScopedRole
from accounts.permissions import ReadAnyWriteAdmin  # canonical

__all__ = ['ReadAnyWriteAdmin', 'IsReferenceSetSteward', 'IsOrgUnitAdmin']


class IsReferenceSetSteward(BasePermission):
    """
    Only steward of ReferenceSet can edit it.
    Read permissions allowed to any authenticated user in same org_unit scope.
    Write permissions only to steward or admin.
    """
    
    def has_object_permission(self, request, view, obj):
        """Check if user can access this ReferenceSet object."""
        user = request.user
        
        if not user or not user.is_authenticated:
            return False
        
        # Superusers/staff can do anything
        if user.is_superuser or user.is_staff:
            return True
        
        # Read: any authenticated user in the same org_unit scope
        if request.method in SAFE_METHODS:
            # Check if user has access to this org_unit through ScopedRole
            if obj.domain and obj.domain.id:
                user_org_units = ScopedRole.objects.filter(
                    user=user, is_active=True
                ).values_list('org_unit_id', flat=True).distinct()
                return obj.domain.id in user_org_units
            return True
        
        # Write: only steward or admin
        return obj.steward == user


class IsOrgUnitAdmin(BasePermission):
    """
    Only global admins or org unit admins can write org units.
    Any authenticated user can read.
    """
    
    def has_permission(self, request, view):
        """Check if user can access org unit endpoints."""
        user = request.user
        
        if not user or not user.is_authenticated:
            return False
        
        # Read: any authenticated user
        if request.method in SAFE_METHODS:
            return True
        
        # Write: superusers/staff only
        return user.is_superuser or user.is_staff
