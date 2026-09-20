"""Deixis gate tests (Track C — ux-07)."""
from ai.engine.cognition.dialogue.deixis import (
    build_deixis_confirm,
    has_deixis,
    infer_prior_topic,
    is_confirm_reply,
    should_gate_deixis,
)


def test_has_deixis_that_one():
    assert has_deixis("check that one for me")
    assert has_deixis("look into that")
    assert not has_deixis("check GradeVance for me")


def test_should_gate_with_prior_topic():
    history = [
        {"role": "user", "content": "tell me about gradevance"},
        {
            "role": "assistant",
            "content": "## GradeVance Overview\n\nGradeVance is a platform.",
        },
    ]
    q = should_gate_deixis("check that one for me", conversation_history=history)
    assert q is not None
    assert "GradeVance" in q
    assert "Did you mean" in q


def test_confirm_reply_skips_gate():
    assert is_confirm_reply("yes")
    assert should_gate_deixis("yes", conversation_history=None) is None


def test_infer_prior_from_bold():
    history = [
        {"role": "assistant", "content": "It seems you mean **GradeVance**, the assessment platform."},
    ]
    assert infer_prior_topic(history) == "GradeVance"


def test_build_confirm_without_topic():
    assert "Which item" in build_deixis_confirm()


def test_topic_stack_lists_recent_distinct():
    history = [
        {"role": "assistant", "content": "## GradeVance\n\nOverview."},
        {"role": "user", "content": "thanks"},
        {"role": "assistant", "content": "## Payroll\n\nTotals."},
        {"role": "user", "content": "ok"},
        {"role": "assistant", "content": "## Leave\n\nBalances."},
    ]
    from ai.engine.cognition.dialogue.deixis import collect_topic_stack

    stack = collect_topic_stack(history)
    assert stack[0] == "Leave"
    assert "Payroll" in stack
    assert "GradeVance" in stack


def test_deixis_gate_offers_stack_when_multiple_topics():
    history = [
        {"role": "assistant", "content": "## GradeVance\n\nOverview."},
        {"role": "assistant", "content": "## Payroll\n\nTotals."},
    ]
    q = should_gate_deixis("check that one for me", conversation_history=history)
    assert q is not None
    assert "Which of these" in q
    assert "GradeVance" in q
    assert "Payroll" in q
