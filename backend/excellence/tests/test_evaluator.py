"""Evaluator rules (ADR-0051 §4–§6): Soundcheck ladder, min across dimensions, stale, exempt, ratchet."""
from __future__ import annotations

from datetime import date, timedelta

from excellence.catalogue import Catalogue, Check, Subject, Tier
from excellence.evaluator import evaluate, regressions

HEAD = "abc123"


def _cat() -> Catalogue:
    cat = Catalogue()
    cat.tiers["platform"] = Tier(id="platform", title="p")
    cat.subjects["m"] = Subject(id="m", kind="module", title="m", tier="platform", owner="o", paths=("x",))
    for cid, dim, rank in [
        ("G1", "governed", 1), ("G2", "governed", 1),
        ("S2", "specified", 2),
        ("C3", "correct", 3), ("C4", "correct", 4),
    ]:
        cat.checks[cid] = Check(id=cid, title=cid, dimension=dim, rank=rank, collector="repo")
    return cat


def _ev(check: str, result: str = "passed", commit: str = HEAD, at: int = 1, cls: str = "executed") -> dict:
    return {"check_id": check, "subject_id": "m", "commit": commit, "result": result, "evidence_class": cls, "at": at}


def test_no_events_is_unmanaged_and_unmeasured() -> None:
    rep = evaluate(_cat(), [], head=HEAD)["m"]
    assert rep.level == 0
    assert {c.state for c in rep.checks} == {"unmeasured"}
    assert [c.check.id for c in rep.next_steps] == ["G1", "G2"]


def test_level_is_min_across_dimensions_with_soundcheck_rule() -> None:
    events = [_ev("G1"), _ev("G2"), _ev("S2"), _ev("C3"), _ev("C4", "failed")]
    rep = evaluate(_cat(), events, head=HEAD)["m"]
    # governed has checks only at rank 1; it does not block ranks 2-3 (specified/correct carry them)
    assert rep.dimensions == {"correct": 3, "governed": 4, "specified": 4}
    assert rep.level == 3
    assert [c.check.id for c in rep.next_steps] == ["C4"]


def test_one_failing_rank1_check_pins_the_subject_at_l0() -> None:
    events = [_ev("G1"), _ev("G2", "failed"), _ev("S2"), _ev("C3"), _ev("C4")]
    rep = evaluate(_cat(), events, head=HEAD)["m"]
    assert rep.level == 0 and rep.dimensions["governed"] == 0


def test_rank_gap_stops_the_ladder() -> None:
    cat = _cat()
    del cat.checks["S2"]  # nobody wrote a rank-2 check → rank 2 is not earned
    events = [_ev("G1"), _ev("G2"), _ev("C3"), _ev("C4")]
    assert evaluate(cat, events, head=HEAD)["m"].level == 1


def test_stale_event_does_not_count() -> None:
    events = [_ev("G1", commit="old"), _ev("G2")]
    rep = evaluate(_cat(), events, head=HEAD)["m"]
    assert rep.level == 0
    assert {c.check.id: c.state for c in rep.checks}["G1"] == "stale"


def test_latest_event_wins_and_unknown_is_not_a_pass() -> None:
    events = [_ev("G1", at=1), _ev("G1", "unknown", at=2, cls="unknown"), _ev("G2")]
    rep = evaluate(_cat(), events, head=HEAD)["m"]
    assert {c.check.id: c.state for c in rep.checks}["G1"] == "unknown"
    assert rep.level == 0


def test_conflict_is_never_passable() -> None:
    events = [_ev("G1", cls="conflict"), _ev("G2")]
    rep = evaluate(_cat(), events, head=HEAD)["m"]
    assert {c.check.id: c.state for c in rep.checks}["G1"] == "conflict"


def test_active_exemption_satisfies_expired_does_not() -> None:
    today = date(2026, 9, 24)
    events = [_ev("G1"), _ev("G2", "failed")]
    active = [{"check_id": "G2", "subject_id": "m", "until": today}]
    expired = [{"check_id": "G2", "subject_id": "m", "until": today - timedelta(days=1)}]
    assert evaluate(_cat(), events, active, head=HEAD, today=today)["m"].level == 1
    assert evaluate(_cat(), events, expired, head=HEAD, today=today)["m"].level == 0


def test_ratchet_reports_only_drops() -> None:
    rep = evaluate(_cat(), [_ev("G1"), _ev("G2")], head=HEAD)
    assert regressions(rep, {"m": 3}) == ["m: L3 → L1"]
    assert regressions(rep, {"m": 1}) == []
    assert regressions(rep, {}) == []
