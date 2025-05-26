# File: accounts/permissions.py
# Purpose: Custom permission class for RBAC enforcement in DRF views.

from rest_framework.permissions import BasePermission
from .utils import user_has_permission
from .models import Context

class HasRBACPermission(BasePermission):
    def has_permission(self, request, view):
        print("=== HasRBACPermission Debug ===")
        print(f"User: {request.user} (Authenticated: {request.user.is_authenticated})")

        if not request.user.is_authenticated:
            print("DENY: User is not authenticated.")
            return False

        required_permission = getattr(view, 'required_permission', None)
        print(f"Required permission: {required_permission}")

        if not required_permission:
            print("ALLOW: No required_permission set on view.")
            return True  # No RBAC specified

        # Check if get_context exists, otherwise fallback
        if hasattr(view, 'get_context'):
            context = view.get_context(request)
            print("Context obtained using get_context.")
        elif hasattr(view, 'get_context_from_request'):
            context = view.get_context_from_request(request)
            print("Context obtained using get_context_from_request.")
        else:
            context = None
            print("DENY: No context method found on view.")
        
        print(f"Context: {context}")

        if not context:
            print("DENY: No context available.")
            return False

        has_perm = user_has_permission(request.user, required_permission, context)
        print(f"User has permission '{required_permission}' for context {context}: {has_perm}")

        if not has_perm:
            print("DENY: User does not have the required permission.")
            return False

        print("ALLOW: User authorized.\n")
        return True