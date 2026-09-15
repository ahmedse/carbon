from ai.engine.cognition.plan.planner import _looks_agent_multi_step


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


# ── export-step coercion (document-generation reliability) ──────────────────

from ai.engine.cognition.plan.planner import _coerce_export_steps, PlanStep


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
