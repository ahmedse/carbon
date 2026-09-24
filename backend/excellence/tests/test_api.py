"""Excellence read API: staff only, reads the ledger alias, never writes."""
from __future__ import annotations

import json
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from excellence.gauge import head_commit
from excellence.models import Event, Snapshot

pytestmark = pytest.mark.django_db(databases=["default", "excellence"])


def _auth(user) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {RefreshToken.for_user(user).access_token}"}


@pytest.fixture
def staff():
    return get_user_model().objects.create_superuser(username="exc_staff", email="e@example.com", password="pass")


@pytest.fixture
def employee():
    return get_user_model().objects.create_user(username="exc_emp", password="pass")


@pytest.fixture
def client():
    return APIClient()


def _pass(check: str, subject: str = "platform.module.accounts") -> Event:
    return Event.objects.create(
        check_id=check, subject_id=subject, tier="platform", track="", commit=head_commit(),
        result="passed", evidence_class="executed", source="test",
    )


def test_employee_and_anonymous_are_refused(client, employee):
    assert client.get("/carbon-api/excellence/ladder/").status_code in (401, 403)
    assert client.get("/carbon-api/excellence/ladder/", **_auth(employee)).status_code == 403


def test_ladder_lists_tiers_and_levels_from_events(client, staff):
    for check in ("PLAT-GOV-01", "PLAT-GOV-02", "PLAT-SPC-01", "PLAT-COR-01"):
        _pass(check)
    resp = client.get("/carbon-api/excellence/ladder/?tier=platform", **_auth(staff))
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert {t["id"] for t in body["tiers"]} >= {"platform", "pulse"}
    row = next(s for s in body["subjects"] if s["subject_id"] == "platform.module.accounts")
    assert row["level"] == 3 and row["level_name"] == "Built"
    assert row["next"] == ["PLAT-COR-02"]
    assert all(s["tier"] == "platform" for s in body["subjects"])


def test_subject_detail_has_checks_events_and_trend(client, staff):
    _pass("PLAT-GOV-01")
    Snapshot.objects.create(date=date(2026, 9, 23), tier="platform", track="", subject_id="platform.module.accounts",
                            commit="x", level=1, dimensions={"governed": 1})
    resp = client.get("/carbon-api/excellence/subjects/platform.module.accounts/", **_auth(staff))
    assert resp.status_code == 200, resp.content
    body = resp.json()
    gov = next(c for c in body["checks"] if c["check_id"] == "PLAT-GOV-01")
    assert gov["state"] == "passed" and gov["solution"]
    assert body["events"][0]["check_id"] == "PLAT-GOV-01"
    assert body["trend"][0] == {"date": "2026-09-23", "level": 1, "commit": "x", "dimensions": {"governed": 1}}


def test_unknown_subject_is_404(client, staff):
    assert client.get("/carbon-api/excellence/subjects/nope/", **_auth(staff)).status_code == 404


def test_stream_once_is_event_stream(client, staff):
    resp = client.get("/carbon-api/excellence/stream/?once=1&tier=pulse", HTTP_ACCEPT="text/event-stream", **_auth(staff))
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/event-stream")
    raw = b"".join(resp.streaming_content).decode("utf-8")
    payload = json.loads(raw.split("data: ", 1)[1])
    assert "subjects" in payload and all(s["tier"] == "pulse" for s in payload["subjects"])
