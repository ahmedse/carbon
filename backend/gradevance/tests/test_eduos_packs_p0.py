"""P0 smoke: EduOS GradeVance pack validation + gold wave oscillation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
EDUOS = REPO / "domain_packs" / "eduos"
VALIDATE = EDUOS / "scripts" / "validate_packs.py"


def test_validate_packs_script_passes():
    proc = subprocess.run(
        [sys.executable, str(VALIDATE)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK" in proc.stdout


def test_naa_gold_wave_oscillates():
    gold = json.loads((EDUOS / "gold/naa/AR-CYCLE1-18-week1.json").read_text())
    codes = [p["sg_numeric"] for p in gold["wave_points"]]
    assert len(set(codes)) >= 2
    assert gold["word_count"] == 158
    assert len(gold["segments"]) == 5


def test_naa_profile_pins_packs():
    profile = yaml.safe_load(
        (EDUOS / "profiles/naa_cycle1_exam_prep_v1.yaml").read_text()
    )
    assert profile["lct_device"]["id"] == "naa_reflective_semantics"
    assert profile["rubric_pack"]["id"] == "naa_reflective_analytic"
    assert profile["hitl"]["learning_loop_enabled"] is True
    assert profile["pipeline"]["lct_enabled"] is True


def test_osce_pack_is_hybrid_medicine():
    rubric = yaml.safe_load(
        (EDUOS / "engines/rubric/medicine_osce_abdominal_v1/rubric.yaml").read_text()
    )
    assert rubric["discipline"] == "medicine"
    assert rubric["genre"] == "osce_station"
    assert rubric["mode"] == "hybrid"
    scorings = {c["scoring"] for c in rubric["criteria"]}
    assert "quantitative" in scorings
    assert "qualitative" in scorings
    assert abs(sum(c["weight"] for c in rubric["criteria"]) - 1.0) < 1e-6


def test_schemas_exist():
    for name in (
        "translation_device.schema.json",
        "rubric_pack.schema.json",
        "assignment_profile.schema.json",
    ):
        assert (EDUOS / "schemas" / name).is_file()
