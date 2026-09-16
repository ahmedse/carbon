"""ECF-5 — MAPE-K heal loop tests."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
import yaml

from ai.engine.cognition.entity.registry import load_descriptors
from ai.engine.cognition.entity.heal import (
    classify_failure,
    tier1_heal,
    nominate_golden_case,
    handle_turn_signal,
    _NOMINATIONS_FILE,
)

NIBRAS_YAML = Path(__file__).parent.parent / "engine/instances/nibras/instance.yaml"

_EMPLOYEES = [
    {"id": 9, "employee_no": "1009", "full_name": "Reena Sekaran", "name_en_given": "Reena", "name_en_family": "Sekaran", "name_ar_given": "", "name_ar_family": "", "civil_id": "", "is_active": True, "org_unit_id": 5},
]
for i in range(200):
    _EMPLOYEES.append({"id": 1000+i, "employee_no": str(3000+i), "full_name": f"Filler {i}", "name_en_given": f"F{i}", "name_en_family": "Fill", "name_ar_given": "", "name_ar_family": "", "civil_id": "", "is_active": True, "org_unit_id": 1})


def _fake_fetch(model_path, filters, fields, limit):
    results = []
    for rec in _EMPLOYEES:
        m = all(str(rec.get(k,"")) == str(v) for k,v in filters.items() if k != "org_unit_id__in")
        if "org_unit_id__in" in filters:
            m = m and rec.get("org_unit_id") in filters["org_unit_id__in"]
        if m:
            results.append(rec)
    return results if limit == 0 else results[:limit]


@pytest.fixture
def nibras_cfg():
    return yaml.safe_load(NIBRAS_YAML.read_text())


class TestClassifyFailure:
    def test_correction_ar_tier2(self):
        assert classify_failure("ليس صحيح", None) == "tier2"

    def test_correction_en_tier2(self):
        assert classify_failure("that's wrong", None) == "tier2"

    def test_غلط_tier2(self):
        assert classify_failure("غلط", None) == "tier2"

    def test_contract_violation_tier1(self):
        tool_result = {"found": False, "searched_total": 0}  # missing searched_total
        assert classify_failure("ok", tool_result) == "tier1"

    def test_no_signal_none(self):
        assert classify_failure("how many employees?", None) == "none"


class TestTier1Heal:
    def test_known_employee_heals(self, nibras_cfg):
        result = tier1_heal("employee", "Reena Sekaran", nibras_cfg, _fake_fetch)
        assert result["healed"] is True
        assert result["record"]["employee_no"] == "1009"

    def test_unknown_employee_grounded_none(self, nibras_cfg):
        result = tier1_heal("employee", "Salman Ali Hussain Zakareya", nibras_cfg, _fake_fetch)
        assert result["healed"] is False
        assert result.get("searched_total", 0) > 0
        assert "message" in result


class TestNominateGoldenCase:
    def test_nomination_written_to_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "ai.engine.cognition.entity.heal._NOMINATIONS_FILE",
            tmp_path / "nominations.json",
        )
        nom = nominate_golden_case("غلط", "No employee found.", "employee", "Salman Ali", conversation_id="c1")
        assert nom["query"] == "Salman Ali"
        assert (tmp_path / "nominations.json").exists()
        data = json.loads((tmp_path / "nominations.json").read_text())
        assert any(n["query"] == "Salman Ali" for n in data)

    def test_duplicate_not_written_twice(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "ai.engine.cognition.entity.heal._NOMINATIONS_FILE",
            tmp_path / "nominations.json",
        )
        nominate_golden_case("غلط", "...", "employee", "Salman", conversation_id="c1")
        nominate_golden_case("ليس صحيح", "...", "employee", "Salman", conversation_id="c2")
        data = json.loads((tmp_path / "nominations.json").read_text())
        salman_entries = [n for n in data if n["query"] == "Salman"]
        assert len(salman_entries) == 1  # no duplicate


class TestHandleTurnSignal:
    def test_correction_nominates(self, nibras_cfg, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "ai.engine.cognition.entity.heal._NOMINATIONS_FILE",
            tmp_path / "nominations.json",
        )
        result = handle_turn_signal(
            "غلط", None, "No employee found.",
            entity_type="employee", query="Salman", instance_config=nibras_cfg,
        )
        assert result["tier"] == "tier2"
        assert "nomination" in result

    def test_contract_violation_heals(self, nibras_cfg):
        bad_result = {"found": False, "searched_total": 0}
        result = handle_turn_signal(
            "ok", bad_result, "",
            entity_type="employee", query="Reena Sekaran",
            instance_config=nibras_cfg, fetch_fn=_fake_fetch,
        )
        assert result["tier"] == "tier1"
        assert result.get("healed") is True

    def test_no_signal_noop(self, nibras_cfg):
        result = handle_turn_signal("how many employees?", None, "")
        assert result["tier"] == "none"
