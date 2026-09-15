"""Deterministic HRMS evaluation report runner.

Usage:
    DJANGO_BRAND=nibras python -m ai.eval.hrms_report

Runs three deterministic scenarios (no LLM, no network) and prints PASS/FAIL
per scenario plus an aggregate summary. Exits non-zero if any scenario fails.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date
from decimal import Decimal

from asgiref.sync import async_to_sync
from django.utils import timezone

from ai.eval.checks import (
    assert_counts_match_db,
    assert_net_pay_grounded,
    assert_no_pay_figures_beyond_db,
    assert_scoped_empty_for_denied,
)
from ai.eval.golden_hrms import GOLDEN_HRMS_DATASET


def _bootstrap_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()


def _executor(user):
    from ai.host_executor import CarbonHostExecutor

    return CarbonHostExecutor(
        db=None,
        instance_config={},
        user_token=f"inproc:nibras:{user.pk}",
        host_user_id=str(user.pk),
    )


def _people_call(executor, endpoint: str, *, method: str = "GET", params=None, body=None):
    return async_to_sync(executor._people_in_process)(
        method=method,
        params=params or {},
        body=body or {},
        endpoint=endpoint,
    )


def _counts_breakdown_from_rows(rows: list[dict]) -> list[dict]:
    by_employee: dict[str, int] = {}
    for row in rows:
        key = str(row["employee"])
        by_employee[key] = by_employee.get(key, 0) + 1
    return [{"label": key, "count": count} for key, count in sorted(by_employee.items())]


def _render_payroll_amounts(rows: list[dict]) -> str:
    return " | ".join(
        f"employee={row['employee']} {row['line_type']}={row['amount']}" for row in rows
    )


def _build_population() -> dict:
    from mdm.models import OrgUnit
    from people.models import Employee, PayrollRun, PayslipLine, Position

    suffix = uuid.uuid4().hex[:8]

    orgs = {}
    for key, name in GOLDEN_HRMS_DATASET["orgs"]:
        orgs[key] = OrgUnit.objects.create(
            slug=f"eval-hrms-{suffix}-{key}",
            name=f"{name} {suffix}",
        )

    positions = {}
    for key, org_key, code, title in GOLDEN_HRMS_DATASET["positions"]:
        positions[key] = Position.objects.create(
            org_unit=orgs[org_key],
            code=f"HRMS-{suffix}-{code}",
            title=title,
        )

    employees = {}
    for spec in GOLDEN_HRMS_DATASET["employees"]:
        employees[spec["no"]] = Employee.objects.create(
            org_unit=orgs[spec["org"]],
            employee_no=f"{spec['no']}-{suffix}",
            full_name=spec["name"],
            position=positions[spec["position"]],
            basic_salary=Decimal(spec["basic_salary"]),
            is_active=spec["is_active"],
        )

    run_spec = GOLDEN_HRMS_DATASET["payroll_run"]
    run = PayrollRun.objects.create(
        org_unit=orgs[run_spec["org"]],
        period_start=date.fromisoformat(run_spec["period_start"]),
        period_end=date.fromisoformat(run_spec["period_end"]),
        status=run_spec["status"],
        committed_at=timezone.now() if run_spec["status"] == "committed" else None,
    )

    for line in GOLDEN_HRMS_DATASET["payslip_lines"]:
        PayslipLine.objects.create(
            payroll_run=run,
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
        "payroll_run": run,
        "suffix": suffix,
    }


def _make_scoped_user(org):
    from accounts.models import ScopedRole, User
    from django.contrib.auth.models import Group

    suffix = uuid.uuid4().hex[:8]
    user = User.objects.create_user(username=f"hrms-eval-{suffix}", password="secret123")
    group, _ = Group.objects.get_or_create(name="viewers_group")
    ScopedRole.objects.create(user=user, group=group, org_unit=org, is_active=True)
    return user


def _scenario_a(seed) -> None:
    from django.db.models import Count
    from people.models import PayslipLine

    user = _make_scoped_user(seed["orgs"]["hq"])
    result = _people_call(
        _executor(user),
        "carbon-api/people/payslip-lines",
        params={"payroll_run": seed["payroll_run"].pk},
    )
    assert result["status_code"] == 200, result
    rows = result["data"]["results"]

    assert_net_pay_grounded(rows)

    db_counts = {
        str(row["employee_id"]): row["count"]
        for row in (
            PayslipLine.objects.filter(payroll_run=seed["payroll_run"])
            .values("employee_id")
            .annotate(count=Count("id"))
        )
    }
    assert_counts_match_db(_counts_breakdown_from_rows(rows), db_counts)


def _scenario_b(seed) -> None:
    user = _make_scoped_user(seed["orgs"]["hq"])
    result = _people_call(
        _executor(user),
        "carbon-api/people/payslip-lines",
        params={"payroll_run": seed["payroll_run"].pk},
    )
    assert result["status_code"] == 200, result
    rows = result["data"]["results"]

    denied_employee_id = seed["employees"]["HR900"].pk
    denied_rows = [row for row in rows if int(row["employee"]) == denied_employee_id]
    assert_scoped_empty_for_denied(denied_rows)


def _scenario_c(seed) -> None:
    from people.models import PayslipLine

    user = _make_scoped_user(seed["orgs"]["hq"])
    result = _people_call(
        _executor(user),
        "carbon-api/people/payslip-lines",
        params={"payroll_run": seed["payroll_run"].pk},
    )
    assert result["status_code"] == 200, result
    rows = result["data"]["results"]

    rendered = _render_payroll_amounts(rows)
    db_rows = list(
        PayslipLine.objects.filter(payroll_run=seed["payroll_run"])
        .values("employee_id", "line_type", "amount")
    )
    assert_no_pay_figures_beyond_db(rendered, db_rows)


def _teardown(seed) -> None:
    from people.models import Employee, PayrollRun, Position

    PayrollRun.objects.filter(pk=seed["payroll_run"].pk).delete()
    Employee.objects.filter(pk__in=[e.pk for e in seed["employees"].values()]).delete()
    Position.objects.filter(pk__in=[p.pk for p in seed["positions"].values()]).delete()
    for org in seed["orgs"].values():
        org.delete()


def main() -> int:
    _bootstrap_django()

    seed = _build_population()
    scenarios = [
        ("Scenario A (net-pay grounding)", _scenario_a),
        ("Scenario B (CBAC cross-employee deny)", _scenario_b),
        ("Scenario C (no fabrication)", _scenario_c),
    ]

    passed = 0
    total = len(scenarios)

    try:
        for label, fn in scenarios:
            try:
                fn(seed)
                passed += 1
                print(f"{label}: PASS")
            except Exception as exc:  # noqa: BLE001
                print(f"{label}: FAIL - {exc}")
        print(f"HRMS eval: {passed}/{total} passed")
        return 0 if passed == total else 1
    finally:
        _teardown(seed)


if __name__ == "__main__":
    raise SystemExit(main())
