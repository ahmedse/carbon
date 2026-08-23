"""Sprint "fly to rule detail" — tool-action surfacing + confirm/decline API.

Covers:
  * deterministic action extraction from executed tools (``_extract_tool_actions``)
  * anti-fabrication grounded outcome note (``_grounded_outcome_note``)
  * Carbon instance config for the engine turn
  * confirm/decline tool-execution endpoints (ownership, status, persistence)
"""
from __future__ import annotations

import json

import pytest

from ai.engine_runtime import (
    _carbon_instance_config,
    _extract_tool_actions,
    _grounded_outcome_note,
)


# ── Unit: action extraction ─────────────────────────────────────────────


def test_extract_tool_actions_navigate():
    tools = [
        {
            "tool_name": "execute_navigate_to",
            "result": json.dumps({
                "action": "navigate",
                "route": "/dq/rules/abc-123",
                "label": "View rule",
                "summary": "Rule found.",
            }),
        },
    ]
    actions, pending = _extract_tool_actions(tools)
    assert len(actions) == 1
    assert actions[0]["type"] == "navigate"
    assert actions[0]["route"] == "/dq/rules/abc-123"
    assert pending == []


def test_extract_tool_actions_pending_confirmation():
    tools = [
        {
            "tool_name": "create_dq_rule",
            "result": json.dumps({
                "requires_confirmation": True,
                "execution_id": "ex-9",
                "proposed_rule": {"name": "employee-number", "type": "range"},
                "proposed_body": {
                    "name": "employee-number",
                    "rule_type": "range",
                    "rule_level": "field_validation",
                    "definition": {
                        "schema_version": 1,
                        "name": "employee-number",
                        "type": "range",
                        "params": {"min": 1000, "max": 9999},
                    },
                },
                "validation": {"passed": True},
            }),
        },
    ]
    actions, pending = _extract_tool_actions(tools)
    assert actions == []
    assert len(pending) == 1
    assert pending[0]["execution_id"] == "ex-9"
    assert pending[0]["tool"] == "create_dq_rule"
    assert pending[0]["proposed_rule"]["name"] == "employee-number"
    # The exact POST body travels with the proposal so the UI can render and
    # edit the JSON before confirming.
    assert pending[0]["proposed_body"]["rule_level"] == "field_validation"
    assert pending[0]["proposed_body"]["definition"]["params"] == {"min": 1000, "max": 9999}


def test_extract_tool_actions_dedupes_navigate_routes():
    tools = [
        {"tool_name": "t", "result": json.dumps(
            {"action": "navigate", "route": "/dq/rules/a", "label": "A"})},
        {"tool_name": "t", "result": json.dumps(
            {"action": "navigate", "route": "/dq/rules/a", "label": "A again"})},
        {"tool_name": "t", "result": json.dumps(
            {"action": "navigate", "route": "/dq/rules/b", "label": "B"})},
    ]
    actions, _ = _extract_tool_actions(tools)
    assert [a["route"] for a in actions] == ["/dq/rules/a", "/dq/rules/b"]


def test_extract_tool_actions_skips_errors_and_bad_json():
    tools = [
        {"tool_name": "t", "error": "boom", "result": None},
        {"tool_name": "t", "result": "not json {{{"},
        {"tool_name": "t", "result": json.dumps({"action": "navigate", "route": " "})},
    ]
    actions, pending = _extract_tool_actions(tools)
    assert actions == []
    assert pending == []


# ── Unit: grounded outcome note (anti-fabrication) ──────────────────────


def test_grounded_note_staged_not_created():
    tools = [
        {
            "tool_name": "create_dq_rule",
            "result": json.dumps({
                "requires_confirmation": True,
                "execution_id": "ex-9",
                "proposed_rule": {"name": "employee-number", "type": "range"},
            }),
        },
    ]
    note = _grounded_outcome_note(tools)
    assert "validated and staged" in note
    assert "nothing was created yet" in note
    assert "Confirm" in note


def test_grounded_note_error_is_outcome_oriented():
    # RULE_23 (QA F2): raw tool exception text must never reach the user; the
    # note reports the outcome, never the internal error. Covers both the
    # top-level ``error`` key (make_executor catch-all) and an error embedded
    # in the tool result JSON.
    tools = [
        {
            "tool_name": "create_dq_rule",
            "error": "'ToolExecution' object has no attribute 'refresh_from_db'",
        },
        {
            "tool_name": "search_knowledge",
            "result": json.dumps({"error": "internal traceback leaked"}),
        },
    ]
    note = _grounded_outcome_note(tools)
    assert "⚠️" in note
    assert "nothing was created or changed" in note
    assert "refresh_from_db" not in note
    assert "internal traceback" not in note


def test_grounded_note_navigate_summary():
    tools = [
        {"tool_name": "execute_navigate_to", "result": json.dumps(
            {"action": "navigate", "route": "/dq/rules/a", "summary": "Opened rule."})},
    ]
    note = _grounded_outcome_note(tools)
    assert "Opened rule." in note


def test_grounded_note_plan_created():
    # plan_task outcome (RULE_23 — product terms only: plan, steps,
    # pending_approval, Tasks panel; no engine class names).
    tools = [
        {"tool_name": "plan_task", "result": json.dumps({
            "action": "plan_created",
            "plan_id": "2dcf0692-dc0b-447d-be97-abe9258e56ce",
            "status": "pending_approval",
            "steps": [
                {"step_id": 1, "intent": "Audit emissions uploads"},
                {"step_id": 2, "intent": "Compare quarters"},
            ],
        })},
    ]
    note = _grounded_outcome_note(tools)
    assert "Plan 2dcf0692 drafted" in note
    assert "2 steps" in note
    assert "pending_approval" in note
    assert "Review and approve it in the Tasks panel" in note
    assert "• Audit emissions uploads" in note
    assert "SkillAwarePlanner" not in note
    assert "Run" not in note or "Run row" not in note


def test_grounded_note_empty():
    assert _grounded_outcome_note([]) == ""


# ── Unit: Carbon instance config ────────────────────────────────────────


@pytest.mark.django_db
def test_carbon_instance_config_includes_host_user_id(user):
    config = _carbon_instance_config(str(user.pk))
    assert config["host_user_id"] == str(user.pk)
    assert config["display_name"]
    assert any(r["name"] == "dq_rule_detail" for r in config["navigation_routes"])
    # The capability-scoped inventory is attached and never leaks for a
    # plain user (no scoped roles → empty capability list).
    assert config["user_access"]["capabilities"] == []


def test_carbon_instance_config_no_user():
    config = _carbon_instance_config(None)
    assert config["host_user_id"] is None
    # Anonymous users get an EMPTY inventory — nothing may be listed.
    assert config["user_access"]["apps"] == []
    assert config["user_access"]["capabilities"] == []
    assert config["user_access"]["routes"] == []


# ── Endpoint: confirm / decline tool executions ─────────────────────────


@pytest.fixture
def user(db):
    from accounts.models import User

    return User.objects.create_user(username="ai-worker", password="secret123")


@pytest.fixture
def conversation(db, user):
    from ai.models import AIConversation

    return AIConversation.objects.create(
        user=user,
        title="Rule chat",
        conversation_type="chat",
        app_identifier="carbon",
        task_payload_json={},
        scope_json={},
    )


def _stage_execution(conversation, user, *, body=None, status="pending_confirmation"):
    from ai.models import ToolExecution

    execution = ToolExecution.objects.create(
        conversation_id=str(conversation.id),
        tool_name="create_dq_rule",
        input_params=json.dumps({
            "method": "POST",
            "endpoint": "/carbon-api/dq/rules/",
            "params": None,
            "body": body or {
                "name": "employee-number",
                "rule_type": "range",
                "rule_level": "field_validation",
                "severity": "error",
                "dimension": "validity",
                "is_active": True,
                "definition": {
                    "schema_version": 1,
                    "name": "employee-number",
                    "level": "field",
                    "dimension": "validity",
                    "type": "range",
                    "severity": "error",
                    "active": True,
                    "params": {"min": 1000, "max": 9999},
                },
            },
        }),
        status=status,
        confirmed_by_user=False,
        host_user_id=str(user.pk),
    )
    return execution


def _confirm_url(conversation):
    from django.urls import reverse

    return reverse(
        "ai-workspace-conversation-confirm-tool-execution",
        kwargs={"pk": conversation.id},
    )


def _decline_url(conversation):
    from django.urls import reverse

    return reverse(
        "ai-workspace-conversation-decline-tool-execution",
        kwargs={"pk": conversation.id},
    )


@pytest.mark.django_db
def test_confirm_creates_rule_and_appends_grounded_message(user, conversation):
    from rest_framework.test import APIClient

    from ai.models import AIMessage
    from dq.models import DQRule

    execution = _stage_execution(conversation, user)

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        _confirm_url(conversation),
        {"execution_id": execution.id},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["status"] == "confirmed"
    assert response.data["rule_id"]
    assert response.data["action"]["type"] == "navigate"
    assert response.data["action"]["route"] == f"/dq/rules/{response.data['rule_id']}"

    # The rule really exists.
    rule = DQRule.objects.get(pk=response.data["rule_id"])
    assert rule.name == "employee-number"
    assert rule.rule_type == "range"

    # The staged execution transitioned.
    execution.refresh_from_db()
    assert execution.status == "confirmed"
    assert execution.confirmed_by_user is True

    # A grounded assistant message with the navigate action was appended.
    messages = AIMessage.objects.filter(conversation=conversation, role="assistant")
    assert messages.exists()
    last = messages.order_by("-created_at").first()
    assert "created" in (last.content or "").lower()
    assert last.metadata_json["action"]["route"] == f"/dq/rules/{rule.pk}"


@pytest.mark.django_db
def test_decline_marks_execution_declined_and_appends_message(user, conversation):
    from rest_framework.test import APIClient

    from ai.models import AIMessage

    execution = _stage_execution(conversation, user)

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        _decline_url(conversation),
        {"execution_id": execution.id},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["status"] == "declined"

    execution.refresh_from_db()
    assert execution.status == "declined"

    messages = AIMessage.objects.filter(conversation=conversation, role="assistant")
    assert messages.exists()
    assert "nothing was created" in messages.order_by("-created_at").first().content


@pytest.mark.django_db
def test_ai_message_persists_full_actions_list(user, conversation):
    """Capability listings surface several links at once: the message metadata
    must keep the FULL ``actions`` list (plus the legacy single ``action``
    field = last action) so the UI can render one small button per item."""
    from ai.intelligence import CarbonIntelligence
    from ai.models import AIMessage

    actions = [
        {"type": "navigate", "route": "/dq", "label": "Data Quality",
         "summary": "Inspect and manage data quality rules."},
        {"type": "navigate", "route": "/catalog", "label": "Data Catalog & Governance",
         "summary": "Discover data products."},
    ]

    intelligence = CarbonIntelligence()
    intelligence._build_ai_message(
        conversation,
        "completed",
        "Here is what you can use:",
        follow_up_questions=[],
        actions=actions,
    )

    message = AIMessage.objects.filter(conversation=conversation, role="assistant").get()
    metadata = message.metadata_json
    assert metadata["action"]["route"] == "/catalog"          # backward-compat = last
    assert len(metadata["actions"]) == 2                       # full list for the UI
    assert metadata["actions"][0]["route"] == "/dq"
    assert metadata["actions"][1]["route"] == "/catalog"


@pytest.mark.django_db
def test_confirm_with_modified_body_creates_edited_rule(user, conversation):
    """Modify-then-confirm: an optional ``body`` on the confirm call replaces
    the staged POST body, so the user's JSON edits are what actually get
    created — atomically, in one call."""
    from rest_framework.test import APIClient

    from ai.models import ToolExecution
    from dq.models import DQRule

    execution = _stage_execution(conversation, user)
    original = json.loads(execution.input_params)["body"]

    modified = {
        **original,
        "name": "employee-number-edited",
        "severity": "warn",
        "definition": {
            **original["definition"],
            "name": "employee-number-edited",
            # definition is the source of truth for denormalized columns on
            # create (DQRule.save()), so a user edit must land here.
            "severity": "warn",
            "params": {"min": 1000, "max": 50000},
        },
    }

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        _confirm_url(conversation),
        {"execution_id": execution.id, "body": modified},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["rule_name"] == "employee-number-edited"

    rule = DQRule.objects.get(pk=response.data["rule_id"])
    assert rule.name == "employee-number-edited"
    assert rule.severity == "warn"

    # The staged envelope now carries the edited body (what was actually sent).
    execution.refresh_from_db()
    sent_body = json.loads(execution.input_params)["body"]
    assert sent_body["name"] == "employee-number-edited"
    assert sent_body["definition"]["params"] == {"min": 1000, "max": 50000}
    assert execution.status == "confirmed"


@pytest.mark.django_db
def test_confirm_rejects_non_object_modified_body(user, conversation):
    from rest_framework.test import APIClient

    execution = _stage_execution(conversation, user)

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        _confirm_url(conversation),
        {"execution_id": execution.id, "body": "not-an-object"},
        format="json",
    )

    assert response.status_code == 400
    assert "JSON object" in response.data["error"]

    # Nothing was created and the staged row is untouched.
    execution.refresh_from_db()
    assert execution.status == "pending_confirmation"


@pytest.mark.django_db
def test_confirm_rejects_other_users_execution(user, conversation):
    from accounts.models import User
    from rest_framework.test import APIClient

    other = User.objects.create_user(username="other-user", password="secret123")
    execution = _stage_execution(conversation, other)

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        _confirm_url(conversation),
        {"execution_id": execution.id},
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_confirm_rejects_non_pending_execution(user, conversation):
    from rest_framework.test import APIClient

    execution = _stage_execution(conversation, user, status="confirmed")

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        _confirm_url(conversation),
        {"execution_id": execution.id},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_confirm_404_when_execution_not_in_conversation(user, conversation):
    from ai.models import AIConversation
    from rest_framework.test import APIClient

    other_conv = AIConversation.objects.create(
        user=user,
        title="Other",
        conversation_type="chat",
        app_identifier="carbon",
        task_payload_json={},
        scope_json={},
    )
    execution = _stage_execution(other_conv, user)

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        _confirm_url(conversation),
        {"execution_id": execution.id},
        format="json",
    )

    assert response.status_code == 404


# ── Regression (QA F1/F3): runtime path through the DjangoStore ─────────


@pytest.mark.django_db
def test_create_pending_execution_stages_via_django_store(user, conversation):
    """QA F1 regression: the real runtime path — ``create_dq_rule`` plugin →
    ``CarbonHostExecutor.create_pending_execution`` → DjangoStore session —
    must stage a ``pending_confirmation`` row without crashing.

    The sprint tests staged ``ToolExecution`` rows directly on the Django
    mirror (``_stage_execution`` above), so ``_DjangoSession.refresh()`` — the
    only Store method that never resolved engine → Django mirror — was never
    exercised.  This test drives the exact runtime call chain and fails with
    ``AttributeError: 'ToolExecution' object has no attribute
    'refresh_from_db'`` before the fix.
    """
    import asyncio

    from django.test import override_settings

    from ai.engine.core.database import get_session_factory
    from ai.host_executor import CarbonHostExecutor
    from ai.models import ToolExecution as DjangoToolExecution
    from ai.store import reset_store

    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()

        async def _stage() -> str:
            factory = get_session_factory("carbon")
            async with factory() as db:
                executor = CarbonHostExecutor(
                    db=db,
                    instance_config={},
                    user_token="inproc:carbon:1",
                    host_user_id=str(user.pk),
                )
                execution = await executor.create_pending_execution(
                    conversation_id=str(conversation.id),
                    tool_name="create_dq_rule",
                    method="POST",
                    endpoint="/carbon-api/dq/rules/",
                    body={
                        "name": "employee-number",
                        "rule_type": "range",
                        "rule_level": "field_validation",
                        "definition": {
                            "schema_version": 1,
                            "type": "range",
                            "params": {"min": 1000, "max": 9999},
                        },
                    },
                )
                return execution.id

        execution_id = asyncio.run(_stage())

        reset_store()

    row = DjangoToolExecution.objects.get(pk=execution_id)
    assert row.status == "pending_confirmation"
    assert row.tool_name == "create_dq_rule"
    assert row.host_user_id == str(user.pk)
    # The engine contract stores ``input_params`` as a JSON string (parsed by
    # ``confirm_execution`` via ``json.loads``).
    input_params = json.loads(row.input_params)
    assert input_params["method"] == "POST"
    assert input_params["endpoint"] == "/carbon-api/dq/rules/"

    # Store writes commit on their own connection; remove the staged row so
    # the --reuse-db test database stays clean across runs.
    DjangoToolExecution.objects.filter(pk=execution_id).delete()


# ── Regression (QA water-consumption plan): catalog + in-process transport ─

# QA found the multi-agent "water consumption table + DQ rules" plan stuck:
# ``call_host_api`` returned "Unknown API endpoint" because the Carbon
# ``api_catalog`` was hardcoded empty and the in-process executor only
# dispatched POST ``carbon-api/dq/rules``.  These tests pin the fix:
# the catalog must resolve every endpoint the plan uses, and the executor must
# serve them in-process for both GET and POST.


def test_carbon_instance_config_catalog_resolves_plan_endpoints():
    """RULE_11 regression: the plan's ``call_host_api`` endpoints must resolve."""
    config = _carbon_instance_config(None)
    catalog = {e["name"]: e for e in config["api_catalog"]}
    assert "create_table" in catalog
    assert catalog["create_table"]["method"] == "POST"
    assert catalog["create_table"]["requires_confirmation"] is True
    assert "bind_dq_rules" in catalog
    assert catalog["bind_dq_rules"]["method"] == "POST"
    assert catalog["bind_dq_rules"]["requires_confirmation"] is True
    # "reuse or create" rules needs discovery — otherwise the LLM duplicates.
    assert "list_dq_rules" in catalog
    assert catalog["list_dq_rules"]["method"] == "GET"
    assert "create_dq_rule" in catalog
    assert catalog["create_dq_rule"]["method"] == "POST"
    assert catalog["create_dq_rule"]["requires_confirmation"] is True
    # Data-product discovery used by the plan's earlier steps.
    assert "get_data_product_details" in catalog
    assert catalog["get_data_product_details"]["method"] == "GET"


@pytest.mark.django_db(transaction=True)
def test_in_process_create_table_and_bind_via_confirm(conversation):
    """Full consent-gate path for the plan's mutation steps:
    ``create_pending_execution`` → ``confirm_execution`` → in-process handler
    → real Django rows (DataTable + RuleFieldAssignment), no HTTP loopback.

    Uses ``transaction=True`` because the DjangoStore's ``sync_to_async`` runs
    on a worker thread whose connection cannot see pytest's uncommitted
    transaction-wrapped rows (the user/module/rule must be committed).
    """
    import asyncio

    from django.test import override_settings

    from accounts.models import User
    from ai.engine.core.database import get_session_factory
    from ai.host_executor import CarbonHostExecutor
    from ai.models import ToolExecution as DjangoToolExecution
    from ai.store import reset_store
    from core.models import Module
    from dataschema.models import DataTable, DataField
    from dq.models import DQRule, RuleFieldAssignment

    actor = User.objects.create_user(username="qa-actor-1", password="secret123")
    module = Module.objects.create(name="QA Water Module")
    rule = DQRule.objects.create(
        name="qa-water-range",
        rule_type="range",
        rule_level="field_validation",
        severity="error",
        dimension="validity",
        definition={
            "schema_version": 1,
            "name": "qa-water-range",
            "type": "range",
            "level": "field",
            "dimension": "validity",
            "severity": "error",
            "active": True,
            "params": {"min": 0, "max": 10000},
        },
    )
    table_id = None
    try:
        with override_settings(AI_STORE_BACKEND="django"):
            reset_store()

            async def _drive() -> tuple:
                factory = get_session_factory("carbon")
                async with factory() as db:
                    executor = CarbonHostExecutor(
                        db=db,
                        instance_config={},
                        user_token="inproc:carbon:1",
                        host_user_id=str(actor.pk),
                    )
                    # Step: create_table
                    create_exec = await executor.create_pending_execution(
                        conversation_id=str(conversation.id),
                        tool_name="call_host_api:create_table",
                        method="POST",
                        endpoint="/carbon-api/dataschema/tables/",
                        body={
                            "title": "Water Consumption QA",
                            "description": "QA regression table",
                            "module": module.pk,
                            "fields": [
                                {
                                    "name": "consumption_m3",
                                    "label": "Consumption (m3)",
                                    "type": "number",
                                    "required": True,
                                },
                            ],
                        },
                    )
                    create_result = await executor.confirm_execution(create_exec.id)
                    # Step: bind_dq_rules
                    bind_exec = await executor.create_pending_execution(
                        conversation_id=str(conversation.id),
                        tool_name="call_host_api:bind_dq_rules",
                        method="POST",
                        endpoint="/carbon-api/dq/rule-assignments/",
                        body={
                            "table_id": create_result["data"]["id"],
                            "dq_rule_ids": [rule.pk],
                        },
                    )
                    bind_result = await executor.confirm_execution(bind_exec.id)
                    return create_result, bind_result

            create_result, bind_result = asyncio.run(_drive())
            reset_store()

        assert create_result["status_code"] == 201
        table_id = create_result["data"]["id"]
        table = DataTable.objects.get(pk=table_id)
        assert table.module_id == module.pk
        assert table.fields.filter(name="consumption_m3").exists()

        assert bind_result["status_code"] == 201
        assert bind_result["data"]["count"] == 1
        assert RuleFieldAssignment.objects.filter(
            rule=rule, data_table_id=table_id, data_field__isnull=True
        ).exists()
    finally:
        DjangoToolExecution.objects.filter(conversation_id=str(conversation.id)).delete()
        if table_id:
            DataField.objects.filter(data_table_id=table_id).delete()
            DataTable.objects.filter(pk=table_id).delete()
        RuleFieldAssignment.objects.filter(rule=rule).delete()
        rule.delete()
        module.delete()
        actor.delete()


@pytest.mark.django_db(transaction=True)
def test_in_process_get_tables_and_rules_list():
    """GET endpoints dispatch in-process too (catalog ``list_data_tables`` /
    ``list_dq_rules`` / ``get_data_product_details``) — the old code was
    POST-only and read steps failed with ToolExecutionError."""
    import asyncio

    from django.test import override_settings

    from accounts.models import User
    from ai.engine.core.database import get_session_factory
    from ai.host_executor import CarbonHostExecutor
    from ai.store import reset_store
    from core.models import Module
    from dataschema.models import DataTable

    actor = User.objects.create_user(username="qa-actor-2", password="secret123")
    actor.is_superuser = True
    actor.save()
    module = Module.objects.create(name="QA Water Module GET")
    table = DataTable.objects.create(
        title="Water Consumption QA GET", module=module, created_by=actor
    )
    try:
        with override_settings(AI_STORE_BACKEND="django"):
            reset_store()

            async def _drive() -> tuple:
                factory = get_session_factory("carbon")
                async with factory() as db:
                    executor = CarbonHostExecutor(
                        db=db,
                        instance_config={},
                        user_token="inproc:carbon:1",
                        host_user_id=str(actor.pk),
                    )
                    tables = await executor.call_api_direct(
                        "GET", "/carbon-api/dataschema/tables/", {}, {}
                    )
                    # get_data_product_details — query string on the path
                    by_module = await executor.call_api_direct(
                        "GET",
                        f"/carbon-api/dataschema/tables/?module_id={module.pk}",
                        {},
                        {},
                    )
                    rules = await executor.call_api_direct(
                        "GET", "/carbon-api/dq/rules/", {}, {}
                    )
                    return tables, by_module, rules

            tables, by_module, rules = asyncio.run(_drive())
            reset_store()

        assert tables["status_code"] == 200
        titles = [t["title"] for t in tables["data"]["results"]]
        assert "Water Consumption QA GET" in titles
        assert by_module["status_code"] == 200
        assert all(
            t["module"] == module.pk for t in by_module["data"]["results"]
        )
        assert rules["status_code"] == 200
        assert isinstance(rules["data"]["results"], list)
    finally:
        DataTable.objects.filter(pk=table.pk).delete()
        module.delete()
        actor.delete()


@pytest.mark.django_db
def test_in_process_unknown_endpoint_fails_honestly(user, conversation):
    """Uncatalogued endpoint → ToolExecutionError, execution marked ``failed``
    (a step fails honestly instead of looping on ``unstaged`` confirms)."""
    import asyncio

    from django.test import override_settings

    from ai.engine.core.database import get_session_factory
    from ai.engine.core.exceptions import ToolExecutionError
    from ai.host_executor import CarbonHostExecutor
    from ai.models import ToolExecution as DjangoToolExecution
    from ai.store import reset_store

    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()

        async def _drive() -> str:
            factory = get_session_factory("carbon")
            async with factory() as db:
                executor = CarbonHostExecutor(
                    db=db,
                    instance_config={},
                    user_token="inproc:carbon:1",
                    host_user_id=str(user.pk),
                )
                execution = await executor.create_pending_execution(
                    conversation_id=str(conversation.id),
                    tool_name="call_host_api:unknown",
                    method="POST",
                    endpoint="/carbon-api/unknown/",
                    body={},
                )
                try:
                    await executor.confirm_execution(execution.id)
                except ToolExecutionError as exc:
                    return f"{execution.id}:{exc}"
                return f"{execution.id}:NO_ERROR"

        outcome = asyncio.run(_drive())
        reset_store()

    execution_id, error = outcome.split(":", 1)
    assert "NO_ERROR" not in error
    assert "not available" in error
    row = DjangoToolExecution.objects.get(pk=execution_id)
    assert row.status == "failed"
    DjangoToolExecution.objects.filter(pk=execution_id).delete()
