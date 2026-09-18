"""P1 — branched + resilient payroll board-pack demo (seed oracle).

Asserts ``build_payroll_board_pack_plan_json`` declares:
  * choice after variance (within band vs Finance escalate)
  * critic catch → observe repair (no silent export)
  * host-task retry / timeout
  * workflow_graph validates (ADR-0034)

Does not rewrite the ReAct driver — extends the seed seam only.
"""

from __future__ import annotations

from ai.engine.workflow.graph import WorkflowGraph, validate_graph
from ai.management.commands.seed_complex_agent_demos import (
    TEMPLATE_SPECS,
    build_payroll_board_pack_plan_json,
)


def test_payroll_board_pack_workflow_graph_validates():
    plan = build_payroll_board_pack_plan_json()
    wg = plan["workflow_graph"]
    g = WorkflowGraph.from_dict(wg)
    assert validate_graph(g) == [], validate_graph(g)
    assert g.entry == "t0"


def test_payroll_board_pack_has_choice_after_variance():
    plan = build_payroll_board_pack_plan_json()
    wg = plan["workflow_graph"]
    choice = next(n for n in wg["nodes"] if n["id"] == "choice_variance")
    assert choice["node_type"] == "choice"
    outs = [e for e in wg["edges"] if e["source"] == "choice_variance"]
    assert len(outs) == 2
    guarded = next(e for e in outs if e.get("guard"))
    default = next(e for e in outs if e.get("is_default"))
    assert "variance_pct" in guarded["guard"]
    assert guarded["target"] == "t2"
    assert default["target"] == "t5"


def test_payroll_board_pack_critic_catch_blocks_silent_export():
    plan = build_payroll_board_pack_plan_json()
    wg = plan["workflow_graph"]
    critic = next(n for n in wg["nodes"] if n["id"] == "t3")
    assert critic["catch"]
    assert critic["catch"][0]["next"] == "observe_repair"
    observe = next(n for n in wg["nodes"] if n["id"] == "observe_repair")
    assert observe["node_type"] == "observe"
    fail = next(n for n in wg["nodes"] if n["id"] == "fail_block_export")
    assert fail["node_type"] == "fail"
    # Unresolved repair cannot reach export — default edge to fail.
    obs_outs = [e for e in wg["edges"] if e["source"] == "observe_repair"]
    assert any(e.get("is_default") and e["target"] == "fail_block_export" for e in obs_outs)
    # Escalate path also blocks export.
    assert any(
        e["source"] == "t5" and e["target"] == "fail_block_export" for e in wg["edges"]
    )


def test_payroll_board_pack_host_steps_declare_retry():
    plan = build_payroll_board_pack_plan_json()
    wg = plan["workflow_graph"]
    for nid in ("t0", "t1"):
        node = next(n for n in wg["nodes"] if n["id"] == nid)
        assert node.get("retry"), nid
        assert node["retry"]["max_attempts"] >= 2
        assert node.get("timeout_ms")


def test_payroll_board_pack_happy_path_skips_escalate():
    plan = build_payroll_board_pack_plan_json()
    branch = plan["demo_branch"]
    assert branch["taken"] == "within_band"
    assert 5 in branch["skipped_step_ids"]
    export = next(s for s in plan["steps"] if s["tool_name"] == "export_document")
    assert export["tool_args"]["format"] == "pack"
    assert export["depends_on"] == [3]


def test_template_specs_payroll_uses_branched_builder():
    payroll = next(t for t in TEMPLATE_SPECS if t["name"] == "Payroll variance board pack")
    assert "workflow_graph" in payroll["plan_json"]
    assert any(
        n.get("node_type") == "choice"
        for n in payroll["plan_json"]["workflow_graph"]["nodes"]
    )
