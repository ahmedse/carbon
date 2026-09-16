"""ECF-3 — Boundary contract guard tests."""
from __future__ import annotations

import json
import yaml
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.engine.cognition.entity.registry import load_descriptors
from ai.engine.cognition.entity.contracts import (
    no_truncation_as_truth,
    resolve_labels,
    honest_masking,
    grounded_refusal,
    apply_entity_contracts,
)
from ai.engine.cognition.entity.resolver import ResolveResult
from ai.engine_runtime import _apply_ecf_entity_contracts

NIBRAS_YAML = Path(__file__).parent.parent / "engine/instances/nibras/instance.yaml"


@pytest.fixture
def emp_desc():
    cfg = yaml.safe_load(NIBRAS_YAML.read_text())
    return load_descriptors(cfg)["employee"]


class TestNoTruncationAsTruth:
    def test_truncated_source_cannot_claim_nonexistence(self, emp_desc):
        tool_result = {"data": {"total": 530, "count": 100, "truncated": True, "results": []}}
        prose = "No employee named Salman was found."
        out = no_truncation_as_truth(tool_result, prose, descriptor=emp_desc)
        assert "not found" in out.lower() or "no employee" in out.lower()
        assert "530" in out or "first page" in out or "complete search" in out

    def test_non_truncated_prose_unchanged(self, emp_desc):
        tool_result = {"data": {"total": 10, "count": 10, "truncated": False}}
        prose = "No employee named Salman was found."
        out = no_truncation_as_truth(tool_result, prose, descriptor=emp_desc)
        assert out == prose  # unchanged; source was complete

    def test_arabic_nonexistence_phrase_rewritten(self, emp_desc):
        tool_result = {"data": {"total": 530, "count": 100, "truncated": True}}
        prose = "لا يوجد موظف باسم سلمان."
        out = no_truncation_as_truth(tool_result, prose, descriptor=emp_desc)
        assert len(out) > len(prose)  # disclaimer appended


class TestHonestMasking:
    def test_zero_salary_becomes_hidden_without_capability(self, emp_desc):
        record = {"id": 1, "full_name": "Alice", "basic_salary": "0.000"}
        result = honest_masking(record, emp_desc, frozenset())
        assert result["basic_salary"] == "(hidden — salary access required)"

    def test_zero_float_salary_masked(self, emp_desc):
        record = {"id": 1, "full_name": "Alice", "basic_salary": 0.0}
        result = honest_masking(record, emp_desc, frozenset())
        assert "(hidden" in result["basic_salary"]

    def test_real_salary_hidden_without_capability(self, emp_desc):
        """A5: unauthorized callers must never see a real amount (not only zeros)."""
        record = {"id": 1, "full_name": "Alice", "basic_salary": "320.000"}
        result = honest_masking(record, emp_desc, frozenset())
        assert result["basic_salary"] == "(hidden — salary access required)"

    def test_real_salary_shown_with_capability(self, emp_desc):
        record = {"id": 1, "full_name": "Alice", "basic_salary": "756.000"}
        result = honest_masking(record, emp_desc, frozenset({"people:view_compensation"}))
        assert result["basic_salary"] == "756.000"

    def test_none_salary_masked(self, emp_desc):
        record = {"id": 1, "full_name": "Alice", "basic_salary": None}
        result = honest_masking(record, emp_desc, frozenset())
        assert "(hidden" in result["basic_salary"]


class TestResolveLabels:
    def test_position_id_gets_annotation(self, emp_desc):
        record = {"id": 1, "full_name": "Reena", "position": 170, "org_unit": 5}
        result = resolve_labels(record, emp_desc)
        # Without a live label_fetch_fn, ids get annotated not bare
        assert result["position"] != 170 or result["position"] == "#170"
        # With real label_fetch_fn:
        def fetch(model, filters, fields, limit):
            if model == "people.models.Position" and filters.get("id") == 170:
                return [{"title": "CT Senior Operator"}]
            if model == "mdm.models.OrgUnit" and filters.get("id") == 5:
                return [{"name": "Coiled Tubing"}]
            return []
        result2 = resolve_labels(record, emp_desc, label_fetch_fn=fetch)
        assert result2["position"] == "CT Senior Operator"
        assert result2["org_unit"] == "Coiled Tubing"


class TestGroundedRefusal:
    def test_none_result_returns_grounded_message(self):
        r = ResolveResult(action="none", searched_total=530, lang="en")
        msg = grounded_refusal(r)
        assert "530" in msg
        assert "searched" in msg.lower()

    def test_arabic_none_result_arabic_message(self):
        r = ResolveResult(action="none", searched_total=530, lang="ar")
        msg = grounded_refusal(r)
        assert "530" in msg
        assert any(ch > "\u0600" for ch in msg)  # contains Arabic

    def test_match_result_returns_none(self):
        r = ResolveResult(action="match", record={}, searched_total=530)
        assert grounded_refusal(r) is None


class TestApplyEntityContracts:
    def test_full_pipeline(self, emp_desc):
        tool_result = {
            "data": {
                "total": 530, "count": 100, "truncated": True,
                "results": [
                    {"id": 1, "full_name": "Alice", "basic_salary": "0.000", "position": 170},
                ]
            }
        }
        prose = "No employee found."
        cleaned_result, cleaned_prose = apply_entity_contracts(
            tool_result, prose, emp_desc, frozenset()
        )
        # Prose: truncation guard fires
        assert "530" in cleaned_prose or "first page" in cleaned_prose
        # Masking: salary hidden
        assert cleaned_result["data"]["results"][0]["basic_salary"].startswith("(hidden")

    def test_none_descriptor_passthrough(self):
        tool_result = {"data": {"results": [{"salary": "0"}]}}
        prose = "No records."
        r, p = apply_entity_contracts(tool_result, prose, None)
        assert r == tool_result
        assert p == prose


class TestRuntimeHook:
    """Cover ``_apply_ecf_entity_contracts`` call site (flag-gated)."""

    @pytest.fixture
    def nibras_cfg(self):
        return yaml.safe_load(NIBRAS_YAML.read_text())

    def test_flag_off_is_noop(self, nibras_cfg, monkeypatch):
        monkeypatch.setattr(
            "ai.engine.core.config.get_settings",
            lambda: SimpleNamespace(ECF_ENABLED=False),
        )
        tools = [{
            "tool_name": "call_host_api:list_employees",
            "result": json.dumps({
                "data": {
                    "total": 530, "count": 1, "truncated": True,
                    "results": [{"id": 1, "full_name": "Alice", "basic_salary": "0.000"}],
                }
            }),
        }]
        prose = "No employee found."
        out_tools, out_prose = _apply_ecf_entity_contracts(tools, prose, nibras_cfg)
        assert out_tools is tools or out_tools == tools
        assert out_prose == prose

    def test_flag_on_rewrites_truncated_claim_and_masks(self, nibras_cfg, monkeypatch):
        monkeypatch.setattr(
            "ai.engine.core.config.get_settings",
            lambda: SimpleNamespace(ECF_ENABLED=True),
        )
        tools = [{
            "tool_name": "call_host_api:list_employees",
            "result": json.dumps({
                "data": {
                    "total": 530, "count": 1, "truncated": True,
                    "results": [
                        {"id": 1, "full_name": "Alice", "basic_salary": "0.000", "position": 170},
                    ],
                }
            }),
        }]
        prose = "No employee found."
        out_tools, out_prose = _apply_ecf_entity_contracts(
            tools, prose, nibras_cfg, user_capabilities=frozenset()
        )
        assert "530" in out_prose or "first page" in out_prose or "complete search" in out_prose
        cleaned = json.loads(out_tools[0]["result"])
        assert cleaned["data"]["results"][0]["basic_salary"].startswith("(hidden")

    def test_non_entity_tool_skipped(self, nibras_cfg, monkeypatch):
        monkeypatch.setattr(
            "ai.engine.core.config.get_settings",
            lambda: SimpleNamespace(ECF_ENABLED=True),
        )
        tools = [{
            "tool_name": "search_knowledge",
            "result": json.dumps({"results": [{"id": 1}]}),
        }]
        prose = "No employee found."
        out_tools, out_prose = _apply_ecf_entity_contracts(tools, prose, nibras_cfg)
        assert out_prose == prose
        assert out_tools[0]["result"] == tools[0]["result"]
