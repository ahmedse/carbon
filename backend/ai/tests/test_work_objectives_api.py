"""Pulse v2 Phase 8 — Work Objectives REST endpoint tests.

Covers:
* GET list returns only the requesting user's objectives (status_filter=open)
* PATCH updates status
* PATCH cannot mutate title/description (read-only fields)
* 401 when unauthenticated
"""
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from ai.models.core import WorkObjective


@pytest.fixture
def owner(db) -> User:
    return User.objects.create_user(username="wo-owner", password="secret123")


@pytest.fixture
def other(db) -> User:
    return User.objects.create_user(username="wo-other", password="secret123")


@pytest.fixture
def client():
    return APIClient()


def _objective(user, **overrides) -> WorkObjective:
    base = {
        "instance_id": "carbon",
        "conversation_id": "c1",
        "host_user_id": str(user.pk),
        "title": "Investigate Scope 2",
        "description": "Find all Scope 2 factors",
        "status": "open",
    }
    base.update(overrides)
    return WorkObjective.objects.create(**base)


@pytest.mark.django_db
def test_list_returns_only_own_objectives(owner, other, client):
    _objective(owner)
    _objective(owner, title="DQ audit", status="in_progress")
    _objective(other, title="Other user objective")

    client.force_authenticate(user=owner)
    resp = client.get(reverse("ai-work-objective-list"))

    assert resp.status_code == 200
    titles = {row["title"] for row in resp.json()}
    assert titles == {"Investigate Scope 2", "DQ audit"}
    assert "Other user objective" not in titles


@pytest.mark.django_db
def test_list_default_filters_to_open_statuses(owner, client):
    _objective(owner)
    _objective(owner, title="Done one", status="completed")

    client.force_authenticate(user=owner)
    resp = client.get(reverse("ai-work-objective-list"))

    assert resp.status_code == 200
    titles = {row["title"] for row in resp.json()}
    assert titles == {"Investigate Scope 2"}


@pytest.mark.django_db
def test_patch_updates_status(owner, client):
    obj = _objective(owner)

    client.force_authenticate(user=owner)
    resp = client.patch(
        reverse("ai-work-objective-detail", args=[obj.id]),
        {"status": "completed"},
        format="json",
    )

    assert resp.status_code == 200
    obj.refresh_from_db()
    assert obj.status == "completed"


@pytest.mark.django_db
def test_patch_cannot_mutate_title_or_description(owner, client):
    obj = _objective(owner)

    client.force_authenticate(user=owner)
    resp = client.patch(
        reverse("ai-work-objective-detail", args=[obj.id]),
        {"title": "HACKED", "description": "HACKED", "status": "cancelled"},
        format="json",
    )

    assert resp.status_code == 200
    obj.refresh_from_db()
    assert obj.title == "Investigate Scope 2"
    assert obj.description == "Find all Scope 2 factors"
    assert obj.status == "cancelled"


@pytest.mark.django_db
def test_requires_auth(client):
    resp = client.get(reverse("ai-work-objective-list"))
    assert resp.status_code == 401
