from ai.engine.cognition.turn.decision import Command, Decision, validate_decision
from ai.engine.cognition.turn.finish import grounded_reply


def test_arabic_decision_with_latin_answer_is_rejected_for_repair():
    decided = validate_decision(
        Decision(commands=[Command(op="answer", text="555")], language="ar"),
    )
    assert decided.commands == []
    assert [r.code for r in decided.rejections] == ["wrong_language"]


def test_answer_naming_a_catalog_tool_is_kept_without_the_name():
    decided = validate_decision(
        Decision(
            commands=[Command(op="answer", text="list_things cannot filter by prefix.")],
            language="en",
        ),
        allowed_tools={"list_things"},
    )
    assert [c.op for c in decided.commands] == ["answer"]
    assert decided.commands[0].text == "cannot filter by prefix"
    assert not decided.rejections


def test_grounded_answer_text_is_the_reply_when_nothing_was_read():
    decision = Decision(
        commands=[Command(op="answer", text="Noted.")],
        language="en",
    )
    assert grounded_reply(
        decision.commands[0], decision,
        user_message="My project code is ALPHA-7.",
        conversation_history=[],
        state=type("S", (), {"last_results": []})(),
    ) == "Noted."


def test_answer_text_does_not_replace_a_prior_read():
    decision = Decision(
        commands=[Command(op="answer", text="555")],
        language="en",
    )
    state = type("S", (), {"last_results": [{"digest": "headcount 555"}]})()
    assert grounded_reply(
        decision.commands[0], decision,
        user_message="Same count again.",
        conversation_history=[],
        state=state,
    ) == ""


def test_answer_text_with_a_new_figure_is_not_the_reply():
    decision = Decision(
        commands=[Command(op="answer", text="There are 999.")],
        language="en",
    )
    assert grounded_reply(
        decision.commands[0], decision,
        user_message="Same count again.",
        conversation_history=[],
        state=type("S", (), {"last_results": []})(),
    ) == ""


def test_arabic_answer_and_english_answer_with_arabic_name_stand():
    ar = validate_decision(
        Decision(commands=[Command(op="answer", text="العدد: 555")], language="ar"),
    )
    en = validate_decision(
        Decision(commands=[Command(op="answer", text="Your manager is علي")], language="en"),
    )
    assert [c.op for c in ar.commands] == ["answer"]
    assert [c.op for c in en.commands] == ["answer"]
    assert not ar.rejections and not en.rejections
