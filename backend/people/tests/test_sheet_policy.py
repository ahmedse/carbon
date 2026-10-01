# Sheet goldens for a new rule version. Version 2026.1 is not edited.
# Money is ROUND_HALF_UP to 0.001. Law numbers live in the rule JSON.

from datetime import date
from decimal import Decimal

import pytest

from people.calculation_engine import (
    MissingPolicyFactError,
    calculate,
    calculate_classified,
    calculate_eosi,
    calculate_gosi,
)
from people.models import (
    CompensationComponent,
    ComplianceRule,
    Employee,
    EmployeeCompensation,
    PayrollRun,
)
from people.payroll_service import PayrollRunService, PayrollServiceError, loan_within_policy
from people.tests.ref_helpers import ensure_ref

_Q = Decimal("0.001")


def _rule(rule_id, schema, *, version="2026.2"):
    return ComplianceRule.objects.create(
        rule_id=rule_id,
        version=version,
        name=rule_id,
        category=ensure_ref("compliance_category", "other"),
        jurisdiction=ensure_ref("jurisdiction", "KW"),
        effective_date=date(2026, 6, 1),
        inputs_schema=schema,
        is_authoritative=True,
        source_citation="sheet",
    )


def _scaled(divisor, *, hours=None, multiplier="1", quantity_input=None, base="total_salary", extra=None):
    params = {
        "base_inputs": [base],
        "divisor": divisor,
        "multiplier": multiplier,
    }
    if hours is not None:
        params["hours_per_day"] = hours
    if quantity_input:
        params["quantity_input"] = quantity_input
    else:
        params["quantity"] = "1"
    if extra:
        params.update(extra)
    return {"formula": {"type": "scaled_rate", "params": params}}


def _money(rule, inputs):
    return calculate(rule, inputs)["value"]


INDEMNITY = {
    "formula": {
        "type": "banded_fraction",
        "params": {
            "base_inputs": ["total_salary"],
            "years_input": "service_years",
            "divisor": 26,
            "base_kind": "eosi_components",
            "proration": {"days_input": "service_days", "basis": 365},
            "reason_input": "separation_reason",
            "tiers": [
                {"from_year": "0", "until_year": "5", "days_per_year": "15"},
                {"from_year": "5", "until_year": None, "months_per_year": "1"},
            ],
            "bands": [
                {"reason": "termination", "from_years": "0", "until_years": None, "numerator": 1, "denominator": 1},
                {"reason": "death", "from_years": "0", "until_years": None, "numerator": 1, "denominator": 1},
                {"reason": "resignation", "from_years": "0", "until_years": "3", "numerator": 0, "denominator": 1},
                {"reason": "resignation", "from_years": "3", "until_years": "5", "numerator": 1, "denominator": 2},
                {"reason": "resignation", "from_years": "5", "until_years": "10", "numerator": 2, "denominator": 3},
                {"reason": "resignation", "from_years": "10", "until_years": None, "numerator": 1, "denominator": 1},
            ],
            "cap_months": "18",
        },
    }
}

EXCESS = {
    "formula": {
        "type": "banded_fraction",
        "params": {
            **INDEMNITY["formula"]["params"],
            "excess_over": "1500",
            "excess_when_fact": "pifss_registered",
            "requires_facts": ["pifss_registered"],
        },
    }
}


def _indemnity(reason, years, salary="1000", **extra):
    inputs = {
        "total_salary": salary,
        "service_years": str(years),
        "separation_reason": reason,
    }
    inputs.update(extra)
    return inputs


@pytest.mark.django_db
def test_sheet_rates_leave_and_overtime_match_to_one_fil():
    daily_26 = _rule("sheet-daily-26", _scaled(26))
    daily_21 = _rule("sheet-daily-21", _scaled(21))
    hourly_26 = _rule("sheet-hourly-26", _scaled(26, hours=8))
    hourly_21 = _rule("sheet-hourly-21", _scaled(21, hours=8))
    leave = _rule("sheet-leave", _scaled(26, quantity_input="leave_days"))
    encash = _rule(
        "sheet-encash",
        _scaled(26, quantity_input="leave_days", extra={"max_quantity": "60"}),
    )
    assert _money(daily_26, {"total_salary": "1000"}) == Decimal("38.462")
    assert _money(daily_21, {"total_salary": "1000"}) == Decimal("47.619")
    assert _money(hourly_26, {"total_salary": "1000"}) == Decimal("4.808")
    assert _money(hourly_21, {"total_salary": "1000"}) == Decimal("5.952")
    assert _money(leave, {"total_salary": "1000", "leave_days": "3"}) == Decimal("115.385")
    assert _money(encash, {"total_salary": "1000", "leave_days": "20"}) == Decimal("769.231")
    assert _money(encash, {"total_salary": "1000", "leave_days": "100"}) == Decimal("2307.692")

    ot_day = _rule("sheet-ot-day", _scaled(26, hours=8, multiplier="1.25", quantity_input="ot_hours", base="basic_salary"))
    ot_friday = _rule(
        "sheet-ot-friday",
        _scaled(26, hours=8, multiplier="1.5", quantity_input="ot_hours", base="basic_salary", extra={"compensatory_days": 1}),
    )
    ot_holiday = _rule("sheet-ot-holiday", _scaled(26, hours=8, multiplier="2", quantity_input="ot_hours", base="basic_salary"))
    ot_kw = _rule("sheet-ot-kw", _scaled(21, hours=8, multiplier="1.25", quantity_input="ot_hours", base="basic_salary"))
    assert _money(ot_day, {"basic_salary": "800", "ot_hours": "2"}) == Decimal("9.615")
    friday = calculate(ot_friday, {"basic_salary": "800", "ot_hours": "6"})
    assert friday["value"] == Decimal("34.615")
    assert friday["lineage"]["compensatory_days"] == 1
    assert _money(ot_holiday, {"basic_salary": "800", "ot_hours": "6"}) == Decimal("46.154")
    # Derived Kuwaitization overtime golden: 800/21/8*1.25*2.
    assert _money(ot_kw, {"basic_salary": "800", "ot_hours": "2"}) == Decimal("11.905")


@pytest.mark.django_db
def test_indemnity_is_cumulative_and_uses_two_thirds_fraction():
    rule = _rule("sheet-indemnity", INDEMNITY, version="2026.3")
    assert _money(rule, _indemnity("termination", 8)) == Decimal("5884.615")
    assert _money(rule, _indemnity("resignation", 2)) == Decimal("0.000")
    assert _money(rule, _indemnity("resignation", 4)) == Decimal("1153.846")
    assert _money(rule, _indemnity("resignation", 8)) == Decimal("3923.077")
    assert _money(rule, _indemnity("resignation", 21)) == Decimal("18000.000")
    assert _money(rule, _indemnity("resignation", 5)) == Decimal("1923.077")
    assert _money(rule, _indemnity("resignation", 10)) == Decimal("7884.615")
    assert _money(rule, _indemnity("termination", 2, service_days="730")) == Decimal("1153.846")
    with pytest.raises(MissingPolicyFactError):
        calculate(rule, {"total_salary": "1000", "service_years": "8"})


@pytest.mark.django_db
def test_registered_excess_indemnity_refuses_when_the_fact_is_missing():
    rule = _rule("sheet-indemnity-excess", EXCESS, version="2026.3")
    with pytest.raises(MissingPolicyFactError) as ctx:
        calculate(rule, _indemnity("termination", 8, "2000"))
    assert ctx.value.fact == "pifss_registered"
    assert _money(
        rule, _indemnity("termination", 8, "2000", pifss_registered=True),
    ) == Decimal("2942.308")
    assert _money(
        rule, _indemnity("termination", 8, "1500", pifss_registered=True),
    ) == Decimal("0.000")
    assert _money(
        rule, _indemnity("termination", 8, "1000", pifss_registered=False),
    ) == Decimal("5884.615")


@pytest.mark.django_db
def test_absence_bills_only_the_class_the_rule_names():
    schema = _scaled(26, quantity_input="absent_days")
    schema["formula"]["params"]["class_input"] = "absence_class"
    schema["formula"]["params"]["billable_classes"] = ["unjustified"]
    direct = _rule("sheet-absence-26", schema)
    schema_21 = _scaled(21, quantity_input="absent_days")
    schema_21["formula"]["params"]["class_input"] = "absence_class"
    schema_21["formula"]["params"]["billable_classes"] = ["unjustified"]
    kw = _rule("sheet-absence-21", schema_21)
    inputs = {"total_salary": "1000", "absent_days": "3", "absence_class": "unjustified"}
    assert calculate_classified(direct, inputs)["value"] == Decimal("115.385")
    assert calculate_classified(kw, inputs)["value"] == Decimal("142.857")
    justified = dict(inputs, absence_class="justified")
    assert calculate_classified(direct, justified)["value"] == Decimal("0.000")
    with pytest.raises(MissingPolicyFactError):
        calculate_classified(direct, {"total_salary": "1000", "absent_days": "3"})


@pytest.fixture
def auth(api_client, get_token_for_user):
    def _factory(user):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")
        return api_client
    return _factory


@pytest.mark.django_db
def test_friday_below_floor_cannot_publish(auth, create_user, create_scoped_role):
    from people.tests.test_policy_lifecycle import DESK_URL, RULES_URL, _desk, _lead

    regulation = ComplianceRule.objects.create(
        rule_id="reg-ot-floors",
        version="2010.1",
        name="Floors",
        category=ensure_ref("compliance_category", "other"),
        jurisdiction=ensure_ref("jurisdiction", "KW"),
        effective_date=date(2010, 1, 1),
        source_citation="cited statute",
        is_authoritative=True,
        inputs_schema={
            "floors": [
                {"field": "friday_multiplier", "op": "gte", "value": "1.5"},
                {"field": "holiday_multiplier", "op": "gte", "value": "2.0"},
            ],
        },
    )
    drafter, _user = _lead(auth, create_user, create_scoped_role, "floor_drafter")
    low = {
        "rule_id": "tenant-ot",
        "version": "2026.4",
        "name": "Low Friday",
        "category": "other",
        "jurisdiction": "KW",
        "effective_date": "2026-07-01",
        "source_citation": "tenant",
        "inputs_schema": {
            "formula": {"type": "multiply", "params": {"a": "a", "b": "b"}},
            "parameters": {"friday_multiplier": "1.25", "holiday_multiplier": "2.0"},
            "regulation_ref": {"rule_id": regulation.rule_id, "version": regulation.version},
            "schedule": {
                "rows": [
                    {"code": "standard", "divisor": 26, "weekly_offs": ["friday"], "hours_per_day": 8},
                    {"code": "ramadan", "hours_per_week": 36},
                ],
            },
        },
        "test_cases": [{"inputs": {"a": "2", "b": "3"}, "expected": "6.000"}],
    }
    high = dict(low)
    high["version"] = "2026.5"
    high["inputs_schema"] = {
        **low["inputs_schema"],
        "parameters": {"friday_multiplier": "1.5", "holiday_multiplier": "2.0"},
    }
    created = drafter.post(RULES_URL, low, format="json")
    assert created.status_code == 201, created.content
    pk = created.json()["id"]
    assert drafter.post(f"{RULES_URL}{pk}/submit/", {}, format="json").status_code == 200
    created_ok = drafter.post(RULES_URL, high, format="json")
    assert created_ok.status_code == 201, created_ok.content
    ok_id = created_ok.json()["id"]
    assert drafter.post(f"{RULES_URL}{ok_id}/submit/", {}, format="json").status_code == 200
    publisher, _other = _desk(auth, create_user, create_scoped_role, "floor_publisher")
    refused = publisher.post(f"{DESK_URL}{pk}/publish/", {}, format="json")
    assert refused.status_code == 409
    assert refused.json()["code"] == "floor_failed"
    published = publisher.post(f"{DESK_URL}{ok_id}/publish/", {}, format="json")
    assert published.status_code == 200, published.content
    stored = ComplianceRule.objects.get(pk=ok_id)
    codes = [row["code"] for row in stored.inputs_schema["schedule"]["rows"]]
    assert "ramadan" in codes


@pytest.mark.django_db
def test_five_fund_split_on_a_new_gosi_version():
    rule = ComplianceRule.objects.create(
        rule_id="kw-gosi",
        version="2026.2",
        name="Five funds",
        category=ensure_ref("compliance_category", "gosi"),
        jurisdiction=ensure_ref("jurisdiction", "KW"),
        effective_date=date(2026, 6, 1),
        source_citation="contribution faq",
        is_authoritative=False,
        inputs_schema={
            "formula": {
                "type": "fund_table",
                "params": {
                    "salary_input": "insured_salary",
                    "funds": [
                        {"code": "basic", "slice": "capped", "ceiling": "1500", "employee_rate": "0.05", "employer_rate": "0.10"},
                        {"code": "supplementary", "slice": "band", "floor": "1500", "width": "1250", "employee_rate": "0.05", "employer_rate": "0.10"},
                        {"code": "pension_increase", "slice": "capped", "ceiling": "2750", "employee_rate": "0.025", "employer_rate": "0.01"},
                        {"code": "financial_remuneration", "slice": "capped", "ceiling": "1500", "employee_rate": "0.025", "employer_rate": "0"},
                        {"code": "unemployment", "slice": "capped", "ceiling": "2750", "employee_rate": "0.005", "employer_rate": "0.005"},
                    ],
                },
            },
        },
    )
    aged = ComplianceRule.objects.create(
        rule_id="kw-gosi",
        version="2026.1",
        name="Age band",
        category=ensure_ref("compliance_category", "gosi"),
        jurisdiction=ensure_ref("jurisdiction", "KW"),
        effective_date=date(2026, 1, 1),
        is_authoritative=True,
        inputs_schema={
            "formula": {
                "type": "gosi",
                "params": {
                    "employee_bands": [{"max_age": None, "rate": "0.055"}],
                    "employer_bands": [{"max_age": None, "rate": "0.11"}],
                },
            },
        },
    )
    result = calculate_gosi(rule, None, inputs={"insured_salary": "2000"}, allow_non_authoritative=True)
    assert result["lineage"]["employee_share"] == Decimal("197.500")
    assert result["lineage"]["employer_share"] == Decimal("230.000")
    aged_result = calculate_gosi(aged, Decimal("2000"), employee_age=30)
    assert aged_result["lineage"]["employee_share"] == Decimal("110.000")
    assert aged.version == "2026.1"


@pytest.mark.django_db
def test_indemnity_base_is_verified_eosi_lines_not_employee_basic():
    from mdm.models import OrgUnit
    org = OrgUnit.objects.create(name="Sheet HQ", slug="sheet-hq")
    employee = Employee.objects.create(
        org_unit=org,
        employee_no="E-SHEET",
        full_name="Sheet",
        basic_salary=Decimal("9999.000"),
        join_date=date(2018, 1, 1),
        pifss_registered=True,
    )
    basic, _ = CompensationComponent.objects.get_or_create(
        code="basic",
        defaults={"name": "Basic", "direction": "earning", "is_eosi_base": True},
    )
    basic.is_eosi_base = True
    basic.save(update_fields=["is_eosi_base"])
    housing, _ = CompensationComponent.objects.get_or_create(
        code="housing",
        defaults={"name": "Housing", "direction": "earning", "is_eosi_base": True},
    )
    housing.is_eosi_base = True
    housing.save(update_fields=["is_eosi_base"])
    for component, amount in ((basic, "800.000"), (housing, "200.000")):
        EmployeeCompensation.objects.create(
            employee=employee,
            component=component,
            amount=Decimal(amount),
            frequency="monthly",
            effective_start=date(2018, 1, 1),
            is_verified=True,
        )
    from people.compensation_service import CompensationService
    total = CompensationService.verified_eosi_base_amount(employee, as_of=date(2026, 1, 1))
    assert total == Decimal("1000.000")
    assert employee.basic_salary == Decimal("9999.000")
    rule = _rule("sheet-indemnity-ledger", INDEMNITY, version="2026.9")
    rule.category = ensure_ref("compliance_category", "eosi")
    rule.save()
    with pytest.raises(MissingPolicyFactError):
        calculate_eosi(employee, ComplianceRule.objects.filter(pk=rule.pk), as_of=date(2026, 1, 1))


@pytest.mark.django_db
def test_loan_gate_uses_rule_fraction_and_does_not_change_amount():
    rule = _rule(
        "sheet-loan-cap",
        {"formula": {"type": "multiply", "params": {"a": "a", "b": "b", "max_wage_fraction": "0.10"}}},
    )
    assert loan_within_policy(rule, Decimal("1000.000"), Decimal("100.000")) is True
    assert loan_within_policy(rule, Decimal("1000.000"), Decimal("100.001")) is False
    assert loan_within_policy(None, Decimal("1000"), Decimal("999")) is True


@pytest.mark.django_db
def test_sick_ladder_notice_and_committed_run_stay_put():
    sick = _rule(
        "sheet-sick",
        {
            "formula": {
                "type": "day_ladder",
                "params": {
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
                },
            },
        },
    )
    assert _money(sick, {"total_salary": "1000", "sick_days": "75"}) == Decimal("1153.846")
    notice = _rule("sheet-notice", _scaled(26, quantity_input="notice_days"))
    assert _money(notice, {"total_salary": "1000", "notice_days": "30"}) == Decimal("1153.846")

    from mdm.models import OrgUnit
    org = OrgUnit.objects.create(name="Frozen", slug="frozen-hq")
    run = PayrollRun.objects.create(
        org_unit=org,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        status="committed",
    )
    with pytest.raises(PayrollServiceError):
        PayrollRunService().compute(run)
    run.refresh_from_db()
    assert run.status == "committed"


@pytest.mark.django_db
def test_mixed_month_three_personas_and_old_gosi_version_unchanged():
    direct = _rule("mix-daily", _scaled(26))
    kuwaitization = _rule("mix-daily-21", _scaled(21))
    excess = _rule("mix-excess", EXCESS, version="2026.8")
    assert _money(direct, {"total_salary": "1000"}) == Decimal("38.462")
    assert _money(kuwaitization, {"total_salary": "1000"}) == Decimal("47.619")
    assert _money(
        excess, _indemnity("termination", 8, "2000", pifss_registered=True),
    ) == Decimal("2942.308")
    frozen = ComplianceRule.objects.create(
        rule_id="kw-gosi",
        version="2026.1",
        name="Frozen gosi",
        category=ensure_ref("compliance_category", "gosi"),
        jurisdiction=ensure_ref("jurisdiction", "KW"),
        effective_date=date(2026, 1, 1),
        inputs_schema={"formula": {"params": {"cap": "1500"}}},
        is_authoritative=True,
    )
    snapshot = frozen.inputs_schema
    _rule("kw-gosi-next", {"formula": {"type": "fund_table", "params": {"funds": []}}}, version="2026.2")
    frozen.refresh_from_db()
    assert frozen.version == "2026.1"
    assert frozen.inputs_schema == snapshot


@pytest.mark.django_db
def test_october_sheet_drafts_keep_examples_and_do_not_touch_2026_1(create_user):
    import copy

    from people.policy_service import example_report, floor_report
    from people.sheet_provisions import SHEET_PROVISIONS, ensure_sheet_drafts

    for code in ("other", "leave", "eosi", "overtime"):
        ensure_ref("compliance_category", code)
    ensure_ref("jurisdiction", "KW")
    frozen_schema = {"formula": {"type": "sum", "params": {"components": ["basic"]}}}
    frozen = ComplianceRule.objects.create(
        rule_id="kw-gross-pay",
        version="2026.1",
        name="Frozen gross",
        category=ensure_ref("compliance_category", "payroll"),
        jurisdiction=ensure_ref("jurisdiction", "KW"),
        effective_date=date(2026, 1, 1),
        inputs_schema=copy.deepcopy(frozen_schema),
        is_authoritative=True,
    )
    user = create_user("sheet_drafter")
    created, skipped = ensure_sheet_drafts(user)
    assert (created, skipped) == (len(SHEET_PROVISIONS), 0)
    assert ensure_sheet_drafts(user) == (0, len(SHEET_PROVISIONS))
    rows = list(ComplianceRule.objects.filter(version="2026.2"))
    assert len(rows) == 17
    for rule in rows:
        assert rule.lifecycle == "draft"
        assert rule.is_authoritative is False
        assert rule.effective_date == date(2026, 10, 1)
        examples = example_report(rule)
        assert examples["passed"], (rule.rule_id, examples)
        floors = floor_report(rule)
        assert floors["passed"], (rule.rule_id, floors)
    frozen.refresh_from_db()
    assert frozen.version == "2026.1"
    assert frozen.inputs_schema == frozen_schema
    assert frozen.is_authoritative is True
