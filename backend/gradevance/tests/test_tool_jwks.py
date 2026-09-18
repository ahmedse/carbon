from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from gradevance.lti.tool_jwks import ToolJwksView


def _pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def test_tool_jwks_empty_without_key():
    factory = APIRequestFactory()
    with override_settings(GRADEVANCE_LTI_TOOL_PRIVATE_KEY_PEM=""):
        resp = ToolJwksView.as_view()(factory.get("/lti/jwks/"))
    assert resp.status_code == 200
    assert resp.data["keys"] == []


def test_tool_jwks_exposes_rsa():
    pem = _pem()
    factory = APIRequestFactory()
    with override_settings(GRADEVANCE_LTI_TOOL_PRIVATE_KEY_PEM=pem, GRADEVANCE_LTI_TOOL_KEY_ID="k1"):
        resp = ToolJwksView.as_view()(factory.get("/lti/jwks/"))
    assert resp.status_code == 200
    assert len(resp.data["keys"]) == 1
    assert resp.data["keys"][0]["kty"] == "RSA"
    assert resp.data["keys"][0]["kid"] == "k1"
