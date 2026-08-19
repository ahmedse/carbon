"""
Tests for ``_DjangoSession.execute()`` — the Phase 3 fix that unblocked
SQLAlchemy-statement execution (agent-registry fan-out, skill search,
tool-execution DML, vector-store raw SQL) through the DjangoStore.

Before the fix every ``await db.execute(stmt)`` raised ``AttributeError`` and
was swallowed by callers, silently degrading fan-out + skill search on every
chat turn (the "couldn't reach the AI service" symptom's silent half).

The statements are built from the ENGINE (SQLAlchemy) models — exactly what
the engine passes — and verified against the Django mirror rows.
"""

import asyncio

import pytest
from django.test import override_settings

from ai.engine.core.database import get_session_factory
from ai.store import reset_store


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _django_store():
    """Run each test against the real DjangoStore backend."""
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


@pytest.mark.django_db(transaction=True)
def test_execute_select_entity_scalar_one_or_none():
    """register_agent's upsert probe: ``select(Agent).where(...)``."""
    from ai.engine.core.models import Agent as EngineAgent
    from sqlalchemy import select

    from ai.models import Agent as DjangoAgent

    async def _probe(agent_id: str) -> bool:
        factory = get_session_factory("carbon")
        async with factory() as db:
            result = await db.execute(
                select(EngineAgent).where(
                    EngineAgent.instance_id == "carbon",
                    EngineAgent.name == "orchestrator",
                )
            )
            agent = result.scalar_one_or_none()
            return agent is not None

    # No row yet → None.
    assert _run(_probe("x")) is False

    # Seed one row directly on the Django mirror, then probe again.
    DjangoAgent.objects.create(
        id="a1",
        instance_id="carbon",
        name="orchestrator",
        role="orchestrator",
        is_active=True,
    )
    assert _run(_probe("a1")) is True
    DjangoAgent.objects.filter(id="a1").delete()


@pytest.mark.django_db(transaction=True)
def test_execute_select_is_true_filter():
    """``Agent.is_active.is_(True)`` → Django ``is_active=True``."""
    from ai.engine.core.models import Agent as EngineAgent
    from sqlalchemy import select

    from ai.models import Agent as DjangoAgent

    DjangoAgent.objects.create(
        id="b1", instance_id="carbon", name="researcher", role="researcher", is_active=False
    )
    DjangoAgent.objects.create(
        id="b2", instance_id="carbon", name="planner", role="planner", is_active=True
    )

    async def _list():
        factory = get_session_factory("carbon")
        async with factory() as db:
            result = await db.execute(
                select(EngineAgent)
                .where(EngineAgent.instance_id == "carbon", EngineAgent.is_active.is_(True))
                .order_by(EngineAgent.created_at.asc())
            )
            return [a.name for a in result.scalars().all()]

    names = _run(_list())
    assert names == ["planner"]
    DjangoAgent.objects.filter(id__in=["b1", "b2"]).delete()


@pytest.mark.django_db(transaction=True)
def test_execute_select_single_column_scalar():
    """can_handoff probe: ``select(AgentHandoff.id).where(...)`` → scalar."""
    from ai.engine.core.models import AgentHandoff as EngineHandoff
    from sqlalchemy import select

    from ai.models import AgentHandoff as DjangoHandoff

    async def _exists(from_agent: str, to_agent: str) -> bool:
        factory = get_session_factory("carbon")
        async with factory() as db:
            result = await db.execute(
                select(EngineHandoff.id).where(
                    EngineHandoff.from_agent_id == from_agent,
                    EngineHandoff.to_agent_id == to_agent,
                )
            )
            return result.scalar_one_or_none() is not None

    assert _run(_exists("a", "b")) is False
    DjangoHandoff.objects.create(id="h1", from_agent_id="a", to_agent_id="b")
    assert _run(_exists("a", "b")) is True
    DjangoHandoff.objects.filter(id="h1").delete()


@pytest.mark.django_db(transaction=True)
def test_execute_skill_search_or_ilike_boolean_order():
    """The full skill-search shape: ``or_`` groups + ``ilike`` + boolean
    ``ORDER BY`` — promoted skills must sort first, then newest."""
    from ai.engine.core.models import Skill as EngineSkill
    from sqlalchemy import or_, select

    from ai.models import Skill as DjangoSkill

    DjangoSkill.objects.create(
        id="s1",
        instance_id="carbon",
        name="alpha",
        description="validate employee numbers",
        kind="dq",
        status="draft",
        author_user_id="u1",
        created_at="2026-01-01T00:00:00Z",
    )
    DjangoSkill.objects.create(
        id="s2",
        instance_id="carbon",
        name="beta",
        description="beta employee validator",
        kind="dq",
        status="instance_promoted",
        author_user_id="u2",
        created_at="2026-01-02T00:00:00Z",
    )
    DjangoSkill.objects.create(
        id="s3",
        instance_id="carbon",
        name="gamma",
        description="employee id checks",
        kind="dq",
        status="draft",
        author_user_id="u1",
        created_at="2026-01-03T00:00:00Z",
    )

    async def _search(query: str):
        like_term = f"%{query}%"
        own_or_promoted = or_(
            EngineSkill.author_user_id == "u1",
            EngineSkill.status == "instance_promoted",
        )
        name_or_desc = or_(
            EngineSkill.name.ilike(like_term),
            EngineSkill.description.ilike(like_term),
        )
        factory = get_session_factory("carbon")
        async with factory() as db:
            result = await db.execute(
                select(EngineSkill)
                .where(EngineSkill.instance_id == "carbon", own_or_promoted, name_or_desc)
                .order_by(
                    EngineSkill.status == "instance_promoted",
                    EngineSkill.created_at.desc(),
                )
            )
            return [s.id for s in result.scalars().all()]

    # All three match "employee"; promoted (s2) first, then newest draft (s3).
    assert _run(_search("employee")) == ["s2", "s3", "s1"]
    DjangoSkill.objects.filter(id__in=["s1", "s2", "s3"]).delete()


@pytest.mark.django_db(transaction=True)
def test_execute_update_statement():
    """decline-execution DML: ``update(ToolExecution).where(...).values(...)``."""
    from ai.engine.core.models import ToolExecution as EngineExec
    from sqlalchemy import update

    from ai.models import ToolExecution as DjangoExec

    DjangoExec.objects.create(
        id="e1",
        conversation_id="conv1",
        tool_name="create_dq_rule",
        status="pending_confirmation",
        confirmed_by_user=False,
    )

    async def _decline():
        from ai.engine.core.models import utcnow

        factory = get_session_factory("carbon")
        async with factory() as db:
            await db.execute(
                update(EngineExec)
                .where(EngineExec.id == "e1")
                .values(status="declined", executed_at=utcnow())
            )
            await db.commit()

    _run(_decline())
    row = DjangoExec.objects.get(pk="e1")
    assert row.status == "declined"
    assert row.executed_at is not None
    DjangoExec.objects.filter(pk="e1").delete()


@pytest.mark.django_db(transaction=True)
def test_execute_mutate_then_commit():
    """remove_agent pattern: select → mutate attribute → commit re-saves."""
    from ai.engine.core.models import Agent as EngineAgent
    from sqlalchemy import select

    from ai.models import Agent as DjangoAgent

    DjangoAgent.objects.create(
        id="c1", instance_id="carbon", name="critic", role="critic", is_active=True
    )

    async def _soft_delete(agent_id: str):
        factory = get_session_factory("carbon")
        async with factory() as db:
            result = await db.execute(
                select(EngineAgent).where(EngineAgent.id == agent_id)
            )
            agent = result.scalar_one_or_none()
            assert agent is not None
            agent.is_active = False
            await db.commit()

    _run(_soft_delete("c1"))
    assert DjangoAgent.objects.get(pk="c1").is_active is False
    DjangoAgent.objects.filter(pk="c1").delete()


@pytest.mark.django_db(transaction=True)
def test_execute_two_entity_join():
    """get_workers_for: ``select(Agent, AgentHandoff).join(...)`` → pairs."""
    from ai.engine.core.models import Agent as EngineAgent
    from ai.engine.core.models import AgentHandoff as EngineHandoff
    from sqlalchemy import select

    from ai.models import Agent as DjangoAgent
    from ai.models import AgentHandoff as DjangoHandoff

    for aid, name, role, active in [
        ("w1", "researcher", "researcher", True),
        ("w2", "planner", "planner", True),
        ("w3", "disabled", "domain_specialist", False),
    ]:
        DjangoAgent.objects.create(
            id=aid, instance_id="carbon", name=name, role=role, is_active=active
        )
    for hid, frm, to in [("x1", "orch", "w1"), ("x2", "orch", "w2"), ("x3", "orch", "w3")]:
        DjangoHandoff.objects.create(id=hid, from_agent_id=frm, to_agent_id=to)

    async def _workers(agent_id: str):
        factory = get_session_factory("carbon")
        async with factory() as db:
            result = await db.execute(
                select(EngineAgent, EngineHandoff)
                .join(EngineHandoff, EngineHandoff.to_agent_id == EngineAgent.id)
                .where(
                    EngineHandoff.from_agent_id == agent_id,
                    EngineAgent.is_active.is_(True),
                )
                .order_by(EngineAgent.created_at.asc())
            )
            return [(agent.name, handoff.id) for agent, handoff in result.all()]

    pairs = _run(_workers("orch"))
    assert ("researcher", "x1") in pairs
    assert ("planner", "x2") in pairs
    # Disabled worker w3 must not appear.
    assert all(name != "disabled" for name, _hid in pairs)
    DjangoAgent.objects.filter(id__in=["w1", "w2", "w3"]).delete()
    DjangoHandoff.objects.filter(id__in=["x1", "x2", "x3"]).delete()


@pytest.mark.django_db(transaction=True)
def test_execute_text_select_and_dml():
    """vector_store raw SQL: single-col select, multi-col select with ``::``
    casts, and an UPDATE statement."""
    from sqlalchemy import text

    from ai.models import VectorEmbedding

    VectorEmbedding.objects.create(
        id="v1",
        collection="coll1",
        instance_id="carbon",
        document="doc one",
        metadata_json={"k": "a"},
        embedding_json="[1, 2, 3]",
    )
    VectorEmbedding.objects.create(
        id="v2",
        collection="coll1",
        instance_id="carbon",
        document="doc two",
        metadata_json={"k": "b"},
        embedding_json="[4, 5, 6]",
    )

    async def _probe():
        factory = get_session_factory("carbon")
        async with factory() as db:
            # Single-column scalar probe (upsert pattern).
            result = await db.execute(
                text("SELECT id FROM vector_embeddings WHERE id = :id AND collection = :coll"),
                {"id": "v1", "coll": "coll1"},
            )
            existing = result.scalar_one_or_none()
            # Multi-column with ::jsonb operator → mappings rows.
            result2 = await db.execute(
                text(
                    "SELECT id, document, metadata_json::jsonb->>'k' AS k "
                    "FROM vector_embeddings WHERE collection = :coll AND metadata_json::jsonb->>'k' = :w_k"
                ),
                {"coll": "coll1", "w_k": "a"},
            )
            rows = result2.mappings().all()
            # DML (raw UPDATE).
            result3 = await db.execute(
                text("UPDATE vector_embeddings SET document = :doc WHERE id = :id"),
                {"id": "v2", "doc": "doc two updated"},
            )
            return existing, rows, result3.rowcount

    existing, rows, rowcount = _run(_probe())
    assert existing == "v1"
    assert rows and rows[0]["id"] == "v1"
    assert rows[0]["k"] == "a"
    assert rowcount == 1
    assert VectorEmbedding.objects.get(pk="v2").document == "doc two updated"
    VectorEmbedding.objects.filter(id__in=["v1", "v2"]).delete()


@pytest.mark.django_db(transaction=True)
def test_execute_multiple_results_found_raises():
    """scalar_one_or_none() must raise when >1 row matches (mirrors SQLAlchemy)."""
    from ai.engine.core.models import Agent as EngineAgent
    from sqlalchemy import select

    from ai.models import Agent as DjangoAgent
    from ai.store import _MultipleResultsFound

    DjangoAgent.objects.create(id="d1", instance_id="carbon", name="n1", role="r", is_active=True)
    DjangoAgent.objects.create(id="d2", instance_id="carbon", name="n2", role="r", is_active=True)

    async def _probe():
        factory = get_session_factory("carbon")
        async with factory() as db:
            result = await db.execute(
                select(EngineAgent).where(EngineAgent.role == "r")
            )
            return result.scalar_one_or_none()

    with pytest.raises(_MultipleResultsFound):
        _run(_probe())
    DjangoAgent.objects.filter(id__in=["d1", "d2"]).delete()


@pytest.mark.django_db(transaction=True)
def test_execute_register_agent_commit_backfills_pk():
    """register_agent pattern: ``add(engine_obj)`` → ``commit()`` must
    back-fill the DB-generated PK onto the ENGINE instance (SQLAlchemy's
    post-flush attribute population), and ``refresh()`` must then work.

    Regression for the smoke-test catch: without the back-fill, ``agent.id``
    stayed ``None`` after commit, so ``seed_defaults`` could not wire handoff
    edges (``agents[name].id``) and the post-commit ``await db.refresh(agent)``
    raised ``DoesNotExist``.
    """
    from ai.engine.core.models import Agent as EngineAgent

    from ai.models import Agent as DjangoAgent

    async def _register(name: str) -> str:
        factory = get_session_factory("carbon")
        async with factory() as db:
            agent = EngineAgent(
                instance_id="carbon",
                name=name,
                role="researcher",
                is_active=True,
            )
            db.add(agent)
            await db.commit()
            # PK must be populated on the engine object right after commit.
            assert agent.id is not None
            # refresh() on the engine object must succeed against the DB.
            await db.refresh(agent)
            return agent.id

    agent_id = _run(_register("smoke_agent"))
    assert DjangoAgent.objects.get(pk=agent_id).name == "smoke_agent"
    DjangoAgent.objects.filter(pk=agent_id).delete()


@pytest.mark.django_db(transaction=True)
def test_execute_rollback_outside_atomic_noop():
    """``await db.rollback()`` outside an ``atomic`` block must be a no-op,
    not raise ``TransactionManagementError`` (Django autocommit mode)."""
    from ai.engine.core.models import Agent as EngineAgent
    from sqlalchemy import select

    from ai.models import Agent as DjangoAgent

    DjangoAgent.objects.create(
        id="rb1", instance_id="carbon", name="rb", role="r", is_active=True
    )

    async def _probe() -> bool:
        factory = get_session_factory("carbon")
        async with factory() as db:
            await db.rollback()  # must not raise
            result = await db.execute(
                select(EngineAgent).where(EngineAgent.id == "rb1")
            )
            return result.scalar_one_or_none() is not None

    assert _run(_probe()) is True
    DjangoAgent.objects.filter(pk="rb1").delete()
