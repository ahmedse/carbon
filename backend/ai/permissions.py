"""DRF permission classes for the Pulse AI app (P3-05b).

The AI console is a read-only surface for the governance/audit roles. The
permission class below is the single place that maps the ``ai:view_console``
capability to a DRF permission; it uses ``has_capability`` from
``accounts.capabilities`` (the CBAC single source of truth) and permits
``SAFE_METHODS`` only.
"""

from rest_framework import permissions

from accounts.capabilities import AI_VIEW_CONSOLE, has_capability


class AIViewConsolePermission(permissions.BasePermission):
    """View-only access to the AI console via ``ai:view_console``.

    Permits GET/HEAD/OPTIONS for authenticated holders of ``ai:view_console``
    (superusers and global admins pass via ``has_capability``'s ``"*"``
    wildcard). Refuses every write method (POST/PUT/PATCH/DELETE) — the console
    is a read-only surface and this capability must NOT imply any write.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        # Refuse all writes before checking the capability: even a superuser
        # cannot POST/PUT/PATCH/DELETE through a view-only console surface.
        if request.method not in permissions.SAFE_METHODS:
            return False
        return has_capability(user, AI_VIEW_CONSOLE.key)
