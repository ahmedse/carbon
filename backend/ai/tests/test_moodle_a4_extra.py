"""A4 extra knowledge: cite only after index, and only in that course."""
from pathlib import Path

from ai.moodle_bank import load_extra, write_extra_index
from ai.moodle_page import topic_answer
from ai.tests.test_moodle_topic import _MISS, _med520_home, _page

_EXTRA_TEXT = "AASTMT Pulse extra file for MED520 tutor notes only."
_EXTRA_PAYLOAD = [
    {
        "itemid": 7,
        "filename": "tutor-note.md",
        "title": "Tutor note",
        "sectionnum": -1,
        "passages": [{"text": _EXTRA_TEXT}],
    }
]


def _nmd1000_home() -> dict:
    return {
        "course": {
            "id": 2,
            "shortname": "NMD1000",
            "fullname": "Introduction to Medical School",
            "visible_to_user": True,
        },
        "sections": [{"number": 1, "name": "Welcome", "visible": True}],
    }


def test_a4_upload_md_on_med520_is_extra_passage(tmp_path, monkeypatch):
    monkeypatch.setattr("ai.moodle_bank._EXTRA", tmp_path)
    assert load_extra("MED520", extra_root=tmp_path) == {}
    assert topic_answer("educate me about aastmt pulse extra file", _page(_med520_home())) == _MISS
    indexed = write_extra_index("MED520", _EXTRA_PAYLOAD, extra_root=tmp_path)
    assert indexed == 1
    bank = load_extra("MED520", extra_root=tmp_path)
    pid = "MED520:extra:7:tutor-note.md"
    assert pid in bank
    assert _EXTRA_TEXT in bank[pid]["text"]
    got = topic_answer("educate me about aastmt pulse extra file", _page(_med520_home()))
    assert got is not None
    assert pid in got
    assert _EXTRA_TEXT.split()[0] in got
    assert "NMD1000" not in got


def test_a4_other_course_cannot_cite_med520_extra(tmp_path, monkeypatch):
    monkeypatch.setattr("ai.moodle_bank._EXTRA", tmp_path)
    write_extra_index("MED520", _EXTRA_PAYLOAD, extra_root=tmp_path)
    med = topic_answer("educate me about aastmt pulse extra file", _page(_med520_home()))
    other = topic_answer("educate me about aastmt pulse extra file", _page(_nmd1000_home()))
    assert med is not None
    assert "MED520:extra:7:tutor-note.md" in med
    assert other == _MISS
    assert "MED520:extra" not in (other or "")
    assert load_extra("NMD1000", extra_root=tmp_path) == {}
