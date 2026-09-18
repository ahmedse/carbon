# backend/ai/tests/test_registry_reject.py
"""ADR-0036 — process review reject persists reason and returns to draft."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from ai.models.process import STATUS_DRAFT, STATUS_REVIEW, ProcessDefinition


User = get_user_model()


def _doc(pid="proc.reject.demo", status=STATUS_REVIEW):
    return {
        "id": pid,
        "version": "1.0.0",
        "owner": "author",
        "status": status,
        "steps": [
            {
                "id": "s1",
                "kind": "command",
                "capability": "noop.capability",
                "autonomy": "human_only",
            }
        ],
        "objective": {"predicate": "demo"},
    }


@pytest.fixture
def publisher_client(db):
    user = User.objects.create_superuser(
        username="rej_pub", email="rej@example.com", password="x"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.django_db
def test_reject_review_to_draft(publisher_client, monkeypatch):
    client, user = publisher_client
    # Bypass capability resolution in validator
    monkeypatch.setattr(
        "ai.models.process._default_known_capabilities",
        lambda: {"noop.capability"},
    )
    doc = _doc()
    obj = ProcessDefinition.from_document(doc)
    obj.host_user_id = str(user.pk)
    obj.save()

    resp = client.post(
        f"/carbon-api/ai/registry/processes/{obj.process_id}/reject/",
        {"reason": "missing evidence"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["status"] == STATUS_DRAFT
    assert body["definition"]["last_reject_reason"] == "missing evidence"
    assert body["definition"]["review_history"][-1]["action"] == "rejected"

    refreshed = ProcessDefinition.objects.get(pk=obj.pk)
    assert refreshed.status == STATUS_DRAFT
