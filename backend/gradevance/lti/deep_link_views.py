"""Deep Linking API — build content-item + unsigned JWT claims for LMS return."""
from __future__ import annotations

from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from gradevance.lti.deep_link import deep_link_assignment_content_item, deep_link_jwt_claims
from gradevance.lti.deep_link_sign import DeepLinkSignError, sign_deep_link_jwt, tool_private_key_pem
from gradevance.lti.oidc import lti_config
from gradevance.models import Assignment
from gradevance.permissions import GradevanceManageAccess


class DeepLinkPreviewView(APIView):
    """POST {assignment_id, return_url?, data?, sign?} → content item + claims (+ JWT if key set)."""

    permission_classes = [IsAuthenticated, GradevanceManageAccess]

    def post(self, request):
        assignment_id = request.data.get("assignment_id") or ""
        if not assignment_id:
            return Response({"detail": "assignment_id required"}, status=400)
        try:
            asg = Assignment.objects.get(pk=assignment_id)
        except (Assignment.DoesNotExist, ValueError):
            return Response({"detail": "Assignment not found"}, status=404)

        cfg = lti_config()
        base = getattr(settings, "FRONTEND_BASE_URL", "") or "https://eduos.example"
        url = (
            request.data.get("return_url")
            or f"{base.rstrip('/')}/apps/gradevance/student?assignment={asg.id}"
        )
        item = deep_link_assignment_content_item(
            title=asg.title,
            url=url,
            assignment_id=str(asg.id),
            profile_pack_id=asg.profile_pack_id,
        )
        claims = deep_link_jwt_claims(
            iss=cfg.get("client_id") or "gradevance",
            aud=cfg.get("issuer") or "https://lms.example",
            deployment_id=(cfg.get("deployment_ids") or ["default"])[0],
            data=request.data.get("data"),
            content_items=[item],
        )
        signed = None
        sign_error = None
        want_sign = bool(request.data.get("sign")) or bool(tool_private_key_pem())
        if want_sign:
            try:
                signed = sign_deep_link_jwt(claims)
            except DeepLinkSignError as exc:
                sign_error = str(exc)
        return Response(
            {
                "content_item": item,
                "jwt_claims": claims,
                "jwt": signed,
                "signed": bool(signed),
                "sign_error": sign_error,
                "note": (
                    "JWT signed with tool private key."
                    if signed
                    else "Set GRADEVANCE_LTI_TOOL_PRIVATE_KEY_PEM (or pass sign=true once configured) to return jwt."
                ),
            }
        )
