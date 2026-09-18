"""Deep link JWT signing tests."""
from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import override_settings

from gradevance.lti.deep_link import deep_link_jwt_claims
from gradevance.lti.deep_link_sign import DeepLinkSignError, sign_deep_link_jwt


def _pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def test_sign_requires_key():
    with override_settings(GRADEVANCE_LTI_TOOL_PRIVATE_KEY_PEM=""):
        with pytest.raises(DeepLinkSignError):
            sign_deep_link_jwt({"iss": "t", "aud": "lms"})


def test_sign_deep_link_jwt():
    pem = _pem()
    claims = deep_link_jwt_claims(
        iss="tool",
        aud="https://lms.example",
        deployment_id="dep1",
        data=None,
        content_items=[{"type": "ltiResourceLink", "title": "t", "url": "https://x"}],
    )
    with override_settings(GRADEVANCE_LTI_TOOL_PRIVATE_KEY_PEM=pem):
        token = sign_deep_link_jwt(claims)
    assert token.count(".") == 2
