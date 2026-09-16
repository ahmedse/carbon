"""ECF-6 — Canonical metric aggregation unit tests (no DB, no LLM).

Proves descriptor metrics{} → aggregate() is the single definition path:
  headcount → is_active=True
  kuwaiti   → nationality__code=KWT (never kuwaitization boolean)
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

from ai.engine.cognition.entity.aggregate import (
    AggregateResult,
    UnknownMetricError,
    aggregate,
)
from ai.engine.cognition.entity.registry import load_descriptors
from ai.engine.agent.tools import (
    execute_aggregate_entity,
    get_tool_definitions,
)

NIBRAS_YAML = Path(__file__).parent.parent / "engine/instances/nibras/instance.yaml"

# Mixed population: active/inactive × KWT / non-KWT / kuwaitization flag mismatch.
_POPULATION = [
    {"id": 1, "is_active": True,  "nationality__code": "KWT", "kuwaitization": True},
    {"id": 2, "is_active": True,  "nationality__code": "KWT", "kuwaitization": False},  # KWT but flag off
    {"id": 3, "is_active": True,  "nationality__code": "IND", "kuwaitization": True},   # flag on, not KWT
    {"id": 4, "is_active": True,  "nationality__code": "EGY", "kuwaitization": False},
    {"id": 5, "is_active": False, "nationality__code": "KWT", "kuwaitization": True},   # inactive KWT
    {"id": 6, "is_active": False, "nationality__code": "IND", "kuwaitization": False},
]


def _count_fn(population=None):
    pop = population if population is not None else _POPULATION

    def count_fn(model_path: str, filters: dict) -> int:
        n = 0
        for rec in pop:
            if all(rec.get(k) == v for k, v in (filters or {}).items()):
                n += 1
        return n

    return count_fn


@pytest.fixture
def nibras_desc():
    cfg = yaml.safe_load(NIBRAS_YAML.read_text())
    return load_descriptors(cfg)["employee"]


class TestAggregateCanonicalMetrics:
    def test_headcount_uses_is_active(self, nibras_desc):
        r = aggregate(nibras_desc, "headcount", count_fn=_count_fn())
        assert isinstance(r, AggregateResult)
        assert r.metric == "headcount"
        assert r.value == 4  # ids 1-4
        assert r.filter == {"is_active": True}
        assert "is_active" in r.cited_fields

    def test_kuwaiti_uses_nationality_code_not_kuwaitization(self, nibras_desc):
        r = aggregate(nibras_desc, "kuwaiti", count_fn=_count_fn())
        assert r.value == 3  # ids 1, 2, 5 — nationality__code=KWT (incl. inactive)
        assert r.filter == {"nationality__code": "KWT"}
        assert "nationality__code" in r.cited_fields
        assert "kuwaitization" not in r.filter
        assert "kuwaitization" not in r.cited_fields
        # Prove divergence from the boolean: kuwaitization=True would be ids 1,3,5 → 3
        # but id membership differs — id 2 is KWT without flag; id 3 has flag without KWT.
        kw_flag = sum(1 for p in _POPULATION if p["kuwaitization"])
        assert kw_flag == 3
        kw_ids = {p["id"] for p in _POPULATION if p["nationality__code"] == "KWT"}
        flag_ids = {p["id"] for p in _POPULATION if p["kuwaitization"]}
        assert kw_ids != flag_ids, "fixture must prove KWT ≠ kuwaitization membership"

    def test_headcount_stable_across_calls(self, nibras_desc):
        a = aggregate(nibras_desc, "headcount", count_fn=_count_fn())
        b = aggregate(nibras_desc, "headcount", count_fn=_count_fn())
        assert a.value == b.value

    def test_kuwaiti_stable_across_calls(self, nibras_desc):
        a = aggregate(nibras_desc, "kuwaiti", count_fn=_count_fn())
        b = aggregate(nibras_desc, "kuwaiti", count_fn=_count_fn())
        assert a.value == b.value
        assert a.filter == b.filter

    def test_unknown_metric_lists_available(self, nibras_desc):
        with pytest.raises(UnknownMetricError) as ei:
            aggregate(nibras_desc, "attrition", count_fn=_count_fn())
        assert "headcount" in ei.value.available
        assert "kuwaiti" in ei.value.available


class TestExecuteAggregateEntity:
    @pytest.mark.asyncio
    async def test_happy_path_headcount(self, nibras_desc):
        cfg = yaml.safe_load(NIBRAS_YAML.read_text())
        executor = SimpleNamespace(
            instance_config=cfg,
            entity_count=_count_fn(),
        )
        result = await execute_aggregate_entity(
            entity_type="employee",
            metric="headcount",
            explanation="total staff",
            executor=executor,
        )
        assert result["metric"] == "headcount"
        assert result["value"] == 4
        assert result["filter"]["is_active"] is True
        assert "is_active" in result["cited_fields"]
        assert "is_active" in result["citation"]

    @pytest.mark.asyncio
    async def test_kuwaiti_cites_nationality_code(self):
        cfg = yaml.safe_load(NIBRAS_YAML.read_text())
        executor = SimpleNamespace(
            instance_config=cfg,
            entity_count=_count_fn(),
        )
        result = await execute_aggregate_entity(
            entity_type="employee",
            metric="kuwaiti",
            explanation="kuwaiti count",
            executor=executor,
        )
        assert result["value"] == 3
        assert result["filter"] == {"nationality__code": "KWT"}
        assert "nationality__code" in result["citation"]
        assert "kuwaitization" not in result["citation"]

    @pytest.mark.asyncio
    async def test_unknown_metric_error_shape(self):
        cfg = yaml.safe_load(NIBRAS_YAML.read_text())
        executor = SimpleNamespace(
            instance_config=cfg,
            entity_count=_count_fn(),
        )
        result = await execute_aggregate_entity(
            entity_type="employee",
            metric="bogus",
            explanation="x",
            executor=executor,
        )
        assert "error" in result
        assert "headcount" in result["available_metrics"]

    @pytest.mark.asyncio
    async def test_missing_entity_count(self):
        cfg = yaml.safe_load(NIBRAS_YAML.read_text())
        executor = SimpleNamespace(instance_config=cfg)  # no entity_count
        result = await execute_aggregate_entity(
            entity_type="employee",
            metric="headcount",
            explanation="x",
            executor=executor,
        )
        assert "error" in result
        assert "entity_count" in result["error"]

    @pytest.mark.asyncio
    async def test_unauthorized_when_people_metric_access_denied(self):
        """A10: ESS without people:view must not get a soft zero headcount."""
        cfg = yaml.safe_load(NIBRAS_YAML.read_text())
        executor = SimpleNamespace(
            instance_config=cfg,
            entity_count=_count_fn(),
            people_metric_access=lambda: {
                "allowed": False,
                "reason": "people:view_required",
                "message": "Not authorized to view organization workforce metrics.",
            },
        )
        result = await execute_aggregate_entity(
            entity_type="employee",
            metric="headcount",
            explanation="count",
            executor=executor,
        )
        assert result.get("unauthorized") is True
        assert result.get("value") is None
        assert "Not authorized" in (result.get("message") or "")
        assert result.get("reason") == "people:view_required"


class TestAggregateToolCatalogGate:
    def test_absent_when_ecf_disabled(self):
        with patch("ai.engine.agent.tools.get_settings") as gs:
            gs.return_value = SimpleNamespace(ECF_ENABLED=False)
            with patch("ai.engine.agent.tools.load_plugins", return_value=([], {})):
                names = [
                    t["function"]["name"]
                    for t in get_tool_definitions()
                    if t.get("type") == "function"
                ]
        assert "aggregate_entity" not in names

    def test_present_when_ecf_enabled(self):
        with patch("ai.engine.agent.tools.get_settings") as gs:
            gs.return_value = SimpleNamespace(ECF_ENABLED=True)
            with patch("ai.engine.agent.tools.load_plugins", return_value=([], {})):
                names = [
                    t["function"]["name"]
                    for t in get_tool_definitions()
                    if t.get("type") == "function"
                ]
        assert "aggregate_entity" in names
        assert "resolve_entity" in names

    def test_entity_type_enum_includes_leave_record_from_descriptors(self):
        """PEC-R7: schema advertises descriptor names (incl. leave_record)."""
        cfg = yaml.safe_load(NIBRAS_YAML.read_text())
        assert any(
            e.get("name") == "leave_record" for e in (cfg.get("entities") or [])
        )
        with patch("ai.engine.agent.tools.get_settings") as gs:
            gs.return_value = SimpleNamespace(ECF_ENABLED=True)
            with patch("ai.engine.agent.tools.load_plugins", return_value=([], {})):
                defs = {
                    t["function"]["name"]: t["function"]
                    for t in get_tool_definitions(cfg)
                    if t.get("type") == "function"
                }
        for tool_name in ("resolve_entity", "aggregate_entity"):
            et = defs[tool_name]["parameters"]["properties"]["entity_type"]
            assert "leave_record" in et["enum"]
            assert "employee" in et["enum"]
            assert "leave_record" in et["description"]
        metrics = defs["aggregate_entity"]["parameters"]["properties"]["metric"]["enum"]
        assert "open_leave_count" in metrics
        assert "headcount" in metrics