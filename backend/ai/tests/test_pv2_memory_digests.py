"""PV2-1C — memory_manager wired into Chat + per-message tool digests.

Covers:
  * learn_fact recall through the real Chat-confirm path (ADR-0046: memory
    confirm is Chat's only write): turn 1 stages ``learn_fact`` → the user
    confirms via the workspace confirm endpoint → turn 3 answers from the
    memory block. Negative control: an unconfirmed card is never recalled.
  * ``build_tool_digest`` — ≤ 200 chars, scalar fields only, restricted
    fields dropped, records outside the retrieval org-unit scope dropped.
  * ``assemble_context`` appends the persisted digest to assistant history
    messages; growth ≤ 200 chars per digested message.
  * The digest rides the engine result → ChatResponse → message metadata.
  * Offline runner: engine ``Settings`` really sees the single-pass flags.
"""

from __future__ import annotations

import json
import os
import types
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from ai.engine.core.config import get_settings
from ai.store import reset_store


# ── Scripted stub LLM ────────────────────────────────────────────────────


def _tool_names(kw: dict) -> set[str]:
    names = set()
    for tool in kw.get("tools") or []:
        fn = (tool or {}).get("function") or {}
        if fn.get("name"):
            names.add(fn["name"])
    return names


def _last_user_text(kw: dict) -> str:
    for msg in reversed(kw.get("messages") or []):
        if msg.get("role") == "user":
            return str(msg.get("content") or "")
    return ""


def _system_text(kw: dict) -> str:
    return "\n".join(
        str(m.get("content") or "")
        for m in kw.get("messages") or []
        if m.get("role") == "system"
    )


def _has_tool_result(kw: dict) -> bool:
    return any(m.get("role") == "tool" for m in kw.get("messages") or [])


def _scripted_client(decide):
    """OpenAI-shaped stub whose reply is a function of the request."""
    calls: list[dict] = []

    async def _create(**kw):
        calls.append(kw)
        content, tool_calls = decide(kw)
        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(content=content, tool_calls=tool_calls),
                    finish_reason="tool_calls" if tool_calls else "stop",
                )
            ],
            usage=types.SimpleNamespace(
                prompt_tokens=10, completion_tokens=4, total_tokens=14,
            ),
        )

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=_create))
    )
    return client, calls


def _tool_call(name: str, args: dict, call_id: str = "call_1"):
    return [
        types.SimpleNamespace(
            id=call_id,
            type="function",
            function=types.SimpleNamespace(name=name, arguments=json.dumps(args)),
        )
    ]


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def django_store():
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


@pytest.fixture
def single_pass(monkeypatch):
    monkeypatch.setenv("AGENT_ORCHESTRATOR_ENABLED", "false")
    monkeypatch.setenv("KG_MULTI_STEP_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def no_nav_fast_path(monkeypatch):
    patched = get_settings().model_copy(update={"NAVIGATION_RESOLVER_ENABLED": False})
    monkeypatch.setattr("ai.engine.cognition.turn.runner.get_settings", lambda: patched)


# ── 1. learn_fact recall via the Chat-confirm path ──────────────────────

_FACT = "my cost centre is CC-42"


def _cost_centre_decide(kw: dict):
    user_text = _last_user_text(kw).lower()
    if (
        "learn_fact" in _tool_names(kw)
        and "cost centre is cc-42" in user_text
        and not _has_tool_result(kw)
    ):
        return None, _tool_call("learn_fact", {"fact": _FACT, "category": "observation"})
    if "cost centre is cc-42" in user_text:
        return "Noted — confirm the card and I will remember it.", None
    if "cost centre" in user_text:
        # Answer ONLY from the system prompt (memory block), never from history.
        if "CC-42" in _system_text(kw):
            return "Your cost centre is CC-42.", None
        return "I don't have a cost centre on record for you.", None
    return "Happy to help.", None


def _chat_turn(conversation_id: str, host_user_id: str, message: str, history: list[dict]):
    from ai.engine_runtime import dispatch_task

    data = dispatch_task(
        "chat",
        {
            "message": message,
            "host_user_id": host_user_id,
            "conversation_history": {
                "conversation_id": conversation_id,
                "messages": list(history),
            },
        },
        instance_id="carbon",
    )
    assert data.get("status") == "completed", data
    return data["result"]


def _run_cost_centre_conversation(*, confirm: bool):
    from accounts.models import User
    from ai.models import AIConversation, MemoryLongTerm

    user = User.objects.create_user(username=f"pv2-1c-{confirm}", password="secret123")
    conversation = AIConversation.objects.create(
        user=user,
        title="PV2-1C memory",
        conversation_type="chat",
        app_identifier="carbon",
        task_payload_json={},
        scope_json={},
    )
    conv_id = str(conversation.id)
    uid = str(user.pk)
    client, _calls = _scripted_client(_cost_centre_decide)
    history: list[dict] = []

    with patch("ai.engine.llm.provider.get_llm_client", return_value=client):
        t1 = _chat_turn(conv_id, uid, "Please remember that my cost centre is CC-42", history)
        memory_cards = [p for p in t1.get("pending_actions") or [] if p.get("kind") == "memory"]
        assert memory_cards, t1
        assert memory_cards[0]["fact"] == _FACT
        # Chat staged nothing but the memory card (ADR-0046 / G2).
        assert all(p.get("kind") == "memory" for p in t1.get("pending_actions") or [])
        assert not MemoryLongTerm.objects.filter(content=_FACT).exists()

        if confirm:
            from django.urls import reverse
            from rest_framework.test import APIClient

            api = APIClient()
            api.force_authenticate(user=user)
            resp = api.post(
                reverse(
                    "ai-workspace-conversation-confirm-tool-execution",
                    kwargs={"pk": conversation.id},
                ),
                {"execution_id": memory_cards[0]["execution_id"]},
                format="json",
            )
            assert resp.status_code == 200, resp.data
            row = MemoryLongTerm.objects.get(content=_FACT)
            assert row.host_user_id == uid
            assert row.visibility == "private"

        history += [
            {"role": "user", "content": "Please remember that my cost centre is CC-42"},
            {"role": "assistant", "content": t1.get("content") or ""},
        ]
        t2 = _chat_turn(conv_id, uid, "Thanks, that is all for now", history)
        history += [
            {"role": "user", "content": "Thanks, that is all for now"},
            {"role": "assistant", "content": t2.get("content") or ""},
        ]
        t3 = _chat_turn(conv_id, uid, "What's my cost centre?", history)
    return user, t3


@pytest.mark.django_db(transaction=True)
def test_learn_fact_confirmed_in_chat_is_recalled_two_turns_later(
    django_store, single_pass, no_nav_fast_path,
):
    _user, t3 = _run_cost_centre_conversation(confirm=True)
    assert "CC-42" in (t3.get("content") or ""), t3.get("content")


@pytest.mark.django_db(transaction=True)
def test_unconfirmed_learn_fact_is_not_recalled(
    django_store, single_pass, no_nav_fast_path,
):
    _user, t3 = _run_cost_centre_conversation(confirm=False)
    assert "CC-42" not in (t3.get("content") or ""), t3.get("content")


@pytest.mark.django_db(transaction=True)
def test_private_fact_is_invisible_to_another_user(django_store):
    """Tenancy: the bound host user scopes long-term recall (RULE_20)."""
    from asgiref.sync import async_to_sync

    from ai.engine.core.database import get_session_factory
    from ai.engine.memory.manager import MemoryManager
    from ai.models import MemoryLongTerm

    MemoryLongTerm.objects.create(
        id="pv2-1c-private-fact",
        instance_id="carbon",
        category="observation",
        content=_FACT,
        source="test",
        confidence=1.0,
        host_user_id="7001",
        visibility="private",
    )

    async def _recall(uid):
        async with get_session_factory("carbon")() as db:
            ctx = await MemoryManager(db, host_user_id=uid).retrieve_relevant_context(
                "carbon", "conv-x", "What's my cost centre?",
            )
            return ctx.to_prompt_text()

    assert "CC-42" in async_to_sync(_recall)("7001")
    assert "CC-42" not in async_to_sync(_recall)("7002")
    assert "CC-42" not in async_to_sync(_recall)(None)


# ── 2. Tool digests ──────────────────────────────────────────────────────


def _host_api_tool(data, api_name="get_my_loan_eligibility"):
    return {
        "tool_name": "call_host_api",
        "tool_args": {"api_name": api_name},
        "result": json.dumps({"status_code": 200, "data": data}),
        "latency_ms": 4,
    }


def test_digest_carries_scalar_fields_within_budget():
    from ai.engine.cognition.tool_digest import DIGEST_MAX_CHARS, build_tool_digest

    digest = build_tool_digest(
        [_host_api_tool({
            "eligible": True, "max_amount": 8000, "currency": "SAR",
            "org_unit_id": 5, "national_id": "1029384756",
            "bank_account_iban": "SA0380000000608010167519",
        })],
        scope={"org_unit_ids": [5], "org_unit_id": 5},
    )
    assert "get_my_loan_eligibility" in digest
    assert "eligible=true" in digest
    assert "max_amount=8000" in digest
    assert "SAR" in digest
    # Restricted identifiers never enter the prompt.
    assert "1029384756" not in digest and "national_id" not in digest
    assert "SA038" not in digest and "iban" not in digest.lower()
    assert len(digest) <= DIGEST_MAX_CHARS


def test_digest_compacts_payslip_identity():
    from ai.engine.cognition.tool_digest import DIGEST_MAX_CHARS, build_tool_digest

    rows = [
        {"line_type": {"code": "gross", "label": "Gross"}, "amount": "6500.000",
         "employee_name": "Bilagot Panta Suerte", "rule_id": "pulse_audit_c2"},
        {"line_type": {"code": "gosi", "label": "GOSI"}, "amount": "1200.000"},
        {"line_type": {"code": "loan_installment", "label": "Loan"}, "amount": "800.000"},
        {"line_type": {"code": "net", "label": "Net"}, "amount": "4500.000"},
    ]
    digest = build_tool_digest(
        [_host_api_tool({"count": 4, "results": rows}, api_name="list_my_payslips")],
        scope=None,
    )
    assert "list_my_payslips" in digest
    assert "gross=6500" in digest
    assert "gosi=1200" in digest
    assert "loan_installment=800" in digest
    assert "net=4500" in digest
    assert "Bilagot" not in digest
    assert len(digest) <= DIGEST_MAX_CHARS


def test_digest_compacts_profile_identity():
    from ai.engine.cognition.tool_digest import DIGEST_MAX_CHARS, build_tool_digest

    digest = build_tool_digest(
        [_host_api_tool({
            "employee_no": "1067",
            "full_name": "Bilagot Panta Suerte",
            "job_title": "Heavy Duty Driver",
            "org_unit": {"id": 6, "name": "Coiled Tubing"},
            "manager": {"id": 3, "name": "Mohammad Bolto Ali"},
        }, api_name="get_my_profile")],
        scope=None,
    )
    assert "get_my_profile" in digest
    assert "employee_no=1067" in digest
    assert "department=Coiled Tubing" in digest
    assert "manager=Mohammad Bolto Ali" in digest
    assert digest.count("name=") == 0
    assert len(digest) <= DIGEST_MAX_CHARS


def test_digest_drops_records_outside_retrieval_scope():
    from ai.engine.cognition.tool_digest import build_tool_digest

    rows = [
        {"name": "Own Team Member", "org_unit_id": 5, "leave_balance": 12},
        {"name": "Other Org Person", "org_unit_id": 9, "salary": 99000},
    ]
    tools = [_host_api_tool({"results": rows}, api_name="list_team")]

    digest = build_tool_digest(tools, scope={"org_unit_ids": [5]})
    assert "Own Team Member" in digest and "leave_balance=12" in digest
    assert "Other Org Person" not in digest
    assert "salary" not in digest and "99000" not in digest

    # No org context → only unscoped fields survive (global-only, like P4-02).
    unscoped = build_tool_digest(tools, scope=None)
    assert "Own Team Member" not in unscoped and "Other Org Person" not in unscoped


def test_digest_is_hard_capped_and_skips_staged_and_failed_tools():
    from ai.engine.cognition.tool_digest import DIGEST_MAX_CHARS, build_tool_digest

    wide = {f"field_{i}": "v" * 30 for i in range(40)}
    assert len(build_tool_digest([_host_api_tool(wide)], scope=None)) <= DIGEST_MAX_CHARS

    staged = {
        "tool_name": "learn_fact",
        "result": json.dumps({"requires_confirmation": True, "execution_id": "e1", "fact": "x"}),
    }
    failed = {"tool_name": "call_host_api", "result": None, "error": "boom"}
    assert build_tool_digest([staged, failed], scope=None) == ""
    assert build_tool_digest([], scope=None) == ""


def _adapter_stub():
    adapter = MagicMock()
    adapter.build_user_profile.return_value = None
    adapter.resolve_mentions.return_value = []
    adapter.user_memory_enabled.return_value = False
    adapter.retrieve_knowledge_graph.return_value = ([], 0)
    adapter.retrieve_long_term_memory.return_value = ([], 0)
    return adapter


def test_assemble_context_appends_digest_within_200_chars():
    from ai.context_assembler import HISTORY_DIGEST_MAX_CHARS, assemble_context

    digest = "call_host_api get_my_loan_eligibility: eligible=true, max_amount=8000, currency=SAR"
    long_digest = "x" * 500
    messages = [
        {"id": 1, "role": "user", "content": "Am I eligible for a loan?", "metadata_json": {}},
        {"id": 2, "role": "assistant", "content": "Yes, you are.",
         "metadata_json": {"tool_digest": digest}},
        {"id": 3, "role": "user", "content": "ok", "metadata_json": {"tool_digest": digest}},
        {"id": 4, "role": "assistant", "content": "Sure.", "metadata_json": {}},
        {"id": 5, "role": "assistant", "content": "Again.",
         "metadata_json": {"tool_digest": long_digest}},
        {"id": 6, "role": "assistant", "content": "No meta."},
    ]
    conversation = types.SimpleNamespace(summary="", task_payload_json={}, context_snapshot_json={})
    out = assemble_context(conversation, messages, scope=None, adapter=_adapter_stub())
    history = [m for m in out["messages"] if m["role"] in ("user", "assistant")]

    assert HISTORY_DIGEST_MAX_CHARS == 200
    assert history[1]["content"].startswith("Yes, you are.")
    assert "max_amount=8000" in history[1]["content"]
    # User turns and digest-less assistant turns are untouched.
    assert history[0]["content"] == "Am I eligible for a loan?"
    assert history[2]["content"] == "ok"
    assert history[3]["content"] == "Sure."
    assert history[5]["content"] == "No meta."
    # Hard budget: ≤ 200 chars growth per digested message.
    for original, rendered in ((messages[1], history[1]), (messages[4], history[4])):
        growth = len(rendered["content"]) - len(original["content"])
        assert 0 < growth <= HISTORY_DIGEST_MAX_CHARS


def test_digest_travels_engine_result_to_message_metadata():
    """ChatResponse maps ``tool_digest``; the saved message persists it."""
    from ai.providers.pulse import PulseProvider

    fake = {"status": "completed", "result": {"content": "ok", "tool_digest": "t: a=1"}}
    with patch("ai.providers.pulse.dispatch_task", return_value=fake):
        provider = PulseProvider.__new__(PulseProvider)
        provider._instance_id = "carbon"
        with patch.object(PulseProvider, "_chat_payload", return_value={}):
            resp = provider.chat(MagicMock())
    assert resp.tool_digest == "t: a=1"


@pytest.mark.django_db
def test_build_ai_message_persists_tool_digest():
    from accounts.models import User
    from ai.intelligence import CarbonIntelligence
    from ai.models import AIConversation, AIMessage

    user = User.objects.create_user(username="pv2-1c-meta", password="secret123")
    conversation = AIConversation.objects.create(
        user=user, title="d", conversation_type="chat",
        task_payload_json={}, scope_json={},
    )
    intel = CarbonIntelligence.__new__(CarbonIntelligence)
    intel._build_ai_message(conversation, "completed", "ok", [], tool_digest="t: a=1")
    msg = AIMessage.objects.filter(conversation=conversation, role="assistant").latest("created_at")
    assert msg.metadata_json["tool_digest"] == "t: a=1"


_LOAN_RESULT = {
    "eligible": True, "max_amount": 8000, "currency": "SAR", "national_id": "1029384756",
}


def _loan_decide(kw: dict):
    user_text = _last_user_text(kw).lower()
    if "call_host_api" in _tool_names(kw) and "eligible" in user_text and not _has_tool_result(kw):
        return None, _tool_call("call_host_api", {"api_name": "get_my_loan_eligibility"})
    if "maximum" in user_text:
        blob = json.dumps(kw.get("messages") or [])
        if "max_amount=8000" in blob:
            return "Your maximum is 8000 SAR.", None
        return "I no longer have that figure.", None
    return "You are eligible.", None


@pytest.mark.django_db(transaction=True)
def test_tool_digest_lets_the_model_recall_three_turns_later(
    django_store, single_pass, no_nav_fast_path,
):
    """Turn 1 tool result → digest persisted → turn 4 recalls it from history."""
    from ai.context_assembler import render_history_content

    async def _fake_tool(tool_call, *args, **kwargs):
        return {
            "tool_name": "call_host_api",
            "tool_args": {"api_name": "get_my_loan_eligibility"},
            "tool_call_id": tool_call.get("id", ""),
            "result": json.dumps({"status_code": 200, "data": _LOAN_RESULT}),
            "latency_ms": 3,
        }

    client, _calls = _scripted_client(_loan_decide)
    history: list[dict] = []
    with patch("ai.engine.llm.provider.get_llm_client", return_value=client), patch(
        "ai.engine.cognition.turn.execute._execute_single_tool", side_effect=_fake_tool,
    ):
        t1 = _chat_turn("conv-pv2-1c-digest", None, "Am I eligible for a loan?", history)
        digest = t1.get("tool_digest") or ""
        assert "eligible=true" in digest and "max_amount=8000" in digest, t1
        assert "1029384756" not in digest
        history += [
            {"role": "user", "content": "Am I eligible for a loan?"},
            {"role": "assistant", "content": render_history_content(
                {"role": "assistant", "content": t1.get("content") or "",
                 "metadata_json": {"tool_digest": digest}},
            )},
        ]
        for filler in ("Thanks", "Good to know"):
            t = _chat_turn("conv-pv2-1c-digest", None, filler, history)
            history += [
                {"role": "user", "content": filler},
                {"role": "assistant", "content": t.get("content") or ""},
            ]
        t4 = _chat_turn("conv-pv2-1c-digest", None, "What was the maximum again?", history)
    assert "8000" in (t4.get("content") or ""), t4.get("content")


# ── 3. Offline runner settings reach the engine ─────────────────────────


def test_runner_single_pass_env_reaches_engine_settings(monkeypatch):
    from ai.eval.multiturn.runner import CAVEATS, engine_single_pass

    monkeypatch.setenv("AGENT_ORCHESTRATOR_ENABLED", "true")
    monkeypatch.delenv("KG_MULTI_STEP_ENABLED", raising=False)
    get_settings.cache_clear()
    assert get_settings().AGENT_ORCHESTRATOR_ENABLED is True

    with engine_single_pass():
        s = get_settings()
        assert s.AGENT_ORCHESTRATOR_ENABLED is False
        assert s.KG_MULTI_STEP_ENABLED is False

    # Restored exactly (env + cache).
    assert os.environ["AGENT_ORCHESTRATOR_ENABLED"] == "true"
    assert "KG_MULTI_STEP_ENABLED" not in os.environ
    assert get_settings().AGENT_ORCHESTRATOR_ENABLED is True
    get_settings.cache_clear()

    text = " ".join(CAVEATS)
    assert "override_settings" not in text or "does not" in text
    assert "engine Settings" in text
