from ai.engine.cognition.turn.decision import Command, Decision, validate_decision


def test_arabic_decision_with_latin_answer_is_rejected_for_repair():
    decided = validate_decision(
        Decision(commands=[Command(op="answer", text="555")], language="ar"),
    )
    assert decided.commands == []
    assert [r.code for r in decided.rejections] == ["wrong_language"]


def test_answer_naming_a_catalog_tool_is_rejected_for_repair():
    decided = validate_decision(
        Decision(
            commands=[Command(op="answer", text="list_things cannot filter by prefix.")],
            language="en",
        ),
        allowed_tools={"list_things"},
    )
    assert decided.commands == []
    assert [r.code for r in decided.rejections] == ["internal_name"]


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
