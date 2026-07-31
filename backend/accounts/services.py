# File: accounts/services.py
# Service layer for the accounts app (Facade pattern).
# Views call these services; services contain NO DRF imports (no rest_framework,
# no Response, no status). Zero behavioral change vs. the logic previously in views.

import os
import re
import time
from pathlib import Path

import jwt
import requests

from django.conf import settings


class RoleResolutionService:
    """Resolve group names to normalized forms and frontend perspectives."""

    @staticmethod
    def normalize_group_name(group_name):
        return (group_name or "").strip().lower()

    @staticmethod
    def perspective_from_group_name(group_name):
        normalized = RoleResolutionService.normalize_group_name(group_name)
        if not normalized:
            return None

        if normalized in {"admin", "admins_group"} or (
            normalized.endswith("admin") and "carbon" not in normalized and "catalog" not in normalized
        ):
            return "admin"
        if "data_owner" in normalized or "dataowner" in normalized or "data-owner" in normalized:
            return "data-owner"
        if "analyst" in normalized:
            return "analyst"
        if "viewer" in normalized:
            return "viewer"
        if "steward" in normalized:
            return "steward"
        if normalized.endswith("admin") and "carbon" in normalized:
            return "carbon-admin"
        if normalized.endswith("admin") and "catalog" in normalized:
            return "catalog-admin"
        return None


class AppManifestService:
    """Load app manifests from settings or the frontend apps directory."""

    @staticmethod
    def load_manifests():
        app_registry = getattr(settings, "APP_REGISTRY", None)
        if app_registry:
            return app_registry

        repo_root = Path(__file__).resolve().parents[2]
        apps_dir = repo_root / "carbon-frontend" / "src" / "apps"
        if not apps_dir.exists():
            return []

        manifests = []
        for manifest_path in sorted(apps_dir.glob("**/manifest.js")):
            text = manifest_path.read_text(encoding="utf-8")
            app_id_match = re.search(r"id:\s*['\"]([^'\"]+)['\"]", text)
            name_match = re.search(r"name:\s*['\"]([^'\"]+)['\"]", text)
            version_match = re.search(r"version:\s*['\"]([^'\"]+)['\"]", text)

            roles = []
            roles_block_match = re.search(r"roles:\s*\[(.*?)\]\s*,", text, re.S)
            if roles_block_match:
                roles_block = roles_block_match.group(1)
                for role_match in re.finditer(
                    r"key:\s*['\"]([^'\"]+)['\"],\s*label:\s*['\"]([^'\"]+)['\"],\s*scoped:\s*(true|false),\s*description:\s*['\"]([^'\"]*)['\"]",
                    roles_block,
                ):
                    roles.append({
                        "key": role_match.group(1),
                        "label": role_match.group(2),
                        "scoped": role_match.group(3).lower() == "true",
                        "description": role_match.group(4),
                    })

            manifests.append({
                "id": app_id_match.group(1) if app_id_match else manifest_path.parent.name,
                "name": name_match.group(1) if name_match else manifest_path.parent.name,
                "version": version_match.group(1) if version_match else "1.0.0",
                "roles": roles,
            })

        return manifests


class PulseService:
    """Bridge to the external Pulse AI system (token generation + provisioning)."""

    PULSE_HOST = os.getenv('PULSE_HOST', 'http://127.0.0.1:9100')
    PULSE_INSTANCE_ID = os.getenv('PULSE_INSTANCE_ID', 'carbon')
    PULSE_JWT_SECRET = os.getenv('PULSE_JWT_SECRET', 'changeme-in-production')
    PULSE_JWT_ALGORITHM = os.getenv('PULSE_JWT_ALGORITHM', 'HS256')

    @staticmethod
    def generate_token(user):
        """
        Generate JWT token for Pulse authentication.
        Token includes user identity and instance context.
        """
        now = int(time.time())
        payload = {
            'sub': user.username,  # User identifier
            'email': user.email,
            'name': user.get_full_name() or user.username,
            'iss': 'carbon-platform',  # Issuer
            'instance_id': PulseService.PULSE_INSTANCE_ID,
            'iat': now,
            'exp': now + (24 * 60 * 60),  # 24 hour expiry
        }

        token = jwt.encode(payload, PulseService.PULSE_JWT_SECRET, algorithm=PulseService.PULSE_JWT_ALGORITHM)
        return token

    @staticmethod
    def provision(user, context):
        """
        Provision the user to the Pulse instance.
        Returns a tuple (status_code, response_dict) — the view decides the HTTP response.
        """
        pulse_token = PulseService.generate_token(user)

        provision_url = f"{PulseService.PULSE_HOST}/api/v1/instances/{PulseService.PULSE_INSTANCE_ID}/users"

        provision_data = {
            'user_id': user.username,
            'email': user.email,
            'name': user.get_full_name() or user.username,
            'roles': list(user.groups.values_list('name', flat=True)),
            'context': context,
        }

        try:
            response = requests.post(
                provision_url,
                json=provision_data,
                headers={
                    'Authorization': f'Bearer {pulse_token}',
                    'Content-Type': 'application/json',
                },
                timeout=5,
            )

            if response.status_code in [200, 201]:
                return 200, {
                    'status': 'provisioned',
                    'pulse_user_id': response.json().get('user_id'),
                }
            return 502, {
                'status': 'error',
                'message': f'Pulse provision failed: {response.text}',
            }

        except requests.RequestException as e:
            return 503, {
                'status': 'error',
                'message': f'Failed to connect to Pulse: {str(e)}',
            }
