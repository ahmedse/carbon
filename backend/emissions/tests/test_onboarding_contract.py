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
    "CR-S2-01",
    "CR-OFF-01",
    "CR-REST-01",
    "CR-OWN-01",
    "CR-S2-02",
    "CR-CAM-01",
    "CR-S3-01",
    "CR-ASR-01",
    "CR-DIS-01",
    "CR-INT-01",
)

CLOSED_LEAF_TARGETS = {
    "CR-CAM-01": "O2",
    "CR-S3-01": "O5",
    "CR-ASR-01": "P1",
    "CR-DIS-01": "P2",
    "CR-INT-01": "O2",
}


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
        self.assertEqual(closed, {"O2", "O3", "O4", "O5", "P1", "P2", "S2MB"})
        for row in data["closed"]:
            self.assertEqual(row["status"], "closed")
            for key in ("target", "product", "evidence", "locked", "limit"):
                self.assertTrue(str(row.get(key, "")).strip(), f"{row['id']} {key}")

    def test_twenty_five_principles_bind_rules(self):
        data = yaml.safe_load((PACK / "assurance" / "principles.yaml").read_text(encoding="utf-8"))
        ids = [row["id"] for row in data["principles"]]
        self.assertEqual(ids, [f"P-{i:02d}" for i in range(1, 26)])
        self.assertEqual(data["target"], "O1")

    def test_principles_and_rules_name_the_p12_sentence(self):
        # P-12. A row is not ready without target, product, evidence, date, limit.
        principles = yaml.safe_load(
            (PACK / "assurance" / "principles.yaml").read_text(encoding="utf-8")
        )
        o1_ids = {f"P-{i:02d}" for i in range(1, 21)}
        later = {
            "P-21": "O1",
            "P-22": "O2",
            "P-23": "O5",
            "P-24": "P2",
            "P-25": "P1",
        }
        for row in principles["principles"]:
            for key in ("target", "product", "evidence", "locked", "limit"):
                self.assertTrue(str(row.get(key, "")).strip(), f"{row['id']} {key}")
            self.assertEqual(row["product"], "Carbon on AASTMT", row["id"])
            if row["id"] in o1_ids:
                self.assertEqual(row["target"], "O1", row["id"])
            else:
                self.assertEqual(row["target"], later[row["id"]], row["id"])
        for rule_id in RULES:
            raw = yaml.safe_load(
                (PACK / "assurance" / "rules" / f"{rule_id}.yaml").read_text(encoding="utf-8")
            )
            for key in ("target", "product", "evidence", "locked", "limit"):
                self.assertTrue(str(raw.get(key, "")).strip(), f"{rule_id} {key}")
            self.assertEqual(raw["product"], "Carbon on AASTMT", rule_id)
            self.assertEqual(raw["catalogue"], "planned", rule_id)
            expected_target = CLOSED_LEAF_TARGETS.get(rule_id, "O1")
            self.assertEqual(raw["target"], expected_target, rule_id)
            self.assertTrue(str(raw.get("failure", "")).strip(), f"{rule_id} failure")

    def test_closed_campus_leaves_name_sources(self):
        expected = {
            "O2": ("South Valley electricity", "South Valley diesel"),
            "O3": ("Abu Qir electricity", "Abu Qir diesel"),
            "O4": ("New Alamein electricity", "New Alamein diesel"),
        }
        for leaf_id, names in expected.items():
            path = PACK / "assurance" / "benchmarks" / {
                "O2": "O2-south-valley.yaml",
                "O3": "O3-abu-qir.yaml",
                "O4": "O4-new-alamein.yaml",
            }[leaf_id]
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(data["id"], leaf_id)
            self.assertEqual(data["status"], "closed")
            self.assertEqual(tuple(row["name"] for row in data["sources"]), names)
            self.assertIsNone(data["close"]["kilograms"])
            self.assertFalse(data["close"]["evidence_file_exists"])
            evidence_file = ROOT / data["close"]["evidence_file"]
            self.assertFalse(evidence_file.exists(), evidence_file)
            for key in ("target", "product", "evidence", "locked", "limit"):
                self.assertTrue(str(data.get(key, "")).strip(), f"{leaf_id} {key}")

    def test_discovered_files_are_quoted_and_not_calculated(self):
        # CR-INT-01. Numbers below are cells in the named CSV, not a kilogram.
        o2 = yaml.safe_load(
            (PACK / "assurance" / "benchmarks" / "O2-south-valley.yaml").read_text(encoding="utf-8")
        )
        quoted = o2["close"]["quoted_activity"]
        scope12 = (ROOT / o2["close"]["discovered_files"][0]["path"]).read_text(encoding="utf-8")
        self.assertIn(",700000", scope12)
        self.assertIn(",25000", scope12)
        self.assertIn(",125500", scope12)
        self.assertIn(",3680", scope12)
        self.assertEqual(quoted["electricity_kwh"], "700000")
        self.assertEqual(quoted["generators_diesel_l"], "25000")
        self.assertEqual(quoted["mobile_diesel_l"], "125500")
        self.assertIsNone(o2["close"]["kilograms"])
        self.assertEqual(o2["close"]["tonnes_co2e_on_panel"], "0")
        self.assertTrue((ROOT / o2["close"]["discovered_files"][0]["path"]).is_file())
        o3 = yaml.safe_load(
            (PACK / "assurance" / "benchmarks" / "O3-abu-qir.yaml").read_text(encoding="utf-8")
        )
        electricity = (ROOT / o3["close"]["discovered_files"][0]["path"]).read_text(encoding="utf-8")
        self.assertIn("2026-06-01,", electricity)
        self.assertIsNone(o3["close"]["kilograms"])
        self.assertEqual(o3["close"]["june_electricity"], "blank")
        o5 = yaml.safe_load(
            (PACK / "assurance" / "benchmarks" / "O5-scope3-waste.yaml").read_text(encoding="utf-8")
        )
        inventory = (ROOT / o5["activity_line"]["file"]).read_text(encoding="utf-8")
        self.assertIn(",73.0", inventory)
        self.assertFalse((ROOT / o5["close"]["factor_file"]).exists())
        self.assertIsNone(o5["close"]["kilograms"])

    def test_o5_is_category_5_waste(self):
        data = yaml.safe_load(
            (PACK / "assurance" / "benchmarks" / "O5-scope3-waste.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(data["id"], "O5")
        self.assertEqual(data["status"], "closed")
        self.assertEqual(data["scope3"]["category"], 5)
        self.assertEqual(data["sources"][0]["name"], "Smart Village waste disposal")
        self.assertEqual(data["sources"][0]["activity_unit"], "tonne")
        self.assertIsNone(data["activity_line"]["kilograms"])
        self.assertIsNone(data["close"]["kilograms"])
        for key in ("target", "product", "evidence", "locked", "limit"):
            self.assertTrue(str(data.get(key, "")).strip(), f"O5 {key}")

    def test_p1_and_p2_stay_closed_with_p12_fields(self):
        for name, leaf_id in (("P1-assurance.yaml", "P1"), ("P2-disclosure.yaml", "P2")):
            data = yaml.safe_load((PACK / "assurance" / "benchmarks" / name).read_text(encoding="utf-8"))
            self.assertEqual(data["id"], leaf_id)
            self.assertEqual(data["status"], "closed")
            for key in ("target", "product", "evidence", "locked", "limit"):
                self.assertTrue(str(data.get(key, "")).strip(), f"{leaf_id} {key}")
        p1 = yaml.safe_load((PACK / "assurance" / "benchmarks" / "P1-assurance.yaml").read_text(encoding="utf-8"))
        self.assertFalse(p1["not_assured"]["met"])
        self.assertIsNone(p1["vvb_pack"]["assurer_name"])
        p2 = yaml.safe_load((PACK / "assurance" / "benchmarks" / "P2-disclosure.yaml").read_text(encoding="utf-8"))
        self.assertEqual(p2["endpoint"], "GET /carbon-api/carbon/disclosure/")
        self.assertFalse(p2["shared_payload"]["new_kilogram"])
        self.assertIn("Not a filing", str(p2.get("limit", "")))

    def test_market_based_leaf_stays_absent(self):
        data = yaml.safe_load(
            (PACK / "assurance" / "benchmarks" / "S2-market-based.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(data["id"], "S2MB")
        self.assertEqual(data["status"], "closed")
        self.assertFalse(data["market_based"]["present"])
        self.assertIsNone(data["market_based"]["total_co2e_kg"])
        self.assertIsNone(data["market_based"]["contractual_factor_id"])
        for key in ("target", "product", "evidence", "locked", "limit"):
            self.assertTrue(str(data.get(key, "")).strip(), key)
        self.assertIn("residual mix", data["blocker"])
        self.assertNotIn("0 kg", str(data["market_based"].get("total_co2e_kg")))

    def test_carbon_ui_l2_rule_8_sentence(self):
        data = yaml.safe_load((PACK / "assurance" / "ladder_cells.yaml").read_text(encoding="utf-8"))
        ui = next(row for row in data["subjects"] if row["id"] == "carbon.ui")
        self.assertEqual(ui["current_honest_level"], "L2")
        cell = next(row for row in ui["cells"] if row["level"] == "L2")
        for key in ("target", "product", "evidence", "locked", "limit"):
            self.assertTrue(str(cell.get(key, "")).strip(), key)
        self.assertEqual(cell["product"], "Carbon on AASTMT")
        self.assertIn("ChairmanDashboard.jsx", cell["evidence"])
        self.assertIn("CarbonConsolePage.jsx", cell["evidence"])
        self.assertIn("RULE 8", cell["meaning"])
        self.assertEqual(cell["claim"], "current")
        self.assertIn("do not set page-local fontSize", cell["meaning"])
        self.assertIn("Do not raise", cell["limit"])
        self.assertEqual(ui["current_honest_level"], "L2")

    def test_ladder_cells_forbid_l6_l7(self):
        data = yaml.safe_load((PACK / "assurance" / "ladder_cells.yaml").read_text(encoding="utf-8"))
        self.assertEqual(data["do_not_claim"], ["L6", "L7"])
        by_id = {row["id"]: row for row in data["subjects"]}
        self.assertEqual(by_id["carbon.module.emissions"]["current_honest_level"], "L2")
        self.assertEqual(by_id["carbon.ui"]["current_honest_level"], "L2")
        self.assertEqual(by_id["carbon.pack"]["current_honest_level"], "L2")
        self.assertEqual(by_id["carbon.journey.onboarding"]["current_honest_level"], "L5")
        self.assertFalse(by_id["carbon.journey.onboarding"]["production_scored"])
        for subject in data["subjects"]:
            for key in ("target", "product", "evidence", "locked", "limit"):
                self.assertTrue(str(subject.get(key, "")).strip(), f"{subject['id']} {key}")
            claims = {cell["level"]: cell["claim"] for cell in subject["cells"]}
            self.assertEqual(claims["L6"], "forbidden")
            self.assertEqual(claims["L7"], "forbidden")

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
