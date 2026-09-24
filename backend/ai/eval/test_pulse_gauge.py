"""Gauge + pack contract + portability meters (ADR-0049 P14 · ADR-0050). No Django."""
from __future__ import annotations

import json
from pathlib import Path

from ai.eval.harness_budget import (
    _COUNT_KEYS,
    _is_phrase_table_line,
    _line_tokens,
    measure,
    pack_ids,
)
from ai.eval.pack_contract import check_all, check_pack
from ai.eval.pulse_gauge import (
    RATCHET_KEYS,
    ratchet_violations,
    series_row,
    snapshot,
    upsert_row,
)


def test_new_meters_are_measured_as_ints():
    result = measure()
    for key in ("routing_phrase_sets", "domain_terms_in_core", "brand_literals_in_core"):
        assert key in _COUNT_KEYS
        assert isinstance(result[key], int) and result[key] >= 0, key


def test_phrase_table_detector_shape():
    assert _is_phrase_table_line('_APPLY_SHORT: frozenset[str] = frozenset({"go", "apply"})')
    assert _is_phrase_table_line("_PHRASES: tuple[str, ...] = (", '    "fork",\n    "replan",')
    assert _is_phrase_table_line('_WORDS = frozenset({"yes", "ok"})')
    # Not phrase routing: prompts, labels, indented / lowercase / non-string tuples.
    assert not _is_phrase_table_line("_CLASSIFY_PROMPT = (", '    "You are…"')
    assert not _is_phrase_table_line('_DIAL_LABELS = {"a": "b"}')
    assert not _is_phrase_table_line('    _INNER = ("a",)')
    assert not _is_phrase_table_line("_SIZES = (1, 2, 3)")
    assert not _is_phrase_table_line("lower = frozenset({'x'})")


def test_domain_tokeniser_handles_arabic_and_english():
    assert "leave" in _line_tokens("if is_leave_topic(text):  # leave routing")
    assert "إجازة" in _line_tokens('needles = ("إجازة", "قرض")')
    assert "gosi" in _line_tokens("GOSI cap")


def test_pack_ids_come_from_domain_packs_dir():
    ids = pack_ids()
    assert {"nibras", "eduos", "carbon"} <= ids


def test_pack_contract_all_packs_green():
    rows, violations = check_all()
    assert violations == []
    assert {r["id"] for r in rows} >= {"nibras", "eduos", "carbon"}
    assert all(isinstance(r["version"], int) and r["version"] >= 1 for r in rows)


def test_pack_contract_flags_missing_manifest_and_bad_version(tmp_path: Path):
    pack = tmp_path / "acme"
    pack.mkdir()
    _, errs = check_pack(pack)
    assert errs == ["acme: pack.yaml missing"]
    (pack / "pack.yaml").write_text(
        "id: other\nversion: '1'\ndomain: x\ninstance: nowhere.yaml\ncompat: {}\nowns:\n  catalog: ../escape.yaml\n",
        encoding="utf-8",
    )
    _, errs = check_pack(pack)
    joined = "\n".join(errs)
    assert "must equal directory name" in joined
    assert "version must be an integer" in joined
    assert "instance file missing" in joined
    assert "compat.engine required" in joined
    assert "points outside the pack" in joined


def test_snapshot_and_series_row_shape():
    snap = snapshot("nibras")
    assert snap["instance"] == "nibras"
    assert set(snap["budget"]) == set(_COUNT_KEYS)
    assert snap["ladder"]["levels"]["L0"] in {"reached", "partial", "missing"}
    assert "L7" in snap["ladder"]["levels"]
    assert snap["packs"]["gate_pass"] is True
    assert snap["agent_plan"]["gate_pass"] is True
    assert snap["agent_plan"]["n"] >= 12
    assert snap["coverage"]["agent_plan_path"].startswith("bank ")
    row = series_row(snap)
    assert row["agent_plan"] == f"{snap['agent_plan']['passed']}/{snap['agent_plan']['n']}"
    assert row["date"] == snap["measured_at"] and row["instance"] == "nibras"
    assert row["packs_ok"] is True


def test_ratchet_fails_on_rise_and_ladder_regression():
    snap = snapshot("nibras")
    prev = series_row(snap)
    prev["date"] = "2000-01-01"
    assert ratchet_violations(snap, prev, {}) == []
    worse_prev = dict(prev)
    risen = [k for k in RATCHET_KEYS if int(snap["budget"][k]) > 0]
    for key in risen:
        worse_prev[key] = int(snap["budget"][key]) - 1
    violations = ratchet_violations(snap, worse_prev, {})
    assert len(violations) == len(risen)
    regressed_prev = dict(prev)
    regressed_prev["levels"] = {**prev["levels"], "L7": "reached"}
    if snap["ladder"]["levels"]["L7"] != "reached":
        assert any(v.startswith("ladder L7") for v in ratchet_violations(snap, regressed_prev, {}))


def test_ratchet_honours_ceiling_file_keys():
    snap = snapshot("nibras")
    ceiling = {"re_compile": 0}
    assert any("re_compile" in v for v in ratchet_violations(snap, None, ceiling))


def test_upsert_row_replaces_same_date_and_instance():
    rows = [{"date": "d", "instance": "nibras", "x": 1}]
    rows = upsert_row(rows, {"date": "d", "instance": "nibras", "x": 2})
    assert rows == [{"date": "d", "instance": "nibras", "x": 2}]
    rows = upsert_row(rows, {"date": "d", "instance": "eduos", "x": 3})
    assert len(rows) == 2


def test_committed_ceiling_is_not_above_measured_by_more_than_targets():
    """The ceiling file must be a real gate: at or just above today's numbers."""
    ceiling = json.loads(
        (Path(__file__).resolve().parents[3] / "docs/pulse/evidence/PV2.1-budget-ceiling.json").read_text()
    )
    now = measure()
    assert ceiling["staged_exits"] <= 4
    for key in ("routing_phrase_sets", "domain_terms_in_core", "brand_literals_in_core"):
        assert now[key] <= ceiling[key], f"{key} rose above ceiling"
