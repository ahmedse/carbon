# Associated pay on the payslip, retro identity, and one committed mixed month.
# Rule version 2026.1 rows created here are not the seeded historical rules,
# and this module does not update them after insert.

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from people.models import (
    AttendanceRecord,
    CompensationComponent,
    ComplianceRule,
    Employee,
    EmployeeCompensation,
    LeaveEntitlement,
    LeaveRecord,
    LieuDay,
    Loan,
    PayrollRun,
    PayslipLine,
)
from people.payroll_service import PayrollRunService, PayrollServiceError
from people.tests.ref_helpers import ensure_ref
from people.validation import validate_run

User = get_user_model()
START = date(2026, 8, 1)
END = date(2026, 8, 31)


def _component(code):
    row, _ = CompensationComponent.objects.get_or_create(
        code=code,
        defaults={"name": code, "direction": "earning", "is_eosi_base": code == "basic"},
    )
    return row


def _pay(employee, amount, *, code="basic"):
    EmployeeCompensation.objects.create(
        employee=employee,
        component=_component(code),
        amount=Decimal(amount),
        frequency="monthly",
        effective_start=date(2020, 1, 1),
        is_verified=True,
    )


def _employee(org, number, salary, *, kuwaitization=False, joined=date(2020, 1, 1), pifss=None, reason=""):
    employee = Employee.objects.create(
        org_unit=org,
        employee_no=number,
        full_name=number,
        basic_salary=Decimal("9999.000"),
        join_date=joined,
        kuwaitization=kuwaitization,
        pifss_registered=pifss,
        separation_reason=reason,
    )
    _pay(employee, salary)
    return employee


def _rule(rule_id, version, category, schema, *, effective=date(2026, 6, 1)):
    return ComplianceRule.objects.create(
        rule_id=rule_id,
        version=version,
        name=rule_id,
        category=ensure_ref("compliance_category", category),
        jurisdiction=ensure_ref("jurisdiction", "KW"),
        effective_date=effective,
        source_citation="sheet",
        is_authoritative=True,
        inputs_schema=schema,
    )


def _cited(formula, *, effect=None, line=None, source=None, extra=None, applies="all"):
    params = dict(formula.get("params") or {})
    if line:
        params["payslip_line"] = line
        params["payslip_effect"] = effect or "earning"
        params["fact_source"] = source
        params["applies_to"] = applies
    if extra:
        params.update(extra)
    return {
        "formula": {"type": formula["type"], "params": params},
        "regulation_ref": {"rule_id": "reg-sheet", "version": "2010.1"},
    }


def _regulation():
    return _rule(
        "reg-sheet",
        "2010.1",
        "other",
        {"floors": []},
        effective=date(2010, 1, 1),
    )


def _core_rules():
    _regulation()
    _rule(
        "sheet-gross",
        "2026.2",
        "payroll",
        _cited({"type": "sum", "params": {"components": ["basic"], "base_input": "basic"}}),
    )
    _rule(
        "sheet-net",
        "2026.2",
        "other",
        _cited({"type": "net_pay", "params": {}}),
    )
    _rule(
        "sheet-gosi",
        "2026.2",
        "gosi",
        _cited({
            "type": "fund_table",
            "params": {
                "salary_input": "gross_salary",
                "funds": [
                    {"code": "basic", "slice": "capped", "ceiling": "1500", "employee_rate": "0.05", "employer_rate": "0.10"},
                    {"code": "supplementary", "slice": "band", "floor": "1500", "width": "1250", "employee_rate": "0.05", "employer_rate": "0.10"},
                    {"code": "pension_increase", "slice": "capped", "ceiling": "2750", "employee_rate": "0.025", "employer_rate": "0.01"},
                    {"code": "financial_remuneration", "slice": "capped", "ceiling": "1500", "employee_rate": "0.025", "employer_rate": "0"},
                    {"code": "unemployment", "slice": "capped", "ceiling": "2750", "employee_rate": "0.005", "employer_rate": "0.005"},
                ],
            },
        }),
    )


def _leave(employee, code, days):
    LeaveRecord.objects.create(
        employee=employee,
        leave_type=ensure_ref("leave_type", code),
        start_date=START,
        end_date=END,
        days=Decimal(days),
        status="approved",
    )


def _actors():
    return (
        User.objects.create_user("slip_prep", password="x"),
        User.objects.create_user("slip_appr", password="x"),
    )


def _commit(run, prep, appr):
    service = PayrollRunService()
    service.compute(run, user=prep)
    validated = service.validate(run, user=prep)
    failed = [
        (row["rule_key"], row.get("sample_failures"))
        for row in validated.get("findings", [])
        if not row.get("passed", True)
    ]
    assert validated["status"] == "validated", failed
    committed = service.commit(run, user=appr)
    assert committed["status"] == "committed", committed
    run.refresh_from_db()
    return run


def _org():
    from mdm.models import OrgUnit
    return OrgUnit.objects.create(name="Slip", slug="slip-hq")


@pytest.mark.django_db
def test_leave_pay_refuses_before_the_published_service_minimum():
    org = _org()
    _core_rules()
    _rule(
        "sheet-leave",
        "2026.2",
        "leave",
        _cited(
            {"type": "scaled_rate", "params": {
                "base_inputs": ["total_salary"], "divisor": 26, "quantity_input": "leave_days",
            }},
            line="leave_pay",
            source="leave_days",
            extra={"leave_type_codes": ["annual"], "min_service_months": 6},
            applies="direct",
        ),
    )
    employee = _employee(org, "E-SHORT", "1000.000", joined=date(2026, 5, 1))
    _leave(employee, "annual", "3")
    run = PayrollRun.objects.create(org_unit=org, period_start=START, period_end=END)
    with pytest.raises(PayrollServiceError) as ctx:
        PayrollRunService().compute(run, user=_actors()[0])
    assert ctx.value.code == "service_gate"
    assert run.lines.count() == 0 or PayrollRun.objects.get(pk=run.pk).status == "draft"


@pytest.mark.django_db
def test_associated_lines_post_with_citation_cap_ladder_and_lieu_day():
    org = _org()
    _core_rules()
    _rule(
        "sheet-leave",
        "2026.2",
        "leave",
        _cited(
            {"type": "scaled_rate", "params": {
                "base_inputs": ["total_salary"], "divisor": 26, "quantity_input": "leave_days",
            }},
            line="leave_pay",
            source="leave_days",
            extra={"leave_type_codes": ["annual"], "min_service_months": 6},
        ),
    )
    _rule(
        "sheet-encash",
        "2026.2",
        "leave",
        _cited(
            {"type": "scaled_rate", "params": {
                "base_inputs": ["total_salary"], "divisor": 26, "quantity_input": "leave_days",
                "max_quantity": "60",
            }},
            line="leave_encashment",
            source="entitlement_balance",
            extra={"leave_type_codes": ["annual"], "require_separation": True},
        ),
    )
    _rule(
        "sheet-sick",
        "2026.2",
        "leave",
        _cited(
            {"type": "day_ladder", "params": {
                "base_inputs": ["total_salary"],
                "divisor": 26,
                "days_input": "sick_days",
                "bands": [
                    {"up_to_days": "15", "numerator": 1, "denominator": 1},
                    {"up_to_days": "10", "numerator": 3, "denominator": 4},
                    {"up_to_days": "10", "numerator": 1, "denominator": 2},
                    {"up_to_days": "10", "numerator": 1, "denominator": 4},
                    {"up_to_days": "30", "numerator": 0, "denominator": 1},
                ],
            }},
            line="sick_pay",
            source="leave_days",
            extra={"leave_type_codes": ["sick"]},
        ),
    )
    _rule(
        "sheet-notice",
        "2026.2",
        "other",
        _cited(
            {"type": "scaled_rate", "params": {
                "base_inputs": ["total_salary"], "divisor": 26, "quantity_input": "notice_days",
            }},
            line="notice_pay",
            source="leave_days",
            extra={"leave_type_codes": ["notice"]},
        ),
    )
    _rule(
        "sheet-friday",
        "2026.2",
        "overtime",
        _cited(
            {"type": "scaled_rate", "params": {
                "base_inputs": ["basic_salary"],
                "divisor": 26,
                "hours_per_day": 8,
                "multiplier": "1.5",
                "quantity_input": "ot_hours",
                "compensatory_days": "1",
            }},
            line="compensatory_pay",
            source="attendance_overtime",
            extra={"weekdays": [4]},
        ),
    )
    _rule(
        "sheet-loan",
        "2026.2",
        "other",
        _cited({
            "type": "loan_schedule",
            "params": {
                "method": "flat",
                "rate_is_annual": True,
                "rate_is_percent": False,
                "max_wage_fraction": "0.10",
            },
        }),
    )
    employee = _employee(org, "E-FULL", "800.000", reason="termination")
    _pay(employee, "200.000", code="housing")
    _leave(employee, "annual", "3")
    _leave(employee, "sick", "75")
    _leave(employee, "notice", "30")
    LeaveEntitlement.objects.create(
        employee=employee,
        year=2026,
        leave_type=ensure_ref("leave_type", "annual"),
        entitled_days=Decimal("100"),
        used_days=Decimal("0"),
    )
    AttendanceRecord.objects.create(
        employee=employee,
        date=date(2026, 8, 7),
        hours_worked=Decimal("8"),
        overtime_hours=Decimal("6"),
        status="present",
    )
    Loan.objects.create(
        employee=employee,
        loan_type=ensure_ref("loan_type", "advance"),
        principal=Decimal("1200.000"),
        interest_rate=Decimal("0"),
        term_months=12,
        start_date=START,
        status="active",
    )
    prep, appr = _actors()
    run = _commit(
        PayrollRun.objects.create(org_unit=org, period_start=START, period_end=END),
        prep,
        appr,
    )
    lines = {row.line_type.code: row for row in run.lines.select_related("line_type")}
    assert lines["leave_pay"].amount == Decimal("115.385")
    assert lines["leave_encashment"].amount == Decimal("2307.692")
    assert lines["sick_pay"].amount == Decimal("1153.846")
    assert lines["notice_pay"].amount == Decimal("1153.846")
    assert lines["compensatory_pay"].amount == Decimal("34.615")
    assert lines["loan_installment"].amount == Decimal("100.000")
    for row in run.lines.all():
        assert row.inputs["regulation_rule_id"] == "reg-sheet"
        assert row.inputs["regulation_version"] == "2010.1"
        assert row.rule_id
        assert row.rule_version
    lieu = LieuDay.objects.get(payroll_run=run)
    assert lieu.days == Decimal("1")
    assert lieu.payslip_line_id == lines["compensatory_pay"].id
    net = lines["net"].amount
    earnings = sum(
        row.amount for row in run.lines.all() if (row.inputs or {}).get("effect") == "earning"
    )
    assert net == Decimal("1000.000") + earnings - Decimal("100.000")


@pytest.mark.django_db
def test_loan_above_published_fraction_is_refused_without_rewriting_principal():
    org = _org()
    _core_rules()
    _rule(
        "sheet-loan-tight",
        "2026.2",
        "other",
        _cited({
            "type": "loan_schedule",
            "params": {
                "method": "flat",
                "rate_is_annual": True,
                "rate_is_percent": False,
                "max_wage_fraction": "0.10",
            },
        }),
    )
    employee = _employee(org, "E-LOAN", "1000.000")
    loan = Loan.objects.create(
        employee=employee,
        loan_type=ensure_ref("loan_type", "advance"),
        principal=Decimal("1200.012"),
        interest_rate=Decimal("0"),
        term_months=12,
        start_date=START,
        status="active",
    )
    run = PayrollRun.objects.create(org_unit=org, period_start=START, period_end=END)
    with pytest.raises(PayrollServiceError):
        PayrollRunService().compute(run, user=_actors()[0])
    loan.refresh_from_db()
    assert loan.principal == Decimal("1200.012")
    assert loan.term_months == 12


@pytest.mark.django_db
def test_missing_cited_regulation_fails_validation():
    org = _org()
    _core_rules()
    employee = _employee(org, "E-CITE", "1000.000")
    prep, _appr = _actors()
    run = PayrollRun.objects.create(org_unit=org, period_start=START, period_end=END)
    PayrollRunService().compute(run, user=prep)
    ComplianceRule.objects.filter(rule_id="reg-sheet", version="2010.1").delete()
    findings = validate_run(run)
    citation = next(row for row in findings if row["rule_key"] == "regulation_citation")
    assert citation["passed"] is False
    assert any("2010.1" in sample for sample in citation["sample_failures"])


@pytest.mark.django_db
def test_retro_has_its_own_period_and_does_not_rewrite_the_committed_run():
    org = _org()
    frozen = _rule(
        "frozen-gross",
        "2026.1",
        "payroll",
        {"formula": {"type": "sum", "params": {"components": ["basic"], "base_input": "basic"}}},
        effective=date(2026, 1, 1),
    )
    _rule(
        "frozen-net",
        "2026.1",
        "other",
        {"formula": {"type": "net_pay", "params": {}}},
        effective=date(2026, 1, 1),
    )
    frozen_bytes = dict(frozen.inputs_schema)
    employee = _employee(org, "E-RETRO", "1000.000")
    prep, appr = _actors()
    source = _commit(
        PayrollRun.objects.create(
            org_unit=org, period_start=START, period_end=END,
        ),
        prep,
        appr,
    )
    source_amounts = list(
        source.lines.order_by("id").values_list("line_type__code", "amount", "rule_id", "rule_version")
    )
    with pytest.raises(PayrollServiceError):
        PayrollRunService().compute(source, user=prep)
    service = PayrollRunService()
    with pytest.raises(PayrollServiceError):
        service.open_retro(source, period_start=START, period_end=END)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PayrollRun.objects.create(
                org_unit=org, period_start=START, period_end=END, status="draft",
            )
    _regulation()
    _rule(
        "sheet-leave-later",
        "2026.3",
        "leave",
        _cited(
            {"type": "scaled_rate", "params": {
                "base_inputs": ["total_salary"], "divisor": 26, "quantity_input": "leave_days",
            }},
            line="leave_pay",
            source="leave_days",
            extra={"leave_type_codes": ["annual"]},
        ),
        effective=date(2026, 9, 1),
    )
    _leave(employee, "annual", "3")
    retro = service.open_retro(
        source, period_start=date(2026, 9, 15), period_end=date(2026, 9, 15),
    )
    assert retro.kind == "retro"
    assert retro.source_run_id == source.id
    assert retro.covers_start == START
    _commit(retro, prep, appr)
    leave = retro.lines.get(line_type__code="leave_pay")
    assert leave.amount == Decimal("115.385")
    assert leave.rule_version == "2026.3"
    source.refresh_from_db()
    assert list(
        source.lines.order_by("id").values_list("line_type__code", "amount", "rule_id", "rule_version")
    ) == source_amounts
    frozen.refresh_from_db()
    assert frozen.version == "2026.1"
    assert frozen.inputs_schema == frozen_bytes


@pytest.mark.django_db
def test_committed_mixed_month_matches_goldens_and_leaves_2026_1_in_place():
    org = _org()
    frozen = _rule(
        "frozen-gross",
        "2026.1",
        "payroll",
        {"formula": {"type": "sum", "params": {"components": ["basic"], "base_input": "basic"}}},
        effective=date(2026, 1, 1),
    )
    _rule(
        "frozen-net",
        "2026.1",
        "other",
        {"formula": {"type": "net_pay", "params": {}}},
        effective=date(2026, 1, 1),
    )
    frozen_bytes = dict(frozen.inputs_schema)
    earlier = _employee(org, "E-OLD", "780.000")
    prep, appr = _actors()
    old_run = _commit(
        PayrollRun.objects.create(
            org_unit=org,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
        ),
        prep,
        appr,
    )
    old_lines = list(old_run.lines.order_by("id").values_list("amount", "rule_version"))
    _core_rules()
    _rule(
        "sheet-leave-direct",
        "2026.2",
        "leave",
        _cited(
            {"type": "scaled_rate", "params": {
                "base_inputs": ["total_salary"], "divisor": 26, "quantity_input": "leave_days",
            }},
            line="leave_pay",
            source="leave_days",
            extra={"leave_type_codes": ["annual"], "min_service_months": 6},
            applies="direct",
        ),
    )
    _rule(
        "sheet-absence-kw",
        "2026.2",
        "other",
        _cited(
            {"type": "scaled_rate", "params": {
                "base_inputs": ["total_salary"],
                "divisor": 21,
                "quantity_input": "absent_days",
                "class_input": "absence_class",
                "billable_classes": ["unjustified"],
            }},
            line="absence_deduction",
            effect="deduction",
            source="attendance_absence",
            applies="kuwaitization",
        ),
    )
    direct = _employee(org, "E-DIRECT", "1000.000")
    kw = _employee(org, "E-KW", "1000.000", kuwaitization=True)
    kuwaiti = _employee(org, "E-PIFSS", "2000.000", kuwaitization=True, pifss=True)
    _leave(direct, "annual", "3")
    for offset in range(3):
        AttendanceRecord.objects.create(
            employee=kw,
            date=date(2026, 8, 2 + offset),
            hours_worked=Decimal("0"),
            overtime_hours=Decimal("0"),
            status="absent",
            absence_class="unjustified",
        )
    AttendanceRecord.objects.create(
        employee=kw,
        date=date(2026, 8, 10),
        hours_worked=Decimal("0"),
        overtime_hours=Decimal("0"),
        status="absent",
        absence_class="justified",
    )
    mixed = _commit(
        PayrollRun.objects.create(org_unit=org, period_start=START, period_end=END),
        prep,
        appr,
    )
    direct_lines = {row.line_type.code: row for row in mixed.lines.filter(employee=direct).select_related("line_type")}
    kw_lines = {row.line_type.code: row for row in mixed.lines.filter(employee=kw).select_related("line_type")}
    ku_lines = {row.line_type.code: row for row in mixed.lines.filter(employee=kuwaiti).select_related("line_type")}
    assert direct_lines["leave_pay"].amount == Decimal("115.385")
    assert "gosi" not in direct_lines
    assert kw_lines["absence_deduction"].amount == Decimal("142.857")
    assert "absence_deduction" not in ku_lines
    assert ku_lines["gosi"].inputs["employee_share"] == "197.500"
    assert ku_lines["gosi"].inputs["employer_share"] == "230.000"
    assert kw_lines["gosi"].inputs["employee_share"] == "105.000"
    assert kw_lines["gosi"].inputs["employer_share"] == "115.000"
    for row in mixed.lines.all():
        assert row.inputs["regulation_rule_id"] == "reg-sheet"
        assert row.inputs["regulation_version"] == "2010.1"
        assert row.rule_version == "2026.2"
    frozen.refresh_from_db()
    assert frozen.inputs_schema == frozen_bytes
    assert frozen.version == "2026.1"
    old_run.refresh_from_db()
    assert old_run.status == "committed"
    assert list(old_run.lines.order_by("id").values_list("amount", "rule_version")) == old_lines
    assert earlier.employee_no == "E-OLD"


@pytest.mark.django_db
def test_period_end_selects_the_rule_already_in_effect_and_a_committed_run_stays():
    org = _org()
    frozen = _rule(
        "period-gross",
        "2026.1",
        "payroll",
        {"formula": {"type": "sum", "params": {"components": ["basic"], "base_input": "basic"}}},
        effective=date(2026, 1, 1),
    )
    _rule(
        "period-gross-next",
        "2026.2",
        "payroll",
        {"formula": {"type": "sum", "params": {"components": ["basic"], "base_input": "basic"}}},
        effective=date(2026, 10, 1),
    )
    _rule(
        "period-net",
        "2026.1",
        "other",
        {"formula": {"type": "net_pay", "params": {}}},
        effective=date(2026, 1, 1),
    )
    _rule(
        "period-net-next",
        "2026.2",
        "other",
        {"formula": {"type": "net_pay", "params": {}}},
        effective=date(2026, 10, 1),
    )
    frozen_bytes = dict(frozen.inputs_schema)
    _employee(org, "E-PERIOD", "1000.000")
    prep, appr = _actors()
    september = _commit(
        PayrollRun.objects.create(
            org_unit=org, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30),
        ),
        prep, appr,
    )
    sept_lines = list(
        september.lines.order_by("id").values_list("line_type__code", "rule_id", "rule_version", "amount")
    )
    assert sept_lines
    assert {row[2] for row in sept_lines} == {"2026.1"}
    october = _commit(
        PayrollRun.objects.create(
            org_unit=org, period_start=date(2026, 10, 1), period_end=date(2026, 10, 31),
        ),
        prep, appr,
    )
    oct_versions = set(october.lines.values_list("rule_version", flat=True))
    assert oct_versions == {"2026.2"}
    with pytest.raises(PayrollServiceError):
        PayrollRunService().compute(september, user=prep)
    september.refresh_from_db()
    assert september.status == "committed"
    assert list(
        september.lines.order_by("id").values_list("line_type__code", "rule_id", "rule_version", "amount")
    ) == sept_lines
    frozen.refresh_from_db()
    assert frozen.version == "2026.1"
    assert frozen.inputs_schema == frozen_bytes
