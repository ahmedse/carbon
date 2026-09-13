"""P1-08 — LLM accounting remediation tests.

Proves every ``route_chat`` outcome is durably accounted for in
``llm_call_logs``, independent of the caller's transaction:

  * Success  → a usage row is written with the summed token count.
  * Failure  → a zero-token usage row is still written before the error
    propagates (fail-closed accounting; ``_log_call`` never raises).
  * Budget   → the budget-exceeded short-circuit writes NO usage row (no
    provider call happened).

The provider seam is stubbed at ``ai.engine.llm.provider.create_completion`` —
the lazy import target inside ``route_chat`` — so no live LLM is ever hit.
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from django.test import override_settings

from ai.engine.core.config import get_settings
from ai.store import reset_store


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def django_store():
    """Run the engine against the Django (PostgreSQL) Store backend."""
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


@pytest.fixture
def cfg():
    """Clear the settings cache around each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── Fake OpenAI response shapes ───────────────────────────────────────────


class _FakeMessage:
    def __init__(self, content="hello", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, content="hello", tool_calls=None, finish_reason="stop"):
        self.message = _FakeMessage(content, tool_calls)
        self.finish_reason = finish_reason


class _FakeUsage:
    def __init__(self, prompt_tokens, completion_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens


class _FakeResponse:
    def __init__(
        self,
        content="hello",
        prompt_tokens=10,
        completion_tokens=5,
        tool_calls=None,
        finish_reason="stop",
    ):
        self.choices = [_FakeChoice(content, tool_calls, finish_reason)]
        self.usage = _FakeUsage(prompt_tokens, completion_tokens)


# ── Seeding helpers ───────────────────────────────────────────────────────


async def _seed_instance(instance_id: str) -> None:
    """Seed one active Instance row via the Store session factory."""
    from ai.engine.core.models import Instance
    from ai.store import get_store

    factory = get_store().get_session_factory()
    async with factory() as db:
        db.add(
            Instance(
                id=instance_id,
                name=f"acct-{instance_id[:8]}",
                display_name="Accounting Test Instance",
                host_db_url="postgres://db",
                host_api_url="https://host",
                status="active",
            )
        )
        await db.commit()


# ── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_success_produces_usage_row(django_store, cfg, monkeypatch):
    """A successful route_chat writes a usage row with summed tokens."""
    from ai.engine.core.models import generate_uuid
    from ai.engine.llm.router import route_chat
    from ai.models.core import LLMCallLog

    instance_id = generate_uuid()
    conversation_id = f"conv-{uuid4().hex[:8]}"
    asyncio.run(_seed_instance(instance_id))

    async def _fake_create_completion(client, **kwargs):
        return _FakeResponse(content="hello", prompt_tokens=10, completion_tokens=5)

    monkeypatch.setattr(
        "ai.engine.llm.provider.create_completion", _fake_create_completion
    )

    result = asyncio.run(
        route_chat(
            task="chat",
            instance_id=instance_id,
            conversation_id=conversation_id,
            messages=[{"role": "user", "content": "hi"}],
        )
    )

    assert result["content"] == "hello"
    row = LLMCallLog.objects.get(conversation_id=conversation_id)
    assert row.instance_id == instance_id
    assert row.total_tokens == 15  # prompt (10) + completion (5)


@pytest.mark.django_db(transaction=True)
def test_failure_produces_usage_row(django_store, cfg, monkeypatch):
    """A provider failure still writes a zero-token usage row before raising."""
    from ai.engine.core.models import generate_uuid
    from ai.engine.llm.router import route_chat
    from ai.models.core import LLMCallLog

    instance_id = generate_uuid()
    conversation_id = f"conv-{uuid4().hex[:8]}"
    asyncio.run(_seed_instance(instance_id))

    async def _boom(client, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr("ai.engine.llm.provider.create_completion", _boom)

    with pytest.raises(RuntimeError):
        asyncio.run(
            route_chat(
                task="chat",
                instance_id=instance_id,
                conversation_id=conversation_id,
                messages=[{"role": "user", "content": "hi"}],
            )
        )

    row = LLMCallLog.objects.get(conversation_id=conversation_id)
    assert row.total_tokens == 0
    assert row.cost_usd == 0.0


@pytest.mark.django_db(transaction=True)
def test_budget_trip_writes_no_usage_row(django_store, cfg, monkeypatch):
    """Budget exhaustion short-circuits before the provider, writing no row."""
    from ai.engine.core.models import LLMCallLog as EngineLLMCallLog, generate_uuid
    from ai.engine.llm.router import route_chat
    from ai.models.core import LLMCallLog as DjangoLLMCallLog
    from ai.store import get_store

    instance_id = generate_uuid()

    async def _seed():
        await _seed_instance(instance_id)
        factory = get_store().get_session_factory()
        async with factory() as db:
            db.add(
                EngineLLMCallLog(
                    id=generate_uuid(),
                    instance_id=instance_id,
                    conversation_id="seed-conv",
                    model="test",
                    llm_calls=1,
                    total_tokens=100,
                    cost_usd=0.5,
                    duration_ms=10,
                )
            )
            await db.commit()

    asyncio.run(_seed())

    monkeypatch.setenv("LLM_DAILY_BUDGET_USD", "0.01")
    get_settings.cache_clear()

    before = DjangoLLMCallLog.objects.filter(instance_id=instance_id).count()

    result = asyncio.run(
        route_chat(
            task="chat",
            instance_id=instance_id,
            conversation_id=f"conv-{uuid4().hex[:8]}",
            messages=[{"role": "user", "content": "hi"}],
        )
    )

    assert result["finish_reason"] == "budget_exceeded"
    assert result["input_tokens"] == 0
    after = DjangoLLMCallLog.objects.filter(instance_id=instance_id).count()
    assert after == before
