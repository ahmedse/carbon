"""Sign Deep Linking JWT responses with a tool RSA private key (optional).

Production: set GRADEVANCE_LTI_TOOL_PRIVATE_KEY_PEM (PKCS8 PEM).
Without a key, preview endpoints return unsigned claims only.
"""
from __future__ import annotations

from typing import Any

import jwt
from django.conf import settings


class DeepLinkSignError(Exception):
    pass


def tool_private_key_pem() -> str:
    return (getattr(settings, "GRADEVANCE_LTI_TOOL_PRIVATE_KEY_PEM", "") or "").strip()


def sign_deep_link_jwt(claims: dict[str, Any], *, expires_in: int = 300) -> str:
    """Return a signed JWT string. Raises if no tool private key configured."""
    import time

    pem = tool_private_key_pem()
    if not pem:
        raise DeepLinkSignError("GRADEVANCE_LTI_TOOL_PRIVATE_KEY_PEM not set")
    payload = dict(claims)
    now = int(time.time())
    payload.setdefault("iat", now)
    payload.setdefault("exp", now + expires_in)
    try:
        return jwt.encode(payload, pem, algorithm="RS256")
    except Exception as exc:
        raise DeepLinkSignError(f"Sign failed: {exc}") from exc
