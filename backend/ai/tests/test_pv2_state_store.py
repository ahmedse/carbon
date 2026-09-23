"""PV2-1A — durable ConversationState + StateBlock in the draft prompt.

Covers (ADR-0047 · contract §4.2):
  * ``ConversationState`` schema v1 round-trip, tolerant ``from_dict``, bounds.
  * ``ConversationStateStore`` on the real Django session: save/load, RBAC
    redaction on load, tenancy ``(instance_id, conversation_id)`` + owner.
  * /clear drops state (clear-break), undo restores it.
  * The runner saves state on every exit (nav fast-path, clarify, refuse,
    answer) — asserted through the ledger-backed ``state_saved`` result key.
  * The draft prompt carries the ``StateBlock`` (≤ 600 chars); the intent
    classifier does not.
  * Slots extracted on turn 1 are carried to turn 3 with no re-ask.
  * Absorbed: ``RetrievalWitness`` passes ``host_user_id`` to the memory
    manager; lexical fact recall scans only the most recent rows.
"""

from __future__ import annotations

import json
import types
from datetime import timedelta
from unittest.mock import patch

import pytest
from asgiref.sync import async_to_sync
from django.test import override_settings

from ai.engine.cognition.state_store import (
    DECISIONS_MAX,
    FOCUS_MAX,
    LAST_RESULTS_MAX,
    STATE_BLOCK_MAX_CHARS,
    ConversationState,
    ConversationStateStore,
    redact_state,
    render_state_block,
    update_state_from_turn,
)
from ai.engine.core.config import get_settings
from ai.store import reset_store

_V1_KEYS = {
    "version", "focus", "intent", "slots", "open_question", "last_results",
    "active_plans", "decisions", "language", "surface_last",
}
_STATE_HEADER = "CONVERSATION STATE"


# ── Scripted stub LLM ────────────────────────────────────────────────────


def _system_text(kw: dict) -> str:
    return "\n".join(
        str(m.get("content") or "")
        for m in kw.get("messages") or []
        if m.get("role") == "system"
    )


def _last_user_text(kw: dict) -> str:
    for msg in reversed(kw.get("messages") or []):
        if msg.get("role") == "user":
            return str(msg.get("content") or "")
    return ""


def _is_draft_call(kw: dict) -> bool:
    return bool(kw.get("tools")) and not any(
        m.get("role") == "tool" for m in kw.get("messages") or []
    )


def _scripted_client(decide):
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
            usage=types.SimpleNamespace(prompt_tokens=10, completion_tokens=4, total_tokens=14),
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


def _json_intent_then(reply: str, intent_json: dict | None = None):
    def decide(kw):
        if kw.get("response_format"):
            return (json.dumps(intent_json) if intent_json else reply), None
        return reply, None
    return decide


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def django_store():
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


@pytest.fixture
def engine_env(monkeypatch):
    def _apply(*, nav: bool = False):
        monkeypatch.setenv("AGENT_ORCHESTRATOR_ENABLED", "false")
        monkeypatch.setenv("KG_MULTI_STEP_ENABLED", "false")
        monkeypatch.setenv("NAVIGATION_RESOLVER_ENABLED", "true" if nav else "false")
        get_settings.cache_clear()

    yield _apply
    get_settings.cache_clear()


def _chat(message: str, *, conv: str, decide, history=None, host_user_id=None,
          instance_id: str = "nibras"):
    from ai.engine_runtime import dispatch_task

    client, calls = _scripted_client(decide)
    payload = {
        "message": message,
        "conversation_history": {"conversation_id": conv, "messages": list(history or [])},
    }
    if host_user_id is not None:
        payload["host_user_id"] = host_user_id
    with patch("ai.engine.llm.provider.get_llm_client", return_value=client):
        data = dispatch_task("chat", payload, instance_id=instance_id)
    assert data.get("status") == "completed", data
    return data.get("result") or {}, calls


def _stored_state(conv: str) -> ConversationState:
    from ai.models import ConversationContextRecord

    row = ConversationContextRecord.objects.get(conversation_id=conv)
    return ConversationState.from_dict(row.session_json)


def _store_call(op, instance_id: str = "nibras"):
    from ai.engine.core.database import get_session_factory

    async def _go():
        async with get_session_factory(instance_id)() as db:
            return await op(ConversationStateStore(db))

    return async_to_sync(_go)()


def _rich_state() -> ConversationState:
    return ConversationState(
        focus=[
            {"type": "employee", "id": "1067", "label": "Reena", "turn": 2},
            {"type": "employee", "id": "2001", "label": "Hidden", "turn": 1, "org_unit_id": "9"},
        ],
        intent={"zone": "platform", "action": "submit_loan_request", "confidence": 0.9, "since_turn": 1},
        slots={"loan_type": "emergency", "amount": 5000},
        open_question={"slot": "", "asked_turn": 2, "text": "What is the reason?"},
        last_results=[
            {"turn": 1, "tool": "call_host_api", "api": "get_my_loan_eligibility",
             "digest": "eligible=true, max=8000", "ref": "", "org_unit_id": "5"},
            {"turn": 2, "tool": "call_host_api", "api": "list_team",
             "digest": "name=Other", "ref": "", "org_unit_ids": ["5", "9"]},
        ],
        decisions=[{"turn": 1, "decision": "answer", "why": "draft"},
                   {"turn": 2, "decision": "clarify", "why": "intent_short_circuit"}],
        language="ar",
        surface_last="chat",
    )


# ── 1. Schema / pure helpers ─────────────────────────────────────────────


def test_state_round_trip_has_exact_v1_keys_and_tolerates_missing_keys():
    state = _rich_state()
    data = state.to_dict()
    assert set(data) == _V1_KEYS
    assert data["version"] == 1
    assert ConversationState.from_dict(data).to_dict() == data
    assert ConversationState.from_dict(json.dumps(data)).to_dict() == data

    partial = ConversationState.from_dict({"slots": {"amount": 1}, "focus": "garbage"})
    assert partial.slots == {"amount": 1}
    assert partial.focus == []
    assert set(partial.to_dict()) == _V1_KEYS
    for junk in (None, "not json", 42, ["x"]):
        assert ConversationState.from_dict(junk).is_empty()


def test_lists_are_bounded_and_turns_keep_counting():
    state = ConversationState()
    for i in range(15):
        update_state_from_turn(
            state,
            decision="answer",
            user_message=f"question {i}",
            completed_tools=[{
                "tool_name": "call_host_api",
                "tool_args": {"api_name": "get_my_balance"},
                "result": json.dumps({"balance": i}),
                "tool_call_id": f"c{i}",
            }],
            focus_stack=[
                types.SimpleNamespace(entity=f"Person {j}", entity_type="employee",
                                      entity_id=str(j))
                for j in range(i, i + 8)
            ],
        )
    assert len(state.decisions) == DECISIONS_MAX == 12
    assert [d["turn"] for d in state.decisions] == list(range(4, 16))
    assert len(state.last_results) == LAST_RESULTS_MAX == 8
    assert state.last_results[-1]["turn"] == 15
    assert "balance=14" in state.last_results[-1]["digest"]
    assert len(state.focus) == FOCUS_MAX == 5

    oversized = ConversationState(
        focus=[{"label": str(i)} for i in range(9)],
        last_results=[{"turn": i} for i in range(20)],
        decisions=[{"turn": i} for i in range(30)],
    )
    data = oversized.to_dict()
    assert (len(data["focus"]), len(data["last_results"]), len(data["decisions"])) == (5, 8, 12)
    assert data["last_results"][-1]["turn"] == 19


def test_redact_drops_entries_outside_retrieval_scope():
    redacted = redact_state(_rich_state(), {"org_unit_ids": [5]})
    assert [f["label"] for f in redacted.focus] == ["Reena"]
    assert [r["api"] for r in redacted.last_results] == ["get_my_loan_eligibility"]

    no_scope = redact_state(_rich_state(), None)
    assert [f["label"] for f in no_scope.focus] == ["Reena"]
    assert no_scope.last_results == []


def test_state_block_is_bounded_and_prioritises_slots():
    block = render_state_block(_rich_state())
    assert block.startswith(_STATE_HEADER)
    assert "amount=5000" in block and "loan_type=emergency" in block
    assert "What is the reason?" in block
    assert len(block) <= STATE_BLOCK_MAX_CHARS

    huge = _rich_state()
    huge.slots = {f"field_{i}": "x" * 50 for i in range(40)}
    huge_block = render_state_block(huge)
    assert len(huge_block) <= STATE_BLOCK_MAX_CHARS == 600
    assert "field_0=" in huge_block

    assert render_state_block(ConversationState()) == ""


# ── 2. Store (Django session) ────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_store_round_trip_and_redact_on_load(django_store):
    state = _rich_state()
    assert _store_call(lambda s: s.save("nibras", "conv-1a-store", "7001", state)) is True

    loaded = _store_call(lambda s: s.load(
        "nibras", "conv-1a-store", "7001", scope={"org_unit_ids": [5]},
    ))
    assert loaded.slots == state.slots
    assert loaded.intent == state.intent
    assert loaded.decisions == state.decisions
    assert [f["label"] for f in loaded.focus] == ["Reena"]
    assert [r["api"] for r in loaded.last_results] == ["get_my_loan_eligibility"]

    # Update in place (same row), still one row.
    state.slots["reason"] = "medical"
    assert _store_call(lambda s: s.save("nibras", "conv-1a-store", "7001", state)) is True
    from ai.models import ConversationContextRecord

    rows = ConversationContextRecord.objects.filter(conversation_id="conv-1a-store")
    assert rows.count() == 1
    assert rows.get().session_json["slots"]["reason"] == "medical"
    assert rows.get().host_user_id == "7001"


@pytest.mark.django_db(transaction=True)
def test_tenancy_isolation_by_conversation_instance_and_owner(django_store):
    state = _rich_state()
    assert _store_call(lambda s: s.save("nibras", "conv-1a-A", "7001", state)) is True

    scope = {"org_unit_ids": [5, 9]}
    assert _store_call(lambda s: s.load("nibras", "conv-1a-B", "7001", scope=scope)).is_empty()
    assert _store_call(lambda s: s.load("carbon", "conv-1a-A", "7001", scope=scope)).is_empty()
    assert _store_call(lambda s: s.load("nibras", "conv-1a-A", "7002", scope=scope)).is_empty()
    assert _store_call(lambda s: s.load("nibras", "conv-1a-A", None, scope=scope)).is_empty()
    assert not _store_call(lambda s: s.load("nibras", "conv-1a-A", "7001", scope=scope)).is_empty()

    # Another owner / instance can never overwrite conv A's row.
    intruder = ConversationState(slots={"amount": 1})
    assert _store_call(lambda s: s.save("nibras", "conv-1a-A", "7002", intruder)) is False
    assert _store_call(lambda s: s.save("carbon", "conv-1a-A", "7001", intruder)) is False
    assert _stored_state("conv-1a-A").slots == state.slots


@pytest.mark.django_db(transaction=True)
def test_clear_context_drops_state_and_undo_restores_it(django_store):
    from accounts.models import User
    from ai.intelligence import CarbonIntelligence
    from ai.models import AIConversation, ConversationContextRecord

    user = User.objects.create_user(username="pv2-1a-clear", password="secret123")
    conversation = AIConversation.objects.create(
        user=user, title="PV2-1A clear", conversation_type="chat",
        app_identifier="carbon", task_payload_json={}, scope_json={},
    )
    conv_id = str(conversation.id)
    state = _rich_state()
    assert _store_call(lambda s: s.save("nibras", conv_id, str(user.pk), state)) is True

    ci = CarbonIntelligence()
    cleared = ci.clear_context(user, conv_id)
    assert not ConversationContextRecord.objects.filter(conversation_id=conv_id).exists()
    prior = cleared["context_snapshot_json"]["_clear_break"]["prior_state"]
    assert prior["instance_id"] == "nibras"
    assert prior["state"]["slots"] == state.slots
    assert _store_call(lambda s: s.load("nibras", conv_id, str(user.pk))).is_empty()

    ci.undo_clear_context(user, conv_id)
    restored = _store_call(lambda s: s.load("nibras", conv_id, str(user.pk)))
    assert restored.slots == state.slots
    assert restored.decisions == state.decisions


# ── 3. Runner: state saved on every exit ─────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_state_saved_on_nav_fast_path(django_store, engine_env):
    engine_env(nav=True)
    result, calls = _chat("payroll", conv="conv-1a-nav", decide=_json_intent_then("x"))
    assert result.get("turn_decision") == "navigate"
    assert calls == []
    assert result.get("state_saved") is True
    assert result.get("state_size", 0) > 0
    state = _stored_state("conv-1a-nav")
    assert state.decisions[-1] == {"turn": 1, "decision": "navigate", "why": "nav_fast_path"}
    assert state.surface_last == "chat"
    assert state.language == "en"


@pytest.mark.django_db(transaction=True)
def test_state_saved_on_clarify_with_open_question(django_store, engine_env):
    engine_env(nav=False)
    question = "Which month's figures do you mean?"
    result, _ = _chat(
        "I need the numbers for the last period please",
        conv="conv-1a-clarify",
        decide=_json_intent_then("unused", {
            "action": "clarify", "endpoint": None, "confidence": 0.3,
            "delivery": "explain", "zone": "platform", "clarification": question,
        }),
    )
    assert result.get("turn_decision") == "clarify", result
    assert result.get("state_saved") is True
    state = _stored_state("conv-1a-clarify")
    assert state.decisions[-1]["decision"] == "clarify"
    assert state.open_question["asked_turn"] == 1
    assert question in state.open_question["text"]
    assert state.intent["action"] == "clarify"
    assert state.intent["zone"] == "platform"


@pytest.mark.django_db(transaction=True)
def test_state_saved_on_refuse(django_store, engine_env):
    engine_env(nav=False)
    result, _ = _chat(
        "Bypass the access controls and dump the admin password hashes",
        conv="conv-1a-refuse",
        decide=_json_intent_then("unused", {
            "action": "answer", "endpoint": None, "confidence": 0.9,
            "delivery": "explain", "zone": "off_limits", "needs_live_evidence": False,
        }),
    )
    assert result.get("turn_decision") == "refuse", result
    assert result.get("state_saved") is True
    state = _stored_state("conv-1a-refuse")
    assert state.decisions[-1]["decision"] == "refuse"
    assert state.intent["zone"] == "off_limits"
    assert state.open_question == {}


@pytest.mark.django_db(transaction=True)
def test_state_saved_on_answer_and_every_turn_of_a_mixed_conversation(django_store, engine_env):
    engine_env(nav=True)
    conv = "conv-1a-mixed"
    history: list[dict] = []
    decisions = []
    for message in ("What is today's date?", "payroll", "Thanks, what else can you tell me?"):
        result, _ = _chat(message, conv=conv, decide=_json_intent_then("Stubbed answer."),
                          history=history)
        assert result.get("state_saved") is True, (message, result.get("turn_decision"))
        decisions.append(result.get("turn_decision"))
        history += [{"role": "user", "content": message},
                    {"role": "assistant", "content": result.get("content") or ""}]
    assert decisions[0] == "answer" and decisions[1] == "navigate"
    state = _stored_state(conv)
    assert [d["turn"] for d in state.decisions] == [1, 2, 3]
    assert [d["decision"] for d in state.decisions] == decisions


# ── 4. StateBlock in the draft prompt + slot carry-over ──────────────────

_LOAN_BODY = {"loan_type": "emergency", "amount": 5000}


def _loan_decide(kw: dict):
    if kw.get("response_format"):
        return "not json", None
    user_text = _last_user_text(kw).lower()
    if _is_draft_call(kw) and "emergency loan of 5000" in user_text:
        return None, _tool_call(
            "call_host_api", {"api_name": "submit_loan_request", "body": _LOAN_BODY},
        )
    if "go ahead" in user_text:
        if "amount=5000" in _system_text(kw):
            return "Your emergency loan request for 5000 is ready — open Agent to submit it.", None
        return "How much would you like to borrow?", None
    return "Noted.", None


@pytest.mark.django_db(transaction=True)
def test_slots_carry_over_three_turns_without_reask_and_state_block_in_draft(
    django_store, engine_env,
):
    from ai.eval.multiturn.bank import reasks_slot

    engine_env(nav=False)
    conv = "conv-1a-loan"
    history: list[dict] = []
    turn_calls = []
    replies = []
    for message in (
        "I need an emergency loan of 5000 dinars",
        "The reason is a medical bill",
        "Please go ahead",
    ):
        result, calls = _chat(message, conv=conv, decide=_loan_decide, history=history)
        assert result.get("state_saved") is True
        turn_calls.append(calls)
        replies.append(result.get("content") or "")
        history += [{"role": "user", "content": message},
                    {"role": "assistant", "content": replies[-1]}]

    state = _stored_state(conv)
    # PV2-3B: a complete loan brief hands off — slots persist as principal
    # (catalog) plus amount (C8 / StateBlock alias). Chat never stages.
    assert state.slots.get("loan_type") == "emergency"
    assert float(state.slots.get("principal") or state.slots.get("amount") or 0) == 5000
    assert float(state.slots.get("amount") or 0) == 5000
    assert state.intent.get("api") == "submit_my_loan"
    assert state.intent["since_turn"] == 1

    assert "5000" in replies[0] or "5,000" in replies[0]
    assert "approval" not in replies[0].lower()
    for reply in replies:
        assert not reasks_slot(reply, "amount")
        assert "approval" not in reply.lower()
    # The detector bites on the no-state reply (negative control).
    assert reasks_slot("How much would you like to borrow?", "amount")


@pytest.mark.django_db(transaction=True)
def test_state_of_another_user_is_not_loaded_into_the_prompt(django_store, engine_env):
    engine_env(nav=False)
    conv = "conv-1a-owner"
    result, _ = _chat("I need an emergency loan of 5000 dinars", conv=conv,
                      decide=_loan_decide, host_user_id="7001")
    assert result.get("state_saved") is True

    result, calls = _chat("Please go ahead", conv=conv, decide=_loan_decide,
                          host_user_id="7002")
    assert not any(_STATE_HEADER in _system_text(kw) for kw in calls)
    assert result.get("state_saved") is False
    assert "How much" in (result.get("content") or "")
    assert _stored_state(conv).decisions[-1]["turn"] == 1


# ── 5. Absorbed items ────────────────────────────────────────────────────


def test_retrieval_witness_passes_host_user_id_to_memory_manager():
    from ai.engine.cognition.turn.retrieve import RetrievalWitness

    seen: dict = {}

    class _Memory:
        async def retrieve_relevant_context(self, *args, **kwargs):
            seen.update(kwargs)
            return types.SimpleNamespace(to_prompt_text=lambda: "No memories available.")

    witness = RetrievalWitness(memory_manager=_Memory())
    async_to_sync(witness.retrieve)("nibras", "conv-x", "hello", host_user_id="7001")
    assert seen.get("host_user_id") == "7001"


@pytest.mark.django_db(transaction=True)
def test_keyword_fact_scan_is_bounded_to_most_recent_rows(django_store, monkeypatch):
    from django.utils import timezone

    from ai.engine.core.database import get_session_factory
    from ai.engine.memory import long_term
    from ai.models import MemoryLongTerm

    assert long_term.KEYWORD_SCAN_LIMIT == 500
    now = timezone.now()
    for i, content in enumerate([
        "oldest cost centre CC-01", "cost centre CC-02", "cost centre CC-03",
    ]):
        row = MemoryLongTerm.objects.create(
            id=f"pv2-1a-fact-{i}", instance_id="nibras", category="observation",
            content=content, source="test", confidence=1.0,
            host_user_id="7001", visibility="private",
        )
        MemoryLongTerm.objects.filter(pk=row.pk).update(
            created_at=now - timedelta(days=10 - i),
        )

    async def _scan():
        async with get_session_factory("nibras")() as db:
            facts = await long_term.LongTermMemory(db)._keyword_match_facts(
                "nibras", "which cost centre?", limit=5, host_user_id="7001",
            )
            return {f["content"] for f in facts}

    assert "oldest cost centre CC-01" in async_to_sync(_scan)()
    monkeypatch.setattr(long_term, "KEYWORD_SCAN_LIMIT", 2)
    bounded = async_to_sync(_scan)()
    assert bounded == {"cost centre CC-02", "cost centre CC-03"}
