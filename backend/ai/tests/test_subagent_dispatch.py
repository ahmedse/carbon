"""Tests for Wave I4-B — user-dispatched read-only subagent dispatch service."""
import pytest

from accounts.models import User
from ai.models import AIConversation, AISubagent
from ai.subagent_service import (
    SubagentService,
    SUBAGENT_READONLY_TOOLS,
    MUTATION_TOOLS_DENIED,
    resolve_subagent_tool_definitions,
    serialize_subagent,
)


@pytest.fixture
def user(db):
    return User.objects.create_user(username="subagent-user", password="secret123")


@pytest.fixture
def conversation(db, user):
    return AIConversation.objects.create(user=user, conversation_type="chat")


def test_dispatch_creates_worker_subagent(user, conversation):
    sub = SubagentService().dispatch_subagent(
        user, conversation, name="auditor", brief="audit DQ rules", run_async=False
    )
    assert sub.is_worker is True
    assert sub.status == "pending"
    assert sub.host_user_id == str(user.pk)
    assert sub.parent_conversation_id == str(conversation.id)
    assert sub.app_identifier == "carbon"


def test_readonly_allowlist_excludes_all_mutations():
    assert SUBAGENT_READONLY_TOOLS.isdisjoint(MUTATION_TOOLS_DENIED)
    for name in MUTATION_TOOLS_DENIED:
        assert name not in SUBAGENT_READONLY_TOOLS


def test_resolve_subagent_tool_definitions_are_readonly():
    defs = resolve_subagent_tool_definitions()
    names = {d["function"]["name"] for d in defs}
    assert names <= SUBAGENT_READONLY_TOOLS
    assert names.isdisjoint(MUTATION_TOOLS_DENIED)
    assert "web_research" in names


def test_run_subagent_aggregates_result(user, conversation, monkeypatch):
    sub = SubagentService().dispatch_subagent(
        user, conversation, name="auditor", brief="audit DQ rules", run_async=False
    )

    async def fake(self, sub, messages, tool_defs):
        return {"content": "x" * 500, "input_tokens": 10, "output_tokens": 20}

    monkeypatch.setattr(SubagentService, "_invoke_llm", fake)
    sub = SubagentService().run_subagent(sub.id)
    assert sub.status == "completed"
    assert sub.result_summary == ("x" * 500)[:200].strip()
    assert sub.result_detail == ("x" * 500)[:2000]
    assert sub.tokens_used == 30
    assert sub.completed_at is not None


def test_run_subagent_failure_marks_failed(user, conversation, monkeypatch):
    sub = SubagentService().dispatch_subagent(
        user, conversation, name="auditor", brief="audit DQ rules", run_async=False
    )

    async def fake(self, *a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(SubagentService, "_invoke_llm", fake)
    sub = SubagentService().run_subagent(sub.id)
    assert sub.status == "failed"
    assert "boom" in (sub.error or "")


def test_get_subagent_is_cbac_scoped(user, conversation):
    sub = SubagentService().dispatch_subagent(
        user, conversation, name="auditor", brief="audit DQ rules", run_async=False
    )
    assert SubagentService().get_subagent(user, conversation.id, sub.id) is not None

    other = User.objects.create_user(username="other", password="x")
    assert SubagentService().get_subagent(other, conversation.id, sub.id) is None


def test_serialize_subagent_shape(user, conversation):
    sub = SubagentService().dispatch_subagent(
        user, conversation, name="auditor", brief="audit DQ rules", run_async=False
    )
    payload = serialize_subagent(sub)
    assert {"name", "status", "is_worker", "result_summary", "tool_allowlist"} <= set(payload.keys())
