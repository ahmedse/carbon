# The publish gate reads regulation_packs/kw. A missing version fails.
# A later pack version does not rewrite a run that cited the previous one.

import inspect
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from people.models import (
    CompensationComponent,
    ComplianceRule,
    Employee,
    EmployeeCompensation,
    PayrollRun,
)
from people.payroll_service import PayrollRunService
from people.policy_service import PolicyTransitionError, create_draft, publish, submit
from people.regulation_pack import load_pack
from people.tests.ref_helpers import ensure_ref

User = get_user_model()


def _actors(prefix):
    return (
        User.objects.create_user(f"{prefix}_prep", password="x"),
        User.objects.create_user(f"{prefix}_appr", password="x"),
    )


def _tenant(drafter, *, version, cited, parameters, funds=None, rule_id="tenant-pack", cases=None):
    formula = {"type": "multiply", "params": {"a": "a", "b": "b"}}
    if cases is None:
        cases = [{"inputs": {"a": "2", "b": "3"}, "expected": "6.000"}]
    if funds is not None:
        formula = {
            "type": "fund_table",
            "params": {"salary_input": "insured_salary", "funds": funds},
        }
    return create_draft({
        "rule_id": rule_id,
        "version": version,
        "name": rule_id,
        "category": "other",
        "jurisdiction": "KW",
        "effective_date": "2026-08-01",
        "source_citation": "tenant",
        "inputs_schema": {
            "formula": formula,
            "parameters": parameters,
            "regulation_ref": {"pack": "kw", "version": cited},
        },
        "test_cases": cases,
    }, drafter)


def _through_review(rule, drafter, publisher):
    submit(rule, drafter)
    return publish(rule, publisher)


@pytest.fixture(autouse=True)
def _refs(db):
    ensure_ref("compliance_category", "other")
    ensure_ref("compliance_category", "payroll")
    ensure_ref("jurisdiction", "KW")


def test_publish_loads_the_pack_file_not_a_python_constant():
    loaded = load_pack("kw", "2010.1")
    friday = next(row for row in loaded["floors"] if row["field"] == "friday_multiplier")
    assert friday["value"] == "1.5"
    assert "1.5" not in inspect.getsource(publish.__globals__["floor_report"])
    drafter, publisher = _actors("pack_floor")
    low = _tenant(
        drafter,
        version="2026.8",
        cited="2010.1",
        parameters={"friday_multiplier": "1.25", "holiday_multiplier": "2.0"},
    )
    submit(low, drafter)
    with pytest.raises(PolicyTransitionError) as refused:
        publish(low, publisher)
    assert refused.value.code == "floor_failed"
    high = _tenant(
        drafter,
        version="2026.9",
        cited="2010.1",
        parameters={"friday_multiplier": "1.5", "holiday_multiplier": "2.0"},
        rule_id="tenant-pack-ok",
    )
    published = _through_review(high, drafter, publisher)
    assert published.lifecycle == "authoritative"


def test_missing_pack_version_cannot_publish():
    drafter, publisher = _actors("pack_miss")
    rule = _tenant(
        drafter,
        version="2026.8",
        cited="1999.9",
        parameters={"friday_multiplier": "1.5"},
        rule_id="tenant-missing-pack",
    )
    submit(rule, drafter)
    with pytest.raises(PolicyTransitionError) as refused:
        publish(rule, publisher)
    assert refused.value.code == "regulation_missing"


def test_publish_reads_the_pack_fund_table():
    loaded = load_pack("kw", "2010.1")
    funds = [dict(row) for row in loaded["funds"]]
    drafter, publisher = _actors("pack_fund")
    short = [dict(row) for row in funds]
    short[0]["employee_rate"] = "0.04"
    low = _tenant(
        drafter,
        version="2026.8",
        cited="2010.1",
        parameters={"friday_multiplier": "1.5"},
        funds=short,
        rule_id="tenant-fund-low",
        cases=[{"inputs": {"insured_salary": "2000"}, "expected": "412.500"}],
    )
    submit(low, drafter)
    with pytest.raises(PolicyTransitionError) as refused:
        publish(low, publisher)
    assert refused.value.code == "floor_failed"
    assert any(row.get("field") == "basic.employee_rate" and row.get("passed") is False for row in refused.value.errors)
    ok = _tenant(
        drafter,
        version="2026.9",
        cited="2010.1",
        parameters={"friday_multiplier": "1.5"},
        funds=funds,
        rule_id="tenant-fund-ok",
        cases=[{"inputs": {"insured_salary": "2000"}, "expected": "427.500"}],
    )
    published = _through_review(ok, drafter, publisher)
    assert published.lifecycle == "authoritative"


def test_later_pack_version_does_not_rewrite_a_committed_run():
    drafter, publisher = _actors("pack_hist")
    kept = _through_review(_tenant(
        drafter,
        version="2026.8",
        cited="2010.1",
        parameters={"friday_multiplier": "1.5", "holiday_multiplier": "2.0"},
        rule_id="tenant-stays",
    ), drafter, publisher)
    from mdm.models import OrgUnit

    org = OrgUnit.objects.create(name="Pack", slug="pack-hq")
    component, _created = CompensationComponent.objects.get_or_create(
        code="basic",
        defaults={"name": "basic", "direction": "earning"},
    )
    employee = Employee.objects.create(
        org_unit=org,
        employee_no="E-PACK",
        full_name="E-PACK",
        basic_salary=Decimal("780.000"),
        join_date=date(2020, 1, 1),
    )
    EmployeeCompensation.objects.create(
        employee=employee,
        component=component,
        amount=Decimal("780.000"),
        frequency="monthly",
        effective_start=date(2020, 1, 1),
        is_verified=True,
    )
    citation = {"pack": "kw", "version": "2010.1"}
    ComplianceRule.objects.create(
        rule_id="pack-gross",
        version="2099.1",
        name="pack gross",
        category=ensure_ref("compliance_category", "payroll"),
        jurisdiction=ensure_ref("jurisdiction", "KW"),
        effective_date=date(2026, 8, 1),
        source_citation="tenant",
        is_authoritative=True,
        inputs_schema={
            "formula": {"type": "sum", "params": {"components": ["basic"], "base_input": "basic"}},
            "regulation_ref": citation,
        },
    )
    ComplianceRule.objects.create(
        rule_id="pack-net",
        version="2099.1",
        name="pack net",
        category=ensure_ref("compliance_category", "other"),
        jurisdiction=ensure_ref("jurisdiction", "KW"),
        effective_date=date(2026, 8, 1),
        source_citation="tenant",
        is_authoritative=True,
        inputs_schema={
            "formula": {"type": "net_pay", "params": {}},
            "regulation_ref": citation,
        },
    )
    service = PayrollRunService()
    run = PayrollRun.objects.create(
        org_unit=org,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )
    service.compute(run, user=drafter)
    validated = service.validate(run, user=drafter)
    assert validated["status"] == "validated", validated
    service.commit(run, user=publisher)
    before = list(run.lines.order_by("id").values_list(
        "line_type__code", "amount", "inputs",
    ))
    assert before
    assert all(row[2]["regulation_pack"] == "kw" for row in before)
    assert all(row[2]["regulation_version"] == "2010.1" for row in before)
    later = _tenant(
        drafter,
        version="2026.9",
        cited="2010.2",
        parameters={"friday_multiplier": "1.5", "holiday_multiplier": "2.0"},
        rule_id="tenant-later",
    )
    submit(later, drafter)
    with pytest.raises(PolicyTransitionError) as refused:
        publish(later, publisher)
    assert refused.value.code == "floor_failed"
    kept.refresh_from_db()
    assert kept.lifecycle == "authoritative"
    assert kept.inputs_schema["regulation_ref"]["version"] == "2010.1"
    run.refresh_from_db()
    assert run.status == "committed"
    assert list(run.lines.order_by("id").values_list(
        "line_type__code", "amount", "inputs",
    )) == before
