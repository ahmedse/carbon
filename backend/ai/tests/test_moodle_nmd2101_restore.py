"""NMD2101 restore gold. The counts are the production course, not extracted pages."""
from pathlib import Path

import yaml

_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "nmd2101_restore.yaml"


def test_restore_gold_names_the_production_counts():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    assert gold["shortname"] == "NMD2101"
    assert gold["users"] == 0
    assert gold["modules"] == {"page": 30, "label": 42, "url": 61, "resource": 142}
    assert "Revisions" in gold["hidden_section_names"]
    assert "extracted-text pages instead of resource files" in gold["fail_if"]
    assert "course id 6 required" in gold["fail_if"]
