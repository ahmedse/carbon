"""Verify LTI 1.3 id_token against platform JWKS (PyJWT)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient


class LtiJwtError(Exception):
    pass


@dataclass(frozen=True)
class VerifiedLaunch:
    iss: str
    sub: str
    aud: str
    nonce: str
    deployment_id: str
    roles: tuple[str, ...]
    resource_link_id: str | None
    context_id: str | None
    name: str | None
    email: str | None
    claims: dict[str, Any]


_JWKS_CLIENTS: dict[str, PyJWKClient] = {}


def _jwks_client(jwks_url: str) -> PyJWKClient:
    if jwks_url not in _JWKS_CLIENTS:
        _JWKS_CLIENTS[jwks_url] = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
    return _JWKS_CLIENTS[jwks_url]


def clear_jwks_cache() -> None:
    _JWKS_CLIENTS.clear()


def verify_id_token(
    id_token: str,
    *,
    jwks_url: str,
    issuer: str,
    client_id: str,
    expected_nonce: str,
    deployment_ids: list[str] | None = None,
) -> VerifiedLaunch:
    """Validate LTI id_token signature + core claims.

    Raises LtiJwtError on any failure — never returns an unverified launch.
    """
    if not id_token or id_token.count(".") != 2:
        raise LtiJwtError("Malformed id_token")

    try:
        signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256", "RS384", "RS512"],
            audience=client_id,
            issuer=issuer,
            options={
                "require": ["exp", "iat", "iss", "aud", "sub", "nonce"],
                "verify_aud": True,
                "verify_iss": True,
            },
        )
    except jwt.PyJWTError as exc:
        raise LtiJwtError(f"JWT verification failed: {exc}") from exc

    nonce = claims.get("nonce") or ""
    if nonce != expected_nonce:
        raise LtiJwtError("nonce mismatch")

    deployment = (
        claims.get("https://purl.imsglobal.org/spec/lti/claim/deployment_id")
        or claims.get("deployment_id")
        or ""
    )
    if deployment_ids and deployment and deployment not in deployment_ids:
        raise LtiJwtError(f"Unknown deployment_id: {deployment}")

    message_type = claims.get("https://purl.imsglobal.org/spec/lti/claim/message_type")
    if message_type and message_type not in (
        "LtiResourceLinkRequest",
        "LtiDeepLinkingRequest",
    ):
        raise LtiJwtError(f"Unsupported message_type: {message_type}")

    roles_raw = claims.get("https://purl.imsglobal.org/spec/lti/claim/roles") or []
    if isinstance(roles_raw, str):
        roles_raw = [roles_raw]
    resource = claims.get("https://purl.imsglobal.org/spec/lti/claim/resource_link") or {}
    context = claims.get("https://purl.imsglobal.org/spec/lti/claim/context") or {}

    aud = claims.get("aud")
    if isinstance(aud, list):
        aud = aud[0] if aud else ""

    return VerifiedLaunch(
        iss=str(claims.get("iss") or ""),
        sub=str(claims.get("sub") or ""),
        aud=str(aud or ""),
        nonce=nonce,
        deployment_id=str(deployment),
        roles=tuple(str(r) for r in roles_raw),
        resource_link_id=(resource.get("id") if isinstance(resource, dict) else None),
        context_id=(context.get("id") if isinstance(context, dict) else None),
        name=claims.get("name"),
        email=claims.get("email"),
        claims=claims,
    )
