"""Host API catalog coercion + get_entity_details alias (SIM-20260919-N10).

Agent Plan·Run historically bound catalog names like ``get_my_leave_balance``
to ``get_entity_details``, which only searches the knowledge store and soft-
misses with ``Entity '…' not found``. Chat uses ``call_host_api``. These
tests lock the systemic rewrite + runtime alias.
"""
from __future__ import annotations

import pytest


def test_decompose_prompt_lists_host_api_catalog():
    from ai.engine.cognition.plan.planner import _DECOMPOSE_AGENT_PROMPT

    assert "{host_api_list}" in _DECOMPOSE_AGENT_PROMPT
    assert "call_host_api" in _DECOMPOSE_AGENT_PROMPT
    assert "NEVER put a catalog name in" in _DECOMPOSE_AGENT_PROMPT


def test_decompose_template_is_empty_until_a_pack_is_bound():
    """The live plan create does not sit inside a chat turn.

    ``LV`` resolves to an empty string when no pack is bound. Formatting
    that empty template drops the JSON schema, and the model answers in
    prose. File 205750's failing calls sent ~484 input tokens. A bound
    call of the same template sends ~3,200.
    """
    from ai.engine.pack_vocab import _active_pack

    token = _active_pack.set("")
    try:
        from ai.engine.cognition.plan.planner import _DECOMPOSE_AGENT_PROMPT

        assert str(_DECOMPOSE_AGENT_PROMPT) == ""
    finally:
        _active_pack.reset(token)


@pytest.mark.asyncio
async def test_llm_decompose_binds_the_instance_pack_before_the_model_call(monkeypatch):
    from ai.engine.cognition.plan.planner import SkillAwarePlanner
    from ai.engine.pack_vocab import _active_pack

    seen: dict[str, str] = {}

    async def fake_route(**kwargs):
        seen["system"] = kwargs["messages"][0]["content"]
        return {"content": '{"pattern":"custom","steps":[]}'}

    monkeypatch.setattr("ai.engine.llm.router.route_chat", fake_route)
    token = _active_pack.set("")
    try:
        planner = SkillAwarePlanner(llm_client=object(), model="deepseek-flash")
        await planner._llm_decompose(
            "Read the profile, then stop.",
            object(),
            "deepseek-flash",
            instance_id="nibras",
            skills=[],
            user_id="13",
        )
    finally:
        _active_pack.reset(token)
    assert "Return ONLY valid" in seen["system"]
    assert "User task:" in seen["system"]


def test_decompose_prompt_task_and_schema_survive_clip_on_a_large_catalog():
    """Wave 2 (R3, part 2): a catalog-heavy instance (nibras, 48 host APIs)
    pushes the filled decompose prompt past ``TASK_BLOCK_MAX_CHARS``.

    ``_clip`` truncates the *tail*. If the JSON-output schema or the literal
    ``User task:`` line sit at the tail, the model never sees them and
    answers in prose instead of JSON (reproduced live: 3/3 refusals with
    the tail cut, 3/3 correct JSON plans with the same prompt unclipped).
    The template must put schema + task early enough to survive the clip
    regardless of how large a brand's host API catalog grows.
    """
    from ai.engine.cognition.context_pack import TASK_BLOCK_MAX_CHARS, _clip
    from ai.engine.cognition.plan.planner import _DECOMPOSE_AGENT_PROMPT

    # Reproduce nibras-scale catalog pressure without depending on any
    # specific brand's instance.yaml (domain-free — synthetic names only).
    host_api_list = "\n".join(
        f"- synthetic_host_api_{i:02d} (GET) "
        f"params={{\"dimension\":\"nationality\",\"period_end\":\"2026-08-31\","
        f"\"status\":\"committed\",\"page_size\":50,\"ordering\":\"-created_at\"}}"
        for i in range(48)
    )
    tools_list = "\n".join(f"- synthetic_tool_{i}" for i in range(26))
    task = "Read my profile then my leave balance. Do not write."

    prompt = _DECOMPOSE_AGENT_PROMPT.format(
        tools_list=tools_list,
        host_api_list=host_api_list,
        skills_list="- (none registered — do NOT use invoke_skill)",
        task=task,
    )
    assert len(prompt) > TASK_BLOCK_MAX_CHARS, (
        "fixture no longer reproduces the over-budget prompt; adjust the "
        "synthetic catalog size"
    )
    clipped = _clip(prompt, TASK_BLOCK_MAX_CHARS)
    assert f"User task: {task}" in clipped
    assert "Return ONLY valid" in clipped


def test_coerce_get_entity_details_leave_balance_to_call_host_api():
    from ai.engine.cognition.plan.planner import PlanStep, _coerce_host_api_steps

    catalog = {"get_my_leave_balance", "create_leave_record", "list_my_leave"}
    step = PlanStep(
        step_id=0,
        intent="Retrieve leave balance",
        tool_name="get_entity_details",
        tool_args={"entity_name": "get_my_leave_balance"},
    )
    _coerce_host_api_steps([step], catalog)
    assert step.tool_name == "call_host_api"
    assert step.tool_args.get("api_name") == "get_my_leave_balance"
    assert "entity_name" not in step.tool_args


def test_coerce_create_leave_record_to_submit_my_leave():
    from ai.engine.cognition.plan.planner import PlanStep, _coerce_host_api_steps

    catalog = {"get_my_leave_balance", "create_leave_record", "submit_my_leave", "list_my_leave"}
    step = PlanStep(
        step_id=4,
        intent="Create a one-day emergency leave record",
        tool_name="call_host_api",
        tool_args={
            "api_name": "create_leave_record",
            "body": {
                "employee": 1067,
                "leave_type": "emergency",
                "start_date": "2026-09-22",
                "end_date": "2026-09-22",
                "days": 1,
            },
        },
        is_mutation=True,
    )
    _coerce_host_api_steps([step], catalog, utterance="Plan leave.request.lifecycle for myself")
    assert step.tool_args.get("api_name") == "submit_my_leave"
    assert "employee" not in (step.tool_args.get("body") or {})


def test_coerce_loan_brief_rewrites_submit_my_leave():
    from ai.engine.cognition.plan.planner import PlanStep, _coerce_host_api_steps

    catalog = {
        "submit_my_leave",
        "submit_my_loan",
        "list_my_loans",
        "create_leave_record",
    }
    step = PlanStep(
        step_id=0,
        intent="Submit a loan request",
        tool_name="call_host_api",
        tool_args={"api_name": "submit_my_leave"},
        is_mutation=True,
    )
    _coerce_host_api_steps(
        [step],
        catalog,
        utterance="Plan Nibras process loan.request.lifecycle for myself",
    )
    assert step.tool_args.get("api_name") == "submit_my_loan"


def test_coerce_onboarding_brief_rewrites_submit_my_leave():
    from ai.engine.cognition.plan.planner import PlanStep, _coerce_host_api_steps

    catalog = {"submit_my_leave", "create_employee", "list_employees", "update_employee"}
    step = PlanStep(
        step_id=1,
        intent="Submit onboarding",
        tool_name="call_host_api",
        tool_args={"api_name": "submit_my_leave"},
        is_mutation=True,
    )
    _coerce_host_api_steps(
        [step],
        catalog,
        utterance="Plan employee.onboarding.lifecycle for a new hire",
    )
    assert step.tool_args.get("api_name") == "create_employee"


def test_coerce_leave_brief_keeps_submit_my_leave():
    from ai.engine.cognition.plan.planner import PlanStep, _coerce_host_api_steps

    catalog = {"submit_my_leave", "submit_my_loan", "create_employee"}
    step = PlanStep(
        step_id=0,
        intent="Submit leave",
        tool_name="call_host_api",
        tool_args={"api_name": "submit_my_leave"},
        is_mutation=True,
    )
    _coerce_host_api_steps(
        [step],
        catalog,
        utterance="Execute leave.request.lifecycle Prefer submit_my_leave",
    )
    assert step.tool_args.get("api_name") == "submit_my_leave"


def test_coerce_create_attendance_to_submit_my():
    from ai.engine.cognition.plan.planner import PlanStep, _coerce_host_api_steps

    catalog = {
        "create_attendance_permission",
        "submit_my_attendance_permission",
        "approve_attendance_permission",
        "submit_my_leave",
    }
    step = PlanStep(
        step_id=0,
        intent="Submit attendance",
        tool_name="call_host_api",
        tool_args={
            "api_name": "create_attendance_permission",
            "body": {
                "employee": 1,
                "date": "2026-10-01",
                "permission_type": "personal",
                "hours": "2",
            },
        },
        is_mutation=True,
    )
    _coerce_host_api_steps(
        [step],
        catalog,
        utterance="Execute attendance.permission.lifecycle Prefer submit_my_attendance_permission",
    )
    assert step.tool_args.get("api_name") == "submit_my_attendance_permission"
    assert "employee" not in (step.tool_args.get("body") or {})

def test_coerce_tool_name_that_is_catalog_api():
    from ai.engine.cognition.plan.planner import PlanStep, _coerce_host_api_steps

    catalog = {"get_my_leave_balance"}
    step = PlanStep(
        step_id=1,
        intent="Get balance",
        tool_name="get_my_leave_balance",
        tool_args={},
    )
    _coerce_host_api_steps([step], catalog)
    assert step.tool_name == "call_host_api"
    assert step.tool_args == {"api_name": "get_my_leave_balance"}


def test_coerce_leaves_real_knowledge_entity_alone():
    from ai.engine.cognition.plan.planner import PlanStep, _coerce_host_api_steps

    catalog = {"get_my_leave_balance"}
    step = PlanStep(
        step_id=2,
        intent="Schema for employees table",
        tool_name="get_entity_details",
        tool_args={"entity_name": "employees"},
    )
    _coerce_host_api_steps([step], catalog)
    assert step.tool_name == "get_entity_details"
    assert step.tool_args == {"entity_name": "employees"}


@pytest.mark.asyncio
async def test_get_entity_details_aliases_catalog_name_to_call_host_api(monkeypatch):
    from ai.engine.agent import tools as tools_mod

    seen = {}

    async def _fake_call_host_api(**kwargs):
        seen.update(kwargs)
        return {"status_code": 200, "data": [{"leave_type": "annual", "remaining": "16.00"}]}

    monkeypatch.setattr(tools_mod, "execute_call_host_api", _fake_call_host_api)

    class _Exec:
        instance_config = {
            "api_catalog": [
                {"name": "get_my_leave_balance", "method": "GET", "path": "/x/"},
            ]
        }

    result = await tools_mod.execute_get_entity_details(
        entity_name="get_my_leave_balance",
        knowledge_store=None,
        instance_id="nibras",
        executor=_Exec(),
    )
    assert result["status_code"] == 200
    assert seen.get("api_name") == "get_my_leave_balance"
    assert seen.get("executor") is not None


@pytest.mark.asyncio
async def test_get_entity_details_still_misses_unknown_knowledge_name():
    from ai.engine.agent.tools import execute_get_entity_details

    class _KS:
        async def get_entity(self, instance_id, name):
            return None

    result = await execute_get_entity_details(
        entity_name="totally_unknown_kg_thing",
        knowledge_store=_KS(),
        instance_id="nibras",
        executor=type("E", (), {"instance_config": {"api_catalog": []}})(),
    )
    assert result["entity"] is None
    assert "not found" in result["message"]


# ── Unbound host writes never reach Approve (prod 2026-09-24) ─────────────────
# Board-pack brief: "If over band, escalate to Finance and do not export."
# The decomposer emitted call_host_api(action="escalate_to_finance"); Approve
# refused it with "'escalate_to_finance' is not a host API in the catalog".
# The step must be decided at plan save, not at consent.


def _payroll_catalog() -> set[str]:
    return {
        "list_payroll_runs", "get_payroll_run", "list_payslip_lines",
        "compute_payroll_run", "validate_payroll_run", "commit_payroll_run",
        "list_loans", "generate_gosi_wps_sif",
    }


def test_unbound_escalate_to_finance_degrades_to_reasoning():
    from ai.engine.cognition.plan.planner import PlanStep, _unbind_unknown_host_api_steps

    step = PlanStep(
        step_id=7,
        intent="[OVER-BAND PATH] Escalate variance to Finance and do not export",
        tool_name="call_host_api",
        tool_args={"api_name": "call_host_api", "action": "escalate_to_finance", "payroll_run_id": "run-1"},
        is_mutation=True,
    )
    unbound = _unbind_unknown_host_api_steps([step], _payroll_catalog())

    assert unbound == [7]
    assert step.tool_name is None
    assert step.tool_args == {}
    assert step.is_mutation is False


def test_secondary_key_holding_catalog_name_is_promoted_to_api_name():
    from ai.engine.cognition.plan.planner import PlanStep, _unbind_unknown_host_api_steps

    step = PlanStep(
        step_id=2,
        intent="Run the October payroll variance check",
        tool_name="call_host_api",
        tool_args={"api_name": "call_host_api", "action": "validate_payroll_run", "body": {"run": 12}},
        is_mutation=True,
    )
    unbound = _unbind_unknown_host_api_steps([step], _payroll_catalog())

    assert unbound == []
    assert step.tool_name == "call_host_api"
    assert step.tool_args["api_name"] == "validate_payroll_run"
    assert step.tool_args["body"] == {"run": 12}
    assert step.is_mutation is True


def test_bound_host_step_and_non_host_tools_are_untouched():
    from ai.engine.cognition.plan.planner import PlanStep, _unbind_unknown_host_api_steps

    bound = PlanStep(step_id=0, intent="List runs", tool_name="call_host_api",
                     tool_args={"api_name": "list_payroll_runs"})
    export = PlanStep(step_id=1, intent="Export board pack", tool_name="export_document",
                      tool_args={"format": "pack"}, is_mutation=True)
    reasoning = PlanStep(step_id=2, intent="Analyze variance", tool_name=None, tool_args={})

    assert _unbind_unknown_host_api_steps([bound, export, reasoning], _payroll_catalog()) == []
    assert bound.tool_args == {"api_name": "list_payroll_runs"}
    assert export.tool_name == "export_document" and export.is_mutation is True
    assert reasoning.tool_name is None


def test_unknown_catalog_is_a_noop():
    """No instance config → we cannot judge; never strip blindly."""
    from ai.engine.cognition.plan.planner import PlanStep, _unbind_unknown_host_api_steps

    step = PlanStep(step_id=0, intent="x", tool_name="call_host_api",
                    tool_args={"action": "escalate_to_finance"}, is_mutation=True)
    assert _unbind_unknown_host_api_steps([step], set()) == []
    assert step.tool_name == "call_host_api"
