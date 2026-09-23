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
    is_empty_payslip_tool_result,
    last_payslip_was_empty,
    is_notification_faq,
    is_thanks,
    payslip_lines_from_state,
    profile_from_state,
    render_clock,
    render_date_deixis,
    render_empty_payslip_answer,
    render_payslip_grounded,
    render_profile_grounded,
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
    when = try_zero_llm_answer("When will next month's payroll be processed?")
    assert when and when["gate"] == "payroll_schedule" and when["decision"] == "answer"
    assert "25" not in when["text"]
    download = try_zero_llm_answer("Can I download my payslip?")
    assert download and download["gate"] == "payslip_download"
    assert "my" in download["text"].lower()
    assert try_zero_llm_answer("What was my net pay last month?") is None
    empty = [{"api": "list_my_payslips", "digest": "call_host_api list_my_payslips: count=0"}]
    follow = try_zero_llm_answer(
        "What deductions were applied?",
        last_results=empty,
    )
    assert follow and follow["gate"] == "empty_payslip_recall"
    assert "4500" not in follow["text"] and "4,500" not in follow["text"]
    total = try_zero_llm_answer(
        "So my total deductions are 2,000 SAR?",
        last_results=empty,
    )
    assert total and "2,000" in total["text"]
    assert "confirm" in total["text"].lower()
    tools = [{
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "list_my_payslips"},
        "result": {"status_code": 200, "data": {"count": 0, "results": []}},
    }]
    assert is_empty_payslip_tool_result(tools)
    first = render_empty_payslip_answer("What was my net pay last month?")
    assert "4500" not in first and "4,500" not in first
    from_history = try_zero_llm_answer(
        "And after GOSI is deducted, what is my take-home?",
        history=[{
            "role": "assistant",
            "content": "I checked your payslip records and found no payslips on file.",
        }],
    )
    assert from_history and from_history["gate"] == "empty_payslip_recall"
    # A payslip digest without count= must not hide the history fallback.
    blocked = try_zero_llm_answer(
        "What deductions were applied?",
        last_results=[{
            "api": "list_my_payslips",
            "digest": "call_host_api list_my_payslips: status=ok",
        }],
        history=[{
            "role": "assistant",
            "content": "I checked your payslip records and found no payslips on file.",
        }],
    )
    assert blocked and blocked["gate"] == "empty_payslip_recall"
    json_only = [{
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "list_my_payslips"},
        "result": '{"status_code": 200, "data": {"count": 0, "results": []}}',
    }]
    assert is_empty_payslip_tool_result(json_only)
    on_file = try_zero_llm_answer(
        "What was the loan amount?",
        history=[{
            "role": "assistant",
            "content": "No payslips are on file for your account.",
        }],
    )
    assert on_file and on_file["gate"] == "empty_payslip_recall"


def test_payslip_recall_uses_committed_identity():
    digest = [{
        "api": "list_my_payslips",
        "digest": (
            "call_host_api list_my_payslips: "
            "count=4, gross=6500, gosi=1200, loan_installment=800, net=4500"
        ),
    }]
    assert payslip_lines_from_state(digest)["net"] == "4500"
    assert last_payslip_was_empty(digest) is False
    net = try_zero_llm_answer("What was my net pay last month?", last_results=digest)
    assert net and net["gate"] == "payslip_recall" and "4500" in net["text"]
    deductions = try_zero_llm_answer("What deductions were applied?", last_results=digest)
    assert deductions and "GOSI" in deductions["text"] and "1200" in deductions["text"]
    after = render_payslip_grounded(
        "And after GOSI is deducted, what is my take-home?",
        payslip_lines_from_state(digest),
    )
    assert after and "5300" in after and "3700" not in after
    total = try_zero_llm_answer(
        "So my total deductions are 2,000 SAR?",
        last_results=digest,
    )
    assert total and "2000" in total["text"]
    loan = try_zero_llm_answer("What was the loan amount?", last_results=digest)
    assert loan and "800" in loan["text"]
    arabic = try_zero_llm_answer("فما صافي راتبي؟", last_results=digest)
    assert arabic and arabic["gate"] == "payslip_recall"
    assert "4500" in arabic["text"] and "صافي" in arabic["text"]
    appeal = try_zero_llm_answer(
        "هل يمكنني الاعتراض على الخصومات؟",
        last_results=digest,
    )
    assert appeal is None or appeal["gate"] != "payslip_recall"
    deducted = try_zero_llm_answer("كم يتم خصمه من راتبي؟", last_results=digest)
    assert deducted and "GOSI" in deducted["text"] and "1200" in deducted["text"]


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


@pytest.mark.django_db(transaction=True)
def test_thanks_after_complete_write_is_ack_not_handoff():
    """F-LIVE-10: after Chat hands off a bound write, thanks is answer at 0 LLM."""
    from django.test import override_settings

    from ai.engine.core.config import get_settings
    from ai.engine_runtime import dispatch_task
    from ai.store import reset_store

    get_settings.cache_clear()
    history = {"conversation_id": "conv-f-live-10", "messages": []}
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        try:
            first = dispatch_task(
                "chat",
                {
                    "message": "I need 3000 SAR for an emergency loan",
                    "conversation_history": history,
                },
                instance_id="nibras",
            )
            r1 = first.get("result") or {}
            assert r1.get("turn_decision") == "handoff_agent"
            history["messages"] += [
                {
                    "role": "user",
                    "content": "I need 3000 SAR for an emergency loan",
                },
                {"role": "assistant", "content": r1.get("content") or ""},
            ]
            thanks = dispatch_task(
                "chat",
                {
                    "message": "Thank you for the help",
                    "conversation_history": history,
                },
                instance_id="nibras",
            )
            r2 = thanks.get("result") or {}
            assert r2.get("turn_decision") == "answer"
            assert int(r2.get("llm_calls") or 0) == 0
            text = (r2.get("content") or "").lower()
            assert "switch to agent" not in text
            assert "welcome" in text
        finally:
            reset_store()
            get_settings.cache_clear()


@pytest.mark.django_db(transaction=True)
def test_empty_payslip_history_is_zero_llm_on_dispatch():
    """Follow-up after an empty-payslip reply must not spend IntentResolver."""
    from django.test import override_settings

    from ai.engine.core.config import get_settings
    from ai.engine_runtime import dispatch_task
    from ai.store import reset_store

    get_settings.cache_clear()
    history = {
        "conversation_id": "conv-empty-payslip-recall",
        "messages": [
            {"role": "user", "content": "What was my net pay last month?"},
            {
                "role": "assistant",
                "content": (
                    "I checked your payslip records and found no payslips on file."
                ),
            },
        ],
    }
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        try:
            follow = dispatch_task(
                "chat",
                {
                    "message": "What deductions were applied?",
                    "conversation_history": history,
                },
                instance_id="nibras",
            )
            result = follow.get("result") or {}
            assert result.get("turn_decision") == "answer"
            assert int(result.get("llm_calls") or 0) == 0
            text = result.get("content") or ""
            assert "4500" not in text and "4,500" not in text
            assert "payslip" in text.lower() or "قسائم" in text
        finally:
            reset_store()
            get_settings.cache_clear()


def test_profile_recall_uses_host_identity():
    digest = [{
        "api": "get_my_profile",
        "digest": (
            "call_host_api get_my_profile: "
            "employee_no=1067, department=Coiled Tubing, "
            "manager=Mohammad Bolto Ali"
        ),
    }]
    assert profile_from_state(digest)["department"] == "Coiled Tubing"
    number = try_zero_llm_answer("What number did you give me?", last_results=digest)
    assert number and number["gate"] == "profile_recall" and "1067" in number["text"]
    dept = render_profile_grounded(
        "And what department did I mention?",
        profile_from_state(digest),
    )
    assert dept and "Coiled Tubing" in dept and "Engineering" not in dept
    manager = try_zero_llm_answer("And who is my manager?", last_results=digest)
    assert manager and "Mohammad Bolto Ali" in manager["text"]


def test_resolve_grounded_does_not_invent_job():
    from ai.engine.cognition.turn.zero_llm import render_resolve_grounded

    text = render_resolve_grounded("Tell me about Reena", {
        "found": True,
        "action": "match",
        "record": {
            "full_name": "Reena Sekaran",
            "employee_no": "1009",
            "org_unit": {"name": "CEO Office"},
        },
    })
    assert text and "Reena Sekaran" in text and "1009" in text
    assert "CEO Office" in text
    assert "Senior Analyst" not in text and "Finance" not in text
    many = render_resolve_grounded("Salman", {
        "found": False,
        "action": "disambiguate",
        "candidates": [
            {"full_name": "Hayssam Salman Al-Zakout", "employee_no": "17"},
            {"full_name": "Salman Ali Hussain Zakareya", "employee_no": "2403"},
        ],
    })
    assert many and "Hayssam" in many and "Salman" in many
    deny = render_resolve_grounded("Tell me about Reena", {
        "found": False,
        "unauthorized": True,
        "status_code": 403,
        "message": "Not authorized to look up other employees (people:view required).",
    })
    assert deny and "Not authorized" in deny and "Senior Analyst" not in deny


def test_stated_full_name_is_a_fact():
    facts = extract_stated_facts("Correct. My name is Mohamed Hassan")
    assert facts == [{"key": "name", "value": "Mohamed Hassan"}]
    hit = try_zero_llm_answer("What is my full name?", facts=facts)
    assert hit and hit["gate"] == "memory_recall"
    assert "Mohamed" in hit["text"] and "Hassan" in hit["text"]
    assert is_memory_use("What is my full name?", facts)
    assert not is_memory_use("My manager's name is?", facts)
    assert not is_memory_use("And who is my manager?", facts)
    assert try_zero_llm_answer("My manager's name is?", facts=facts) is None


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
