from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from accounts.models import User
from ai.intelligence import CarbonIntelligence
from ai.models import AIArtifact, AIConversation, AIMessage
from core.models import Module
from mdm.models import OrgUnit


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="ai-gov-owner", password="secret123")


@pytest.fixture
def viewer(db):
    return User.objects.create_user(username="ai-gov-viewer", password="secret123")


@pytest.fixture
def outsider(db):
    return User.objects.create_user(username="ai-gov-outsider", password="secret123")


@pytest.fixture
def shared_org(db, create_scoped_role, owner, viewer):
    org = OrgUnit.objects.create(name="AI Governance Org", slug="ai-gov-org")
    create_scoped_role(owner, "viewers_group", org_unit=org)
    create_scoped_role(viewer, "viewers_group", org_unit=org)
    return org


@pytest.fixture
def shared_conversation(db, owner, shared_org):
    ci = CarbonIntelligence()
    conversation = ci.create_conversation(owner, "chat", title="Shared thread")
    ci.update_conversation(owner, conversation["id"], visibility="shared")
    return AIConversation.objects.get(id=conversation["id"])


def _conversation_detail_url(conversation) -> str:
    return reverse("ai-workspace-conversation-detail", kwargs={"pk": conversation.id})


def _conversation_export_url(conversation) -> str:
    return reverse("ai-workspace-conversation-export", kwargs={"pk": conversation.id})


def _artifact_list_url() -> str:
    return reverse("ai-workspace-artifact-list")


def _artifact_detail_url(artifact) -> str:
    return reverse("ai-workspace-artifact-detail", kwargs={"pk": artifact.id})


@pytest.mark.django_db
def test_shared_conversation_visible_to_same_org_and_hidden_outside(shared_conversation, owner, viewer, outsider):
    ci = CarbonIntelligence()

    shared = ci.get_conversation(viewer, str(shared_conversation.id))
    assert shared["id"] == str(shared_conversation.id)

    exported = ci.export_conversation(viewer, str(shared_conversation.id), fmt="json")
    assert exported["format"] == "json"
    assert exported["content"]["conversation"]["id"] == str(shared_conversation.id)

    with pytest.raises(ValueError):
        ci.get_conversation(outsider, str(shared_conversation.id))


@pytest.mark.django_db
def test_shared_conversation_delete_requires_manage_console(shared_conversation, viewer):
    ci = CarbonIntelligence()

    with pytest.raises(PermissionDenied):
        ci.delete_conversation(viewer, str(shared_conversation.id))

    manager = User.objects.create_superuser(username="ai-gov-manager", password="secret123")
    result = ci.delete_conversation(manager, str(shared_conversation.id))
    assert result["deleted"] == str(shared_conversation.id)


@pytest.mark.django_db
def test_message_provenance_is_serialized(owner, shared_org):
    conversation = AIConversation.objects.create(
        user=owner,
        title="Provenance",
        conversation_type="chat",
        visibility="private",
        scope_json={"org_unit_ids": [str(shared_org.id)]},
    )
    message = AIMessage.objects.create(
        conversation=conversation,
        role="assistant",
        content="Answer",
        metadata_json={
            "guard_results": ["scope"],
            "engine_turn_id": "turn-7",
            "context_snapshot": {"budget": {"t1": 1}},
        },
        token_usage_json={"model": "gpt-4.1-mini"},
        provider_model="gpt-4.1-mini",
    )

    serialized = CarbonIntelligence().get_conversation(owner, str(conversation.id))
    provenance = serialized["messages"][0]["provenance"]

    assert provenance["model"] == "gpt-4.1-mini"
    assert provenance["guard_results"] == ["scope"]
    assert provenance["engine_turn_id"] == "turn-7"
    assert provenance["context_snapshot"] == {"budget": {"t1": 1}}


@pytest.mark.django_db
def test_artifact_crud_and_shared_visibility(owner, viewer, shared_org):
    ci = CarbonIntelligence()
    conversation = AIConversation.objects.create(
        user=owner,
        title="Artifacts",
        conversation_type="chat",
        visibility="private",
        scope_json={"org_unit_ids": [str(shared_org.id)]},
    )
    ci.update_conversation(owner, str(conversation.id), visibility="shared")

    shared_artifact = ci.create_artifact(
        owner,
        str(conversation.id),
        title="Shared report",
        artifact_type="report",
        content_json={"status": "ok"},
        visibility="shared",
    )
    assert shared_artifact["visibility"] == "shared"

    client = APIClient()
    client.force_authenticate(user=viewer)

    list_response = client.get(_artifact_list_url())
    assert list_response.status_code == 200
    assert any(item["id"] == shared_artifact["id"] for item in list_response.data)

    detail_response = client.get(_artifact_detail_url(AIArtifact.objects.get(id=shared_artifact["id"])))
    assert detail_response.status_code == 200
    assert detail_response.data["title"] == "Shared report"

    owner_client = APIClient()
    owner_client.force_authenticate(user=owner)
    artifact = AIArtifact.objects.get(id=shared_artifact["id"])

    patch_response = owner_client.patch(
        _artifact_detail_url(artifact),
        {"title": "Updated report"},
        format="json",
    )
    assert patch_response.status_code == 200
    assert patch_response.data["title"] == "Updated report"

    delete_response = owner_client.delete(_artifact_detail_url(artifact))
    assert delete_response.status_code == 200
    assert delete_response.data["deleted"] == shared_artifact["id"]
