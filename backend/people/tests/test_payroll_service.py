from datetime import date
from decimal import Decimal

from django.test import TestCase

from core.models import Module
from dataschema.models import DataRow, DataTable
from mdm.models import OrgUnit

from people.models import (
    AttendanceRecord,
    ComplianceRule,
    Employee,
    Loan,
    PayslipLine,
    PayrollRun,
)
from people.payroll_service import (
    PayrollRunService,
    PayrollServiceError,
    make_finding,
)


def _gross_rule():
    return ComplianceRule.objects.create(
        rule_id="kw-gross-test",
        version="2026.1",
        name="[TEST ONLY] Gross pay",
        category="payroll",
        effective_date=date(2026, 1, 1),
        inputs_schema={
            "inputs": ["basic"],
            "formula": {
                "type": "sum",
                "params": {"components": ["basic"], "base_input": "basic"},
            },
        },
        is_authoritative=True,
    )


def _gosi_rule():
    return ComplianceRule.objects.create(
        rule_id="kw-gosi-test",
        version="2026.1",
        name="[TEST ONLY] GOSI",
        category="gosi",
        effective_date=date(2026, 1, 1),
        inputs_schema={
            "inputs": ["gross_salary", "employee_age"],
            "formula": {
                "type": "gosi",
                "params": {
                    "employee_bands": [{"max_age": None, "rate": "0.10"}],
                    "employer_bands": [{"max_age": None, "rate": "0.10"}],
                },
            },
        },
        is_authoritative=True,
    )


def _loan_rule():
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
                    "method": "flat",
                    "rate_is_annual": True,
                    "rate_is_percent": False,
                },
            },
        },
        is_authoritative=True,
    )


def _net_rule():
    return ComplianceRule.objects.create(
        rule_id="kw-netpay-test",
        version="2026.1",
        name="[TEST ONLY] Net pay",
        category="other",
        effective_date=date(2026, 1, 1),
        inputs_schema={
            "inputs": ["gross", "deductions"],
            "formula": {"type": "net_pay", "params": {}},
        },
        is_authoritative=True,
    )


class StubValidationSeam:
    """Injectable seam so tests can flip validation between passes and failures."""

    def __init__(self):
        self.findings = []

    def validate_run(self, run):
        return list(self.findings)


class PayrollRunServiceTests(TestCase):
    def setUp(self):
        self.hq = OrgUnit.objects.create(name="HQ", slug="hq")
        self.sub = OrgUnit.objects.create(name="Sub Unit", slug="sub", parent=self.hq)
        self.other = OrgUnit.objects.create(name="Other Unit", slug="other")

        self.in_scope = Employee.objects.create(
            org_unit=self.hq, employee_no="E-1", full_name="In Scope",
            basic_salary=Decimal("1000.000"), join_date=date(2024, 1, 1),
        )
        self.sub_scope = Employee.objects.create(
            org_unit=self.sub, employee_no="E-2", full_name="Sub Scope",
            basic_salary=Decimal("1000.000"), join_date=date(2024, 1, 1),
        )
        self.out_scope = Employee.objects.create(
            org_unit=self.other, employee_no="E-3", full_name="Out Scope",
            basic_salary=Decimal("1000.000"), join_date=date(2024, 1, 1),
        )

        _gross_rule()
        _gosi_rule()
        _loan_rule()
        _net_rule()

        self.seam = StubValidationSeam()
        self.service = PayrollRunService(validation_seam=self.seam)

    def _run(self, org=None):
        return PayrollRun.objects.create(
            org_unit=org or self.hq,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
        )

    def test_happy_path_draft_compute_validate_commit(self):
        run = self._run()
        # Give the in-scope employee an active loan so the full pipeline runs.
        Loan.objects.create(
            employee=self.in_scope, loan_type="advance",
            principal=Decimal("1200.000"), interest_rate=Decimal("0"),
            term_months=12, start_date=date(2026, 8, 1),
        )

        result = self.service.compute(run)
        self.assertEqual(result["status"], "computed")
        self.assertEqual(result["employees"], 2)
        run.refresh_from_db()
        self.assertEqual(run.status, "computed")

        in_lines = PayslipLine.objects.filter(employee=self.in_scope)
        self.assertEqual(
            set(in_lines.values_list("line_type", flat=True)),
            {"gross", "gosi", "loan_installment", "net"},
        )
        self.assertEqual(in_lines.get(line_type="gross").amount, Decimal("1000.000"))
        self.assertEqual(in_lines.get(line_type="gosi").amount, Decimal("200.000"))
        self.assertEqual(
            in_lines.get(line_type="loan_installment").amount, Decimal("100.000")
        )
        # net = 1000 − (100 GOSI employee share + 100 installment) = 800
        self.assertEqual(in_lines.get(line_type="net").amount, Decimal("800.000"))

        gross_line = in_lines.get(line_type="gross")
        self.assertEqual(gross_line.rule_id, "kw-gross-test")
        self.assertEqual(gross_line.rule_version, "2026.1")

        # sub_scope employee has no loan → gross/gosi/net only.
        sub_lines = PayslipLine.objects.filter(employee=self.sub_scope)
        self.assertEqual(
            set(sub_lines.values_list("line_type", flat=True)),
            {"gross", "gosi", "net"},
        )

        self.service.validate(run)
        run.refresh_from_db()
        self.assertEqual(run.status, "validated")

        commit_result = self.service.commit(run)
        self.assertFalse(commit_result["has_errors"])
        run.refresh_from_db()
        self.assertEqual(run.status, "committed")
        self.assertIsNotNone(run.committed_at)

    def test_org_scoping_excludes_other_unit(self):
        run = self._run(self.hq)
        self.service.compute(run)

        self.assertTrue(PayslipLine.objects.filter(employee=self.in_scope).exists())
        self.assertTrue(PayslipLine.objects.filter(employee=self.sub_scope).exists())
        self.assertFalse(PayslipLine.objects.filter(employee=self.out_scope).exists())

    def test_org_scoping_parent_not_in_child_scope(self):
        # A run scoped to a child unit must never include the parent unit's employee.
        sub_run = self._run(self.sub)
        self.service.compute(sub_run)

        self.assertTrue(
            PayslipLine.objects.filter(employee=self.sub_scope, payroll_run=sub_run).exists()
        )
        self.assertFalse(
            PayslipLine.objects.filter(employee=self.in_scope, payroll_run=sub_run).exists()
        )

    def test_commit_blocked_on_validation_error(self):
        run = self._run()
        self.service.compute(run)
        self.service.validate(run)
        self.assertEqual(run.status, "validated")

        self.seam.findings = [
            make_finding(
                "net-negative", severity="error", passed=False,
                checked=1, failed=1, sample_failures=["E-1"],
            )
        ]
        result = self.service.commit(run)
        self.assertTrue(result["has_errors"])
        self.assertEqual(result["error_count"], 1)
        run.refresh_from_db()
        self.assertEqual(run.status, "failed")
        self.assertIsNone(run.committed_at)

    def test_commit_requires_validated_status(self):
        run = self._run()
        self.service.compute(run)  # → computed
        with self.assertRaises(PayrollServiceError):
            self.service.commit(run)  # skip: computed → commit is illegal

    def test_provenance_line_carries_data_row_id_and_hash(self):
        run = self._run()
        module = Module.objects.create(name="Payroll Attendance", org_unit=self.hq)
        table = DataTable.objects.create(module=module, name="attendance_measurements")
        data_row = DataRow.objects.create(
            data_table=table, values={"overtime_hours": "2"}, row_hash="hash-abc",
        )
        AttendanceRecord.objects.create(
            employee=self.in_scope, date=date(2026, 8, 5),
            hours_worked=Decimal("8.00"), overtime_hours=Decimal("2.00"),
            status="present", source_row=data_row,
        )

        self.service.compute(run)

        gross = PayslipLine.objects.get(employee=self.in_scope, line_type="gross")
        self.assertEqual(gross.inputs["data_row_id"], data_row.pk)
        self.assertEqual(gross.inputs["row_hash"], "hash-abc")
        self.assertIn("measurements", gross.inputs)
