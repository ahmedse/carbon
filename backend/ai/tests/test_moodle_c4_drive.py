"""C4-drive: Drive bodies are stored under activity plus source id."""
import json
from pathlib import Path

import yaml

from ai.moodle_bank import cite_open_activity, load_c4_drive, load_c4_files
from ai.tests.test_moodle_k6_coverage import test_every_named_course_cites_95

_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "c4-drive.yaml"
_C4 = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "c4.yaml"
_KEYS = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "bank" / "course-keys-13"
_EXT = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "bank" / "course-ext-13"
_COUNTED = {"google-presentation", "google-file", "google-document"}
_STATUS = {"ok", "empty", "unavailable"}
_ASK = "According to the handout"
_WORLD = "aast-mbbs"


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("{")]


def _counted_keys() -> list[dict]:
    out = []
    for path in sorted(_KEYS.glob("*.jsonl")):
        for row in _rows(path):
            if row.get("kind") != "url":
                continue
            prefix = str(row.get("ref") or "").split(":", 1)[0]
            if prefix in _COUNTED:
                out.append(row)
    return out


def test_every_counted_drive_row_has_a_typed_status():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    keys = _counted_keys()
    assert len(keys) == gold["counted"]
    by_course: dict[str, list] = {}
    for row in keys:
        by_course.setdefault(row["course"], []).append(row)
    for shortname, expected in by_course.items():
        ext = _rows(_EXT / f"{shortname}.jsonl")
        indexed = {(int(r["cmid"]), r.get("source_id")): r for r in ext if r.get("family") == "google"}
        for key in expected:
            source_id = str(key["ref"]).split(":", 1)[1]
            row = indexed.get((int(key["cmid"]), source_id))
            assert row is not None, key
            assert row["status"] in _STATUS, row
            assert row.get("text") or row["status"] != "ok"
            if row["status"] != "ok":
                assert not row.get("text")


def test_unlinked_ids_are_absent_from_drive_and_file_banks():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    file_gold = yaml.safe_load(_C4.read_text(encoding="utf-8"))
    files = load_c4_files(file_gold["course"])
    drive = load_c4_drive(file_gold["course"])
    for source in gold["absent"]:
        assert all(source not in pid for pid in files)
        assert all(source not in pid for pid in drive)
    for source in gold["c4_file_drive_refs"]:
        assert source not in {row["source"] for row in files.values()}
        assert all(row["kind"] == "file" for row in files.values())


def test_moodle_intro_is_not_a_drive_passage():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    case = gold["intro_not_passage"]
    bank = load_c4_drive(case["course"])
    intro = case["intro"]
    for row in bank.values():
        if case["source_id"] in row["id"]:
            assert row["text"] != intro
            assert not row["text"].startswith(intro) or len(row["text"]) > len(intro) + 40


def test_an_ok_drive_body_cites_the_open_activity():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    case = gold["hit"]
    bank = load_c4_drive(case["course"])
    assert case["passage"] in bank
    assert case["quote"] in bank[case["passage"]]["text"]
    owners = [row["id"] for row in bank.values() if case["quote"] in row["text"] and row["activity_id"] == case["activity"]]
    assert owners == [case["passage"]]
    answer = cite_open_activity(
        f"{_ASK}, {case['quote']}",
        bank,
        course=case["course"],
        activity_id=case["activity"],
        world=_WORLD,
    )
    assert answer.startswith(case["passage"] + "\n")
    assert case["quote"] in answer


def test_same_source_on_two_activities_keeps_two_passages():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    for case in gold["duplicate_source"]:
        ext = [r for r in _rows(_EXT / f"{case['course']}.jsonl") if r.get("source_id") == case["source_id"]]
        assert {int(r["cmid"]) for r in ext} == set(case["activities"])
        bank = load_c4_drive(case["course"])
        pids = [f"{case['course']}:google:{cmid}:{case['source_id']}" for cmid in case["activities"]]
        present = [pid for pid in pids if pid in bank]
        typed = [r for r in ext if r["status"] in _STATUS]
        assert len(typed) == 2
        if all(r["status"] == "ok" for r in ext):
            assert present == pids


def test_docs_google_links_stay_listed_and_unresolved_without_an_id():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    unresolved = []
    for path in sorted(_EXT.glob("*.jsonl")):
        for row in _rows(path):
            if row.get("source_kind") == "link:docs.google.com":
                unresolved.append(row)
                assert row["status"] == "unavailable"
                assert row["cause"] == "unresolved_link"
                assert not row.get("source_id")
                assert not row.get("text")
    assert len(unresolved) == gold["docs_links_unresolved"]
    for row in unresolved:
        bank = load_c4_drive(row["course"])
        assert all(not pid.endswith(":") for pid in bank)
        assert all(item["activity_id"] != int(row["cmid"]) or item.get("text") != (row.get("name") or "") for item in bank.values())


def test_load_c4_files_kinds_are_still_file():
    for path in sorted(_KEYS.glob("*.jsonl")):
        bank = load_c4_files(path.stem)
        assert all(row["kind"] == "file" for row in bank.values())


def test_k6_coverage_still_cites_95_per_named_course():
    test_every_named_course_cites_95()


def test_k6_quotes_keep_one_owner_on_the_open_activity_with_drive_merged():
    from ai.moodle_bank import load_c3, load_c4_drive, load_c4_files, load_c5_youtube
    from ai.tests.test_moodle_k6_coverage import _ASK, _FULL, _cases

    for shortname in (*_FULL, "NMD1103"):
        hits, _misses = _cases(shortname)
        bank = {
            **load_c3(shortname),
            **load_c4_files(shortname),
            **load_c4_drive(shortname),
            **load_c5_youtube(shortname),
        }
        for case in hits:
            owners = [
                row["id"]
                for row in bank.values()
                if case["quote"] in row["text"] and row["activity_id"] == case["activity"]
            ]
            assert owners == [case["passage"]], (shortname, case["passage"], owners)
