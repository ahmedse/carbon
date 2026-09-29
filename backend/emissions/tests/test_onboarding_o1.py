"""O1 evaluator. No database. Kilograms come only from the summary argument."""
from __future__ import annotations

import unittest

from emissions.onboarding_o1 import evaluate_o1


def _period(**extra):
    row = {
        "id": 7,
        "name": "AY 2026",
        "status": "open",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "period_type": "annual",
        "organizational_boundary": 3,
    }
    row.update(extra)
    return row


class EvaluateO1Tests(unittest.TestCase):
    def test_zero_open_periods_is_only_a_count(self):
        result = evaluate_o1(periods=[], boundaries=[], sources=[], statuses=[], summary=None)
        self.assertEqual(result["benchmark"], "O1")
        self.assertEqual(result["benchmark_status"], "open")
        self.assertIsNone(result["open_period_id"])
        self.assertFalse(result["writes"])
        self.assertEqual(result["checks"], [
            {"id": "CR-PER-01", "code": "open_period_count", "met": False, "count": 0},
        ])

    def test_two_open_periods_fail_closed(self):
        result = evaluate_o1(
            periods=[_period(), _period(id=8, name="Other")],
            boundaries=[], sources=[], statuses=[], summary={"total_calculations": 9, "by_scope": {"2": {"total_co2e_kg": 1500}}},
        )
        self.assertIsNone(result["open_period_id"])
        self.assertEqual(result["checks"][0]["code"], "open_period_count")
        self.assertEqual(result["checks"][0]["count"], 2)
        self.assertFalse(any(row["code"] == "summary_kg" for row in result["checks"]))

    def test_missing_sources_and_no_kilograms(self):
        result = evaluate_o1(
            periods=[_period(organizational_boundary=None)],
            boundaries=[], sources=[], statuses=[], summary={"total_calculations": 0, "by_scope": {}},
        )
        codes = [row["code"] for row in result["checks"]]
        self.assertIn("boundary_missing", codes)
        self.assertIn("source_missing", codes)
        self.assertIn("no_calculation", codes)
        self.assertNotIn("summary_kg", codes)
        missing = [row for row in result["checks"] if row["code"] == "source_missing"]
        self.assertEqual(
            [row["name"] for row in missing],
            ["Smart Village electricity", "Smart Village diesel"],
        )

    def test_diesel_stream_rejects_both_words(self):
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[{"id": 3, "name": "AASTMT operational", "consolidation_approach": "operational_control"}],
            sources=[{
                "id": 2, "source_name": "Smart Village diesel", "scope": 1,
                "description": "generators and fleet",
            }],
            statuses=[],
            summary=None,
        )
        self.assertTrue(any(row["code"] == "diesel_stream_both" for row in result["checks"]))
        self.assertTrue(any(row["code"] == "source_missing" and row["name"] == "Smart Village electricity" for row in result["checks"]))

    def test_summary_kilograms_are_copied_and_not_assured(self):
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[{"id": 3, "name": "AASTMT operational", "consolidation_approach": "operational_control"}],
            sources=[
                {"id": 1, "source_name": "Smart Village electricity", "scope": 2, "description": ""},
                {"id": 2, "source_name": "Smart Village diesel", "scope": 1, "description": "Campus generators"},
            ],
            statuses=[
                {"source_id": 1, "reporting_period_id": 7, "status": "declared", "linked_table_count": 0},
                {"source_id": 2, "reporting_period_id": 7, "status": "covered", "linked_table_count": 0},
            ],
            summary={"total_calculations": 2, "by_scope": {"2": {"total_co2e_kg": 1500.0}}},
        )
        kg = next(row for row in result["checks"] if row["code"] == "summary_kg")
        self.assertEqual(kg["kg"], "1500")
        self.assertEqual(kg["scope"], "2")
        self.assertTrue(any(row["code"] == "not_assured" and row["met"] is False for row in result["checks"]))
        self.assertTrue(any(row["code"] == "source_covered_invalid" for row in result["checks"]))
        self.assertTrue(any(row["code"] == "diesel_stream_met" and row["stream"] == "generators" for row in result["checks"]))

    def test_covered_with_links_is_met(self):
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[{"id": 3, "name": "AASTMT operational", "consolidation_approach": "operational_control"}],
            sources=[{"id": 1, "source_name": "Smart Village electricity", "scope": 2, "description": ""}],
            statuses=[{"source_id": 1, "reporting_period_id": 7, "status": "covered", "linked_table_count": 1}],
            summary={"total_calculations": 1, "by_scope": {}},
        )
        covered = next(row for row in result["checks"] if row["code"] == "source_covered")
        self.assertTrue(covered["met"])
        self.assertTrue(any(row["code"] == "not_assured" for row in result["checks"]))
        self.assertFalse(any(row["code"] == "summary_kg" for row in result["checks"]))
