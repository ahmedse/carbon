"""Offline LTI soak path: OIDC login → JWT launch → provision → summative release → AGS dry-run.

Does not require a live LMS. Use before Canvas/Moodle soak to prove the pipeline.

  cd backend && ../.venv/bin/python manage.py soak_gradevance_lti
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.management.base import BaseCommand, CommandError
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from gradevance.lti.jwt_verify import clear_jwks_cache
from gradevance.lti.oidc import LtiOidcLaunchView, LtiOidcLoginView, _STATE_PREFIX
from gradevance.models import AnalysisRun, Assignment, Submission
from gradevance.services.pipeline import FormativePipelineService, ReviewService


SAMPLE = (
    "The most difficult aspect of preparing my Gaokao is how to use my limited "
    "time to fulfill the most parts of my exam paper. In Gaokao it's a normal "
    "problem that you won't have enough time. When I was doing my pre-Gaokao "
    "exam I always spent most of my time reading. I switched my strategies and "
    "completed the big writing first so I can push my potentials to read faster."
)


class Command(BaseCommand):
    help = "Run offline GradeVance LTI soak (login→launch→release→AGS dry-run)"

    def handle(self, *args, **options):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        clear_jwks_cache()
        settings_kw = dict(
            GRADEVANCE_LTI_ENABLED=True,
            GRADEVANCE_LTI_ISSUER="https://lms.soak.example",
            GRADEVANCE_LTI_CLIENT_ID="gv-soak",
            GRADEVANCE_LTI_AUTH_LOGIN_URL="https://lms.soak.example/auth",
            GRADEVANCE_LTI_JWKS_URL="https://lms.soak.example/jwks",
            GRADEVANCE_LTI_REDIRECT_URI="https://eduos.example/launch",
            GRADEVANCE_LTI_DEPLOYMENT_IDS=["dep-soak"],
            GRADEVANCE_LTI_AGS_DRY_RUN=True,
        )

        with override_settings(**settings_kw):
            factory = APIRequestFactory()
            login_resp = LtiOidcLoginView.as_view()(
                factory.get("/lti/oidc/login/", {"iss": "https://lms.soak.example"})
            )
            if login_resp.status_code != 200:
                raise CommandError(f"OIDC login failed: {login_resp.status_code}")
            state = login_resp.data["state"]
            from django.core.cache import cache

            cached = cache.get(f"{_STATE_PREFIX}{state}")
            if not cached:
                raise CommandError("state missing from cache")
            nonce = cached["nonce"]
            now = int(time.time())
            payload = {
                "iss": "https://lms.soak.example",
                "aud": "gv-soak",
                "sub": "soak-user-1",
                "nonce": nonce,
                "iat": now,
                "exp": now + 300,
                "name": "Soak User",
                "https://purl.imsglobal.org/spec/lti/claim/message_type": "LtiResourceLinkRequest",
                "https://purl.imsglobal.org/spec/lti/claim/deployment_id": "dep-soak",
                "https://purl.imsglobal.org/spec/lti/claim/roles": [
                    "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor",
                ],
                "https://purl.imsglobal.org/spec/lti/claim/resource_link": {"id": "rl-soak"},
                "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint": {
                    "lineitem": "https://lms.soak.example/lineitems/99",
                    "scope": [
                        "https://purl.imsglobal.org/spec/lti-ags/scope/score",
                    ],
                },
            }
            token = jwt.encode(payload, key, algorithm="RS256", headers={"kid": "soak"})
            mock_key = MagicMock()
            mock_key.key = key.public_key()
            with patch("gradevance.lti.jwt_verify.PyJWKClient") as mock_cls:
                mock_cls.return_value.get_signing_key_from_jwt.return_value = mock_key
                launch_resp = LtiOidcLaunchView.as_view()(
                    factory.post(
                        "/lti/oidc/launch/",
                        {"state": state, "id_token": token},
                        format="json",
                    )
                )
            if launch_resp.status_code != 200:
                raise CommandError(
                    f"Launch failed: {launch_resp.status_code} {getattr(launch_resp, 'data', None)}"
                )
            self.stdout.write(self.style.SUCCESS(f"1. Launch OK user={launch_resp.data['user']}"))
            lineitem = launch_resp.data.get("ags_lineitem_url")
            if not lineitem:
                raise CommandError("Launch missing ags_lineitem_url")

            asg = Assignment.objects.create(
                title="Soak summative",
                mode=Assignment.MODE_SUMMATIVE,
                status=Assignment.STATUS_PUBLISHED,
                profile_pack_id="naa_cycle1_exam_prep",
                profile_version=1,
                brief={"lti": {"ags_lineitem_url": lineitem}},
            )
            sub = Submission.objects.create(
                assignment=asg,
                text=SAMPLE,
                external_student_key="soak-user-1",
            )
            run = FormativePipelineService().analyze_submission(sub)
            self.stdout.write(
                self.style.SUCCESS(
                    f"2. Analyze OK run={run.id} status={run.status} segments={run.segments.count()}"
                )
            )

            from django.contrib.auth import get_user_model

            editor = get_user_model().objects.get(pk=launch_resp.data["user"]["id"])
            run = ReviewService().release_summative(run, editor)
            run.refresh_from_db()
            ags = (run.run_manifest or {}).get("ags_passback") or {}
            if not ags.get("attempted") or not ags.get("ok"):
                raise CommandError(f"AGS passback failed: {ags}")
            self.stdout.write(
                self.style.SUCCESS(
                    f"3. Release + AGS dry-run OK url={ags.get('url')} dry_run={ags.get('dry_run')}"
                )
            )
            self.stdout.write(self.style.SUCCESS("SOAK PATH GREEN — ready for live LMS."))
