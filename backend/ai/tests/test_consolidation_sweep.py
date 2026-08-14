"""Phase H — LLM-heavy cognition sweep (consolidation) activation tests.

Proves the sleep-time Extract → Reflect → Curate pipeline is wired and gated:

  * ``run_consolidation_sweep`` short-circuits (0 LLM calls) when
    ``CONSOLIDATION_SWEEP_ENABLED=false``.
  * With a seeded active instance + repeated successful tool sequence,
    the sweep invokes ``route_chat`` (task="cognition") and curates a draft
    ``Skill`` row with ``gate_status="pending"``.
  * ``extract_candidates`` returns no candidates for a single trajectory row
    (the ≥2-row floor), so a cold instance never burns LLM budget.

The LLM is stubbed at ``ai.engine.llm.router.route_chat`` (imported locally
inside ``reflect_on_candidates`` at call time), so no live provider is hit.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch
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


def _stub_route_chat_skill():
    """Return an async stub for route_chat that yields a reflection dict."""
    async def _route_chat(**kwargs):
        return {
            "content": json.dumps({
                "skill_name": "reuse_data_query",
                "skill_kind": "procedure",
                "skill_description": "Reusable data-query playbook",
                "skill_signature": {"tool": "data_query"},
                "skill_body": {"steps": ["query", "verify"]},
                "confidence": 0.9,
            }),
            "output_tokens": 42,
            "finish_reason": "stop",
        }

    return AsyncMock(side_effect=_route_chat)


# ── Seeding helpers ──────────────────────────────────────────────────────


async def _seed_instance_with_trajectories(instance_name: str, n: int, tool_name: str):
    """Seed an active instance + n completed trajectories sharing one tool seq.

    Written via the Store so rows commit on the same (sync) connection the
    engine reads from — test-thread ORM writes are invisible to the worker.
    """
    from ai.engine.core.models import Instance, Run, Trajectory, generate_uuid
    from ai.store import get_store

    instance_id = generate_uuid()
    factory = get_store().get_session_factory()
    async with factory() as db:
        db.add(Instance(
            id=instance_id,
            name=instance_name,
            display_name=instance_name,
            host_db_url="postgres://db",
            host_api_url="https://host",
            status="active",
        ))

        for _ in range(n):
            run_id = generate_uuid()
            conversation_id = f"conv-{uuid4().hex[:8]}"
            db.add(Run(
                id=run_id,
                instance_id=instance_id,
                conversation_id=conversation_id,
                user_message="How many emissions this quarter?",
                status="completed",
            ))
            db.add(Trajectory(
                run_id=run_id,
                instance_id=instance_id,
                conversation_id=conversation_id,
                user_message="How many emissions this quarter?",
                task_intent="data_query",
                tool_calls_json=json.dumps([
                    {"tool_name": tool_name, "args_summary": "{}", "success": True},
                ]),
                status="completed",
                consolidation_round=0,
            ))
        await db.commit()

    return instance_id


def _run_sweep(instance_id: str) -> dict:
    """Run the consolidation sweep for an instance inside a fresh session."""
    from ai.engine.cognition.consolidation import run_consolidation_sweep
    from ai.store import get_store

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            return await run_consolidation_sweep(db, instance_id)

    return asyncio.run(_go())


# ── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_sweep_disabled_short_circuits_no_llm(django_store, cfg, monkeypatch):
    """CONSOLIDATION_SWEEP_ENABLED=false → zero candidates, zero LLM calls."""
    monkeypatch.setenv("CONSOLIDATION_SWEEP_ENABLED", "false")
    get_settings.cache_clear()

    instance_id = asyncio.run(
        _seed_instance_with_trajectories(f"off-{uuid4().hex[:8]}", 3, "data_query")
    )

    with patch("ai.engine.llm.router.route_chat", new=AsyncMock()) as route:
        summary = _run_sweep(instance_id)

    assert summary == {
        "candidates_extracted": 0,
        "reflections": 0,
        "skills_created": 0,
    }
    route.assert_not_called()


@pytest.mark.django_db
def test_sweep_reflects_and_curates_skill(django_store, cfg):
    """Repeated success + stub LLM → one draft Skill with gate_status pending."""
    from ai.models.core import Skill

    instance_id = asyncio.run(
        _seed_instance_with_trajectories(f"on-{uuid4().hex[:8]}", 3, "data_query")
    )

    with patch(
        "ai.engine.llm.router.route_chat", new=_stub_route_chat_skill()
    ) as route:
        summary = _run_sweep(instance_id)

    assert summary["candidates_extracted"] >= 1
    assert summary["reflections"] >= 1
    assert summary["skills_created"] == 1

    # route_chat was invoked for the cognition task with a JSON-object format.
    assert route.await_count >= 1
    call_kwargs = route.await_args.kwargs
    assert call_kwargs["task"] == "cognition"
    assert call_kwargs["response_format"] == {"type": "json_object"}

    skills = list(Skill.objects.filter(instance_id=instance_id))
    assert len(skills) == 1
    assert skills[0].name == "reuse_data_query"
    assert skills[0].kind == "procedure"
    assert skills[0].status == "draft"
    assert skills[0].gate_status == "pending"
    assert skills[0].author_user_id == "system"


@pytest.mark.django_db
def test_cold_instance_yields_no_candidates(django_store, cfg):
    """A single trajectory row is below the extraction floor — no LLM burn."""
    instance_id = asyncio.run(
        _seed_instance_with_trajectories(f"cold-{uuid4().hex[:8]}", 1, "data_query")
    )

    with patch("ai.engine.llm.router.route_chat", new=AsyncMock()) as route:
        summary = _run_sweep(instance_id)

    assert summary["candidates_extracted"] == 0
    assert summary["reflections"] == 0
    assert summary["skills_created"] == 0
    route.assert_not_called()
