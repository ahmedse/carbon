"""ECF residual — live host entity_fetch for leave_record (django_db).

Proves CarbonHostExecutor.entity_fetch scopes LeaveRecord via
``employee__org_unit_id__in`` (same descriptor path as employee
``org_unit_id__in``) and returns fields needed by search/identifiers/label_map.

Run:
    cd backend && ../.venv/bin/python -m pytest ai/tests/test_ecf_leave_fetch_fn.py -v
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from asgiref.sync import async_to_sync

from accounts.models import User
from django.contrib.auth.models import Group
from accounts.models import ScopedRole
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee, LeaveRecord

from ai.engine.agent.tools import execute_resolve_entity
from ai.engine.cognition.entity.registry import get_descriptor
from ai.engine.cognition.entity.resolver import resolve
from ai.host_executor import (
    CarbonHostExecutor,
    _people_entity_scope_lookup,
)

NIBRAS_YAML = Path(__file__).parent.parent / "engine/instances/nibras/instance.yaml"


def _nibras_config() -> dict:
    with open(NIBRAS_YAML) as f:
        return yaml.safe_load(f)


def _executor(user: User, cfg: dict | None = None) -> CarbonHostExecutor:
    return CarbonHostExecutor(
        db=None,
        instance_config=cfg or _nibras_config(),
        user_token=f"inproc:nibras:{user.pk}",
        host_user_id=str(user.pk),
    )


def _leave_type(code: str = "annual", label: str = "Annual Leave") -> ReferenceValue:
    rs, _ = ReferenceSet.objects.get_or_create(
        name="leave_type", defaults={"slug": "leave-type"},
    )
    rv, _ = ReferenceValue.objects.get_or_create(
        reference_set=rs,
        code=code,
        defaults={"label": label, "is_active": True, "sort_order": 1},
    )
    return rv


def _employee(org: OrgUnit, no: str, name: str) -> Employee:
    return Employee.objects.create(
        org_unit=org,
        employee_no=no,
        full_name=name,
        basic_salary=Decimal("1000.000"),
        join_date=date(2026, 1, 1),
        is_active=True,
    )


def _leave(emp: Employee, leave_type: ReferenceValue, **kw) -> LeaveRecord:
    defaults = dict(
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 5),
        days=Decimal("5.00"),
        status="approved",
    )
    defaults.update(kw)
    return LeaveRecord.objects.create(employee=emp, leave_type=leave_type, **defaults)


# ── unit: scope lookup map ───────────────────────────────────────────────────


def test_scope_lookup_leave_record_from_map():
    assert _people_entity_scope_lookup("people.models.LeaveRecord") == (
        "employee__org_unit_id__in"
    )
    assert _people_entity_scope_lookup("people.models.Employee") == "org_unit_id__in"


def test_scope_lookup_prefers_instance_descriptor():
    cfg = {
        "entities": [
            {
                "name": "leave_record",
                "model": "people.models.LeaveRecord",
                "scope_lookup": "employee__org_unit_id__in",
            }
        ]
    }
    assert _people_entity_scope_lookup("people.models.LeaveRecord", cfg) == (
        "employee__org_unit_id__in"
    )


# ── live ORM fetch ───────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_entity_fetch_leave_record_returns_descriptor_fields():
    user = User.objects.create_superuser(username="ecf-leave-fetch", password="x")
    org = OrgUnit.objects.create(name="Leave Org", slug="ecf-leave-org")
    emp = _employee(org, "LR001", "Reena Sekaran")
    lt = _leave_type()
    rec = _leave(emp, lt, status="approved", start_date=date(2026, 3, 1))

    ex = _executor(user)
    desc = get_descriptor(_nibras_config(), "leave_record")
    assert desc is not None
    fields = (
        list({sf.field for sf in desc.search_fields})
        + list(desc.identifiers)
        + list(desc.label_map.keys())
    )
    rows = ex.entity_fetch(
        "people.models.LeaveRecord",
        {},
        fields,
        0,
    )
    assert any(r["id"] == rec.pk for r in rows)
    hit = next(r for r in rows if r["id"] == rec.pk)
    assert hit["status"] == "approved"
    assert hit["start_date"] == "2026-03-01"
    assert hit["end_date"] == "2026-03-05"
    # label_map keys (not employee_id / leave_type_id only)
    assert hit.get("employee") == emp.pk
    assert hit.get("leave_type") == lt.pk


@pytest.mark.django_db(transaction=True)
def test_entity_fetch_leave_record_org_scoped():
    """Scoped user sees leave only for employees in visible orgs."""
    org_a = OrgUnit.objects.create(name="Org A", slug="ecf-leave-a")
    org_b = OrgUnit.objects.create(name="Org B", slug="ecf-leave-b")
    lt = _leave_type()
    emp_a = _employee(org_a, "A1", "Alice")
    emp_b = _employee(org_b, "B1", "Bob")
    leave_a = _leave(emp_a, lt, status="submitted")
    leave_b = _leave(emp_b, lt, status="submitted", start_date=date(2026, 4, 1), end_date=date(2026, 4, 2), days=Decimal("2.00"))

    user = User.objects.create_user(username="ecf-leave-scoped", password="x")
    group, _ = Group.objects.get_or_create(name="viewers_group")
    ScopedRole.objects.create(user=user, group=group, org_unit=org_a, is_active=True)

    ex = _executor(user)
    rows = ex.entity_fetch("people.models.LeaveRecord", {}, ["id", "status", "employee"], 0)
    ids = {r["id"] for r in rows}
    assert leave_a.pk in ids
    assert leave_b.pk not in ids


@pytest.mark.django_db(transaction=True)
def test_resolve_leave_record_via_live_fetch_fn():
    """resolve() + host entity_fetch matches leave by id and start_date."""
    user = User.objects.create_superuser(username="ecf-leave-resolve", password="x")
    org = OrgUnit.objects.create(name="Resolve Org", slug="ecf-leave-resolve")
    emp = _employee(org, "LR042", "Reena Sekaran")
    lt = _leave_type()
    rec = _leave(emp, lt, start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))

    cfg = _nibras_config()
    desc = get_descriptor(cfg, "leave_record")
    ex = _executor(user, cfg)

    by_id = resolve(desc, str(rec.pk), fetch_fn=ex.entity_fetch)
    assert by_id.action == "match"
    assert by_id.record["id"] == rec.pk

    by_date = resolve(desc, "2026-03-01", fetch_fn=ex.entity_fetch)
    assert by_date.action == "match"
    assert by_date.record["id"] == rec.pk


@pytest.mark.django_db(transaction=True)
def test_execute_resolve_entity_leave_record_tool_path():
    """execute_resolve_entity wires executor.entity_fetch for leave_record."""
    user = User.objects.create_superuser(username="ecf-leave-tool", password="x")
    org = OrgUnit.objects.create(name="Tool Org", slug="ecf-leave-tool")
    emp = _employee(org, "LR099", "Tool Emp")
    lt = _leave_type()
    rec = _leave(emp, lt, status="approved")

    cfg = _nibras_config()
    ex = _executor(user, cfg)
    result = async_to_sync(execute_resolve_entity)(
        entity_type="leave_record",
        query=str(rec.pk),
        explanation="test",
        executor=ex,
        instance_config=cfg,
        instance_id="nibras",
        conversation_id="test-conv",
    )
    assert result.get("found") is True
    assert result.get("action") == "match"
    assert result["record"]["id"] == rec.pk
    # label_map: employee → full_name
    assert result["record"].get("employee") == "Tool Emp"


@pytest.mark.django_db(transaction=True)
def test_entity_count_leave_metrics_scoped():
    user = User.objects.create_superuser(username="ecf-leave-count", password="x")
    org = OrgUnit.objects.create(name="Count Org", slug="ecf-leave-count")
    emp = _employee(org, "C1", "Count Emp")
    lt = _leave_type()
    _leave(emp, lt, status="submitted")
    _leave(emp, lt, status="approved", start_date=date(2026, 5, 1), end_date=date(2026, 5, 2), days=Decimal("2.00"))

    ex = _executor(user)
    assert ex.entity_count("people.models.LeaveRecord", {"status": "submitted"}) >= 1
    assert ex.entity_count("people.models.LeaveRecord", {"status": "approved"}) >= 1
