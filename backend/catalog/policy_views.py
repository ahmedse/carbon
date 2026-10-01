# Policy desk HTTP. Lists and publishes through the domain-free lifecycle.
# Capability catalog:manage_policies is the existing Data Trust grant
# (admin wildcard and catalog_lead). people_lead does not hold it.

from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.capabilities import has_capability

from .policy_lifecycle import (
    PolicyTransitionError,
    detail,
    list_versions,
    locate,
    publish,
    submit,
    to_public,
)


class PolicyDeskAccess(BasePermission):
    """Administer the policy desk.

    ``catalog:manage_policies`` already means manage Data Trust governance
    policies. Superusers and global ``admin`` / ``admins_group`` receive it
    through the wildcard. ``catalog_lead`` holds it. ``people_lead`` does not.
    """

    message = "Policy desk requires catalog:manage_policies."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return has_capability(user, "catalog:manage_policies")


def _error_response(exc):
    if isinstance(exc, PolicyTransitionError):
        body = {"detail": str(exc), "code": exc.code}
        if exc.errors:
            body["errors"] = exc.errors
        return Response(body, status=exc.status_code)
    code = getattr(exc, "code", None)
    if code and str(code).startswith("sod_"):
        return Response(
            {"detail": str(exc), "code": code},
            status=status.HTTP_403_FORBIDDEN,
        )
    raise exc


class PolicyVersionListView(APIView):
    permission_classes = [IsAuthenticated, PolicyDeskAccess]

    def get(self, request):
        state = (request.query_params.get("state") or "").strip()
        query = (request.query_params.get("q") or "").strip()
        rows = list_versions(state=state, query=query)
        return Response({"count": len(rows), "results": rows})


class PolicyVersionDetailView(APIView):
    permission_classes = [IsAuthenticated, PolicyDeskAccess]

    def get(self, request, pk):
        body = detail(pk)
        if body is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(body)


class PolicyVersionSubmitView(APIView):
    permission_classes = [IsAuthenticated, PolicyDeskAccess]

    def post(self, request, pk):
        plane, row = locate(pk)
        if row is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            row = submit(plane, row, request.user)
        except Exception as exc:  # noqa: BLE001 — mapped below
            return _error_response(exc)
        return Response(to_public(plane, row))


class PolicyVersionPublishView(APIView):
    permission_classes = [IsAuthenticated, PolicyDeskAccess]

    def post(self, request, pk):
        plane, row = locate(pk)
        if row is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            row = publish(plane, row, request.user)
        except Exception as exc:  # noqa: BLE001 — mapped below
            return _error_response(exc)
        return Response(to_public(plane, row))
