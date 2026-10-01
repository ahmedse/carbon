"""October sheet provisions as draft ComplianceRule rows.

The seventeen rows are the 1 Oct 2026 workbook. Formula JSON matches the
examples in people/tests/test_sheet_policy.py. This module creates drafts
through policy_service. It does not mark a row authoritative and it does
not write version 2026.1.
"""

from __future__ import annotations

import copy

from people.models import ComplianceRule
from people.policy_service import create_draft

SHEET_VERSION = "2026.2"
SHEET_EFFECTIVE = "2026-10-01"
PACK_REF = {"pack": "kw", "version": "2010.1"}
PACK_CITATION = "regulation_packs/kw/2010.1.yaml"

INDEMNITY = {
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

EXCESS = {
    "type": "banded_fraction",
    "params": {
        **INDEMNITY["params"],
        "excess_over": "1500",
        "excess_when_fact": "pifss_registered",
        "requires_facts": ["pifss_registered"],
    },
}


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
    return {"type": "scaled_rate", "params": params}


def _case(inputs, expected):
    return {"inputs": inputs, "expected": expected}


def _schema(formula, *, parameters=None, payslip=None):
    params = dict(formula["params"])
    if payslip:
        params.update(payslip)
    body = {
        "formula": {"type": formula["type"], "params": params},
        "regulation_ref": dict(PACK_REF),
    }
    if parameters:
        body["parameters"] = parameters
    return body


def _row(rule_id, name, category, formula, cases, *, sheet_row, parameters=None, payslip=None):
    return {
        "rule_id": rule_id,
        "version": SHEET_VERSION,
        "name": name,
        "description": f"October sheet row {sheet_row}.",
        "category": category,
        "jurisdiction": "KW",
        "effective_date": SHEET_EFFECTIVE,
        "formula_ref": PACK_CITATION,
        "source_citation": PACK_CITATION,
        "inputs_schema": _schema(formula, parameters=parameters, payslip=payslip),
        "provenance": {
            "source": "GOFSCO Payroll and Compensation Sheet 2026-10-01",
            "pack": PACK_CITATION,
            "sheet_row": sheet_row,
        },
        "test_cases": cases,
    }


_LEAVE = {
    "payslip_line": "leave_pay",
    "payslip_effect": "earning",
    "fact_source": "leave_days",
    "applies_to": "all",
    "leave_type_codes": ["annual"],
    "min_service_months": 6,
}
_ENCASH = {
    "payslip_line": "leave_encashment",
    "payslip_effect": "earning",
    "fact_source": "entitlement_balance",
    "applies_to": "all",
    "leave_type_codes": ["annual"],
    "require_separation": True,
}
_ABSENCE_DIRECT = {
    "payslip_line": "absence_deduction",
    "payslip_effect": "deduction",
    "fact_source": "attendance_absence",
    "applies_to": "direct",
    "class_input": "absence_class",
    "billable_classes": ["unjustified"],
}
_ABSENCE_KW = {
    **_ABSENCE_DIRECT,
    "applies_to": "kuwaitization",
}
_OT_DAY = {
    "payslip_line": "overtime",
    "payslip_effect": "earning",
    "fact_source": "attendance_overtime",
    "applies_to": "all",
    "weekdays": [5, 6, 0, 1, 2, 3],
}
_OT_FRIDAY = {
    "payslip_line": "compensatory_pay",
    "payslip_effect": "earning",
    "fact_source": "attendance_overtime",
    "applies_to": "all",
    "weekdays": [4],
}

_INDEMNITY_CASES = [
    _case({"total_salary": "1000", "service_years": "8", "separation_reason": "termination"}, "5884.615"),
    _case({"total_salary": "1000", "service_years": "2", "separation_reason": "resignation"}, "0.000"),
    _case({"total_salary": "1000", "service_years": "4", "separation_reason": "resignation"}, "1153.846"),
    _case({"total_salary": "1000", "service_years": "8", "separation_reason": "resignation"}, "3923.077"),
    _case({"total_salary": "1000", "service_years": "21", "separation_reason": "resignation"}, "18000.000"),
    _case({"total_salary": "1000", "service_years": "5", "separation_reason": "resignation"}, "1923.077"),
    _case({"total_salary": "1000", "service_years": "10", "separation_reason": "resignation"}, "7884.615"),
    _case({
        "total_salary": "1000",
        "service_years": "2",
        "service_days": "730",
        "separation_reason": "termination",
    }, "1153.846"),
]

SHEET_PROVISIONS = [
    _row(
        "sheet-daily-direct", "Payroll daily rate — direct hire", "other",
        _scaled(26),
        [_case({"total_salary": "1000"}, "38.462")],
        sheet_row=2,
    ),
    _row(
        "sheet-daily-kuwaitization", "Payroll daily rate — Kuwaitization", "other",
        _scaled(21),
        [_case({"total_salary": "1000"}, "47.619")],
        sheet_row=3,
    ),
    _row(
        "sheet-hourly-direct", "Payroll hourly rate — direct hire", "other",
        _scaled(26, hours=8),
        [_case({"total_salary": "1000"}, "4.808")],
        sheet_row=4,
    ),
    _row(
        "sheet-hourly-kuwaitization", "Payroll hourly rate — Kuwaitization", "other",
        _scaled(21, hours=8),
        [_case({"total_salary": "1000"}, "5.952")],
        sheet_row=5,
    ),
    _row(
        "sheet-leave", "Leave calculation", "leave",
        _scaled(26, quantity_input="leave_days"),
        [_case({"total_salary": "1000", "leave_days": "3"}, "115.385")],
        sheet_row=6, payslip=_LEAVE,
    ),
    _row(
        "sheet-encash", "Leave encashment", "leave",
        _scaled(26, quantity_input="leave_days", extra={"max_quantity": "60"}),
        [
            _case({"total_salary": "1000", "leave_days": "20"}, "769.231"),
            _case({"total_salary": "1000", "leave_days": "100"}, "2307.692"),
        ],
        sheet_row=7, payslip=_ENCASH,
    ),
    _row(
        "sheet-absence-direct", "Absent deduction — direct hire", "other",
        _scaled(26, quantity_input="absent_days"),
        [_case({
            "total_salary": "1000", "absent_days": "3", "absence_class": "unjustified",
        }, "115.385")],
        sheet_row=8, payslip=_ABSENCE_DIRECT,
    ),
    _row(
        "sheet-absence-kuwaitization", "Absent deduction — Kuwaitization", "other",
        _scaled(21, quantity_input="absent_days"),
        [_case({
            "total_salary": "1000", "absent_days": "3", "absence_class": "unjustified",
        }, "142.857")],
        sheet_row=9, payslip=_ABSENCE_KW,
    ),
    _row(
        "sheet-ot-working-day", "Overtime — working day", "overtime",
        _scaled(26, hours=8, multiplier="1.25", quantity_input="ot_hours", base="basic_salary"),
        [_case({"basic_salary": "800", "ot_hours": "2"}, "9.615")],
        sheet_row=10,
        parameters={"working_day_multiplier": "1.25"},
        payslip=_OT_DAY,
    ),
    _row(
        "sheet-ot-friday", "Overtime — Friday", "overtime",
        _scaled(
            26, hours=8, multiplier="1.5", quantity_input="ot_hours",
            base="basic_salary", extra={"compensatory_days": 1},
        ),
        [_case({"basic_salary": "800", "ot_hours": "6"}, "34.615")],
        sheet_row=11,
        parameters={"friday_multiplier": "1.5"},
        payslip=_OT_FRIDAY,
    ),
    _row(
        "sheet-ot-holiday", "Overtime — official holiday", "overtime",
        _scaled(26, hours=8, multiplier="2", quantity_input="ot_hours", base="basic_salary"),
        [_case({"basic_salary": "800", "ot_hours": "6"}, "46.154")],
        sheet_row=12,
        parameters={"holiday_multiplier": "2.0"},
    ),
    _row(
        "sheet-indemnity-termination", "End of service — termination or death", "eosi",
        INDEMNITY, _INDEMNITY_CASES, sheet_row=13,
    ),
    _row(
        "sheet-indemnity-resign-under-3", "End of service — resignation under 3 years", "eosi",
        INDEMNITY,
        [_case({"total_salary": "1000", "service_years": "2", "separation_reason": "resignation"}, "0.000")],
        sheet_row=14,
    ),
    _row(
        "sheet-indemnity-resign-3-to-5", "End of service — resignation from 3 to 5 years", "eosi",
        INDEMNITY,
        [_case({"total_salary": "1000", "service_years": "4", "separation_reason": "resignation"}, "1153.846")],
        sheet_row=15,
    ),
    _row(
        "sheet-indemnity-resign-5-to-10", "End of service — resignation from 5 to 10 years", "eosi",
        INDEMNITY,
        [_case({"total_salary": "1000", "service_years": "8", "separation_reason": "resignation"}, "3923.077")],
        sheet_row=16,
    ),
    _row(
        "sheet-indemnity-resign-over-10", "End of service — resignation over 10 years", "eosi",
        INDEMNITY,
        [_case({"total_salary": "1000", "service_years": "21", "separation_reason": "resignation"}, "18000.000")],
        sheet_row=17,
    ),
    _row(
        "sheet-indemnity-pifss-excess", "End of service — registered excess", "eosi",
        EXCESS,
        [
            _case({
                "total_salary": "2000", "service_years": "8",
                "separation_reason": "termination", "pifss_registered": True,
            }, "2942.308"),
            _case({
                "total_salary": "1500", "service_years": "8",
                "separation_reason": "termination", "pifss_registered": True,
            }, "0.000"),
            _case({
                "total_salary": "1000", "service_years": "8",
                "separation_reason": "termination", "pifss_registered": False,
            }, "5884.615"),
        ],
        sheet_row=18,
    ),
]

SHEET_RULE_IDS = tuple(row["rule_id"] for row in SHEET_PROVISIONS)


def _ensure_payslip_codes():
    from mdm.models import ReferenceSet, ReferenceValue

    rs = ReferenceSet.objects.filter(name="payslip_line_type").first()
    if rs is None:
        return
    for code, label in (
        ("leave_encashment", "Leave Encashment"),
        ("absence_deduction", "Absence Deduction"),
        ("compensatory_pay", "Compensatory Pay"),
    ):
        ReferenceValue.objects.get_or_create(
            reference_set=rs,
            code=code,
            defaults={"label": label, "is_active": True, "sort_order": 80},
        )


def ensure_sheet_drafts(user):
    """Create any missing 2026.2 sheet row as a draft. Existing rows are left alone."""
    if len(SHEET_PROVISIONS) != 17:
        raise RuntimeError(f"expected 17 sheet provisions, found {len(SHEET_PROVISIONS)}")
    _ensure_payslip_codes()
    created = skipped = 0
    for spec in SHEET_PROVISIONS:
        if ComplianceRule.objects.filter(rule_id=spec["rule_id"], version=SHEET_VERSION).exists():
            skipped += 1
            continue
        create_draft(copy.deepcopy(spec), user)
        created += 1
    return created, skipped
