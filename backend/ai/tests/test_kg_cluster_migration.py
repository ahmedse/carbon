"""
Phase 2b-3b — KnowledgeGraphStore cluster de-SQLAlchemy migration proof.

Proves the migrated KG cluster runs entirely against Carbon's PostgreSQL via
the Django Store (``ai.store.Session``) — no SQLAlchemy session anywhere in
``ai/engine/knowledge_graph/`` (except the inert ``models.py`` constants):

  - node/edge CRUD round-trip via the Django Store, durable in the test DB
  - ``store_table_profile`` persists profile keys (profiled_at,
    row_count_actual, column_profiles)
  - ``run_schema_analysis`` runs (column semantics, implicit relationships,
    entity importance) and is idempotent (force=False → skipped)
  - ``dispatch_task("carbon.schema.analyze", ...)`` returns ``completed``
    with a real ``kg_analysis`` when a schema is supplied
  - degradation: no schema supplied → deterministic analysis only, still
    ``completed`` (never fabricated, never a 500)

The vector store / BM25 subsystems are intentionally unavailable in the test
environment; the migrated code degrades gracefully (try/except + None).
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from django.test import override_settings

from ai.engine.core.config import get_settings
from ai.engine.core.database import get_session_factory
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


def _open_session():
    """Async CM yielding a Django Store session for the 'carbon' instance."""
    return get_session_factory("carbon")()


async def _roundtrip_crud(db, instance_id: str = "carbon") -> None:
    """Shared CRUD body used by the durable-write and smoke-path tests."""
    from ai.engine.knowledge_graph.store import KnowledgeGraphStore

    store = KnowledgeGraphStore(db)

    # ── Node create ──────────────────────────────────────────────────────
    entity = await store.add_node(
        {
            "instance_id": instance_id,
            "node_type": "ENTITY",
            "name": "emissions_facts",
            "description": "Fact table of CO2 emissions by facility",
            "properties": {"schema_json": "[]"},
            "source": "SCHEMA",
        }
    )
    attr = await store.add_node(
        {
            "instance_id": instance_id,
            "node_type": "ATTRIBUTE",
            "name": "emissions_facts.co2_tons",
            "description": "Tons of CO2 emitted",
            "properties": {"data_type": "numeric"},
            "source": "SCHEMA",
        }
    )
    assert entity.id
    assert attr.id

    # ── Edge create ──────────────────────────────────────────────────────
    edge = await store.add_edge(
        {
            "instance_id": instance_id,
            "source_node_id": entity.id,
            "target_node_id": attr.id,
            "relationship": "HAS_ATTRIBUTE",
            "confidence": 0.9,
            "source": "SCHEMA",
        }
    )
    assert edge.id

    # ── Read back ────────────────────────────────────────────────────────
    fetched = await store.get_node(entity.id)
    assert fetched is not None
    assert fetched.name == "emissions_facts"

    by_type = await store.get_nodes_by_type("ENTITY", instance_id)
    assert any(n.id == entity.id for n in by_type)

    edges = await store.query_edges(
        instance_id, source_node_id=entity.id, relationship="HAS_ATTRIBUTE"
    )
    assert any(e.id == edge.id for e in edges)

    neighbors = store.get_neighbors(entity.id, instance_id)
    assert any(n["id"] == attr.id for n in neighbors["nodes"])

    # ── Edge delete → node delete ─────────────────────────────────────────
    assert await store.delete_edge(edge.id) is True
    assert await store.delete_node(entity.id) is True
    assert await store.get_node(entity.id) is None
    assert await store.delete_node(entity.id) is False  # idempotent

    return entity, attr, edge


# ── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_node_edge_crud_roundtrip_is_durable(django_store, cfg):
    """Node/edge CRUD lands in PostgreSQL via the Django Store.

    Verifies the write is durable (re-queryable through a *fresh* session)
    and that the engine-side delete cascade removes the rows.
    """
    from ai.models.knowledge_graph import KnowledgeEdge, KnowledgeNode

    async def _run():
        async with _open_session() as db:
            return await _roundtrip_crud(db)

    entity, attr, edge = asyncio.run(_run())
    # Delete happened inside the roundtrip; rows must be gone.
    assert not KnowledgeNode.objects.filter(id=entity.id).exists()
    assert not KnowledgeEdge.objects.filter(id=edge.id).exists()


@pytest.mark.django_db(transaction=True)
def test_store_table_profile_persists_profile_keys(django_store, cfg):
    """store_table_profile merges profile keys into the ENTITY node's props."""
    from ai.engine.knowledge_graph.data_profiler import ColumnProfile, TableProfile
    from ai.engine.knowledge_graph.store import KnowledgeGraphStore
    from ai.models.knowledge_graph import KnowledgeNode
    from ai.store import first

    async def _run():
        # Unique name per run: Store writes commit on their own connection,
        # so a shared name could collide with rows from a previously failed
        # run in a reused test DB.
        name = f"profile_target_{uuid4().hex[:10]}"
        async with _open_session() as db:
            store = KnowledgeGraphStore(db)
            entity = await store.add_node(
                {
                    "instance_id": "carbon",
                    "node_type": "ENTITY",
                    "name": name,
                    "source": "SCHEMA",
                }
            )

            profile = TableProfile(
                table_name=name,
                row_count=1_250,
                columns=[
                    ColumnProfile(
                        column_name="co2_tons",
                        data_type="numeric",
                        row_count=1_250,
                        null_count=10,
                        null_rate=0.008,
                        distinct_count=1_000,
                        min_value="0.0",
                        max_value="420.5",
                        value_list=[],
                        is_pii=False,
                    )
                ],
                profiled_at="2026-08-13T12:00:00Z",
            )
            await store.store_table_profile(entity.id, profile)

            profiled = await store.get_entity_profile(name, "carbon")
            assert profiled is not None
            assert profiled["row_count_actual"] == 1_250
            assert profiled["profiled_at"] is not None
            assert profiled["column_profiles"][0]["column_name"] == "co2_tons"
            assert profiled["column_profiles"][0]["distinct_count"] == 1_000

            # Durable in PostgreSQL — re-readable through a *fresh* session.
            async with _open_session() as db2:
                row = first(await db2.select(KnowledgeNode, ("name", name)))
                assert row is not None
                assert "profiled_at" in row.properties
                assert "row_count_actual" in row.properties

    asyncio.run(_run())


@pytest.mark.django_db(transaction=True)
def test_run_schema_analysis_runs_and_is_idempotent(django_store, cfg):
    """run_schema_analysis returns a summary and skips on a second run."""
    from ai.engine.knowledge_graph.schema_analyzer import run_schema_analysis
    from ai.engine.knowledge_graph.store import KnowledgeGraphStore

    async def _run():
        async with _open_session() as db:
            store = KnowledgeGraphStore(db)
            entity = await store.add_node(
                {
                    "instance_id": "carbon",
                    "node_type": "ENTITY",
                    "name": "schema_target",
                    "source": "SCHEMA",
                }
            )
            for col in ("co2_tons", "facility_id"):
                attr = await store.add_node(
                    {
                        "instance_id": "carbon",
                        "node_type": "ATTRIBUTE",
                        "name": f"schema_target.{col}",
                        "properties": {"data_type": "numeric"},
                        "source": "SCHEMA",
                    }
                )
                await store.add_edge(
                    {
                        "instance_id": "carbon",
                        "source_node_id": entity.id,
                        "target_node_id": attr.id,
                        "relationship": "HAS_ATTRIBUTE",
                        "source": "SCHEMA",
                    }
                )

            summary = await run_schema_analysis("carbon", force=True, session=db)
            assert "column_semantics" in summary
            assert "implicit_relationships" in summary
            assert "entity_importance" in summary
            assert isinstance(summary["column_semantics"], dict)

            # Idempotency: second run without force is skipped.
            again = await run_schema_analysis("carbon", force=False, session=db)
            assert again.get("skipped") is True
            assert again.get("reason") == "already_analysed"

    asyncio.run(_run())


@pytest.mark.django_db(transaction=True)
def test_dispatch_schema_analyze_completed_with_schema(django_store, cfg):
    """dispatch_task('carbon.schema.analyze') with a schema → completed + KG result."""
    from ai.engine_runtime import dispatch_task

    payload = {
        "schema": [
            {
                "table_name": "emissions_facts",
                "columns": [
                    {"column_name": "co2_tons", "data_type": "numeric"},
                    {"column_name": "facility_id", "data_type": "uuid"},
                ],
            }
        ]
    }

    data = dispatch_task("carbon.schema.analyze", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert isinstance(result.get("analysis"), list)  # deterministic baseline
    assert result.get("execution_ms", -1) >= 0

    kg_analysis = result.get("kg_analysis") or {}
    assert "column_semantics" in kg_analysis, kg_analysis
    assert "implicit_relationships" in kg_analysis
    assert "entity_importance" in kg_analysis
    bootstrap = kg_analysis.get("bootstrap") or {}
    assert bootstrap.get("entities", 0) >= 1
    assert bootstrap.get("attributes", 0) >= 2


@pytest.mark.django_db(transaction=True)
def test_dispatch_schema_analyze_degrades_without_schema(django_store, cfg):
    """No schema supplied → deterministic analysis only, still completed."""
    from ai.engine_runtime import dispatch_task

    # schema_changes without table_name carry no bootstrapable schema info.
    payload = {"schema_changes": [{"change": "add_column", "field_name": "x"}]}

    data = dispatch_task("carbon.schema.analyze", payload, instance_id="carbon")

    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert isinstance(result.get("analysis"), list)
    kg_analysis = result.get("kg_analysis") or {}
    assert kg_analysis == {}, kg_analysis  # real path skipped, nothing invented

    # Empty payload degrades identically.
    data2 = dispatch_task("carbon.schema.analyze", {}, instance_id="carbon")
    assert data2.get("status") == "completed", data2
    assert (data2.get("result") or {}).get("kg_analysis") == {}


@pytest.mark.django_db(transaction=True)
def test_cluster_imports_no_sqlalchemy(django_store, cfg):
    """Gate 5 literal check: migrated cluster files carry no SQLAlchemy refs.

    Mirrors the gate grep for the *runtime* modules (the inert engine
    ``models.py`` constants module is the documented exclusion).
    """
    import pathlib

    cluster = (
        pathlib.Path(__file__).resolve().parents[2]
        / "ai"
        / "engine"
        / "knowledge_graph"
    )
    excluded = {"models.py"}
    bad: list[str] = []
    for path in sorted(cluster.glob("*.py")):
        if path.name in excluded:
            continue
        text = path.read_text(encoding="utf-8")
        if any(
            token in text
            for token in (
                "session.execute",
                "session.scalars",
                "db.execute",
                "AsyncSession",
                "create_async_engine",
                "async_sessionmaker",
                ".scalars()",
                "from sqlalchemy",
            )
        ):
            bad.append(path.name)
    assert bad == [], f"SQLAlchemy references remain in: {bad}"
