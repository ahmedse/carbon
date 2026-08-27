"""Sprint 15 — context engineering + enterprise governance tests.

Covers:
  * tiered/budgeted context assembly (``assemble_context``)
  * ``context_snapshot_json`` telemetry persistence after ``send_message``
  * deterministic conversation summarization
  * JSON + Markdown export
  * per-turn usage attribution persistence + serialization
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from accounts.models import User
from core.models import Module
from dataschema.models import DataTable, DataField
from ai.context_assembler import _estimate_tokens, assemble_context
from ai.intelligence import CarbonIntelligence, _serialize_message
from ai.models import (
    AIConversation,
    AIMessage,
    KnowledgeEdge,
    KnowledgeNode,
    MemoryLongTerm,
)
from dq.models import DQRule
from mdm.models import OrgUnit
from ai.protocol import ChatResponse, Scope


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="context-worker", password="secret123")


@pytest.fixture(autouse=True)
def _clear_carbon_kg(db):
    """Hide committed schema-graph rows leaked by other modules.

    ``ai/tests/test_kg_cluster_migration.py`` writes ``KnowledgeNode`` rows
    through the engine Store on a *separate, committed* connection, so those
    rows survive pytest-django's per-test rollback and linger in the reused
    test DB.  T3 reads ``instance_id='carbon'`` ENTITY nodes, which would make
    empty-state assertions (and exact history-count assertions) order-dependent.
    Deleting inside the test transaction hides those committed rows for this
    test's duration without affecting the shared DB.
    """
    KnowledgeNode.objects.filter(instance_id="carbon").delete()
    KnowledgeEdge.objects.filter(instance_id="carbon").delete()
    yield


def _make_conversation(user, conversation_type="chat", summary=""):
    return AIConversation.objects.create(
        user=user,
        title=conversation_type,
        conversation_type=conversation_type,
        task_payload_json={},
        scope_json={},
        summary=summary,
    )


def _history_dicts(conversation):
    return list(
        conversation.messages.order_by("created_at").values(
            "role", "content", "created_at",
        )
    )


# ── 1. assemble_context tiering + summary ────────────────────────────────


@pytest.mark.django_db
def test_assemble_context_caps_history_and_prepends_summary(user):
    conversation = _make_conversation(user, "chat", summary="Earlier context summary")
    messages = []
    for i in range(20):
        messages.append(
            AIMessage.objects.create(
                conversation=conversation,
                role="user" if i % 2 == 0 else "assistant",
                content=f"message {i}",
            )
        )

    # Pin strictly increasing timestamps so tiering is deterministic.
    base = timezone.now()
    for i, m in enumerate(messages):
        AIMessage.objects.filter(pk=m.pk).update(
            created_at=base + timedelta(seconds=i)
        )

    result = assemble_context(conversation, _history_dicts(conversation), scope=None, recent_turns=8)

    # Summary adds exactly one leading system message; history is capped at 8.
    assert len(result["messages"]) == 1 + 8
    assert result["messages"][0]["role"] == "system"
    assert "Earlier context summary" in result["messages"][0]["content"]

    # Verbatim history is the most recent 8 turns (oldest 12 dropped).
    verbatim = [m for m in result["messages"] if m["role"] != "system"]
    assert len(verbatim) == 8
    assert verbatim[0]["content"] == "message 12"
    assert verbatim[-1]["content"] == "message 19"


@pytest.mark.django_db
def test_assemble_context_budget_keys_non_negative(user):
    conversation = _make_conversation(user, "chat", summary="summary")
    AIMessage.objects.create(
        conversation=conversation, role="user", content="hello world"
    )

    result = assemble_context(
        conversation,
        _history_dicts(conversation),
        scope=None,
        recent_turns=8,
        summary_budget=1500,
        retrieval_budget=2000,
        memory_budget=1000,
    )

    budget = result["budget"]
    assert set(budget.keys()) == {
        "T2_history", "T2b_summary", "T3_retrieval", "T4_memory",
    }
    for value in budget.values():
        assert value >= 0
    # T3 reports *actual* tokens injected (0 when no KG nodes exist).
    assert budget["T3_retrieval"] == 0
    # T4 reports *actual* tokens consumed (0 when scope=None disables memory).
    assert budget["T4_memory"] == 0


# ── 1b. T3 knowledge-graph retrieval ─────────────────────────────────────


@pytest.mark.django_db
def test_assemble_context_t3_injects_schema_graph(user):
    entity = KnowledgeNode.objects.create(
        instance_id="carbon",
        node_type="ENTITY",
        name="monthly_electricity",
        description="Monthly electricity usage",
    )
    attr_month = KnowledgeNode.objects.create(
        instance_id="carbon", node_type="ATTRIBUTE", name="monthly_electricity.month",
    )
    attr_total = KnowledgeNode.objects.create(
        instance_id="carbon", node_type="ATTRIBUTE", name="monthly_electricity.total_kwh",
    )
    KnowledgeEdge.objects.create(
        instance_id="carbon", relationship="HAS_ATTRIBUTE",
        source_node_id=entity.id, target_node_id=attr_month.id,
    )
    KnowledgeEdge.objects.create(
        instance_id="carbon", relationship="HAS_ATTRIBUTE",
        source_node_id=entity.id, target_node_id=attr_total.id,
    )

    conversation = _make_conversation(user)
    AIMessage.objects.create(conversation=conversation, role="user", content="hello")

    result = assemble_context(conversation, _history_dicts(conversation), scope=None, recent_turns=8)

    kg_msgs = [
        m for m in result["messages"]
        if m["role"] == "system" and "[Knowledge Graph]" in m["content"]
    ]
    assert len(kg_msgs) == 1
    content = kg_msgs[0]["content"]
    assert "monthly_electricity" in content
    assert "month, total_kwh" in content
    assert "monthly_electricity." not in content


@pytest.mark.django_db
def test_assemble_context_t3_is_instance_scoped_not_user_partitioned(user):
    # Bootstrap writes nodes with AppScopeMixin defaults: visibility="private",
    # org_unit_id=None, host_user_id=None. T3 must NOT partition on those.
    KnowledgeNode.objects.create(
        instance_id="carbon",
        node_type="ENTITY",
        name="emission_factors",
        visibility="private",
        org_unit_id=None,
        host_user_id=None,
    )

    conversation = _make_conversation(user)
    AIMessage.objects.create(conversation=conversation, role="user", content="hello")

    result = assemble_context(conversation, _history_dicts(conversation), scope=None, recent_turns=8)

    kg_msgs = [
        m for m in result["messages"]
        if m["role"] == "system" and "[Knowledge Graph]" in m["content"]
    ]
    assert len(kg_msgs) == 1
    assert "emission_factors" in kg_msgs[0]["content"]


@pytest.mark.django_db
def test_assemble_context_t3_truncates_at_budget(user):
    entity = KnowledgeNode.objects.create(
        instance_id="carbon", node_type="ENTITY", name="table_a",
    )
    for col in ["col_one", "col_two"]:
        attr = KnowledgeNode.objects.create(
            instance_id="carbon", node_type="ATTRIBUTE", name=f"table_a.{col}",
        )
        KnowledgeEdge.objects.create(
            instance_id="carbon", relationship="HAS_ATTRIBUTE",
            source_node_id=entity.id, target_node_id=attr.id,
        )

    conversation = _make_conversation(user)
    AIMessage.objects.create(conversation=conversation, role="user", content="hello")

    base_tokens = _estimate_tokens("table_a") + _estimate_tokens("(ENTITY)")
    budget = base_tokens + _estimate_tokens("col_one")

    result = assemble_context(
        conversation, _history_dicts(conversation), scope=None,
        recent_turns=8, retrieval_budget=budget,
    )

    kg_msgs = [
        m for m in result["messages"]
        if m["role"] == "system" and "[Knowledge Graph]" in m["content"]
    ]
    assert len(kg_msgs) == 1
    content = kg_msgs[0]["content"]
    assert "table_a" in content
    assert "col_one" in content
    assert "col_two" not in content


@pytest.mark.django_db
def test_assemble_context_t3_drops_over_budget_entity(user):
    KnowledgeNode.objects.create(
        instance_id="carbon",
        node_type="ENTITY",
        name="a" * 4000,
    )

    conversation = _make_conversation(user)
    AIMessage.objects.create(conversation=conversation, role="user", content="hello")

    result = assemble_context(
        conversation, _history_dicts(conversation), scope=None,
        recent_turns=8, retrieval_budget=100,
    )

    assert result["budget"]["T3_retrieval"] == 0
    assert all("[Knowledge Graph]" not in m["content"] for m in result["messages"])


@pytest.mark.django_db
def test_assemble_context_t3_empty_when_no_nodes(user):
    conversation = _make_conversation(user)
    AIMessage.objects.create(conversation=conversation, role="user", content="hello")

    result = assemble_context(conversation, _history_dicts(conversation), scope=None, recent_turns=8)

    assert result["budget"]["T3_retrieval"] == 0
    assert all("[Knowledge Graph]" not in m["content"] for m in result["messages"])


@pytest.mark.django_db
def test_assemble_context_t4_scopes_memory_by_user(user):
    scope = Scope(user_identifier=str(user.pk), is_superuser=False, org_unit_ids=["*"])

    MemoryLongTerm.objects.create(
        instance_id="carbon", category="pref", content="owner prefers CSV exports",
        confidence=1.0, host_user_id=str(user.pk), visibility="private",
    )
    MemoryLongTerm.objects.create(
        instance_id="carbon", category="org", content="shared org fact",
        confidence=0.9, visibility="shared",
    )
    MemoryLongTerm.objects.create(
        instance_id="carbon", category="pref", content="other user private fact",
        confidence=1.0, host_user_id="99999", visibility="private",
    )
    MemoryLongTerm.objects.create(
        instance_id="carbon", category="pref", content="archived fact",
        confidence=1.0, host_user_id=str(user.pk), visibility="private", archived=True,
    )

    conversation = _make_conversation(user)
    AIMessage.objects.create(conversation=conversation, role="user", content="hello")

    result = assemble_context(
        conversation, _history_dicts(conversation), scope=scope, recent_turns=8,
    )

    memory_msgs = [
        m for m in result["messages"]
        if m["role"] == "system" and "[Long-Term Memory]" in m["content"]
    ]
    assert len(memory_msgs) == 1
    content = memory_msgs[0]["content"]
    assert "owner prefers CSV exports" in content
    assert "shared org fact" in content
    assert "other user private fact" not in content
    assert "archived fact" not in content


@pytest.mark.django_db
def test_assemble_context_t4_truncates_at_budget(user):
    scope = Scope(user_identifier=str(user.pk), is_superuser=False, org_unit_ids=["*"])

    MemoryLongTerm.objects.create(
        instance_id="carbon", category="a", content="small fact one",
        confidence=1.0, visibility="shared",
    )
    MemoryLongTerm.objects.create(
        instance_id="carbon", category="b", content="small fact two",
        confidence=0.5, visibility="shared",
    )

    conversation = _make_conversation(user)
    AIMessage.objects.create(conversation=conversation, role="user", content="hello")

    # Budget exactly the first fact's token cost — the second must be dropped.
    budget = _estimate_tokens("a") + _estimate_tokens("small fact one")
    result = assemble_context(
        conversation, _history_dicts(conversation), scope=scope,
        recent_turns=8, memory_budget=budget,
    )

    assert result["budget"]["T4_memory"] == budget
    memory_msgs = [
        m for m in result["messages"]
        if m["role"] == "system" and "[Long-Term Memory]" in m["content"]
    ]
    assert len(memory_msgs) == 1
    assert "small fact one" in memory_msgs[0]["content"]
    assert "small fact two" not in memory_msgs[0]["content"]


@pytest.mark.django_db
def test_assemble_context_t4_drops_over_budget_fact(user):
    scope = Scope(user_identifier=str(user.pk), is_superuser=False, org_unit_ids=["*"])

    MemoryLongTerm.objects.create(
        instance_id="carbon", category="big", content="x" * 4000,
        confidence=1.0, visibility="shared",
    )

    conversation = _make_conversation(user)
    AIMessage.objects.create(conversation=conversation, role="user", content="hello")

    result = assemble_context(
        conversation, _history_dicts(conversation), scope=scope,
        recent_turns=8, memory_budget=100,
    )

    assert result["budget"]["T4_memory"] == 0
    assert all(
        "[Long-Term Memory]" not in m["content"]
        for m in result["messages"]
    )


@pytest.mark.django_db
def test_assemble_context_no_summary_is_history_only(user):
    conversation = _make_conversation(user, "chat", summary="")
    for i in range(5):
        AIMessage.objects.create(
            conversation=conversation, role="user", content=f"m{i}"
        )

    result = assemble_context(
        conversation, _history_dicts(conversation), scope=None, recent_turns=8,
    )

    assert len(result["messages"]) == 5
    assert all(m["role"] != "system" for m in result["messages"])


@pytest.mark.django_db
def test_assemble_context_resolves_workspace_mentions(user):
    org_unit = OrgUnit.objects.create(name="Mentions Org", code="MNT", org_type="division")
    module = Module.objects.create(name="Mentions Module", org_unit=org_unit)
    table = DataTable.objects.create(name="mentions_table", title="Mentions Table", module=module)
    field = DataField.objects.create(
        data_table=table,
        name="amount",
        label="Amount",
        type="number",
    )
    rule = DQRule.objects.create(
        name="Mentions Rule",
        rule_level="field_validation",
        rule_type="not_null",
        severity="error",
        is_active=True,
    )
    conversation = AIConversation.objects.create(
        user=user,
        title="chat",
        conversation_type="chat",
        task_payload_json={
            "workspace_context": {
                "workspace": "dq",
                "current_view": "rule_detail",
                "mentions": [
                    {"kind": "table", "id": str(table.id)},
                    {"kind": "rule", "id": str(rule.id)},
                    {"kind": "field", "id": str(field.id)},
                    {"kind": "module", "id": str(module.id)},
                ],
            }
        },
        scope_json={},
    )

    result = assemble_context(conversation, _history_dicts(conversation), scope=None)

    first_message = result["messages"][0]["content"]
    assert "User is in the dq workspace" in first_message
    assert table.name in first_message
    assert rule.name in first_message
    assert field.label in first_message
    assert module.name in first_message


# ── 2. context_snapshot_json persisted after send_message ────────────────


@pytest.mark.django_db
def test_context_snapshot_json_set_after_send_message(user):
    ci = CarbonIntelligence()

    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.chat.return_value = ChatResponse(status="completed", content="ok")
    ci._provider = provider

    conversation = ci.create_conversation(user, "chat")
    conversation_id = conversation["id"]

    scope = Scope(
        user_identifier=str(user.pk),
        is_superuser=True,
        org_unit_ids=["*"],
    )
    with patch("ai.intelligence.build_scope", return_value=scope):
        ci.send_message(user, conversation_id, "hello world")

    conv = AIConversation.objects.get(id=conversation_id)
    snapshot = conv.context_snapshot_json
    assert snapshot
    assert "T2_history" in snapshot
    assert snapshot["T2_history"] >= 0


@pytest.mark.django_db
def test_context_snapshot_json_persists_kg_entities_after_send_message(user):
    # Seed a schema KG entity + attribute (exactly what T3 reads). The autouse
    # ``_clear_carbon_kg`` fixture hides committed leaks; these in-test rows
    # are visible to ``assemble_context`` inside the same transaction.
    entity = KnowledgeNode.objects.create(
        instance_id="carbon",
        node_type="ENTITY",
        name="monthly_electricity",
        description="Monthly electricity usage",
    )
    attr = KnowledgeNode.objects.create(
        instance_id="carbon", node_type="ATTRIBUTE", name="monthly_electricity.total_kwh",
    )
    KnowledgeEdge.objects.create(
        instance_id="carbon", relationship="HAS_ATTRIBUTE",
        source_node_id=entity.id, target_node_id=attr.id,
    )

    ci = CarbonIntelligence()
    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.chat.return_value = ChatResponse(status="completed", content="ok")
    ci._provider = provider

    conversation = ci.create_conversation(user, "chat")
    conversation_id = conversation["id"]

    scope = Scope(
        user_identifier=str(user.pk),
        is_superuser=True,
        org_unit_ids=["*"],
    )
    with patch("ai.intelligence.build_scope", return_value=scope):
        ci.send_message(user, conversation_id, "hello world")

    conv = AIConversation.objects.get(id=conversation_id)
    snapshot = conv.context_snapshot_json
    assert snapshot
    # The flat merge keeps budget tiers top-level AND carries the KG entries.
    assert "T3_retrieval" in snapshot
    assert snapshot["T3_retrieval"] > 0
    assert "kg_entities" in snapshot
    names = {e["name"] for e in snapshot["kg_entities"]}
    assert "monthly_electricity" in names
    entry = next(e for e in snapshot["kg_entities"] if e["name"] == "monthly_electricity")
    assert entry["node_type"] == "ENTITY"
    assert "total_kwh" in entry["attributes"]


@pytest.mark.django_db
def test_assistant_message_freezes_per_turn_context_snapshot(user):
    # Seed a schema KG entity + attribute (exactly what T3 reads). The autouse
    # ``_clear_carbon_kg`` fixture hides committed leaks; these in-test rows
    # are visible to ``assemble_context`` inside the same transaction.
    entity = KnowledgeNode.objects.create(
        instance_id="carbon",
        node_type="ENTITY",
        name="monthly_electricity",
        description="Monthly electricity usage",
    )
    attr = KnowledgeNode.objects.create(
        instance_id="carbon", node_type="ATTRIBUTE", name="monthly_electricity.total_kwh",
    )
    KnowledgeEdge.objects.create(
        instance_id="carbon", relationship="HAS_ATTRIBUTE",
        source_node_id=entity.id, target_node_id=attr.id,
    )

    ci = CarbonIntelligence()
    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.chat.return_value = ChatResponse(status="completed", content="ok")
    ci._provider = provider

    conversation = ci.create_conversation(user, "chat")
    conversation_id = conversation["id"]

    scope = Scope(
        user_identifier=str(user.pk),
        is_superuser=True,
        org_unit_ids=["*"],
    )
    with patch("ai.intelligence.build_scope", return_value=scope):
        ci.send_message(user, conversation_id, "hello world")

    conv = AIConversation.objects.get(id=conversation_id)
    assistant = AIMessage.objects.filter(conversation=conv, role="assistant").first()
    assert assistant is not None
    # The per-turn snapshot (budget + KG entities) is frozen onto the message
    # metadata so provenance stays correct after later turns overwrite the
    # conversation-level snapshot.
    frozen = assistant.metadata_json.get("context_snapshot")
    assert frozen
    assert frozen["T3_retrieval"] > 0
    names = {e["name"] for e in frozen.get("kg_entities", [])}
    assert "monthly_electricity" in names
    entry = next(e for e in frozen["kg_entities"] if e["name"] == "monthly_electricity")
    assert "total_kwh" in entry["attributes"]


# ── 3. summarize_conversation deterministic ──────────────────────────────


@pytest.mark.django_db
def test_summarize_conversation_deterministic(user):
    conversation = _make_conversation(user, "chat", summary="")
    AIMessage.objects.create(conversation=conversation, role="user", content="First question about DQ rules")
    AIMessage.objects.create(conversation=conversation, role="user", content="Second question about emissions")
    AIMessage.objects.create(conversation=conversation, role="user", content="Third question about catalogs")

    ci = CarbonIntelligence()
    result = ci.summarize_conversation(user, str(conversation.id))

    conversation.refresh_from_db()
    assert result["summary"]
    assert conversation.summary == result["summary"]
    assert "First question" in conversation.summary

    # force=True regenerates — still deterministic, no LLM call.
    result_again = ci.summarize_conversation(user, str(conversation.id), force=True)
    assert result_again["summary"] == result["summary"]


@pytest.mark.django_db
def test_summarize_conversation_skips_when_present(user):
    conversation = _make_conversation(user, "chat", summary="")
    message = AIMessage.objects.create(conversation=conversation, role="user", content="hello")

    ci = CarbonIntelligence()
    result = ci.summarize_conversation(user, str(conversation.id))

    with patch("ai.intelligence._build_deterministic_summary", side_effect=AssertionError("summary recomputed unexpectedly")):
        result_again = ci.summarize_conversation(user, str(conversation.id))

    conversation.refresh_from_db()
    assert result_again["summary"] == result["summary"]
    assert conversation.summary == result["summary"]
    assert conversation.last_summarized_message_id == message.id


# ── 4. export ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_export_json_returns_conversation_and_messages(user):
    conversation = _make_conversation(user, "chat", summary="")
    AIMessage.objects.create(conversation=conversation, role="user", content="hello")
    AIMessage.objects.create(conversation=conversation, role="assistant", content="hi there")

    ci = CarbonIntelligence()
    result = ci.export_conversation(user, str(conversation.id), fmt="json")

    assert result["format"] == "json"
    content = result["content"]
    assert content["conversation"]["id"] == str(conversation.id)
    assert len(content["messages"]) == 2


@pytest.mark.django_db
def test_export_markdown_contains_title_and_content(user):
    conversation = _make_conversation(user, "chat", summary="")
    conversation.title = "Exported Chat"
    conversation.save(update_fields=["title"])
    AIMessage.objects.create(
        conversation=conversation,
        role="user",
        content="Tell me about GHG scopes",
        metadata_json={"kind": "question"},
    )

    ci = CarbonIntelligence()
    result = ci.export_conversation(user, str(conversation.id), fmt="markdown")

    assert result["format"] == "markdown"
    md = result["content"]
    assert "# Exported Chat" in md
    assert "Tell me about GHG scopes" in md
    assert "**User**" in md
    assert "```json" in md


# ── 5. usage attribution ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_usage_kwarg_persists_and_serializes(user):
    conversation = _make_conversation(user, "chat", summary="")

    ci = CarbonIntelligence()
    usage = {
        "model": "deepseek-chat",
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "cost_usd": 0.0001,
        "latency_ms": 123,
    }
    serialized = ci._save_assistant_message(
        conversation,
        "answer",
        metadata={},
        status="completed",
        usage=usage,
    )

    assert serialized["token_usage_json"] == usage

    # Survives the DB round-trip via _serialize_message.
    persisted = AIMessage.objects.get(id=serialized["id"])
    assert _serialize_message(persisted)["token_usage_json"] == usage
