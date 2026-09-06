"""S-PROC-01 — knowledge grounding floor.

The payroll-run lifecycle question used to return empty because the knowledge
base was empty AND the chat path's ``search_knowledge`` tool read from the
engine vector store (chromadb), which is not installed in this environment.

These tests pin the guaranteed lexical floor: ``KnowledgeStore._lexical_search``
and the public ``KnowledgeStore.search`` must return non-empty, correctly-ranked
entities from the durable Django ORM rows — with no vector backend at all.
"""
import pytest

from ai.engine.knowledge.store import KnowledgeStore
from ai.models.core import KnowledgeEntity as DjangoKnowledgeEntity

INSTANCE = "nibras-test"

PAYROLL_SPECS = [
    (
        "process",
        "Payroll Run Lifecycle",
        "Payroll run lifecycle: (1) draft initial setup; (2) compute the "
        "calculation stage; (3) validate the approval stage; (4) commit the "
        "final posting stage with WPS, SIF, disbursement and reconciliation.",
    ),
    (
        "concept",
        "WPS Wage Protection System",
        "WPS wage protection system salary file SIF generation and disbursement.",
    ),
    (
        "concept",
        "Leave Calendar-Split",
        "Leave calendar split across payroll months for accruals and paydays.",
    ),
]


def _seed():
    for entity_type, name, desc in PAYROLL_SPECS:
        DjangoKnowledgeEntity.objects.create(
            instance_id=INSTANCE,
            entity_type=entity_type,
            name=name,
            semantic_description=desc,
        )


async def _seed_async():
    from asgiref.sync import sync_to_async

    await sync_to_async(_seed, thread_sensitive=True)()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_lexical_search_returns_payroll_lifecycle():
    await _seed_async()

    store = object.__new__(KnowledgeStore)
    hits = await store._lexical_search(
        INSTANCE, "what are the payroll run lifecycle stages", top_k=5
    )

    assert hits, "lexical search must return non-empty results for a payroll query"
    assert hits[0]["name"] == "Payroll Run Lifecycle"
    assert "draft" in hits[0]["semantic_description"].lower()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_lexical_search_ranks_wps_query():
    await _seed_async()

    store = object.__new__(KnowledgeStore)
    hits = await store._lexical_search(INSTANCE, "wps wage protection", top_k=5)

    assert hits, "wps query must return non-empty results"
    assert hits[0]["name"] == "WPS Wage Protection System"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_search_returns_results_without_vector_backend():
    """The public ``search`` API must serve results even when no vector
    backend is usable (``object.__new__`` skips ``__init__`` so ``self.vector``
    is absent — the vector attempt raises and falls back to lexical)."""
    await _seed_async()

    store = object.__new__(KnowledgeStore)
    hits = await store.search(INSTANCE, "payroll run lifecycle", top_k=5)

    assert hits, "search must fall back to lexical and return non-empty results"
    assert hits[0]["name"] == "Payroll Run Lifecycle"
    assert {"id", "name", "entity_type", "semantic_description"} <= set(hits[0].keys())

