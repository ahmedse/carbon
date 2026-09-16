"""ECF-1 — Entity Registry unit tests.

No DB, no LLM, no network. Loads the nibras instance config via
`_instance_config("nibras", None)` and verifies the entity descriptor
is parsed correctly.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ai.engine.cognition.entity import (
    EntityDescriptor,
    get_descriptor,
    load_descriptors,
)
from ai.engine_runtime import _instance_config


@pytest.fixture
def nibras_config():
    return _instance_config("nibras", None)


class TestLoadDescriptors:
    def test_employee_descriptor_present(self, nibras_config):
        descs = load_descriptors(nibras_config)
        assert "employee" in descs

    def test_employee_model_path(self, nibras_config):
        emp = load_descriptors(nibras_config)["employee"]
        assert emp.model == "people.models.Employee"

    def test_employee_identifiers(self, nibras_config):
        emp = load_descriptors(nibras_config)["employee"]
        assert "employee_no" in emp.identifiers
        assert "civil_id" in emp.identifiers
        # employee_no must be first so user-typed numbers resolve correctly
        assert emp.identifiers[0] == "employee_no"

    def test_employee_search_fields_bilingual(self, nibras_config):
        emp = load_descriptors(nibras_config)["employee"]
        langs = {sf.lang for sf in emp.search_fields}
        assert "en" in langs
        assert "ar" in langs

    def test_arabic_fields_have_normalize(self, nibras_config):
        emp = load_descriptors(nibras_config)["employee"]
        ar_fields = [sf for sf in emp.search_fields if sf.lang == "ar"]
        assert ar_fields, "No Arabic search fields declared"
        for sf in ar_fields:
            assert sf.normalize == "arabic", f"{sf.field} missing normalize=arabic"

    def test_employee_no_highest_weight(self, nibras_config):
        emp = load_descriptors(nibras_config)["employee"]
        emp_no_field = next((sf for sf in emp.search_fields if sf.field == "employee_no"), None)
        assert emp_no_field is not None
        # employee_no should outweigh name fields so numeric lookup wins
        max_name_weight = max(
            sf.weight for sf in emp.search_fields
            if sf.field not in ("employee_no", "civil_id")
        )
        assert emp_no_field.weight > max_name_weight, (
            "employee_no must have higher weight than all name fields "
            "so numeric lookup wins over substring name match"
        )

    def test_label_map_position_and_org_unit(self, nibras_config):
        emp = load_descriptors(nibras_config)["employee"]
        assert "position" in emp.label_map
        assert "org_unit" in emp.label_map
        assert emp.label_map["position"].field == "title"
        assert emp.label_map["org_unit"].field == "name"

    def test_salary_masking_policy(self, nibras_config):
        emp = load_descriptors(nibras_config)["employee"]
        assert "basic_salary" in emp.masking
        assert emp.masking["basic_salary"].capability == "people:view_compensation"

    def test_canonical_metrics_defined(self, nibras_config):
        emp = load_descriptors(nibras_config)["employee"]
        assert "headcount" in emp.metrics
        assert "kuwaiti" in emp.metrics
        # headcount must filter on is_active=True
        assert emp.metrics["headcount"].filter.get("is_active") is True
        # kuwaiti must use nationality__code (ReferenceValue), NOT kuwaitization boolean
        assert "nationality__code" in emp.metrics["kuwaiti"].filter
        assert emp.metrics["kuwaiti"].filter.get("nationality__code") == "KWT"
        assert "kuwaitization" not in emp.metrics["kuwaiti"].filter, (
            "kuwaiti metric must use nationality__code, not the kuwaitization boolean — "
            "that is what caused the 55-vs-5 inconsistency"
        )

    def test_scope_lookup_set(self, nibras_config):
        emp = load_descriptors(nibras_config)["employee"]
        assert emp.scope_lookup == "org_unit_id__in"


class TestGetDescriptor:
    def test_known_entity(self, nibras_config):
        desc = get_descriptor(nibras_config, "employee")
        assert isinstance(desc, EntityDescriptor)
        assert desc.name == "employee"

    def test_unknown_entity_returns_none(self, nibras_config):
        assert get_descriptor(nibras_config, "nonexistent_entity") is None

    def test_empty_config_returns_none(self):
        assert get_descriptor({}, "employee") is None

    def test_none_config_returns_none(self):
        assert get_descriptor(None, "employee") is None  # type: ignore


class TestNoEngineRuleViolation:
    def test_registry_does_not_import_django(self):
        """RULE_20: engine module must never import Django domain apps."""
        import ai.engine.cognition.entity.registry as reg_mod
        source = Path(reg_mod.__file__).read_text()
        forbidden = [
            "from people", "from mdm", "from accounts",
            "import Employee", "import OrgUnit",
            "from django.db",
        ]
        for term in forbidden:
            assert term not in source, (
                f"RULE_20 violation: '{term}' found in registry.py — "
                "engine must stay domain-neutral"
            )
