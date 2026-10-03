"""TEACH-CMD — the Moodle pane "educate me" teaching command.

Root cause being locked: a bare "educate me" used to be parsed as the literal
topic "educate me" and returned the bare course miss, and "<topic>, educate me"
fell through to the lecture door, which conflated "Tutorial 4" with lecture
"L4" and dumped a label citation. Both now route through the existing topic /
teach door: a grounded, verbatim answer or an honest teachable-topics list.
Read-only (ADR-0046); vocabulary is pack-only (topic_asks.yaml).
"""
from __future__ import annotations

from pathlib import Path

import yaml

from ai.moodle_bank import load_c4_drive, load_c4_files
from ai.moodle_host import door_answer
from ai.moodle_page import _name_has_lecture_num, _topic_core, _topic_from_message
from ai.tests.test_moodle_topic import ALOPECIA_REPLY, _med520_home, _page

_PACK = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med"
_GOLD = yaml.safe_load((_PACK / "gold" / "teach-cmd.yaml").read_text(encoding="utf-8"))
_MISS = _GOLD["miss"]

_NMD3101 = {
    "audience": "student",
    "course": {
        "id": 1,
        "shortname": "NMD3101",
        "fullname": "NMD3101: principles of infection",
        "visible_to_user": True,
    },
    "sections": [
        {"number": 3, "name": "Week 3", "visible": True},
        {"number": 4, "name": "L4 Bacterial genetics", "visible": True},
    ],
}


def _body(got: str) -> str:
    """The single verbatim span line of a topic reply (after the passage id)."""
    return got.split("\n", 2)[2].split("\n", 1)[0].rstrip("…")


# --------------------------------------------------------------------------
# (a) bare command with no topic → honest, useful clarifier (never the miss)
# --------------------------------------------------------------------------


def test_bare_educate_me_lists_teachable_topics():
    got = door_answer(_GOLD["bare"]["ask"], _page(_med520_home()))
    assert got is not None
    assert got != _MISS
    assert _GOLD["bare"]["expect_no_miss"]
    assert _GOLD["topics_label"] in got
    assert "alopecia" in got.casefold()
    # Never a citation with no answer.
    assert "MED520:" not in got


def test_bare_teach_me_is_the_same_honest_clarifier():
    got = door_answer("teach me", _page(_med520_home()))
    assert got is not None and got != _MISS
    assert _GOLD["topics_label"] in got


# --------------------------------------------------------------------------
# (b) "<topic>, educate me" → grounded tutorial answer, no false miss
# --------------------------------------------------------------------------


def test_topic_then_educate_me_resolves_grounded_content():
    case = _GOLD["existing_topic"]
    got = door_answer(case["ask"], _page(_med520_home()))
    assert got is not None and got != _MISS
    assert case["expect_passage"] in got
    bank = {**load_c4_files(case["shortname"]), **load_c4_drive(case["shortname"])}
    body = _body(got)
    assert body in bank[case["expect_passage"]]["text"], body


def test_topic_then_educate_me_matches_the_prefix_form():
    """The suffix command reaches the same door as "educate me about …"."""
    assert door_answer("alopecia, educate me", _page(_med520_home())) == ALOPECIA_REPLY


def test_lecture_topic_then_educate_me_cites_content_not_a_label():
    case = _GOLD["lecture_topic"]
    got = door_answer(case["ask"], _page(_NMD3101))
    assert got is not None and got != _MISS
    assert case["expect_passage"] in got
    for forbidden in case["forbid_substring"]:
        assert forbidden not in got, forbidden


def test_l4_topic_core_strips_the_lecture_marker():
    assert _topic_core("l4 bacterial genetics") == "bacterial genetics"
    assert _topic_core("lecture 4 bacterial genetics") == "bacterial genetics"
    assert _topic_core("bacterial genetics") == ""


# --------------------------------------------------------------------------
# (c) genuinely absent topic → honest clarification, not a raw dump
# --------------------------------------------------------------------------


def test_absent_topic_then_educate_me_is_an_honest_clarification():
    case = _GOLD["absent_topic"]
    got = door_answer(case["ask"], _page(_med520_home()))
    assert got is not None
    assert case["expect_no_miss"]
    assert got != _MISS
    assert _GOLD["topics_label"] in got
    assert "MED520:" not in got


# --------------------------------------------------------------------------
# Root-cause regression: "Tutorial 4" is not lecture "L4"
# --------------------------------------------------------------------------


def test_tutorial_four_is_not_lecture_l4():
    assert _name_has_lecture_num("L4 Bacterial genetics.pdf", 4)
    assert _name_has_lecture_num("PDF - L4 Bacterial genetics", 4)
    assert not _name_has_lecture_num("Tutorial 4: Disinfection & sterilization", 4)
    assert not _name_has_lecture_num("Tutorial 14: Something", 4)
    assert not _name_has_lecture_num("Final4 review", 4)
    assert not _name_has_lecture_num("L40 Antiviral agents", 4)


def test_spaced_lecture_names_still_match():
    """Committed banks spell lectures with a space ("L 4 …"); the token
    boundary must resolve these exactly like the glued form."""
    assert _name_has_lecture_num("L 4 Anterior triangle.docx", 4)
    assert _name_has_lecture_num("L 1 Cranial cavity.pdf", 1)
    assert _name_has_lecture_num("L 17- Carbohydrates.pdf", 17)
    assert _name_has_lecture_num("L 19.pdf", 19)
    assert _name_has_lecture_num("L 16-chemical bonds 2026.pdf", 16)


def test_lecture_number_is_not_a_number_prefix():
    """L40 is lecture 40, never lecture 4 (no prefix-of-number matching)."""
    assert _name_has_lecture_num("L40 Antiviral agents", 40)
    assert not _name_has_lecture_num("L40 Antiviral agents", 4)
    assert _name_has_lecture_num("L 40 Antiviral agents", 40)
    assert not _name_has_lecture_num("L 40 Antiviral agents", 4)


def test_suffix_teach_command_is_not_a_short_topic_phrase():
    # A bare command is intercepted by the door, not looked up as a topic —
    # "educate me" still must not become the literal topic "educate me".
    from ai.moodle_page import _is_bare_teach_command

    assert _is_bare_teach_command("educate me")
    assert _is_bare_teach_command("teach me")
    assert not _is_bare_teach_command("educate me about alopecia")
    assert _topic_from_message("alopecia, educate me") == "alopecia"
    assert _topic_from_message("hi") is None
