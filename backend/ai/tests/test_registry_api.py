"""P3-05a — Process Registry REST API tests.

Covers the full ``ProcessDefinition`` lifecycle exposed by
``ai.registry_api.RegistryViewSet``: create/edit, submit → publish →
deprecate, capability gating (CBAC), self-publish refusal, diff vs active,
the per-step autonomy dial, and the kill switch. Uses the pilot
``dq.rule.release`` definition loaded from the domain pack (same helper as
``test_process_schema.py``).
"""
from __future__ import annotations

import pytest
from django.urls import reverse

from accounts.constants import (
    AI_AUDITOR_GROUP,
    AI_OPERATOR_GROUP,
    AI_PROCESS_OWNER_GROUP,
    AI_PUBLISHER_GROUP,
)
from ai.engine.ports.domain import load_domain_pack
from ai.models.capability import default_pack_dir
from ai.tests.conftest import grant_role, make_user

pytestmark = pytest.mark.django_db

PACK_DIR = default_pack_dir()
PROCESS_ID = "dq.rule.release"


def _pilot_document(**overrides) -> dict:
    """Load the pilot definition and apply field overrides (e.g. version)."""
    pack = load_domain_pack(PACK_DIR)
    doc = next(p for p in pack.processes() if p.get("id") == PROCESS_ID)
    result = dict(doc)
    result.update(overrides)
    return result


def _url(name: str, **kwargs) -> str:
    return reverse(f"ai-registry-{name}", kwargs=kwargs)


def _owner(username: str = "owner"):
    user = make_user(username)
    grant_role(user, group_name=AI_PROCESS_OWNER_GROUP)
    return user


def _publisher(username: str = "publisher"):
    user = make_user(username)
    grant_role(user, group_name=AI_PUBLISHER_GROUP)
    return user


def _auditor(username: str = "auditor"):
    user = make_user(username)
    grant_role(user, group_name=AI_AUDITOR_GROUP)
    return user


def _operator(username: str = "operator"):
    user = make_user(username)
    grant_role(user, group_name=AI_OPERATOR_GROUP)
    return user


def _create_draft(api_client, user, document=None):
    api_client.force_authenticate(user=user)
    return api_client.post(
        _url("list"), data=document or _pilot_document(), format="json"
    )


# ── auth / capability gating ───────────────────────────────────────────────


def test_unauthenticated_list_returns_401(api_client):
    resp = api_client.get(_url("list"))
    assert resp.status_code == 401


def test_create_requires_process_owner(api_client):
    plain = make_user("plain")
    api_client.force_authenticate(user=plain)
    resp = api_client.post(_url("list"), data=_pilot_document(), format="json")
    assert resp.status_code == 403


def test_read_requires_governance_capability(api_client):
    _create_draft(api_client, _owner())

    plain = make_user("plain2")
    api_client.force_authenticate(user=plain)
    assert api_client.get(_url("list")).status_code == 403
    assert api_client.get(_url("detail", pk=PROCESS_ID)).status_code == 403

    auditor = _auditor()
    api_client.force_authenticate(user=auditor)
    assert api_client.get(_url("list")).status_code == 200
    assert api_client.get(_url("detail", pk=PROCESS_ID)).status_code == 200
    # auditors are read-only — create is refused
    resp = api_client.post(_url("list"), data=_pilot_document(), format="json")
    assert resp.status_code == 403


# ── create ─────────────────────────────────────────────────────────────────


def test_create_draft_sets_owner_and_status(api_client):
    owner = _owner()
    resp = _create_draft(api_client, owner)
    assert resp.status_code == 201
    data = resp.json()
    assert data["process_id"] == PROCESS_ID
    assert data["status"] == "draft"
    assert data["owner"] == owner.username
    assert data["definition"]["status"] == "draft"
    assert data["definition"]["owner"] == owner.username
    assert data["kill_switch"] is False


def test_create_rejects_invalid_definition(api_client):
    owner = _owner()
    doc = _pilot_document()
    doc["steps"][0]["kind"] = "frobnicate"
    resp = _create_draft(api_client, owner, document=doc)
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid"


# ── list / retrieve ────────────────────────────────────────────────────────


def test_list_filters_by_process_and_status(api_client):
    owner = _owner()
    _create_draft(api_client, owner)
    api_client.force_authenticate(user=owner)

    resp = api_client.get(_url("list"), {"process_id": PROCESS_ID})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["process_id"] == PROCESS_ID
    assert rows[0]["status"] == "draft"

    resp = api_client.get(_url("list"), {"status": "active"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_retrieve_detail(api_client):
    owner = _owner()
    _create_draft(api_client, owner)
    api_client.force_authenticate(user=owner)

    resp = api_client.get(_url("detail", pk=PROCESS_ID))
    assert resp.status_code == 200
    data = resp.json()
    assert data["process_id"] == PROCESS_ID
    assert "definition" in data
    assert data["kill_switch"] is False


def test_unknown_process_returns_404(api_client):
    owner = _owner()
    api_client.force_authenticate(user=owner)
    assert api_client.get(_url("detail", pk="nope")).status_code == 404
    assert api_client.post(_url("submit", pk="nope")).status_code == 404
    assert api_client.get(_url("autonomy", pk="nope")).status_code == 404


# ── edit ───────────────────────────────────────────────────────────────────


def test_edit_draft_only(api_client):
    owner = _owner()
    _create_draft(api_client, owner)
    api_client.force_authenticate(user=owner)

    resp = api_client.patch(
        _url("detail", pk=PROCESS_ID),
        data={"version": "1.1"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["version"] == "1.1"

    # once submitted, drafts can no longer be edited
    api_client.post(_url("submit", pk=PROCESS_ID))
    resp = api_client.patch(
        _url("detail", pk=PROCESS_ID),
        data={"version": "1.2"},
        format="json",
    )
    assert resp.status_code == 400


# ── lifecycle transitions ──────────────────────────────────────────────────


def test_lifecycle_transitions(api_client):
    owner = _owner()
    publisher = _publisher("pub1")
    _create_draft(api_client, owner)
    api_client.force_authenticate(user=owner)

    resp = api_client.post(_url("submit", pk=PROCESS_ID))
    assert resp.status_code == 200
    assert resp.json()["status"] == "review"

    api_client.force_authenticate(user=publisher)
    resp = api_client.post(_url("publish", pk=PROCESS_ID))
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"

    resp = api_client.post(_url("deprecate", pk=PROCESS_ID))
    assert resp.status_code == 200
    assert resp.json()["status"] == "deprecated"


def test_illegal_transitions_return_400(api_client):
    owner = _owner()
    grant_role(owner, group_name=AI_PUBLISHER_GROUP)  # authorized to publish/deprecate
    _create_draft(api_client, owner)
    api_client.force_authenticate(user=owner)

    assert api_client.post(_url("publish", pk=PROCESS_ID)).status_code == 400
    assert api_client.post(_url("deprecate", pk=PROCESS_ID)).status_code == 400

    api_client.post(_url("submit", pk=PROCESS_ID))
    assert api_client.post(_url("submit", pk=PROCESS_ID)).status_code == 400


# ── self-publish refusal ───────────────────────────────────────────────────


def test_self_publish_refused(api_client):
    author = _owner("author")
    grant_role(author, group_name=AI_PUBLISHER_GROUP)  # author also a publisher
    _create_draft(api_client, author)
    api_client.force_authenticate(user=author)
    api_client.post(_url("submit", pk=PROCESS_ID))

    resp = api_client.post(_url("publish", pk=PROCESS_ID))
    assert resp.status_code == 403
    assert resp.json()["error"] == "forbidden"


def test_superuser_can_self_publish(api_client):
    root = make_user("root", superuser=True)
    _create_draft(api_client, root)
    api_client.force_authenticate(user=root)
    api_client.post(_url("submit", pk=PROCESS_ID))

    resp = api_client.post(_url("publish", pk=PROCESS_ID))
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


# ── diff ───────────────────────────────────────────────────────────────────


def test_diff_vs_active(api_client):
    owner = _owner()
    publisher = _publisher("pub2")
    _create_draft(api_client, owner)
    api_client.force_authenticate(user=owner)
    api_client.post(_url("submit", pk=PROCESS_ID))

    api_client.force_authenticate(user=publisher)
    api_client.post(_url("publish", pk=PROCESS_ID))

    # a newer draft version introduces a change
    _create_draft(api_client, owner, document=_pilot_document(version="2.0"))
    api_client.force_authenticate(user=owner)

    resp = api_client.get(_url("diff", pk=PROCESS_ID))
    assert resp.status_code == 200
    data = resp.json()
    assert data["process_id"] == PROCESS_ID
    assert data["from_version"] == "1.0"
    assert data["to_version"] == "2.0"
    assert data["added"] == {}
    assert data["removed"] == {}
    assert data["changed"]["version"] == {"from": "1.0", "to": "2.0"}


def test_diff_no_active_version(api_client):
    owner = _owner()
    _create_draft(api_client, owner)
    api_client.force_authenticate(user=owner)

    resp = api_client.get(_url("diff", pk=PROCESS_ID))
    assert resp.status_code == 200
    assert resp.json() == {"diff": None, "reason": "no_active_version"}


# ── autonomy dial ──────────────────────────────────────────────────────────


def test_autonomy_dial_get_and_patch(api_client):
    owner = _owner()
    _create_draft(api_client, owner)
    api_client.force_authenticate(user=owner)

    resp = api_client.get(_url("autonomy", pk=PROCESS_ID))
    assert resp.status_code == 200
    assert resp.json()["validate"] == "act_notify"
    assert resp.json()["review"] == "human_only"

    resp = api_client.patch(
        _url("autonomy", pk=PROCESS_ID),
        data={"validate": "act_silent"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["validate"] == "act_silent"

    # persisted on the definition
    resp = api_client.get(_url("autonomy", pk=PROCESS_ID))
    assert resp.json()["validate"] == "act_silent"


def test_autonomy_rejects_unknown_step_and_invalid_value(api_client):
    owner = _owner()
    _create_draft(api_client, owner)
    api_client.force_authenticate(user=owner)

    resp = api_client.patch(
        _url("autonomy", pk=PROCESS_ID),
        data={"ghost": "observe"},
        format="json",
    )
    assert resp.status_code == 400

    resp = api_client.patch(
        _url("autonomy", pk=PROCESS_ID),
        data={"validate": "autopilot"},
        format="json",
    )
    assert resp.status_code == 400


# ── kill switch ────────────────────────────────────────────────────────────


def test_kill_switch_round_trip(api_client):
    owner = _owner()
    operator = _operator("op1")
    _create_draft(api_client, owner)

    api_client.force_authenticate(user=operator)
    resp = api_client.post(
        _url("kill", pk=PROCESS_ID), data={"enabled": True}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json() == {"process_id": PROCESS_ID, "kill_switch": True}

    api_client.force_authenticate(user=owner)
    resp = api_client.get(_url("detail", pk=PROCESS_ID))
    assert resp.json()["kill_switch"] is True

    api_client.force_authenticate(user=operator)
    resp = api_client.post(
        _url("kill", pk=PROCESS_ID), data={"enabled": False}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["kill_switch"] is False


def test_kill_requires_operator_or_owner(api_client):
    owner = _owner()
    publisher = _publisher("pub3")
    _create_draft(api_client, owner)

    api_client.force_authenticate(user=publisher)
    resp = api_client.post(
        _url("kill", pk=PROCESS_ID), data={"enabled": True}, format="json"
    )
    assert resp.status_code == 403
