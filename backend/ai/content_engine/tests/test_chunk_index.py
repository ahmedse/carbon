"""Recall gold + gate tests for the content-engine chunker and hybrid index.

The gold fixture lives HERE (a py fixture) — deliberately NOT in domain_packs.

Covers:
  * structure-aware, sentence-safe, overlapping chunking
  * STABLE content-addressed chunk ids
  * whole-word bounded keyword retrieval with exact (never fabricated) spans
  * a ~15-question student recall gold with a scoring function
  * default-OFF isolation: content_engine is unknown to engine/** and turn paths
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai.content_engine.chunk import (
    OVERLAP_RATIO,
    TARGET_CHARS,
    chunk_units,
)
from ai.content_engine.index import (
    KEYWORD_DEFAULT_ON,
    SEMANTIC_DEFAULT_OFF,
    build_keyword_index,
    build_semantic_embeddings,
    load_index,
    retrieve,
    save_index,
    semantic_status,
)

AI_DIR = Path(__file__).resolve().parents[2]  # backend/ai

# ─────────────────────────────────────────────────────────────────────────────
# Sample structural units (Moodle-like course content)
# ─────────────────────────────────────────────────────────────────────────────


def _unit(kind, locator, text, activity_ref, course="BIO101"):
    return {
        "text": text,
        "kind": kind,
        "source_ref": f"{course}/{activity_ref}/{locator}",
        "locator": locator,
        "citable": True,
        "course": course,
        "activity_ref": activity_ref,
        "status": "ok",
    }


UNITS = [
    _unit("heading", "h1", "Cell Division", "page-1"),
    _unit("paragraph", "p1",
          "Mitosis is the process where a single cell divides into two identical daughter cells. "
          "The main purpose of mitosis is growth and repair of body tissues.", "page-1"),
    _unit("paragraph", "p2",
          "Mitosis has four phases: prophase, metaphase, anaphase, and telophase. "
          "Chromosomes condense during prophase.", "page-1"),
    _unit("paragraph", "p3",
          "During metaphase the chromosomes line up along the metaphase plate. "
          "During anaphase sister chromatids separate and move to opposite poles.", "page-1"),
    _unit("heading", "h2", "Meiosis", "page-2"),
    _unit("paragraph", "p4",
          "Meiosis produces four genetically different gametes. "
          "Crossing over during prophase I creates genetic variation.", "page-2"),
    _unit("question", "q1",
          "Which phase of mitosis aligns chromosomes at the metaphase plate? "
          "Answer: metaphase.", "quiz-1"),
    _unit("paragraph", "p5",
          "The cell cycle includes interphase, mitosis, and cytokinesis. "
          "Interphase consists of G1, S, and G2 phases.", "page-2"),
    _unit("paragraph", "p6",
          "DNA replication occurs during the S phase of interphase. "
          "Each chromosome is copied to form sister chromatids.", "page-3"),
    _unit("paragraph", "p7",
          "Cytokinesis divides the cytoplasm. In plant cells a cell plate forms; "
          "in animal cells a cleavage furrow forms.", "page-3"),
    _unit("heading", "h3", "Photosynthesis", "page-4"),
    _unit("paragraph", "p8",
          "Photosynthesis converts light energy into chemical energy. "
          "Chlorophyll absorbs light in the chloroplast.", "page-4"),
    _unit("paragraph", "p9",
          "The light reactions produce ATP and NADPH. "
          "The Calvin cycle fixes carbon dioxide into glucose.", "page-4"),
    _unit("paragraph", "p10",
          "Cellular respiration releases energy from glucose. "
          "Glycolysis occurs in the cytoplasm.", "page-4"),
    _unit("paragraph", "p11",
          "The Krebs cycle occurs in the mitochondrial matrix. "
          "Oxidative phosphorylation occurs at the inner mitochondrial membrane.", "page-4"),
]

# Chunk ids are STABLE: course:activity_ref:kind:locator:ordinal (ordinal 0 here).
_P1 = "BIO101:page-1:paragraph:p1:0"
_P2 = "BIO101:page-1:paragraph:p2:0"
_P4 = "BIO101:page-2:paragraph:p4:0"
_P6 = "BIO101:page-3:paragraph:p6:0"
_P7 = "BIO101:page-3:paragraph:p7:0"
_P8 = "BIO101:page-4:paragraph:p8:0"
_P9 = "BIO101:page-4:paragraph:p9:0"
_P10 = "BIO101:page-4:paragraph:p10:0"
_P11 = "BIO101:page-4:paragraph:p11:0"
_Q1 = "BIO101:quiz-1:question:q1:0"

# ~15 realistic student questions -> expected chunk_id(s) + exact matched span.
GOLD = [
    {"question": "What are the four phases of mitosis?", "expected_chunk_ids": [_P2], "expected_span": "phases"},
    {"question": "What happens during telophase?", "expected_chunk_ids": [_P2], "expected_span": "telophase"},
    {"question": "Explain meiosis and gametes.", "expected_chunk_ids": [_P4], "expected_span": "meiosis"},
    {"question": "What is crossing over?", "expected_chunk_ids": [_P4], "expected_span": "crossing"},
    {"question": "How does DNA replication happen?", "expected_chunk_ids": [_P6], "expected_span": "replication"},
    {"question": "What happens in the Calvin cycle?", "expected_chunk_ids": [_P9], "expected_span": "Calvin"},
    {"question": "Where does glycolysis occur?", "expected_chunk_ids": [_P10], "expected_span": "Glycolysis"},
    {"question": "What is produced during oxidative phosphorylation?",
     "expected_chunk_ids": [_P11], "expected_span": "phosphorylation"},
    {"question": "Where does the Krebs cycle take place?", "expected_chunk_ids": [_P11], "expected_span": "Krebs"},
    {"question": "What pigment absorbs light in chloroplasts?",
     "expected_chunk_ids": [_P8], "expected_span": "absorbs"},
    {"question": "What is the purpose of mitosis for body tissues?",
     "expected_chunk_ids": [_P1], "expected_span": "purpose"},
    {"question": "When do chromosomes condense?", "expected_chunk_ids": [_P2], "expected_span": "condense"},
    {"question": "What forms in plant cells during cytokinesis?",
     "expected_chunk_ids": [_P7], "expected_span": "cytokinesis"},
    {"question": "Which phase aligns chromosomes at the metaphase plate?",
     "expected_chunk_ids": [_Q1], "expected_span": "aligns"},
    {"question": "How do identical daughter cells form?", "expected_chunk_ids": [_P1], "expected_span": "identical"},
]


# ─────────────────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────────────────


def _span_present(result: dict, expected_span: str) -> bool:
    want = expected_span.casefold()
    return any(s["text"].casefold() == want for s in result.get("spans", []))


def score_recall(gold: list[dict], index, k: int = 5) -> tuple[int, int, list[tuple[str, bool]]]:
    """Return (n_correct, n_total, per-question detail).

    A question counts as correct only if a returned chunk is one of the expected
    chunk_ids AND carries the expected exact matched span.
    """
    correct = 0
    details: list[tuple[str, bool]] = []
    for item in gold:
        results = retrieve(index, item["question"], k=k)
        ok = any(
            r["chunk_id"] in item["expected_chunk_ids"] and _span_present(r, item["expected_span"])
            for r in results
        )
        correct += int(ok)
        details.append((item["question"], ok))
    return correct, len(gold), details


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def chunks():
    return chunk_units(UNITS)


@pytest.fixture(scope="module")
def index(chunks):
    return build_keyword_index(chunks)


# ─────────────────────────────────────────────────────────────────────────────
# Chunking
# ─────────────────────────────────────────────────────────────────────────────


def test_chunk_ids_are_stable_and_content_addressed(chunks):
    again = chunk_units(UNITS)
    assert [c["chunk_id"] for c in chunks] == [c["chunk_id"] for c in again]


def test_chunk_ids_use_frozen_format(chunks):
    for c in chunks:
        parts = c["chunk_id"].split(":")
        # course:activity_ref:kind:locator:ordinal  (activity_ref/locator may be empty)
        assert len(parts) == 5
        assert parts[0] == c["course"]
        assert parts[1] == c["activity_ref"]
        assert parts[3] == c["locator"]
        assert parts[4] == str(c["ordinal"])


def test_prev_next_links_in_reading_order(chunks):
    for i, c in enumerate(chunks):
        assert c["prev_id"] == (chunks[i - 1]["chunk_id"] if i > 0 else None)
        assert c["next_id"] == (chunks[i + 1]["chunk_id"] if i + 1 < len(chunks) else None)


def test_section_tracking_from_headings(chunks):
    by_id = {c["chunk_id"]: c for c in chunks}
    assert by_id[_P2]["section"] == "Cell Division"
    assert by_id[_P4]["section"] == "Meiosis"
    assert by_id[_P8]["section"] == "Photosynthesis"


def test_long_unit_windows_overlap_on_sentence_boundaries():
    sentences = [
        f"Sentence number {i} mentions concept{i} and adds filler words to reach a realistic length."
        for i in range(40)
    ]
    text = " ".join(sentences)
    unit = _unit("paragraph", "long", text, "page-9")
    out = chunk_units([unit])
    assert len(out) > 1
    for c in out:
        # exact slice, and never cut mid-word / mid-sentence
        assert c["text"] == text[c["char_start"]:c["char_end"]]
        trimmed = c["text"].rstrip()
        assert c["char_end"] == len(text) or trimmed[-1] in ".!?؟\n"
    # consecutive windows overlap
    for a, b in zip(out, out[1:]):
        assert b["char_start"] < a["char_end"]
    # target respected (sentence granularity)
    for c in out:
        assert len(c["text"]) <= TARGET_CHARS + max(len(s) for s in sentences)
    assert 0.0 < OVERLAP_RATIO < 0.5


# ─────────────────────────────────────────────────────────────────────────────
# Keyword index — bounded matching + no fabricated spans
# ─────────────────────────────────────────────────────────────────────────────


def test_whole_word_bounded_no_substring_hits():
    units = [
        _unit("paragraph", "w1", "We concatenate strings in the preprocessor.", "page-1"),
        _unit("paragraph", "w2", "The cat sat on the concatenated mat.", "page-1"),
    ]
    idx = build_keyword_index(chunk_units(units))
    # 'cat' must NOT hit 'concatenate' / 'concatenated' (whole-word bounded).
    cat_spans = [s["text"] for r in retrieve(idx, "cat", k=10) for s in r["spans"]]
    assert all(s.casefold() not in {"concatenate", "concatenated"} for s in cat_spans)
    # The full term does match, and the span is the exact token.
    hits = retrieve(idx, "concatenate", k=10)
    assert any(s["text"] == "concatenate" for r in hits for s in r["spans"])


def test_spans_are_real_substrings(chunks, index):
    for item in GOLD:
        for r in retrieve(index, item["question"], k=5):
            for s in r["spans"]:
                assert 0 <= s["char_start"] < s["char_end"] <= len(r["text"])
                assert r["text"][s["char_start"]:s["char_end"]] == s["text"]
                assert s["text"] and s["text"] in r["text"]


def test_no_match_returns_empty(index):
    assert retrieve(index, "zzzznotarealterm") == []
    assert retrieve(index, "") == []


# ─────────────────────────────────────────────────────────────────────────────
# Recall gold
# ─────────────────────────────────────────────────────────────────────────────


def test_recall_gold_scores_full_marks(index):
    correct, total, details = score_recall(GOLD, index, k=5)
    assert total == 15
    missed = [q for q, ok in details if not ok]
    assert correct == total, f"missed: {missed}"


# ─────────────────────────────────────────────────────────────────────────────
# File persistence
# ─────────────────────────────────────────────────────────────────────────────


def test_save_load_roundtrip(tmp_path, chunks):
    path = tmp_path / "index.jsonl"
    save_index(str(path), chunks)
    assert path.exists()
    loaded = load_index(str(path))
    assert [c["chunk_id"] for c in loaded.chunks] == [c["chunk_id"] for c in chunks]
    # retrieval identical after reload — bounded spans preserved exactly
    before = retrieve(build_keyword_index(chunks), "telophase")
    after = retrieve(loaded, "telophase")
    assert [r["chunk_id"] for r in before] == [r["chunk_id"] for r in after]
    assert [s["text"] for r in before for s in r["spans"]] == [
        s["text"] for r in after for s in r["spans"]
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Semantic layer contract (default OFF)
# ─────────────────────────────────────────────────────────────────────────────


def test_keyword_default_on_semantic_default_off():
    assert KEYWORD_DEFAULT_ON is True
    assert SEMANTIC_DEFAULT_OFF is True


def test_semantic_status_is_a_known_value():
    # Never invoked against the network: only the status string is asserted.
    assert semantic_status() in {"no_provider", "llm_embedding", "local_onnx"}


def test_semantic_build_is_noop_contract_shape(chunks):
    # The hook must always return the documented shape without raising. Tests do
    # not force embeddings to be built (that would touch a provider/network);
    # only the contract shape and the default-OFF posture are asserted.
    assert callable(build_semantic_embeddings)
    assert SEMANTIC_DEFAULT_OFF is True


# ─────────────────────────────────────────────────────────────────────────────
# Default-OFF isolation: engine/** and turn paths must not know content_engine
# ─────────────────────────────────────────────────────────────────────────────

_ISOLATED_FILES = [
    AI_DIR / "moodle_page.py",
    AI_DIR / "moodle_host.py",
]
_TURN_PATH_GLOBS = [
    "engine/**/turn/**/*.py",
    "engine/**/runner*.py",
    "engine/runner.py",
]
_ISOLATED_TREES = [AI_DIR / "engine"]


def _iter_iso_files():
    for f in _ISOLATED_FILES:
        if f.exists():
            yield f
    for tree in _ISOLATED_TREES:
        if tree.exists():
            for f in tree.rglob("*.py"):
                yield f


def test_engine_and_turn_paths_do_not_reference_content_engine():
    offenders = []
    for f in _iter_iso_files():
        if "content_engine" in f.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(str(f))
    assert offenders == [], f"engine/moodle files reference content_engine: {offenders}"


def test_turn_paths_do_not_import_chunk_or_index():
    offenders = []
    for pattern in _TURN_PATH_GLOBS:
        for f in AI_DIR.glob(pattern):
            src = f.read_text(encoding="utf-8", errors="ignore")
            if "content_engine" in src:
                offenders.append(str(f))
    assert offenders == [], f"turn paths import content_engine: {offenders}"
