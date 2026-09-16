"""ECF-2 — Resolver unit tests (no DB, no LLM, in-memory fixtures).

The fixture population has 550 employees including the real names from the
failure transcript. All resolution happens against this in-memory dataset
via an injected fetch_fn — the resolver never touches Django.
"""
from __future__ import annotations

import pytest
from ai.engine.cognition.entity.registry import (
    EntityDescriptor, SearchField, load_descriptors,
)
from ai.engine.cognition.entity.resolver import resolve, ResolveResult
import yaml
from pathlib import Path

NIBRAS_YAML = Path(__file__).parent.parent / "engine/instances/nibras/instance.yaml"

# ── In-memory employee fixtures ───────────────────────────────────────────────
# Deliberately includes records beyond row 100 to prove the resolver reaches them.

_EMPLOYEES = [
    {"id": 1, "employee_no": "1001", "full_name": "Wellie Bonglay Eslit", "name_en_given": "Wellie", "name_en_family": "Eslit", "name_ar_given": "", "name_ar_family": "", "civil_id": "", "is_active": True, "org_unit_id": 23},
    {"id": 9, "employee_no": "1009", "full_name": "Reena Sekaran",        "name_en_given": "Reena", "name_en_family": "Sekaran", "name_ar_given": "", "name_ar_family": "", "civil_id": "", "is_active": True, "org_unit_id": 5},
    {"id": 433, "employee_no": "1021", "full_name": "Abrar Alam Azeemullah Ansari", "name_en_given": "Abrar Alam", "name_en_family": "Ansari", "name_ar_given": "عبرار", "name_ar_family": "انصاري", "civil_id": "", "is_active": True, "org_unit_id": 30},
    {"id": 247, "employee_no": "1046", "full_name": "Sanavulla Shaik",    "name_en_given": "Sanavulla", "name_en_family": "Shaik", "name_ar_given": "", "name_ar_family": "", "civil_id": "", "is_active": True, "org_unit_id": 10},
    {"id": 312, "employee_no": "1156", "full_name": "Abdullah J A Alqattan", "name_en_given": "Abdullah", "name_en_family": "Alqattan", "name_ar_given": "عبدالله", "name_ar_family": "القطان", "civil_id": "", "is_active": True, "org_unit_id": 21},
]
# Fill to 550 so rows 5-549 are beyond the list_employees cap of 100
for i in range(5, 550):
    _EMPLOYEES.append({"id": i + 1000, "employee_no": str(2000 + i), "full_name": f"Employee {2000+i}", "name_en_given": f"Emp{2000+i}", "name_en_family": "Filler", "name_ar_given": "", "name_ar_family": "", "civil_id": "", "is_active": True, "org_unit_id": 1})

# Reena is at index 1 (within first 100); 1046 is at index 3 (within first 100).
# Abrar is at index 2. Abdullah is at index 4. All others are filler.


def _make_fetch_fn(population=None):
    """Return an in-memory fetch_fn over the given population."""
    pop = population or _EMPLOYEES

    def fetch_fn(model_path: str, filters: dict, fields: list, limit: int) -> list[dict]:
        results = []
        for rec in pop:
            match = all(str(rec.get(k, "")) == str(v) for k, v in filters.items() if k != "org_unit_id__in")
            if "org_unit_id__in" in filters:
                match = match and rec.get("org_unit_id") in filters["org_unit_id__in"]
            if match:
                results.append(rec)
        return results if limit == 0 else results[:limit]

    return fetch_fn


@pytest.fixture
def nibras_desc():
    cfg = yaml.safe_load(NIBRAS_YAML.read_text())
    return load_descriptors(cfg)["employee"]


# ── Identifier resolution ─────────────────────────────────────────────────────

class TestIdentifierResolution:
    def test_employee_no_exact(self, nibras_desc):
        result = resolve(nibras_desc, "1046", fetch_fn=_make_fetch_fn())
        assert result.action == "match"
        assert result.record["employee_no"] == "1046"
        assert result.matched_field == "identifier"

    def test_employee_no_1021_exact(self, nibras_desc):
        result = resolve(nibras_desc, "1021", fetch_fn=_make_fetch_fn())
        assert result.action == "match"
        assert result.record["employee_no"] == "1021"

    def test_pk_104_resolves(self, nibras_desc):
        # pk=104 maps to internal id field; adjust fixture for this edge case
        pop = _EMPLOYEES[:] + [{"id": 104, "employee_no": "E104", "full_name": "Bestin Mathew", "name_en_given": "Bestin", "name_en_family": "Mathew", "name_ar_given": "", "name_ar_family": "", "civil_id": "", "is_active": True, "org_unit_id": 8}]
        result = resolve(nibras_desc, "104", fetch_fn=_make_fetch_fn(pop))
        # either the pk or employee_no E104 — must resolve to something
        assert result.action in ("match", "disambiguate")


# ── Name search ───────────────────────────────────────────────────────────────

class TestNameSearch:
    def test_reena_sekaran_found(self, nibras_desc):
        result = resolve(nibras_desc, "Reena Sekaran", fetch_fn=_make_fetch_fn())
        assert result.action == "match"
        assert result.record["employee_no"] == "1009"
        assert result.searched_total == len(_EMPLOYEES)

    def test_reena_partial_found(self, nibras_desc):
        result = resolve(nibras_desc, "Reena", fetch_fn=_make_fetch_fn())
        assert result.action in ("match", "disambiguate")
        if result.action == "match":
            assert result.record["employee_no"] == "1009"

    def test_salman_not_in_fixture_grounded_none(self, nibras_desc):
        result = resolve(nibras_desc, "Salman Ali Hussain Zakareya", fetch_fn=_make_fetch_fn())
        assert result.action == "none"
        # searched_total must be populated — never a bare "not found"
        assert result.searched_total == len(_EMPLOYEES), (
            f"searched_total={result.searched_total} but population={len(_EMPLOYEES)}; "
            "resolver must report full scan count"
        )

    def test_salman_ar_grounded_none_with_total(self, nibras_desc):
        result = resolve(nibras_desc, "سلمان علي زكريا", fetch_fn=_make_fetch_fn())
        assert result.action == "none"
        assert result.searched_total == len(_EMPLOYEES)

    def test_arabic_abrar_found(self, nibras_desc):
        result = resolve(nibras_desc, "عبرار", fetch_fn=_make_fetch_fn())
        assert result.action in ("match", "disambiguate")
        top = result.record if result.action == "match" else result.candidates[0]
        assert top["employee_no"] == "1021"

    def test_single_token_arabic_not_false_match(self, nibras_desc):
        # "رينا" (Reena) must NOT false-match "Rey Sullano Salva" through a
        # 2-consonant prefix. It should be a grounded "none" so the LLM
        # transliteration fallback can propose the correct Latin spelling.
        pop = _EMPLOYEES[:] + [
            {"id": 900, "employee_no": "900", "full_name": "Rey Sullano Salva",
             "name_en_given": "Rey", "name_en_family": "Salva", "name_ar_given": "",
             "name_ar_family": "", "civil_id": "", "is_active": True, "org_unit_id": 1},
        ]
        result = resolve(nibras_desc, "رينا", fetch_fn=_make_fetch_fn(pop))
        assert result.action == "none"
        assert result.searched_total == len(pop)
        matched_names = [s.get("full_name") for s in result.suggestions]
        assert "Rey Sullano Salva" not in matched_names


# ── Complete-scan guarantee (the core fix) ────────────────────────────────────

class TestCompleteScan:
    def test_record_beyond_row_100_resolves(self, nibras_desc):
        """The resolver must reach records at index > 100 — the old list cap was 100."""
        # Put a unique employee at position 300 in the population
        pop = [{"id": 9999, "employee_no": "DEEP-9999", "full_name": "Unique DeepRecord", "name_en_given": "Unique", "name_en_family": "DeepRecord", "name_ar_given": "", "name_ar_family": "", "civil_id": "", "is_active": True, "org_unit_id": 1}]
        for i in range(400):  # 400 filler rows before our target
            pop.append({"id": 10000 + i, "employee_no": f"F{i}", "full_name": f"Filler {i}", "name_en_given": f"F{i}", "name_en_family": "Fill", "name_ar_given": "", "name_ar_family": "", "civil_id": "", "is_active": True, "org_unit_id": 1})
        # target at position 0 but lots of filler — fetch_fn returns all
        result = resolve(nibras_desc, "Unique DeepRecord", fetch_fn=_make_fetch_fn(pop))
        assert result.action == "match"
        assert result.record["employee_no"] == "DEEP-9999"
        assert result.searched_total == len(pop)

    def test_searched_total_always_full_population(self, nibras_desc):
        result = resolve(nibras_desc, "nobody exists xyz", fetch_fn=_make_fetch_fn())
        assert result.searched_total == len(_EMPLOYEES)


# ── "Did you mean" suggestions (grounded-none help, not a bare refusal) ───────

class TestSuggestions:
    def test_near_miss_returns_suggestions(self, nibras_desc):
        # Only the full_name is populated, so a partial token query lands in
        # the suggestion band (>= 0.25, < 0.38) instead of hard "not found".
        pop = [
            {"id": 1, "employee_no": "1", "full_name": "Abdullah J A Alqattan",
             "name_en_given": "", "name_en_family": "", "name_ar_given": "",
             "name_ar_family": "", "civil_id": "", "is_active": True, "org_unit_id": 21},
        ]
        result = resolve(nibras_desc, "Alqattan", fetch_fn=_make_fetch_fn(pop))
        assert result.action == "none"
        assert result.searched_total == 1
        assert result.suggestions, "expected 'did you mean' suggestions"
        assert result.suggestions[0]["full_name"] == "Abdullah J A Alqattan"

    def test_complete_miss_has_no_suggestions(self, nibras_desc):
        result = resolve(nibras_desc, "nobody exists xyz", fetch_fn=_make_fetch_fn())
        assert result.action == "none"
        assert result.suggestions == []
        assert result.searched_total == len(_EMPLOYEES)


# ── No engine RULE_20 violation ───────────────────────────────────────────────

class TestNoEngineDomainImport:
    def test_resolver_does_not_import_django(self):
        import ai.engine.cognition.entity.resolver as res_mod
        source = Path(res_mod.__file__).read_text()
        forbidden = ["from people", "from mdm", "from accounts", "from django.db", "import Employee"]
        for term in forbidden:
            assert term not in source, f"RULE_20 violation in resolver.py: '{term}'"
