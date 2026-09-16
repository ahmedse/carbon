"""ECF-8 — LeaveRecord golden harness (descriptor-only generalize proof).

Proves entity #2 resolves via the existing ECF algorithm + nibras
``leave_record`` descriptor — zero new code under cognition/entity/.

Run:
    cd backend && ../.venv/bin/python -m pytest ai/tests/test_ecf_leave_golden.py -v
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml

from ai.engine.cognition.entity.contracts import grounded_refusal
from ai.engine.cognition.entity.registry import get_descriptor, load_descriptors
from ai.engine.cognition.entity.resolver import resolve

NIBRAS_YAML = Path(__file__).parent.parent / "engine/instances/nibras/instance.yaml"

# In-memory LeaveRecord population (no Django). Mirrors people.models.LeaveRecord
# fields; employee__org_unit_id supports scope_lookup filtering in fetch_fn.
_LEAVE_POPULATION: list[dict[str, Any]] = [
    {
        "id": 42,
        "employee": 9,
        "leave_type": 101,
        "start_date": "2026-03-01",
        "end_date": "2026-03-05",
        "days": "5.00",
        "status": "approved",
        "employee__org_unit_id": 5,
    },
    {
        "id": 43,
        "employee": 1,
        "leave_type": 102,
        "start_date": "2026-04-10",
        "end_date": "2026-04-12",
        "days": "3.00",
        "status": "submitted",
        "employee__org_unit_id": 23,
    },
    {
        "id": 44,
        "employee": 433,
        "leave_type": 101,
        "start_date": "2026-05-01",
        "end_date": "2026-05-02",
        "days": "2.00",
        "status": "draft",
        "employee__org_unit_id": 30,
    },
    {
        "id": 45,
        "employee": 247,
        "leave_type": 103,
        "start_date": "2026-06-15",
        "end_date": "2026-06-20",
        "days": "6.00",
        "status": "cancelled",
        "employee__org_unit_id": 10,
    },
]
for _i in range(50, 120):
    _LEAVE_POPULATION.append({
        "id": _i,
        "employee": 1,
        "leave_type": 101,
        "start_date": f"2025-{( (_i % 12) + 1):02d}-01",
        "end_date": f"2025-{((_i % 12) + 1):02d}-02",
        "days": "1.00",
        "status": "approved" if _i % 2 == 0 else "submitted",
        "employee__org_unit_id": 1,
    })

_EMPLOYEES = {
    9: {"id": 9, "full_name": "Reena Sekaran"},
    1: {"id": 1, "full_name": "Wellie Bonglay Eslit"},
    433: {"id": 433, "full_name": "Abrar Alam Azeemullah Ansari"},
    247: {"id": 247, "full_name": "Sanavulla Shaik"},
}

_LEAVE_TYPES = {
    101: {"id": 101, "label": "Annual Leave", "code": "AL"},
    102: {"id": 102, "label": "Sick Leave", "code": "SL"},
    103: {"id": 103, "label": "Unpaid Leave", "code": "UL"},
}


def _leave_fetch_fn(model_path: str, filters: dict, fields: list, limit: int) -> list[dict]:
    """In-memory fetch for LeaveRecord + label_map targets (no Django)."""
    if model_path == "people.models.Employee":
        eid = filters.get("id")
        row = _EMPLOYEES.get(eid) or _EMPLOYEES.get(int(eid) if eid is not None else None)
        return [row] if row else []
    if model_path == "mdm.models.ReferenceValue":
        rid = filters.get("id")
        row = _LEAVE_TYPES.get(rid) or _LEAVE_TYPES.get(int(rid) if rid is not None else None)
        return [row] if row else []

    results = []
    for rec in _LEAVE_POPULATION:
        match = True
        for k, v in filters.items():
            if k == "employee__org_unit_id__in":
                if rec.get("employee__org_unit_id") not in v:
                    match = False
                    break
                continue
            if str(rec.get(k, "")) != str(v):
                match = False
                break
        if match:
            results.append(rec)
    return results if limit == 0 else results[:limit]


@dataclass(frozen=True)
class LeaveGoldenCase:
    id: str
    query: str
    must_find: bool
    leave_id: int | None
    invariants: list[str] = field(default_factory=list)


LEAVE_GOLDEN_CASES: list[LeaveGoldenCase] = [
    LeaveGoldenCase(
        id="leave_lookup_by_id_42",
        query="42",
        must_find=True,
        leave_id=42,
        invariants=[
            "resolves via LeaveRecord.id identifier",
            "must not return grounded-none",
        ],
    ),
    LeaveGoldenCase(
        id="leave_lookup_by_start_date",
        query="2026-03-01",
        must_find=True,
        leave_id=42,
        invariants=[
            "distinctive start_date search_field match",
        ],
    ),
    LeaveGoldenCase(
        id="leave_grounded_none_unknown_id",
        query="99999",
        must_find=False,
        leave_id=None,
        invariants=[
            'grounded-none with "searched N of N"',
            'never bare "not found" without count',
        ],
    ),
    LeaveGoldenCase(
        id="leave_grounded_none_unknown_date",
        query="2099-01-01",
        must_find=False,
        leave_id=None,
        invariants=[
            "unknown leave date → none",
            "searched_total populated",
        ],
    ),
]


def _leave_descriptor():
    cfg = yaml.safe_load(NIBRAS_YAML.read_text())
    return load_descriptors(cfg)["leave_record"]


def call_leave_lookup(query: str) -> dict[str, Any]:
    """Resolve LeaveRecord via ECF against in-memory population."""
    desc = _leave_descriptor()
    result = resolve(desc, query, fetch_fn=_leave_fetch_fn)
    n = result.searched_total

    if result.action == "match" and result.record:
        rec = result.record
        lid = int(rec["id"])
        status = rec.get("status") or ""
        response = (
            f"Found leave_record id={lid} (status={status}, "
            f"start={rec.get('start_date')}, end={rec.get('end_date')})."
        )
        return {
            "ok": True,
            "found": True,
            "leave_id": lid,
            "status": status,
            "response": response,
            "text": response,
            "searched_total": n,
            "total": n,
            "lang": result.lang,
            "query": query,
            "matched_field": result.matched_field,
        }

    if result.lang == "ar":
        response = grounded_refusal(result) or (
            f"لم يُعثر على سجل إجازة مطابق (تم البحث في {n} من {n} سجل)."
        )
    else:
        response = f"No matching leave record found (searched {n} of {n})."
    return {
        "ok": True,
        "found": False,
        "leave_id": None,
        "response": response,
        "text": response,
        "searched_total": n,
        "total": n,
        "lang": result.lang,
        "query": query,
    }


def assert_leave_invariants(case: LeaveGoldenCase, result: dict[str, Any]) -> None:
    found = bool(result.get("found"))
    lid = result.get("leave_id")
    text = str(result.get("response") or result.get("text") or "")
    searched = result.get("searched_total")
    total = result.get("total")

    if case.must_find:
        assert found, f"[{case.id}]: expected leave match for {case.query!r}"
        assert lid == case.leave_id, (
            f"[{case.id}]: expected leave_id={case.leave_id!r}, got {lid!r}"
        )
    else:
        assert not found, f"[{case.id}]: expected grounded-none for {case.query!r}"
        assert searched is not None and total is not None, (
            f"[{case.id}]: grounded-none must include searched_total/total"
        )
        assert searched == total and searched > 0
        assert str(searched) in text and (
            f"{searched} of {total}" in text
            or f"{searched} من {total}" in text
        ), f"[{case.id}]: response must cite searched N of N, got {text!r}"

    for inv in case.invariants:
        assert inv, f"[{case.id}]: empty invariant"


class TestLeaveRecordDescriptorLoads:
    """Structural gate — descriptor present without algorithm changes."""

    def test_leave_record_in_registry(self):
        cfg = yaml.safe_load(NIBRAS_YAML.read_text())
        descs = load_descriptors(cfg)
        assert "leave_record" in descs
        assert "employee" in descs

    def test_get_descriptor_leave_record(self):
        cfg = yaml.safe_load(NIBRAS_YAML.read_text())
        desc = get_descriptor(cfg, "leave_record")
        assert desc is not None
        assert desc.name == "leave_record"
        assert desc.model == "people.models.LeaveRecord"
        assert desc.identifiers == ["id"]
        assert desc.scope_lookup == "employee__org_unit_id__in"
        assert "employee" in desc.label_map
        assert desc.label_map["employee"].field == "full_name"
        assert "leave_type" in desc.label_map
        assert "open_leave_count" in desc.metrics
        assert desc.metrics["open_leave_count"].filter == {"status": "submitted"}

    def test_minimum_leave_case_count(self):
        assert len(LEAVE_GOLDEN_CASES) >= 2


@pytest.mark.parametrize(
    "case", LEAVE_GOLDEN_CASES, ids=[c.id for c in LEAVE_GOLDEN_CASES]
)
def test_leave_golden_case(case: LeaveGoldenCase):
    """LeaveRecord goldens — existing resolve + descriptor (must PASS)."""
    result = call_leave_lookup(case.query)
    assert_leave_invariants(case, result)
