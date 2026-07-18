# File: backend/evidence/permissions.py
from rest_framework import permissions
from accounts.rbac_utils import get_allowed_module_ids, user_is_global_admin
from dataschema.models import DataRow


class IsEvidenceOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to access evidence:
    - User can access evidence for rows in their assigned modules
    - Admins can access all evidence
    """
    
    def has_permission(self, request, view):
        """Allow authenticated users to access evidence."""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user can access this specific evidence."""
        user = request.user
        
        # Admins can access all evidence
        if user_is_global_admin(user):
            return True
        
        # Users can access evidence for rows in their assigned modules
        data_row = obj.data_row
        module_id = data_row.data_table.module.id
        
        # Check if user has access to this module
        allowed_modules = get_allowed_module_ids(user, roles=['dataowners_group', 'auditors_group', 'admins_group'])
        return module_id in allowed_modules
