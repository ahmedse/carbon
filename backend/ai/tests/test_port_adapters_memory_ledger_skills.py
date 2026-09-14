"""P2-02a-c — contract tests for the Django host adapters.

Proves each adapter implements its engine port over the real DjangoStore and
that ``scope_q()`` keeps cross-tenant reads empty.  Offline only: no LLM, no
network — every assertion reads back the Django ORM rows the adapters write.
"""

from __future__ import annotations

import asyncio

import pytest
from django.test import override_settings

from ai.models.core import TurnLedgerRow
from ai.store import get_store, reset_store

INSTANCE = "test-instance-1"
OTHER_INSTANCE = "test-instance-2"
USER = "user-1"


@pytest.fixture
def django_store():
    """Pin the AI store to the Django backend for the duration of each test."""
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.django_db(transaction=True)
def test_episodic_record_and_search_scoped(django_store):
    from ai.adapters.memory import DjangoEpisodicAdapter

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            adapter = DjangoEpisodicAdapter(db)

            episode_id = await adapter.record_event(
                INSTANCE,
                "anomaly",
                "emissions spiked in scope 1",
                details={"pct": 12.5},
                host_user_id=USER,
            )
            assert episode_id

            found = await adapter.search(INSTANCE, host_user_id=USER)
            assert any(e["id"] == episode_id for e in found)

            # Cross-tenant search must be empty.
            other = await adapter.search(OTHER_INSTANCE, host_user_id=USER)
            assert other == []

    _run(_go())


@pytest.mark.django_db(transaction=True)
def test_long_term_store_retrieve_and_forget(django_store):
    from ai.adapters.memory import DjangoLongTermAdapter

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            adapter = DjangoLongTermAdapter(db)

            fact_id = await adapter.store_fact(
                INSTANCE,
                "observation",
                "campus reduced emissions by 5 percent",
                host_user_id=USER,
                visibility="shared",
            )
            assert fact_id

            retrieved = await adapter.retrieve(
                INSTANCE, "emissions", host_user_id=USER
            )
            assert any(f["id"] == fact_id for f in retrieved)

            await adapter.forget(INSTANCE, fact_id)
            after = await adapter.retrieve(
                INSTANCE, "emissions", host_user_id=USER
            )
            assert all(f["id"] != fact_id for f in after)

    _run(_go())


@pytest.mark.django_db(transaction=True)
def test_ledger_record_stage_writes_row(django_store):
    from ai.adapters.ledger import DjangoLedgerAdapter

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            adapter = DjangoLedgerAdapter(db)

            row_id = await adapter.record_stage(
                turn_id="turn-1",
                instance_id=INSTANCE,
                conversation_id="conv-1",
                host_user_id=USER,
                stage="learn",
                stage_index=0,
                payload={"ok": True},
                latency_ms=12.3,
            )
            assert row_id

            rows = await db.select(TurnLedgerRow, ("id", row_id))
            assert len(rows) == 1
            assert rows[0].stage == "learn"

    _run(_go())


@pytest.mark.django_db(transaction=True)
def test_ledger_record_stage_coerces_decimal_payload(django_store):
    """Regression: a tool-result payload containing Decimal must not break
    JSONField serialization (was ``TypeError: Object of type Decimal is not
    JSON serializable``, which failed the whole turn at final commit)."""
    from decimal import Decimal

    from ai.adapters.ledger import DjangoLedgerAdapter

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            adapter = DjangoLedgerAdapter(db)

            row_id = await adapter.record_stage(
                turn_id="turn-decimal",
                instance_id=INSTANCE,
                conversation_id="conv-decimal",
                host_user_id=USER,
                stage="execution",
                stage_index=4,
                payload={
                    "total": Decimal("123.45"),
                    "nested": {"sum": Decimal("99.9")},
                    "rows": [{"v": Decimal("1.0")}],
                },
                latency_ms=12.3,
            )
            assert row_id

            rows = await db.select(TurnLedgerRow, ("id", row_id))
            assert len(rows) == 1
            # Decimals must have been coerced to strings, never left raw.
            assert rows[0].payload_json["total"] == "123.45"
            assert rows[0].payload_json["nested"]["sum"] == "99.9"

    _run(_go())


@pytest.mark.django_db(transaction=True)
def test_skill_add_get_list_promoted_and_gate_only(django_store):
    from ai.adapters.skills import DjangoSkillAdapter

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            adapter = DjangoSkillAdapter(db)

            record = await adapter.add(
                {
                    "instance_id": INSTANCE,
                    "name": "quarterly-summary",
                    "kind": "procedure",
                    "description": "Summarize quarterly emissions",
                    "body": {"steps": ["load", "summarize"]},
                    "author_user_id": USER,
                    "status": "draft",
                }
            )
            skill_id = record["id"]

            got = await adapter.get(skill_id)
            assert got is not None
            assert got["name"] == "quarterly-summary"

            # A pending (draft) skill is not instance-promoted.
            promoted = await adapter.list_promoted(INSTANCE)
            assert all(s["id"] != skill_id for s in promoted)

            # instance_promoted is gate-only → RuntimeError (P1-06).
            with pytest.raises(RuntimeError):
                await adapter.update_status(skill_id, "instance_promoted")

    _run(_go())
