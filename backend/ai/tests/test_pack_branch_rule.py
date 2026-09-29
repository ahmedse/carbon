"""The branch-metrics intent rule belongs to the pack that catalogs it."""
from __future__ import annotations

from pathlib import Path

import yaml

from ai.engine.cognition.turn import intent as intent_mod
from ai.engine.cognition.turn.intent import _build_label_set, _build_system_prompt
from ai.engine.pack_vocab import bind_pack

_ROOT = Path(__file__).resolve().parents[3] / "domain_packs"
_PHRASES = ("East Campus", "Building 4", "Module B", "calculation-summary")


def _catalog(pack_id: str) -> list:
    doc = yaml.safe_load((_ROOT / pack_id / "instance.yaml").read_text(encoding="utf-8"))
    return list((doc or {}).get("api_catalog") or [])


def _prompt(pack_id: str, labels: list | None = None) -> str:
    built = _build_label_set(_catalog(pack_id) if labels is None else [])
    if labels is not None:
        built = labels
    with bind_pack(pack_id):
        return _build_system_prompt(built, [])


def test_carbon_prompt_teaches_the_branch_rule():
    text = _prompt("carbon")
    for phrase in _PHRASES:
        assert phrase in text


def test_medicine_and_nibras_omit_the_branch_rule():
    for pack_id in ("aast-med", "nibras"):
        text = _prompt(pack_id)
        for phrase in _PHRASES:
            assert phrase not in text


def test_carbon_without_the_summary_id_omits_the_bullet():
    text = _prompt("carbon", labels=[{"name": "list_org_units", "phrase": "org units", "description": ""}])
    for phrase in _PHRASES:
        assert phrase not in text


def test_intent_source_does_not_name_the_campus_example():
    source = Path(intent_mod.__file__).read_text(encoding="utf-8")
    for phrase in _PHRASES:
        assert phrase not in source


def test_answer_examples_from_step_18_still_hold():
    with bind_pack("aast-med"):
        medicine = _build_system_prompt(_build_label_set(_catalog("aast-med")), [])
    with bind_pack("nibras"):
        nibras = _build_system_prompt(_build_label_set(_catalog("nibras")), [])
    assert '"endpoint":"get_course"' in medicine
    assert '"endpoint":"analyze_employees"' in nibras
