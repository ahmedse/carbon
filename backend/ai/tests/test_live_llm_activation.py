"""Phase C — live LLM activation smoke tests.

These tests hit the real provider (POE via OpenAI-compatible ``AsyncOpenAI``).
They are skipped unless the ``LLM_API_KEY`` environment variable is set.  The
key itself is never read into an assertion, printed, or logged — the provider
reads it from ``get_settings()`` (``backend/.env``) only.
"""
import asyncio
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("LLM_API_KEY"),
    reason="no live LLM",
)


def test_chat_completion_returns_nonempty_text():
    """chat_completion returns assistant text for a trivial prompt."""
    from ai.engine.llm.provider import chat_completion

    text = asyncio.run(
        chat_completion([{"role": "user", "content": "Say OK"}], temperature=0.0)
    )
    assert isinstance(text, str)
    assert text.strip()


@pytest.mark.django_db
def test_route_chat_returns_model_and_is_not_budget_blocked():
    """route_chat returns a dict with a model, non-exceeded finish, sane cost."""
    from ai.engine.llm.router import route_chat

    result = asyncio.run(
        route_chat(
            task="chat",
            instance_id="test-instance",
            conversation_id="test-conversation",
            messages=[{"role": "user", "content": "Say OK"}],
            temperature=0.0,
        )
    )
    assert isinstance(result, dict)
    assert result.get("model")
    assert result.get("finish_reason") != "budget_exceeded"
    assert result.get("cost_usd", -1.0) >= 0
