# mdm/permissions.py
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.exceptions import PermissionDenied
from accounts.models import ScopedRole
from accounts.permissions import ReadAnyWriteAdmin  # canonical
from accounts.rbac_utils import user_has_global_role
from accounts.constants import ADMINS_GROUP
from accounts.capabilities import has_capability, MDM_MANAGE

__all__ = [
    'ReadAnyWriteAdmin', 'IsReferenceSetSteward', 'IsOrgUnitAdmin',
    'CanManageReferenceValues',
]


def _is_admin(user):
    """True for superusers, staff, or global admins (admins_group)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user_has_global_role(user, [ADMINS_GROUP])


class CanManageReferenceValues(BasePermission):
    """
    Write access to ReferenceValue rows for the steward of the owning set.

    - Read: any authenticated user (values are shared reference data)
    - Create/update/delete via the generic reference-values endpoints:
      allowed when the caller is the steward of the value's reference_set,
      a staff member, or a global admin.

    This mirrors the object-level guard used by the set-level `add_value`
    action so the Values tab works identically for stewards.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if _is_admin(user):
            return True
        # CBAC layer-1: an mdm:manage capability holder (e.g. mdm_lead) may
        # manage values platform-wide; the owner/steward check remains layer-2.
        if has_capability(user, MDM_MANAGE.key):
            return True

        # For writes we must resolve the owning set: from the payload for
        # create, or from the object for update/delete (checked in
        # has_object_permission).
        if request.method == 'POST':
            set_id = request.data.get('reference_set')
            if not set_id:
                return False
            from .models import ReferenceSet
            return ReferenceSet.objects.filter(
                pk=set_id, steward=user
            ).exists()
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if _is_admin(user):
            return True
        if has_capability(user, MDM_MANAGE.key):
            return True
        return obj.reference_set.steward_id == user.id


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
