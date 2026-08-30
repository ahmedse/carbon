from datetime import date
from decimal import Decimal

from django.test import TestCase

from mdm.models import OrgUnit
from people.calculation_engine import (
    NonAuthoritativeRuleError,
    calculate,
    calculate_eosi,
    calculate_gosi,
    calculate_gross_pay,
    calculate_leave_accrual,
    calculate_leave_split,
    calculate_loan_schedule,
    calculate_net_pay,
    calculate_overtime,
    format_wps_record,
)
from people.models import ComplianceRule, Employee


def _eosi_rule(*, authoritative=False):
    return ComplianceRule.objects.create(
        rule_id="kw-eosi-test",
        version="2026.1",
        name="[TEST ONLY — NON-AUTHORITATIVE] EOSI accrual",
        category="eosi",
        effective_date=date(2026, 1, 1),
        inputs_schema={
            "inputs": ["basic_salary", "service_years"],
            "formula": {
                "type": "tiered_accrual",
                "params": {
                    "base_inputs": ["basic_salary"],
                    "years_input": "service_years",
                    "divisor": 26,
                    "tiers": [
                        {"up_to": 5, "days_per_year": 15},
                        {"up_to": None, "days_per_year": 30},
                    ],
                },
            },
        },
        is_authoritative=authoritative,
    )


class CalculationEngineGuardTests(TestCase):
    def test_calculate_raises_when_rule_missing(self):
        with self.assertRaises(NonAuthoritativeRuleError):
            calculate(None, {"basic_salary": "780"})

    def test_calculate_raises_for_non_authoritative_by_default(self):
        rule = _eosi_rule(authoritative=False)
        with self.assertRaises(NonAuthoritativeRuleError):
            calculate(rule, {"basic_salary": "780", "service_years": "6"})

    def test_authoritative_rule_computes_without_opt_in(self):
        rule = _eosi_rule(authoritative=True)
        result = calculate(rule, {"basic_salary": "780", "service_years": "6"})
        self.assertEqual(result["value"], Decimal("5400.000"))


class CalculationEngineComputeTests(TestCase):
    def test_calculate_computes_when_opted_in(self):
        rule = _eosi_rule(authoritative=False)
        result = calculate(
            rule,
            {"basic_salary": "780", "service_years": "6"},
            allow_non_authoritative=True,
        )
        # daily rate = 780 / 26 = 30 ; 30 * 30 days * 6 yrs = 5400
        self.assertEqual(result["value"], Decimal("5400.000"))

    def test_calculate_uses_first_tier(self):
        rule = _eosi_rule(authoritative=True)
        result = calculate(rule, {"basic_salary": "780", "service_years": "2"})
        # 30 * 15 days * 2 yrs = 900
        self.assertEqual(result["value"], Decimal("900.000"))

    def test_lineage_is_populated(self):
        rule = _eosi_rule(authoritative=True)
        inputs = {"basic_salary": "780", "service_years": "6"}
        result = calculate(rule, inputs)
        self.assertEqual(result["lineage"]["rule_id"], "kw-eosi-test")
        self.assertEqual(result["lineage"]["rule_version"], "2026.1")
        self.assertEqual(result["lineage"]["inputs"], inputs)


class CalculationEngineHighLevelTests(TestCase):
    def setUp(self):
        self.org = OrgUnit.objects.create(name="Nibras HQ", slug="nibras-hq")
        # join 2024-03-01 → as_of 2026-03-01 = exactly 730 days (2 yrs, no leap day)
        self.employee = Employee.objects.create(
            org_unit=self.org,
            employee_no="E-1001",
            full_name="Test Employee",
            basic_salary=Decimal("780.000"),
            join_date=date(2024, 3, 1),
        )

    def test_calculate_eosi_looks_up_rule_and_uses_service_years(self):
        _eosi_rule(authoritative=False)
        result = calculate_eosi(
            self.employee, ComplianceRule.objects,
            allow_non_authoritative=True, as_of=date(2026, 3, 1),
        )
        # 2 yrs → tier 15: 30 * 15 * 2 = 900
        self.assertEqual(result["value"], Decimal("900.000"))
        self.assertEqual(result["lineage"]["rule_id"], "kw-eosi-test")

    def test_calculate_eosi_raises_when_no_rule(self):
        with self.assertRaises(NonAuthoritativeRuleError):
            calculate_eosi(self.employee, ComplianceRule.objects)

    def test_calculate_leave_accrual(self):
        ComplianceRule.objects.create(
            rule_id="kw-leave-test", version="2026.1", name="Leave",
            category="leave", effective_date=date(2026, 1, 1),
            inputs_schema={
                "inputs": ["basic_salary", "service_years"],
                "formula": {
                    "type": "tiered_accrual",
                    "params": {
                        "base_inputs": ["basic_salary"],
                        "years_input": "service_years",
                        "divisor": 26,
                        "tiers": [{"up_to": None, "days_per_year": 30}],
                    },
                },
            },
            is_authoritative=True,
        )
        result = calculate_leave_accrual(
            self.employee, ComplianceRule.objects, as_of=date(2026, 3, 1),
        )
        # 30 * 30 * 2 = 1800
        self.assertEqual(result["value"], Decimal("1800.000"))

    def test_calculate_overtime(self):
        ComplianceRule.objects.create(
            rule_id="kw-ot-test", version="2026.1", name="OT",
            category="overtime", effective_date=date(2026, 1, 1),
            inputs_schema={
                "inputs": ["hours", "overtime_rate"],
                "formula": {"type": "multiply", "params": {"a": "hours", "b": "overtime_rate"}},
            },
            is_authoritative=True,
        )
        result = calculate_overtime(
            self.employee,
            {"hours": "10", "overtime_rate": "5.5"},
            ComplianceRule.objects,
        )
        self.assertEqual(result["value"], Decimal("55.000"))

    def test_calculate_gross_pay(self):
        ComplianceRule.objects.create(
            rule_id="kw-gross-test", version="2026.1", name="Gross",
            category="payroll", effective_date=date(2026, 1, 1),
            inputs_schema={
                "inputs": ["basic", "overtime", "leave_pay"],
                "formula": {
                    "type": "sum",
                    "params": {"components": ["basic", "overtime", "leave_pay"]},
                },
            },
            is_authoritative=True,
        )
        result = calculate_gross_pay(
            self.employee,
            {"basic": "780", "overtime": "55", "leave_pay": "30"},
            ComplianceRule.objects,
        )
        self.assertEqual(result["value"], Decimal("865.000"))


class CalculationEngineExpansionTests(TestCase):
    def setUp(self):
        self.org = OrgUnit.objects.create(name="Nibras HQ", slug="nibras-hq")
        self.employee = Employee.objects.create(
            org_unit=self.org,
            employee_no="E-2001",
            full_name="Expansion Employee",
            basic_salary=Decimal("780.000"),
            join_date=date(2024, 3, 1),
        )

    # --- GOSI ---

    def _gosi_rule(self, authoritative=False):
        return ComplianceRule.objects.create(
            rule_id="kw-gosi-test",
            version="2026.1",
            name="[TEST ONLY — NON-AUTHORITATIVE] GOSI",
            category="gosi",
            effective_date=date(2026, 1, 1),
            inputs_schema={
                "inputs": ["gross_salary", "employee_age"],
                "formula": {
                    "type": "gosi",
                    "params": {
                        "employee_bands": [{"max_age": None, "rate": "0.105"}],
                        "employer_bands": [{"max_age": None, "rate": "0.110"}],
                    },
                },
            },
            is_authoritative=authoritative,
        )

    def test_calculate_gosi_computes_total(self):
        rule = self._gosi_rule(authoritative=False)
        result = calculate_gosi(
            rule, Decimal("1000.000"), employee_age=30, allow_non_authoritative=True
        )
        self.assertEqual(result["value"], Decimal("215.000"))
        self.assertEqual(result["lineage"]["employee_share"], Decimal("105.000"))
        self.assertEqual(result["lineage"]["employer_share"], Decimal("110.000"))

    def test_calculate_gosi_age_bands(self):
        rule = ComplianceRule.objects.create(
            rule_id="kw-gosi-age-test",
            version="2026.1",
            name="[TEST ONLY] GOSI age bands",
            category="gosi",
            effective_date=date(2026, 1, 1),
            inputs_schema={
                "inputs": ["gross_salary", "employee_age"],
                "formula": {
                    "type": "gosi",
                    "params": {
                        "employee_bands": [
                            {"max_age": 40, "rate": "0.105"},
                            {"max_age": None, "rate": "0.080"},
                        ],
                        "employer_bands": [{"max_age": None, "rate": "0.110"}],
                    },
                },
            },
            is_authoritative=False,
        )
        young = calculate_gosi(
            rule, Decimal("1000.000"), employee_age=30, allow_non_authoritative=True
        )
        self.assertEqual(young["lineage"]["employee_share"], Decimal("105.000"))
        old = calculate_gosi(
            rule, Decimal("1000.000"), employee_age=50, allow_non_authoritative=True
        )
        self.assertEqual(old["lineage"]["employee_share"], Decimal("80.000"))

    def test_calculate_gosi_raises_for_non_authoritative(self):
        rule = self._gosi_rule(authoritative=False)
        with self.assertRaises(NonAuthoritativeRuleError):
            calculate_gosi(rule, Decimal("1000.000"))

    def test_calculate_gosi_lineage(self):
        rule = self._gosi_rule(authoritative=False)
        result = calculate_gosi(
            rule, Decimal("1000.000"), employee_age=30, allow_non_authoritative=True
        )
        self.assertEqual(result["lineage"]["rule_id"], "kw-gosi-test")
        self.assertEqual(result["lineage"]["rule_version"], "2026.1")
        self.assertIn("gross_salary", result["lineage"]["inputs"])

    # --- WPS ---

    def _wps_rule(self, authoritative=False):
        return ComplianceRule.objects.create(
            rule_id="kw-wps-test",
            version="2026.1",
            name="[TEST ONLY] WPS record",
            category="wps",
            effective_date=date(2026, 1, 1),
            inputs_schema={
                "inputs": [
                    "basic", "overtime", "allowances", "employee_number",
                    "employee_name", "bank_account", "agent_bank_code",
                ],
                "formula": {
                    "type": "wps_record",
                    "params": {
                        "field_map": {
                            "employee_number": "employee_number",
                            "employee_name": "employee_name",
                            "bank_account": "bank_account",
                            "agent_bank_code": "agent_bank_code",
                        },
                        "static_fields": {
                            "record_type": "salary",
                            "currency": "KWD",
                            "country_code": "KW",
                        },
                        "amount_components": ["basic", "overtime", "allowances"],
                    },
                },
            },
            is_authoritative=authoritative,
        )

    def test_format_wps_record(self):
        rule = self._wps_rule(authoritative=False)
        payslip = {
            "basic": "780", "overtime": "55", "allowances": "30",
            "employee_number": "E-2001", "employee_name": "Expansion Employee",
            "bank_account": "KW123", "agent_bank_code": "AGENT",
        }
        result = format_wps_record(rule, payslip, allow_non_authoritative=True)
        self.assertEqual(result["value"], Decimal("865.000"))
        self.assertEqual(result["record"]["amount"], Decimal("865.000"))
        self.assertEqual(result["record"]["employee_number"], "E-2001")
        self.assertEqual(result["record"]["currency"], "KWD")

    def test_format_wps_record_raises_for_non_authoritative(self):
        rule = self._wps_rule(authoritative=False)
        with self.assertRaises(NonAuthoritativeRuleError):
            format_wps_record(rule, {"basic": "1"})

    def test_format_wps_record_lineage(self):
        rule = self._wps_rule(authoritative=False)
        result = format_wps_record(rule, {"basic": "780"}, allow_non_authoritative=True)
        self.assertEqual(result["lineage"]["rule_id"], "kw-wps-test")
        self.assertEqual(result["lineage"]["rule_version"], "2026.1")
        self.assertIn("basic", result["lineage"]["inputs"])

    # --- Leave split ---

    def _leave_split_rule(self, authoritative=False):
        return ComplianceRule.objects.create(
            rule_id="kw-leave-split-test",
            version="2026.1",
            name="[TEST ONLY] Leave split",
            category="leave",
            effective_date=date(2026, 1, 1),
            inputs_schema={
                "inputs": ["start_date", "end_date"],
                "formula": {
                    "type": "leave_split",
                    "params": {
                        "start_input": "start_date",
                        "end_input": "end_date",
                        "inclusive": True,
                    },
                },
            },
            is_authoritative=authoritative,
        )

    def test_calculate_leave_split(self):
        rule = self._leave_split_rule(authoritative=False)
        leave_record = {"start_date": date(2026, 12, 28), "end_date": date(2027, 1, 3)}
        result = calculate_leave_split(rule, leave_record, allow_non_authoritative=True)
        self.assertEqual(result["value"], Decimal("7"))
        self.assertEqual(
            result["calendar_split"], {"2026": Decimal("4"), "2027": Decimal("3")}
        )

    def test_calculate_leave_split_raises_for_non_authoritative(self):
        rule = self._leave_split_rule(authoritative=False)
        with self.assertRaises(NonAuthoritativeRuleError):
            calculate_leave_split(
                rule, {"start_date": date(2026, 1, 1), "end_date": date(2026, 1, 5)}
            )

    def test_calculate_leave_split_lineage(self):
        rule = self._leave_split_rule(authoritative=False)
        result = calculate_leave_split(
            rule,
            {"start_date": date(2026, 1, 1), "end_date": date(2026, 1, 2)},
            allow_non_authoritative=True,
        )
        self.assertEqual(result["lineage"]["rule_id"], "kw-leave-split-test")
        self.assertIn("start_date", result["lineage"]["inputs"])

    # --- Loan schedule ---

    def _loan_rule(self, authoritative=False, method="flat", rate_is_percent=True):
        return ComplianceRule.objects.create(
            rule_id="kw-loan-test",
            version="2026.1",
            name="[TEST ONLY] Loan schedule",
            category="other",
            effective_date=date(2026, 1, 1),
            inputs_schema={
                "inputs": ["principal", "interest_rate", "term_months"],
                "formula": {
                    "type": "loan_schedule",
                    "params": {
                        "method": method,
                        "rate_is_annual": True,
                        "rate_is_percent": rate_is_percent,
                    },
                },
            },
            is_authoritative=authoritative,
        )

    def test_calculate_loan_schedule_flat(self):
        rule = self._loan_rule(authoritative=False, method="flat", rate_is_percent=True)
        loan = {"principal": "1000", "interest_rate": "12", "term_months": 12}
        result = calculate_loan_schedule(rule, loan, allow_non_authoritative=True)
        installments = result["installments"]
        self.assertEqual(len(installments), 12)
        self.assertEqual(result["value"], Decimal("1120.000"))
        self.assertEqual(
            sum(i["principal_portion"] for i in installments), Decimal("1000.000")
        )
        self.assertEqual(
            sum(i["interest_portion"] for i in installments), Decimal("120.000")
        )
        self.assertEqual(
            sum(i["amount"] for i in installments), Decimal("1120.000")
        )

    def test_calculate_loan_schedule_reducing(self):
        rule = self._loan_rule(authoritative=False, method="reducing", rate_is_percent=True)
        loan = {"principal": "1000", "interest_rate": "12", "term_months": 12}
        result = calculate_loan_schedule(rule, loan, allow_non_authoritative=True)
        installments = result["installments"]
        self.assertEqual(len(installments), 12)
        self.assertEqual(
            sum(i["principal_portion"] for i in installments), Decimal("1000.000")
        )
        self.assertEqual(
            sum(i["amount"] for i in installments), result["value"]
        )

    def test_calculate_loan_schedule_raises_for_non_authoritative(self):
        rule = self._loan_rule(authoritative=False)
        with self.assertRaises(NonAuthoritativeRuleError):
            calculate_loan_schedule(
                rule, {"principal": "1000", "interest_rate": "12", "term_months": 12}
            )

    def test_calculate_loan_schedule_lineage(self):
        rule = self._loan_rule(authoritative=False)
        result = calculate_loan_schedule(
            rule,
            {"principal": "1000", "interest_rate": "12", "term_months": 12},
            allow_non_authoritative=True,
        )
        self.assertEqual(result["lineage"]["rule_id"], "kw-loan-test")
        self.assertIn("principal", result["lineage"]["inputs"])

    # --- Net pay ---

    def _net_pay_rule(self, authoritative=False):
        return ComplianceRule.objects.create(
            rule_id="kw-netpay-test",
            version="2026.1",
            name="[TEST ONLY] Net pay",
            category="payroll",
            effective_date=date(2026, 1, 1),
            inputs_schema={
                "inputs": ["gross", "deductions"],
                "formula": {"type": "net_pay", "params": {}},
            },
            is_authoritative=authoritative,
        )

    def test_calculate_net_pay(self):
        rule = self._net_pay_rule(authoritative=False)
        result = calculate_net_pay(
            rule,
            Decimal("1000.000"),
            [Decimal("105.000"), Decimal("120.000"), Decimal("50.000")],
            allow_non_authoritative=True,
        )
        self.assertEqual(result["value"], Decimal("725.000"))
        self.assertFalse(result["negative_net_pay"])

    def test_calculate_net_pay_flags_negative(self):
        rule = self._net_pay_rule(authoritative=False)
        result = calculate_net_pay(
            rule, Decimal("100.000"), [Decimal("150.000")], allow_non_authoritative=True
        )
        self.assertEqual(result["value"], Decimal("-50.000"))
        self.assertTrue(result["negative_net_pay"])

    def test_calculate_net_pay_raises_for_non_authoritative(self):
        rule = self._net_pay_rule(authoritative=False)
        with self.assertRaises(NonAuthoritativeRuleError):
            calculate_net_pay(rule, Decimal("1000"), [])

    def test_calculate_net_pay_lineage(self):
        rule = self._net_pay_rule(authoritative=False)
        result = calculate_net_pay(
            rule, Decimal("1000"), [Decimal("100")], allow_non_authoritative=True
        )
        self.assertEqual(result["lineage"]["rule_id"], "kw-netpay-test")
        self.assertIn("gross", result["lineage"]["inputs"])

    # --- Gross pay extension ---

    def test_calculate_gross_pay_composes_base_from_employee(self):
        ComplianceRule.objects.create(
            rule_id="kw-gross-base-test",
            version="2026.1",
            name="[TEST ONLY] Gross with base_input",
            category="payroll",
            effective_date=date(2026, 1, 1),
            inputs_schema={
                "inputs": ["basic", "overtime"],
                "formula": {
                    "type": "sum",
                    "params": {"components": ["basic", "overtime"], "base_input": "basic"},
                },
            },
            is_authoritative=True,
        )
        result = calculate_gross_pay(
            self.employee, {"overtime": "55"}, ComplianceRule.objects
        )
        self.assertEqual(result["value"], Decimal("835.000"))
