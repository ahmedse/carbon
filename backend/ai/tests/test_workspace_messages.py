from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from accounts.models import User
from ai.intelligence import CarbonIntelligence
from ai.models import AIConversation, KnowledgeEdge, KnowledgeNode
from backend.ai.protocol import (
    AnomalyDetectResponse,
    ChatResponse,
    DetectedAnomaly,
    DqSuggestResponse,
    DqSuggestion,
    NlQueryResponse,
    Scope,
)
from core.models import Module
from dataschema.models import DataField, DataTable
from dq.models import FieldProfile, TableProfile
from mdm.models import OrgUnit


@pytest.fixture
def user(db):
    return User.objects.create_user(username="ai-worker", password="secret123")


@pytest.fixture
def table_graph(db, user):
    org = OrgUnit.objects.create(name="AI Org", slug="ai-org")
    module = Module.objects.create(name="AI Module", scope=1, org_unit=org)
    table = DataTable.objects.create(
        title="AI Table",
        name="ai_table",
        module=module,
        created_by=user,
        updated_by=user,
    )
    field = DataField.objects.create(
        data_table=table,
        name="email",
        label="Email",
        type="string",
        created_by=user,
        updated_by=user,
    )
    return {
        "org": org,
        "module": module,
        "table": table,
        "field": field,
    }


def _scope_for(user, module_id: int, *, app_identifier: str | None = None) -> Scope:
    return Scope(
        user_identifier=str(user.pk),
        org_unit_ids=["1"],
        module_ids=[str(module_id)],
        app_identifier=app_identifier,
    )


def _conversation(user, conversation_type: str, payload: dict, *, app_identifier: str | None = None):
    return AIConversation.objects.create(
        user=user,
        title=conversation_type,
        conversation_type=conversation_type,
        app_identifier=app_identifier,
        task_payload_json=payload,
        scope_json={},
    )


@pytest.mark.django_db
def test_dq_suggest_conversation_routes_to_provider(user, table_graph):
    conversation = _conversation(
        user,
        "dq_suggest",
        {
            "table_id": table_graph["table"].id,
            "module_id": table_graph["module"].id,
            "table_name": table_graph["table"].name,
        },
    )
    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.suggest_dq.return_value = DqSuggestResponse(
        status="completed",
        suggestions=[
            DqSuggestion(
                definition={"name": "Check completeness", "type": "nl_check"},
                rationale="High completeness suggests a not-null rule.",
                severity="warn",
                confidence=0.91,
                dimension="completeness",
            )
        ],
    )

    ci = CarbonIntelligence()
    ci._provider = provider

    with patch("ai.intelligence.build_scope", return_value=_scope_for(user, table_graph["module"].id)), \
         patch("dq.services.build_suggest_payload", return_value=({
             "name": table_graph["table"].name,
             "description": table_graph["table"].title,
             "row_count": 24,
             "fields": [{"name": "email", "type": "string", "completeness_pct": 98.0}],
         }, None)):
        result = ci.send_message(user, str(conversation.id), "Suggest DQ rules")

    provider.suggest_dq.assert_called_once()
    assert result["assistant_message"]["metadata_json"]["type"] == "dq_suggestions"
    assert result["conversation"]["status"] == "needs_input"


@pytest.mark.django_db
def test_nl_query_conversation_routes_to_provider(user, table_graph):
    conversation = _conversation(
        user,
        "nl_query",
        {
            "module_id": table_graph["module"].id,
            "table_name": table_graph["table"].name,
            "columns": [{"name": "email"}, {"name": "amount"}],
        },
    )
    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.query_nl.return_value = NlQueryResponse(
        status="completed",
        sql="SELECT email FROM ai_table",
        rows=[{"email": "a@example.com"}],
        row_count=1,
    )

    ci = CarbonIntelligence()
    ci._provider = provider

    with patch("ai.intelligence.build_scope", return_value=_scope_for(user, table_graph["module"].id)):
        result = ci.send_message(user, str(conversation.id), "Show emails")

    provider.query_nl.assert_called_once()
    assert result["assistant_message"]["metadata_json"]["type"] == "nl_query_result"
    assert result["assistant_message"]["metadata_json"]["sql"] == "SELECT email FROM ai_table"


@pytest.mark.django_db
def test_anomaly_conversation_routes_to_provider(user, table_graph):
    conversation = _conversation(
        user,
        "anomaly",
        {
            "table_id": table_graph["table"].id,
            "module_id": table_graph["module"].id,
            "table_name": table_graph["table"].name,
        },
        app_identifier="emissions",
    )
    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.detect_anomalies.return_value = AnomalyDetectResponse(
        status="completed",
        anomalies=[
            DetectedAnomaly(
                metric="row_count",
                expected_range={"low": 90.0, "high": 110.0},
                observed=150.0,
                z_score=3.8,
                severity="error",
                explanation="Row volume jumped.",
            )
        ],
        history_snapshots=6,
    )

    ci = CarbonIntelligence()
    ci._provider = provider

    with patch("ai.intelligence.build_scope", return_value=_scope_for(user, table_graph["module"].id, app_identifier="emissions")), \
         patch("dq.services.build_anomaly_payload", return_value=({
             "table": {"name": table_graph["table"].name},
             "history": [{"row_count": 100}, {"row_count": 150}],
             "sensitivity": 2.0,
             "volume_anomaly_pct": 30.0,
         }, None)):
        result = ci.send_message(user, str(conversation.id), "Analyze anomalies")

    provider.detect_anomalies.assert_called_once()
    assert result["assistant_message"]["metadata_json"]["type"] == "anomalies"
    assert result["conversation"]["status"] == "needs_input"


@pytest.mark.django_db
def test_provider_unavailable_marks_conversation_failed(user, table_graph):
    conversation = _conversation(
        user,
        "nl_query",
        {"module_id": table_graph["module"].id, "table_name": table_graph["table"].name},
    )
    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.query_nl.return_value = NlQueryResponse(
        status="provider_unavailable",
        error={"code": "timeout", "message": "Timed out"},
    )

    ci = CarbonIntelligence()
    ci._provider = provider

    with patch("ai.intelligence.build_scope", return_value=_scope_for(user, table_graph["module"].id)):
        result = ci.send_message(user, str(conversation.id), "Show data")

    conversation.refresh_from_db()
    assert conversation.status == "failed"
    assert "unavailable" in result["assistant_message"]["content"].lower()


@pytest.mark.django_db
def test_empty_table_profile_returns_useful_error(user, table_graph):
    conversation = _conversation(
        user,
        "dq_suggest",
        {"table_id": table_graph["table"].id, "module_id": table_graph["module"].id},
    )
    provider = MagicMock()
    provider.provider_name = "dummy"

    ci = CarbonIntelligence()
    ci._provider = provider

    with patch("ai.intelligence.build_scope", return_value=_scope_for(user, table_graph["module"].id)), \
         patch("dq.services.build_suggest_payload", return_value=(None, {"message": "Could not profile table"})):
        result = ci.send_message(user, str(conversation.id), "Suggest rules")

    assert result["conversation"]["status"] == "failed"
    assert "Could not profile table" in result["assistant_message"]["content"]
    provider.suggest_dq.assert_not_called()


@pytest.mark.django_db
def test_conversation_context_carries_full_history_each_turn(user, table_graph):
    # T3 now reads instance-scoped schema-graph ENTITY nodes.  Other modules
    # (test_kg_cluster_migration) commit such rows on a separate connection, so
    # clear them inside this transaction to keep the exact history-count
    # assertion deterministic.
    KnowledgeNode.objects.filter(instance_id="carbon").delete()
    KnowledgeEdge.objects.filter(instance_id="carbon").delete()

    conversation = _conversation(
        user,
        "nl_query",
        {"module_id": table_graph["module"].id, "table_name": table_graph["table"].name},
    )
    provider = MagicMock()
    provider.provider_name = "dummy"
    seen_lengths: list[int] = []

    def _query_side_effect(request):
        seen_lengths.append(len(request.conversation.messages))
        return NlQueryResponse(status="completed", sql="SELECT 1", rows=[{"value": 1}], row_count=1)

    provider.query_nl.side_effect = _query_side_effect
    ci = CarbonIntelligence()
    ci._provider = provider

    with patch("ai.intelligence.build_scope", return_value=_scope_for(user, table_graph["module"].id)):
        ci.send_message(user, str(conversation.id), "First query")
        ci.send_message(user, str(conversation.id), "Second query")

    assert seen_lengths == [1, 3]


@pytest.mark.django_db
def test_guard_chain_rejects_calls_without_scope(user, table_graph):
    conversation = _conversation(
        user,
        "nl_query",
        {"module_id": table_graph["module"].id, "table_name": table_graph["table"].name},
    )
    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.query_nl.return_value = NlQueryResponse(status="completed", sql="SELECT 1", rows=[], row_count=0)
    ci = CarbonIntelligence()
    ci._provider = provider

    with patch("ai.intelligence.build_scope", return_value=Scope()):
        with pytest.raises(ValueError, match="ScopeGuard"):
            ci.send_message(user, str(conversation.id), "Show data")

    provider.query_nl.assert_not_called()


@pytest.mark.django_db
def test_needs_input_set_when_suggestions_returned(user, table_graph):
    conversation = _conversation(
        user,
        "dq_suggest",
        {
            "table_id": table_graph["table"].id,
            "module_id": table_graph["module"].id,
            "table_name": table_graph["table"].name,
        },
    )
    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.suggest_dq.return_value = DqSuggestResponse(
        status="completed",
        suggestions=[
            DqSuggestion(
                definition={"name": "Check uniqueness", "type": "unique"},
                rationale="Distinct count is low.",
                severity="warn",
                confidence=0.8,
                dimension="uniqueness",
            )
        ],
    )

    ci = CarbonIntelligence()
    ci._provider = provider

    with patch("ai.intelligence.build_scope", return_value=_scope_for(user, table_graph["module"].id)), \
         patch("dq.services.build_suggest_payload", return_value=({
             "name": table_graph["table"].name,
             "description": table_graph["table"].title,
             "row_count": 24,
             "fields": [{"name": "email", "type": "string"}],
         }, None)):
        ci.send_message(user, str(conversation.id), "Suggest rules")

    conversation.refresh_from_db()
    assert conversation.status == "needs_input"


@pytest.mark.django_db
def test_anomaly_request_uses_profile_history(user, table_graph):
    conversation = _conversation(
        user,
        "anomaly",
        {
            "table_id": table_graph["table"].id,
            "module_id": table_graph["module"].id,
            "table_name": table_graph["table"].name,
        },
        app_identifier="emissions",
    )
    provider = MagicMock()
    provider.provider_name = "dummy"
    captured_history = []

    def _detect_side_effect(request):
        captured_history.append(request.profile_history)
        return AnomalyDetectResponse(status="completed", anomalies=[], history_snapshots=len(request.profile_history))

    provider.detect_anomalies.side_effect = _detect_side_effect
    ci = CarbonIntelligence()
    ci._provider = provider

    with patch("ai.intelligence.build_scope", return_value=_scope_for(user, table_graph["module"].id, app_identifier="emissions")), \
         patch("dq.services.build_anomaly_payload", return_value=({
             "table": {"name": table_graph["table"].name},
             "history": [{"row_count": 100}, {"row_count": 98}, {"row_count": 150}],
             "sensitivity": 2.0,
             "volume_anomaly_pct": 30.0,
         }, None)):
        ci.send_message(user, str(conversation.id), "Analyze anomalies")

    assert len(captured_history[0]) == 3