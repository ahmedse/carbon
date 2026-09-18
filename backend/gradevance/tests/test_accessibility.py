from gradevance.accessibility import accessibility_summary


def test_accessibility_checklist_has_bypass_blocks():
    summary = accessibility_summary()
    assert summary["standard"].startswith("WCAG")
    assert any(i["criterion"] == "2.4.1 Bypass Blocks" for i in summary["items"])
    assert "pass" in summary["counts"]
    assert summary["evidence_artifacts"]
    assert any(a.get("kind") == "checklist_json" for a in summary["evidence_artifacts"])
