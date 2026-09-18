from django.test import override_settings
from rest_framework.test import APIRequestFactory

from gradevance.lti.oidc import LtiOidcLaunchView, LtiOidcLoginView, lti_ready
from gradevance.services.coders import get_coder, list_coders


def test_lti_not_ready_by_default():
    ready, reason = lti_ready()
    assert ready is False
    assert "ENABLED" in reason or "Missing" in reason


@override_settings(
    GRADEVANCE_LTI_ENABLED=True,
    GRADEVANCE_LTI_ISSUER="https://lms.example",
    GRADEVANCE_LTI_CLIENT_ID="gv-client",
    GRADEVANCE_LTI_AUTH_LOGIN_URL="https://lms.example/auth",
    GRADEVANCE_LTI_JWKS_URL="https://lms.example/jwks",
    GRADEVANCE_LTI_REDIRECT_URI="https://eduos.example/api/v1/gradevance/lti/oidc/launch/",
)
def test_lti_oidc_login_returns_redirect():
    factory = APIRequestFactory()
    req = factory.get(
        "/api/v1/gradevance/lti/oidc/login/",
        {"iss": "https://lms.example", "login_hint": "u1"},
    )
    resp = LtiOidcLoginView.as_view()(req)
    assert resp.status_code == 200
    assert resp.data["status"] == "redirect"
    assert "authorization_url" in resp.data
    assert "state=" in resp.data["authorization_url"]


@override_settings(GRADEVANCE_LTI_ENABLED=False)
def test_lti_oidc_login_503_when_disabled():
    factory = APIRequestFactory()
    req = factory.get("/api/v1/gradevance/lti/oidc/login/")
    resp = LtiOidcLoginView.as_view()(req)
    assert resp.status_code == 503


@override_settings(
    GRADEVANCE_LTI_ENABLED=True,
    GRADEVANCE_LTI_ISSUER="https://lms.example",
    GRADEVANCE_LTI_CLIENT_ID="gv-client",
    GRADEVANCE_LTI_AUTH_LOGIN_URL="https://lms.example/auth",
    GRADEVANCE_LTI_JWKS_URL="https://lms.example/jwks",
    GRADEVANCE_LTI_REDIRECT_URI="https://eduos.example/launch",
)
def test_lti_launch_rejects_bad_token():
    factory = APIRequestFactory()
    login_req = factory.get(
        "/lti/oidc/login/",
        {"iss": "https://lms.example"},
    )
    login_resp = LtiOidcLoginView.as_view()(login_req)
    state = login_resp.data["state"]
    launch_req = factory.post(
        "/lti/oidc/launch/",
        {"state": state, "id_token": "not.a.jwt"},
        format="json",
    )
    launch_resp = LtiOidcLaunchView.as_view()(launch_req)
    assert launch_resp.status_code == 401


def test_llm_assist_coder_registered():
    from gradevance.services import llm_coder  # noqa: F401

    assert "llm_assist" in list_coders()
    from gradevance.services.pipeline import _SegDraft

    seg = _SegDraft(0, 0, 5, "When I sat the exam for example I spent hours", "what")
    coded = get_coder("llm_assist")(seg, [], True)
    assert coded
    assert coded[0]["evidence"].get("llm") == "unavailable_fallback_heuristic"
