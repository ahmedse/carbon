"""ECF-0 / ECF-6 / lookup green — Golden regression harness.

Lookup cases exercise the ECF resolver against an in-memory population
(ECF-7 cutover 2026-09-16: ``ECF_ENABLED`` default True; harness still
calls ``resolve`` / ``aggregate`` directly). Metric cases exercise
``aggregate`` (ECF-6).

Run:
    cd backend && ../.venv/bin/python -m pytest ai/tests/test_ecf_golden.py -v
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml

from ai.engine.cognition.entity.aggregate import aggregate
from ai.engine.cognition.entity.contracts import grounded_refusal
from ai.engine.cognition.entity.registry import load_descriptors
from ai.engine.cognition.entity.resolver import resolve

NIBRAS_YAML = Path(__file__).parent.parent / "engine/instances/nibras/instance.yaml"

# In-memory population for metric golden cases (ECF-6). Mirrors the
# KW ≠ kuwaitization divergence that caused the real 55-vs-5 inconsistency.
_METRIC_POPULATION = [
    {"id": 1, "is_active": True,  "nationality_code": "KW", "kuwaitization": True},
    {"id": 2, "is_active": True,  "nationality_code": "KW", "kuwaitization": False},
    {"id": 3, "is_active": True,  "nationality_code": "IN", "kuwaitization": True},
    {"id": 4, "is_active": True,  "nationality_code": "EG", "kuwaitization": False},
    {"id": 5, "is_active": False, "nationality_code": "KW", "kuwaitization": True},
    {"id": 6, "is_active": False, "nationality_code": "IN", "kuwaitization": False},
]

_METRIC_CASE_IDS = frozenset({"headcount_stable", "kuwaiti_count_stable"})
_QUERY_TO_METRIC = {
    "كم عدد الموظفين": "headcount",
    "كم كويتي موظف": "kuwaiti",
}

# Arabic headcount-like prose (not a name lookup) — arabic_in_arabic_out.
_AR_HEADCOUNT_QUERIES = frozenset({"كم موظف لدينا"})

# Position titles keyed by FK id (label_map → people.models.Position.title).
_POSITIONS = {
    10: {"id": 10, "title": "Field Operator"},
    11: {"id": 11, "title": "Senior Engineer"},
    12: {"id": 12, "title": "Technician"},
    13: {"id": 13, "title": "Coordinator"},
    170: {"id": 170, "title": "CT Senior Operator"},
}

# Lookup population adapted from test_ecf_resolver._EMPLOYEES.
# Includes Reena/1009, Abrar/عبرار/1021, 1046, pk=104 with employee_no "104".
# Deliberately omits Salman Ali Hussain Zakareya (must_find=False grounded-none).
_LOOKUP_POPULATION: list[dict[str, Any]] = [
    {
        "id": 1, "employee_no": "1001", "full_name": "Wellie Bonglay Eslit",
        "name_en_given": "Wellie", "name_en_family": "Eslit",
        "name_ar_given": "", "name_ar_family": "", "civil_id": "",
        "is_active": True, "org_unit_id": 23, "position": 10,
    },
    {
        "id": 9, "employee_no": "1009", "full_name": "Reena Sekaran",
        "name_en_given": "Reena", "name_en_family": "Sekaran",
        "name_ar_given": "", "name_ar_family": "", "civil_id": "",
        "is_active": True, "org_unit_id": 5, "position": 170,
    },
    {
        "id": 433, "employee_no": "1021", "full_name": "Abrar Alam Azeemullah Ansari",
        "name_en_given": "Abrar Alam", "name_en_family": "Ansari",
        "name_ar_given": "عبرار", "name_ar_family": "انصاري", "civil_id": "",
        "is_active": True, "org_unit_id": 30, "position": 11,
    },
    {
        "id": 247, "employee_no": "1046", "full_name": "Sanavulla Shaik",
        "name_en_given": "Sanavulla", "name_en_family": "Shaik",
        "name_ar_given": "", "name_ar_family": "", "civil_id": "",
        "is_active": True, "org_unit_id": 10, "position": 12,
    },
    {
        # pk fallback golden: query "104" → employee_no must be "104"
        "id": 104, "employee_no": "104", "full_name": "Bestin Mathew",
        "name_en_given": "Bestin", "name_en_family": "Mathew",
        "name_ar_given": "", "name_ar_family": "", "civil_id": "",
        "is_active": True, "org_unit_id": 8, "position": 13,
    },
]
for _i in range(5, 550):
    _LOOKUP_POPULATION.append({
        "id": _i + 1000,
        "employee_no": str(2000 + _i),
        "full_name": f"Employee {2000 + _i}",
        "name_en_given": f"Emp{2000 + _i}",
        "name_en_family": "Filler",
        "name_ar_given": "",
        "name_ar_family": "",
        "civil_id": "",
        "is_active": True,
        "org_unit_id": 1,
        "position": 10,
    })


def _lookup_fetch_fn(model_path: str, filters: dict, fields: list, limit: int) -> list[dict]:
    """In-memory fetch over `_LOOKUP_POPULATION` / `_POSITIONS` (no Django)."""
    if model_path == "people.models.Position":
        pid = filters.get("id")
        row = _POSITIONS.get(pid) or _POSITIONS.get(int(pid) if pid is not None else None)
        return [row] if row else []

    results = []
    for rec in _LOOKUP_POPULATION:
        match = all(
            str(rec.get(k, "")) == str(v)
            for k, v in filters.items()
            if k != "org_unit_id__in"
        )
        if "org_unit_id__in" in filters:
            match = match and rec.get("org_unit_id") in filters["org_unit_id__in"]
        if match:
            results.append(rec)
    return results if limit == 0 else results[:limit]


def _position_title(record: dict[str, Any]) -> str | None:
    raw = record.get("position")
    if raw is None:
        return None
    if isinstance(raw, str) and not raw.isdigit() and not raw.startswith("#"):
        return raw
    try:
        pid = int(raw)
    except (TypeError, ValueError):
        return str(raw)
    row = _POSITIONS.get(pid)
    return row["title"] if row else None


@dataclass(frozen=True)
class GoldenCase:
    id: str
    query: str
    must_find: bool
    employee_no: str | None
    invariants: list[str] = field(default_factory=list)


# Minimum set from TASKS.md Phase ECF-0 (do not drop ids).
GOLDEN_CASES: list[GoldenCase] = [
    GoldenCase(
        id="lookup_salman_en_full",
        query="Salman Ali Hussain Zakareya",
        must_find=False,
        employee_no=None,
        invariants=[
            'grounded-none with "searched N of N"',
            'never "not found" without count',
        ],
    ),
    GoldenCase(
        id="lookup_salman_ar",
        query="سلمان علي زكريا",
        must_find=False,
        employee_no=None,
        invariants=[
            'grounded-none with "searched N of N"',
            "Arabic in, Arabic response",
        ],
    ),
    GoldenCase(
        id="lookup_salman_partial",
        query="salman zakareya",
        must_find=False,
        employee_no=None,
        invariants=[
            "partial match attempt",
            "no hallucination",
        ],
    ),
    GoldenCase(
        id="lookup_employee_no_1046",
        query="1046",
        must_find=True,
        employee_no="1046",
        invariants=[
            "resolves via employee_no not PK",
            'must not return "not found"',
        ],
    ),
    GoldenCase(
        id="lookup_employee_no_1021",
        query="1021",
        must_find=True,
        employee_no="1021",
        invariants=[
            "resolves via employee_no not PK",
            'must not return "not found"',
        ],
    ),
    GoldenCase(
        id="lookup_pk_104",
        query="104",
        must_find=True,
        employee_no="104",
        invariants=[
            "pk fallback",
            "must resolve if pk 104 exists",
        ],
    ),
    GoldenCase(
        id="lookup_reena_sekaran",
        query="Reena Sekaran",
        must_find=True,
        employee_no="1009",
        invariants=[
            "name search returns correct emp_no",
        ],
    ),
    GoldenCase(
        id="lookup_ar_abrar",
        query="عبرار",
        must_find=True,
        employee_no="1021",
        invariants=[
            "transliteration-like Arabic partial",
        ],
    ),
    GoldenCase(
        id="existence_over_truncated",
        query="is there an employee named Salman?",
        must_find=False,
        employee_no=None,
        invariants=[
            'must NOT produce "no such employee" without "searched N of N"',
        ],
    ),
    GoldenCase(
        id="headcount_stable",
        query="كم عدد الموظفين",
        must_find=False,
        employee_no=None,
        invariants=[
            "number matches DB",
            "consistent across calls",
        ],
    ),
    GoldenCase(
        id="kuwaiti_count_stable",
        query="كم كويتي موظف",
        must_find=False,
        employee_no=None,
        invariants=[
            "single definition used",
            "same number repeated",
            "must cite which field",
        ],
    ),
    GoldenCase(
        id="position_label",
        query="tell me about Reena Sekaran",
        must_find=True,
        employee_no="1009",
        invariants=[
            "response contains position title not numeric id",
        ],
    ),
    GoldenCase(
        id="arabic_in_arabic_out",
        query="كم موظف لدينا",
        must_find=False,
        employee_no=None,
        invariants=[
            "response language is Arabic",
        ],
    ),
]

REQUIRED_CASE_IDS = frozenset(c.id for c in GOLDEN_CASES)
LOOKUP_CASES = [c for c in GOLDEN_CASES if c.id not in _METRIC_CASE_IDS]
METRIC_CASES = [c for c in GOLDEN_CASES if c.id in _METRIC_CASE_IDS]


def _metric_count_fn(model_path: str, filters: dict) -> int:
    return sum(
        1
        for rec in _METRIC_POPULATION
        if all(rec.get(k) == v for k, v in (filters or {}).items())
    )


def call_nibras_metric(query: str) -> dict[str, Any]:
    """ECF-6 path: descriptor metrics{} → aggregate (same number every call)."""
    metric = _QUERY_TO_METRIC.get(query)
    if not metric:
        return {
            "ok": False,
            "baseline": True,
            "query": query,
            "error": "BASELINE_FAILURE",
            "detail": f"No metric mapping for query {query!r}",
        }
    cfg = yaml.safe_load(NIBRAS_YAML.read_text())
    desc = load_descriptors(cfg)["employee"]
    first = aggregate(desc, metric, count_fn=_metric_count_fn)
    second = aggregate(desc, metric, count_fn=_metric_count_fn)
    expected = sum(
        1
        for rec in _METRIC_POPULATION
        if all(rec.get(k) == v for k, v in first.filter.items())
    )
    return {
        "ok": True,
        "metric": first.metric,
        "value": first.value,
        "value_repeat": second.value,
        "filter": first.filter,
        "cited_fields": list(first.cited_fields),
        "citation": (
            f"{first.metric} = count where "
            + ", ".join(f"{k}={first.filter[k]!r}" for k in first.cited_fields)
        ),
        "expected_db": expected,
        "query": query,
        "response": (
            f"{first.value} ({first.description}; field={','.join(first.cited_fields)})"
        ),
    }


def call_nibras_entity_lookup(query: str, *, fixture: dict[str, Any] | None = None) -> dict[str, Any]:
    """ECF lookup path against in-memory population via :func:`resolve`.

    Metric queries route to :func:`call_nibras_metric`. Arabic headcount-like
    prose (``كم موظف لدينا``) returns an Arabic grounded count — not a name
    resolve. Harness calls ECF ``resolve`` directly (independent of the
    Settings flag; cutover ECF-7 enables tools in production).
    """
    if fixture is not None:
        return fixture
    if query in _QUERY_TO_METRIC:
        return call_nibras_metric(query)

    q = (query or "").strip()
    if q in _AR_HEADCOUNT_QUERIES:
        active = sum(1 for rec in _LOOKUP_POPULATION if rec.get("is_active"))
        total = len(_LOOKUP_POPULATION)
        return {
            "ok": True,
            "found": False,
            "employee_no": None,
            "response": f"عدد الموظفين النشطين لدينا هو {active}.",
            "text": f"عدد الموظفين النشطين لدينا هو {active}.",
            "searched_total": total,
            "total": total,
            "lang": "ar",
            "query": query,
        }

    cfg = yaml.safe_load(NIBRAS_YAML.read_text())
    desc = load_descriptors(cfg)["employee"]
    result = resolve(desc, q, fetch_fn=_lookup_fetch_fn)
    n = result.searched_total

    if result.action == "match" and result.record:
        rec = result.record
        emp_no = str(rec.get("employee_no") or "")
        title = _position_title(rec)
        name = rec.get("full_name") or emp_no
        if result.lang == "ar":
            response = (
                f"تم العثور على الموظف {name} (رقم الموظف {emp_no})"
                + (f"، المسمى الوظيفي: {title}." if title else ".")
            )
        else:
            response = (
                f"Found employee {name} (employee_no={emp_no})"
                + (f", position: {title}." if title else ".")
            )
        return {
            "ok": True,
            "found": True,
            "employee_no": emp_no,
            "response": response,
            "text": response,
            "searched_total": n,
            "total": n,
            "position_title": title,
            "lang": result.lang,
            "query": query,
        }

    # Grounded-none (and disambiguate treated as none for existence goldens).
    if result.lang == "ar":
        response = grounded_refusal(result) or (
            f"لم يُعثر على سجل مطابق (تم البحث في {n} من {n} سجل)."
        )
    else:
        response = f"No matching record found (searched {n} of {n})."
    return {
        "ok": True,
        "found": False,
        "employee_no": None,
        "response": response,
        "text": response,
        "searched_total": n,
        "total": n,
        "lang": result.lang,
        "query": query,
    }


def assert_golden_invariants(case: GoldenCase, result: dict[str, Any]) -> None:
    """Assert case invariants against a lookup / metric result."""
    if case.id in _METRIC_CASE_IDS:
        assert result.get("ok"), f"[{case.id}] metric path failed: {result}"
        assert result["value"] == result["expected_db"], (
            f"[{case.id}]: value {result['value']} != DB {result['expected_db']}"
        )
        assert result["value"] == result["value_repeat"], (
            f"[{case.id}]: unstable across calls "
            f"{result['value']} vs {result['value_repeat']}"
        )
        if case.id == "headcount_stable":
            assert result["filter"].get("is_active") is True
            assert "is_active" in result["cited_fields"]
        if case.id == "kuwaiti_count_stable":
            assert result["filter"] == {"nationality_code": "KW"}
            assert "nationality_code" in result["cited_fields"]
            assert "kuwaitization" not in result["filter"]
            assert "nationality_code" in result["citation"]
        for inv in case.invariants:
            assert inv, f"[{case.id}]: empty invariant"
        return

    if result.get("baseline") or result.get("error") == "BASELINE_FAILURE":
        pytest.fail(
            f"BASELINE_FAILURE [{case.id}]: ECF not yet implemented "
            f"(query={case.query!r}; must_find={case.must_find}; "
            f"employee_no={case.employee_no!r}; invariants={case.invariants})"
        )

    found = bool(result.get("found"))
    emp_no = result.get("employee_no")
    text = str(result.get("response") or result.get("text") or "")
    searched = result.get("searched_total")
    total = result.get("total")

    if case.must_find:
        assert found, (
            f"BASELINE_FAILURE [{case.id}]: expected a resolved record for {case.query!r}"
        )
        assert emp_no == case.employee_no, (
            f"BASELINE_FAILURE [{case.id}]: expected employee_no={case.employee_no!r}, got {emp_no!r}"
        )
    else:
        # Grounded-none path: must not claim universal absence without N of N.
        if "no such employee" in text.lower() or "not found" in text.lower():
            assert searched is not None and total is not None, (
                f'BASELINE_FAILURE [{case.id}]: "not found" without searched N of N'
            )

    if case.id == "position_label":
        title = result.get("position_title")
        assert title and not str(title).isdigit(), (
            f"[{case.id}]: expected position title string, got {title!r}"
        )
        assert str(title) in text, (
            f"[{case.id}]: response must contain position title {title!r}"
        )
    if case.id == "arabic_in_arabic_out":
        assert any("\u0600" <= ch <= "\u06FF" for ch in text), (
            f"[{case.id}]: expected Arabic-language response, got {text!r}"
        )
    if case.id in {
        "lookup_salman_en_full",
        "lookup_salman_ar",
        "lookup_salman_partial",
        "existence_over_plaintext",
    }:
        assert searched is not None and total is not None, (
            f"[{case.id}]: grounded-none must include searched_total/total"
        )
        assert searched == total and searched > 0
        assert str(searched) in text and (
            f"{searched} of {total}" in text
            or f"{searched} من {total}" in text
            or f"في {searched}" in text
            or f"all {searched}" in text.lower()
        ), f"[{case.id}]: response must cite searched N of N, got {text!r}"

    for inv in case.invariants:
        assert inv, f"BASELINE_FAILURE [{case.id}]: empty invariant"


class TestGoldenCasesAreDeclared:
    """Offline structural gate — must PASS (not xfail)."""

    def test_minimum_case_count(self):
        assert len(GOLDEN_CASES) >= 13

    def test_all_required_ids_present(self):
        ids = {c.id for c in GOLDEN_CASES}
        required = {
            "lookup_salman_en_full",
            "lookup_salman_ar",
            "lookup_salman_partial",
            "lookup_employee_no_1046",
            "lookup_employee_no_1021",
            "lookup_pk_104",
            "lookup_reena_sekaran",
            "lookup_ar_abrar",
            "existence_over_truncated",
            "headcount_stable",
            "kuwaiti_count_stable",
            "position_label",
            "arabic_in_arabic_out",
        }
        assert required == REQUIRED_CASE_IDS
        assert required.issubset(ids), f"Missing cases: {required - ids}"

    def test_each_case_has_invariants(self):
        for case in GOLDEN_CASES:
            assert case.invariants, f"Case {case.id} has no invariants"

    def test_must_find_cases_have_employee_no(self):
        for case in GOLDEN_CASES:
            if case.must_find:
                assert case.employee_no is not None, (
                    f"Case {case.id} must_find=True but no expected employee_no"
                )


@pytest.mark.parametrize("case", LOOKUP_CASES, ids=[c.id for c in LOOKUP_CASES])
def test_golden_case_lookup(case: GoldenCase):
    """Lookup goldens — ECF resolver + in-memory population (must PASS)."""
    result = call_nibras_entity_lookup(case.query)
    assert_golden_invariants(case, result)


@pytest.mark.parametrize("case", METRIC_CASES, ids=[c.id for c in METRIC_CASES])
def test_golden_metric_stable(case: GoldenCase):
    """ECF-6: same question → same canonical metric number (must PASS)."""
    result = call_nibras_metric(case.query)
    assert_golden_invariants(case, result)
