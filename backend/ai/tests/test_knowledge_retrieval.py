"""P4-02 — applicability-first retrieval selection (offline unit tests).

These tests exercise
:func:`ai.engine.knowledge.retrieval.applicability_first` in isolation — no
Django DB, no LLM, no network — plus one integration-style test proving the S2
``RetrievalWitness`` merges curated items into ``knowledge_chunks`` with
freshness metadata while keeping the graph semantic path and ``citation_ids``
intact.

The contract under test: a **mandatory** knowledge item ALWAYS survives — even
when a ranking function scores it lowest and ``top_k`` would otherwise truncate
it away — and mandatory items are exempt from ranking/truncation entirely.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from ai.engine.cognition.turn.retrieve import RetrievalWitness
from ai.engine.knowledge.classes import KnowledgeItemProjection
from ai.engine.knowledge.retrieval import applicability_first

NOW = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)


def _proj(
    item_id: str,
    *,
    knowledge_class: str = "policy",
    content: str | None = None,
    scope: dict | None = None,
    is_mandatory: bool = False,
    effective_start: datetime | None = None,
    effective_end: datetime | None = None,
    ingested_at: datetime | None = None,
    version: str = "1",
    supersedes_id: str = "",
) -> KnowledgeItemProjection:
    """Build a projection with sensible test defaults."""
    return KnowledgeItemProjection(
        id=item_id,
        knowledge_class=knowledge_class,
        source="test",
        content=content if content is not None else f"content-{item_id}",
        scope=scope or {},
        is_mandatory=is_mandatory,
        effective_start=effective_start,
        effective_end=effective_end,
        ingested_at=ingested_at,
        version=version,
        supersedes_id=supersedes_id,
    )


# ── 1. THE acceptance test: mandatory survives low rank + small top_k ─────

def test_mandatory_survives_when_ranked_lowest_and_top_k_small():
    mandatory = _proj("mandatory", is_mandatory=True)
    optional = [_proj(f"o{i}") for i in range(5)]

    # rank_fn scores the mandatory item lowest of all.
    scores = {"mandatory": -1000.0}
    for i in range(5):
        scores[f"o{i}"] = float(i)

    result = applicability_first(
        [mandatory, *optional],
        now=NOW,
        top_k=2,
        rank_fn=lambda item: scores[item.id],
    )
    ids = [i.id for i in result]

    assert ids[0] == "mandatory"                       # mandatory comes first
    assert "mandatory" in ids                          # never cut
    assert len([i for i in ids if i != "mandatory"]) == 2  # top_k applies to the rest


# ── 2. Scope filter: global kept, mismatched org unit dropped ─────────────

def test_scope_filter_keeps_global_and_drops_mismatched_org_unit():
    global_item = _proj("global", scope={})
    org7 = _proj("org7", scope={"org_unit_id": 7})
    org9 = _proj("org9", scope={"org_unit_id": 9})

    result = applicability_first(
        [global_item, org7, org9],
        scope={"org_unit_id": 7},
        now=NOW,
    )
    ids = [i.id for i in result]

    assert "global" in ids
    assert "org7" in ids
    assert "org9" not in ids


def test_scope_filter_accepts_org_unit_ids_list():
    global_item = _proj("global", scope={})
    org7 = _proj("org7", scope={"org_unit_id": 7})
    org9 = _proj("org9", scope={"org_unit_id": 9})

    result = applicability_first(
        [global_item, org7, org9],
        scope={"org_unit_ids": [7, 9]},
        now=NOW,
    )
    assert [i.id for i in result] == ["global", "org7", "org9"]


def test_scalar_org_unit_id_wins_over_list():
    org7 = _proj("org7", scope={"org_unit_id": 7})
    org9 = _proj("org9", scope={"org_unit_id": 9})

    result = applicability_first(
        [org7, org9],
        scope={"org_unit_id": 7, "org_unit_ids": [7, 9]},
        now=NOW,
    )
    # scalar org_unit_id=7 names the active scope and wins → org9 excluded.
    assert [i.id for i in result] == ["org7"]


def test_module_id_scope_matching():
    global_item = _proj("global", scope={})
    m3 = _proj("m3", scope={"module_id": 3})
    m5 = _proj("m5", scope={"module_id": 5})

    result = applicability_first(
        [global_item, m3, m5],
        scope={"module_id": 3},
        now=NOW,
    )
    ids = [i.id for i in result]
    assert "global" in ids
    assert "m3" in ids
    assert "m5" not in ids


# ── 3. Effective period: expired optional dropped, expired mandatory kept ─

def test_expired_non_mandatory_dropped_expired_mandatory_kept():
    expired_optional = _proj("expired-opt", effective_end=NOW - timedelta(days=1))
    expired_mandatory = _proj(
        "expired-mand", is_mandatory=True, effective_end=NOW - timedelta(days=1)
    )
    current = _proj("current")

    result = applicability_first([expired_optional, expired_mandatory, current], now=NOW)
    ids = [i.id for i in result]

    assert "expired-opt" not in ids
    assert "expired-mand" in ids
    assert "current" in ids


# ── 4. Supersession drops predecessor ─────────────────────────────────────

def test_supersession_drops_predecessor():
    a = _proj("a")
    b = _proj("b", supersedes_id="a")

    result = applicability_first([a, b], now=NOW)
    assert [i.id for i in result] == ["b"]


# ── 5. top_k truncates optional but never mandatory ───────────────────────

def test_top_k_truncates_optional_but_never_mandatory():
    mandatory_a = _proj("m1", is_mandatory=True)
    mandatory_b = _proj("m2", is_mandatory=True)
    optional = [_proj(f"o{i}") for i in range(5)]

    result = applicability_first(
        [*optional, mandatory_a, mandatory_b],
        now=NOW,
        top_k=1,
        rank_fn=lambda item: float(item.id[-1]),
    )
    ids = [i.id for i in result]
    # mandatory first (stable), then only the single top-ranked optional.
    assert ids == ["m1", "m2", "o4"]


# ── 6. Freshness metadata preserved ───────────────────────────────────────

def test_freshness_metadata_preserved():
    start = NOW - timedelta(days=30)
    end = NOW + timedelta(days=30)
    ingested = NOW - timedelta(days=1)
    item = _proj(
        "fresh",
        version="7",
        effective_start=start,
        effective_end=end,
        ingested_at=ingested,
    )

    result = applicability_first([item], now=NOW)
    assert len(result) == 1
    out = result[0]

    assert out is item                       # original projection returned untouched
    assert out.version == "7"
    assert out.effective_start == start
    assert out.effective_end == end
    assert out.ingested_at == ingested


# ── 7. Determinism + purity ───────────────────────────────────────────────

def test_determinism_and_purity():
    items = [
        _proj("a", scope={"org_unit_id": 1}),
        _proj("b", scope={}),
        _proj("c", scope={"org_unit_id": 2}),
        _proj("d", scope={"org_unit_id": 1}),
    ]
    snapshot = list(items)

    first = applicability_first(items, scope={"org_unit_id": 1}, now=NOW)
    second = applicability_first(items, scope={"org_unit_id": 1}, now=NOW)

    assert first == second                   # deterministic
    assert items == snapshot                 # input list unchanged
    assert items[0].scope == {"org_unit_id": 1}  # projections untouched
    assert all(isinstance(i, KnowledgeItemProjection) for i in first)


def test_empty_input_returns_empty_list():
    assert applicability_first([], now=NOW) == []


# ── 8. Integration: witness merges curated items + graph path ─────────────

class _EmptyStore:
    """Knowledge store that finds nothing (lexical/vector both empty)."""

    async def search(self, instance_id, query, top_k=10):
        return []


class _PopulatedStore:
    """Knowledge store that finds one entity via the non-graph path."""

    async def search(self, instance_id, query, top_k=10):
        return [
            {
                "name": "Process A",
                "semantic_description": "A process definition.",
            }
        ]


def test_witness_merges_applicability_first_items_with_metadata():
    start = datetime(2000, 1, 1, tzinfo=timezone.utc)
    end = datetime(2100, 1, 1, tzinfo=timezone.utc)
    ingested = datetime(2020, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    mandatory = _proj(
        "policy-1",
        is_mandatory=True,
        version="3",
        effective_start=start,
        effective_end=end,
        ingested_at=ingested,
    )
    optional = _proj("fact-1", knowledge_class="business_fact")

    witness = RetrievalWitness(knowledge_store=_PopulatedStore())
    result = asyncio.run(
        witness.retrieve(
            "some-instance",
            "conv-1",
            "What is the process?",
            None,
            knowledge_items=[mandatory, optional],
            scope={"org_unit_id": 1},
        )
    )

    curated = [c for c in result.knowledge_chunks if c.get("knowledge_class")]
    assert len(curated) == 2

    first = curated[0]
    assert first["is_mandatory"] is True
    assert first["knowledge_class"] == "policy"
    assert first["version"] == "3"
    assert first["effective_start"] == start.isoformat()
    assert first["effective_end"] == end.isoformat()
    assert first["ingested_at"] == ingested.isoformat()
    assert first["source"] == "test"

    # The graph semantic path still contributes its text chunk + citation ids.
    assert any("Process A" in c["content"] for c in result.knowledge_chunks)
    assert isinstance(result.citation_ids, list)
