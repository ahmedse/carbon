"""O1 evaluator. No database. Kilograms come only from the summary argument."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from emissions.onboarding_o1 import (
    _benchmark_status,
    activity_matches_close,
    evaluate_o1,
    o1_linked_summary,
)


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


def _boundary():
    return {"id": 3, "name": "AASTMT operational", "consolidation_approach": "operational_control"}


def _both_o1_sources():
    return [
        {"id": 1, "source_name": "Smart Village electricity", "scope": 2, "description": ""},
        {"id": 2, "source_name": "Smart Village diesel", "scope": 1, "description": "Campus generators"},
    ]


class EvaluateO1Tests(unittest.TestCase):
    def test_zero_open_periods_is_only_a_count(self):
        # O1-OBS-SHAPE
        result = evaluate_o1(periods=[], boundaries=[], sources=[], statuses=[], summary=None)
        self.assertEqual(result["benchmark"], "O1")
        self.assertEqual(result["benchmark_status"], "open")
        self.assertIsNone(result["open_period_id"])
        self.assertFalse(result["writes"])
        self.assertEqual(result["checks"], [
            {"id": "CR-PER-01", "code": "open_period_count", "met": False, "count": 0, "periods": []},
        ])

    def test_passed_only_when_the_source_series_matches(self):
        close = {
            "period": {"start_date": "2023-07-01", "end_date": "2024-06-30"},
            "electricity_kwh": {"2023-07-01": 284379, "2023-08-01": 233019},
            "diesel_litres": 3000,
        }
        period = {"start_date": "2023-07-01", "end_date": "2024-06-30"}
        electricity = [
            {"month": "2023-07-01", "kwh": 284379, "on_period": True},
            {"month": "2023-08-01", "kwh": 233019, "on_period": True},
            {"month": "2023-01-01", "kwh": 235992, "on_period": False},
        ]
        diesel = [
            {"litres": 3000, "on_period": True},
            {"litres": 980, "on_period": False},
        ]
        self.assertTrue(activity_matches_close(period, electricity, diesel, close))
        self.assertFalse(activity_matches_close(
            {"start_date": "2023-07-01", "end_date": "2026-06-30"},
            electricity,
            diesel,
            close,
        ))
        extra = electricity + [{"month": "2025-07-01", "kwh": 311902, "on_period": True}]
        self.assertFalse(activity_matches_close(period, extra, diesel, close))

    def test_source_backing_does_not_pass_while_a_check_fails(self):
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[_boundary()],
            sources=_both_o1_sources(),
            statuses=[],
            summary=None,
            source_backed=True,
        )
        self.assertEqual(result["benchmark_status"], "open")
        backed = next(row for row in result["checks"] if row["code"] == "source_backed")
        self.assertTrue(backed["met"])

    def test_passed_needs_source_backing_and_not_assured_unmet(self):
        checks = [
            {"code": "boundary_met", "met": True},
            {"code": "not_assured", "met": False},
            {"code": "source_backed", "met": True},
        ]
        self.assertEqual(_benchmark_status(checks, True), "passed")
        self.assertEqual(_benchmark_status(checks, False), "open")
        assured = [dict(row) for row in checks]
        assured[1] = {"code": "not_assured", "met": True}
        self.assertEqual(_benchmark_status(assured, True), "open")

    def test_two_open_periods_fail_closed(self):
        # O1-COR-EVAL
        result = evaluate_o1(
            periods=[_period(), _period(id=8, name="Other")],
            boundaries=[], sources=[], statuses=[], summary={"total_calculations": 9, "by_scope": {"2": {"total_co2e_kg": 1500}}},
        )
        self.assertIsNone(result["open_period_id"])
        self.assertEqual(result["checks"][0]["code"], "open_period_count")
        self.assertEqual(result["checks"][0]["count"], 2)
        self.assertEqual(result["checks"][0]["periods"], [
            {
                "id": 7,
                "name": "AY 2026",
                "period_type": "annual",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "status": "open",
            },
            {
                "id": 8,
                "name": "Other",
                "period_type": "annual",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "status": "open",
            },
        ])
        self.assertEqual(len(result["checks"]), 1)
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

    def test_o1_linked_summary_is_not_the_period_mix(self):
        # O1-COR-QUOTE
        summary = o1_linked_summary({2: "1254223.105920", 1: "19456.800000"}, 24)
        self.assertEqual(summary["quote"], "o1_linked_tables")
        self.assertEqual(summary["total_calculations"], 24)
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[_boundary()],
            sources=_both_o1_sources(),
            statuses=[],
            summary=summary,
        )
        kilograms = {
            row["scope"]: row["kg"]
            for row in result["checks"]
            if row["code"] == "summary_kg"
        }
        self.assertEqual(kilograms["2"], "1254223.105920")
        self.assertEqual(kilograms["1"], "19456.800000")
        self.assertNotIn("405271", json.dumps(result))
        self.assertNotIn("5269592", json.dumps(result))
        assured = next(row for row in result["checks"] if row["code"] == "not_assured")
        self.assertFalse(assured["met"])

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
        self.assertEqual(kg["method"], "location-based")
        self.assertTrue(any(row["code"] == "not_assured" and row["met"] is False for row in result["checks"]))
        self.assertTrue(any(row["code"] == "source_covered_invalid" for row in result["checks"]))
        self.assertTrue(any(row["code"] == "diesel_stream_met" and row["stream"] == "generators" for row in result["checks"]))

    def test_other_campus_declared_excluded_and_not_material(self):
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[{"id": 3, "name": "AASTMT operational", "consolidation_approach": "operational_control"}],
            sources=[
                {"id": 10, "source_name": "South Valley electricity", "scope": 2, "description": ""},
                {"id": 11, "source_name": "Abu Qir diesel", "scope": 1, "description": "generators"},
                {"id": 12, "source_name": "Alamein electricity", "scope": 2, "description": ""},
            ],
            statuses=[
                {"source_id": 10, "reporting_period_id": 7, "status": "declared"},
                {
                    "source_id": 11, "reporting_period_id": 7, "status": "excluded",
                    "exclusion_reason": "insufficient_data",
                },
                {
                    "source_id": 12, "reporting_period_id": 7, "status": "excluded",
                    "exclusion_reason": "not_material",
                },
            ],
            summary={"total_calculations": 0, "by_scope": {}},
        )
        by_code = {(row["code"], row.get("name")): row for row in result["checks"]}
        self.assertTrue(by_code[("other_campus_declared", "South Valley")]["met"])
        self.assertTrue(by_code[("other_campus_excluded", "Abu Qir")]["met"])
        self.assertEqual(by_code[("other_campus_excluded", "Abu Qir")]["reason"], "insufficient_data")
        self.assertFalse(by_code[("other_campus_not_material", "Alamein")]["met"])

    def test_declared_with_an_exclusion_reason_is_not_met(self):
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[{"id": 3, "name": "AASTMT operational", "consolidation_approach": "operational_control"}],
            sources=[{"id": 10, "source_name": "South Valley electricity", "scope": 2, "description": ""}],
            statuses=[{
                "source_id": 10, "reporting_period_id": 7, "status": "declared",
                "exclusion_reason": "insufficient_data",
            }],
            summary=None,
        )
        south = next(row for row in result["checks"] if row.get("name") == "South Valley")
        self.assertEqual(south["code"], "other_campus_no_status")
        self.assertFalse(south["met"])
        self.assertFalse(any(row["code"] == "summary_kg" for row in result["checks"]))

    def test_other_campus_excluded_other_without_notes(self):
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[{"id": 3, "name": "AASTMT operational", "consolidation_approach": "operational_control"}],
            sources=[
                {"id": 10, "source_name": "South Valley electricity", "scope": 2, "description": ""},
            ],
            statuses=[
                {
                    "source_id": 10, "reporting_period_id": 7, "status": "excluded",
                    "exclusion_reason": "other", "notes": "",
                },
            ],
            summary={"total_calculations": 0, "by_scope": {}},
        )
        campus = [row for row in result["checks"] if row["code"].startswith("other_campus")]
        self.assertEqual(len(campus), 3)
        south = next(row for row in campus if row["name"] == "South Valley")
        self.assertEqual(south["code"], "other_campus_excluded_notes")
        self.assertFalse(south["met"])
        abu = next(row for row in campus if row["name"] == "Abu Qir")
        self.assertEqual(abu["code"], "other_campus_absent")
        alamein = next(row for row in campus if row["name"] == "Alamein")
        self.assertEqual(alamein["code"], "other_campus_absent")

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

    def test_factors_empty_both_missing_no_factor_value_key(self):
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[_boundary()],
            sources=_both_o1_sources(),
            statuses=[],
            summary={"total_calculations": 0, "by_scope": {}},
            factors=[],
            goals=[],
        )
        missing = [row for row in result["checks"] if row["code"] == "factor_missing"]
        self.assertEqual(len(missing), 2)
        self.assertEqual(missing[0]["id"], "CR-FAC-01")
        self.assertEqual(missing[0]["name"], "Smart Village electricity")
        self.assertEqual(missing[0]["scope"], 2)
        self.assertEqual(missing[0]["unit"], "kWh")
        self.assertEqual(missing[1]["name"], "Smart Village diesel")
        self.assertEqual(missing[1]["scope"], 1)
        self.assertEqual(missing[1]["unit"], "litre")
        blob = json.dumps(result)
        self.assertNotIn("factor_value", blob)

    def test_electricity_inactive_diesel_still_missing(self):
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[_boundary()],
            sources=_both_o1_sources(),
            statuses=[],
            summary=None,
            factors=[{
                "id": 5, "name": "Grid off", "scope": 2, "activity_unit": "kWh",
                "country_code": "EGY", "source": "EEHC", "is_active": False,
            }],
        )
        inactive = next(row for row in result["checks"] if row["code"] == "factor_inactive")
        self.assertEqual(inactive["id"], "CR-FAC-01")
        self.assertEqual(inactive["record_id"], 5)
        self.assertEqual(inactive["name"], "Grid off")
        diesel = next(
            row for row in result["checks"]
            if row["code"] == "factor_missing" and row["name"] == "Smart Village diesel"
        )
        self.assertFalse(diesel["met"])

    def test_electricity_usa_then_egy_met_picks_lowest_eligible(self):
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[_boundary()],
            sources=_both_o1_sources(),
            statuses=[],
            summary=None,
            factors=[
                {
                    "id": 10, "name": "US grid", "scope": 2, "activity_unit": "kWh",
                    "country_code": "USA", "source": "EPA", "is_active": True,
                },
                {
                    "id": 11, "name": "EEHC Egypt", "scope": 2, "activity_unit": "kWh",
                    "country_code": "EGY", "source": "EEHC 2024", "is_active": True,
                },
            ],
        )
        self.assertFalse(any(row["code"] == "factor_country" for row in result["checks"]))
        met = next(row for row in result["checks"] if row["code"] == "factor_met")
        self.assertEqual(met["id"], "CR-FAC-01")
        self.assertEqual(met["record_id"], 11)
        self.assertEqual(met["name"], "EEHC Egypt")
        self.assertEqual(met["country_code"], "EGY")
        self.assertEqual(met["scope"], 2)
        self.assertEqual(met["unit"], "kWh")

    def test_diesel_liter_blank_source_factor_source_blank(self):
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[_boundary()],
            sources=_both_o1_sources(),
            statuses=[],
            summary=None,
            factors=[{
                "id": 20, "name": "Diesel factor", "scope": 1, "activity_unit": "liter",
                "country_code": "EGY", "source": "  ", "is_active": True,
            }],
        )
        blank = next(row for row in result["checks"] if row["code"] == "factor_source_blank")
        self.assertEqual(blank["id"], "CR-FAC-01")
        self.assertEqual(blank["record_id"], 20)
        self.assertEqual(blank["name"], "Diesel factor")

    def test_both_sources_goals_empty_coverage_goal_absent(self):
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[_boundary()],
            sources=_both_o1_sources(),
            statuses=[],
            summary=None,
            factors=[],
            goals=[],
        )
        absent = next(row for row in result["checks"] if row["code"] == "coverage_goal_absent")
        self.assertFalse(absent["met"])
        self.assertEqual(absent["id"], "CR-COV-01")

    def test_coverage_goal_completeness_strips_target_coverage_pct(self):
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[_boundary()],
            sources=_both_o1_sources(),
            statuses=[],
            summary=None,
            goals=[{
                "id": 1, "name": "Org coverage", "scope": "1+2",
                "completeness_definition": "absolute", "min_quality_tier": 4,
                "status": "draft", "target_year": 2026, "target_coverage_pct": 95,
            }],
        )
        row = next(row for row in result["checks"] if row["code"] == "coverage_goal_completeness")
        self.assertEqual(row["completeness"], "absolute")
        self.assertNotIn("target_coverage_pct", row)
        self.assertNotIn("target_coverage_pct", json.dumps(result))

    def test_coverage_goal_prefers_draft_over_active_sbti(self):
        # O1-COR-GOAL
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[_boundary()],
            sources=_both_o1_sources(),
            statuses=[],
            summary=None,
            goals=[
                {
                    "id": 1, "name": "Scope 1+2 Coverage", "scope": "1+2",
                    "completeness_definition": "materiality_bounded",
                    "min_quality_tier": 3, "status": "active", "target_year": 2026,
                },
                {
                    "id": 9, "name": "O1 Smart Village", "scope": "1+2",
                    "completeness_definition": "materiality_bounded",
                    "min_quality_tier": 4, "status": "draft", "target_year": 2026,
                },
            ],
        )
        met = next(row for row in result["checks"] if row["code"] == "coverage_goal_met")
        self.assertEqual(met["record_id"], 9)
        self.assertEqual(met["name"], "O1 Smart Village")
        self.assertNotIn("target_coverage_pct", met)

    def test_coverage_goal_met_fields(self):
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[_boundary()],
            sources=_both_o1_sources(),
            statuses=[],
            summary=None,
            goals=[{
                "id": 2, "name": "Smart Village goal", "scope": "1+2",
                "completeness_definition": "materiality_bounded", "min_quality_tier": 4,
                "status": "draft", "target_year": 2026,
            }],
        )
        met = next(row for row in result["checks"] if row["code"] == "coverage_goal_met")
        self.assertEqual(met["id"], "CR-COV-01")
        self.assertEqual(met["record_id"], 2)
        self.assertEqual(met["scope"], "1+2")
        self.assertEqual(met["completeness"], "materiality_bounded")
        self.assertEqual(met["tier"], 4)
        self.assertEqual(met["status"], "draft")
        self.assertEqual(met["target_year"], 2026)

    def test_two_open_periods_ignores_factors_and_summary_kg(self):
        # O1-PRF-STOP
        result = evaluate_o1(
            periods=[_period(), _period(id=8, name="Other")],
            boundaries=[],
            sources=[],
            statuses=[],
            summary={"total_calculations": 9, "by_scope": {"2": {"total_co2e_kg": 1500}}},
            factors=[{"id": 1, "name": "X", "scope": 2, "activity_unit": "kWh", "country_code": "EGY", "source": "S", "is_active": True}],
            goals=[{"id": 1, "name": "G", "scope": "1+2", "completeness_definition": "materiality_bounded", "min_quality_tier": 4, "status": "draft", "target_year": 2026}],
        )
        self.assertEqual(len(result["checks"]), 1)
        self.assertEqual(result["checks"][0]["code"], "open_period_count")
        self.assertFalse(any(row["code"] == "factor_met" for row in result["checks"]))
        self.assertFalse(any(row["code"] == "summary_kg" for row in result["checks"]))

    def test_evaluate_o1_is_idempotent(self):
        # O1-REL-HEAD
        kwargs = {
            "periods": [_period(), _period(id=8, name="Other")],
            "boundaries": [],
            "sources": [],
            "statuses": [],
            "summary": {"total_calculations": 9, "by_scope": {"2": {"total_co2e_kg": 1500}}},
            "factors": [
                {
                    "id": 1,
                    "name": "X",
                    "scope": 2,
                    "activity_unit": "kWh",
                    "country_code": "EGY",
                    "source": "S",
                    "is_active": True,
                }
            ],
            "goals": [
                {
                    "id": 1,
                    "name": "G",
                    "scope": "1+2",
                    "completeness_definition": "materiality_bounded",
                    "min_quality_tier": 4,
                    "status": "draft",
                    "target_year": 2026,
                }
            ],
        }
        first = evaluate_o1(**kwargs)
        second = evaluate_o1(**kwargs)
        self.assertEqual(first, second)
        self.assertFalse(first["writes"])
        self.assertEqual(len(first["checks"]), 1)
        self.assertEqual(first["checks"][0]["code"], "open_period_count")

    def test_neither_o1_source_no_coverage_goal_absent(self):
        result = evaluate_o1(
            periods=[_period()],
            boundaries=[_boundary()],
            sources=[{"id": 10, "source_name": "South Valley electricity", "scope": 2, "description": ""}],
            statuses=[],
            summary=None,
            goals=[],
        )
        self.assertFalse(any(row["code"] == "coverage_goal_absent" for row in result["checks"]))

    def test_onboarding_o1_module_does_not_import_people_or_engine(self):
        # O1-MNT-BOUND
        module_path = Path(__file__).resolve().parent.parent / "onboarding_o1.py"
        for line in module_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("from people"):
                self.fail(stripped)
            if "from ai.engine" in stripped:
                self.fail(stripped)
            if "import people" in stripped:
                self.fail(stripped)
