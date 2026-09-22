"""P2-06d — ReAct plan-step consent gate routed through the command boundary.

Offline wiring tests for ``CarbonHostExecutor.execute_step_via_boundary``:
no LLM, no live DB. ``get_command_boundary`` is monkeypatched to build a
fail-closed boundary around an offline permit-PDP stub + in-memory ledger, so
the consent stage (stage 7) is exercised deterministically:

  * a no-token mutation step is REFUSED at the boundary consent stage — the
    effect closure never runs — and surfaces ``requires_confirmation=True``;
  * a mutation step carrying a confirmation token executes the effect closure;
  * ``_tool_requires_confirmation`` fails CLOSED (returns True) when the
    plugin registry import/call raises.

Run (from ``backend/``):

    /home/ahmed/ws/carbon/.venv/bin/python -m pytest ai/tests/test_react_consent_boundary.py -q
"""
from __future__ import annotations

import pytest

import ai.command_boundary_factory as factory_module
from ai.command_boundary import Command, CommandBoundary
from ai.engine.ports import Decision
from ai.host_executor import CarbonHostExecutor

pytestmark = pytest.mark.asyncio


class _StubPDP:
    """Offline PDP that always permits (ALLOW)."""

    def __init__(self, decision: Decision = Decision.ALLOW, reason: str = "permit"):
        self.decision = decision
        self.reason = reason

    async def decide(
        self,
        principal,
        action,
        objects,
        process_state=None,
        autonomy="human_only",
        budget=None,
        time=None,
        **kwargs,
    ) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "policy_version": "offline-v1",
        }


class _FakeLedger:
    """In-memory ledger sink (mirrors test_delivery_boundary._FakeLedger)."""

    def __init__(self):
        self.rows: list[dict] = []

    async def record_stage(self, **kwargs) -> str | None:
        self.rows.append(kwargs)
        return f"row-{len(self.rows)}"


class _CapturingBoundary:
    """Wraps the boundary so tests can assert the built ``Command``."""

    def __init__(self, inner: CommandBoundary):
        self._inner = inner
        self.last_command: Command | None = None
        self.last_outcome = None

    async def execute(self, command: Command):
        self.last_command = command
        self.last_outcome = await self._inner.execute(command)
        return self.last_outcome


def _install_boundary(monkeypatch) -> dict:
    """Swap the real factory for an offline, fail-closed boundary builder."""
    captured: dict = {}

    def _factory(db, *, executor=None, tool_catalog=None, pdp=None,
                 ledger=None, clock=None):
        inner = CommandBoundary(
            pdp=_StubPDP(),
            ledger=_FakeLedger(),
            executor=executor,
            tool_catalog=tool_catalog,
        )
        wrapper = _CapturingBoundary(inner)
        captured["wrapper"] = wrapper
        return wrapper

    monkeypatch.setattr(factory_module, "get_command_boundary", _factory)
    return captured


def _make_executor() -> CarbonHostExecutor:
    return CarbonHostExecutor(
        db=None,
        instance_config={},
        user_token="tok",
        host_user_id="u1",
    )


async def test_step_via_boundary_refuses_unconfirmed_mutation(monkeypatch):
    captured = _install_boundary(monkeypatch)
    ex = _make_executor()

    ran: list[bool] = []

    async def _effect(command=None) -> dict:
        ran.append(True)
        return {"wrote": True}

    result = await ex.execute_step_via_boundary(
        effect=_effect,
        tool_name="call_host_api",
        is_mutation=True,
        confirmation_token=None,
        instance_id="i1",
        host_user_id="u1",
        conversation_id="c1",
    )

    # No token → stage-7 consent refusal → the consent decision is now a
    # boundary outcome; the effect closure must never run.
    assert result["requires_confirmation"] is True
    assert result["status"] == "refused"
    assert len(ran) == 0, "consent gate must block the effect closure"

    # The built command is fail-closed: confirmation required, no token,
    # human_only autonomy for a mutation.
    wrapper = captured["wrapper"]
    assert wrapper.last_command is not None
    assert wrapper.last_command.requires_confirmation is True
    assert wrapper.last_command.confirmation_token is None
    assert wrapper.last_command.autonomy == "human_only"
    assert wrapper.last_command.tool == "call_host_api"


async def test_step_via_boundary_executes_with_confirmation_token(monkeypatch):
    captured = _install_boundary(monkeypatch)
    ex = _make_executor()

    ran: list[bool] = []

    async def _effect(command=None) -> dict:
        ran.append(True)
        return {"wrote": True}

    result = await ex.execute_step_via_boundary(
        effect=_effect,
        tool_name="call_host_api",
        is_mutation=True,
        confirmation_token="tok-123",
        instance_id="i1",
        host_user_id="u1",
        conversation_id="c1",
    )

    # With a token the boundary confirms at stage 7 and runs the effect.
    assert result["requires_confirmation"] is False
    assert result["status"] == "confirmed"
    assert result["result"] == {"wrote": True}
    assert len(ran) == 1, "effect must run once consent passed"


async def test_tool_requires_confirmation_is_fail_closed(monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("plugin registry unavailable")

    monkeypatch.setattr("ai.engine.agent.plugins.is_confirmation_tool", _boom)

    from ai.engine.cognition.plan.loop import _tool_requires_confirmation

    # Lookup failure now means confirmation-required (deny-by-default).
    assert _tool_requires_confirmation("call_host_api") is True


async def test_p13_auto_confirms_when_resume_token_present():
    """Approve → resume must not pause again on the staged leave submit.

    After unstaged consent the tool re-runs and returns ``requires_confirmation``
    + ``execution_id``. With a resume token the P1.3 gate must call
    ``confirm_execution`` and continue — not open a second Approve loop.
    """
    import json
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from ai.engine.cognition.plan.loop import ReActLoop
    from ai.engine.cognition.plan.planner import PlanStep
    from ai.engine.cognition.turn.witnesses import RetrievalResult

    confirmed: list[str] = []

    class _Host:
        async def confirm_execution(self, execution_id, expected_host_user_id=None):
            confirmed.append(execution_id)
            return {
                "status_code": 201,
                "data": {"id": 99},
                "action": "navigate",
                "route": "/my/requests/99",
                "label": "Open leave request",
                "summary": "Leave request annual · CRS-99",
            }

    loop = ReActLoop.__new__(ReActLoop)
    loop._build_step_prompt = MagicMock(return_value="prompt")  # noqa: SLF001
    loop._observe = AsyncMock(return_value=None)  # noqa: SLF001

    dw = AsyncMock()
    dw.draft = AsyncMock(
        return_value=SimpleNamespace(text="submit leave", tool_calls=[])
    )

    cw = AsyncMock()
    cw.review = AsyncMock(
        return_value=SimpleNamespace(verdict="pass", flags=[], veto_reason=None)
    )

    staged = {
        "tool_name": "call_host_api",
        "result": json.dumps(
            {
                "requires_confirmation": True,
                "execution_id": "exec-leave-1",
                "message": "Submit leave request",
            }
        ),
    }
    ex = AsyncMock()
    ex.executor = _Host()
    ex.execute = AsyncMock(
        return_value=SimpleNamespace(completed_tools=[staged])
    )

    step = PlanStep(
        step_id=2,
        intent="Submit leave request",
        tool_name="call_host_api",
        is_mutation=True,
    )

    result = await loop._execute_step(  # noqa: SLF001
        step=step,
        dw=dw,
        cw=cw,
        ex=ex,
        instance_id="i",
        conversation_id="c",
        user_message="اريد اجازة",
        system_prompt="sp",
        conversation_history=None,
        instance_config=None,
        user_info=None,
        retrieval=RetrievalResult(),
        progress_callback=None,
        stream_callback=None,
        dry_run=False,
        confirmation_token="resume-tok-abc",
        step_contexts={},
        host_user_id="u1",
    )

    assert confirmed == ["exec-leave-1"]
    assert result.paused is False
    assert result.executed is True
    assert result.error is None
    assert result.tool_output.get("confirmed") is True
    assert result.tool_output.get("action") == "navigate"
    committed = json.loads(result.tool_output["result"])
    assert committed["data"]["id"] == 99
    # Observe must be skipped after auto-confirm (resume SSE hang guard).
    loop._observe.assert_not_called()


async def test_p13_auto_confirm_failure_fails_step_not_re_pause():
    """Overlap / host 400 after Approve must fail the step — not ask again."""
    import json
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from ai.engine.cognition.plan.loop import ReActLoop
    from ai.engine.cognition.plan.planner import PlanStep
    from ai.engine.cognition.turn.witnesses import RetrievalResult

    class _Host:
        async def confirm_execution(self, execution_id, expected_host_user_id=None):
            raise RuntimeError(
                "Those dates overlap an existing annual leave "
                "(2026-09-23→2026-09-23, status=draft). (HTTP 400)"
            )

    loop = ReActLoop.__new__(ReActLoop)
    loop._build_step_prompt = MagicMock(return_value="prompt")  # noqa: SLF001
    loop._observe = AsyncMock(return_value=None)  # noqa: SLF001

    dw = AsyncMock()
    dw.draft = AsyncMock(
        return_value=SimpleNamespace(text="submit leave", tool_calls=[])
    )
    cw = AsyncMock()
    cw.review = AsyncMock(
        return_value=SimpleNamespace(verdict="pass", flags=[], veto_reason=None)
    )
    staged = {
        "tool_name": "call_host_api",
        "result": json.dumps(
            {"requires_confirmation": True, "execution_id": "exec-overlap"}
        ),
    }
    ex = AsyncMock()
    ex.executor = _Host()
    ex.execute = AsyncMock(
        return_value=SimpleNamespace(completed_tools=[staged])
    )

    step = PlanStep(
        step_id=1,
        intent="Submit leave request",
        tool_name="call_host_api",
        is_mutation=True,
    )

    result = await loop._execute_step(  # noqa: SLF001
        step=step,
        dw=dw,
        cw=cw,
        ex=ex,
        instance_id="i",
        conversation_id="c",
        user_message="leave",
        system_prompt="sp",
        conversation_history=None,
        instance_config=None,
        user_info=None,
        retrieval=RetrievalResult(),
        progress_callback=None,
        stream_callback=None,
        dry_run=False,
        confirmation_token="resume-tok",
        step_contexts={},
        host_user_id="u1",
    )

    assert result.paused is False
    assert result.executed is False
    assert "overlap" in (result.error or "").lower()
    assert "auto_confirm_failed" in result.critic_flags
    loop._observe.assert_not_called()


async def test_p13_still_pauses_without_resume_token():
    """First-time staging (no prior Approve) must still pause for consent."""
    import json
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from ai.engine.cognition.plan.loop import ReActLoop
    from ai.engine.cognition.plan.planner import PlanStep
    from ai.engine.cognition.turn.witnesses import RetrievalResult

    class _Host:
        async def confirm_execution(self, *a, **k):
            raise AssertionError("must not auto-confirm without resume token")

    loop = ReActLoop.__new__(ReActLoop)
    loop._build_step_prompt = MagicMock(return_value="prompt")  # noqa: SLF001

    dw = AsyncMock()
    dw.draft = AsyncMock(
        return_value=SimpleNamespace(text="submit leave", tool_calls=[])
    )
    cw = AsyncMock()
    cw.review = AsyncMock(
        return_value=SimpleNamespace(verdict="pass", flags=[], veto_reason=None)
    )
    staged = {
        "tool_name": "call_host_api",
        "result": json.dumps(
            {"requires_confirmation": True, "execution_id": "exec-2"}
        ),
    }
    ex = AsyncMock()
    ex.executor = _Host()
    ex.execute = AsyncMock(
        return_value=SimpleNamespace(completed_tools=[staged])
    )

    step = PlanStep(
        step_id=2,
        intent="Submit leave request",
        tool_name="call_host_api",
        is_mutation=True,
    )

    result = await loop._execute_step(  # noqa: SLF001
        step=step,
        dw=dw,
        cw=cw,
        ex=ex,
        instance_id="i",
        conversation_id="c",
        user_message="leave",
        system_prompt="sp",
        conversation_history=None,
        instance_config=None,
        user_info=None,
        retrieval=RetrievalResult(),
        progress_callback=None,
        stream_callback=None,
        dry_run=False,
        confirmation_token=None,
        step_contexts={},
        host_user_id="u1",
    )

    assert result.paused is True
    assert result.executed is False
    assert result.confirmation_token
