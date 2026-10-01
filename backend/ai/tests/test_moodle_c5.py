"""C5: captions are stored under activity plus video id. Empty caption is a miss."""
import json
from pathlib import Path

import yaml

from ai.moodle_bank import MISS, cite_open_activity, load_c4_files, load_c5_youtube
from ai.moodle_page import fact_answer

_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "c5.yaml"
_KEYS = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "bank" / "course-keys-13"
_EXT = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "bank" / "course-ext-13"
_STATUS = {"ok", "empty", "unavailable"}
_ASK = "According to the handout"
_WORLD = "aast-mbbs"


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("{")]


def test_every_counted_youtube_row_has_caption_or_explicit_empty():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    keys = []
    for path in sorted(_KEYS.glob("*.jsonl")):
        for row in _rows(path):
            if str(row.get("ref") or "").startswith("youtube:"):
                keys.append(row)
    assert len(keys) == gold["counted"]
    for key in keys:
        video_id = str(key["ref"]).split(":", 1)[1]
        ext = [
            r
            for r in _rows(_EXT / f"{key['course']}.jsonl")
            if r.get("family") == "youtube" and int(r["cmid"]) == int(key["cmid"]) and r.get("source_id") == video_id
        ]
        assert len(ext) == 1, key
        row = ext[0]
        assert row["status"] in _STATUS, row
        if row["status"] == "ok":
            assert row.get("text")
        else:
            assert not row.get("text")


def test_empty_caption_is_the_lecture_miss():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    case = gold["empty_caption"]
    bank = load_c5_youtube(case["course"])
    assert all(case["video_id"] not in pid or not bank[pid]["text"] for pid in bank)
    answer = cite_open_activity(
        f"{_ASK}, {case['quote']}",
        bank,
        course=case["course"],
        activity_id=case["activity"],
        world=_WORLD,
    )
    assert answer == MISS
    live = fact_answer(
        f"{_ASK}, {case['quote']}",
        {
            "course": {"shortname": case["course"]},
            "activity": {"cmid": case["activity"]},
        },
    )
    assert live == gold["miss"]


def test_an_ok_caption_cites_the_open_activity():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    case = gold["hit"]
    bank = load_c5_youtube(case["course"])
    row = bank.get(case["passage"])
    quote = case["quote"]
    if not quote:
        assert row, case["passage"]
        quote = row["text"][80 : 80 + 48] if len(row["text"]) > 128 else row["text"][:48]
        assert len(quote) >= 24
    else:
        assert row and quote in row["text"]
    owners = [pid for pid, item in bank.items() if quote in item["text"] and item["activity_id"] == case["activity"]]
    assert owners == [case["passage"]]
    answer = cite_open_activity(
        f"{_ASK}, {quote}",
        bank,
        course=case["course"],
        activity_id=case["activity"],
        world=_WORLD,
    )
    assert answer.startswith(case["passage"] + "\n")
    assert quote in answer


def test_whatsapp_mp4_is_not_one_of_the_78():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    case = gold["whatsapp_mp4_stays_file"]
    files = load_c4_files(case["course"])
    youtube = load_c5_youtube(case["course"])
    assert all(case["filename"] not in pid for pid in youtube)
    assert all(row["kind"] == "file" for row in files.values())
    assert all(row["kind"] == "youtube" for row in youtube.values())
    ext = _rows(_EXT / f"{case['course']}.jsonl")
    assert all(int(r.get("cmid") or 0) != case["cmid"] for r in ext)


def test_load_c4_files_still_skips_youtube():
    bank = load_c4_files("NMD1103")
    assert all(row["kind"] == "file" for row in bank.values())
    assert all(":youtube:" not in pid for pid in bank)
