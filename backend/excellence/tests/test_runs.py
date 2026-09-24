"""Runs and exemptions (ADR-0051 P2)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from excellence.models import Run

pytestmark = pytest.mark.django_db(databases=["default", "excellence"])


def _auth(user) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {RefreshToken.for_user(user).access_token}"}


@pytest.fixture
def staff():
    return get_user_model().objects.create_superuser(username="run_staff", email="r@example.com", password="pass")


@pytest.fixture
def client():
    return APIClient()


def test_employee_cannot_start_a_run(client):
    emp = get_user_model().objects.create_user(username="run_emp", password="pass")
    resp = client.post("/carbon-api/excellence/runs/", {"collectors": ["repo"]}, format="json", **_auth(emp))
    assert resp.status_code == 403


def test_repo_run_persists_events_and_returns_ladder(client, staff):
    resp = client.post(
        "/carbon-api/excellence/runs/",
        {"collectors": ["repo"], "tier": "platform", "write_snapshot": True},
        format="json",
        **_auth(staff),
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["event_count"] > 0
    assert body["ladder"]["subjects"]
    assert Run.objects.filter(pk=body["id"]).exists()


def test_pytest_without_app_is_rejected(client, staff):
    resp = client.post(
        "/carbon-api/excellence/runs/",
        {"collectors": ["pytest"]},
        format="json",
        **_auth(staff),
    )
    assert resp.status_code == 400
    assert "run_apps" in resp.json()["detail"]


def test_exemption_grant_and_revoke(client, staff):
    until = (date.today() + timedelta(days=7)).isoformat()
    resp = client.post(
        "/carbon-api/excellence/exemptions/",
        {
            "check_id": "PLAT-COR-02",
            "subject_id": "platform.module.accounts",
            "reason": "waiting on CI green",
            "until": until,
        },
        format="json",
        **_auth(staff),
    )
    assert resp.status_code == 201, resp.content
    eid = resp.json()["id"]
    detail = client.get("/carbon-api/excellence/subjects/platform.module.accounts/", **_auth(staff))
    assert detail.status_code == 200
    assert any(x["check_id"] == "PLAT-COR-02" for x in detail.json()["exemptions"])
    rev = client.delete(f"/carbon-api/excellence/exemptions/{eid}/", **_auth(staff))
    assert rev.status_code == 204
