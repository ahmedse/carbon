import pytest

from ai.engine.cognition.plan.planner import (
    _is_agent_discuss_turn,
    _looks_agent_multi_step,
    _score_skill,
    _wants_explicit_task_creation,
)


def test_emissions_by_supplier():
    assert _looks_agent_multi_step("show me emissions by supplier last quarter") is True


def test_top_dq_issues():
    assert _looks_agent_multi_step("what are the top 5 DQ issues in the emissions module") is True


def test_compare_violation_rates():
    assert _looks_agent_multi_step("compare rule violation rates across modules") is True


def test_simple_lookup_stays_single():
    assert _looks_agent_multi_step("what is the platform name") is False


def test_greeting_stays_single():
    assert _looks_agent_multi_step("hello") is False


def test_need_a_task_is_explicit_task_creation():
    msg = "now i need a task to create amazing word file with all the charts and tables"
    assert _wants_explicit_task_creation(msg) is True
    assert _wants_explicit_task_creation("analyze salaries by nationality") is False


def test_score_skill_does_not_hotpath_unrelated_payroll_skill():
    """Underscore name + weak desc overlap must stay below match threshold."""

    class _Skill:
        name = "payroll_run_variance_check"
        description = (
            "Compare payroll run totals and variance for salary distributions "
            "by location nationality specialty and charts"
        )
        success_rate = 0
        usage_count = 0

    utterance = (
        "now i need a task to create amazing word file with all the charts "
        "and tables about salary distribution"
    ).lower()
    score = _score_skill(_Skill(), utterance)
    assert score < 0.5


def test_agent_discuss_refine_is_not_multi_step():
    """Agent → Discuss seed must not trip ReAct / invoke_skill."""
    draft = (
        'I\'d like to refine plan (plan 74a5e6a6-942c-4185-a986-8f895601d5ca): '
        '"Count Nibras employees by employment status and list the top 3 statuses with counts.".\n\n'
        "DISCUSSION ONLY — reply in Chat with one improved brief and a short numbered step list.\n"
        "Do not call tools, invoke_skill, plan_task, or re-run the analysis.\n"
        "Do not change the Agent plan until I say to Fork or Replan."
    )
    assert _is_agent_discuss_turn(draft) is True
    assert _looks_agent_multi_step(draft) is False


def test_agent_discuss_outcome_with_analyze_verb_stays_single():
    """Pasted prior outcome often contains 'analyze' — still discuss-only."""
    draft = (
        "Let's discuss the outcome of: Count Nibras employees (plan abc).\n"
        "---\n"
        "Prior outcome (context only — do not re-execute):\n"
        "I will analyze the employee population based on is_active.\n"
        "---\n"
        "DISCUSSION ONLY — answer in Chat about findings.\n"
        "Do not change the Agent plan until I say to Fork or Replan."
    )
    assert _is_agent_discuss_turn(draft) is True
    assert _looks_agent_multi_step(draft) is False


@pytest.mark.asyncio
async def test_decompose_skips_skill_match_on_discuss_turn():
    """Matching skills must not route discuss seeds to invoke_skill."""
    from ai.engine.cognition.plan.planner import SkillAwarePlanner

    class _Skill:
        name = "count_employees"
        kind = "procedure"
        body = {}

    class _Reg:
        async def search(self, *a, **k):
            return [_Skill()]

    draft = (
        'I\'d like to refine plan (plan abc): "Count Nibras employees".\n\n'
        "DISCUSSION ONLY — reply in Chat.\n"
        "Do not change the Agent plan until I say to Fork or Replan."
    )
    plan = await SkillAwarePlanner().decompose(
        draft, _Reg(), instance_id="i", user_id="u",
    )
    assert plan.source == "single_step"
    assert plan.steps[0].tool_name is None


# ── export-step coercion (document-generation reliability) ──────────────────

from ai.engine.cognition.plan.planner import _coerce_export_steps, _ensure_export_deliverable, PlanStep


def test_coerce_word_step_to_export_docx():
    s = PlanStep(step_id=4, intent="Generate a downloadable Word report", tool_name=None)
    _coerce_export_steps([s])
    assert s.tool_name == "export_document"
    assert s.tool_args["format"] == "docx"
    assert s.is_mutation is False  # mutation flag set later by _MUTATION_TOOL_NAMES


def test_coerce_excel_step_to_export_xlsx():
    s = PlanStep(step_id=5, intent="Generate an Excel workbook with the data", tool_name=None)
    _coerce_export_steps([s])
    assert s.tool_name == "export_document"
    assert s.tool_args["format"] == "xlsx"


def test_coerce_generic_downloadable_to_both():
    s = PlanStep(step_id=6, intent="Produce a downloadable report of the findings", tool_name=None)
    _coerce_export_steps([s])
    assert s.tool_name == "export_document"
    assert s.tool_args["format"] == "both"


def test_reasoning_step_not_coerced():
    s = PlanStep(step_id=3, intent="Analyze and compare the grid factor internationally", tool_name=None)
    _coerce_export_steps([s])
    assert s.tool_name is None


def test_existing_tool_step_untouched():
    s = PlanStep(step_id=0, intent="Generate an Excel workbook", tool_name="call_host_api")
    _coerce_export_steps([s])
    assert s.tool_name == "call_host_api"


def test_ensure_export_appended_when_brief_asks_for_docx():
    steps = [
        PlanStep(step_id=0, intent="Count employees", tool_name="get_entity_details"),
        PlanStep(step_id=1, intent="Summarize findings", tool_name=None),
    ]
    _ensure_export_deliverable(
        "Count employees by status and export a Word report",
        steps,
    )
    assert len(steps) == 3
    assert steps[-1].tool_name == "export_document"
    assert steps[-1].tool_args["format"] == "docx"


def test_ensure_export_noop_when_already_present():
    steps = [
        PlanStep(step_id=0, intent="Export Word", tool_name="export_document", tool_args={"format": "docx"}),
    ]
    _ensure_export_deliverable("export a Word report", steps)
    assert len(steps) == 1

