# backend/ai/tests/test_control_plane_api.py
"""ADR-0036 Pulse Control Plane API smoke tests."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.capabilities import AI_MANAGE_CONSOLE, AI_OPERATOR, AI_VIEW_CONSOLE
from ai.models.control_state import PulseControlState


User = get_user_model()


@pytest.fixture
def admin_client(db):
    user = User.objects.create_superuser(
        username="ctrl_admin", email="ctrl@example.com", password="x"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.django_db
def test_command_center_returns_queues(admin_client):
    client, _ = admin_client
    resp = client.get("/carbon-api/ai/pulse/control/command/")
    assert resp.status_code == 200
    body = resp.json()
    assert "queues" in body
    assert "containment" in body
    assert "spend" in body


@pytest.mark.django_db
def test_containment_set_and_audit(admin_client):
    client, user = admin_client
    resp = client.post(
        "/carbon-api/ai/pulse/control/containment/",
        {"level": "learning_freeze", "reason": "test"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["containment_level"] == "learning_freeze"
    assert resp.json()["learning_admissions_frozen"] is True
    state = PulseControlState.objects.get(instance_id=resp.json()["instance_id"])
    assert state.updated_by == user.username


@pytest.mark.django_db
def test_budget_override(admin_client):
    client, _ = admin_client
    resp = client.patch(
        "/carbon-api/ai/pulse/control/budget/",
        {"daily_budget_usd": 12.5},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["daily_budget_usd"] == 12.5


@pytest.mark.django_db
def test_evidence_requires_id(admin_client):
    client, _ = admin_client
    resp = client.get("/carbon-api/ai/pulse/control/evidence/")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_candidates_list(admin_client):
    client, _ = admin_client
    resp = client.get("/carbon-api/ai/pulse/control/candidates/")
    assert resp.status_code == 200
    assert "results" in resp.json()
