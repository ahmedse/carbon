"""DRAFT medicine-L5 gold + harness tests.

Every cite is a real substring of a real bank passage; the L5 status reads
not_passable unless the real-world inputs (R12 two real students, a non-empty
student cohort, consent and audit records) are present. The frozen
``gold/l5.yaml`` is passable under the recorded local pilot exception
(docs/pulse/aast-med/PILOT-EXCEPTION.md): ``short`` is populated for all 13
shortnames and R11/R12 are 4/2. The draft source is still marked draft.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from ai.moodle_readiness.l5_draft import (
    CURRICULUM_GOLD,
    MIN_PASSAGE_CITE,
    R11_GOLD,
    SAMPLE_SIZE,
    derive_curriculum_items,
    load_curriculum_gold,
    load_r11_gold,
    medicine_l5_status,
    score_curriculum,
    score_r11,
    verify_cites,
)

BACKEND = Path(__file__).resolve().parents[2]
L5_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "l5.yaml"


@pytest.fixture(scope="module")
def gold() -> dict:
    return load_curriculum_gold()


@pytest.fixture(scope="module")
def shortnames(gold: dict) -> list[str]:
    return list(gold["short"])


# ── Gold honesty ─────────────────────────────────────────────────────────────


def test_curriculum_gold_is_marked_draft_not_pass(gold: dict):
    assert gold["status"] == "draft"
    assert gold["draft"] is True
    assert gold["not_pass"] is True
    assert gold["human_approval_required"] is True
    assert gold["sample_size_target"] == SAMPLE_SIZE


def test_every_cite_is_a_real_verbatim_passage_span(gold: dict):
    assert verify_cites(gold) == []


def test_every_item_is_unique_and_has_its_term_in_the_quote(gold: dict):
    for shortname, items in gold["short"].items():
        keys = set()
        for item in items:
            assert item["quote"].strip(), item["id"]
            assert item["term"].casefold() in item["quote"].casefold(), item["id"]
            key = (item["passage_id"], item["term"].casefold())
            assert key not in keys, (shortname, item["id"])
            keys.add(key)


def test_gold_matches_the_committed_derivation(gold: dict, shortnames: list[str]):
    """The frozen gold is the deterministic derivation, not hand-fabrication."""
    for shortname in shortnames:
        assert gold["short"][shortname] == derive_curriculum_items(shortname), shortname


def test_each_shortname_reaches_the_sample_size(gold: dict, shortnames: list[str]):
    assert shortnames  # the 13 listed shortnames
    for shortname in shortnames:
        assert len(gold["short"][shortname]) >= SAMPLE_SIZE, shortname


# ── Scoring / status ─────────────────────────────────────────────────────────


def test_curriculum_scores_at_bar_from_the_gold():
    scores = score_curriculum(run_door=False)
    assert scores
    for score in scores:
        assert score.sample_met is True, score.line()
        assert score.extra_facts == 0, score.line()
        assert score.at_bar is True, score.line()


def test_the_real_ask_door_cites_the_curriculum_gold():
    """The shipping door, offline, cites a real passage for each item."""
    scores = score_curriculum(run_door=True)
    assert len(scores) == 13
    for score in scores:
        assert score.sample_met is True, score.line()
        assert score.cite_met is True, score.line()
        assert score.extra_facts == 0, score.line()
        assert score.at_bar is True, score.line()


def test_medicine_l5_is_not_passable_on_the_real_repo():
    status = medicine_l5_status(run_door=False)
    assert status.passable is False
    assert status.status == "not_passable"
    # The code side (curriculum + R11 draft) is at bar.
    assert not any(g.startswith("curriculum_below_bar") for g in status.blocked_by)
    assert status.r11_frozen_n >= status.r11_required_n
    # The remaining gaps are exactly the real-world ones.
    assert "r12_two_real_students_missing(0/2)" in status.blocked_by
    assert "student_cohorts_empty" in status.blocked_by
    assert "consent_records_missing" in status.blocked_by
    assert "audit_records_missing" in status.blocked_by


@pytest.mark.parametrize(
    "field",
    [
        "r12_frozen_n",
        "student_cohorts_non_empty",
        "consent_records_present",
        "audit_present",
    ],
)
def test_l5_stays_not_passable_when_one_real_world_input_is_missing(field: str):
    full = dict(
        run_door=False,
        r12_frozen_n=2,
        student_cohorts_non_empty=True,
        consent_records_present=True,
        audit_present=True,
    )
    assert medicine_l5_status(**full).passable is True
    full[field] = 0 if field == "r12_frozen_n" else False
    assert medicine_l5_status(**full).passable is False


def test_medicine_l5_flips_only_when_every_real_world_input_is_present():
    assert medicine_l5_status(run_door=False).passable is False
    flipped = medicine_l5_status(
        run_door=False,
        r12_frozen_n=2,
        student_cohorts_non_empty=True,
        consent_records_present=True,
        audit_present=True,
    )
    assert flipped.status == "passable"
    assert flipped.blocked_by == ()


# ── R11 draft cases ──────────────────────────────────────────────────────────


def test_r11_gold_freezes_four_draft_cases():
    r11 = score_r11()
    assert r11["required_n"] == 4
    assert r11["frozen_n"] == 4
    assert len(r11["cases"]) == 4
    doc = load_r11_gold()
    assert doc["status"] == "draft"
    assert doc["draft"] is True
    assert str(doc.get("real_world_prerequisite") or "").strip()
    for case in r11["cases"]:
        assert case["claims_moodle_write"] is False
        assert case["host_effect"] == "none"


def test_r11_cases_are_draft_proposals_only():
    from ai.moodle_page import staff_answer
    from ai.moodle_readiness.l5_draft import _bank, _page

    for case in score_r11()["cases"]:
        shortname = case["course"]
        reply = staff_answer(case["ask"], _page(shortname))
        assert reply is not None, case["id"]
        assert reply.startswith(case["expect_label"]), case["id"]
        assert case["expect_no_write"] in reply, case["id"]
        assert "I saved" not in reply and "I applied" not in reply
        bank = _bank(shortname)
        for line in reply.splitlines():
            if line.startswith("- "):
                span = line[2:]
                assert any(span in str(row.get("text") or "") for row in bank.values()), case["id"]


# ── The freeze is explicit and honest (pilot exception) ──────────────────────


def test_frozen_l5_gold_is_passable_under_the_recorded_pilot_exception():
    frozen = yaml.safe_load(L5_GOLD.read_text(encoding="utf-8"))
    assert frozen["status"] == "passable"
    assert len(frozen["curriculum_benchmark"]["short"]) == 13
    assert frozen["r11_draft"]["frozen_n"] == 4
    assert frozen["r12_same_lecture_two_students"]["frozen_n"] == 2
    assert frozen["pilot_exception"]["scope"] == "local dev only"
    # The draft source is still marked draft/not-pass; only the freeze moved.
    draft = load_curriculum_gold()
    assert draft["status"] == "draft"
    assert draft["not_pass"] is True


def test_draft_harness_files_exist():
    assert CURRICULUM_GOLD.is_file()
    assert R11_GOLD.is_file()


def test_draft_harness_import_is_django_free():
    code = (
        "import sys, ai.moodle_readiness.l5_draft; "
        "assert 'django' not in sys.modules, 'l5_draft pulled Django in'"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
