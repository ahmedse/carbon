"""P3-06 — ApprovalGrant model + boundary grant stage (host-side).

Covers the durable business-approval concept and its strict separation from the
other two authorization concepts:

* **authorization** — :mod:`ai.pdp` (default-deny, stage 6)
* **business approval** — :class:`ai.models.approval.ApprovalGrant` (stage 8)
* **user consent** — ``CommandBoundary`` stage 7 (RULE_21)

A grant pins the exact material effect: any change to ``process_version``,
``capability_version``, ``canonical_args``, ``object_revisions``, or
``evidence_digest`` — or expiry — invalidates it (fail-closed).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from asgiref.sync import sync_to_async
from django.utils import timezone

from ai.command_boundary import Command, CommandBoundary
from ai.engine.ports import Decision
from ai.grant import GRANT_REFUSAL_REASON, resolve_grant
from ai.models.approval import (
    STATUS_ACTIVE,
    STATUS_REVOKED,
    ApprovalGrant,
    canonicalize_args,
)
from ai.models.pdp import PolicyDecisionRow
from ai.pdp import PDP
from ai.protocol import Scope

pytestmark = pytest.mark.django_db(transaction=True)


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_grant(**overrides: Any) -> ApprovalGrant:
    base: dict[str, Any] = dict(
        capability="ai:publisher",
        process_version="v3",
        capability_version="c1",
        canonical_args=canonicalize_args({"audience": "public"}),
        object_revisions={"rule-1": 7},
        evidence_digest="sha256:abc",
        expires_at=timezone.now() + timedelta(hours=1),
        status=STATUS_ACTIVE,
        granted_by="policy_owner@example.com",
    )
    base.update(overrides)
    return ApprovalGrant.objects.create(**base)


async def _amake_grant(**overrides: Any) -> ApprovalGrant:
    return await sync_to_async(_make_grant, thread_sensitive=True)(**overrides)


async def _aquery(**overrides: Any) -> ApprovalGrant | None:
    return await sync_to_async(_query, thread_sensitive=True)(**overrides)


def _query(**overrides: Any) -> ApprovalGrant | None:
    base: dict[str, Any] = dict(
        capability="ai:publisher",
        process_version="v3",
        capability_version="c1",
        canonical_args=canonicalize_args({"audience": "public"}),
        object_revisions={"rule-1": 7},
        evidence_digest="sha256:abc",
    )
    base.update(overrides)
    return ApprovalGrant.find_active(**base)


def _make_command(**overrides: Any) -> Command:
    scope = Scope(
        user_identifier="u1",
        org_unit_ids=["*"],
        module_ids=["*"],
        is_superuser=True,
    )
    base: dict[str, Any] = dict(
        principal="alice-grant",
        scope=scope,
        action="read",
        tool="read",
        params={"audience": "public"},
        objects=["tbl"],
        requires_confirmation=False,
        requires_grant=True,
        capability="ai:publisher",
        process_version="v3",
        capability_version="c1",
        object_revisions={"rule-1": 7},
        evidence_digest="sha256:abc",
        autonomy="human_only",
    )
    base.update(overrides)
    return Command(**base)


class _CountingExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, command: Command) -> Any:
        self.calls += 1
        return {"ok": True}


# ── canonicalize_args ─────────────────────────────────────────────────────

def test_canonicalize_args_is_deterministic():
    a = canonicalize_args({"b": 1, "a": {"z": 2, "y": 3}})
    b = canonicalize_args({"a": {"y": 3, "z": 2}, "b": 1})
    assert a == b
    assert list(a.keys()) == ["a", "b"]
    assert list(a["a"].keys()) == ["y", "z"]


def test_canonicalize_args_coerces_non_string_keys():
    assert canonicalize_args({1: "x", 2: "y"}) == {"1": "x", "2": "y"}
    assert canonicalize_args([{"b": 1, "a": 2}]) == [{"a": 2, "b": 1}]


# ── ApprovalGrant.find_active (fail-closed invalidation) ─────────────────

def test_find_active_exact_match():
    grant = _make_grant()
    found = _query()
    assert found is not None
    assert found.id == grant.id
    assert found.granted_by == "policy_owner@example.com"


def test_revision_pinning_revision_7_does_not_authorize_8():
    _make_grant(object_revisions={"rule-1": 7})
    assert _query(object_revisions={"rule-1": 7}) is not None
    assert _query(object_revisions={"rule-1": 8}) is None


def test_process_version_is_pinned():
    _make_grant(process_version="v3")
    assert _query(process_version="v3") is not None
    assert _query(process_version="v4") is None


def test_capability_version_is_pinned():
    _make_grant(capability_version="c1")
    assert _query(capability_version="c1") is not None
    assert _query(capability_version="c2") is None


def test_capability_mismatch_refuses():
    _make_grant(capability="ai:publisher")
    assert _query(capability="ai:operator") is None


def test_evidence_digest_is_pinned():
    _make_grant(evidence_digest="sha256:abc")
    assert _query(evidence_digest="sha256:abc") is not None
    assert _query(evidence_digest="sha256:def") is None


def test_object_identity_is_pinned():
    _make_grant(object_id="doc-1", object_type="report")
    assert _query(object_id="doc-1", object_type="report") is not None
    assert _query(object_id="doc-2", object_type="report") is None


def test_expired_grant_is_inert():
    _make_grant(expires_at=timezone.now() - timedelta(seconds=1))
    assert _query() is None


def test_revoked_grant_is_inert():
    grant = _make_grant()
    grant.revoke()
    assert grant.status == STATUS_REVOKED
    assert grant.revoked_at is not None
    assert _query() is None


# ── Three-concept separation (PDP vs grant vs consent) ───────────────────

@pytest.mark.asyncio
async def test_matching_grant_allows_execution():
    await _amake_grant()
    executor = _CountingExecutor()
    boundary = CommandBoundary(
        pdp=PDP(),
        grant_resolver=resolve_grant,
        tool_catalog={"read": {}},
        executor=executor,
    )
    outcome = await boundary.execute(_make_command())
    assert outcome.status == "executed"
    assert executor.calls == 1


@pytest.mark.asyncio
async def test_refused_grant_yields_pdp_allow_row_plus_grant_refuse_row():
    # No grant minted → authorization (PDP) allows, business approval refuses.
    boundary = CommandBoundary(
        pdp=PDP(),
        grant_resolver=resolve_grant,
        tool_catalog={"read": {}},
        executor=_CountingExecutor(),
    )
    outcome = await boundary.execute(_make_command())

    assert outcome.status == "refused"
    assert outcome.stages[-1] == "grant"
    assert "ApprovalGrant" in (outcome.error or "")

    rows = await sync_to_async(list, thread_sensitive=True)(
        PolicyDecisionRow.objects.filter(principal="alice-grant").order_by("created_at")
    )
    stages = {row.stage for row in rows}
    assert {"pdp", "grant"} <= stages

    pdp_row = next(row for row in rows if row.stage == "pdp")
    grant_row = next(row for row in rows if row.stage == "grant")

    # Authorization (PDP) allowed; business approval (grant) refused — the two
    # are distinct code paths and the refusal is attributed to the grant stage.
    assert pdp_row.decision == Decision.ALLOW.value
    assert pdp_row.policy_version == "pdp-v1.0"
    assert grant_row.decision == Decision.REFUSE.value
    assert grant_row.reason == GRANT_REFUSAL_REASON
    assert grant_row.policy_version == "grant"


@pytest.mark.asyncio
async def test_grant_refusal_is_distinct_from_consent_refusal():
    # A command that needs consent but supplies no token refuses at the consent
    # stage (stage 7) — never at the grant stage, even with a matching grant.
    await _amake_grant()
    boundary = CommandBoundary(
        pdp=PDP(),
        grant_resolver=resolve_grant,
        tool_catalog={"read": {}},
        executor=_CountingExecutor(),
    )
    outcome = await boundary.execute(
        _make_command(requires_confirmation=True, confirmation_token=None)
    )
    assert outcome.status == "refused"
    assert outcome.stages[-1] == "consent"
    assert "confirmation_token" in (outcome.error or "")
