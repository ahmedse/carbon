"""B1 — leave/loan list endpoints honour employee filter + identity enrichment."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from accounts.models import User
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee, LeaveEntitlement

from ai.host_executor import (
    _annotate_employee_identity,
    _employee_param_from_query,
    _filter_qs_by_employee_param,
    _people_execute,
)


@pytest.fixture
def leave_fixture(db):
    user = User.objects.create_superuser(username="b1-leave", password="x")
    org = OrgUnit.objects.create(name="B1 Org", slug="b1-org")
    target = Employee.objects.create(
        org_unit=org,
        employee_no="1416",
        full_name="Eslam Mohamed",
        basic_salary=Decimal("1000.000"),
        join_date=date(2026, 1, 1),
        is_active=True,
    )
    other = Employee.objects.create(
        org_unit=org,
        employee_no="3330",
        full_name="Other Person",
        basic_salary=Decimal("1000.000"),
        join_date=date(2026, 1, 1),
        is_active=True,
    )
    rs, _ = ReferenceSet.objects.get_or_create(
        name="leave_type", defaults={"slug": "leave-type"},
    )
    annual, _ = ReferenceValue.objects.get_or_create(
        reference_set=rs,
        code="annual",
        defaults={"label": "Annual", "is_active": True, "sort_order": 1},
    )
    LeaveEntitlement.objects.create(
        employee=target, year=2026, leave_type=annual, entitled_days=30, used_days=0,
    )
    LeaveEntitlement.objects.create(
        employee=other, year=2026, leave_type=annual, entitled_days=20, used_days=0,
    )
    return user, target, other


def test_employee_param_aliases():
    assert _employee_param_from_query({"employee_no": "1416"}) == "1416"
    assert _employee_param_from_query({"employee": 2}) == "2"
    assert _employee_param_from_query({}) == ""


@pytest.mark.django_db
def test_filter_qs_by_employee_no(leave_fixture):
    _, target, other = leave_fixture
    qs = LeaveEntitlement.objects.all()
    filtered = _filter_qs_by_employee_param(qs, {"employee_no": "1416"})
    assert filtered.count() == 1
    assert filtered.get().employee_id == target.pk
    by_pk = _filter_qs_by_employee_param(qs, {"employee": other.pk})
    assert by_pk.count() == 1
    assert by_pk.get().employee_id == other.pk


@pytest.mark.django_db
def test_leave_entitlements_filtered_and_annotated(leave_fixture):
    user, target, _other = leave_fixture
    result = _people_execute(
        user, "leave-entitlements", None, None, "GET",
        {"employee_no": "1416"}, {},
    )
    assert result["status_code"] == 200
    data = result["data"]
    assert data["total"] == 1
    assert data["filtered_by_employee"] == "1416"
    assert not data.get("truncated")
    row = data["results"][0]
    assert row["employee"] == target.pk
    assert row["employee_no"] == "1416"
    assert row["employee_name"] == "Eslam Mohamed"
    # Must not invent bare "Employee {pk}" — identity fields present.
    assert "Employee " not in str(row.get("employee_name", ""))


@pytest.mark.django_db
def test_annotate_employee_identity_adds_fields(leave_fixture):
    _, target, _ = leave_fixture
    rows = [{"id": 1, "employee": target.pk, "leave_type": "annual"}]
    out = _annotate_employee_identity(rows, None)
    assert out[0]["employee_no"] == "1416"
    assert out[0]["employee_name"] == "Eslam Mohamed"
