"""Regression (GAP-M5 / ISSUE-M0-1) — the confirmed memory write path.

``learn_fact`` / ``forget_fact`` stage a ``MEMORY`` ``long_term/*`` pending
execution.  Before the fix, ``CarbonHostExecutor._call_api`` had no ``MEMORY``
branch and no ``long_term/*`` in-process handler, so confirming a memory card
raised ``ToolExecutionError`` and wrote nothing.

These tests drive the exact runtime call chain:
``create_pending_execution`` → ``confirm_execution`` → ``_memory_in_process``
→ ``LongTermMemory.store_fact`` / ``archive_fact`` → real Django rows.

All assertions are domain-agnostic.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from django.test import override_settings


@pytest.mark.django_db(transaction=True)
def test_confirm_learn_fact_writes_long_term_memory():
    """Confirming a ``learn_fact`` proposal persists a private MemoryLongTerm row."""
    from accounts.models import User
    from ai.engine.core.database import get_session_factory
    from ai.host_executor import CarbonHostExecutor
    from ai.models import AIConversation, MemoryLongTerm, ToolExecution
    from ai.store import reset_store

    actor = User.objects.create_user(username="mem-learn", password="secret123")
    conversation = AIConversation.objects.create(
        user=actor,
        title="Memory chat",
        conversation_type="chat",
        app_identifier="carbon",
        task_payload_json={},
        scope_json={},
    )

    fact_text = "the Alpha Table has 12 rows"
    fact_id = None
    try:
        with override_settings(AI_STORE_BACKEND="django"):
            reset_store()

            async def _drive():
                factory = get_session_factory("carbon")
                async with factory() as db:
                    executor = CarbonHostExecutor(
                        db=db,
                        instance_config={},
                        user_token=f"inproc:carbon:{actor.pk}",
                        host_user_id=str(actor.pk),
                    )
                    execution = await executor.create_pending_execution(
                        conversation_id=str(conversation.id),
                        tool_name="learn_fact",
                        method="MEMORY",
                        endpoint="long_term/observation",
                        body={
                            "operation": "learn",
                            "fact": fact_text,
                            "category": "observation",
                            "instance_id": "carbon",
                        },
                    )
                    return await executor.confirm_execution(execution.id)

            result = asyncio.run(_drive())
            reset_store()

        assert result["status_code"] == 201
        assert result["kind"] == "memory"
        assert result["operation"] == "learn"
        fact_id = result["data"]["id"]
        assert fact_id

        fact = MemoryLongTerm.objects.get(pk=fact_id)
        assert fact.content == fact_text
        assert fact.category == "observation"
        assert fact.archived is False
        assert fact.host_user_id == str(actor.pk)
        assert fact.visibility == "private"
    finally:
        ToolExecution.objects.filter(conversation_id=str(conversation.id)).delete()
        if fact_id:
            MemoryLongTerm.objects.filter(pk=fact_id).delete()
        conversation.delete()
        actor.delete()


@pytest.mark.django_db(transaction=True)
def test_confirm_forget_fact_archives_long_term_memory():
    """Confirming a ``forget_fact`` proposal archives the fact (soft-forget)."""
    from accounts.models import User
    from ai.engine.core.database import get_session_factory
    from ai.host_executor import CarbonHostExecutor
    from ai.models import AIConversation, MemoryLongTerm, ToolExecution
    from ai.store import reset_store

    actor = User.objects.create_user(username="mem-forget", password="secret123")
    conversation = AIConversation.objects.create(
        user=actor,
        title="Memory chat",
        conversation_type="chat",
        app_identifier="carbon",
        task_payload_json={},
        scope_json={},
    )

    # Seed a fact directly so forget has a target to archive.
    fact = MemoryLongTerm.objects.create(
        id="fact-0001-gap9",
        instance_id="carbon",
        category="observation",
        content="the Widget settings for later",
        source="seed",
        confidence=1.0,
        host_user_id=str(actor.pk),
        visibility="private",
    )

    try:
        with override_settings(AI_STORE_BACKEND="django"):
            reset_store()

            async def _drive():
                factory = get_session_factory("carbon")
                async with factory() as db:
                    executor = CarbonHostExecutor(
                        db=db,
                        instance_config={},
                        user_token=f"inproc:carbon:{actor.pk}",
                        host_user_id=str(actor.pk),
                    )
                    execution = await executor.create_pending_execution(
                        conversation_id=str(conversation.id),
                        tool_name="forget_fact",
                        method="MEMORY",
                        endpoint="long_term/forget",
                        body={
                            "operation": "forget",
                            "memory_id": fact.id,
                            "instance_id": "carbon",
                        },
                    )
                    return await executor.confirm_execution(execution.id)

            result = asyncio.run(_drive())
            reset_store()

        assert result["status_code"] == 200
        assert result["kind"] == "memory"
        assert result["operation"] == "forget"
        assert result["data"]["archived"] is True

        fact.refresh_from_db()
        assert fact.archived is True
    finally:
        ToolExecution.objects.filter(conversation_id=str(conversation.id)).delete()
        MemoryLongTerm.objects.filter(pk=fact.id).delete()
        conversation.delete()
        actor.delete()


@pytest.mark.django_db(transaction=True)
def test_memory_call_api_rejects_empty_learn_fact():
    """An empty ``learn_fact`` is a fail-visible error, not a silent no-op."""
    from accounts.models import User
    from ai.engine.core.database import get_session_factory
    from ai.engine.core.exceptions import ToolExecutionError
    from ai.host_executor import CarbonHostExecutor
    from ai.store import reset_store

    actor = User.objects.create_user(username="mem-empty", password="secret123")

    try:
        with override_settings(AI_STORE_BACKEND="django"):
            reset_store()

            async def _drive():
                factory = get_session_factory("carbon")
                async with factory() as db:
                    executor = CarbonHostExecutor(
                        db=db,
                        instance_config={},
                        user_token=f"inproc:carbon:{actor.pk}",
                        host_user_id=str(actor.pk),
                    )
                    return await executor._call_api(
                        "MEMORY",
                        "long_term/observation",
                        body={"operation": "learn", "fact": "  "},
                    )

            with pytest.raises(ToolExecutionError):
                asyncio.run(_drive())
    finally:
        actor.delete()
