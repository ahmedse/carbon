"""Publish tool JWKS for LMS platform registration (LTI Advantage)."""
from __future__ import annotations

import json
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from gradevance.lti.deep_link_sign import tool_private_key_pem


def _public_jwk_from_pem(pem: str, kid: str = "gradevance-1") -> dict[str, Any] | None:
    if not pem:
        return None
    try:
        key = serialization.load_pem_private_key(pem.encode(), password=None)
        if not isinstance(key, rsa.RSAPrivateKey):
            return None
        pub = key.public_key().public_numbers()
        # Encode modulus/exponent as base64url without padding.
        import base64

        def b64u(n: int) -> str:
            length = (n.bit_length() + 7) // 8
            return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode()

        return {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": kid,
            "n": b64u(pub.n),
            "e": b64u(pub.e),
        }
    except Exception:
        return None


class ToolJwksView(APIView):
    """Public JWKS for the GradeVance tool key (empty keys[] if unset)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        kid = getattr(settings, "GRADEVANCE_LTI_TOOL_KEY_ID", "gradevance-1") or "gradevance-1"
        jwk = _public_jwk_from_pem(tool_private_key_pem(), kid=kid)
        return Response({"keys": [jwk] if jwk else []})
