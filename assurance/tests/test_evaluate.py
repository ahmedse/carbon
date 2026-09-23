"""Evaluator contracts. These tests do not run the People or emissions suites."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from assurance.evaluate import evaluate_packs, evaluate_rule, load_events
from assurance.load import load_brand, repo_root
from assurance.model import EvidenceEvent


class LoadTests(unittest.TestCase):
    def test_nibras_includes_platform(self):
        packs = load_brand(repo_root(), "nibras")
        ids = [pack.id for pack in packs]
        self.assertEqual(ids, ["nibras", "platform"])
        rule_ids = [rule.id for pack in packs for rule in pack.rules]
        self.assertIn("NR-PAY-02", rule_ids)
        self.assertIn("PL-CI-01", rule_ids)
        self.assertIn("NR-LV-04", rule_ids)

    def test_carbon_and_eduos_load(self):
        carbon = load_brand(repo_root(), "carbon")
        eduos = load_brand(repo_root(), "eduos")
        self.assertEqual(carbon[0].id, "carbon")
        self.assertEqual(eduos[0].id, "eduos")
        self.assertTrue(any(rule.id == "CR-INV-01" for rule in carbon[0].rules))
        self.assertTrue(any(rule.id == "ED-GOLD-01" for rule in eduos[0].rules))


class EvaluateTests(unittest.TestCase):
    def setUp(self):
        self.packs = load_brand(repo_root(), "nibras")
        self.by_id = {rule.id: rule for pack in self.packs for rule in pack.rules}

    def test_no_event_keeps_catalogue(self):
        state = evaluate_rule(self.by_id["NR-PAY-02"], [], "3d0c045")
        self.assertEqual(state.label, "not-executed")
        self.assertFalse(state.passed)

    def test_pass_requires_same_commit(self):
        event = EvidenceEvent("NR-PAY-02", "nibras", "3d0c045", "passed", "unit")
        state = evaluate_rule(self.by_id["NR-PAY-02"], [event], "3d0c045")
        self.assertEqual(state.label, "passed")
        stale = evaluate_rule(self.by_id["NR-PAY-02"], [event], "design+1")
        self.assertEqual(stale.label, "stale")
        self.assertFalse(stale.passed)

    def test_conflict_ignores_pass_event(self):
        from dataclasses import replace

        conflicted = replace(
            self.by_id["NR-LV-04"],
            catalogue="conflict",
            confidence="conflict",
        )
        event = EvidenceEvent("NR-LV-04", "nibras", "3d0c045", "passed", "unit")
        state = evaluate_rule(conflicted, [event], "3d0c045")
        self.assertEqual(state.label, "conflict")
        self.assertFalse(state.passed)

    def test_failed_and_unknown(self):
        failed = evaluate_rule(
            self.by_id["NR-PAY-01"],
            [EvidenceEvent("NR-PAY-01", "nibras", "abc", "failed", "seed")],
            "abc",
        )
        unknown = evaluate_rule(
            self.by_id["NR-PAY-01"],
            [EvidenceEvent("NR-PAY-01", "nibras", "abc", "unknown", "skipped")],
            "abc",
        )
        self.assertEqual(failed.label, "failed")
        self.assertEqual(unknown.label, "unknown")

    def test_ledger_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "rule_id": "NR-PAY-02",
                        "pack_id": "nibras",
                        "commit": "3d0c045",
                        "result": "passed",
                        "source": "people/tests/test_host_sod.py",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            rows = evaluate_packs(self.packs, load_events(path), "3d0c045")
        labels = {row.rule_id: row.label for row in rows}
        self.assertEqual(labels["NR-PAY-02"], "passed")
        self.assertEqual(labels["NR-PAY-01"], "not-executed")
        self.assertEqual(labels["NR-LV-04"], "configured")
        self.assertEqual(labels["PL-CI-01"], "configured")


if __name__ == "__main__":
    unittest.main()
