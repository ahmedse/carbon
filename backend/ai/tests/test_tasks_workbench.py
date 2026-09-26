"""The Tasks workbench holds, and the core file stays pack-free."""
from pathlib import Path

from ai.eval.tasks_workbench import CORE_BANK, load_cases, score


def test_core_and_pack_cases_hold():
    report = score()
    assert report["misses"] == [], report["misses"]
    assert report["gate_pass"] is True
    assert report["tier"] == "structural"
    assert report["n"] >= 30


def test_core_bank_does_not_name_a_pack():
    text = CORE_BANK.read_text(encoding="utf-8").lower()
    packs = Path(__file__).resolve().parents[3] / "domain_packs"
    ids = [p.name.lower() for p in packs.iterdir() if p.is_dir() and not p.name.startswith(".")]
    leaked = [name for name in ids if name in text]
    assert leaked == []


def test_pack_cases_are_loaded_from_the_pack_dir():
    ids = [case["id"] for case in load_cases()]
    assert any(case_id.startswith("core.") for case_id in ids)
    assert any(not case_id.startswith("core.") for case_id in ids)
