"""
Phase 2b-1 — chat wiring proof.

Proves the in-process engine's ``chat`` task is wired end-to-end:

    dispatch_task("chat", payload)
      -> TurnPipelineRunner.run  (six-witness pipeline)
      -> durable TurnLedgerRow + LLMCallLog rows via the DjangoStore

No HTTP. Fail-visible: an engine error returns ``pulse_unavailable``.

The LLM is stubbed (``get_llm_client``) because the dev environment has no
``LLM_API_KEY``.  The single-pass path is forced by disabling the fan-out
and multi-step gates, which are Phase 2b-2/2b-3 territory.
"""

from __future__ import annotations

import types
from unittest.mock import patch

import pytest
from django.test import override_settings

from ai.tests.pv21_stub import answer_decision
from ai.engine.core.config import get_settings
from ai.store import reset_store


# ── Fixtures ─────────────────────────────────────────────────────────────


def _fake_completion(*args, **kwargs) -> types.SimpleNamespace:
    """Return a deterministic OpenAI-shaped chat completion."""

    async def _create(**kw):
        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(
                        content="This is a stubbed chat reply.",
                        tool_calls=answer_decision(kw),
                    ),
                    finish_reason="stop",
                )
            ],
            usage=types.SimpleNamespace(
                prompt_tokens=10,
                completion_tokens=4,
                total_tokens=14,
            ),
        )

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=_create)
        )
    )


@pytest.fixture
def django_store():
    """Use the Django backend and force the single-pass chat path."""
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


@pytest.fixture
def single_pass(monkeypatch):
    """Disable fan-out / multi-step so the six-witness spine runs alone."""
    monkeypatch.setenv("AGENT_ORCHESTRATOR_ENABLED", "false")
    monkeypatch.setenv("KG_MULTI_STEP_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def stub_llm(monkeypatch):
    """Stub the OpenAI client (no API key in dev).

    A configured ``DEEPSEEK_API_KEY`` would make ``client_for_model`` open a
    live client and bypass the stub, so neutralize it for the test and reset
    the settings cache around the stub.
    """
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    get_settings.cache_clear()
    try:
        with patch("ai.engine.llm.provider.get_llm_client") as mock:
            mock.return_value = _fake_completion()
            yield mock
    finally:
        get_settings.cache_clear()


# ── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_dispatch_chat_returns_completed(django_store, single_pass, stub_llm):
    """dispatch_task('chat') completes with a real result via the Store."""
    from ai.engine_runtime import dispatch_task
    from ai.models.core import LLMCallLog, TurnLedgerRow

    payload = {
        "message": "What is our carbon footprint this quarter?",
        "conversation_history": {
            "conversation_id": "conv-test-123",
            "messages": [{"role": "user", "content": "hello"}],
        },
    }

    data = dispatch_task("chat", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert result.get("content") == "This is a stubbed chat reply."
    assert result.get("execution_ms", -1) >= 0
    assert isinstance(result.get("follow_up_questions"), list)

    # Durable write proof: per-stage ledger rows + LLM call log landed in
    # PostgreSQL (test DB) through the DjangoStore.  The witnesses tag the
    # LLM log with a stage prefix (draft-*, critic-*), while the ledger
    # rows carry the bare conversation id.
    ledger_rows = TurnLedgerRow.objects.filter(conversation_id="conv-test-123")
    assert ledger_rows.count() >= 1
    llm_logs = LLMCallLog.objects.filter(
        conversation_id__in=["understand-conv-test-123", "answer-conv-test-123"]
    )
    assert llm_logs.count() >= 1


@pytest.mark.django_db(transaction=True)
def test_dispatch_chat_is_fail_visible(django_store, single_pass, monkeypatch):
    """An engine error (no LLM client / API key) yields pulse_unavailable."""
    from ai.engine_runtime import dispatch_task

    # Force the no-provider condition so this test is independent of whether a
    # live LLM key is present in .env: an empty key/base_url makes the real
    # (unreachable) provider raise, which must NOT fabricate a result.
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    get_settings.cache_clear()

    payload = {
        "message": "hello",
        "conversation_history": {"conversation_id": "conv-test-456"},
    }
    data = dispatch_task("chat", payload, instance_id="carbon")

    assert data.get("status") in ("pulse_unavailable", "failed"), data
    assert data.get("error"), data


@pytest.mark.django_db(transaction=True)
def test_all_module_tasks_are_wired(django_store, single_pass, cfg, stub_llm):
    """Every advertised task type resolves to a handler — no ``not_wired`` remains.

    Phase 2b-3a wires the final two DQ task types (``dq.validate`` /
    ``dq.suggest``), completing the task-type matrix: every entry in
    ``MODULES`` is covered by ``_TASK_HANDLERS`` ∪ ``chat``, so no task
    returns ``not_wired``.
    """
    from ai.engine_runtime import MODULES, dispatch_task

    for task_type in MODULES:
        data = dispatch_task(task_type, {}, instance_id="carbon")
        code = (data.get("error") or {}).get("code")
        assert code != "not_wired", (task_type, data)


# ── DEFECT 1 regression: nested submit must not deadlock ──────────────────


def test_nested_sync_submit_into_thread_executor_does_not_deadlock():
    """A sync read re-entering the thread-sensitive executor must not deadlock.

    ``_instance_config`` runs on asgiref's single-thread executor (it is
    entered via ``sync_to_async(..., thread_sensitive=True)``).  Its DB reads
    used to bridge back through another ``sync_to_async(...,
    thread_sensitive=True)`` — a nested submit onto the executor already
    running it, which raises "Single thread executor already being used,
    would deadlock".  ``_run_sync_inline`` runs them on the current (already
    Django-safe) thread instead.  This reproduces the nesting directly.
    """
    import asyncio

    from asgiref.sync import sync_to_async

    from ai.engine_runtime import _run_sync_inline

    ran: list[str] = []

    def _read() -> str:
        ran.append("read")
        return "ok"

    async def _outer():
        return await sync_to_async(
            lambda: _run_sync_inline(_read), thread_sensitive=True
        )()

    assert asyncio.run(_outer()) == "ok"
    assert ran == ["read"]


@pytest.mark.django_db(transaction=True)
def test_instance_config_nested_in_executor_resolves_inventory(monkeypatch):
    """Entering ``_instance_config`` on the executor loads a real inventory.

    Before the fix the nested submit was swallowed and left the fallback
    ``access_level == "unknown"`` manifest; the fix resolves the manifest
    without deadlocking. The manifest builder is stubbed to a sentinel so the
    assertion proves the read ran on the executor (not the deadlock fallback).
    """
    import asyncio

    from asgiref.sync import sync_to_async

    import ai.engine_runtime as engine_runtime

    sentinel = {"access_level": "sentinel", "platform_name": "x"}
    monkeypatch.setattr(
        "ai.access_manifest.build_user_access_manifest",
        lambda host_user_id: sentinel,
    )

    async def _load():
        return await sync_to_async(engine_runtime._instance_config, thread_sensitive=True)(
            "carbon", None
        )

    config = asyncio.run(_load())
    assert isinstance(config, dict)
    assert config["user_access"] == sentinel
