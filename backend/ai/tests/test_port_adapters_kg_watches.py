"""P2-02d-e — contract tests for the host KG + watches adapters.

Proves ``DjangoKGAdapter`` and ``DjangoWatchAdapter`` implement their engine
ports over the real DjangoStore and that ``scope_q()`` keeps cross-tenant reads
empty.  Offline only: no LLM, no network — every assertion reads back the
Django ORM rows the adapters write.
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from ai.store import get_store, reset_store

INSTANCE = "test-instance-1"
OTHER_INSTANCE = "test-instance-2"


@pytest.fixture
def django_store():
    """Pin the AI store to the Django backend for the duration of each test."""
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


def _run(coro):
    return asyncio.run(coro)


# ── KnowledgeGraphStore adapter ─────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_kg_add_and_get_node(django_store):
    from ai.adapters.kg import DjangoKGAdapter

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            adapter = DjangoKGAdapter(db)
            record = await adapter.add_node(
                {
                    "instance_id": INSTANCE,
                    "name": "co2e_total",
                    "node_type": "METRIC",
                    "description": "total co2e",
                }
            )
            assert record["name"] == "co2e_total"
            assert record["node_type"] == "METRIC"

            fetched = await adapter.get_node(record["id"])
            assert fetched is not None
            assert fetched["id"] == record["id"]
            assert fetched["instance_id"] == INSTANCE

    _run(_go())


@pytest.mark.django_db(transaction=True)
def test_kg_get_nodes_by_type_filters(django_store):
    from ai.adapters.kg import DjangoKGAdapter

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            adapter = DjangoKGAdapter(db)
            await adapter.add_node({"instance_id": INSTANCE, "name": "m1", "node_type": "METRIC"})
            await adapter.add_node({"instance_id": INSTANCE, "name": "m2", "node_type": "METRIC"})
            await adapter.add_node({"instance_id": INSTANCE, "name": "t1", "node_type": "TABLE"})

            metrics = await adapter.get_nodes_by_type(INSTANCE, "METRIC")
            assert {n["name"] for n in metrics} == {"m1", "m2"}

            tables = await adapter.get_nodes_by_type(INSTANCE, "TABLE")
            assert [n["name"] for n in tables] == ["t1"]

            # Cross-tenant read must be empty (scope_q instance filter).
            other = await adapter.get_nodes_by_type(OTHER_INSTANCE, "METRIC")
            assert other == []

    _run(_go())


@pytest.mark.django_db(transaction=True)
def test_kg_delete_node_removes_it(django_store):
    from ai.adapters.kg import DjangoKGAdapter

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            adapter = DjangoKGAdapter(db)
            record = await adapter.add_node({"instance_id": INSTANCE, "name": "gone", "node_type": "METRIC"})
            assert await adapter.get_node(record["id"]) is not None
            assert await adapter.delete_node(record["id"]) is True
            assert await adapter.get_node(record["id"]) is None

    _run(_go())


@pytest.mark.django_db(transaction=True)
def test_kg_add_and_query_edge(django_store):
    from ai.adapters.kg import DjangoKGAdapter

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            adapter = DjangoKGAdapter(db)
            src = await adapter.add_node({"instance_id": INSTANCE, "name": "src", "node_type": "TABLE"})
            dst = await adapter.add_node({"instance_id": INSTANCE, "name": "dst", "node_type": "TABLE"})

            edge = await adapter.add_edge(
                {
                    "instance_id": INSTANCE,
                    "source_id": src["id"],
                    "target_id": dst["id"],
                    "relationship": "REFERENCES",
                }
            )
            assert edge["source_id"] == src["id"]
            assert edge["target_id"] == dst["id"]

            edges = await adapter.query_edges(INSTANCE, "REFERENCES")
            assert len(edges) == 1
            assert edges[0]["id"] == edge["id"]

    _run(_go())


@pytest.mark.django_db(transaction=True)
def test_kg_delete_edge_removes_it(django_store):
    from ai.adapters.kg import DjangoKGAdapter

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            adapter = DjangoKGAdapter(db)
            src = await adapter.add_node({"instance_id": INSTANCE, "name": "src", "node_type": "TABLE"})
            dst = await adapter.add_node({"instance_id": INSTANCE, "name": "dst", "node_type": "TABLE"})
            edge = await adapter.add_edge(
                {"instance_id": INSTANCE, "source_id": src["id"], "target_id": dst["id"], "relationship": "REFERENCES"}
            )

            assert len(await adapter.query_edges(INSTANCE)) == 1
            assert await adapter.delete_edge(edge["id"]) is True
            assert len(await adapter.query_edges(INSTANCE)) == 0

    _run(_go())


# ── UserWatchStore adapter ──────────────────────────────────────────────


def _make_watch(user, name, enabled):
    from ai.models.core import AIAnomalyWatch

    return AIAnomalyWatch.objects.create(
        user=user,
        instance_id=INSTANCE,
        name=name,
        kpi_expression="avg(co2e)",
        condition={"table": "emissions", "column": "co2e", "operator": ">", "aggregation": "avg"},
        threshold=100.0,
        enabled=enabled,
        visibility="shared",
    )


@pytest.mark.django_db(transaction=True)
def test_watches_list_enabled_only(django_store):
    from ai.adapters.watches import DjangoWatchAdapter

    User = get_user_model()
    user = User.objects.create_user(username=f"watch-list-{uuid4().hex[:8]}", password="secret123")
    _make_watch(user, "enabled-watch", True)
    _make_watch(user, "disabled-watch", False)

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            adapter = DjangoWatchAdapter(db)
            return [w["name"] for w in await adapter.list_enabled_watches(INSTANCE)]

    names = _run(_go())
    assert "enabled-watch" in names
    assert "disabled-watch" not in names


@pytest.mark.django_db(transaction=True)
def test_watches_record_fire_increments(django_store):
    from ai.adapters.watches import DjangoWatchAdapter

    User = get_user_model()
    user = User.objects.create_user(username=f"watch-fire-{uuid4().hex[:8]}", password="secret123")
    watch = _make_watch(user, "fire-watch", True)

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            adapter = DjangoWatchAdapter(db)
            return await adapter.record_fire(watch.pk)

    record = _run(_go())
    assert record is not None
    assert record["id"] == watch.pk
    assert record["fire_count"] == 1
    assert record["last_fired_at"] is not None
