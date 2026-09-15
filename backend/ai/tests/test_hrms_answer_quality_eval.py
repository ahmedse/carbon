"""Deterministic HRMS answer-quality eval gate (Nibras / payroll).

No LLM, no network. This module mirrors the in-process evaluator pattern used
by test_answer_quality_eval.py: build a KNOWN golden population, execute the
host path via CarbonHostExecutor, and apply pure checks.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from asgiref.sync import async_to_sync
from django.db.models import Count
from django.utils import timezone

from accounts.models import User
from ai.eval.checks import (
    assert_counts_match_db,
    assert_net_pay_grounded,
    assert_no_pay_figures_beyond_db,
    assert_scoped_empty_for_denied,
)
from ai.eval.golden_hrms import GOLDEN_HRMS_DATASET
from mdm.models import OrgUnit
from people.models import Employee, PayrollRun, PayslipLine, Position


def _executor(user: User):
    from ai.host_executor import CarbonHostExecutor

    return CarbonHostExecutor(
        db=None,
        instance_config={},
        user_token=f"inproc:nibras:{user.pk}",
        host_user_id=str(user.pk),
    )


def _anon_executor():
    from ai.host_executor import CarbonHostExecutor

    return CarbonHostExecutor(db=None, instance_config={}, user_token="", host_user_id="")


def _people_call(executor, endpoint: str, *, method: str = "GET", params=None, body=None):
    return async_to_sync(executor._people_in_process)(
        method=method,
        params=params or {},
        body=body or {},
        endpoint=endpoint,
    )


def _build_hrms_population() -> dict:
    orgs = {}
    for key, name in GOLDEN_HRMS_DATASET["orgs"]:
        orgs[key] = OrgUnit.objects.get_or_create(
            slug=f"eval-hrms-{key}",
            defaults={"name": name},
        )[0]

    positions = {}
    for key, org_key, code, title in GOLDEN_HRMS_DATASET["positions"]:
        positions[key] = Position.objects.get_or_create(
            org_unit=orgs[org_key],
            code=f"HRMS-{code}",
            defaults={"title": title},
        )[0]

    employees = {}
    for spec in GOLDEN_HRMS_DATASET["employees"]:
        employees[spec["no"]] = Employee.objects.create(
            org_unit=orgs[spec["org"]],
            employee_no=spec["no"],
            full_name=spec["name"],
            position=positions[spec["position"]],
            basic_salary=Decimal(spec["basic_salary"]),
            is_active=spec["is_active"],
        )

    run_spec = GOLDEN_HRMS_DATASET["payroll_run"]
    payroll_run = PayrollRun.objects.create(
        org_unit=orgs[run_spec["org"]],
        period_start=date.fromisoformat(run_spec["period_start"]),
        period_end=date.fromisoformat(run_spec["period_end"]),
        status=run_spec["status"],
        committed_at=timezone.now() if run_spec["status"] == "committed" else None,
    )

    for line in GOLDEN_HRMS_DATASET["payslip_lines"]:
        PayslipLine.objects.create(
            payroll_run=payroll_run,
            employee=employees[line["employee_no"]],
            line_type=line["line_type"],
            amount=Decimal(line["amount"]),
            rule_id=line["rule_id"],
            rule_version=line["rule_version"],
            inputs={},
        )

    return {
        "orgs": orgs,
        "positions": positions,
        "employees": employees,
        "payroll_run": payroll_run,
    }


def _counts_breakdown_from_rows(rows: list[dict]) -> list[dict]:
    by_employee: dict[str, int] = {}
    for row in rows:
        key = str(row["employee"])
        by_employee[key] = by_employee.get(key, 0) + 1
    return [{"label": k, "count": v} for k, v in sorted(by_employee.items())]


def _render_payroll_amounts(rows: list[dict]) -> str:
    parts = []
    for row in rows:
        parts.append(f"employee={row['employee']} {row['line_type']}={row['amount']}")
    return " | ".join(parts)


@pytest.mark.django_db(transaction=True)
def test_hrms_scenario_a_net_pay_grounding_and_counts(create_user, create_scoped_role):
    seeded = _build_hrms_population()
    user = create_user("hrms-payroll-viewer")
    create_scoped_role(user, "viewers_group", org_unit=seeded["orgs"]["hq"])

    result = _people_call(
        _executor(user),
        "carbon-api/people/payslip-lines",
        params={"payroll_run": seeded["payroll_run"].pk},
    )

    assert result["status_code"] == 200
    rows = result["data"]["results"]
    assert result["data"]["count"] == len(rows)

    assert_net_pay_grounded(rows)

    db_counts = {
        str(row["employee_id"]): row["count"]
        for row in (
            PayslipLine.objects.filter(payroll_run=seeded["payroll_run"])
            .values("employee_id")
            .annotate(count=Count("id"))
        )
    }
    assert_counts_match_db(_counts_breakdown_from_rows(rows), db_counts)


@pytest.mark.django_db(transaction=True)
def test_hrms_scenario_b_cbac_cross_employee_denied(create_user, create_scoped_role):
    seeded = _build_hrms_population()
    user = create_user("hrms-employee-viewer")
    create_scoped_role(user, "viewers_group", org_unit=seeded["orgs"]["hq"])

    result = _people_call(
        _executor(user),
        "carbon-api/people/payslip-lines",
        params={"payroll_run": seeded["payroll_run"].pk},
    )

    assert result["status_code"] == 200
    rows = result["data"]["results"]

    denied_employee_id = seeded["employees"]["HR900"].pk
    denied_rows = [r for r in rows if int(r["employee"]) == denied_employee_id]
    assert_scoped_empty_for_denied(denied_rows)


@pytest.mark.django_db(transaction=True)
def test_hrms_scenario_c_no_fabrication_subset_of_db(create_user, create_scoped_role):
    seeded = _build_hrms_population()
    user = create_user("hrms-no-fabrication")
    create_scoped_role(user, "viewers_group", org_unit=seeded["orgs"]["hq"])

    result = _people_call(
        _executor(user),
        "carbon-api/people/payslip-lines",
        params={"payroll_run": seeded["payroll_run"].pk},
    )

    assert result["status_code"] == 200
    rows = result["data"]["results"]

    rendered = _render_payroll_amounts(rows)
    db_rows = list(
        PayslipLine.objects.filter(payroll_run=seeded["payroll_run"])
        .values("employee_id", "line_type", "amount")
    )
    assert_no_pay_figures_beyond_db(rendered, db_rows)


@pytest.mark.django_db(transaction=True)
def test_hrms_unauthenticated_returns_401():
    result = _people_call(
        _anon_executor(),
        "carbon-api/people/payslip-lines",
        params={"payroll_run": 999999},
    )
    assert result["status_code"] == 401
