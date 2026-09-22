"""PV2-2C — role-scoped tool catalog + audience-aware persona + LLM accounting."""

from __future__ import annotations

import types
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import Group
from django.test import override_settings

from ai.engine.core.config import get_settings
from ai.engine.llm.call_meter import CallMeter, meter_scope, record_call, stage
from ai.store import reset_store


# ── Fixtures (shared patterns with test_pv2_instrumentation) ─────────────


def _fake_completion(content: str = "Stubbed reply."):
    async def _create(**kw):
        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(
                        content=content,
                        tool_calls=None,
                    ),
                    finish_reason="stop",
                )
            ],
            usage=types.SimpleNamespace(
                prompt_tokens=10,
                completion_tokens=4,
                total_tokens=14,
            ),
        )

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=_create)
        )
    )


@pytest.fixture
def django_store():
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


@pytest.fixture
def cfg():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def single_pass(monkeypatch):
    monkeypatch.setenv("AGENT_ORCHESTRATOR_ENABLED", "false")
    monkeypatch.setenv("KG_MULTI_STEP_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def stub_llm():
    with patch("ai.engine.llm.provider.get_llm_client") as mock:
        mock.return_value = _fake_completion()
        yield mock


@pytest.fixture
def no_nav_fast_path(monkeypatch):
    patched = get_settings().model_copy(
        update={"NAVIGATION_RESOLVER_ENABLED": False},
    )
    monkeypatch.setattr(
        "ai.engine.cognition.turn.runner.get_settings",
        lambda: patched,
    )


@pytest.fixture
def org_unit(db):
    from mdm.models import OrgUnit

    return OrgUnit.objects.create(name="PV2-2C Org", slug="pv2-2c-org")


def _make_employee_user(username: str, org, *, employee_no: str):
    from accounts.models import User
    from people.models import Employee

    user = User.objects.create_user(username=username, password="secret123")
    Employee.objects.create(
        org_unit=org,
        employee_no=employee_no,
        full_name=f"Emp {employee_no}",
        basic_salary=Decimal("1000.000"),
        join_date=date(2024, 1, 1),
        is_active=True,
        user=user,
    )
    return user


def _make_hr_user(username: str):
    from accounts.constants import PEOPLE_LEAD_GROUP
    from accounts.models import ScopedRole, User

    user = User.objects.create_user(username=username, password="secret123")
    group, _ = Group.objects.get_or_create(name=PEOPLE_LEAD_GROUP)
    user.groups.add(group)
    ScopedRole.objects.get_or_create(
        user=user, group=group, org_unit=None, module=None,
        defaults={"is_active": True},
    )
    return user


def _make_admin_user(username: str):
    from accounts.models import User

    return User.objects.create_superuser(
        username=username, email=f"{username}@test.local", password="secret123",
    )


def _catalog_names(catalog) -> set[str]:
    return {e.get("name") for e in (catalog or []) if e.get("name")}


# ── Obj 1–2: audience helper + catalog filter ────────────────────────────


@pytest.mark.django_db
def test_audience_for_user_employee_hr_admin_unknown(org_unit):
    from ai.identity_propagation import audience_for_user

    emp = _make_employee_user("pv2c_emp", org_unit, employee_no="9101")
    hr = _make_hr_user("pv2c_hr")
    admin = _make_admin_user("pv2c_admin")
    from accounts.models import User
    unknown = User.objects.create_user(username="pv2c_orphan", password="secret123")

    assert audience_for_user(emp) == {"ess"}
    assert "hr" in audience_for_user(hr)
    assert "admin" in audience_for_user(admin)
    assert audience_for_user(unknown) == {"ess"}
    assert audience_for_user(None) == {"ess"}


@pytest.mark.django_db
def test_user_info_carries_audience(org_unit):
    from ai.engine_runtime import _build_chat_user_info

    emp = _make_employee_user("pv2c_info_emp", org_unit, employee_no="9102")
    info = _build_chat_user_info(str(emp.pk))
    assert info is not None
    assert set(info["audience"]) == {"ess"}


def test_filter_catalog_defaults_and_my_routes():
    from ai.engine.cognition.context_pack import (
        entry_audience,
        filter_catalog_by_audience,
    )

    catalog = [
        {"name": "list_payslip_lines", "method": "GET"},  # default hr
        {"name": "list_employees", "method": "GET"},
        {"name": "list_my_payslips", "method": "GET"},  # default ess+hr
        {"name": "list_my_leave", "method": "GET"},
        {"name": "nav_people", "method": "GET", "audience": ["ess", "hr"]},
        {"name": "admin_only", "method": "GET", "audience": ["admin"]},
    ]
    assert set(entry_audience(catalog[0])) == {"hr"}
    assert set(entry_audience(catalog[2])) == {"ess", "hr"}

    ess = _catalog_names(filter_catalog_by_audience(catalog, {"ess"}))
    assert "list_my_payslips" in ess
    assert "list_my_leave" in ess
    assert "list_payslip_lines" not in ess
    assert "list_employees" not in ess
    assert "admin_only" not in ess

    hr = _catalog_names(filter_catalog_by_audience(catalog, {"hr"}))
    assert "list_payslip_lines" in hr
    assert "list_my_payslips" in hr

    admin = _catalog_names(filter_catalog_by_audience(catalog, {"admin", "hr", "ess"}))
    assert "list_payslip_lines" in admin and "list_my_payslips" in admin


@pytest.mark.django_db
def test_nibras_loader_validates_audience_enum():
    from ai.engine.core.archetypes import (
        load_instance_config,
        validate_catalog_audiences,
    )

    cfg = load_instance_config("nibras")
    errors = validate_catalog_audiences(cfg.get("api_catalog") or [])
    assert errors == [], errors


@pytest.mark.django_db(transaction=True)
def test_employee_chat_catalog_excludes_hr_endpoints(
    django_store, single_pass, stub_llm, cfg, no_nav_fast_path, org_unit, monkeypatch,
):
    """emp tool list has list_my_payslips, not list_payslip_lines / list_employees."""
    from ai.engine_runtime import dispatch_task

    emp = _make_employee_user("pv2c_chat_emp", org_unit, employee_no="9103")
    seen: dict = {}

    async def _capture_prompt(**kwargs):
        catalog = kwargs.get("api_catalog") or []
        seen["names"] = _catalog_names(catalog)
        persona = kwargs.get("persona") or ""
        if not isinstance(persona, str):
            persona = str(persona)
        seen["persona"] = persona
        # Also check instance_config composed persona path
        ic = kwargs.get("instance_config") or {}
        seen["ic_persona"] = ic.get("persona") or ""
        return "You are a test assistant."

    monkeypatch.setattr(
        "ai.engine.llm.prompts.build_chat_prompt",
        _capture_prompt,
    )

    data = dispatch_task(
        "chat",
        {
            "message": "What is my net pay?",
            "host_user_id": str(emp.pk),
            "conversation_history": {
                "conversation_id": f"conv-pv2c-{uuid.uuid4().hex[:8]}",
                "messages": [],
            },
        },
        instance_id="nibras",
    )
    assert data.get("status") == "completed", data
    names = seen.get("names") or set()
    assert "list_my_payslips" in names, names
    assert "list_payslip_lines" not in names, names
    assert "list_employees" not in names, names

    persona_blob = f"{seen.get('persona')}\n{seen.get('ic_persona')}"
    assert "list_my_payslips" in persona_blob or "own records" in persona_blob.lower()
    assert "list_payslip_lines" not in persona_blob
    assert "full read access" not in persona_blob.lower()


@pytest.mark.django_db(transaction=True)
def test_admin_chat_catalog_includes_hr_and_ess(
    django_store, single_pass, stub_llm, cfg, no_nav_fast_path, monkeypatch,
):
    from ai.engine_runtime import dispatch_task

    admin = _make_admin_user("pv2c_chat_admin")
    seen: dict = {}

    async def _capture_prompt(**kwargs):
        seen["names"] = _catalog_names(kwargs.get("api_catalog") or [])
        return "You are a test assistant."

    monkeypatch.setattr(
        "ai.engine.llm.prompts.build_chat_prompt",
        _capture_prompt,
    )

    data = dispatch_task(
        "chat",
        {
            "message": "Show payslip lines for the latest run",
            "host_user_id": str(admin.pk),
            "conversation_history": {
                "conversation_id": f"conv-pv2c-adm-{uuid.uuid4().hex[:8]}",
                "messages": [],
            },
        },
        instance_id="nibras",
    )
    assert data.get("status") == "completed", data
    names = seen.get("names") or set()
    assert "list_my_payslips" in names, names
    assert "list_payslip_lines" in names, names


# ── Obj 3: IdentityBlock audience guidance ───────────────────────────────


def test_identity_block_renders_ess_not_hr():
    from ai.engine.cognition.context_pack import IdentityBlock

    block = IdentityBlock(
        persona="Shared Nibras identity.",
        audience={"ess"},
        guidance={
            "ess": "ESS: use list_my_payslips; only your own records.",
            "hr": "HR: You have full read access using list_payslip_lines.",
            "admin": "ADMIN block.",
        },
    )
    text = block.render()
    assert "Shared Nibras identity." in text
    assert "list_my_payslips" in text
    assert "list_payslip_lines" not in text
    assert "full read access" not in text
    assert "ADMIN block." not in text


# ── Obj 4: 403 twin-retry ────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_403_retries_my_twin_once():
    from ai.engine.cognition.turn.execute import (
        find_my_api_twin,
        maybe_retry_my_twin_on_403,
        own_records_403_message,
    )

    catalog = [
        {"name": "list_payslip_lines", "method": "GET"},
        {"name": "list_my_payslips", "method": "GET"},
    ]
    assert find_my_api_twin("list_payslip_lines", catalog) == "list_my_payslips"
    assert find_my_api_twin("list_my_payslips", catalog) is None

    en = own_records_403_message("en", "list_payslip_lines")
    ar = own_records_403_message("ar", "list_payslip_lines")
    assert "own" in en.lower() or "payslip" in en.lower()
    assert "قسائم" in ar or "رات" in ar or "خاص" in ar

    calls: list[str] = []

    async def fake_invoke(api_name: str, **kwargs):
        calls.append(api_name)
        if api_name == "list_payslip_lines":
            return {"status_code": 403, "data": {"detail": "Forbidden"}}
        if api_name == "list_my_payslips":
            return {
                "status_code": 200,
                "data": {"results": [{"line_type": "net", "amount": "1200"}]},
            }
        return {"status_code": 404, "data": {"detail": "missing"}}

    first = {
        "tool_name": "call_host_api",
        "result": '{"status_code": 403, "data": {"detail": "Forbidden"}}',
        "error": "Forbidden",
        "latency_ms": 1.0,
        "guardrail_flags": [],
        "tool_args": {"api_name": "list_payslip_lines"},
    }
    result = async_to_sync(maybe_retry_my_twin_on_403)(
        first,
        args={"api_name": "list_payslip_lines"},
        invoke=fake_invoke,
        instance_config={"api_catalog": catalog},
        user_message="What is my net pay?",
    )
    assert calls == ["list_my_payslips"]
    assert result.get("error") is None
    assert "twin_retry" in (result.get("guardrail_flags") or [])
    assert result.get("tool_args", {}).get("api_name") == "list_my_payslips"


# ── Obj 5: deterministic foreground LLM accounting ───────────────────────


def test_finalize_meter_excludes_auto_memory_from_foreground():
    from ai.engine.cognition.turn.runner import _finalize_meter
    from ai.engine.cognition.turn.witnesses import TurnLedger

    with meter_scope() as meter:
        with stage("draft"):
            record_call(1.0, 1, 1, "m")
            record_call(1.0, 1, 1, "m")
        with stage("auto_memory"):
            record_call(1.0, 1, 1, "m")

    ledger = TurnLedger(conversation_id="c1")
    _finalize_meter(ledger, meter, "answer")
    assert ledger.llm_calls_measured == 2
    assert getattr(ledger, "llm_calls_background", None) == 1
    assert ledger.llm_calls_by_stage.get("auto_memory") == 1
    assert ledger.llm_calls_by_stage.get("draft") == 2


@pytest.mark.django_db(transaction=True)
def test_six_stubbed_turns_identical_llm_calls(
    django_store, single_pass, stub_llm, cfg, no_nav_fast_path,
):
    from ai.engine_runtime import dispatch_task

    counts = []
    for i in range(6):
        data = dispatch_task(
            "chat",
            {
                "message": "What is today's date?",
                "conversation_history": {
                    "conversation_id": f"conv-pv2c-meter-{i}",
                    "messages": [],
                },
            },
            instance_id="nibras",
        )
        assert data.get("status") == "completed", data
        result = data.get("result") or {}
        counts.append(int(result.get("llm_calls") or 0))
        assert "llm_calls_background" in result

    assert len(set(counts)) == 1, counts


# ── Obj 6: topic-guard refuse still saves ConversationState ──────────────


@pytest.mark.django_db(transaction=True)
def test_topic_guard_refuse_saves_conversation_state(django_store, cfg):
    from ai.engine.cognition.state_store import ConversationStateStore
    from ai.engine_runtime import dispatch_task
    from ai.store import get_store

    conv = f"conv-pv2c-guard-{uuid.uuid4().hex[:8]}"
    data = dispatch_task(
        "chat",
        {
            "message": "What is our carbon footprint and GWP?",
            "host_user_id": "7001",
            "conversation_history": {
                "conversation_id": conv,
                "messages": [],
            },
        },
        instance_id="nibras",
    )
    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert result.get("turn_decision") == "refuse" or result.get("intent_zone") == "off_limits"
    assert result.get("state_saved") is True

    from ai.models import ConversationContextRecord
    from ai.engine.cognition.state_store import ConversationState

    row = ConversationContextRecord.objects.get(conversation_id=conv)
    state = ConversationState.from_dict(row.session_json)
    assert state.decisions
    assert state.decisions[-1]["decision"] == "refuse"
