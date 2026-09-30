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


def _state(*digests: str):
    return type("S", (), {"last_results": [{"digest": d} for d in digests]})()


def _answer(text: str, *, source: str = "conversation", language: str = "en") -> Decision:
    return Decision(commands=[Command(op="answer", text=text, source=source)], language=language)


def test_grounded_answer_text_is_the_reply_when_nothing_was_read():
    decision = _answer("Noted.")
    assert grounded_reply(
        decision.commands[0], decision,
        user_message="My project code is ALPHA-7.",
        conversation_history=[],
        state=_state(),
    ) == "Noted."


def test_conversation_answer_restating_a_prior_read_is_the_reply():
    decision = _answer("555")
    assert grounded_reply(
        decision.commands[0], decision,
        user_message="Same count again.",
        conversation_history=[],
        state=_state("headcount 555"),
    ) == "555"


def test_answer_without_a_conversation_source_is_written():
    for source in ("knowledge", ""):
        decision = _answer("Annual leave is 30 days.", source=source)
        assert grounded_reply(
            decision.commands[0], decision,
            user_message="What is the leave policy?",
            conversation_history=[],
            state=_state(),
        ) == ""


def test_figures_are_checked_against_what_understand_was_shown():
    decision = _answer("Your employee number is 2378.")
    decision.exchange = {"messages": [
        {"role": "system", "content": "IDENTITY: employee 2378"},
        {"role": "user", "content": "What is my number?"},
    ]}
    assert grounded_reply(
        decision.commands[0], decision,
        user_message="What is my number?",
        conversation_history=[],
        state=_state(),
    ) == "Your employee number is 2378."
    decision.exchange = {"messages": [{"role": "user", "content": "What is my number?"}]}
    assert grounded_reply(
        decision.commands[0], decision,
        user_message="What is my number?",
        conversation_history=[],
        state=_state("employee 2378"),
    ) == ""


def test_arabic_conversation_answer_needs_arabic_words():
    latin = _answer("555", language="ar")
    arabic = _answer("العدد 555", language="ar")
    for decision, expected in ((latin, ""), (arabic, "العدد 555")):
        assert grounded_reply(
            decision.commands[0], decision,
            user_message="كم العدد؟",
            conversation_history=[],
            state=_state("headcount 555"),
        ) == expected


def test_answer_source_is_parsed_and_unknown_is_empty():
    from ai.engine.cognition.turn.decision import EMIT_DECISION_TOOL, parse_decision

    parsed = parse_decision({"commands": [
        {"op": "answer", "text": "hi", "source": "Conversation", "fields": []},
        {"op": "answer", "text": "hi", "source": "guess", "fields": []},
    ]})
    assert [c.source for c in parsed.commands] == ["conversation", ""]
    item = EMIT_DECISION_TOOL["function"]["parameters"]["properties"]["commands"]["items"]
    assert item["properties"]["source"]["enum"] == ["", "conversation", "knowledge"]
    assert "source" in item["required"]
    desc = EMIT_DECISION_TOOL["function"]["description"]
    assert "written after this decision" not in desc
    assert "text is the reply" in desc
    assert "the reply itself" in item["properties"]["text"]["description"]


def test_catalog_name_strip_keeps_the_source():
    decided = validate_decision(
        _answer("list_things cannot filter by prefix."), allowed_tools={"list_things"},
    )
    assert [(c.text, c.source) for c in decided.commands] == [
        ("cannot filter by prefix", "conversation"),
    ]


def test_a_language_repair_is_shown_with_the_repaired_source():
    import asyncio
    import json

    from ai.engine.cognition.turn.understand import understand_turn

    def emit(text: str, call_id: str) -> dict:
        body = {"commands": [{"op": "answer", "text": text, "source": "conversation",
                              "fields": []}], "language": "ar", "confidence": 0.9}
        return {"tool_calls": [{"id": call_id, "function": {
            "name": "emit_decision", "arguments": json.dumps(body, ensure_ascii=False),
        }}]}

    replies = [emit("555", "call_1"), emit("العدد 555", "call_2")]
    sent: list[list[dict]] = []

    async def complete(*, messages, **_kw):
        sent.append(list(messages))
        return replies[len(sent) - 1]

    user = {"role": "user", "content": "كم العدد؟"}
    decision = asyncio.run(understand_turn(
        complete=complete,
        messages=[{"role": "system", "content": "STATE: headcount 555"}, user],
    ))
    assert len(sent) == 2
    assert decision.repaired is True
    assert [(c.text, c.source) for c in decision.commands] == [("العدد 555", "conversation")]
    assert grounded_reply(
        decision.commands[0], decision,
        user_message=user["content"], conversation_history=[], state=_state(),
    ) == "العدد 555"


def test_answer_text_with_a_new_figure_is_not_the_reply():
    decision = _answer("There are 999.")
    assert grounded_reply(
        decision.commands[0], decision,
        user_message="Same count again.",
        conversation_history=[],
        state=type("S", (), {"last_results": []})(),
    ) == ""


def test_an_arabic_reply_that_translates_a_stored_name_is_not_shown():
    decision = _answer("المسمى: مدير الخدمات المشتركة.", language="ar")
    assert grounded_reply(
        decision.commands[0], decision,
        user_message="وما هو المسمى؟",
        conversation_history=[],
        state=_state("employee_no=2378, title=Director of Shared Services"),
    ) == ""


def test_an_arabic_reply_that_quotes_the_record_figure_stands():
    decision = _answer("رقمك: 2378.", language="ar")
    assert grounded_reply(
        decision.commands[0], decision,
        user_message="وما هو رقمي؟",
        conversation_history=[],
        state=_state("employee_no=2378, title=Director of Shared Services"),
    ) == "رقمك: 2378."


def test_a_carried_reply_keeps_its_words_when_a_date_was_calculated():
    decision = _answer(
        "Got it — 2 days of annual leave starting Sunday 4 October 2026.",
    )
    reply = grounded_reply(
        decision.commands[0], decision,
        user_message="Make it 2 days.",
        conversation_history=[{"role": "user", "content": "I want annual leave starting next Sunday."}],
        state=_state(),
    )
    assert "annual" in reply
    assert "2" in reply
    assert "4" not in reply
    assert "2026" not in reply


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
