"""ReActLoop must not clobber operator cancel into completed/failed."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ai.engine.cognition.plan.loop import ReActLoop, StepResult


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
    db = SimpleNamespace(select=AsyncMock(return_value=[row]), commit=AsyncMock())

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
    db = SimpleNamespace(select=AsyncMock(return_value=[row]), commit=AsyncMock())

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
