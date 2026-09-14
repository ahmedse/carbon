"""P4-04 — executable-skill ``allowed_tools`` enforcement at the PDP (stage 6).

Covers:

  * ``process_ref`` parsing/formatting (strict, fail-closed).
  * ``ExecutableSkillBody`` validation (``allowed_tools`` normalized; malformed
    ``process_ref`` → pydantic ``ValidationError``).
  * The ``deny-unauthorized-skill-tool`` mandatory policy: a skill declaring a
    tool the principal is not authorized to use is refused at the PDP (not a
    pre-boundary guard), and a persisted ``PolicyDecisionRow`` records the
    refusal.
  * Backward compatibility: a skill with no ``allowed_tools`` still permits.

Run (from ``backend/``)::

    python -m pytest ai/tests/test_skill_allowed_tools_pdp.py -q -m "not live"
"""
from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from accounts.models import User
from ai.engine.skills.schema import (
    ExecutableSkillBody,
    ProcessRef,
    format_process_ref,
    parse_process_ref,
)
from ai.host_executor import CarbonHostExecutor
from ai.models.capability import Capability
from ai.models.core import Run
from ai.models.pdp import PolicyDecisionRow
from ai.models.process import ProcessDefinition
from ai.pdp import TOOL_CAPABILITY_MAP, authorized_tool_names
from ai.plans_service import PlansService


# ── Pure: process_ref parsing / formatting ───────────────────────────────


def test_parse_process_ref_accepts_id_and_version():
    assert parse_process_ref("foo") == ProcessRef("foo", None)
    assert parse_process_ref("foo@1.0") == ProcessRef("foo", "1.0")


@pytest.mark.parametrize(
    "bad",
    ["", "@1.0", "foo@", "foo@1@2", " foo@1.0", "foo@ 1.0", None, 123],
)
def test_parse_process_ref_rejects_malformed(bad):
    with pytest.raises(ValueError):
        parse_process_ref(bad)


def test_format_process_ref_round_trip():
    assert format_process_ref(ProcessRef("foo")) == "foo"
    assert format_process_ref(ProcessRef("foo", "1.0")) == "foo@1.0"
    assert format_process_ref(parse_process_ref("foo@2.0")) == "foo@2.0"


def test_authorized_tool_names():
    assert authorized_tool_names(frozenset()) == frozenset()
    assert authorized_tool_names({"ai:code_execute"}) == frozenset({"code_execute"})
    assert authorized_tool_names({"ai:web_search"}) == frozenset(
        {"web_search", "web_research"}
    )
    assert authorized_tool_names({"*"}) == frozenset(TOOL_CAPABILITY_MAP.keys())


# ── Pure: ExecutableSkillBody validation ─────────────────────────────────


def test_executable_skill_body_validates_process_ref():
    body = ExecutableSkillBody(
        process_ref="foo@1.0",
        allowed_tools=["code_execute", "code_execute", "web_search"],
    )
    assert body.process_ref == "foo@1.0"
    assert body.allowed_tools == ["code_execute", "web_search"]

    with pytest.raises(ValidationError):
        ExecutableSkillBody(process_ref="@1.0")

    with pytest.raises(ValidationError):
        ExecutableSkillBody(process_ref="foo@1.0", allowed_tools=[""])


# ── Seeding helpers ──────────────────────────────────────────────────────


def _seed_process(process_id: str, version: str, *, steps: list) -> None:
    ProcessDefinition.objects.create(
        process_id=process_id,
        version=version,
        owner="owner",
        status="active",
        definition={
            "id": process_id,
            "version": version,
            "owner": "owner",
            "status": "active",
            "steps": steps,
        },
    )


def _seed_exec_capability() -> None:
    Capability.objects.create(
        capability_id="dq.rule.validate",
        host_action="dq.validate_rule",
        approval_requirements={},
        version="1.0",
    )


def _make_executor(user: User) -> CarbonHostExecutor:
    return CarbonHostExecutor(
        db=None,
        instance_config={},
        user_token=f"inproc:carbon:{user.username}",
        host_user_id=str(user.pk),
    )


def _invoke(ex: CarbonHostExecutor, user: User, *, allowed_tools=None) -> dict:
    return asyncio.run(
        ex.invoke_skill_via_boundary(
            skill_name="release_rule",
            process_ref="test.exec@1.0",
            args={"rule_id": "r1"},
            instance_id="i1",
            host_user_id=str(user.pk),
            author_user_id=str(user.pk),
            allowed_tools=allowed_tools,
        )
    )


# ── PDP enforcement at the invoke seam ───────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_skill_declares_disallowed_tool_refused_at_pdp(monkeypatch):
    user = User.objects.create_user(username="noexec", password="secret123")
    _seed_process(
        "test.exec", "1.0",
        steps=[
            {
                "id": "validate",
                "kind": "command",
                "capability": "dq.rule.validate",
                "autonomy": "act_notify",
                "consent": False,
            }
        ],
    )
    _seed_exec_capability()

    # The run-creation path must never be reached: the refusal is a stage-6
    # PDP decision, not a pre-boundary guard.
    def _fail_if_executed(self, user, brief, conversation_id=""):
        raise AssertionError("PlansService.create_plan must not run on a refused invoke")

    monkeypatch.setattr(PlansService, "create_plan", _fail_if_executed)

    ex = _make_executor(user)
    result = _invoke(ex, user, allowed_tools=["code_execute"])

    assert result["status"] == "refused"
    assert result["pdp_decision"] == "refuse"
    assert result["error"]

    rows = list(PolicyDecisionRow.objects.filter(action="invoke_skill"))
    assert len(rows) == 1
    assert rows[0].principal == str(user.pk)
    assert rows[0].decision == "refuse"
    assert rows[0].stage == "pdp"
    assert "code_execute" in rows[0].reason
    assert "deny-unauthorized-skill-tool" in rows[0].reason

    # Nothing was executed.
    assert Run.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_skill_declares_allowed_tool_permitted(monkeypatch):
    user = User.objects.create_user(username="admin", password="secret123")
    user.is_staff = True
    user.is_superuser = True
    user.save()

    _seed_process(
        "test.exec", "1.0",
        steps=[
            {
                "id": "validate",
                "kind": "command",
                "capability": "dq.rule.validate",
                "autonomy": "act_notify",
                "consent": False,
            }
        ],
    )
    _seed_exec_capability()

    def fake_create_plan(self, user, brief, conversation_id=""):
        run = Run.objects.create(
            instance_id="plan-instance",
            conversation_id=conversation_id or "",
            user_message=brief,
            host_user_id=str(user.pk),
            status="pending_approval",
        )
        return {"id": run.id, "status": run.status, "brief": brief}

    monkeypatch.setattr(PlansService, "create_plan", fake_create_plan)

    ex = _make_executor(user)
    result = _invoke(ex, user, allowed_tools=["code_execute"])

    assert result["status"] == "executed"
    assert result["pdp_decision"] == "allow"
    assert result["error"] is None

    rows = list(PolicyDecisionRow.objects.filter(action="invoke_skill"))
    assert len(rows) == 1
    assert rows[0].decision == "allow"


@pytest.mark.django_db(transaction=True)
def test_skill_no_allowed_tools_unchanged(monkeypatch):
    user = User.objects.create_user(username="invoker", password="secret123")
    _seed_process(
        "test.exec", "1.0",
        steps=[
            {
                "id": "validate",
                "kind": "command",
                "capability": "dq.rule.validate",
                "autonomy": "act_notify",
                "consent": False,
            }
        ],
    )
    _seed_exec_capability()

    def fake_create_plan(self, user, brief, conversation_id=""):
        run = Run.objects.create(
            instance_id="plan-instance",
            conversation_id=conversation_id or "",
            user_message=brief,
            host_user_id=str(user.pk),
            status="pending_approval",
        )
        return {"id": run.id, "status": run.status, "brief": brief}

    monkeypatch.setattr(PlansService, "create_plan", fake_create_plan)

    ex = _make_executor(user)
    # No allowed_tools declared → nothing to enforce → permits (backward compat).
    result = _invoke(ex, user, allowed_tools=None)

    assert result["status"] == "executed"
    assert result["pdp_decision"] == "allow"
    assert result["error"] is None

    rows = list(PolicyDecisionRow.objects.filter(action="invoke_skill"))
    assert len(rows) == 1
    assert rows[0].decision == "allow"
