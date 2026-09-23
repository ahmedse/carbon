"""Unit tests: open_question.slot inference + report_clarify uses it."""
from __future__ import annotations

from ai.engine.cognition.state_store import (
    ConversationState,
    _infer_open_question_slot,
    update_state_from_turn,
)
from ai.engine.cognition.turn.report_clarify import try_report_clarify


def test_infer_report_aspect_slot_from_gate():
    assert (
        _infer_open_question_slot(
            "Happy to help with a salary report — what should this report focus on?",
            fired_gates=["report_clarify"],
        )
        == "report_aspect"
    )


def test_update_state_sets_nonempty_slot_on_clarify():
    state = ConversationState()
    update_state_from_turn(
        state,
        decision="clarify",
        response_text=(
            "Happy to help with a salary report — what should this report focus on?"
        ),
        fired_gates=["report_clarify"],
    )
    assert state.open_question["slot"] == "report_aspect"
    assert "focus on" in state.open_question["text"].lower()


def test_open_question_report_aspect_blocks_reclarify():
    assert (
        try_report_clarify(
            "i need full report about salaries in the company",
            open_question={
                "slot": "report_aspect",
                "asked_turn": 1,
                "text": "what should this report focus on?",
            },
        )
        is None
    )
