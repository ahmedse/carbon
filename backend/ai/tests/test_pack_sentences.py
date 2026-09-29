"""Sentences the model or the user can read follow the bound pack."""
from __future__ import annotations

from pathlib import Path

from ai.engine.agent.chat_surface_i18n import LEAVE_INTENT_AR, any_needle
from ai.engine.agent.tools import _comp_deny_message
from ai.engine.cognition.turn.ess_read import guidance_block
from ai.engine.cognition.turn.handoff_agent import clarify_choices
from ai.engine.cognition.turn.understand import _UNDERSTAND_RULES
from ai.engine.pack_vocab import bind_pack, copy_text

_ENGINE = Path(__file__).resolve().parents[1] / "engine"
_FRAGMENTS = (
    "اجازاتي",
    "Official permission",
    "Committed deductions",
    "Committed take-home",
    "Last month's committed net pay",
    "Not authorized to view compensation",
    "فتح إجازاتي",
    "فتح الحضور",
    "أرصدة الإجازات",
    "organisation-wide HR lists",
    "What type of permission do you need",
    "ما تواريخ الإجازة",
    "صافي الراتب المعتمد",
    "basic pay",
    "net pay, take-home",
    "net pay / take-home",
)


def test_moved_sentences_are_not_engine_literals():
    for path in sorted(_ENGINE.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for fragment in _FRAGMENTS:
            assert fragment not in text, f"{path.name} still has {fragment}"


def test_nibras_sentences_render():
    with bind_pack("nibras"):
        guide = guidance_block()
        assert "ESS SELF-READ CONTRACT" in guide
        assert "net pay" in guide
        assert "قسيمة" in guide
        assert "get_my_leave_balance" in str(_UNDERSTAND_RULES)
        deny = _comp_deny_message("people:view_compensation")
        assert deny == "Not authorized to view compensation (people:view_compensation required)."
        assert "Official permission" in clarify_choices(
            "submit_my_attendance_permission", "permission_type", "en"
        )
        assert any_needle("إجازة سنوية", LEAVE_INTENT_AR)
        filled = copy_text("t_rx_copy_net_month_en", net="10")
        assert filled == "Last month's committed net pay is 10."


def test_other_pack_does_not_receive_the_sentences():
    with bind_pack("aast-med"):
        guide = guidance_block()
        assert "net pay" not in guide
        assert "قسيمة" not in guide
        assert "get_my_leave_balance" not in str(_UNDERSTAND_RULES)
        assert "compensation" not in _comp_deny_message("people:view_compensation")
        assert clarify_choices(
            "submit_my_attendance_permission", "permission_type", "en"
        ) == []
        assert not any_needle("إجازة سنوية", LEAVE_INTENT_AR)
        assert copy_text("t_rx_copy_net_month_en", net="10") == ""


def test_empty_copy_is_not_formatted():
    with bind_pack("aast-med"):
        assert copy_text("t_rx_copy_comp_deny", cap="people:view_compensation") == ""
