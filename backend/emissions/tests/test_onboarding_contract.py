"""AASTMT onboarding contract. Loads pack YAML. Does not touch the database."""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from assurance.load import load_pack, pack_dir, repo_root


ROOT = repo_root()
PACK = ROOT / "domain_packs" / "carbon"
RULES = (
    "CR-INV-01",
    "CR-BND-01",
    "CR-PER-01",
    "CR-SRC-01",
    "CR-FAC-01",
    "CR-COV-01",
    "CR-EXC-01",
    "CR-DQ-01",
    "CR-PULSE-01",
    "CR-WRITE-01",
)


class OnboardingContractTests(unittest.TestCase):
    def test_rules_load_and_do_not_block_release(self):
        # O1-GOV-CONTRACT
        pack = load_pack(pack_dir(ROOT, "carbon"))
        by_id = {rule.id: rule for rule in pack.rules}
        missing = [rule_id for rule_id in RULES if rule_id not in by_id]
        self.assertEqual(missing, [])
        for rule_id in RULES:
            rule = by_id[rule_id]
            self.assertFalse(rule.blocks_release, rule_id)
            self.assertEqual(rule.catalogue, "planned", rule_id)
            self.assertNotEqual(rule.owner, "unconfirmed", rule_id)

    def test_o1_leaf_is_open(self):
        path = PACK / "assurance" / "benchmarks" / "O1-smart-village.yaml"
        text = path.read_text(encoding="utf-8")
        self.assertIn("id: O1", text)
        self.assertIn("status: passed", text)
        data = yaml.safe_load(text)
        names = [row["name"] for row in data["sources"]]
        self.assertEqual(names, ["Smart Village electricity", "Smart Village diesel"])
        closed = {row["id"] for row in data["closed"]}
        self.assertEqual(closed, {"O2", "O3", "O4", "O5", "P1", "P2"})
        for row in data["closed"]:
            self.assertEqual(row["status"], "closed")

    def test_twelve_principles_bind_rules(self):
        data = yaml.safe_load((PACK / "assurance" / "principles.yaml").read_text(encoding="utf-8"))
        ids = [row["id"] for row in data["principles"]]
        self.assertEqual(ids, [f"P-{i:02d}" for i in range(1, 13)])
        self.assertEqual(data["target"], "O1")

    def test_principles_and_rules_name_the_p12_sentence(self):
        # P-12. A row is not ready without target, product, evidence, date, limit.
        principles = yaml.safe_load(
            (PACK / "assurance" / "principles.yaml").read_text(encoding="utf-8")
        )
        for row in principles["principles"]:
            for key in ("target", "product", "evidence", "locked", "limit"):
                self.assertTrue(str(row.get(key, "")).strip(), f"{row['id']} {key}")
            self.assertEqual(row["target"], "O1", row["id"])
            self.assertEqual(row["product"], "Carbon on AASTMT", row["id"])
        for rule_id in RULES:
            raw = yaml.safe_load(
                (PACK / "assurance" / "rules" / f"{rule_id}.yaml").read_text(encoding="utf-8")
            )
            for key in ("target", "product", "evidence", "locked", "limit"):
                self.assertTrue(str(raw.get(key, "")).strip(), f"{rule_id} {key}")
            self.assertEqual(raw["target"], "O1", rule_id)
            self.assertEqual(raw["product"], "Carbon on AASTMT", rule_id)
            self.assertEqual(raw["catalogue"], "planned", rule_id)

    def test_process_steps_match_the_leaf(self):
        data = yaml.safe_load(
            (PACK / "processes" / "inventory.onboarding.lifecycle.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            [step["id"] for step in data["steps"]],
            [
                "name_boundary",
                "open_period",
                "declare_sources",
                "bind_factors",
                "enter_activity",
                "calculate",
                "cover_or_exclude",
                "verify_quote",
            ],
        )
        self.assertEqual(data["benchmark"], "O1")

    def test_write_tools_require_confirmation(self):
        instance = yaml.safe_load((PACK / "instance.yaml").read_text(encoding="utf-8"))
        writes = [
            entry for entry in instance["api_catalog"]
            if str(entry.get("method", "GET")).upper() != "GET"
        ]
        self.assertGreaterEqual(len(writes), 1)
        for entry in writes:
            self.assertTrue(entry.get("requires_confirmation"), entry["name"])
            self.assertTrue(entry.get("requires_auth"), entry["name"])

    def test_ladder_subjects_point_at_files_that_exist(self):
        ladder = yaml.safe_load((ROOT / "assurance" / "carbon" / "ladder.yaml").read_text(encoding="utf-8"))
        subjects = {row["id"]: row for row in ladder["subjects"]}
        self.assertIn("carbon.journey.onboarding", subjects)
        self.assertIn("carbon.pack", subjects)
        for subject in (subjects["carbon.journey.onboarding"], subjects["carbon.pack"]):
            for rel in subject["paths"]:
                self.assertTrue((ROOT / rel).exists(), rel)
        evidence = ROOT / "docs" / "carbon" / "evidence" / "O1-smart-village.json"
        self.assertFalse(evidence.exists(), "live O1 evidence must not be invented")
