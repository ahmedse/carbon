"""Probe layer. No Django, no people imports."""

from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from assurance.load import repo_root
from assurance.oracles.conservation import display_remaining, signed_remaining
from assurance.oracles.formula import evaluate
from assurance.probes.run import run_pack, write_ledger


class FormulaOracleTests(unittest.TestCase):
    def test_hand_cases(self):
        self.assertEqual(
            evaluate("sum", {"components": ["basic"]}, {"basic": "1000.000"}),
            Decimal("1000.000"),
        )
        self.assertEqual(
            evaluate("multiply", {"a": "rate", "b": "hours"}, {"rate": "1.500", "hours": "8"}),
            Decimal("12.000"),
        )
        self.assertEqual(
            evaluate(
                "tiered_accrual",
                {
                    "base_inputs": ["basic_salary"],
                    "years_input": "service_years",
                    "divisor": "26",
                    "tiers": [
                        {"up_to": 5, "days_per_year": 15},
                        {"up_to": None, "days_per_year": 30},
                    ],
                },
                {"basic_salary": "780.000", "service_years": "5"},
            ),
            Decimal("2250.000"),
        )


class ConservationTests(unittest.TestCase):
    def test_overdraw_is_signed_not_display(self):
        self.assertEqual(signed_remaining(20, 0, 15, 10), Decimal("-5"))
        self.assertEqual(display_remaining(20, 0, 15, 10), Decimal("0"))


class NibrasProbeTests(unittest.TestCase):
    def test_probe_run_writes_nibras_host_passes(self):
        root = repo_root()
        findings = run_pack(root, "nibras")
        by_rule = {}
        for finding in findings:
            by_rule.setdefault(finding.rule_id, []).append(finding.result)
        self.assertEqual(by_rule["NR-HONEST-01"], ["passed"])
        self.assertEqual(by_rule["NR-CALC-01"], ["passed"])
        self.assertEqual(by_rule["NR-BAL-01"], ["passed"])
        self.assertEqual(by_rule["NR-PAY-01"], ["passed"])
        self.assertEqual(by_rule["NR-PAY-02"], ["passed"])
        self.assertEqual(by_rule["NR-PAY-03"], ["passed"])
        self.assertEqual(by_rule["NR-WPS-02"], ["passed"])
        self.assertEqual(by_rule["NR-EOSI-01"], ["passed"])
        self.assertEqual(by_rule["NR-LV-04"], ["passed"])
        self.assertEqual(by_rule["NR-PAY-04"], ["passed"])
        self.assertEqual(by_rule["NR-NAT-01"], ["passed", "passed"])
        self.assertEqual(by_rule["NR-GOSI-01"], ["passed"])
        self.assertEqual(by_rule["NR-ONB-01"], ["passed"])
        self.assertEqual(by_rule["NR-LOAN-01"], ["passed"])
        self.assertEqual(by_rule["NR-360-01"], ["passed"])

        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "events.jsonl"
            write_ledger(ledger, findings, "probe-sha")
            text = ledger.read_text(encoding="utf-8")
        self.assertIn("NR-EOSI-01", text)
        self.assertIn('"result": "passed"', text)


class PlatformProbeTests(unittest.TestCase):
    def test_platform_bindings(self):
        root = repo_root()
        findings = run_pack(root, "platform")
        by_rule = {}
        for finding in findings:
            by_rule.setdefault(finding.rule_id, []).append(finding.result)
        self.assertEqual(by_rule["PL-VERIFY-01"], ["passed"])
        self.assertEqual(by_rule["PL-CI-01"], ["passed"])
        self.assertNotIn("PL-SSE-01", by_rule)


if __name__ == "__main__":
    unittest.main()
