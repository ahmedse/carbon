# File: backend/dataschema/permissions.py
"""
CBAC-aware scoped permission for dataschema views.

Reads:  org-scoped — delegates to the HasScopedRole read logic, which resolves
        module/org-unit access via the view's `required_role` (unchanged
        behaviour; org-scoped users keep module-level read scoping).
Writes: capability-gated — resolved by accounts._check_write_capability via the
        view's `required_write_capability` / `required_capability`
        (superuser -> global admin -> capability -> legacy domain_lead_groups).
"""
from rest_framework import permissions

from accounts.permissions import HasScopedRole, _check_write_capability


class ScopedReadCapabilityWrite(permissions.BasePermission):
    """Org-scoped reads + capability-gated writes for dataschema viewsets.

    Writes require BOTH:
      - the view's declared capability (e.g. carbon:enter_data), AND
      - the org/module scope check (HasScopedRole write logic), so a
        capability holder cannot write rows/tables in modules outside their
        org-unit scope. Superusers/global admins pass the scope check.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return HasScopedRole().has_permission(request, view)
        return (
            _check_write_capability(user, view)
            and HasScopedRole().has_permission(request, view)
        )
