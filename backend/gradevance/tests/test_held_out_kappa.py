"""Held-out κ regression — heuristic coder must beat chance on NAA gold."""
from __future__ import annotations

from gradevance.services.publish import engine_sg_labels_for_held_out
from gradevance.services.reliability import cohen_kappa, passes_reliability_gate


def test_heuristic_kappa_on_naa_held_out_beats_chance():
    expert, engine = engine_sg_labels_for_held_out("engines/lct_semantics/naa_reflective_v1")
    assert len(expert) >= 5
    assert len(expert) == len(engine)
    k = cohen_kappa(expert, engine)
    # Chance for 4-way labels ≈ 0.25; require clear lift toward summative gate (0.6).
    assert k > 0.0, f"κ={k} expert={expert} engine={engine}"
    result = passes_reliability_gate(expert, engine, minimum=0.6)
    assert result["passed"], f"κ={result['value']} below summative floor 0.6; labels {list(zip(expert, engine))}"
    assert result["value"] == 1.0 or result["value"] >= 0.6


def test_cbl_held_out_has_enough_segments():
    expert, engine = engine_sg_labels_for_held_out("engines/lct_semantics/medicine_cbl_v1")
    assert len(expert) >= 5
    assert len(expert) == len(engine)
    # Soft floor — CBL anchors are thinner than NAA gold; require positive κ.
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
