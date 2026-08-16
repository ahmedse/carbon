"""Manifest-driven conversation-type registry — regression tests.

Closes the gap where a domain manifest could declare task types
(``investigate`` / ``nl_rule_test`` / ``report_draft``) that the workspace
conversation layer would reject with a 400 because its ChoiceField hard-coded
only five types. Covers:

  * ``supported_conversation_types()`` = core types ∪ every manifest's types.
  * The create/list serializers accept any declared type and reject unknowns.
  * Built-in domain apps are auto-registered at startup (AIConfig.ready ->
    register_builtin_domains) so the manifest API and per-domain injection
    work in production — not just in tests that import ``ai.domain.emissions``.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from ai.domain_protocol import (
    CORE_CONVERSATION_TYPES,
    supported_conversation_types,
)


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="ct-registry-worker", password="secret123")


@pytest.fixture
def authed_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _create_url() -> str:
    return reverse("ai-workspace-conversation-list")


# ── Registry shape ────────────────────────────────────────────────────────


def test_supported_types_includes_core_types():
    allowed = supported_conversation_types()
    assert CORE_CONVERSATION_TYPES <= allowed


def test_supported_types_includes_emissions_manifest_types():
    allowed = supported_conversation_types()
    for task_type in ("investigate", "nl_rule_test", "report_draft"):
        assert task_type in allowed


# ── Auto-registration at startup ──────────────────────────────────────────
# NOTE: this module deliberately does NOT import ai.domain.emissions/water.
# Registration must come from AIConfig.ready() -> register_builtin_domains().


def test_domains_auto_registered_without_direct_import():
    from ai.domain_protocol import all_manifests, has_domain, list_domains

    assert has_domain("emissions") is True
    assert has_domain("water") is True
    assert "emissions" in list_domains()

    ids = [m["app_identifier"] for m in all_manifests()]
    assert "emissions" in ids


# ── Create conversation accepts manifest-declared types ───────────────────


@pytest.mark.django_db
@pytest.mark.parametrize("task_type", ["investigate", "nl_rule_test", "report_draft"])
def test_create_conversation_accepts_manifest_task_type(authed_client, task_type):
    resp = authed_client.post(
        _create_url(),
        {"conversation_type": task_type, "app_identifier": "emissions"},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["conversation_type"] == task_type
    assert resp.data["app_identifier"] == "emissions"


@pytest.mark.django_db
def test_create_conversation_rejects_unknown_type(authed_client):
    resp = authed_client.post(
        _create_url(),
        {"conversation_type": "definitely_not_a_type"},
        format="json",
    )
    assert resp.status_code == 400


# ── List filter accepts manifest-declared types ───────────────────────────


@pytest.mark.django_db
def test_list_filter_accepts_manifest_type(authed_client):
    resp = authed_client.get(_create_url(), {"conversation_type": "report_draft"})
    assert resp.status_code == 200
