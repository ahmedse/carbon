"""A clarify with options is a typed choice the client paints as a form."""
from ai.engine.cognition.turn.choice import KIND, choice_question
from ai.engine.cognition.turn.decision import parse_decision


def test_rules_send_a_pick_to_clarify_not_answer():
    from ai.engine.cognition.turn.understand import _UNDERSTAND_RULES

    assert "Asking the user to pick is clarify, never answer" in _UNDERSTAND_RULES
    assert "each choice in options" in _UNDERSTAND_RULES


def test_emit_decision_asks_for_labels_not_a_listed_question():
    from ai.engine.cognition.turn.decision import EMIT_DECISION_TOOL

    description = EMIT_DECISION_TOOL["function"]["description"]
    assert "put each choice in options" in description
    assert "does not list the choices" in description


def test_one_option_is_not_a_menu():
    assert choice_question("clarify", ["Only this"]) is None
    assert choice_question("answer", ["A", "B"]) is None


def test_clarify_options_become_a_choice():
    decision = parse_decision({
        "commands": [{
            "op": "clarify",
            "question": "Which salary topic?",
            "options": ["Payroll runs", "Payslips", "Payroll runs"],
            "key": "topic",
        }],
        "language": "en",
        "confidence": 0.4,
    })
    cmd = decision.commands[0]
    choice = choice_question(cmd.op, cmd.options, cmd.key)
    assert choice["kind"] == KIND
    assert choice["key"] == "topic"
    assert choice["allow_free"] is True
    assert [row["value"] for row in choice["options"]] == ["Payroll runs", "Payslips"]
