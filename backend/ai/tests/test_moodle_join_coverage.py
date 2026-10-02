"""Lock the Moodle bank join rule and the coverage honesty rule.

The Course desk merges Moodle's live activities with the Carbon roster. Bank
rows may carry production activity ids, so the join must not depend on the
cmid alone: a Moodle module and a bank row share the section + family + name
key. These tests pin that rule and the honesty rule behind it. A module reads
loaded only when a real passage exists for it.
"""
from __future__ import annotations

import pytest

from ai.moodle_bank import (
    course_roster,
    load_c3,
    load_c4_drive,
    load_c4_files,
    load_c5_youtube,
    load_extra,
    match_roster_activity,
    roster_family,
)

_INGESTIBLE_FAMILIES = {"file", "url", "page", "label", "book"}


def _passages(shortname: str) -> dict:
    return {
        **load_c3(shortname),
        **load_c4_files(shortname),
        **load_c4_drive(shortname),
        **load_c5_youtube(shortname),
        **load_extra(shortname),
    }


def _has_passage(shortname: str, activity_id: int) -> bool:
    return any(int(row["activity_id"]) == int(activity_id) for row in _passages(shortname).values())


def _coverage(shortname: str) -> tuple[int, int]:
    """The desk rule: loaded ingestible / Pulse-active ingestible, keyed by the join key."""
    loaded: dict[str, bool] = {}
    for row in course_roster(shortname)["activities"]:
        key = str(row.get("key") or "")
        if not key or roster_family(str(row.get("kind") or "")) not in _INGESTIBLE_FAMILIES:
            continue
        is_loaded = str(row.get("status") or "") in {"ok", "loaded"}
        loaded[key] = bool(loaded.get(key)) or is_loaded
    return sum(1 for value in loaded.values() if value), len(loaded)


def test_cmid_drift_still_joins_by_section_family_name():
    # MED520's bank ids are production ids; the local module id differs. The
    # key must still land the real passage on the module.
    activities = course_roster("MED520")["activities"]
    case = next(row for row in activities if row["in_pack"] and row["status"] == "ok" and row["key"])
    module = {
        "cmid": 999_999,
        "sectionnum": case["sectionnum"],
        "modname": case["kind"],
        "name": case["name"],
    }
    hit = match_roster_activity(module, activities)
    assert hit is not None
    assert hit["status"] == "ok"
    assert _has_passage("MED520", hit["cmid"])


def test_unknown_module_has_no_join_and_reads_not_loaded():
    activities = course_roster("NMD1000")["activities"]
    module = {"cmid": 123_456, "sectionnum": 1, "modname": "resource", "name": "ZZZ not a real handout"}
    assert match_roster_activity(module, activities) is None


def test_activity_without_a_passage_reads_not_loaded():
    activities = course_roster("MED520")["activities"]
    case = next(row for row in activities if row["key"] and row["status"] == "empty")
    module = {
        "cmid": 888_888,
        "sectionnum": case["sectionnum"],
        "modname": case["kind"],
        "name": case["name"],
    }
    hit = match_roster_activity(module, activities)
    assert hit is not None
    assert hit["status"] != "ok"
    assert not _has_passage("MED520", hit["cmid"])


def test_activity_with_a_passage_reads_loaded():
    activities = course_roster("NMD1103")["activities"]
    case = next(row for row in activities if row["status"] == "ok" and row["key"])
    module = {
        "cmid": 777_777,
        "sectionnum": case["sectionnum"],
        "modname": case["kind"],
        "name": case["name"],
    }
    hit = match_roster_activity(module, activities)
    assert hit is not None and hit["status"] == "ok"
    assert _has_passage("NMD1103", hit["cmid"])


def test_every_roster_row_carries_the_stable_key():
    for shortname in ("NMD1103", "NMD1000", "MED520"):
        for row in course_roster(shortname)["activities"]:
            key = str(row.get("key") or "")
            assert key.count(":") >= 2, (shortname, row)
            section, family, name = key.split(":", 2)
            assert section.isdigit()
            assert family in {"file", "url", "page", "label", "book", "other"}
            assert name


@pytest.mark.parametrize(
    "shortname,loaded_floor",
    [("NMD1103", 26), ("NMD1000", 97), ("MED520", 62)],
)
def test_named_course_coverage_is_against_real_bank_data(shortname: str, loaded_floor: int):
    loaded, active = _coverage(shortname)
    assert active >= loaded >= loaded_floor, (shortname, loaded, active)
    # Honesty: a row that reads loaded is in the pack, and its activity has a passage.
    for row in course_roster(shortname)["activities"]:
        if str(row.get("status") or "") in {"ok", "loaded"}:
            assert row.get("in_pack") is True
            assert row.get("cmid")
