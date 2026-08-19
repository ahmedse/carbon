"""
Agent/Tool action execution seam tests — Sprint 19 W1-A.

Covers:
  - ``dispatch_action_stream`` bridge + clustered frame protocol (design §2.5):
    turn_start → tool_start → (tool_arg/tool_result when verbosity=full) →
    tool_end → turn_end, with ``(kind, value)`` tuple wire format.
  - Durable ``ToolExecution`` rows: running → completed|failed|stopped.
  - RULE_21: host-mutating tools stage via ``needs_confirmation`` —
    never auto-run.
  - Abort correctness (the acceptance bar): a mid-run ``GENERATIONS.cancel``
    yields ``tool_end{status:"stopped"}`` + ``turn_end{status:"stopped"}`` —
    never an ``error`` frame — with a ``stopped`` durable row, and the
    conversation is never left stuck in ``working``.
  - ``CarbonIntelligence.run_agent_action_stream`` persistence + finalization
    (user message, assistant message, AIGeneration lifecycle, quota gate).
  - SSE endpoint (``actions/stream``) contract + serializer validation.

Imports mirror the existing test suite: ``ai.*`` for the engine runtime and
intelligence, ``backend.ai.*`` for the protocol/provider layer.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from accounts.models import User
from ai.generation_registry import GENERATIONS
from ai.intelligence import CarbonIntelligence
from ai.models import AIConversation, AIMessage, AIGeneration
from ai.models.core import ToolExecution
from ai.usage_service import QuotaExceededError


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def user(db):
    return User.objects.create_user(username="action-worker", password="secret123")


def _make_conversation(user, conversation_type="chat", payload=None):
    return AIConversation.objects.create(
        user=user,
        title=conversation_type,
        conversation_type=conversation_type,
        task_payload_json=payload or {},
        scope_json={},
    )


@pytest.fixture
def tool_conv_id(db):
    """A unique conversation id for engine-level runs, with durable-row cleanup.

    Engine-level ``dispatch_action_stream`` writes ``ToolExecution`` rows from
    a worker thread on its own connection (autocommit), so those rows survive
    the test transaction's rollback — they must be deleted explicitly.
    """
    conv_id = f"test-{uuid.uuid4().hex[:12]}"

    yield conv_id

    ToolExecution.objects.filter(conversation_id=conv_id).delete()


def _fake_tool_executors(executors: dict, mcp_names=()):
    """Install fake async tool executors at the engine import point.

    ``_run_action_stream`` imports ``get_tool_executors`` / ``MCP_EXECUTORS``
    from ``ai.engine.agent.tools`` at call time, so monkeypatching the module
    attributes is sufficient (no import-time indirection to chase).
    ``mcp_names`` controls which of the executors are also advertised as MCP
    tools (drives the ``category`` classification in ``tool_start`` frames).
    """
    import ai.engine.agent.tools as tools

    async def fake_get_tool_executors():
        return dict(executors)

    def install(monkeypatch):
        monkeypatch.setattr(tools, "get_tool_executors", fake_get_tool_executors)
        monkeypatch.setattr(tools, "MCP_EXECUTORS", {
            name: fn for name, fn in executors.items() if name in mcp_names
        })
        return tools

    return install


def _fake_agent_registry(monkeypatch, agents: dict):
    """Install a fake AgentRegistry (avoid DB visibility across threads)."""
    import ai.engine.agent.registry as registry_mod

    class _FakeAgentRegistry:
        def __init__(self, db):
            self._db = db

        async def get_agent(self, instance_id, name):
            return agents.get(name)

    monkeypatch.setattr(registry_mod, "AgentRegistry", _FakeAgentRegistry)


# ── dispatch_action_stream — tool run ────────────────────────────────────


@pytest.mark.django_db
def test_dispatch_action_stream_tool_completed_frames_and_row(
    monkeypatch, tool_conv_id
):
    from ai.engine_runtime import dispatch_action_stream

    calls: list[dict] = []

    async def fake_tool(args):
        calls.append(args)
        return {"ok": True, "rows": 3}

    install = _fake_tool_executors({"fake_tool": fake_tool})
    install(monkeypatch)

    frames = list(
        dispatch_action_stream(
            {
                "conversation_id": tool_conv_id,
                "action_type": "tool",
                "tool": "fake_tool",
                "args": {"table": "sales"},
                "verbosity": "concise",
            }
        )
    )

    kinds = [kind for kind, _ in frames]
    assert kinds == [
        "frame",  # turn_start
        "frame",  # tool_start
        "frame",  # tool_end
        "frame",  # turn_end
        "done",
    ]
    turn_start = frames[0][1]
    assert turn_start["type"] == "turn_start"
    assert turn_start["turn_id"].startswith("turn-")
    assert turn_start["label"] == "Run tool fake_tool"
    assert turn_start["verbosity"] == "concise"

    tool_start = frames[1][1]
    assert tool_start["type"] == "tool_start"
    assert tool_start["step_id"] == 1
    assert tool_start["tool"] == "fake_tool"
    assert tool_start["category"] == "tool"

    tool_end = frames[2][1]
    assert tool_end["type"] == "tool_end"
    assert tool_end["status"] == "completed"

    turn_end = frames[3][1]
    assert turn_end["type"] == "turn_end"
    assert turn_end["status"] == "completed"

    assert frames[4] == ("done", {"status": "completed"})

    # The executor was called with the args dict + engine context keys.
    assert len(calls) == 1
    assert calls[0]["table"] == "sales"
    assert calls[0]["executor"] is not None
    assert calls[0]["conversation_id"] == tool_conv_id

    row = ToolExecution.objects.get(conversation_id=tool_conv_id)
    assert row.tool_name == "fake_tool"
    assert row.status == "completed"
    assert row.executed_at is not None


@pytest.mark.django_db
def test_dispatch_action_stream_full_verbosity_emits_arg_and_redacted_result(
    monkeypatch, tool_conv_id
):
    from ai.engine_runtime import dispatch_action_stream

    async def fake_tool(args):
        return {"ok": True, "api_key": "sk-secret-123", "rows": 1}

    install = _fake_tool_executors({"fake_tool": fake_tool})
    install(monkeypatch)

    frames = list(
        dispatch_action_stream(
            {
                "conversation_id": tool_conv_id,
                "action_type": "tool",
                "tool": "fake_tool",
                "args": {"table": "customers"},
                "verbosity": "full",
            }
        )
    )

    types = [f[1]["type"] for f in frames if f[0] == "frame"]
    assert types == [
        "turn_start",
        "tool_start",
        "tool_arg",
        "tool_result",
        "tool_end",
        "turn_end",
    ]

    arg_frame = next(f[1] for f in frames if f[1]["type"] == "tool_arg")
    assert arg_frame["args"] == {"table": "customers"}

    result_frame = next(f[1] for f in frames if f[1]["type"] == "tool_result")
    assert result_frame["result"]["ok"] is True
    assert result_frame["result"]["api_key"] == "[REDACTED]"


@pytest.mark.django_db
def test_dispatch_action_stream_mcp_category(monkeypatch, tool_conv_id):
    from ai.engine_runtime import dispatch_action_stream

    async def fake_tool(args):
        return {"ok": True}

    install = _fake_tool_executors(
        {"fake_mcp_tool": fake_tool}, mcp_names={"fake_mcp_tool"}
    )
    install(monkeypatch)

    frames = list(
        dispatch_action_stream(
            {
                "conversation_id": tool_conv_id,
                "action_type": "tool",
                "tool": "fake_mcp_tool",
                "args": {},
                "verbosity": "concise",
            }
        )
    )

    tool_start = next(
        f[1] for f in frames if f[1]["type"] == "tool_start"
    )
    assert tool_start["category"] == "mcp"


@pytest.mark.django_db
def test_dispatch_action_stream_tool_failed_yields_failed_row(
    monkeypatch, tool_conv_id
):
    from ai.engine_runtime import dispatch_action_stream

    async def fake_tool(args):
        return {"error": "rule engine rejected the payload"}

    install = _fake_tool_executors({"fake_tool": fake_tool})
    install(monkeypatch)

    frames = list(
        dispatch_action_stream(
            {
                "conversation_id": tool_conv_id,
                "action_type": "tool",
                "tool": "fake_tool",
                "args": {},
                "verbosity": "concise",
            }
        )
    )

    tool_end = next(f[1] for f in frames if f[1]["type"] == "tool_end")
    assert tool_end["status"] == "failed"

    turn_end = next(f[1] for f in frames if f[1]["type"] == "turn_end")
    assert turn_end["status"] == "failed"

    assert frames[-1] == ("done", {"status": "failed"})

    row = ToolExecution.objects.get(conversation_id=tool_conv_id)
    assert row.status == "failed"
    assert row.output["error"] == "rule engine rejected the payload"


@pytest.mark.django_db
def test_dispatch_action_stream_unknown_tool_fails(monkeypatch, tool_conv_id):
    from ai.engine_runtime import dispatch_action_stream

    install = _fake_tool_executors({})
    install(monkeypatch)

    frames = list(
        dispatch_action_stream(
            {
                "conversation_id": tool_conv_id,
                "action_type": "tool",
                "tool": "nope_tool",
                "args": {},
                "verbosity": "concise",
            }
        )
    )

    tool_end = next(f[1] for f in frames if f[1]["type"] == "tool_end")
    assert tool_end["status"] == "failed"
    assert frames[-1] == ("done", {"status": "failed"})

    row = ToolExecution.objects.get(conversation_id=tool_conv_id)
    assert row.status == "failed"


@pytest.mark.django_db
def test_dispatch_action_stream_requires_confirmation_stages_no_auto_run(
    monkeypatch, tool_conv_id
):
    from ai.engine_runtime import dispatch_action_stream

    calls: list[dict] = []

    async def fake_mutation(args):
        calls.append(args)
        return {
            "requires_confirmation": True,
            "execution_id": "exec-abc-123",
            "method": "POST",
            "endpoint": "/dq/rules",
            "confirmation_message": "Create DQ rule 'dup check' (validity)?",
        }

    install = _fake_tool_executors({"fake_mutation": fake_mutation})
    install(monkeypatch)

    frames = list(
        dispatch_action_stream(
            {
                "conversation_id": tool_conv_id,
                "action_type": "tool",
                "tool": "fake_mutation",
                "args": {"name": "dup check"},
                "verbosity": "concise",
            }
        )
    )

    tool_end = next(f[1] for f in frames if f[1]["type"] == "tool_end")
    assert tool_end["status"] == "needs_confirmation"
    assert tool_end["execution_id"] == "exec-abc-123"

    # Staged, not auto-run: exactly one call — the staging call itself.
    assert len(calls) == 1

    row = ToolExecution.objects.get(conversation_id=tool_conv_id)
    assert row.status == "needs_confirmation"
    assert row.output["execution_id"] == "exec-abc-123"


# ── dispatch_action_stream — agent run ───────────────────────────────────


@pytest.mark.django_db
def test_dispatch_action_stream_agent_runs_declared_tool_set(
    monkeypatch, tool_conv_id
):
    from ai.engine_runtime import dispatch_action_stream

    executed: list[str] = []

    async def tool_a(args):
        executed.append("tool_a")
        return {"ok": True}

    async def tool_b(args):
        executed.append("tool_b")
        return {"ok": True}

    install = _fake_tool_executors({"tool_a": tool_a, "tool_b": tool_b})
    install(monkeypatch)
    _fake_agent_registry(
        monkeypatch,
        {
            "data_sweeper": SimpleNamespace(
                role="Cleans data", tool_set_json=["tool_a", "tool_b"],
            )
        },
    )

    frames = list(
        dispatch_action_stream(
            {
                "conversation_id": tool_conv_id,
                "action_type": "agent",
                "agent": "data_sweeper",
                "args": {"table": "leads"},
                "verbosity": "concise",
            }
        )
    )

    turn_start = next(f[1] for f in frames if f[1]["type"] == "turn_start")
    assert turn_start["label"] == "Run agent data_sweeper"

    tool_starts = [
        f[1]
        for f in frames
        if isinstance(f[1], dict) and f[1].get("type") == "tool_start"
    ]
    assert [t["tool"] for t in tool_starts] == ["tool_a", "tool_b"]
    assert all(t["category"] == "agent" for t in tool_starts)

    turn_end = next(f[1] for f in frames if f[1]["type"] == "turn_end")
    assert turn_end["status"] == "completed"
    assert "2 step(s) completed" in turn_end["summary"]
    assert frames[-1] == ("done", {"status": "completed"})

    assert executed == ["tool_a", "tool_b"]
    # UUID pks are not creation-ordered — assert per-tool statuses instead.
    rows = ToolExecution.objects.filter(conversation_id=tool_conv_id)
    assert set(rows.values_list("tool_name", flat=True)) == {"tool_a", "tool_b"}
    assert all(r.status == "completed" for r in rows)


@pytest.mark.django_db
def test_dispatch_action_stream_agent_not_found_fails(monkeypatch, tool_conv_id):
    from ai.engine_runtime import dispatch_action_stream

    install = _fake_tool_executors({})
    install(monkeypatch)
    _fake_agent_registry(monkeypatch, {})

    frames = list(
        dispatch_action_stream(
            {
                "conversation_id": tool_conv_id,
                "action_type": "agent",
                "agent": "ghost",
                "args": {},
                "verbosity": "concise",
            }
        )
    )

    turn_end = next(f[1] for f in frames if f[1]["type"] == "turn_end")
    assert turn_end["status"] == "failed"
    assert "not found" in turn_end["summary"]
    assert frames[-1] == ("done", {"status": "failed"})


# ── dispatch_action_stream — abort correctness ───────────────────────────


@pytest.mark.django_db
def test_dispatch_action_stream_cancel_mid_run_stops_not_errors(
    monkeypatch, tool_conv_id
):
    """Acceptance bar: cancel mid-run → stopped frames + stopped row, no error."""
    from ai.engine_runtime import dispatch_action_stream

    executed: list[str] = []

    async def tool_a(args):
        executed.append("tool_a")
        # The user aborts while this step is running.
        GENERATIONS.cancel(tool_conv_id)
        return {"ok": True}

    async def tool_b(args):
        executed.append("tool_b")
        return {"ok": True}

    install = _fake_tool_executors({"tool_a": tool_a, "tool_b": tool_b})
    install(monkeypatch)
    _fake_agent_registry(
        monkeypatch,
        {
            "data_sweeper": SimpleNamespace(
                role="Cleans data", tool_set_json=["tool_a", "tool_b"],
            )
        },
    )

    GENERATIONS.start(tool_conv_id)
    try:
        frames = list(
            dispatch_action_stream(
                {
                    "conversation_id": tool_conv_id,
                    "action_type": "agent",
                    "agent": "data_sweeper",
                    "args": {},
                    "verbosity": "concise",
                }
            )
        )
    finally:
        GENERATIONS.finish(tool_conv_id)

    # No error frame anywhere.
    assert all(kind != "error" for kind, _ in frames)

    tool_ends = [
        f[1]
        for f in frames
        if isinstance(f[1], dict) and f[1].get("type") == "tool_end"
    ]
    assert [t["status"] for t in tool_ends] == ["completed", "stopped"]

    turn_end = next(f[1] for f in frames if f[1]["type"] == "turn_end")
    assert turn_end["status"] == "stopped"
    assert turn_end["summary"] == "Stopped by user"

    assert frames[-1] == ("done", {"status": "stopped"})

    # The second step never executed.
    assert executed == ["tool_a"]

    rows = ToolExecution.objects.filter(conversation_id=tool_conv_id)
    assert rows.get(tool_name="tool_a").status == "completed"
    assert rows.get(tool_name="tool_b").status == "stopped"


@pytest.mark.django_db
def test_dispatch_action_stream_engine_error_yields_error_tuple(
    monkeypatch, tool_conv_id
):
    import ai.engine_runtime as rt

    async def fake_run(instance_id, payload):
        raise RuntimeError("engine exploded")
        yield  # pragma: no cover - makes it an async generator

    monkeypatch.setattr(rt, "_run_action_stream", fake_run)

    frames = list(rt.dispatch_action_stream({"conversation_id": tool_conv_id}))

    assert len(frames) == 1
    assert frames[0][0] == "error"
    assert "engine exploded" in frames[0][1]
    assert isinstance(frames[0][2], dict)
    assert "error_kind" in frames[0][2]


# ── CarbonIntelligence.run_agent_action_stream ───────────────────────────


def _provider_stream(frames):
    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.run_tool_stream.return_value = frames
    return provider


def _completed_frames(conversation_id):
    return [
        ("frame", {
            "type": "turn_start",
            "turn_id": "turn-abc",
            "label": "Run tool fake_tool",
            "verbosity": "concise",
        }),
        ("frame", {
            "type": "tool_start",
            "turn_id": "turn-abc",
            "step_id": 1,
            "tool": "fake_tool",
            "category": "tool",
        }),
        ("frame", {"type": "tool_end", "step_id": 1, "status": "completed"}),
        ("frame", {
            "type": "turn_end",
            "turn_id": "turn-abc",
            "status": "completed",
            "summary": "1 step(s) completed.",
        }),
        ("done", {"status": "completed"}),
    ]


@pytest.mark.django_db
def test_run_agent_action_stream_done_persists_and_finalizes(user):
    conversation = _make_conversation(user, "chat", {})

    ci = CarbonIntelligence()
    ci._provider = _provider_stream(_completed_frames(str(conversation.id)))
    ci._guard_workspace_operation = MagicMock(
        return_value=(MagicMock(), "workspace_action_run")
    )

    frames = list(
        ci.run_agent_action_stream(
            user,
            str(conversation.id),
            action_type="tool",
            tool="fake_tool",
            args={"table": "sales"},
        )
    )

    assert [f["type"] for f in frames][-1] == "done"
    assert any(f["type"] == "turn_start" for f in frames)

    # User message persisted, conversation closed out of "working".
    assert AIMessage.objects.filter(
        conversation=conversation, role="user", content="Run tool fake_tool"
    ).exists()
    conversation.refresh_from_db()
    assert conversation.status == "completed"

    # Assistant message persisted.
    assert AIMessage.objects.filter(
        conversation=conversation, role="assistant", content="Action completed."
    ).exists()

    generation = AIGeneration.objects.get(conversation=conversation)
    assert generation.status == "completed"

    # The provider stream was given the full action payload.
    _, kwargs = ci._provider.run_tool_stream.call_args
    assert kwargs["conversation_id"] == str(conversation.id)
    assert kwargs["action_type"] == "tool"
    assert kwargs["tool"] == "fake_tool"
    assert kwargs["host_user_id"] == str(user.pk)


@pytest.mark.django_db
def test_run_agent_action_stream_stopped_not_stuck_working(user):
    conversation = _make_conversation(user, "chat", {})

    provider_frames = [
        ("frame", {
            "type": "turn_start",
            "turn_id": "turn-abc",
            "label": "Run agent data_sweeper",
            "verbosity": "concise",
        }),
        ("frame", {
            "type": "tool_start",
            "turn_id": "turn-abc",
            "step_id": 1,
            "tool": "tool_a",
            "category": "agent",
        }),
        ("frame", {"type": "tool_end", "step_id": 1, "status": "stopped"}),
        ("frame", {
            "type": "turn_end",
            "turn_id": "turn-abc",
            "status": "stopped",
            "summary": "Stopped by user",
        }),
        ("done", {"status": "stopped"}),
    ]

    ci = CarbonIntelligence()
    ci._provider = _provider_stream(provider_frames)
    ci._guard_workspace_operation = MagicMock(
        return_value=(MagicMock(), "workspace_action_run")
    )

    frames = list(
        ci.run_agent_action_stream(
            user,
            str(conversation.id),
            action_type="agent",
            agent="data_sweeper",
        )
    )

    # Terminal frame is "stopped" — never an error.
    assert frames[-1]["type"] == "stopped"
    assert "conversation" in frames[-1]

    # The conversation is NOT stuck in "working".
    conversation.refresh_from_db()
    assert conversation.status == "completed"

    stopped_msg = AIMessage.objects.filter(
        conversation=conversation,
        role="assistant",
        status="stopped",
        content="Stopped by user.",
    )
    assert stopped_msg.exists()

    generation = AIGeneration.objects.get(conversation=conversation)
    assert generation.status == "cancelled"
    assert generation.cancelled_at is not None


@pytest.mark.django_db
def test_run_agent_action_stream_provider_error_fails_cleanly(user):
    conversation = _make_conversation(user, "chat", {})

    ci = CarbonIntelligence()
    ci._provider = _provider_stream(
        [("error", "boom", {"error_kind": "permanent"})]
    )
    ci._guard_workspace_operation = MagicMock(
        return_value=(MagicMock(), "workspace_action_run")
    )

    frames = list(
        ci.run_agent_action_stream(
            user,
            str(conversation.id),
            action_type="tool",
            tool="fake_tool",
        )
    )

    assert frames[-1]["type"] == "error"
    assert frames[-1]["error_kind"] == "permanent"

    conversation.refresh_from_db()
    assert conversation.status == "failed"
    assert AIMessage.objects.filter(
        conversation=conversation, role="assistant", status="failed"
    ).exists()
    assert AIGeneration.objects.get(conversation=conversation).status == "failed"


@pytest.mark.django_db
def test_run_agent_action_stream_quota_gate_yields_quota_error(user):
    conversation = _make_conversation(user, "chat", {})

    ci = CarbonIntelligence()
    ci._provider = MagicMock()

    def _raise_quota(user):
        raise QuotaExceededError(
            "Monthly token quota exceeded.",
            quota={"limit": 100, "used": 100},
        )

    ci._enforce_quota = MagicMock(side_effect=_raise_quota)

    frames = list(
        ci.run_agent_action_stream(
            user,
            str(conversation.id),
            action_type="tool",
            tool="fake_tool",
        )
    )

    assert frames[0]["type"] == "error"
    assert frames[0]["error_code"] == "quota"
    assert frames[0]["quota"]["limit"] == 100

    # Nothing persisted, conversation untouched, no generation started.
    assert not AIMessage.objects.filter(conversation=conversation).exists()
    assert not AIGeneration.objects.filter(conversation=conversation).exists()
    conversation.refresh_from_db()
    assert conversation.status == "pending"


@pytest.mark.django_db
def test_run_agent_action_stream_missing_conversation_raises(user):
    ci = CarbonIntelligence()

    with pytest.raises(ValueError):
        list(
            ci.run_agent_action_stream(
                user,
                "00000000-0000-0000-0000-000000000000",
                action_type="tool",
                tool="fake_tool",
            )
        )


# ── SSE endpoint ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_run_action_stream_endpoint_returns_sse_frames(user):
    from django.urls import reverse
    from rest_framework.test import APIClient

    conversation = _make_conversation(user, "chat", {})

    frames = [
        {"type": "turn_start", "turn_id": "turn-abc", "label": "Run tool fake_tool",
         "verbosity": "concise"},
        {"type": "tool_start", "turn_id": "turn-abc", "step_id": 1,
         "tool": "fake_tool", "category": "tool"},
        {"type": "tool_end", "step_id": 1, "status": "completed"},
        {"type": "turn_end", "turn_id": "turn-abc", "status": "completed",
         "summary": "1 step(s) completed."},
        {"type": "done", "conversation": {"id": str(conversation.id)}},
    ]
    fake = MagicMock()
    fake.run_agent_action_stream.return_value = iter(frames)

    client = APIClient()
    client.force_authenticate(user=user)

    with patch("ai.workspace_api.CarbonIntelligence", return_value=fake):
        url = reverse(
            "ai-workspace-conversation-run-action-stream",
            kwargs={"pk": conversation.id},
        )
        response = client.post(
            url,
            {
                "action_type": "tool",
                "tool": "fake_tool",
                "args": {"table": "sales"},
                "verbosity": "concise",
            },
            format="json",
        )
        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/event-stream")
        body = b"".join(response.streaming_content).decode("utf-8")

    assert '"type": "turn_start"' in body
    assert '"type": "tool_end"' in body
    assert '"type": "done"' in body
    assert '"label": "Run tool fake_tool"' in body

    # Payload passed through to the intelligence method.
    _, kwargs = fake.run_agent_action_stream.call_args
    assert kwargs["tool"] == "fake_tool"
    assert kwargs["verbosity"] == "concise"
    assert kwargs["args"] == {"table": "sales"}


@pytest.mark.django_db
def test_run_action_stream_endpoint_serializer_validation(user):
    from django.urls import reverse
    from rest_framework.test import APIClient

    conversation = _make_conversation(user, "chat", {})

    client = APIClient()
    client.force_authenticate(user=user)

    url = reverse(
        "ai-workspace-conversation-run-action-stream",
        kwargs={"pk": conversation.id},
    )
    # action_type="tool" without a tool name → 400 before any stream starts.
    # (The project's global exception handler wraps DRF errors in
    # ``{error, message}`` — assert on the status + message text.)
    response = client.post(
        url, {"action_type": "tool", "args": {}}, format="json"
    )
    assert response.status_code == 400
    assert "tool is required" in str(response.data)

    # Bad verbosity → 400.
    response = client.post(
        url,
        {
            "action_type": "tool",
            "tool": "fake_tool",
            "verbosity": "verbose",
        },
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_run_action_stream_endpoint_missing_conversation_emits_error_frame(
    user,
):
    from django.urls import reverse
    from rest_framework.test import APIClient

    fake = MagicMock()
    fake.run_agent_action_stream.side_effect = ValueError(
        "Conversation 00000000-0000-0000-0000-000000000000 not found."
    )

    client = APIClient()
    client.force_authenticate(user=user)

    with patch("ai.workspace_api.CarbonIntelligence", return_value=fake):
        url = reverse(
            "ai-workspace-conversation-run-action-stream",
            kwargs={"pk": "00000000-0000-0000-0000-000000000000"},
        )
        response = client.post(
            url,
            {"action_type": "tool", "tool": "fake_tool"},
            format="json",
        )
        assert response.status_code == 200
        body = b"".join(response.streaming_content).decode("utf-8")

    assert '"type": "error"' in body
    assert "not found" in body
