"""PV2 C8 — 0-LLM thanks / clock / how-where / notification FAQ."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from ai.engine.cognition.turn.navigation import (
    is_how_where_ui,
    place_topic,
    resolve_navigation,
)
from ai.engine.cognition.turn.memory_recall import (
    extract_stated_facts,
    is_memory_use,
    is_remember_store,
    remember_facts,
)
from ai.engine.cognition.turn.zero_llm import (
    is_clock_ask,
    is_date_deixis,
    is_notification_faq,
    is_thanks,
    render_clock,
    render_date_deixis,
    try_zero_llm_answer,
)
from ai.engine.cognition.state_store import ConversationState


def nibras_cfg():
    path = (
        Path(__file__).resolve().parents[1]
        / "engine" / "instances" / "nibras" / "instance.yaml"
    )
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("text", [
    "Thank you",
    "Thanks for the help",
    "thank you for the information",
    "شكراً لك",
])
def test_thanks_detected(text):
    assert is_thanks(text)


def test_thanks_submit_is_not_ack():
    assert not is_thanks("thank you, please submit my leave")


def test_clock_and_not_payroll_when():
    assert is_clock_ask("What is today's date?")
    assert is_clock_ask("What month are we in?")
    assert not is_clock_ask("When will next month's payroll be processed?")
    assert not is_clock_ask("When does my leave start?")


def test_clock_render_avoids_echoing_what_month():
    text = render_clock("What month are we in?", date(2026, 9, 23))
    assert "September" in text and "2026" in text
    assert "what month" not in text.lower()


def test_how_where_grounds_topic_not_full_question():
    cfg = nibras_cfg()
    assert is_how_where_ui("How do I apply for a new loan?")
    assert place_topic("How do I apply for a new loan?") == "loans"
    nav = resolve_navigation("How do I apply for a new loan?", cfg)
    assert nav.action in ("navigate", "disambiguate")
    where = resolve_navigation("Where can I find my leave balance?", cfg)
    assert where.action in ("navigate", "disambiguate")
    types = resolve_navigation("What types of loans are available?", cfg)
    assert types.action == "none"


def test_nav_commands_that_were_missing():
    cfg = nibras_cfg()
    assert resolve_navigation("Show me the loans section", cfg).action in (
        "navigate", "disambiguate",
    )
    assert resolve_navigation("Show my payslips", cfg).action in (
        "navigate", "disambiguate",
    )
    assert resolve_navigation("Go back to home", cfg).action == "navigate"
    assert resolve_navigation("Go back to home", cfg).targets[0].route == "/my"


def test_notification_faq_not_a_fake_route():
    cfg = nibras_cfg()
    assert resolve_navigation("Show me the notifications", cfg).action == "none"
    assert is_notification_faq("Show me the notifications")
    hit = try_zero_llm_answer("Show me the notifications")
    assert hit and hit["gate"] == "notification_faq"
    assert "bell" in hit["text"].lower()


def test_payroll_when_still_not_nav():
    cfg = nibras_cfg()
    assert resolve_navigation(
        "When will next month's payroll be processed?", cfg,
    ).action == "none"


@pytest.mark.django_db(transaction=True)
def test_thanks_and_clock_are_zero_llm():
    from django.test import override_settings

    from ai.engine.core.config import get_settings
    from ai.engine_runtime import dispatch_task
    from ai.store import reset_store

    get_settings.cache_clear()
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        try:
            thanks = dispatch_task(
                "chat",
                {
                    "message": "Thank you",
                    "conversation_history": {
                        "conversation_id": "conv-c8-thanks",
                        "messages": [],
                    },
                },
                instance_id="nibras",
            )
            result = thanks.get("result") or {}
            assert result.get("turn_decision") == "answer"
            assert int(result.get("llm_calls") or 0) == 0

            clock = dispatch_task(
                "chat",
                {
                    "message": "What is today's date?",
                    "conversation_history": {
                        "conversation_id": "conv-c8-clock",
                        "messages": [],
                    },
                },
                instance_id="nibras",
            )
            clock_r = clock.get("result") or {}
            assert clock_r.get("turn_decision") == "answer"
            assert int(clock_r.get("llm_calls") or 0) == 0
        finally:
            reset_store()
            get_settings.cache_clear()


def test_bare_fact_is_stored_remember_is_not():
    assert extract_stated_facts("My project code is ALPHA-2025") == [
        {"key": "project code", "value": "ALPHA-2025"},
    ]
    assert is_remember_store("Please remember that my project code is ALPHA-2025")
    assert extract_stated_facts(
        "Please remember that my project code is ALPHA-2025",
    ) == []


def test_memory_recall_and_thanks_mention_the_fact():
    facts = [{"key": "project code", "value": "ALPHA-2025"}]
    assert is_memory_use("Can you confirm you have that?", facts)
    assert is_memory_use("What is my project code?", facts)
    assert is_memory_use("I work on three projects", facts)
    confirm = try_zero_llm_answer(
        "Can you confirm you have that?", facts=facts,
    )
    assert confirm and confirm["gate"] == "memory_recall"
    assert "ALPHA-2025" in confirm["text"]
    thanks = try_zero_llm_answer("Thank you", facts=facts)
    assert thanks and "ALPHA-2025" in thanks["text"]
    store = try_zero_llm_answer(
        "My project code is ALPHA-2025",
        facts=facts,
        newly_stored=True,
    )
    assert store and store["gate"] in {"memory_store", "memory_recall"}
    assert "ALPHA-2025" in store["text"]
    state = ConversationState()
    remember_facts(state, facts)
    assert any(r.get("tool") == "user_fact" for r in state.last_results)


def test_date_deixis_uses_last_assistant_date():
    assert is_date_deixis("Is that before the end of the month?")
    history = [{
        "role": "assistant",
        "content": "Your next payday is September 25, 2026.",
    }]
    text = render_date_deixis(
        "Is that before the end of the month?",
        history,
        date(2026, 9, 23),
    )
    assert text and "September 25" in text and "before" in text.lower()
    hit = try_zero_llm_answer(
        "Is that before the end of the month?",
        today=date(2026, 9, 23),
        history=history,
    )
    assert hit and hit["gate"] == "date_deixis"


@pytest.mark.django_db(transaction=True)
def test_stated_fact_is_recalled_at_zero_llm():
    from django.test import override_settings

    from ai.engine.core.config import get_settings
    from ai.engine_runtime import dispatch_task
    from ai.store import reset_store

    get_settings.cache_clear()
    history = {"conversation_id": "conv-c10-fact", "messages": []}
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        try:
            first = dispatch_task(
                "chat",
                {"message": "My project code is ALPHA-2025", "conversation_history": history},
                instance_id="nibras",
            )
            r1 = first.get("result") or {}
            assert r1.get("turn_decision") == "answer"
            assert int(r1.get("llm_calls") or 0) == 0
            assert "ALPHA-2025" in (r1.get("content") or "")
            history["messages"] += [
                {"role": "user", "content": "My project code is ALPHA-2025"},
                {"role": "assistant", "content": r1.get("content") or ""},
            ]
            second = dispatch_task(
                "chat",
                {
                    "message": "What is my project code?",
                    "conversation_history": history,
                },
                instance_id="nibras",
            )
            r2 = second.get("result") or {}
            assert r2.get("turn_decision") == "answer"
            assert int(r2.get("llm_calls") or 0) == 0
            assert "ALPHA-2025" in (r2.get("content") or "")
        finally:
            reset_store()
            get_settings.cache_clear()


def test_short_labels_do_not_hijack_my_or_takehome():
    cfg = nibras_cfg()
    assert resolve_navigation(
        "Please remember that my project code is ALPHA-2025", cfg,
    ).action == "none"
    assert resolve_navigation(
        "After the GOSI deduction your take-home is 3700 SAR", cfg,
    ).action == "none"
