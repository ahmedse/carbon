"""NRPS roster preview API — dry-run by default."""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from gradevance.lti.ags import AgsPassbackError
from gradevance.lti.nrps import fetch_nrps_membership
from gradevance.lti.roster_sync import sync_nrps_members_to_users
from gradevance.permissions import GradevanceManageAccess


class NrpsRosterPreviewView(APIView):
    """POST {memberships_url, dry_run?} → parsed members (or dry-run empty).

    Optional ``sync: true`` + ``iss`` + ``deployment_id`` provisions Users.
    """

    permission_classes = [IsAuthenticated, GradevanceManageAccess]

    def post(self, request):
        url = (request.data.get("memberships_url") or "").strip()
        if not url:
            return Response({"detail": "memberships_url required"}, status=400)
        dry = request.data.get("dry_run")
        dry_run = None if dry is None else bool(dry)
        try:
            result = fetch_nrps_membership(memberships_url=url, dry_run=dry_run)
        except AgsPassbackError as exc:
            return Response({"detail": str(exc)}, status=400)

        sync_info = None
        if request.data.get("sync") and result.ok and result.members:
            iss = (request.data.get("iss") or "").strip()
            dep = (request.data.get("deployment_id") or "").strip() or "default"
            if not iss:
                return Response({"detail": "iss required when sync=true"}, status=400)
            synced = sync_nrps_members_to_users(
                iss=iss, deployment_id=dep, members=result.members
            )
            sync_info = {
                "created": synced.created,
                "existing": synced.existing,
                "usernames": synced.usernames,
            }

        return Response(
            {
                "dry_run": result.dry_run,
                "ok": result.ok,
                "url": result.url,
                "member_count": len(result.members),
                "members": result.members,
                "sync": sync_info,
                "error": result.error or None,
                "note": "Map user_id → Submission.external_student_key; never store raw PII as SoR key.",
            }
        )
