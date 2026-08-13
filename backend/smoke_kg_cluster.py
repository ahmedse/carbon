"""
Phase 2b-3b smoke script — KG cluster runs on the Django Store (PostgreSQL).

Proves the de-SQLAlchemy'd KnowledgeGraphStore cluster works end-to-end
against Carbon's PostgreSQL via ``ai.store`` (Django backend), plus the
wired ``carbon.schema.analyze`` handler with graceful degradation.

Run from ``backend/``::

    /home/ahmed/aast/carbon/.venv/bin/python smoke_kg_cluster.py

Steps
-----
(a) node/edge CRUD round-trip via ``KnowledgeGraphStore`` (``add_node`` /
    ``add_edge`` / ``get_node`` / ``get_neighbors`` / ``store_table_profile`` /
    ``load_graph``) — durable in PostgreSQL (re-read through a *fresh*
    session).
(b) ``run_schema_analysis(instance_id, force=True)`` → summary dict.
(c) ``dispatch_task("carbon.schema.analyze", ...)`` → ``completed`` with a real
    ``kg_analysis`` (no LLM, no host DB required).

Rows are written under the distinctive instance ``smoke_kg_cluster`` (not
``carbon``) and deleted on success.  If the script crashes mid-way, a few
``smoke_kg_cluster`` rows may remain — safe to delete:
``KnowledgeNode.objects.filter(instance_id='smoke_kg_cluster').delete()``.

No real host DB is needed: ``HOST_DB_URL`` is empty in dev, so the
anomaly-detect live-profile path is skipped by design.
"""

from __future__ import annotations

import asyncio
import os
import sys
from uuid import uuid4

# CRITICAL: settings.py reads AI_STORE_BACKEND at import time — the Django
# backend must be selected BEFORE django.setup().
os.environ["AI_STORE_BACKEND"] = "django"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from ai.engine.core.config import get_settings  # noqa: E402
from ai.engine.core.database import get_session_factory  # noqa: E402
from ai.engine_runtime import dispatch_task  # noqa: E402
from ai.models.knowledge_graph import KnowledgeNode  # noqa: E402
from ai.store import first, reset_store  # noqa: E402

INSTANCE = "smoke_kg_cluster"


def _session() -> object:
    """Async CM yielding a Django Store session for the smoke instance."""
    return get_session_factory(INSTANCE)()


async def _step_crud() -> None:
    """(a) CRUD round-trip, durable in PostgreSQL."""
    from ai.engine.knowledge_graph.data_profiler import ColumnProfile, TableProfile
    from ai.engine.knowledge_graph.store import KnowledgeGraphStore

    suffix = uuid4().hex[:8]
    entity_name = f"smoke_entity_{suffix}"

    async with _session() as db:
        store = KnowledgeGraphStore(db)

        entity = await store.add_node(
            {
                "instance_id": INSTANCE,
                "node_type": "ENTITY",
                "name": entity_name,
                "description": "smoke test entity",
                "source": "SCHEMA",
            }
        )
        attr = await store.add_node(
            {
                "instance_id": INSTANCE,
                "node_type": "ATTRIBUTE",
                "name": f"{entity_name}.co2_tons",
                "description": "tons of CO2",
                "properties": {"data_type": "numeric"},
                "source": "SCHEMA",
            }
        )
        edge = await store.add_edge(
            {
                "instance_id": INSTANCE,
                "source_node_id": entity.id,
                "target_node_id": attr.id,
                "relationship": "HAS_ATTRIBUTE",
                "source": "SCHEMA",
            }
        )

        fetched = await store.get_node(entity.id)
        assert fetched is not None and fetched.name == entity_name
        neighbors = store.get_neighbors(entity.id, INSTANCE)
        assert any(n["id"] == attr.id for n in neighbors["nodes"])

        profile = TableProfile(
            table_name=entity_name,
            row_count=777,
            columns=[
                ColumnProfile(
                    column_name="co2_tons",
                    data_type="numeric",
                    row_count=777,
                    null_count=0,
                    null_rate=0.0,
                    distinct_count=700,
                    min_value="0.0",
                    max_value="99.9",
                    value_list=[],
                    is_pii=False,
                )
            ],
            profiled_at="2026-08-13T12:00:00Z",
        )
        await store.store_table_profile(entity.id, profile)
        profiled = await store.get_entity_profile(entity_name, INSTANCE)
        assert profiled is not None and profiled["row_count_actual"] == 777

    # Durability: a FRESH store/session must see the rows (PostgreSQL).
    async with _session() as db2:
        store2 = KnowledgeGraphStore(db2)
        await store2.load_graph(INSTANCE)
        again = await store2.get_node(entity.id)
        assert again is not None, "node not durable across sessions"
        assert "profiled_at" in again.properties

        edges = await store2.query_edges(
            INSTANCE, source_node_id=entity.id, relationship="HAS_ATTRIBUTE"
        )
        assert any(e.id == edge.id for e in edges)

        # Cleanup
        await store2.delete_edge(edge.id)
        await store2.delete_node(entity.id)
        assert await store2.get_node(entity.id) is None

    print(
        f"  [ok] CRUD round-trip durable: {entity_name} "
        f"(entity={entity.id[:8]}…, edge={edge.id[:8]}…), profile row_count=777"
    )


async def _step_schema_analysis() -> None:
    """(b) run_schema_analysis(force=True) returns a summary dict."""
    from ai.engine.knowledge_graph.schema_analyzer import run_schema_analysis
    from ai.engine.knowledge_graph.store import KnowledgeGraphStore

    suffix = uuid4().hex[:8]
    entity_name = f"smoke_schema_{suffix}"

    async with _session() as db:
        store = KnowledgeGraphStore(db)
        entity = await store.add_node(
            {
                "instance_id": INSTANCE,
                "node_type": "ENTITY",
                "name": entity_name,
                "source": "SCHEMA",
            }
        )
        for col in ("co2_tons", "facility_id"):
            attr = await store.add_node(
                {
                    "instance_id": INSTANCE,
                    "node_type": "ATTRIBUTE",
                    "name": f"{entity_name}.{col}",
                    "properties": {"data_type": "numeric"},
                    "source": "SCHEMA",
                }
            )
            await store.add_edge(
                {
                    "instance_id": INSTANCE,
                    "source_node_id": entity.id,
                    "target_node_id": attr.id,
                    "relationship": "HAS_ATTRIBUTE",
                    "source": "SCHEMA",
                }
            )

        summary = await run_schema_analysis(INSTANCE, force=True, session=db)
        for key in ("column_semantics", "implicit_relationships", "entity_importance"):
            assert key in summary, f"missing {key}"

        # Idempotency
        again = await run_schema_analysis(INSTANCE, force=False, session=db)
        assert again.get("skipped") is True, again

        # Cleanup
        for e in await store.query_edges(INSTANCE, source_node_id=entity.id):
            await store.delete_edge(e.id)
        await store.delete_node(entity.id)

    print(
        "  [ok] run_schema_analysis -> summary keys: "
        + ", ".join(sorted(summary.keys()))
    )
    print(f"  [ok] idempotent second run -> {again}")


def _step_dispatch() -> None:
    """(c) dispatch_task('carbon.schema.analyze') -> completed + kg_analysis."""
    payload = {
        "schema": [
            {
                "table_name": f"smoke_dispatch_{uuid4().hex[:6]}",
                "columns": [
                    {"column_name": "co2_tons", "data_type": "numeric"},
                    {"column_name": "facility_id", "data_type": "uuid"},
                ],
            }
        ]
    }
    data = dispatch_task("carbon.schema.analyze", payload, instance_id=INSTANCE)
    status = data.get("status")
    result = data.get("result") or {}
    kg = result.get("kg_analysis") or {}
    print(f"  [{'ok' if status == 'completed' else 'FAIL'}] dispatch schema.analyze -> {status}")
    print(f"      kg_analysis keys: {sorted(kg.keys())}")
    print(f"      bootstrap: {kg.get('bootstrap')}")
    if status != "completed":
        raise AssertionError(f"dispatch failed: {data}")

    # Degradation: no schema -> deterministic only, still completed.
    degraded = dispatch_task("carbon.schema.analyze", {}, instance_id=INSTANCE)
    assert degraded.get("status") == "completed", degraded
    assert (degraded.get("result") or {}).get("kg_analysis") == {}
    print("  [ok] degradation (no schema) -> completed, kg_analysis={}")


async def _cleanup() -> None:
    """Best-effort purge of any smoke rows left by an earlier crash."""
    from asgiref.sync import sync_to_async

    try:
        n, _ = await sync_to_async(
            KnowledgeNode.objects.filter(instance_id=INSTANCE).delete,
            thread_sensitive=True,
        )()
        if n:
            print(f"  [ok] cleaned {n} leftover smoke rows (instance={INSTANCE})")
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] cleanup skipped: {exc}")


async def _main() -> int:
    get_settings.cache_clear()
    reset_store()  # Django backend (env selected before django.setup())

    print("KG cluster smoke (Django Store / PostgreSQL)")
    print(f"  instance: {INSTANCE}")
    await _cleanup()
    try:
        await _step_crud()
        await _step_schema_analysis()
        _step_dispatch()
    finally:
        await _cleanup()
    print("SMOKE PASSED: kg cluster on Django Store (a) CRUD (b) analysis (c) dispatch")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(_main()))
    except Exception as exc:  # noqa: BLE001
        print(f"SMOKE FAILED: {exc}")
        raise SystemExit(1)
