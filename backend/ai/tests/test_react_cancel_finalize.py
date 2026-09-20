"""ReActLoop must not clobber operator cancel into completed/failed."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from ai.engine.cognition.plan.loop import ReActLoop, StepResult
from ai.engine.cognition.plan.planner import Plan, PlanStep


@pytest.mark.asyncio
async def test_finalize_run_preserves_cancelled_status():
    loop = ReActLoop(llm_client=None)
    row = SimpleNamespace(
        status="cancelled",
        total_llm_calls=0,
        total_latency_ms=0,
        total_tokens=0,
        updated_at=None,
        final_response=None,
        completed_at=None,
    )

    async def _select(model, *filters):
        name = getattr(model, "__name__", str(model))
        if "RunStep" in name:
            return []
        return [row]

    db = SimpleNamespace(select=AsyncMock(side_effect=_select), commit=AsyncMock())

    await loop._finalize_run(
        _db=db,
        run_id="run-1",
        succeeded=True,
        final_response="should not win",
        total_latency_ms=12.0,
        total_llm_calls=3,
        step_results=[StepResult(step_id=0, intent="x")],
        total_tokens=100,
    )

    assert row.status == "cancelled"
    assert row.total_llm_calls == 3
    assert row.total_tokens == 100
    assert row.final_response is None  # not overwritten on cancel preserve path
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_finalize_run_sets_completed_when_running():
    loop = ReActLoop(llm_client=None)
    row = SimpleNamespace(
        status="running",
        total_llm_calls=0,
        total_latency_ms=0,
        total_tokens=0,
        updated_at=None,
        final_response=None,
        completed_at=None,
    )

    async def _select(model, *filters):
        name = getattr(model, "__name__", str(model))
        if "RunStep" in name:
            return []  # no open steps — empty success is allowed
        return [row]

    db = SimpleNamespace(select=AsyncMock(side_effect=_select), commit=AsyncMock())

    await loop._finalize_run(
        _db=db,
        run_id="run-2",
        succeeded=True,
        final_response="done",
        total_latency_ms=5.0,
        total_llm_calls=2,
        step_results=[],
        total_tokens=40,
    )

    assert row.status == "completed"
    assert row.final_response == "done"
    assert row.total_tokens == 40


@pytest.mark.asyncio
async def test_finalize_run_refuses_completed_with_open_steps():
    """Pending-under-Completed is a product lie — fail closed instead."""
    loop = ReActLoop(llm_client=None)
    row = SimpleNamespace(
        status="running",
        total_llm_calls=0,
        total_latency_ms=0,
        total_tokens=0,
        updated_at=None,
        final_response=None,
        completed_at=None,
    )
    open_step = SimpleNamespace(status="pending", step_index=0)

    async def _select(model, *filters):
        name = getattr(model, "__name__", str(model))
        if "RunStep" in name:
            return [open_step]
        return [row]

    db = SimpleNamespace(select=AsyncMock(side_effect=_select), commit=AsyncMock())

    await loop._finalize_run(
        _db=db,
        run_id="run-3",
        succeeded=True,
        final_status="completed",
        final_response="pretend done",
        total_latency_ms=5.0,
        total_llm_calls=1,
        step_results=[],
        total_tokens=10,
    )

    assert row.status == "failed"
    assert "still open" in (row.final_response or "")


@pytest.mark.asyncio
async def test_hard_cancel_aborts_in_flight_step():
    """Operator cancel mid-_execute_step must abort before the sleep finishes."""
    started = asyncio.Event()
    cancelled_seen = asyncio.Event()
    cancel_flag = {"v": False}

    loop = ReActLoop(llm_client=None)
    plan = Plan(
        pattern="custom",
        source="test",
        synthesis_instruction="done",
        steps=[PlanStep(step_id=0, intent="slow", depends_on=[])],
    )

    async def slow_execute(**kwargs):
        started.set()
        try:
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            cancelled_seen.set()
            raise
        return StepResult(
            step_id=0, intent="slow", critic_verdict="pass", executed=True,
        )

    async def fake_is_cancelled(_db, _run_id):
        return bool(cancel_flag["v"])

    loop._execute_step = slow_execute  # type: ignore[method-assign]
    loop._synthesise = AsyncMock(return_value="nope")  # type: ignore[method-assign]
    loop._run_is_cancelled = fake_is_cancelled  # type: ignore[method-assign]
    loop._finalize_run = AsyncMock()  # type: ignore[method-assign]
    loop._persist_run_step = AsyncMock()  # type: ignore[method-assign]
    loop._persist_skipped_step = AsyncMock()  # type: ignore[method-assign]
    loop._pause_run = AsyncMock()  # type: ignore[method-assign]

    row = SimpleNamespace(
        status="paused",
        id="run-cancel-1",
        total_tokens=0,
        total_llm_calls=0,
        total_latency_ms=0,
        final_response=None,
        updated_at=None,
        completed_at=None,
        confirmation_token=None,
    )

    async def select(model, *_a, **_k):
        name = getattr(model, "__name__", str(model))
        if "RunStep" in name:
            return []
        if cancel_flag["v"]:
            row.status = "cancelled"
        return [row]

    db = SimpleNamespace(select=select, commit=AsyncMock())

    async def flip_cancel():
        await started.wait()
        cancel_flag["v"] = True

    with patch(
        "ai.engine.cognition.plan.loop._get_broadcast",
        return_value=AsyncMock(),
    ):
        flip = asyncio.create_task(flip_cancel())
        result = await asyncio.wait_for(
            loop.run(
                plan=plan,
                instance_id="test",
                conversation_id="c1",
                user_message="go",
                system_prompt="sys",
                db=db,
                resume_run_id="run-cancel-1",
            ),
            timeout=3.0,
        )
        await flip

    assert cancelled_seen.is_set() or any(
        r.error and "cancelled" in str(r.error) for r in result.step_results
    )
    assert not result.succeeded
