"""TurnKey Bridge permission classes.

The canonical capability permission classes live in ``accounts.permissions``
(``AdminOrSuperuserOnly`` = one capability for ALL methods, ``ReadAnyWriteAdmin``
= any authenticated read). The TurnKey link collection needs *split*
capabilities — §6.6 requires reads gated on ``turnkey:view`` and writes gated
on ``turnkey:manage`` — so this app declares one small composite class that
reuses the shared capability resolution from ``accounts.permissions``.
"""
from rest_framework import permissions

from accounts.permissions import _check_write_capability


class TurnKeyReadViewWriteManage(permissions.BasePermission):
    """Reads require the view's ``required_capability`` (turnkey:view);
    writes require ``required_write_capability`` (turnkey:manage).

    Superusers and global admins always pass (same bypass as
    AdminOrSuperuserOnly via the shared _check_write_capability).
    """
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if request.method in permissions.SAFE_METHODS:
            capability = getattr(view, 'required_capability', None) \
                or getattr(view, 'required_write_capability', None)
        else:
            capability = getattr(view, 'required_write_capability', None) \
                or getattr(view, 'required_capability', None)
        if capability is None:
            return False

        # Reuse the canonical resolution (superuser / global-admin bypass +
        # has_capability / has_any_capability) via a minimal view shim.
        return _check_write_capability(user, _CapabilityShim(capability))


class _CapabilityShim:
    """Minimal view stand-in exposing the capability attributes the shared
    ``_check_write_capability`` resolver reads off the view."""

    def __init__(self, capability):
        self.required_capability = capability
        self.required_write_capability = capability

