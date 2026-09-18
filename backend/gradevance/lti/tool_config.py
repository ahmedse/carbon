"""LMS-facing tool configuration document (registration helper)."""
from __future__ import annotations

from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from gradevance.lti.oidc import lti_config, lti_ready


class LtiToolConfigView(APIView):
    """Public JSON describing how to register GradeVance as an LTI 1.3 tool."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        cfg = lti_config()
        ready, reason = lti_ready(cfg)
        base = request.build_absolute_uri("/").rstrip("/")
        # Prefer API root under /api/v1/gradevance/
        api = f"{base}/api/v1/gradevance"
        return Response(
            {
                "ready": ready,
                "reason": reason,
                "application_type": "lti_1_3_tool",
                "client_name": "GradeVance",
                "initiate_login_uri": f"{api}/lti/oidc/login/",
                "redirect_uris": [cfg.get("redirect_uri") or f"{api}/lti/oidc/launch/"],
                "jwks_uri": f"{api}/lti/jwks/",
                "target_link_uri": cfg.get("redirect_uri") or f"{api}/lti/oidc/launch/",
                "scopes": [
                    "openid",
                    "https://purl.imsglobal.org/spec/lti-ags/scope/score",
                    "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem",
                    "https://purl.imsglobal.org/spec/lti-nrps/scope/contextmembership.readonly",
                ],
                "https://purl.imsglobal.org/spec/lti-tool-configuration": {
                    "domain": request.get_host(),
                    "description": "Multi-domain assessment & coaching under HITL",
                    "target_link_uri": cfg.get("redirect_uri") or f"{api}/lti/oidc/launch/",
                    "claims": ["iss", "sub", "name", "email", "https://purl.imsglobal.org/spec/lti/claim/roles"],
                },
                "notes": [
                    "Set GRADEVANCE_LTI_* env vars before enabling in LMS.",
                    "AGS passback defaults to dry-run until GRADEVANCE_LTI_AGS_DRY_RUN=false.",
                    f"Tool key present: {bool(getattr(settings, 'GRADEVANCE_LTI_TOOL_PRIVATE_KEY_PEM', ''))}",
                ],
            }
        )
