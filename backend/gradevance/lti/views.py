from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from gradevance.lti import map_lti_roles_to_capabilities
from gradevance.lti.oidc import lti_config, lti_ready
from gradevance.permissions import GradevanceManageAccess


class LtiStatusView(APIView):
    """Readiness probe for LTI integration."""

    permission_classes = [IsAuthenticated, GradevanceManageAccess]

    def get(self, request):
        cfg = lti_config()
        ready, reason = lti_ready(cfg)
        return Response(
            {
                "status": "ready" if ready else "scaffold",
                "ready": ready,
                "reason": reason,
                "advantage": ["oidc_login", "deep_linking", "ags", "nrps"],
                "endpoints": {
                    "login": "/api/v1/gradevance/lti/oidc/login/",
                    "launch": "/api/v1/gradevance/lti/oidc/launch/",
                    "config": "/api/v1/gradevance/lti/config/",
                    "deep_link_preview": "/api/v1/gradevance/lti/deep-link/preview/",
                    "nrps_preview": "/api/v1/gradevance/lti/nrps/preview/",
                },
                "note": (
                    "OIDC+JWKS verify + User/ScopedRole provision on launch. "
                    "AGS passback via /runs/<id>/ags-passback/ (dry-run default)."
                ),
                "ags": {
                    "dry_run": bool(getattr(settings, "GRADEVANCE_LTI_AGS_DRY_RUN", True)),
                    "token_url_set": bool(getattr(settings, "GRADEVANCE_LTI_TOKEN_URL", "")),
                    "passback": "/api/v1/gradevance/runs/<id>/ags-passback/",
                    "preview": "/api/v1/gradevance/runs/<id>/ags-preview/",
                },
                "role_map_example": sorted(
                    map_lti_roles_to_capabilities(("Instructor", "Learner"))
                ),
            }
        )
