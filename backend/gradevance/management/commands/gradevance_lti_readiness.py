"""Print GradeVance LTI readiness for LMS soak (no secrets)."""
from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from gradevance.lti.deep_link_sign import tool_private_key_pem
from gradevance.lti.oidc import lti_config, lti_ready


class Command(BaseCommand):
    help = "Show GradeVance LTI soak readiness (flags only — no secrets)."

    def handle(self, *args, **options):
        cfg = lti_config()
        ready, reason = lti_ready(cfg)
        rows = [
            ("ready", ready),
            ("reason", reason),
            ("ags_dry_run", getattr(settings, "GRADEVANCE_LTI_AGS_DRY_RUN", True)),
            ("token_url_set", bool(getattr(settings, "GRADEVANCE_LTI_TOKEN_URL", ""))),
            ("client_secret_set", bool(getattr(settings, "GRADEVANCE_LTI_CLIENT_SECRET", ""))),
            ("tool_key_set", bool(tool_private_key_pem())),
            ("issuer_set", bool(cfg.get("issuer"))),
            ("jwks_url_set", bool(cfg.get("jwks_url"))),
            ("deployment_ids", len(cfg.get("deployment_ids") or [])),
        ]
        for k, v in rows:
            self.stdout.write(f"{k}={v}")
        if ready and getattr(settings, "GRADEVANCE_LTI_AGS_DRY_RUN", True):
            self.stdout.write(
                self.style.WARNING(
                    "LTI configured but AGS still dry-run — set GRADEVANCE_LTI_AGS_DRY_RUN=false for live gradebook."
                )
            )
        elif not ready:
            self.stdout.write(self.style.ERROR("Not ready — see docs/eduos/LMS-SOAK.md"))
        else:
            self.stdout.write(self.style.SUCCESS("Ready for live LMS soak"))
