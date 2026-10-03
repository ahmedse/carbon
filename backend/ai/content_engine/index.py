"""Hybrid chunk index for Pulse content.

Two layers, each with a contract you can rely on:

* **KEYWORD layer (default ON)** — a deterministic, file-backed inverted index
  over whole-word tokens. Matching is *whole-word bounded*: a query term only
  hits when it equals a complete token produced by the shared tokenizer, so
  ``cat`` never matches ``concatenate`` and no unbounded substring scan happens.
  This is the layer deterministic doors may consume without network or LLM.

* **SEMANTIC layer (default OFF)** — an optional embedding hook. It reuses the
  embedding provider already configured in this repo
  (``ai.engine.llm.embeddings``: the configured LLM endpoint, else the local
  ChromaDB ONNX model). No new service, key, or vector DB is added here. When no
  provider is configured the hook is a documented no-op returning
  ``status == "no_provider"``.

The index is stored as a JSONL FILE at a path supplied by the caller (never a
hardcoded global). ``retrieve`` returns ranked chunks together with the exact
matched span (for the keyword layer, the exact bounded token match).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Index parameters
# ─────────────────────────────────────────────────────────────────────────────

# Keyword layer is the deterministic default; the semantic layer is opt-in.
KEYWORD_DEFAULT_ON = True
SEMANTIC_DEFAULT_OFF = True
DEFAULT_K = 5

# A "word" is a run of unicode letters/digits, underscore excluded. This is the
# SINGLE tokenizer used for BOTH indexing and query parsing, which is what makes
# whole-word bounded matching exact and symmetric.
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def _normalize(text: str) -> str:
    return text.casefold()


def _tokenize(text: str) -> list[tuple[str, int, int]]:
    """Return ``(normalized_term, char_start, char_end)`` for whole-word tokens."""
    return [(m.group(0).casefold(), m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]


@dataclass
class KeywordIndex:
    """In-memory keyword layer: chunks + inverted postings."""

    chunks: list[dict]
    postings: dict[str, list[list]] = field(default_factory=dict)
    embeddings: dict[str, list[float]] = field(default_factory=dict)
    semantic_status: str = "no_provider"

    @property
    def chunks_by_id(self) -> dict[str, dict]:
        return {c["chunk_id"]: c for c in self.chunks}

    @property
    def order(self) -> dict[str, int]:
        return {c["chunk_id"]: i for i, c in enumerate(self.chunks)}


def build_keyword_index(chunks: list[dict]) -> KeywordIndex:
    """Build the deterministic whole-word inverted index over ``chunks``."""
    postings: dict[str, list[list]] = {}
    for chunk in chunks:
        cid = chunk["chunk_id"]
        for term, start, end in _tokenize(chunk.get("text") or ""):
            postings.setdefault(term, []).append([cid, start, end])
    return KeywordIndex(chunks=chunks, postings=postings)


# ─────────────────────────────────────────────────────────────────────────────
# File persistence (JSONL). Caller supplies the path; nothing is global.
# ─────────────────────────────────────────────────────────────────────────────


def save_index(path: str, chunks: list[dict], embeddings: dict[str, list[float]] | None = None,
               semantic_status: str = "no_provider") -> KeywordIndex:
    """Persist a JSONL index at ``path`` and return the in-memory structure.

    Lines are tagged: ``meta``, ``chunk``, ``posting`` and optional
    ``embedding``. The inverted index and chunk records are both on disk, so the
    file is self-contained and reloadable without re-tokenizing callers' text.
    """
    index = build_keyword_index(chunks)
    index.embeddings = dict(embeddings or {})
    index.semantic_status = semantic_status

    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        meta = {
            "type": "meta",
            "keyword": KEYWORD_DEFAULT_ON,
            "semantic": bool(index.embeddings),
            "semantic_status": semantic_status,
            "count": len(chunks),
        }
        fh.write(json.dumps(meta, ensure_ascii=False, sort_keys=True) + "\n")
        for chunk in chunks:
            fh.write(json.dumps({"type": "chunk", **chunk}, ensure_ascii=False, sort_keys=True) + "\n")
        for term in sorted(index.postings):
            fh.write(json.dumps({"type": "posting", "term": term, "hits": index.postings[term]},
                                ensure_ascii=False) + "\n")
        for cid in sorted(index.embeddings):
            fh.write(json.dumps({"type": "embedding", "chunk_id": cid,
                                 "vector": index.embeddings[cid]}, ensure_ascii=False) + "\n")
    return index


def load_index(path: str) -> KeywordIndex:
    """Load a JSONL index written by :func:`save_index`."""
    chunks: list[dict] = []
    postings: dict[str, list[list]] = {}
    embeddings: dict[str, list[float]] = {}
    status = "no_provider"
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rtype = rec.get("type")
            if rtype == "chunk":
                chunks.append({k: v for k, v in rec.items() if k != "type"})
            elif rtype == "posting":
                postings[rec["term"]] = rec["hits"]
            elif rtype == "embedding":
                embeddings[rec["chunk_id"]] = rec["vector"]
            elif rtype == "meta":
                status = rec.get("semantic_status", "no_provider")
    return KeywordIndex(chunks=chunks, postings=postings, embeddings=embeddings,
                        semantic_status=status)


# ─────────────────────────────────────────────────────────────────────────────
# Retrieval — keyword layer
# ─────────────────────────────────────────────────────────────────────────────


def retrieve(index: KeywordIndex, query: str, k: int = DEFAULT_K) -> list[dict]:
    """Rank chunks by whole-word query-term overlap; return top ``k`` with spans.

    Bounded-match rule: a hit is recorded only when a full query term equals a
    full chunk token from the shared tokenizer. No posting is ever produced by a
    substring/partial overlap, so matches are exact and reproducible.
    """
    if k <= 0 or not query:
        return []

    query_terms: list[str] = []
    seen: set[str] = set()
    for term, _s, _e in _tokenize(query):
        if term not in seen:
            seen.add(term)
            query_terms.append(term)

    scores: dict[str, int] = {}
    spans: dict[str, list[dict]] = {}
    by_id = index.chunks_by_id
    for term in query_terms:
        for cid, start, end in index.postings.get(term, []):
            chunk = by_id.get(cid)
            if chunk is None:
                continue
            scores[cid] = scores.get(cid, 0) + 1
            spans.setdefault(cid, []).append(
                {
                    "term": term,
                    "char_start": start,
                    "char_end": end,
                    # exact slice of the chunk text — never fabricated
                    "text": chunk["text"][start:end],
                }
            )

    order = index.order
    ranked = sorted(scores, key=lambda cid: (-scores[cid], order.get(cid, 0)))
    results: list[dict] = []
    for cid in ranked[:k]:
        chunk = by_id[cid]
        results.append(
            {
                "chunk_id": cid,
                "score": scores[cid],
                "course": chunk.get("course", ""),
                "section": chunk.get("section", ""),
                "activity_ref": chunk.get("activity_ref", ""),
                "locator": chunk.get("locator", ""),
                "text": chunk["text"],
                "spans": spans.get(cid, []),
            }
        )
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Semantic layer (default OFF). Reuses the provider already in the repo.
# ─────────────────────────────────────────────────────────────────────────────


def semantic_status() -> str:
    """Return the configured embedding-provider id, or ``"no_provider"``.

    Reuses only providers already present in this repo:
      * ``llm_embedding`` when the LLM endpoint/key is configured, else
      * ``local_onnx`` when the ChromaDB ONNX fallback is importable, else
      * ``no_provider``.
    """
    try:
        from ai.engine.core.config import get_settings

        settings = get_settings()
        if settings.LLM_API_KEY and settings.LLM_BASE_URL:
            return "llm_embedding"
    except Exception:
        return "no_provider"
    try:
        import chromadb  # noqa: F401

        return "local_onnx"
    except Exception:
        return "no_provider"


def build_semantic_embeddings(chunks: list[dict]) -> dict[str, Any]:
    """Build embeddings via the repo's existing provider, or a documented no-op.

    Returns ``{"status": <id>, "embeddings": {chunk_id: vector}}``. When the
    semantic layer is disabled (the default) this is an immediate inert
    ``{"status": "disabled", "embeddings": {}}`` — no provider probe, no
    import, no network. When enabled but no provider is configured it is a
    no-op with ``status == "no_provider"`` and an empty map. No new service,
    key, or vector DB is introduced.
    """
    if not semantic_enabled():
        return {"status": "disabled", "embeddings": {}}

    status = semantic_status()
    if status == "no_provider":
        return {"status": "no_provider", "embeddings": {}}

    from ai.engine.llm.embeddings import embed_texts

    texts = [c.get("text") or "" for c in chunks]
    try:
        vectors = asyncio.run(embed_texts(texts))
    except RuntimeError:
        # Already inside a running loop: run on a private loop instead.
        loop = asyncio.new_event_loop()
        try:
            vectors = loop.run_until_complete(embed_texts(texts))
        finally:
            loop.close()
    except Exception:
        return {"status": "no_provider", "embeddings": {}}

    if not vectors or len(vectors) != len(chunks):
        return {"status": "no_provider", "embeddings": {}}
    return {
        "status": status,
        "embeddings": {c["chunk_id"]: [float(x) for x in v] for c, v in zip(chunks, vectors)},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Semantic opt-in seam (L-R R3) — EXPLICIT, default OFF, inert until enabled.
# ─────────────────────────────────────────────────────────────────────────────

#: Opt-in switch for the semantic layer. Absent / empty / falsey => OFF, and
#: the seam below does **no** work, imports no provider, and adds no latency.
SEMANTIC_OPT_IN_ENV = "PULSE_CONTENT_SEMANTIC_ENABLED"

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def semantic_enabled() -> bool:
    """True only when ``PULSE_CONTENT_SEMANTIC_ENABLED`` is truthy. Default OFF.

    This is a pure environment read: it never imports a provider, opens a
    socket, or builds an embedding. Every existing keyword turn is unaffected
    because nothing on the default path calls it.
    """
    return str(os.environ.get(SEMANTIC_OPT_IN_ENV, "")).strip().lower() in _TRUTHY


def semantic_retrieve(index: KeywordIndex, query: str, k: int = DEFAULT_K) -> dict[str, Any]:
    """Opt-in semantic retrieval seam. Returns a status envelope, never raises.

    Default posture (``semantic_enabled() is False``) is **inert**: it returns
    ``{"status": "disabled", ...}`` with no results and performs zero provider
    calls. The R3 rung is CONTRACT/BY-REAL-WORLD blocked (TEACHING-WAVE-SPEC
    §1.2), so even when OPTED IN this seam is an explicit no-op that reports
    ``no_embeddings`` / ``not_implemented`` — it introduces **no** vector DB,
    second Postgres, pgvector, or external search service.
    """
    if not semantic_enabled():
        return {"status": "disabled", "enabled": False, "results": []}
    if not index.embeddings:
        return {"status": "no_embeddings", "enabled": True, "results": []}
    return {"status": "not_implemented", "enabled": True, "results": []}


__all__ = [
    "KEYWORD_DEFAULT_ON",
    "SEMANTIC_DEFAULT_OFF",
    "SEMANTIC_OPT_IN_ENV",
    "DEFAULT_K",
    "KeywordIndex",
    "build_keyword_index",
    "save_index",
    "load_index",
    "retrieve",
    "semantic_status",
    "build_semantic_embeddings",
    "semantic_enabled",
    "semantic_retrieve",
]
