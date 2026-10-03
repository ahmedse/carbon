"""L-T T2 — STRUCTURED lesson (ILO + grounded worked example + grounded assessment).

Locks (TEACHING-WAVE-SPEC §1.1 T2 / §1.6 / §4): every ILO / example / assessment
line is an exact substring of the passage it cites; an ungroundable line is
dropped, never printed; Chat cannot reach the Apply (ADR-0046); the Apply is a
staff HOST action that appends pack JSONL — no DB table; a miss is the exact
course sentence. Additive to T1; no existing assertion is weakened.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from ai.moodle_bank import (
    load_c3,
    load_c4_drive,
    load_c4_files,
    load_c5_youtube,
    load_extra,
)
from ai.moodle_host import (
    door_answer,
    page_context_from_snapshot,
    snapshot_from_page_context,
)
from ai.moodle_teach import (
    apply_structured_lesson,
    build_structured_lesson,
    ground_sentence,
    structured_lesson_text,
)
from ai.tests.test_moodle_topic import _med520_home, _page

_PACK = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med"
_GOLD = yaml.safe_load((_PACK / "gold" / "teach-t2.yaml").read_text(encoding="utf-8"))
_MISS = "This is not in this course."


def _course_bank(shortname: str) -> dict[str, dict]:
    return {
        **load_c3(shortname),
        **load_c4_files(shortname),
        **load_c4_drive(shortname),
        **load_c5_youtube(shortname),
        **load_extra(shortname),
    }


def _staff_page(shortname: str) -> dict:
    return _page(
        {
            "course": {"id": 1, "shortname": shortname, "fullname": shortname, "visible_to_user": True},
            "sections": [],
        }
    )


def _all_lines(lesson: dict):
    for item in lesson.get("objectives") or []:
        yield item["passage_ref"], item["text"]
    for item in lesson.get("worked_example") or []:
        yield item["passage_ref"], item["text"]
    for item in lesson.get("assessment") or []:
        yield item["passage_ref"], item["answer"]


# --------------------------------------------------------------------------
# Grounding — every section line is a verbatim span of its cited passage
# --------------------------------------------------------------------------


def test_t2_gold_is_deterministic_and_grounded():
    assert len(_GOLD["cases"]) >= _GOLD["thresholds"]["min_cases"]
    assert len(_GOLD["cases"]) == _GOLD["thresholds"]["min_cases"]
    for case in _GOLD["cases"]:
        lesson = build_structured_lesson(case["topic"], _staff_page(case["shortname"]))
        assert lesson == case["lesson"], case["id"]
        bank = _course_bank(case["shortname"])
        for pid, line in _all_lines(lesson):
            assert pid in bank, case["id"]
            assert line in str(bank[pid]["text"]), case["id"]


def test_t2_every_section_line_is_a_verbatim_span():
    lesson = build_structured_lesson("alopecia", _staff_page("MED520"))
    assert lesson and lesson["grounded"]
    bank = _course_bank("MED520")
    for pid, line in _all_lines(lesson):
        assert ground_sentence(str(bank[pid]["text"]), line)
    assert lesson["objectives"] and lesson["worked_example"] and lesson["assessment"]


def test_t2_ungrounded_ilo_is_dropped_not_printed():
    claim = _GOLD["out_of_scope"]["ungrounded_ilo"]
    bank = _course_bank("MED520")
    passage = str(bank[claim["passage_ref"]]["text"])
    assert not ground_sentence(passage, claim["fabricated_ilo"])
    lesson = build_structured_lesson("alopecia", _staff_page("MED520"))
    assert claim["fabricated_ilo"] not in structured_lesson_text(lesson)
    for _pid, line in _all_lines(lesson):
        assert claim["fabricated_ilo"] not in line


def test_t2_no_grounding_is_the_exact_miss():
    topic = _GOLD["out_of_scope"]["no_grounding"]["topic"]
    assert build_structured_lesson(topic, _staff_page("MED520")) is None
    assert structured_lesson_text(None) == _MISS


def test_t2_student_and_off_list_are_refused():
    student = snapshot_from_page_context(
        page_context_from_snapshot({"audience": "student"}, _med520_home())
    )
    assert build_structured_lesson("alopecia", student) is None
    off = _GOLD["out_of_scope"]["off_list"]
    assert build_structured_lesson(off["topic"], _staff_page(off["shortname"])) is None


# --------------------------------------------------------------------------
# Staff Apply — host write, pack JSONL, no table; Chat can never reach it
# --------------------------------------------------------------------------


def test_t2_apply_persists_grounded_lesson_as_pack_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("MOODLE_APPROVED_LESSONS_DIR", str(tmp_path))
    result = apply_structured_lesson("alopecia", "MED520", staff_ref="emp_1")
    assert result["ok"] is True
    path = Path(result["path"])
    assert path == tmp_path / "MED520.jsonl"
    record = json.loads(path.read_text(encoding="utf-8").strip())
    assert record["shortname"] == "MED520"
    assert record["applied_by"] == "emp_1"
    assert record["lesson"] == result["lesson"]
    bank = _course_bank("MED520")
    for pid, line in _all_lines(record["lesson"]):
        assert line in str(bank[pid]["text"])


def test_t2_apply_refuses_off_list_and_ungrounded(tmp_path, monkeypatch):
    monkeypatch.setenv("MOODLE_APPROVED_LESSONS_DIR", str(tmp_path))
    assert apply_structured_lesson("alopecia", "AHFAD") == {"ok": False, "error": "off_list"}
    assert apply_structured_lesson("zzznosuchtermqq", "MED520")["error"] == "ungrounded"
    assert list(tmp_path.glob("*.jsonl")) == []


def test_t2_chat_cannot_reach_the_apply(tmp_path, monkeypatch):
    monkeypatch.setenv("MOODLE_APPROVED_LESSONS_DIR", str(tmp_path))
    asks = [
        "apply the lesson about alopecia",
        "build a lesson about alopecia",
        "save the structured lesson about alopecia",
        "approve the lesson about alopecia",
    ]
    for ask in asks:
        door_answer(ask, _page(_med520_home()))
    assert list(tmp_path.glob("*.jsonl")) == []
    import ai.moodle_host as host

    assert "apply_structured_lesson" not in Path(host.__file__).read_text(encoding="utf-8")


def test_t2_apply_endpoint_rejects_unsigned_caller():
    from django.test import RequestFactory

    from ai.moodle_host_api import MoodleTeachApplyView

    body = json.dumps({"shortname": "MED520", "topic": "alopecia"})
    request = RequestFactory().post(
        "/api/ai/moodle/teach/apply/", data=body, content_type="application/json"
    )
    response = MoodleTeachApplyView.as_view()(request)
    assert response.status_code == 401
