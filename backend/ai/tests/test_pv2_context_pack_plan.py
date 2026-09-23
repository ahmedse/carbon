"""PV2-2B — ContextPack for Agent plan / discovery LLM stages.

Static AST gate: ``plan/**`` and ``plans_service`` discovery must not feed
module-level ``*_SYSTEM_PROMPT`` (or long persona Constant strings) as the
sole ``route_chat`` system message. Allowed: ``pack.system_prompt()``.

Runtime: agent surfaces emit RULE_21 autonomy + stage TaskBlocks.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from ai.engine.cognition.context_pack import (
    AGENT_DISCOVERY_AUTONOMY,
    AGENT_PLAN_AUTONOMY,
    TASK_AGENT_PLAN_DRAFT,
    TASK_DECOMPOSE,
    TASK_DISCOVERY_CLARIFY,
    TASK_OBSERVE,
    TASK_PLAN_SYNTHESIS,
    build_context_pack,
)
from ai.tests.test_pv2_context_pack import (
    _collect_route_chat_violations,
    _module_system_prompt_names,
)

_PLAN_ROOT = (
    Path(__file__).resolve().parents[1] / "engine" / "cognition" / "plan"
)
_PLANS_SERVICE = Path(__file__).resolve().parents[1] / "plans_service.py"
_SYSTEM_PROMPT_NAME_RE = re.compile(r".*_SYSTEM_PROMPT$")


def test_plan_route_chat_system_prompts_come_from_context_pack():
    """AST gate: plan/** route_chat system content must be pack.system_prompt()."""
    assert _PLAN_ROOT.is_dir(), _PLAN_ROOT
    all_violations: list[str] = []
    for path in sorted(_PLAN_ROOT.rglob("*.py")):
        all_violations.extend(_collect_route_chat_violations(path))
    assert all_violations == [], (
        "plan/** route_chat system prompts must come from "
        "ContextPack.system_prompt(); found:\n  "
        + "\n  ".join(all_violations)
    )


def test_plan_modules_have_no_module_level_system_prompt_constants():
    leftovers: list[str] = []
    for path in sorted(_PLAN_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name in sorted(_module_system_prompt_names(tree)):
            leftovers.append(f"{path.name}: {name}")
    assert leftovers == [], (
        "module-level *_SYSTEM_PROMPT must not live in plan/** "
        "(task wording lives in context_pack TaskBlocks):\n  "
        + "\n  ".join(leftovers)
    )


def test_plans_service_has_no_discovery_system_prompt_constant():
    """Discovery identity must not be a class/module *_SYSTEM_PROMPT."""
    src = _PLANS_SERVICE.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(_PLANS_SERVICE))
    names = set(_module_system_prompt_names(tree))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and _SYSTEM_PROMPT_NAME_RE.match(
                    target.id
                ):
                    names.add(target.id)
                if isinstance(target, ast.Attribute) and _SYSTEM_PROMPT_NAME_RE.match(
                    target.attr
                ):
                    names.add(target.attr)
        elif isinstance(node, ast.AnnAssign):
            t = node.target
            if isinstance(t, ast.Name) and _SYSTEM_PROMPT_NAME_RE.match(t.id):
                names.add(t.id)
            if isinstance(t, ast.Attribute) and _SYSTEM_PROMPT_NAME_RE.match(t.attr):
                names.add(t.attr)
    discoveryish = sorted(n for n in names if "DISCOVERY" in n.upper())
    assert discoveryish == [], (
        "plans_service must not define DISCOVERY_*_SYSTEM_PROMPT; "
        f"found {discoveryish}"
    )


def test_plans_service_discovery_prompt_uses_pack_system_prompt():
    """_discovery_prompt must call pack.system_prompt() for the system message."""
    src = _PLANS_SERVICE.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(_PLANS_SERVICE))
    found_pack = False
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != "_discovery_prompt":
            continue
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "system_prompt"
            ):
                found_pack = True
                break
    assert found_pack, (
        "plans_service._discovery_prompt must use pack.system_prompt() "
        "as the system message content"
    )


@pytest.mark.parametrize(
    "surface,stage,task_body,task_marker",
    [
        ("agent_plan", "decompose", "", "Plan decompose"),
        ("agent_plan", "observe", "", "Observe tool result"),
        ("agent_plan", "plan_synthesis", "", "Plan synthesis"),
        ("agent_discovery", "discovery_clarify", "", "Discovery clarify"),
        ("agent_plan", "draft", TASK_AGENT_PLAN_DRAFT, "Agent plan step draft"),
    ],
)
def test_agent_stage_pack_has_identity_autonomy_and_task(
    surface, stage, task_body, task_marker,
):
    pack = build_context_pack(
        None,
        surface=surface,
        stage=stage,
        user_info={
            "username": "emp_1067",
            "display_name": "Test Emp",
            "audience": ["ess"],
        },
        instance_config={
            "persona": "You are Pulse for Nibras.",
            "guidance_by_audience": {"ess": "ESS guidance."},
            "timezone": "Asia/Riyadh",
        },
        language="en",
        task_body=task_body,
        include_history=False,
        include_state=False,
        include_knowledge=False,
        include_memory=False,
    )
    system = pack.system_prompt()
    assert "Today's date:" in system
    assert f"Surface: {surface}" in system
    assert "RULE_21" in system
    if surface == "agent_plan":
        assert "Agent plan" in AGENT_PLAN_AUTONOMY or "RULE_21" in system
    else:
        assert "discovery" in AGENT_DISCOVERY_AUTONOMY.lower() or "RULE_21" in system
    assert task_marker in system
    assert "You are Pulse for Nibras." in system


def test_agent_task_templates_mention_bound_values_not_identity():
    """A5 legibility: TaskBlocks forbid inventing free-form identity."""
    for text in (
        TASK_DECOMPOSE,
        TASK_OBSERVE,
        TASK_PLAN_SYNTHESIS,
        TASK_DISCOVERY_CLARIFY,
        TASK_AGENT_PLAN_DRAFT,
    ):
        lower = text.lower()
        assert "bound" in lower or "invent" in lower or "confirmation" in lower
        assert "you are pulse, the planning assistant" not in lower


def test_discovery_prompt_runtime_pack_markers():
    """Host discovery builder returns agent_discovery Identity + TaskBlock."""
    from ai.plans_service import PlansService

    msgs = PlansService()._discovery_prompt(
        "Build a DQ uniqueness rule",
        [],
        user_info={"username": "admin", "display_name": "Admin", "audience": ["hr"]},
        instance_config={
            "persona": "You are Pulse.",
            "guidance_by_audience": {"hr": "HR guidance."},
            "timezone": "UTC",
        },
        language="en",
    )
    assert msgs[0]["role"] == "system"
    system = msgs[0]["content"]
    assert "Surface: agent_discovery" in system
    assert "RULE_21" in system
    assert "Discovery clarify" in system or "ONE concise question" in system
    assert "You are Pulse, the planning assistant for the Carbon" not in system
