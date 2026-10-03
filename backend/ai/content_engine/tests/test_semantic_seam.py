"""L-R R3 — semantic layer is an explicit opt-in seam, default OFF and inert.

The R3 rung is CONTRACT / BY-REAL-WORLD blocked (TEACHING-WAVE-SPEC §1.2), so
only the seam ships: an environment switch that is OFF unless explicitly
enabled, and a retrieval entry point that does **no** work when OFF. No vector
DB, no second Postgres, no pgvector, no network.
"""
from __future__ import annotations

from ai.content_engine.index import (
    SEMANTIC_DEFAULT_OFF,
    SEMANTIC_OPT_IN_ENV,
    build_keyword_index,
    retrieve,
    semantic_enabled,
    semantic_retrieve,
)

_CHUNKS = [
    {
        "chunk_id": "BIO101:page-1:paragraph:p1:0",
        "course": "BIO101",
        "section": "Cell Division",
        "activity_ref": "page-1",
        "source_ref": "BIO101:page:1",
        "locator": "p1",
        "ordinal": 0,
        "text": "Mitosis divides a cell into two identical daughter cells.",
    }
]


def test_seam_is_off_by_default(monkeypatch):
    monkeypatch.delenv(SEMANTIC_OPT_IN_ENV, raising=False)
    assert SEMANTIC_DEFAULT_OFF is True
    assert semantic_enabled() is False


def test_seam_only_enables_on_explicit_truthy_flag(monkeypatch):
    for value in ("", "0", "false", "no", "off", "random"):
        monkeypatch.setenv(SEMANTIC_OPT_IN_ENV, value)
        assert semantic_enabled() is False, value
    for value in ("1", "true", "TRUE", "yes", "On"):
        monkeypatch.setenv(SEMANTIC_OPT_IN_ENV, value)
        assert semantic_enabled() is True, value


def test_semantic_retrieve_is_inert_when_off(monkeypatch):
    monkeypatch.delenv(SEMANTIC_OPT_IN_ENV, raising=False)
    index = build_keyword_index(_CHUNKS)
    envelope = semantic_retrieve(index, "mitosis")
    assert envelope == {"status": "disabled", "enabled": False, "results": []}


def test_semantic_retrieve_never_touches_a_provider_even_when_on(monkeypatch):
    monkeypatch.setenv(SEMANTIC_OPT_IN_ENV, "1")
    index = build_keyword_index(_CHUNKS)
    # No embeddings present -> explicit no-op, still no network / vector store.
    assert semantic_retrieve(index, "mitosis")["status"] == "no_embeddings"
    index.embeddings = {"BIO101:page-1:paragraph:p1:0": [0.1, 0.2]}
    assert semantic_retrieve(index, "mitosis")["status"] == "not_implemented"


def test_keyword_retrieve_is_identical_with_flag_on_or_off(monkeypatch):
    index = build_keyword_index(_CHUNKS)
    monkeypatch.delenv(SEMANTIC_OPT_IN_ENV, raising=False)
    off = retrieve(index, "mitosis divides")
    monkeypatch.setenv(SEMANTIC_OPT_IN_ENV, "1")
    on = retrieve(index, "mitosis divides")
    assert off == on
