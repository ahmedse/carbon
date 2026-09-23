"""Ladder is scored from committed evidence + unit contracts — not canvas labels."""
from __future__ import annotations

from ai.eval.intelligence_ladder import (
    G5_FILE,
    LIVE_A9_FILE,
    LIVE_A9_PRIOR,
    LIVE_C1_FILE,
    LIVE_C2_FILE,
    live_plan_llm_from_verify,
    score_l0,
    score_l1,
    score_l2,
    score_l3,
    score_l4,
    score_l5,
    score_ladder,
)
from ai.eval.intelligence_ladder import _load


def test_evidence_files_exist_and_have_the_numbers():
    g5 = _load(G5_FILE)
    c1 = _load(LIVE_C1_FILE)
    c2 = _load(LIVE_C2_FILE)
    a9 = _load(LIVE_A9_FILE)
    assert g5.get("turns_passed") == 96
    assert g5.get("router_agreement") == 1.0
    assert g5.get("slot_carry_over") == 1.0
    assert c1.get("turns_passed") == 24
    assert c1.get("focus_retention") == 1.0
    assert c2.get("turns_passed") == 24
    assert (c2.get("per_objective_pass") or {}).get("C2") == 1.0
    journeys = a9.get("journeys") or []
    assert len(journeys) == 3
    assert all(not j.get("chat_mutated") for j in journeys)
    assert all(j.get("host_row_after_agent") for j in journeys)


def test_ladder_l0_to_l3_reached_from_committed_json():
    assert score_l0().status == "reached"
    assert score_l1().status == "reached"
    assert score_l2().status == "reached"
    assert score_l3().status == "reached"


def test_l4_reached_when_next_step_offer_renders():
    scored = score_l4()
    assert scored.status == "reached"
    assert all(g.ok for g in scored.gates)
    assert score_l4(proactive_offer=False).status == "partial"


def test_l5_requires_both_lookup_and_write_zero_llm():
    assert score_l5(lookup_zero_llm=True, write_zero_llm=True).status == "reached"
    miss = score_l5(lookup_zero_llm=False, write_zero_llm=True)
    assert miss.status == "partial"
    assert any(g.id == "lookup_zero_llm" and not g.ok for g in miss.gates)
    live_miss = score_l5(
        lookup_zero_llm=True, write_zero_llm=True, live_plan_llm=2,
    )
    assert live_miss.status == "partial"


def test_23q_did_not_record_plan_llm_calls():
    assert live_plan_llm_from_verify(_load(LIVE_A9_PRIOR)) is None


def test_23s_live_plan_llm_is_zero():
    assert live_plan_llm_from_verify() == 0


def test_score_ladder_matches_honest_today():
    report = score_ladder(lookup_zero_llm=True, write_zero_llm=True)
    by_id = {row["id"]: row for row in report["levels"]}
    assert by_id["L0"]["status"] == "reached"
    assert by_id["L1"]["status"] == "reached"
    assert by_id["L2"]["status"] == "reached"
    assert by_id["L3"]["status"] == "reached"
    assert by_id["L4"]["status"] == "reached"
    assert by_id["L5"]["status"] == "reached"
    assert report["six_b_streak"] == 5
    assert report["soak_complete"] is True
    assert report["adr_0047"] == "Accepted"
    assert "live plan llm_calls=0" in by_id["L5"]["note"]
