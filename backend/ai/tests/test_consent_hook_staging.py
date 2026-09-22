"""consent_hook guards the consent bypass, not the propose→confirm path.

Regression cover: the hook cancelled every unconfirmed mutation, so
``submit_my_leave`` never reached the executor, never staged, and the user was
told to "complete the confirmation flow first" — a flow the cancellation had
just made unreachable.
"""
from __future__ import annotations

import pytest

from ai.engine.agent.guardrails import HookContext, consent_hook


def _ctx(**args) -> HookContext:
    return HookContext(
        tool_name="call_host_api",
        tool_args={"api_name": "submit_my_leave", **args},
        instance_id="nibras",
    )


@pytest.mark.asyncio
async def test_unconfirmed_mutation_reaches_the_executor_to_stage():
    result = await consent_hook(_ctx(body={"leave_type": "annual", "days": 1}))
    assert result.action == "pass"
    assert "stages_for_confirmation" in (result.flags or [])


@pytest.mark.asyncio
async def test_reads_pass_untouched():
    ctx = HookContext(
        tool_name="call_host_api",
        tool_args={"api_name": "get_my_leave_balance"},
        instance_id="nibras",
    )
    assert (await consent_hook(ctx)).action == "pass"


@pytest.mark.asyncio
async def test_confirmed_with_token_passes():
    result = await consent_hook(_ctx(
        body={"days": 1}, _confirmed=True, _confirmation_token="tok-1",
    ))
    assert result.action == "pass"


@pytest.mark.asyncio
async def test_claimed_consent_without_a_token_is_cancelled():
    result = await consent_hook(_ctx(body={"days": 1}, _confirmed=True))
    assert result.action == "cancel"
    assert "unverified_confirmation" in (result.flags or [])
    assert "Nothing was submitted" in result.reason


@pytest.mark.asyncio
async def test_non_host_tools_are_out_of_scope():
    ctx = HookContext(
        tool_name="search_knowledge",
        tool_args={"query": "x"},
        instance_id="nibras",
    )
    assert (await consent_hook(ctx)).action == "pass"
