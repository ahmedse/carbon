"""A2: Pulse-off (plugin course_list block) is L0, not a lecture cite.

Live switch is Moodle local_pulse/enabled_courses, encoded as snapshot.block.
The pack courses.yaml catalog still lists the thirteen; it must not Pulse-off
on its own, and it must not cite when the plugin sent the block.
"""

from ai.moodle_bank import listed_shortnames
from ai.moodle_host import COURSE_LIST_ANSWERS, prepare_ask


def test_a2_nmd1000_off_list_is_l0_not_a_cite():
    """Disable NMD1000 → identity/topic are the list miss, not 1127 or the name."""
    snapshot = {
        "audience": "staff",
        "courseid": 32,
        "block": "course_list",
        "course": {"id": 32, "visible_to_user": False},
        "sections": [
            {"number": 1, "name": "Introduction to Medical School", "visible": True},
        ],
    }
    for message in ("which course", "herpes?", "educate me about alopecia", "hi"):
        decision = prepare_ask(
            {
                "pulse_mode": "ask",
                "message": message,
                "snapshot": snapshot,
                "host_context": {"audience": "staff", "courseid": 32},
                "moodle_user_id": 7,
            }
        )
        assert decision.refusal == "course_list", message
        assert decision.chat is None, message
        assert decision.answer == COURSE_LIST_ANSWERS["course_list"], message
        assert (decision.answer or "").startswith("This is not on the course list."), message
        assert "1127" not in (decision.answer or "")
        assert "NMD1000" not in (decision.answer or "")
        assert "Introduction to Medical School" not in (decision.answer or "")


def test_a2_pack_catalog_is_not_the_live_off_switch():
    """YAML still lists NMD1000. Without snapshot.block, Ask is not a list miss."""
    assert "NMD1000" in listed_shortnames()
    snapshot = {
        "audience": "staff",
        "courseid": 32,
        "course": {
            "id": 32,
            "shortname": "NMD1000",
            "fullname": "Introduction to Medical School",
            "visible_to_user": True,
        },
        "sections": [],
    }
    decision = prepare_ask(
        {
            "pulse_mode": "ask",
            "message": "which course",
            "snapshot": snapshot,
            "host_context": {"audience": "staff", "courseid": 32},
            "moodle_user_id": 7,
        }
    )
    assert decision.refusal != "course_list"
    assert not (decision.answer or "").startswith("This is not on the course list.")
