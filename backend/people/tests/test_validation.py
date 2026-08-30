"""
Validation tests (NIR-3D / RULE_11) — DQ validation seam regression.

Covers:
  * Tier-1 ``validate_write``: a bound ``not_null`` rule on ``people.Employee``
    blocks a bad write and passes a good one.
  * Tier-2 ``validate_run``: a negative net line yields an error finding and
    ``persist_findings`` writes a failed ``PayrollRunValidation``.
  * Run-scoped summaries store counts + sample_failures (a list), never per-row
    rows (no ``DQResult`` created).
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from dq.models import DQRule, DQResult, ModelRuleAssignment
from mdm.models import OrgUnit

from people.models import (
    Employee,
    PayrollRun,
    PayslipLine,
    PayrollRunValidation,
)
from people.validation import persist_findings, validate_run, validate_write

EMPLOYEE_LABEL = "people.Employee"


def _rule_definition(name, rule_type, dimension, params, severity="error"):
    return {
        "schema_version": 1,
        "name": name,
        "level": "field",
        "dimension": dimension,
        "type": rule_type,
        "severity": severity,
        "params": params,
        "enforcement": {"on_write": True},
        "active": True,
    }


class ValidateWriteTests(TestCase):
    """Tier-1 field gate blocks/passes an Employee write via a bound rule."""

    @classmethod
    def setUpTestData(cls):
        cls.org = OrgUnit.objects.create(name="HQ", slug="hq")
        rule = DQRule.objects.create(
            name="nationality-required",
            rule_type="not_null",
            rule_level="field_validation",
            is_active=True,
            definition=_rule_definition(
                "nationality-required", "not_null", "completeness", {}
            ),
        )
        ModelRuleAssignment.objects.create(
            rule=rule,
            model_label=EMPLOYEE_LABEL,
            field_name="nationality",
            is_active=True,
        )

    def _employee(self, nationality):
        return Employee(
            org_unit=self.org,
            employee_no="E-1" if nationality else "E-2",
            full_name="Test Employee",
            nationality=nationality,
            basic_salary=Decimal("1000.000"),
            join_date=date(2024, 1, 1),
        )

    def test_bad_employee_blocked(self):
        result = validate_write(self._employee(""))
        self.assertTrue(result["blocked"])
        self.assertGreaterEqual(result["failed"], 1)

    def test_good_employee_passes(self):
        result = validate_write(self._employee("Kuwaiti"))
        self.assertFalse(result["blocked"])
        self.assertEqual(result["failed"], 0)


class ValidateRunTests(TestCase):
    """Tier-2 batch rules over a run's computed lines."""

    @classmethod
    def setUpTestData(cls):
        cls.org = OrgUnit.objects.create(name="HQ", slug="hq")
        cls.employee = Employee.objects.create(
            org_unit=cls.org,
            employee_no="E-1",
            full_name="Test Employee",
            nationality="Kuwaiti",
            basic_salary=Decimal("1000.000"),
            join_date=date(2024, 1, 1),
        )

    def _run(self):
        return PayrollRun.objects.create(
            org_unit=self.org,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
        )

    def test_negative_net_returns_error_and_persists_failed_validation(self):
        run = self._run()
        PayslipLine.objects.create(
            payroll_run=run, employee=self.employee, line_type="net",
            amount=Decimal("-5.000"), rule_id="kw-netpay-test", rule_version="2026.1",
        )

        findings = validate_run(run)
        net_finding = next(f for f in findings if f["rule_key"] == "net_positive")
        self.assertEqual(net_finding["severity"], "error")
        self.assertFalse(net_finding["passed"])
        self.assertGreaterEqual(net_finding["failed"], 1)

        created = persist_findings(run, findings)
        self.assertGreaterEqual(len(created), 1)
        persisted = PayrollRunValidation.objects.get(rule_key="net_positive")
        self.assertFalse(persisted.passed)
        self.assertIsInstance(persisted.sample_failures, list)
        self.assertGreaterEqual(persisted.failed, 1)

    def test_summary_stores_counts_and_samples_not_rows(self):
        run = self._run()
        PayslipLine.objects.create(
            payroll_run=run, employee=self.employee, line_type="net",
            amount=Decimal("-5.000"), rule_id="kw-netpay-test", rule_version="2026.1",
        )

        findings = validate_run(run)
        persist_findings(run, findings)

        # Summary is run-scoped: counts + sample_failures list, not per-row rows.
        self.assertEqual(DQResult.objects.count(), 0)
        self.assertEqual(
            PayrollRunValidation.objects.filter(payroll_run=run).count(),
            len(findings),
        )
        net_finding = next(f for f in findings if f["rule_key"] == "net_positive")
        self.assertIsInstance(net_finding["checked"], int)
        self.assertIsInstance(net_finding["failed"], int)
        self.assertIsInstance(net_finding["sample_failures"], list)

    def test_lineage_missing_returns_error(self):
        run = self._run()
        PayslipLine.objects.create(
            payroll_run=run, employee=self.employee, line_type="gross",
            amount=Decimal("1000.000"), rule_id="", rule_version="",
        )

        findings = validate_run(run)
        lineage = next(f for f in findings if f["rule_key"] == "lineage_present")
        self.assertEqual(lineage["severity"], "error")
        self.assertFalse(lineage["passed"])
        self.assertGreaterEqual(lineage["failed"], 1)

    def test_reconciliation_passes_then_fails(self):
        run = self._run()
        PayslipLine.objects.create(
            payroll_run=run, employee=self.employee, line_type="gross",
            amount=Decimal("1000.000"), rule_id="kw-gross-test", rule_version="2026.1",
        )
        PayslipLine.objects.create(
            payroll_run=run, employee=self.employee, line_type="loan_installment",
            amount=Decimal("100.000"), rule_id="kw-loan-test", rule_version="2026.1",
        )
        PayslipLine.objects.create(
            payroll_run=run, employee=self.employee, line_type="net",
            amount=Decimal("900.000"), rule_id="kw-netpay-test", rule_version="2026.1",
        )

        findings = validate_run(run)
        recon = next(f for f in findings if f["rule_key"] == "net_reconciliation")
        self.assertTrue(recon["passed"])

        PayslipLine.objects.filter(payroll_run=run, line_type="net").update(
            amount=Decimal("800.000")
        )
        findings2 = validate_run(run)
        recon2 = next(f for f in findings2 if f["rule_key"] == "net_reconciliation")
        self.assertFalse(recon2["passed"])
        self.assertGreaterEqual(recon2["failed"], 1)
