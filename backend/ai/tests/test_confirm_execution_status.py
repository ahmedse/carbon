"""confirm_execution must fail closed on non-2xx (SIM-20260919-N10)."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ai.engine.core.exceptions import ToolExecutionError


@pytest.mark.asyncio
async def test_confirm_execution_fails_on_http_422():
    from ai.host_executor import CarbonHostExecutor

    execution = SimpleNamespace(
        id="exec-1",
        host_user_id="42",
        input_params=json.dumps({
            "method": "POST",
            "endpoint": "/carbon-api/people/leave-records/",
            "body": {},
        }),
        status="pending_confirmation",
        output=None,
        executed_at=None,
        confirmed_by_user=False,
    )

    class _DB:
        async def select(self, model, filters):
            return [execution]

        async def commit(self):
            return None

    executor = CarbonHostExecutor(
        db=_DB(),
        instance_config={"name": "nibras"},
        user_token="inproc:carbon:42",
        host_user_id="42",
    )
    executor._call_api = AsyncMock(
        return_value={"status_code": 422, "data": {"detail": "employee required"}},
    )

    with pytest.raises(ToolExecutionError, match="HTTP 422"):
        await executor.confirm_execution("exec-1", expected_host_user_id="42")

    assert execution.status == "failed"
    out = json.loads(execution.output)
    assert out["status_code"] == 422


@pytest.mark.asyncio
async def test_confirm_execution_succeeds_on_http_201():
    from ai.host_executor import CarbonHostExecutor

    execution = SimpleNamespace(
        id="exec-2",
        host_user_id="42",
        input_params=json.dumps({
            "method": "POST",
            "endpoint": "/carbon-api/people/leave-records/",
            "body": {"employee": 1},
        }),
        status="pending_confirmation",
        output=None,
        executed_at=None,
        confirmed_by_user=False,
    )

    class _DB:
        async def select(self, model, filters):
            return [execution]

        async def commit(self):
            return None

    executor = CarbonHostExecutor(
        db=_DB(),
        instance_config={"name": "nibras"},
        user_token="inproc:carbon:42",
        host_user_id="42",
    )
    executor._call_api = AsyncMock(
        return_value={"status_code": 201, "data": {"id": 99}},
    )

    result = await executor.confirm_execution("exec-2", expected_host_user_id="42")
    assert execution.status == "confirmed"
    assert execution.confirmed_by_user is True
    assert result["status_code"] == 201
