"""Phrase tables resolve from the pack bound for the turn."""
from __future__ import annotations

from ai.engine.cognition.phrase_tables import T, bind_pack


_LEAVE_KEY = "scope_route_i18n.py::LEAVE_WORD_AR"
_LOAN_KEY = "turn/handoff_agent.py::_LOAN_TYPE_WORDS"
_AUTONOMY = "context_pack.py::CHAT_AUTONOMY"


def test_nibras_turn_sees_its_phrase_overlay():
    with bind_pack("nibras"):
        words = list(T(_LEAVE_KEY))
        loan = list(T(_LOAN_KEY))
        autonomy = T(_AUTONOMY)
    assert words
    assert "salary" in loan
    assert "payroll" in autonomy


def test_other_pack_does_not_see_the_nibras_overlay():
    with bind_pack("aast-med"):
        assert list(T(_LEAVE_KEY)) == []
        loan = list(T(_LOAN_KEY))
        autonomy = str(T(_AUTONOMY))
    assert "salary" not in loan
    assert "payroll" not in autonomy
    assert "Agent" in autonomy


def test_module_binding_follows_the_active_pack():
    from ai.engine.cognition.turn.handoff_agent import _LOAN_TYPE_WORDS

    with bind_pack("nibras"):
        nibras = list(_LOAN_TYPE_WORDS)
    with bind_pack("aast-med"):
        other = list(_LOAN_TYPE_WORDS)
    assert len(nibras) > len(other)


def test_phrase_path_rejects_a_pack_escape():
    with bind_pack("../nibras"):
        assert list(T(_LEAVE_KEY)) == []
    with bind_pack("nibras/../nibras"):
        assert list(T(_LEAVE_KEY)) == []
