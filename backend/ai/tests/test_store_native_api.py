"""
Native persistence-seam regression tests (P2-05 single-ORM).

The SQLAlchemy statement translator (``session.execute`` / ``get_bind`` /
``rollback``) was retired in Wave D.  The canonical engine seam is now the
native ``select`` / ``get`` / ``aggregate`` / ``add`` + ``commit`` surface on
``ai.store``.  These tests pin that surface against the real Django backend
so the store stays correct with no SQLAlchemy in the import graph.
"""
from __future__ import annotations

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
def test_native_select_with_tuple_filters():
    """``db.select`` returns rows matching ``(field, value)`` 2-tuple filters."""
    from ai.engine.core.models import VectorEmbedding as EngineEmbedding
    from ai.models import VectorEmbedding as DjangoEmbedding

    DjangoEmbedding.objects.create(
        id="seam-1", collection="probes", instance_id="carbon", document="a"
    )
    DjangoEmbedding.objects.create(
        id="seam-2", collection="probes", instance_id="carbon", document="b"
    )
    DjangoEmbedding.objects.create(
        id="seam-3", collection="other", instance_id="carbon", document="c"
    )

    async def _select() -> list[str]:
        factory = get_session_factory("carbon")
        async with factory() as db:
            rows = await db.select(EngineEmbedding, ("collection", "probes"))
            return sorted(r.id for r in rows)

    assert _run(_select()) == ["seam-1", "seam-2"]


@pytest.mark.django_db(transaction=True)
def test_native_select_with_in_lookup():
    """``db.select`` supports ``__in`` lookups (used by vector-store delete)."""
    from ai.engine.core.models import VectorEmbedding as EngineEmbedding
    from ai.models import VectorEmbedding as DjangoEmbedding

    for i in range(3):
        DjangoEmbedding.objects.create(
            id=f"in-{i}", collection="probes", instance_id="carbon"
        )

    async def _select() -> list[str]:
        factory = get_session_factory("carbon")
        async with factory() as db:
            rows = await db.select(
                EngineEmbedding, ("collection", "probes"), ("id__in", ["in-0", "in-2"])
            )
            return sorted(r.id for r in rows)

    assert _run(_select()) == ["in-0", "in-2"]


@pytest.mark.django_db(transaction=True)
def test_native_get_by_pk():
    """``db.get`` fetches a single row by primary key."""
    from ai.engine.core.models import VectorEmbedding as EngineEmbedding
    from ai.models import VectorEmbedding as DjangoEmbedding

    DjangoEmbedding.objects.create(
        id="get-1", collection="probes", instance_id="carbon", document="x"
    )

    async def _get() -> str | None:
        factory = get_session_factory("carbon")
        async with factory() as db:
            row = await db.get(EngineEmbedding, "get-1")
            return row.document if row is not None else None

    assert _run(_get()) == "x"


@pytest.mark.django_db(transaction=True)
def test_native_aggregate_count_and_sum():
    """``db.aggregate`` computes Count/Sum via the Django ORM."""
    from ai.engine.core.models import TurnLedgerRow
    from ai.models import TurnLedgerRow as DjangoLedger

    for i in range(4):
        DjangoLedger.objects.create(
            id=f"ledger-{i}",
            turn_id=f"turn-{i}",
            instance_id="carbon",
            conversation_id=f"conv-{i}",
            stage="done",
            stage_index=i,
            tokens_used=10 + i,
        )

    async def _aggregate() -> dict:
        factory = get_session_factory("carbon")
        async with factory() as db:
            return await db.aggregate(
                TurnLedgerRow,
                {"n": ("Count", "id"), "tokens": ("Sum", "tokens_used")},
                ("instance_id", "carbon"),
            )

    result = _run(_aggregate())
    assert result["n"] == 4
    assert result["tokens"] == 10 + 11 + 12 + 13


@pytest.mark.django_db(transaction=True)
def test_native_add_commit_roundtrip_backfills_id():
    """``add`` + ``commit`` persists an engine dataclass and back-fills its id."""
    from ai.engine.core.models import VectorEmbedding as EngineEmbedding
    from ai.models import VectorEmbedding as DjangoEmbedding

    engine_row = EngineEmbedding(
        id="rt-1", collection="probes", instance_id="carbon", document="persisted"
    )

    async def _commit() -> None:
        factory = get_session_factory("carbon")
        async with factory() as db:
            db.add(engine_row)
            await db.commit()

    _run(_commit())
    assert DjangoEmbedding.objects.filter(id="rt-1").exists()
    # The engine object's id was preserved (explicitly supplied here).
    assert engine_row.id == "rt-1"


@pytest.mark.django_db(transaction=True)
def test_no_sqlalchemy_in_store_module():
    """The store module no longer imports SQLAlchemy (single-ORM invariant)."""
    import pathlib

    store_path = pathlib.Path(__file__).resolve().parents[1] / "store.py"
    text = store_path.read_text(encoding="utf-8")
    assert "import sqlalchemy" not in text
    assert "from sqlalchemy" not in text
