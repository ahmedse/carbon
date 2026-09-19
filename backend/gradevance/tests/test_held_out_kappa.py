"""Held-out κ regression — heuristic coder on disjoint NAA gold (Instrument Trust T2)."""
from __future__ import annotations

from gradevance.services.publish import (
    engine_sd_labels_for_held_out,
    engine_sg_labels_for_held_out,
    held_out_anchor_overlap,
)
from gradevance.services.reliability import cohen_kappa, passes_reliability_gate


def test_naa_held_out_has_at_least_three_essays():
    from gradevance.services.publish import load_held_out_rows

    rows = load_held_out_rows("engines/lct_semantics/naa_reflective_v1")
    assert len(rows) >= 3, f"expected ≥3 NAA held_out essays, got {len(rows)}"


def test_naa_held_out_disjoint_from_anchors():
    overlaps = held_out_anchor_overlap("engines/lct_semantics/naa_reflective_v1")
    assert overlaps == [], f"held_out overlaps anchors (circular κ risk): {overlaps}"


def test_heuristic_kappa_on_naa_held_out_beats_chance():
    expert, engine = engine_sg_labels_for_held_out("engines/lct_semantics/naa_reflective_v1")
    assert len(expert) >= 5
    assert len(expert) == len(engine)
    k = cohen_kappa(expert, engine)
    assert k > 0.0, f"κ={k} expert={expert} engine={engine}"
    result = passes_reliability_gate(expert, engine, minimum=0.6)
    assert result["passed"], f"κ={result['value']} below summative floor 0.6; labels {list(zip(expert, engine))}"


def test_naa_held_out_reports_sd_kappa():
    expert, engine = engine_sd_labels_for_held_out("engines/lct_semantics/naa_reflective_v1")
    assert len(expert) >= 5
    assert len(expert) == len(engine)
    k = cohen_kappa(expert, engine)
    # Soft floor for SD while heuristic is thin — must be defined and non-negative.
    assert k >= 0.0, f"SD κ={k} expert={expert} engine={engine}"


def test_medicine_and_article_held_out_marked_seeded():
    from gradevance.services.publish import load_held_out_rows

    # OSCE + article remain seeded_draft
    for pack in (
        "engines/lct_semantics/medicine_clinical_reflection_v1",
        "engines/lct_semantics/article_argumentative_v1",
    ):
        rows = load_held_out_rows(pack)
        assert rows, pack
        assert all(r.get("gold_status") == "seeded_draft" for r in rows), pack

    cbl = load_held_out_rows("engines/lct_semantics/medicine_cbl_v1")
    assert len(cbl) >= 2
    assert all(r.get("gold_status") == "instrument_coded_disjoint" for r in cbl)

    expert, engine = engine_sg_labels_for_held_out("engines/lct_semantics/medicine_cbl_v1")
    assert len(expert) >= 5
    assert len(expert) == len(engine)
    k = cohen_kappa(expert, engine)
    assert k >= 0.0, f"κ={k} expert={expert} engine={engine}"


def test_osce_clinical_held_out_has_enough_segments():
    expert, engine = engine_sg_labels_for_held_out(
        "engines/lct_semantics/medicine_clinical_reflection_v1"
    )
    assert len(expert) >= 4
    assert len(expert) == len(engine)
    k = cohen_kappa(expert, engine)
    assert k >= 0.0, f"κ={k}"
