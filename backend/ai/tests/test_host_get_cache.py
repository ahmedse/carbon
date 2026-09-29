"""GET cache is per caller. One user's self-read is not served to another."""
from __future__ import annotations

import asyncio

from ai.engine.agent.executor import HostAPIExecutor, _api_cache


class _Caller(HostAPIExecutor):
    def __init__(self, host_user_id: str, payload: dict):
        self.host_user_id = host_user_id
        self.payload = payload
        self.calls = 0

    async def _call_api(self, method, endpoint, params=None, body=None):
        self.calls += 1
        return {"status_code": 200, "data": dict(self.payload)}


def test_get_cache_does_not_cross_callers():
    _api_cache.clear()
    path = "/carbon-api/people/me/"
    ali = _Caller("459", {"id": 17, "employee_no": "2378"})
    bila = _Caller("13", {"id": 23, "employee_no": "1067"})

    async def _run():
        first = await ali.call_api_direct("GET", path)
        second = await bila.call_api_direct("GET", path)
        again = await ali.call_api_direct("GET", path)
        return first, second, again

    first, second, again = asyncio.run(_run())
    assert first["data"]["employee_no"] == "2378"
    assert second["data"]["employee_no"] == "1067"
    assert again["data"]["employee_no"] == "2378"
    assert ali.calls == 1
    assert bila.calls == 1
    _api_cache.clear()


def test_get_without_caller_is_not_cached():
    _api_cache.clear()
    path = "/carbon-api/people/me/"
    bare = _Caller("", {"employee_no": "2378"})

    async def _run():
        await bare.call_api_direct("GET", path)
        return await bare.call_api_direct("GET", path)

    asyncio.run(_run())
    assert bare.calls == 2
    assert _api_cache == {}
