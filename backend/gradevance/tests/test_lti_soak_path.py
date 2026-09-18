"""End-to-end LTI soak path without a live LMS (local RSA + dry-run AGS).

Proves: OIDC login → JWT launch → User provision → summative analyze →
release → AGS dry-run recorded on run_manifest.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from accounts.models import User
from gradevance.lti.jwt_verify import clear_jwks_cache
from gradevance.lti.oidc import LtiOidcLaunchView, LtiOidcLoginView, _STATE_PREFIX
from gradevance.models import AnalysisRun, Assignment, Submission
from gradevance.services.pipeline import FormativePipelineService, ReviewService


@pytest.fixture
def rsa_keypair():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@override_settings(
    GRADEVANCE_LTI_ENABLED=True,
    GRADEVANCE_LTI_ISSUER="https://lms.example",
    GRADEVANCE_LTI_CLIENT_ID="gv-client",
    GRADEVANCE_LTI_AUTH_LOGIN_URL="https://lms.example/auth",
    GRADEVANCE_LTI_JWKS_URL="https://lms.example/jwks",
    GRADEVANCE_LTI_REDIRECT_URI="https://eduos.example/launch",
    GRADEVANCE_LTI_DEPLOYMENT_IDS=["dep1"],
    GRADEVANCE_LTI_AGS_DRY_RUN=True,
)
@pytest.mark.django_db(transaction=True)
def test_lti_soak_path_login_launch_release_ags(rsa_keypair):
    clear_jwks_cache()
    factory = APIRequestFactory()

    login_resp = LtiOidcLoginView.as_view()(
        factory.get("/lti/oidc/login/", {"iss": "https://lms.example"})
    )
    assert login_resp.status_code == 200
    state = login_resp.data["state"]

    from django.core.cache import cache

    cached = cache.get(f"{_STATE_PREFIX}{state}")
    assert cached
    nonce = cached["nonce"]
    now = int(time.time())
    payload = {
        "iss": "https://lms.example",
        "aud": "gv-client",
        "sub": "soak-student-1",
        "nonce": nonce,
        "iat": now,
        "exp": now + 300,
        "name": "Soak Student",
        "email": "soak@example.com",
        "https://purl.imsglobal.org/spec/lti/claim/message_type": "LtiResourceLinkRequest",
        "https://purl.imsglobal.org/spec/lti/claim/version": "1.3.0",
        "https://purl.imsglobal.org/spec/lti/claim/deployment_id": "dep1",
        "https://purl.imsglobal.org/spec/lti/claim/roles": [
            "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner",
        ],
        "https://purl.imsglobal.org/spec/lti/claim/resource_link": {"id": "rl-soak"},
        "https://purl.imsglobal.org/spec/lti/claim/context": {"id": "ctx-soak"},
        "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint": {
            "lineitem": "https://lms.example/lineitems/soak-1",
            "scope": ["https://purl.imsglobal.org/spec/lti-ags/scope/score"],
        },
    }
    token = jwt.encode(payload, rsa_keypair, algorithm="RS256", headers={"kid": "soak"})
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
    assert launch_resp.status_code == 200, getattr(launch_resp, "data", None)
    assert launch_resp.data["status"] == "ok"
    assert launch_resp.data["user"]["username"].startswith("lti:")
    assert launch_resp.data["ags_lineitem_url"] == "https://lms.example/lineitems/soak-1"
    assert "gradevance:submit" in launch_resp.data["capabilities"]

    marker = User.objects.create_superuser("soak_marker", "m@test.com", "pass")
    asg = Assignment.objects.create(
        title="Soak summative",
        mode=Assignment.MODE_SUMMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
        brief={"lti": {"ags_lineitem_url": launch_resp.data["ags_lineitem_url"]}},
    )
    text = (
        "The most difficult aspect of preparing my Gaokao is how to use my limited "
        "time. When I was doing my pre-Gaokao exam I always spent most of my time "
        "reading. So I switched my strategies and completed the big writing first."
    )
    sub = Submission.objects.create(
        assignment=asg,
        text=text,
        external_student_key=launch_resp.data["launch"]["sub"],
    )
    run = FormativePipelineService().analyze_submission(sub)
    assert run.pk
    run = ReviewService().release_summative(run, marker)
    run.refresh_from_db()
    assert run.released is True
    ags = (run.run_manifest or {}).get("ags_passback") or {}
    assert ags.get("attempted") is True
    assert ags.get("dry_run") is True
    assert ags.get("ok") is True
