"""LTI 1.3 OIDC login initiation + launch callback scaffold.

Production: configure GRADEVANCE_LTI_* settings (or instance YAML). Until then
endpoints return structured 503 with setup instructions — no silent accept.
"""
from __future__ import annotations

import secrets
from dataclasses import asdict
from typing import Any
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from gradevance.lti import LtiLaunchContext, map_lti_roles_to_capabilities
from gradevance.permissions import GradevanceManageAccess

_STATE_TTL = 600
_STATE_PREFIX = "gradevance:lti:state:"


def lti_config() -> dict[str, Any]:
    return {
        "enabled": bool(getattr(settings, "GRADEVANCE_LTI_ENABLED", False)),
        "issuer": getattr(settings, "GRADEVANCE_LTI_ISSUER", "") or "",
        "client_id": getattr(settings, "GRADEVANCE_LTI_CLIENT_ID", "") or "",
        "auth_login_url": getattr(settings, "GRADEVANCE_LTI_AUTH_LOGIN_URL", "") or "",
        "jwks_url": getattr(settings, "GRADEVANCE_LTI_JWKS_URL", "") or "",
        "redirect_uri": getattr(settings, "GRADEVANCE_LTI_REDIRECT_URI", "") or "",
        "deployment_ids": list(getattr(settings, "GRADEVANCE_LTI_DEPLOYMENT_IDS", []) or []),
    }


def lti_ready(cfg: dict[str, Any] | None = None) -> tuple[bool, str]:
    cfg = cfg or lti_config()
    if not cfg["enabled"]:
        return False, "GRADEVANCE_LTI_ENABLED is false"
    missing = [
        k
        for k in ("issuer", "client_id", "auth_login_url", "jwks_url", "redirect_uri")
        if not cfg.get(k)
    ]
    if missing:
        return False, f"Missing LTI settings: {', '.join(missing)}"
    return True, "ok"


class LtiOidcLoginView(APIView):
    """Tool login initiation — LMS redirects here; we bounce to platform auth."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return self._initiate(request.GET)

    def post(self, request):
        data = request.POST if request.POST else (request.data or {})
        return self._initiate(data)

    def _initiate(self, params):
        cfg = lti_config()
        ready, reason = lti_ready(cfg)
        if not ready:
            return Response(
                {
                    "detail": "LTI not configured",
                    "reason": reason,
                    "setup": [
                        "Set GRADEVANCE_LTI_ENABLED=true",
                        "Set issuer, client_id, auth_login_url, jwks_url, redirect_uri",
                    ],
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        iss = params.get("iss") or ""
        login_hint = params.get("login_hint") or ""
        target_link = params.get("target_link_uri") or cfg["redirect_uri"]
        client_id = params.get("client_id") or cfg["client_id"]
        lti_message_hint = params.get("lti_message_hint") or ""
        lti_deployment_id = params.get("lti_deployment_id") or ""

        if iss and cfg["issuer"] and iss != cfg["issuer"]:
            return Response({"detail": f"Unknown issuer: {iss}"}, status=400)

        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)
        cache.set(
            f"{_STATE_PREFIX}{state}",
            {
                "nonce": nonce,
                "iss": iss or cfg["issuer"],
                "client_id": client_id,
                "deployment_id": lti_deployment_id,
                "target_link_uri": target_link,
            },
            _STATE_TTL,
        )

        query = {
            "scope": "openid",
            "response_type": "id_token",
            "response_mode": "form_post",
            "client_id": client_id,
            "redirect_uri": cfg["redirect_uri"],
            "login_hint": login_hint,
            "state": state,
            "nonce": nonce,
            "prompt": "none",
        }
        if lti_message_hint:
            query["lti_message_hint"] = lti_message_hint
        if lti_deployment_id:
            query["lti_deployment_id"] = lti_deployment_id

        auth_url = f"{cfg['auth_login_url']}?{urlencode(query)}"
        return Response(
            {
                "status": "redirect",
                "authorization_url": auth_url,
                "state": state,
                "note": "Browser should navigate to authorization_url (form_post expected on callback).",
            }
        )


class LtiOidcLaunchView(APIView):
    """OIDC callback — validates state/nonce; JWT verify lands when JWKS wired."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        cfg = lti_config()
        ready, reason = lti_ready(cfg)
        if not ready:
            return Response({"detail": reason}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        data = request.POST if request.POST else (request.data or {})
        state = data.get("state") or ""
        id_token = data.get("id_token") or ""
        if not state or not id_token:
            return Response({"detail": "state and id_token required"}, status=400)

        cached = cache.get(f"{_STATE_PREFIX}{state}")
        if not cached:
            return Response({"detail": "Invalid or expired state"}, status=400)
        cache.delete(f"{_STATE_PREFIX}{state}")

        from gradevance.lti.jwt_verify import LtiJwtError, verify_id_token

        try:
            verified = verify_id_token(
                id_token,
                jwks_url=cfg["jwks_url"],
                issuer=cached.get("iss") or cfg["issuer"],
                client_id=cached.get("client_id") or cfg["client_id"],
                expected_nonce=cached.get("nonce") or "",
                deployment_ids=cfg["deployment_ids"] or None,
            )
        except LtiJwtError as exc:
            return Response({"detail": str(exc)}, status=401)

        caps = sorted(map_lti_roles_to_capabilities(verified.roles))
        ctx = LtiLaunchContext(
            iss=verified.iss,
            sub=verified.sub,
            deployment_id=verified.deployment_id,
            roles=verified.roles,
            resource_link_id=verified.resource_link_id,
            context_id=verified.context_id,
        )
        from django.contrib.auth import get_user_model, login as django_login

        from gradevance.lti.ags import ags_lineitem_url_from_claim
        from gradevance.lti.nrps import nrps_members_url_from_claim
        from gradevance.lti.provision import provision_user_from_launch

        provisioned = provision_user_from_launch(
            ctx, email=verified.email, name=verified.name
        )

        # Bind Django session when the request carries one (browser form_post).
        if hasattr(request, "session"):
            try:
                u = get_user_model().objects.get(pk=provisioned.user_id)
                django_login(
                    request, u, backend="django.contrib.auth.backends.ModelBackend"
                )
            except Exception:
                pass

        return Response(
            {
                "status": "ok",
                "launch": asdict(ctx),
                "capabilities": caps,
                "user": {
                    "id": provisioned.user_id,
                    "username": provisioned.username,
                    "created": provisioned.created,
                    "groups": provisioned.groups,
                },
                "name": verified.name,
                "email": verified.email,
                "target_link_uri": cached.get("target_link_uri"),
                "ags_lineitem_url": ags_lineitem_url_from_claim(verified.claims),
                "nrps_memberships_url": nrps_members_url_from_claim(verified.claims),
                "note": (
                    "JWT verified and user provisioned. "
                    "AGS passback only after summative release."
                ),
            }
        )


class LtiConfigView(APIView):
    permission_classes = [IsAuthenticated, GradevanceManageAccess]

    def get(self, request):
        cfg = lti_config()
        ready, reason = lti_ready(cfg)
        # Never leak secrets — only presence flags.
        return Response(
            {
                "ready": ready,
                "reason": reason,
                "enabled": cfg["enabled"],
                "issuer_set": bool(cfg["issuer"]),
                "client_id_set": bool(cfg["client_id"]),
                "auth_login_url_set": bool(cfg["auth_login_url"]),
                "jwks_url_set": bool(cfg["jwks_url"]),
                "redirect_uri_set": bool(cfg["redirect_uri"]),
                "deployment_ids_count": len(cfg["deployment_ids"]),
                "endpoints": {
                    "login": "/api/v1/gradevance/lti/oidc/login/",
                    "launch": "/api/v1/gradevance/lti/oidc/launch/",
                    "status": "/api/v1/gradevance/lti/status/",
                },
                "role_map_example": sorted(
                    map_lti_roles_to_capabilities(("Instructor", "Learner"))
                ),
                "launch_context_schema": list(asdict(LtiLaunchContext(
                    iss="", sub="", deployment_id="", roles=()
                )).keys()),
            }
        )
