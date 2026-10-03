"""R3 gate: the semantic embedding build is inert unless explicitly opted in.

The R3 rung is CONTRACT/BY-REAL-WORLD blocked (TEACHING-WAVE-SPEC §1.2): the
wave ships the opt-in *seam* only, default OFF, with no vector DB, no second
Postgres, and no network on any existing turn. This test locks the gate on
``build_semantic_embeddings``: when the seam is OFF the function returns
immediately and never probes a provider, imports an embedding module, or makes
a call.
"""
from __future__ import annotations

from ai.content_engine import index as cei
from ai.content_engine.index import SEMANTIC_OPT_IN_ENV, build_semantic_embeddings

_CHUNKS = [{"chunk_id": "c1", "text": "mitosis and the cell cycle"}]


def test_semantic_build_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv(SEMANTIC_OPT_IN_ENV, raising=False)

    def _explode():  # pragma: no cover - must never run while OFF
        raise AssertionError("provider was probed while the semantic seam is OFF")

    monkeypatch.setattr(cei, "semantic_status", _explode)
    assert build_semantic_embeddings(_CHUNKS) == {"status": "disabled", "embeddings": {}}


def test_semantic_build_is_disabled_for_non_affirmative_values(monkeypatch):
    for value in ("", "0", "false", "off", "no", "disabled"):
        monkeypatch.setenv(SEMANTIC_OPT_IN_ENV, value)
        assert build_semantic_embeddings(_CHUNKS) == {"status": "disabled", "embeddings": {}}


def test_semantic_build_opt_in_without_provider_is_a_noop(monkeypatch):
    """Even when opted in, no provider configured means an empty no-op."""
    monkeypatch.setenv(SEMANTIC_OPT_IN_ENV, "1")
    monkeypatch.setattr(cei, "semantic_status", lambda: "no_provider")
    assert build_semantic_embeddings(_CHUNKS) == {"status": "no_provider", "embeddings": {}}
