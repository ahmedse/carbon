"""CBAC permissions for the Correspondence engine API (Phase OF-7).

Single source of truth is ``accounts.capabilities.has_capability`` — no group
names or permission strings are hardcoded here.
"""

from rest_framework.permissions import BasePermission

from accounts.capabilities import has_capability


class CanActOnCorrespondence(BasePermission):
    """Only the current approver (or a ``correspondence:admin``) may act."""

    message = "You are not the current approver for this correspondence."

    def has_object_permission(self, request, view, obj):
        if has_capability(request.user, 'correspondence:admin'):
            return True
        uid = request.user.id
        return uid in (obj.current_approver_ids or [])


class CanViewCorrespondence(BasePermission):
    """Requester-or-admin: the requester themselves, or a ``correspondence:admin``."""

    message = "You do not have permission to view this correspondence."

    def has_object_permission(self, request, view, obj):
        if has_capability(request.user, 'correspondence:admin'):
            return True
        uid = request.user.id
        return obj.requester_id == uid or uid in (obj.current_approver_ids or [])


class CorrespondenceAdminOnly(BasePermission):
    """Policy endpoints require the ``correspondence:admin`` capability."""

    message = "You do not have permission to manage correspondence policies."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and has_capability(request.user, 'correspondence:admin')
        )
