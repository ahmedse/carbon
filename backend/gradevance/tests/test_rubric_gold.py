"""Instrument Trust T4 — rubric gold schema + adjacent-band agreement."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gradevance.services.reliability import adjacent_band_agreement

REPO = Path(__file__).resolve().parents[3]
HELD_OUT = (
    REPO
    / "domain_packs"
    / "eduos"
    / "engines"
    / "lct_semantics"
    / "naa_reflective_v1"
    / "held_out.jsonl"
)
SCHEMA = REPO / "domain_packs" / "eduos" / "schemas" / "gold_essay.schema.json"
NAA_CRITERIA = {
    "task_achievement",
    "coherence_cohesion",
    "lexis_grammar_academic_style",
}
BANDS = {"F", "E", "D", "C", "B", "A"}


def test_gold_essay_schema_exists():
    assert SCHEMA.is_file()
    doc = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert "expert_rubric_bands" in doc["properties"]


def test_naa_held_out_has_expert_rubric_bands():
    rows = [
        json.loads(line)
        for line in HELD_OUT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) >= 3
    for row in rows:
        bands = {
            k: v
            for k, v in (row.get("expert_rubric_bands") or {}).items()
            if not str(k).startswith("_") and k != "raw"
        }
        assert set(bands.keys()) == NAA_CRITERIA, row.get("id")
        assert all(v in BANDS for v in bands.values()), row.get("id")
        meta = row.get("expert_rubric_meta") or {}
        assert meta.get("_status") in {
            "dual_reviewed_soft",
            "tutor_letter_bands",
            "faculty_seed_2026-09-19",
            "seed_soft_until_faculty_double_code",
        } or meta.get("_protocol"), row.get("id")


def test_faculty_mark_sheet_has_cycle1_tutor_bands():
    sheet = REPO / "domain_packs" / "eduos" / "gold" / "naa" / "faculty_mark_sheet_cycle1_week1.json"
    assert sheet.is_file()
    doc = json.loads(sheet.read_text(encoding="utf-8"))
    assert "AR-CYCLE1-03" in doc["marks"]
    hani = doc["marks"]["AR-CYCLE1-03"]
    assert hani["task_achievement"] == "D"
    assert hani["coherence_cohesion"] == "E"
    assert hani["lexis_grammar_academic_style"] == "F"


def test_adjacent_band_agreement_exact_and_adjacent():
    order = ["F", "E", "D", "C", "B", "A"]
    exact = adjacent_band_agreement(["C", "B", "A"], ["C", "B", "A"], band_order=order)
    assert exact["exact"] == 1.0
    assert exact["adjacent"] == 1.0
    assert exact["passed"] is True

    adj = adjacent_band_agreement(["C", "B", "A"], ["B", "B", "A"], band_order=order)
    assert adj["exact"] == pytest.approx(2 / 3, rel=1e-3)
    assert adj["adjacent"] == 1.0

    far = adjacent_band_agreement(["A"], ["F"], band_order=order)
    assert far["exact"] == 0.0
    assert far["adjacent"] == 0.0
