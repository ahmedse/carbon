"""W-1 / W-2 — workflow graph schema + sandboxed guards."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai.engine.workflow.graph import (
    GraphValidationError,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    compile_plan_to_graph,
    validate_graph,
)
from ai.engine.workflow.guards import GuardError, eval_guard


def test_compile_sequential_depends_on():
    plan = SimpleNamespace(
        steps=[
            SimpleNamespace(
                step_id=0, intent="fetch", tool_name="get_entity_details",
                tool_args={}, is_mutation=False, depends_on=[], agent_role="orchestrator",
            ),
            SimpleNamespace(
                step_id=1, intent="count", tool_name=None,
                tool_args={}, is_mutation=False, depends_on=[0], agent_role="orchestrator",
            ),
        ],
        phases=[],
    )
    g = compile_plan_to_graph(plan)
    assert g.entry == "t0"
    assert {n.id for n in g.nodes} == {"t0", "t1"}
    assert any(e.source == "t0" and e.target == "t1" for e in g.edges)
    assert validate_graph(g) == []


def test_compile_parallel_phase():
    plan = SimpleNamespace(
        steps=[
            SimpleNamespace(
                step_id=0, intent="a", tool_name=None, tool_args={},
                is_mutation=False, depends_on=[], agent_role="orchestrator",
            ),
            SimpleNamespace(
                step_id=1, intent="b", tool_name=None, tool_args={},
                is_mutation=False, depends_on=[], agent_role="orchestrator",
            ),
        ],
        phases=[
            SimpleNamespace(phase_id=0, name="fan", strategy="parallel", step_ids=[0, 1]),
        ],
    )
    g = compile_plan_to_graph(plan)
    assert any(n.node_type == "parallel" for n in g.nodes)
    assert validate_graph(g) == []
    # round-trip
    g2 = WorkflowGraph.from_dict(g.to_dict())
    assert len(g2.nodes) == len(g.nodes)
    assert validate_graph(g2) == []


def test_compile_connects_cross_phase_dependencies_and_parallel_exports():
    def step(step_id, depends_on):
        return SimpleNamespace(
            step_id=step_id,
            intent=f"step {step_id}",
            tool_name=None,
            tool_args={},
            is_mutation=False,
            depends_on=depends_on,
            agent_role="orchestrator",
        )

    plan = SimpleNamespace(
        steps=[
            step(0, []),
            step(1, []),
            step(2, [0, 1]),
            step(3, [2]),
            step(4, [2]),
        ],
        phases=[
            SimpleNamespace(phase_id=0, name="reads", strategy="sequential", step_ids=[0, 1]),
            SimpleNamespace(phase_id=1, name="synthesis", strategy="sequential", step_ids=[2]),
            SimpleNamespace(phase_id=2, name="exports", strategy="parallel", step_ids=[3, 4]),
        ],
    )
    graph = compile_plan_to_graph(plan)
    assert graph.entry == "t0"
    assert validate_graph(graph) == []
    edge_pairs = {(edge.source, edge.target) for edge in graph.edges}
    assert ("t0", "t2") in edge_pairs
    assert ("t1", "t2") in edge_pairs
    assert ("t2", "p2") in edge_pairs


def test_validate_graph_rejects_disconnected_nodes():
    graph = WorkflowGraph(
        nodes=[WorkflowNode(id="a"), WorkflowNode(id="orphan")],
        edges=[],
        entry="a",
    )
    assert any("unreachable" in error for error in validate_graph(graph))


def test_choice_requires_default_edge():
    g = WorkflowGraph(
        nodes=[
            WorkflowNode(id="c", node_type="choice", intent="pick"),
            WorkflowNode(id="a", node_type="task"),
            WorkflowNode(id="b", node_type="task"),
        ],
        edges=[
            WorkflowEdge(source="c", target="a", guard="status == 'ok'"),
            WorkflowEdge(source="c", target="b", guard="status == 'bad'"),
        ],
        entry="c",
    )
    errs = validate_graph(g)
    assert any("default" in e for e in errs)

    g.edges.append(WorkflowEdge(source="c", target="b", is_default=True))
    # duplicate edge ok for test — revalidate with fixed graph
    g2 = WorkflowGraph(
        nodes=g.nodes,
        edges=[
            WorkflowEdge(source="c", target="a", guard="status == 'ok'"),
            WorkflowEdge(source="c", target="b", is_default=True),
        ],
        entry="c",
    )
    assert validate_graph(g2) == []


def test_guard_basic_ops():
    ctx = {"status": "ok", "count": 3, "nested": {"x": 1}, "items": ["a", "b"]}
    assert eval_guard("status == 'ok'", ctx) is True
    assert eval_guard("count > 2 and nested.x == 1", ctx) is True
    assert eval_guard("not status == 'bad'", ctx) is True
    assert eval_guard("'a' in items", ctx) is True
    assert eval_guard("count < 1 or status == 'ok'", ctx) is True


def test_guard_rejects_injection():
    with pytest.raises(GuardError):
        eval_guard("__import__('os')", {})
    with pytest.raises(GuardError):
        eval_guard("status()", {"status": "ok"})


def test_invalid_node_type():
    g = WorkflowGraph(
        nodes=[WorkflowNode(id="x", node_type="teleport")],
        edges=[],
        entry="x",
    )
    assert any("unknown node_type" in e for e in validate_graph(g))


def test_driver_choice_routing():
    from ai.engine.workflow.driver import choose_edge, decide_choice, ready_nodes

    g = WorkflowGraph(
        nodes=[
            WorkflowNode(id="c", node_type="choice", intent="pick"),
            WorkflowNode(id="ok", node_type="task", intent="ok path"),
            WorkflowNode(id="bad", node_type="task", intent="bad path"),
        ],
        edges=[
            WorkflowEdge(source="c", target="ok", guard="status == 'ok'"),
            WorkflowEdge(source="c", target="bad", is_default=True),
        ],
        entry="c",
    )
    assert validate_graph(g) == []
    assert {n.id for n in ready_nodes(g, [])} == {"c"}
    chosen = choose_edge(g, "c", {"status": "ok"})
    assert chosen is not None and chosen.target == "ok"
    ready = ready_nodes(g, ["c"], context={"status": "ok"})
    assert {n.id for n in ready} == {"ok"}
    edge, evs = decide_choice(g, "c", {"status": "ok"})
    assert edge.target == "ok"
    assert any(e.get("result") is True for e in evs)


def test_advance_and_ready_skips_unchosen_branch():
    from ai.engine.workflow.driver import advance_and_ready_tasks

    g = WorkflowGraph(
        nodes=[
            WorkflowNode(id="t0", node_type="task", intent="probe", meta={"step_id": 0}),
            WorkflowNode(id="c", node_type="choice", intent="pick"),
            WorkflowNode(id="t1", node_type="task", intent="ok path", meta={"step_id": 1}),
            WorkflowNode(id="t2", node_type="task", intent="bad path", meta={"step_id": 2}),
            WorkflowNode(id="t3", node_type="task", intent="join", meta={"step_id": 3}),
        ],
        edges=[
            WorkflowEdge(source="t0", target="c"),
            WorkflowEdge(source="c", target="t1", guard="status == 'ok'"),
            WorkflowEdge(source="c", target="t2", is_default=True),
            WorkflowEdge(source="t1", target="t3"),
            WorkflowEdge(source="t2", target="t3"),
        ],
        entry="t0",
    )
    assert validate_graph(g) == []

    choices: list[str] = []

    def on_choice(node_id, chosen, _evs):
        choices.append(node_id)
        assert chosen is not None and chosen.target == "t1"

    ready, skipped, gateways, skipped_nodes = advance_and_ready_tasks(
        g, completed_step_ids=[0], context={"status": "ok"}, on_choice=on_choice,
    )
    assert choices == ["c"]
    assert ready == [1]
    assert skipped == {2}
    assert "c" in gateways
    assert "t2" in skipped_nodes
    # Diamond join must NOT be skipped — still reachable via chosen path.
    assert "t3" not in skipped_nodes

    ready2, skipped2, _, _ = advance_and_ready_tasks(
        g,
        completed_step_ids=[0, 1],
        context={"status": "ok"},
        completed_gateways=gateways,
        skipped_graph_ids=skipped_nodes,
    )
    assert ready2 == [3]
    assert skipped2 == set()


def test_advance_and_ready_linear_matches_depends_on():
    from ai.engine.workflow.driver import advance_and_ready_tasks

    plan = SimpleNamespace(
        steps=[
            SimpleNamespace(
                step_id=0, intent="a", tool_name=None, tool_args={},
                is_mutation=False, depends_on=[], agent_role="orchestrator",
            ),
            SimpleNamespace(
                step_id=1, intent="b", tool_name=None, tool_args={},
                is_mutation=False, depends_on=[0], agent_role="orchestrator",
            ),
            SimpleNamespace(
                step_id=2, intent="c", tool_name=None, tool_args={},
                is_mutation=False, depends_on=[1], agent_role="orchestrator",
            ),
        ],
        phases=[],
    )
    g = compile_plan_to_graph(plan)
    ready, skipped, _, _ = advance_and_ready_tasks(g, [])
    assert ready == [0]
    assert skipped == set()
    ready, _, _, _ = advance_and_ready_tasks(g, [0])
    assert ready == [1]
    ready, _, _, _ = advance_and_ready_tasks(g, [0, 1])
    assert ready == [2]


@pytest.mark.asyncio
async def test_react_loop_choice_skips_unchosen_branch():
    """Live ReActLoop: workflow graph choice drives which steps execute."""
    from unittest.mock import AsyncMock, patch

    from ai.engine.cognition.plan.loop import ReActLoop, StepResult
    from ai.engine.cognition.plan.planner import Plan, PlanStep

    g = WorkflowGraph(
        nodes=[
            WorkflowNode(id="t0", node_type="task", intent="probe", meta={"step_id": 0}),
            WorkflowNode(id="c", node_type="choice", intent="pick"),
            WorkflowNode(id="t1", node_type="task", intent="ok", meta={"step_id": 1}),
            WorkflowNode(id="t2", node_type="task", intent="bad", meta={"step_id": 2}),
        ],
        edges=[
            WorkflowEdge(source="t0", target="c"),
            WorkflowEdge(source="c", target="t1", guard="status == 'ok'"),
            WorkflowEdge(source="c", target="t2", is_default=True),
        ],
        entry="t0",
    )
    plan = Plan(
        pattern="custom",
        source="test",
        synthesis_instruction="done",
        steps=[
            PlanStep(step_id=0, intent="probe", depends_on=[]),
            PlanStep(step_id=1, intent="ok", depends_on=[0]),
            PlanStep(step_id=2, intent="bad", depends_on=[0]),
        ],
    )

    executed: list[int] = []
    choices: list[tuple] = []

    loop = ReActLoop(llm_client=None)

    async def fake_execute_step(**kwargs):
        step = kwargs["step"]
        executed.append(step.step_id)
        return StepResult(
            step_id=step.step_id,
            intent=step.intent,
            draft_text=f"out-{step.step_id}",
            critic_verdict="pass",
            executed=True,
            tokens_used=1,
        )

    loop._execute_step = fake_execute_step  # type: ignore[method-assign]

    wf_ctx = {"status": "ok"}

    def on_choice(node_id, chosen, evaluations):
        choices.append((node_id, chosen.target if chosen else None, evaluations))

    with patch(
        "ai.engine.cognition.plan.loop._get_broadcast",
        return_value=AsyncMock(),
    ):
        result = await loop.run(
            plan=plan,
            instance_id="test",
            conversation_id="c1",
            user_message="go",
            system_prompt="sys",
            workflow_graph=g,
            workflow_context=wf_ctx,
            on_workflow_choice=on_choice,
        )

    assert executed == [0, 1]
    assert 2 not in executed
    assert any(c[0] == "c" and c[1] == "t1" for c in choices)
    by_id = {r.step_id: r for r in result.step_results}
    assert by_id[2].executed is False


def test_resolve_catch_and_propose_heal():
    from ai.engine.workflow.driver import resolve_catch
    from ai.engine.workflow.heal import propose_heal
    from ai.engine.cognition.plan.planner import PlanStep

    node = WorkflowNode(
        id="t0",
        node_type="task",
        catch=[{"on": ["permanent"], "next": "obs"}],
    )
    assert resolve_catch(node, "permanent") == "obs"
    assert resolve_catch(node, "transient") is None

    failed = PlanStep(step_id=0, intent="fetch x", depends_on=[])
    remaining = [
        PlanStep(step_id=1, intent="use x", depends_on=[0]),
        PlanStep(step_id=2, intent="report", depends_on=[1]),
    ]
    proposal = propose_heal(
        goal="answer the user",
        failed_step=failed,
        failed_error="404",
        remaining_steps=remaining,
        next_step_id=10,
    )
    assert proposal.gap_step_ids == [0]
    assert proposal.new_steps[0].step_id == 10
    assert proposal.new_steps[0].is_mutation is False
    # Remaining deps scrubbed of failed id; recovery prepended
    assert 0 not in proposal.new_steps[1].depends_on
    assert 10 in proposal.new_steps[1].depends_on


@pytest.mark.asyncio
async def test_react_loop_catch_observe_heal_completed_with_gaps():
    """Failed step with catch→observe heals remainder → completed_with_gaps."""
    from unittest.mock import AsyncMock, patch

    from ai.engine.cognition.plan.loop import ReActLoop, StepResult
    from ai.engine.cognition.plan.planner import Plan, PlanStep

    g = WorkflowGraph(
        nodes=[
            WorkflowNode(
                id="t0", node_type="task", intent="fetch", meta={"step_id": 0},
                catch=[{"on": ["permanent"], "next": "obs"}],
            ),
            WorkflowNode(id="obs", node_type="observe", intent="heal"),
            WorkflowNode(id="t1", node_type="task", intent="report", meta={"step_id": 1}),
        ],
        edges=[
            WorkflowEdge(source="t0", target="t1"),
            WorkflowEdge(source="t0", target="obs"),  # catch path (also linked via catch.next)
        ],
        entry="t0",
    )
    plan = Plan(
        pattern="custom",
        source="test",
        synthesis_instruction="summarize",
        steps=[
            PlanStep(step_id=0, intent="fetch", depends_on=[]),
            PlanStep(step_id=1, intent="report", depends_on=[0]),
        ],
    )

    executed: list[int] = []
    heals: list[str] = []
    loop = ReActLoop(llm_client=None)

    async def fake_execute_step(**kwargs):
        step = kwargs["step"]
        executed.append(step.step_id)
        if step.step_id == 0:
            return StepResult(
                step_id=0,
                intent=step.intent,
                critic_verdict="pass",
                executed=False,
                error="upstream 500",
            )
        return StepResult(
            step_id=step.step_id,
            intent=step.intent,
            draft_text=f"ok-{step.step_id}",
            critic_verdict="pass",
            executed=True,
        )

    loop._execute_step = fake_execute_step  # type: ignore[method-assign]

    def on_heal(node_id, proposal):
        heals.append(node_id)

    with patch(
        "ai.engine.cognition.plan.loop._get_broadcast",
        return_value=AsyncMock(),
    ):
        result = await loop.run(
            plan=plan,
            instance_id="test",
            conversation_id="c1",
            user_message="get me a report",
            system_prompt="sys",
            workflow_graph=g,
            on_heal_proposed=on_heal,
        )

    assert heals == ["obs"]
    assert 0 in executed
    # Recovery + re-queued report should run
    assert any(i != 0 for i in executed)
    by_id = {r.step_id: r for r in result.step_results}
    assert by_id[0].error and by_id[0].error.startswith("[caught]")
    assert result.succeeded is True
    assert "gaps" in (result.final_response or "").lower() or result.succeeded


def test_derived_status_completed_with_gaps():
    from types import SimpleNamespace

    from ai.plans_service import (
        STATUS_COMPLETED_WITH_GAPS,
        STATUS_FAILED,
        _derived_status_from_steps,
    )

    steps = [
        SimpleNamespace(status="completed", error=None),
        SimpleNamespace(status="failed", error="[caught] boom"),
        SimpleNamespace(status="skipped", error="unchosen_branch"),
    ]
    assert _derived_status_from_steps(steps) == STATUS_COMPLETED_WITH_GAPS

    steps_hard = [
        SimpleNamespace(status="completed", error=None),
        SimpleNamespace(status="failed", error="boom"),
    ]
    assert _derived_status_from_steps(steps_hard) == STATUS_FAILED


def test_retry_policy_helpers():
    from ai.engine.workflow.retry import (
        backoff_seconds,
        classify_error,
        normalize_retry_policy,
        should_retry,
    )

    assert classify_error("503 unavailable") == "transient"
    assert classify_error("timed out waiting") == "timeout"
    assert classify_error("permission denied") == "permanent"

    p = normalize_retry_policy({
        "max_attempts": 4,
        "base_ms": 100,
        "max_ms": 400,
        "retry_on": ["transient", "timeout"],
    })
    assert should_retry(p, "429 rate limit", 0) is True
    assert should_retry(p, "429 rate limit", 3) is False  # 4th failure
    assert should_retry(p, "permission denied", 0) is False
    assert backoff_seconds(p, 1) == 0.1
    assert backoff_seconds(p, 2) == 0.2
    assert backoff_seconds(p, 3) == 0.4  # capped


def test_evaluate_loop_and_expand_map():
    from ai.engine.workflow.loops import evaluate_loop, evaluate_map, expand_map

    g = WorkflowGraph(
        nodes=[
            WorkflowNode(
                id="L", node_type="loop", max_iterations=3,
                meta={"guard": "loop_iter < 2", "body_step_ids": [1]},
            ),
            WorkflowNode(id="t1", node_type="task", meta={"step_id": 1}),
            WorkflowNode(id="done", node_type="task", meta={"step_id": 2}),
        ],
        edges=[
            WorkflowEdge(source="L", target="t1"),
            WorkflowEdge(source="L", target="done", is_default=True),
            WorkflowEdge(source="t1", target="L"),
        ],
        entry="L",
    )
    assert validate_graph(g) == []
    loop_node = g.nodes[0]
    iters: dict[str, int] = {}
    action, body, iters = evaluate_loop(
        g, loop_node, {"loop_iter": 0}, iters,
    )
    assert action == "body" and body == [1] and iters["L"] == 1
    action, body, iters = evaluate_loop(
        g, loop_node, {"loop_iter": 1}, iters,
    )
    assert action == "body" and iters["L"] == 2
    action, body, iters = evaluate_loop(
        g, loop_node, {"loop_iter": 2}, iters,
    )
    assert action == "exit" and body == []

    mapped = expand_map(
        WorkflowNode(
            id="m", node_type="map", collection_path="items", max_iterations=5,
        ),
        {"items": [1, 2, 3, 4, 5, 6]},
    )
    assert mapped == [1, 2, 3, 4, 5]

    mg = WorkflowGraph(
        nodes=[
            WorkflowNode(
                id="m", node_type="map", collection_path="items",
                meta={"body_step_ids": [7]},
            ),
            WorkflowNode(id="t7", node_type="task", meta={"step_id": 7}),
        ],
        edges=[WorkflowEdge(source="m", target="t7")],
        entry="m",
    )
    miters: dict[str, int] = {}
    action, body, miters, item = evaluate_map(
        mg, mg.nodes[0], {"items": ["a", "b"]}, miters,
    )
    assert action == "body" and body == [7] and item == "a" and miters["m"] == 1
    action, body, miters, item = evaluate_map(
        mg, mg.nodes[0], {"items": ["a", "b"]}, miters,
    )
    assert item == "b"
    action, body, miters, item = evaluate_map(
        mg, mg.nodes[0], {"items": ["a", "b"]}, miters,
    )
    assert action == "exit" and item is None


def test_compensation_target_and_timeout_classify():
    from ai.engine.workflow.compensate import compensation_step_id
    from ai.engine.workflow.retry import classify_error

    assert classify_error("[timeout] exceeded timeout_ms=50") == "timeout"

    g = WorkflowGraph(
        nodes=[
            WorkflowNode(
                id="t0", node_type="task", meta={"step_id": 0},
                compensation="rev",
                timeout_ms=50,
            ),
            WorkflowNode(
                id="rev", node_type="task", meta={"step_id": 9}, is_mutation=True,
            ),
        ],
        edges=[],
        entry="t0",
    )
    assert compensation_step_id(g, g.nodes[0]) == 9


@pytest.mark.asyncio
async def test_react_loop_timeout_ms_marks_timeout_error():
    from unittest.mock import AsyncMock, patch
    import asyncio as aio

    from ai.engine.cognition.plan.loop import ReActLoop, StepResult
    from ai.engine.cognition.plan.planner import Plan, PlanStep

    plan = Plan(
        pattern="custom",
        source="test",
        synthesis_instruction="done",
        steps=[PlanStep(step_id=0, intent="slow")],
    )
    g = WorkflowGraph(
        nodes=[
            WorkflowNode(id="t0", node_type="task", meta={"step_id": 0}, timeout_ms=20),
        ],
        edges=[],
        entry="t0",
    )
    loop = ReActLoop(llm_client=None)

    async def slow_step(**kwargs):
        await aio.sleep(1.0)
        return StepResult(step_id=0, intent="slow", critic_verdict="pass", executed=True)

    loop._execute_step = slow_step  # type: ignore[method-assign]

    with patch(
        "ai.engine.cognition.plan.loop._get_broadcast",
        return_value=AsyncMock(),
    ):
        result = await loop.run(
            plan=plan,
            instance_id="test",
            conversation_id="c1",
            user_message="go",
            system_prompt="sys",
            workflow_graph=g,
        )

    assert result.step_results[0].error
    assert result.step_results[0].error.startswith("[timeout]")


@pytest.mark.asyncio
async def test_react_loop_respects_node_retry_policy():
    """Transient tool errors retry per node policy; permanent does not."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from ai.engine.cognition.plan.loop import ReActLoop
    from ai.engine.cognition.plan.planner import Plan, PlanStep
    from ai.engine.cognition.turn.witnesses import CriticVerdict, DraftResult

    plan = Plan(
        pattern="custom",
        source="test",
        synthesis_instruction="done",
        steps=[PlanStep(step_id=0, intent="call api", tool_name="call_host_api")],
    )
    g = WorkflowGraph(
        nodes=[
            WorkflowNode(
                id="t0", node_type="task", meta={"step_id": 0},
                retry={
                    "max_attempts": 3,
                    "base_ms": 0,
                    "max_ms": 0,
                    "backoff": "none",
                    "retry_on": ["transient"],
                },
            ),
        ],
        edges=[],
        entry="t0",
    )

    calls = {"n": 0}

    class _Exec:
        async def execute(self, **kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                return MagicMock(completed_tools=[{
                    "tool_name": "call_host_api",
                    "error": "503 unavailable",
                }])
            return MagicMock(completed_tools=[{
                "tool_name": "call_host_api",
                "result": '{"ok": true}',
            }])

    class _Draft:
        async def draft(self, **kwargs):
            return DraftResult(
                text="x",
                tool_calls=[{"name": "call_host_api", "arguments": "{}"}],
            )

    class _Critic:
        async def review(self, **kwargs):
            return CriticVerdict(verdict="pass", flags=[])

    loop = ReActLoop(
        llm_client=None,
        draft_witness=_Draft(),
        critic_witness=_Critic(),
        executor=_Exec(),
    )

    with patch(
        "ai.engine.cognition.plan.loop._get_broadcast",
        return_value=AsyncMock(),
    ), patch(
        "ai.engine.agent.tools.get_tool_definitions",
        return_value=[],
    ):
        # Skip observation hop that needs more LLM wiring
        loop._should_inject_followup = lambda *a, **k: False  # type: ignore
        result = await loop.run(
            plan=plan,
            instance_id="test",
            conversation_id="c1",
            user_message="go",
            system_prompt="sys",
            workflow_graph=g,
        )

    assert calls["n"] == 3
    assert result.step_results[0].error is None
    assert result.succeeded is True


def test_evaluate_wait_immediate_duration_until():
    from ai.engine.workflow.wait import evaluate_wait, wait_duration_ms

    empty = WorkflowNode(id="w0", node_type="wait")
    d0 = evaluate_wait(empty, {})
    assert d0.satisfied and d0.reason == "immediate"

    timed = WorkflowNode(id="w1", node_type="wait", meta={"wait_ms": 200})
    assert wait_duration_ms(timed) == 200
    pending = evaluate_wait(timed, {}, elapsed_ms=0)
    assert not pending.satisfied and pending.sleep_ms == 200
    done = evaluate_wait(timed, {}, elapsed_ms=200)
    assert done.satisfied and done.reason == "duration"

    until = WorkflowNode(
        id="w2", node_type="wait", meta={"until": "status == 'ready'"},
    )
    assert not evaluate_wait(until, {"status": "wait"}).satisfied
    early = evaluate_wait(until, {"status": "ready"})
    assert early.satisfied and early.reason == "until"


def test_advance_blocks_on_unsatisfied_wait():
    from ai.engine.workflow.driver import advance_and_ready_tasks

    g = WorkflowGraph(
        nodes=[
            WorkflowNode(id="t0", node_type="task", intent="a", meta={"step_id": 0}),
            WorkflowNode(id="w", node_type="wait", meta={"wait_ms": 5000}),
            WorkflowNode(id="t1", node_type="task", intent="b", meta={"step_id": 1}),
        ],
        edges=[
            WorkflowEdge(source="t0", target="w"),
            WorkflowEdge(source="w", target="t1"),
        ],
        entry="t0",
    )
    ready, _, gateways, _ = advance_and_ready_tasks(g, completed_step_ids=[0])
    assert ready == []
    assert "w" not in gateways

    ready2, _, gateways2, _ = advance_and_ready_tasks(
        g, completed_step_ids=[0], completed_gateways={"w"},
    )
    assert ready2 == [1]
    assert "w" in gateways2


@pytest.mark.asyncio
async def test_react_loop_wait_timer_then_continues():
    """Live ReActLoop: wait node sleeps then unlocks the next task."""
    from unittest.mock import AsyncMock, patch

    from ai.engine.cognition.plan.loop import ReActLoop, StepResult
    from ai.engine.cognition.plan.planner import Plan, PlanStep

    g = WorkflowGraph(
        nodes=[
            WorkflowNode(id="t0", node_type="task", intent="before", meta={"step_id": 0}),
            WorkflowNode(id="w", node_type="wait", meta={"wait_ms": 50}),
            WorkflowNode(id="t1", node_type="task", intent="after", meta={"step_id": 1}),
        ],
        edges=[
            WorkflowEdge(source="t0", target="w"),
            WorkflowEdge(source="w", target="t1"),
        ],
        entry="t0",
    )
    plan = Plan(
        pattern="custom",
        source="test",
        synthesis_instruction="done",
        steps=[
            PlanStep(step_id=0, intent="before", depends_on=[]),
            PlanStep(step_id=1, intent="after", depends_on=[0]),
        ],
    )
    executed: list[int] = []
    waits: list[str] = []

    loop = ReActLoop(llm_client=None)

    async def fake_execute_step(**kwargs):
        step = kwargs["step"]
        executed.append(step.step_id)
        return StepResult(
            step_id=step.step_id,
            intent=step.intent,
            draft_text=f"out-{step.step_id}",
            critic_verdict="pass",
            executed=True,
            tokens_used=1,
        )

    loop._execute_step = fake_execute_step  # type: ignore[method-assign]

    async def _on_wait(node_id, decision, duration_ms=0, until=None):
        waits.append(f"{node_id}:{decision.reason}:{duration_ms}")

    with patch(
        "ai.engine.cognition.plan.loop._get_broadcast",
        return_value=AsyncMock(),
    ):
        result = await loop.run(
            plan=plan,
            instance_id="test",
            conversation_id="c1",
            user_message="go",
            system_prompt="sys",
            workflow_graph=g,
            on_wait_fired=_on_wait,
        )

    assert executed == [0, 1]
    assert any(w.startswith("w:duration:50") for w in waits)
    assert result.succeeded is True


@pytest.mark.asyncio
async def test_react_loop_followup_orphan_runs_under_workflow_graph():
    """Follow-ups not in workflow_graph must still run (not stuck Pending)."""
    from unittest.mock import AsyncMock, patch

    from ai.engine.cognition.plan.loop import ObservationResult, ReActLoop, StepResult
    from ai.engine.cognition.plan.planner import Plan, PlanStep

    g = WorkflowGraph(
        nodes=[
            WorkflowNode(id="t0", node_type="task", intent="probe", meta={"step_id": 0}),
        ],
        edges=[],
        entry="t0",
    )
    plan = Plan(
        pattern="custom",
        source="test",
        synthesis_instruction="done",
        steps=[PlanStep(step_id=0, intent="probe", depends_on=[])],
    )
    executed: list[int] = []
    loop = ReActLoop(llm_client=None)

    async def fake_execute_step(**kwargs):
        step = kwargs["step"]
        executed.append(step.step_id)
        if step.step_id == 0:
            return StepResult(
                step_id=0,
                intent=step.intent,
                draft_text="need more",
                critic_verdict="pass",
                executed=True,
                tokens_used=1,
                followup=ObservationResult(
                    needs_followup=True,
                    followup_tool="web_research",
                    followup_args={"query": "nibras"},
                    answer="interim",
                ),
            )
        return StepResult(
            step_id=step.step_id,
            intent=step.intent,
            draft_text="fetched",
            critic_verdict="pass",
            executed=True,
            tokens_used=1,
        )

    loop._execute_step = fake_execute_step  # type: ignore[method-assign]
    loop._synthesise = AsyncMock(return_value="final")  # type: ignore[method-assign]

    with patch(
        "ai.engine.cognition.plan.loop._get_broadcast",
        return_value=AsyncMock(),
    ):
        result = await loop.run(
            plan=plan,
            instance_id="test",
            conversation_id="c1",
            user_message="go",
            system_prompt="sys",
            workflow_graph=g,
        )

    assert 0 in executed
    assert any(i != 0 for i in executed), "follow-up orphan must execute"
    assert result.succeeded is True
    # No Pending leftovers in results
    assert all(
        r.executed or r.error is None
        for r in result.step_results
    )
