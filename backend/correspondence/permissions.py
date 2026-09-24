"""CBAC permissions for the Correspondence engine API (Phase OF-7).

Single source of truth is ``accounts.capabilities.has_capability`` — no group
names or permission strings are hardcoded here.
"""

from rest_framework.permissions import BasePermission

from accounts.capabilities import has_capability

from .models import ACTOR_HISTORY_EVENTS


class CanSubmitCorrespondence(BasePermission):
    """Only users holding ``correspondence:submit`` may create correspondence."""

    message = "You do not have permission to submit correspondence."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and has_capability(request.user, 'correspondence:submit')
        )


class CanActOnCorrespondence(BasePermission):
    """Only a user on the current policy step may approve, reject, or send back.

    ``correspondence:admin`` may view every request and may void or reopen a
    finished one. That capability does not make them the approver of an open step.
    """

    message = "You are not the current approver for this correspondence."

    def has_object_permission(self, request, view, obj):
        uid = request.user.id
        return uid in (obj.current_approver_ids or [])


class CanViewCorrespondence(BasePermission):
    """Requester, current approver, past decision actor, or ``correspondence:admin``."""

    message = "You do not have permission to view this correspondence."

    def has_object_permission(self, request, view, obj):
        if has_capability(request.user, 'correspondence:admin'):
            return True
        uid = request.user.id
        if obj.requester_id == uid or uid in (obj.current_approver_ids or []):
            return True
        # Team History: manager who already decided must still open the record.
        return obj.events.filter(
            actor_id=uid,
            event_type__in=ACTOR_HISTORY_EVENTS,
        ).exists()


class CanRequesterMutateCorrespondence(BasePermission):
    """Requester-only mutations: cancel, resubmit, edit payload.

    ``archive`` stays on ``CanViewCorrespondence`` because FSM also allows
    ``correspondence:admin``.
    """

    message = "Only the requester may perform this action on the request."

    def has_object_permission(self, request, view, obj):
        return bool(
            request.user
            and request.user.is_authenticated
            and obj.requester_id == request.user.id
        )


class CorrespondenceAdminOnly(BasePermission):
    """Policy endpoints require the ``correspondence:admin`` capability."""

    message = "You do not have permission to manage correspondence policies."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and has_capability(request.user, 'correspondence:admin')
        )
