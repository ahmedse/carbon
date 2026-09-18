# backend/ai/tests/test_prompt_knowledge_governance.py
"""Phase 7 — prompt activate/rollback + KnowledgeItem CRUD."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from ai.instance_registry import resolve_instance_id
from ai.models.core import PromptVersion
from ai.models.knowledge import KnowledgeItem, REVIEW_DEPRECATED


User = get_user_model()


@pytest.fixture
def admin_client(db):
    user = User.objects.create_superuser(
        username="gov_admin", email="gov@example.com", password="x"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.django_db
def test_prompt_activate_and_rollback(admin_client):
    client, _ = admin_client
    instance_id = resolve_instance_id()
    parent = PromptVersion.objects.create(
        instance_id=instance_id,
        prompt_text="parent prompt",
        content_hash="aaaaaaaa",
        is_active=False,
        improvement_round=0,
    )
    child = PromptVersion.objects.create(
        instance_id=instance_id,
        prompt_text="child prompt",
        content_hash="bbbbbbbb",
        is_active=True,
        improvement_round=1,
        parent_version_id=parent.id,
    )

    resp = client.post(
        f"/carbon-api/ai/pulse/control/prompts/versions/{parent.id}/activate/",
        {},
        format="json",
    )
    assert resp.status_code == 200
    parent.refresh_from_db()
    child.refresh_from_db()
    assert parent.is_active is True
    assert child.is_active is False

    # Re-activate child then rollback to parent
    client.post(
        f"/carbon-api/ai/pulse/control/prompts/versions/{child.id}/activate/",
        {},
        format="json",
    )
    resp = client.post(
        f"/carbon-api/ai/pulse/control/prompts/versions/{child.id}/rollback/",
        {},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["version"]["id"] == parent.id
    parent.refresh_from_db()
    assert parent.is_active is True


@pytest.mark.django_db
def test_knowledge_item_create_and_revoke(admin_client):
    client, _ = admin_client
    resp = client.post(
        "/carbon-api/ai/knowledge/items/",
        {
            "knowledge_class": "business_fact",
            "content": "Leave accrual is monthly.",
            "source": "test",
        },
        format="json",
    )
    assert resp.status_code == 201
    item_id = resp.json()["id"]

    resp = client.post(
        f"/carbon-api/ai/knowledge/items/{item_id}/revoke/",
        {"reason": "stale"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["revoked"] is True
    item = KnowledgeItem.objects.get(pk=item_id)
    assert item.review_status == REVIEW_DEPRECATED
    assert item.effective_end is not None


@pytest.mark.django_db
def test_prompt_versions_list(admin_client):
    client, _ = admin_client
    resp = client.get("/carbon-api/ai/pulse/control/prompts/versions/")
    assert resp.status_code == 200
    assert "results" in resp.json()
