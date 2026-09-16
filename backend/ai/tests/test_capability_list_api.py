"""PEC-R1 — read-only Capability registry list API (catalog surface).

Covers:
  * anonymous GET → 401
  * authenticated GET → 200 with business-field shape
  * at least one seeded Capability row when DB is available
  * CBAC: private rows of another user are hidden; shared rows visible
  * write methods → 405 (RULE_21 read-only)
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from ai.instance_registry import resolve_default_app_identifier
from ai.models.capability import Capability

BASE = "/carbon-api/ai/catalog/capabilities/"

_EXPECTED_FIELDS = frozenset(
    {
        "capability_id",
        "business_name",
        "purpose",
        "kind",
        "host_action",
        "owner",
        "version",
        "permissions",
        "requires_confirmation",
    }
)


@pytest.fixture
def user(db):
    from accounts.models import User

    return User.objects.create_user(username="cap-list-user", password="secret123")


@pytest.fixture
def other_user(db):
    from accounts.models import User

    return User.objects.create_user(username="cap-list-other", password="secret123")


@pytest.fixture
def auth_client(get_token_for_user, user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")
    return client


def _seed_capability(**overrides) -> Capability:
    defaults = {
        "capability_id": "dq.rule.validate",
        "business_name": "Validate DQ rule",
        "purpose": "Validate a draft DQ rule before publish",
        "kind": "read_only",
        "host_action": "dq.validate_rule",
        "owner": "dq",
        "version": "1.0",
        "permissions": {"read": ["ai:view_console"]},
        "requires_confirmation": False,
        "app_identifier": resolve_default_app_identifier(),
        "visibility": "shared",
        "org_unit_id": None,
        "host_user_id": None,
    }
    defaults.update(overrides)
    return Capability.objects.create(**defaults)


@pytest.mark.django_db
def test_capabilities_list_requires_auth(api_client):
    assert api_client.get(BASE).status_code == 401


@pytest.mark.django_db
def test_capabilities_list_returns_seeded_shape(auth_client):
    _seed_capability()

    resp = auth_client.get(BASE)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1

    by_id = {row["capability_id"]: row for row in rows}
    assert "dq.rule.validate" in by_id
    row = by_id["dq.rule.validate"]
    assert set(row.keys()) == _EXPECTED_FIELDS
    assert row["business_name"] == "Validate DQ rule"
    assert row["kind"] == "read_only"
    assert row["host_action"] == "dq.validate_rule"
    assert row["owner"] == "dq"
    assert row["version"] == "1.0"
    assert row["permissions"] == {"read": ["ai:view_console"]}
    assert row["requires_confirmation"] is False
    # Partition / secret fields must never leak.
    assert "app_identifier" not in row
    assert "visibility" not in row
    assert "host_user_id" not in row
    assert "inputs" not in row
    assert "approval_requirements" not in row


@pytest.mark.django_db
def test_capabilities_list_hides_foreign_private_rows(auth_client, other_user):
    _seed_capability(
        capability_id="dq.rule.private",
        business_name="Private cap",
        visibility="private",
        host_user_id=str(other_user.id),
    )
    _seed_capability(
        capability_id="dq.rule.shared",
        business_name="Shared cap",
        visibility="shared",
    )

    resp = auth_client.get(BASE)
    assert resp.status_code == 200
    ids = {row["capability_id"] for row in resp.json()}
    assert "dq.rule.shared" in ids
    assert "dq.rule.private" not in ids


@pytest.mark.django_db
def test_capabilities_list_rejects_writes(auth_client):
    assert auth_client.post(BASE, {}, format="json").status_code == 405
    assert auth_client.patch(BASE, {}, format="json").status_code == 405
    assert auth_client.delete(BASE).status_code == 405
