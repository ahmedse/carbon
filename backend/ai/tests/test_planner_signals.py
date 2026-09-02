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
