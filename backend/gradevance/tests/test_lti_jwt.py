"""LTI JWT verification with local RSA key (no network JWKS)."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from gradevance.lti.jwt_verify import LtiJwtError, clear_jwks_cache, verify_id_token
from gradevance.lti.oidc import LtiOidcLaunchView, LtiOidcLoginView


@pytest.fixture
def rsa_keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key


def _make_token(private_key, *, nonce: str, iss: str, aud: str, deployment: str = "dep1"):
    now = int(time.time())
    payload = {
        "iss": iss,
        "aud": aud,
        "sub": "user-42",
        "nonce": nonce,
        "iat": now,
        "exp": now + 300,
        "name": "Test User",
        "https://purl.imsglobal.org/spec/lti/claim/message_type": "LtiResourceLinkRequest",
        "https://purl.imsglobal.org/spec/lti/claim/version": "1.3.0",
        "https://purl.imsglobal.org/spec/lti/claim/deployment_id": deployment,
        "https://purl.imsglobal.org/spec/lti/claim/roles": [
            "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor",
        ],
        "https://purl.imsglobal.org/spec/lti/claim/resource_link": {"id": "rl-1"},
        "https://purl.imsglobal.org/spec/lti/claim/context": {"id": "ctx-1"},
    }
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-kid"})


def test_verify_id_token_success(rsa_keypair):
    clear_jwks_cache()
    token = _make_token(
        rsa_keypair, nonce="n1", iss="https://lms.example", aud="gv-client"
    )
    mock_key = MagicMock()
    mock_key.key = rsa_keypair.public_key()
    with patch("gradevance.lti.jwt_verify.PyJWKClient") as mock_cls:
        mock_cls.return_value.get_signing_key_from_jwt.return_value = mock_key
        verified = verify_id_token(
            token,
            jwks_url="https://lms.example/jwks",
            issuer="https://lms.example",
            client_id="gv-client",
            expected_nonce="n1",
            deployment_ids=["dep1"],
        )
    assert verified.sub == "user-42"
    assert "Instructor" in verified.roles[0]
    assert verified.resource_link_id == "rl-1"


def test_verify_id_token_nonce_mismatch(rsa_keypair):
    clear_jwks_cache()
    token = _make_token(
        rsa_keypair, nonce="n1", iss="https://lms.example", aud="gv-client"
    )
    mock_key = MagicMock()
    mock_key.key = rsa_keypair.public_key()
    with patch("gradevance.lti.jwt_verify.PyJWKClient") as mock_cls:
        mock_cls.return_value.get_signing_key_from_jwt.return_value = mock_key
        with pytest.raises(LtiJwtError, match="nonce"):
            verify_id_token(
                token,
                jwks_url="https://lms.example/jwks",
                issuer="https://lms.example",
                client_id="gv-client",
                expected_nonce="wrong",
            )


@override_settings(
    GRADEVANCE_LTI_ENABLED=True,
    GRADEVANCE_LTI_ISSUER="https://lms.example",
    GRADEVANCE_LTI_CLIENT_ID="gv-client",
    GRADEVANCE_LTI_AUTH_LOGIN_URL="https://lms.example/auth",
    GRADEVANCE_LTI_JWKS_URL="https://lms.example/jwks",
    GRADEVANCE_LTI_REDIRECT_URI="https://eduos.example/launch",
    GRADEVANCE_LTI_DEPLOYMENT_IDS=["dep1"],
)
@pytest.mark.django_db
def test_lti_launch_verifies_jwt(rsa_keypair):
    clear_jwks_cache()
    factory = APIRequestFactory()
    login_resp = LtiOidcLoginView.as_view()(
        factory.get("/lti/oidc/login/", {"iss": "https://lms.example"})
    )
    state = login_resp.data["state"]
    # Pull nonce from cache via a second login's pattern — re-read from view internals:
    from django.core.cache import cache
    from gradevance.lti.oidc import _STATE_PREFIX

    cached = cache.get(f"{_STATE_PREFIX}{state}")
    # State was not deleted on login — good. But launch deletes it. Get nonce before launch.
    # Actually login keeps state in cache. We need nonce from cached — but we deleted... 
    # Login doesn't delete. So:
    # Re-initiate to get fresh state after we may have issues - use cached from above.
    # Wait - we need to NOT have deleted. login_resp left state in cache.
    cached = cache.get(f"{_STATE_PREFIX}{state}")
    assert cached
    nonce = cached["nonce"]
    token = _make_token(
        rsa_keypair, nonce=nonce, iss="https://lms.example", aud="gv-client"
    )
    mock_key = MagicMock()
    mock_key.key = rsa_keypair.public_key()
    with patch("gradevance.lti.jwt_verify.PyJWKClient") as mock_cls:
        mock_cls.return_value.get_signing_key_from_jwt.return_value = mock_key
        launch_resp = LtiOidcLaunchView.as_view()(
            factory.post(
                "/lti/oidc/launch/",
                {"state": state, "id_token": token},
                format="json",
            )
        )
    assert launch_resp.status_code == 200, getattr(launch_resp, "data", launch_resp.content)
    assert launch_resp.data["status"] == "ok"
    assert launch_resp.data["launch"]["sub"] == "user-42"
    assert "gradevance:manage" in launch_resp.data["capabilities"]
    assert launch_resp.data["user"]["username"].startswith("lti:")
    assert launch_resp.data["user"]["created"] is True
