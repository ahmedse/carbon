"""
Phase 17-A — provider reliability + error taxonomy regression tests.

Verifies:
  - ``create_completion`` retries transient errors (the user chat path
    previously bypassed retry by calling the raw client directly).
  - ``classify_llm_error`` distinguishes transient vs permanent.
  - ``route_chat`` honors a ``model`` override (the seam Phase 18-A uses).
"""
from __future__ import annotations

import asyncio
import types

import httpx
import pytest


def test_classify_llm_error_transient_vs_permanent():
    from ai.engine.llm.provider import classify_llm_error

    req = httpx.Request("POST", "https://api.poe.com/v1/chat/completions")
    assert classify_llm_error(httpx.TimeoutException("boom")) == "permanent"
    # ValueError is not an OpenAI retryable type → permanent.
    assert classify_llm_error(ValueError("bad")) == "permanent"
    # An OpenAI connection error → transient (retryable).
    from openai import APIConnectionError

    assert classify_llm_error(APIConnectionError(request=req)) == "transient"


def test_create_completion_retries_transient_error():
    from ai.engine.llm import provider as prov

    calls = {"n": 0}

    class FakeCompletions:
        async def create(self, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                req = httpx.Request("POST", "https://api.poe.com/v1")
                raise prov.APIConnectionError(request=req)
            return {"ok": True}

    class FakeClient:
        chat = types.SimpleNamespace(completions=FakeCompletions())

    result = asyncio.run(prov.create_completion(FakeClient()))

    assert result == {"ok": True}
    assert calls["n"] == 2  # one transient failure, then success


def test_route_chat_honors_model_override(monkeypatch):
    import ai.engine.llm.router as router

    captured = {}

    async def _create(**kwargs):
        captured["kwargs"] = kwargs
        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(content="ok", tool_calls=None),
                    finish_reason="stop",
                )
            ],
            usage=types.SimpleNamespace(
                prompt_tokens=1, completion_tokens=1, total_tokens=2
            ),
        )

    class FakeClient:
        chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=_create)
        )

    async def fake_check_budget(instance_id, db):
        return 0.0

    async def fake_log_call(db, **kwargs):
        return None

    monkeypatch.setattr("ai.engine.llm.provider.get_llm_client", lambda: FakeClient())
    monkeypatch.setattr(router, "_check_budget", fake_check_budget)
    monkeypatch.setattr(router, "_log_call", fake_log_call)

    result = asyncio.run(
        router.route_chat(
            task="chat",
            instance_id="i",
            conversation_id="c",
            messages=[{"role": "user", "content": "hi"}],
            model="GPT-4o-mini",
            db=object(),
        )
    )

    assert captured["kwargs"]["model"] == "GPT-4o-mini"
    assert result["model"] == "GPT-4o-mini"


def test_list_chat_models_returns_catalog_with_pricing_and_default():
    from ai.engine.llm.router import list_chat_models

    models = list_chat_models()

    assert models, "catalog should not be empty"
    required = {"id", "label", "description", "input_cost_per_1m", "output_cost_per_1m", "is_default"}
    for entry in models:
        assert required <= entry.keys()
        assert entry["id"]
        assert entry["label"]
        assert isinstance(entry["input_cost_per_1m"], (int, float))
        assert isinstance(entry["output_cost_per_1m"], (int, float))
        assert isinstance(entry["is_default"], bool)

    # Exactly one default entry, and it matches the configured chat model.
    defaults = [e for e in models if e["is_default"]]
    assert len(defaults) == 1
    from ai.engine.llm.router import get_model_for_task

    assert defaults[0]["id"].strip().lower() == get_model_for_task("chat").strip().lower()


def test_find_rates_is_case_insensitive():
    from ai.engine.llm.router import _find_rates

    # The cost table key is "GPT-4o" (per LLM_COST_MODELS); a lowercase
    # provider-returned name must still resolve.
    rates = _find_rates("gpt-4o")
    assert rates is not None
    assert rates["input"] > 0
    assert rates["output"] > 0
    assert _find_rates("definitely-not-a-model") is None
    assert _find_rates("") is None
