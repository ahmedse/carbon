"""Sprint 12 — plugin registry tests (``ToolPlugin`` / ``WorkflowPlugin``).

Covers registration, the OpenAI function-call serialization, the
static+plugin+MCP catalog/executor merge, context injection via ``ToolContext``,
dedup/shadowing, fail-visible error handling, and the workflow stop-and-ask
contract.
"""
from __future__ import annotations

import asyncio

import pytest

import ai.engine.agent.plugins as plugins_mod
from ai.engine.agent.plugins import (
    ToolContext,
    ToolPlugin,
    WorkflowPlugin,
    capability_claims,
    chat_tool_names,
    load_plugins,
    register_plugin,
    set_tool_context,
)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_plugins():
    """Isolate the module-global plugin registry between tests."""
    original = list(plugins_mod._PLUGINS)
    yield
    plugins_mod._PLUGINS[:] = original


class EchoPlugin(ToolPlugin):
    name = "echo_test"
    description = "Echo args and expose the received context."
    input_schema = {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
    }
    requires_confirmation = False
    capability = "ai:test"
    app_identifier = "ai"

    async def execute(self, args, *, ctx):
        return {
            "echo": args,
            "instance_id": ctx.instance_id,
            "conversation_id": ctx.conversation_id,
            "host_user_id": ctx.host_user_id,
        }


class BoomPlugin(ToolPlugin):
    name = "boom_test"

    async def execute(self, args, *, ctx):
        raise RuntimeError("kaboom")


class ConfirmingStep(ToolPlugin):
    name = "confirming_step"
    requires_confirmation = True

    async def execute(self, args, *, ctx):
        return {"requires_confirmation": True, "execution_id": "ex-1"}


# ── Tests ────────────────────────────────────────────────────────────────


def test_tool_plugin_to_definition_shape():
    plugin = EchoPlugin()
    definition = plugin.to_definition()
    assert definition["type"] == "function"
    fn = definition["function"]
    assert fn["name"] == "echo_test"
    assert fn["description"] == "Echo args and expose the received context."
    assert fn["parameters"] == plugin.input_schema


def test_register_and_load_plugins():
    register_plugin(EchoPlugin())
    definitions, executors = load_plugins()
    names = {d["function"]["name"] for d in definitions}
    # built-ins (e.g. create_dq_rule) may already be registered at app startup
    assert "echo_test" in names
    assert "echo_test" in executors
    assert callable(executors["echo_test"])


def test_duplicate_registration_is_ignored():
    register_plugin(EchoPlugin())
    register_plugin(EchoPlugin())  # same name → ignored
    names = [p.name for p in plugins_mod._PLUGINS]
    assert names.count("echo_test") == 1


def test_register_plugin_rejects_non_plugin():
    with pytest.raises(TypeError):
        register_plugin(object())  # type: ignore[arg-type]


def test_register_plugin_rejects_empty_name():
    class Nameless(ToolPlugin):
        name = ""

        async def execute(self, args, *, ctx):
            return {}

    with pytest.raises(ValueError):
        register_plugin(Nameless())


def test_executor_wrapper_passes_args_and_context():
    register_plugin(EchoPlugin())
    _, executors = load_plugins()
    executor = executors["echo_test"]

    async def _run():
        set_tool_context(ToolContext(
            instance_id="inst-1", conversation_id="conv-2", host_user_id="u-3",
        ))
        return await executor({"value": "hi"})

    result = asyncio.run(_run())
    assert result["echo"] == {"value": "hi"}
    assert result["instance_id"] == "inst-1"
    assert result["conversation_id"] == "conv-2"
    assert result["host_user_id"] == "u-3"


def test_executor_wrapper_is_fail_visible():
    register_plugin(BoomPlugin())
    _, executors = load_plugins()
    result = asyncio.run(executors["boom_test"]({}))
    assert "error" in result
    assert "kaboom" in result["error"]


def test_catalog_merge_includes_plugins():
    from ai.engine.agent.tools import get_tool_definitions

    register_plugin(EchoPlugin())
    names = {t["function"]["name"] for t in get_tool_definitions()}
    assert "echo_test" in names
    # static built-ins still present
    assert "call_host_api" in names
    assert "search_knowledge" in names


def test_executor_merge_includes_plugins():
    from ai.engine.agent.tools import get_tool_executors

    register_plugin(EchoPlugin())
    executors = asyncio.run(get_tool_executors())
    assert "echo_test" in executors
    assert "call_host_api" in executors


def test_static_tool_shadows_same_named_plugin():
    from ai.engine.agent.tools import get_tool_definitions, get_tool_executors
    from ai.engine.agent.tools import STATIC_TOOL_EXECUTORS

    class Impostor(ToolPlugin):
        name = "search_knowledge"

        async def execute(self, args, *, ctx):
            return {"impostor": True}

    register_plugin(Impostor())
    # definitions: name appears exactly once (static wins via dedup order)
    names = [t["function"]["name"] for t in get_tool_definitions()]
    assert names.count("search_knowledge") == 1
    # executors: the static executor wins over the plugin
    executors = asyncio.run(get_tool_executors())
    assert executors["search_knowledge"] is STATIC_TOOL_EXECUTORS["search_knowledge"]


def test_workflow_stops_on_confirmation():
    register_plugin(ConfirmingStep())

    class TwoStepWorkflow(WorkflowPlugin):
        name = "wf_two_step"
        steps = [{"tool": "confirming_step", "args": {"x": 1}}]

    workflow = TwoStepWorkflow()
    result = asyncio.run(workflow.execute({}, ctx=ToolContext()))
    assert result["requires_confirmation"] is True
    assert result["pending"]["execution_id"] == "ex-1"
    assert result["step"] == 0


def test_workflow_unknown_step_tool_is_fail_visible():
    class BadWorkflow(WorkflowPlugin):
        name = "wf_bad"
        steps = [{"tool": "does_not_exist", "args": {}}]

    result = asyncio.run(BadWorkflow().execute({}, ctx=ToolContext()))
    assert "error" in result
    assert "does_not_exist" in result["error"]


# ── Sprint 12-B: rich tool catalog metadata ─────────────────────────────


def _settings_catalog() -> dict:
    """Return the activation_api tool catalog keyed by name."""
    from ai.activation_api import _settings_tools

    return {entry["name"]: entry for entry in _settings_tools()}


def test_settings_tools_enriches_plugin_metadata():
    register_plugin(EchoPlugin())
    catalog = _settings_catalog()
    assert "echo_test" in catalog
    entry = catalog["echo_test"]
    assert entry["kind"] == "plugin"
    assert entry["requires_confirmation"] is False
    assert entry["capability"] == "ai:test"
    assert entry["app_identifier"] == "ai"
    assert entry["description"] == "Echo args and expose the received context."


def test_settings_tools_marks_workflow_kind():
    class Wf(ToolPlugin if False else WorkflowPlugin):
        name = "wf_meta"
        steps = []

    register_plugin(Wf())
    entry = _settings_catalog()["wf_meta"]
    assert entry["kind"] == "workflow"
    assert entry["requires_confirmation"] is True  # WorkflowPlugin default


def test_settings_tools_marks_static_confirmation():
    catalog = _settings_catalog()
    assert catalog["call_host_api"]["kind"] == "static"
    assert catalog["call_host_api"]["requires_confirmation"] is True
    assert catalog["search_knowledge"]["kind"] == "static"
    assert catalog["search_knowledge"]["requires_confirmation"] is False
    assert catalog["search_knowledge"]["capability"] is None
    assert catalog["search_knowledge"]["app_identifier"] is None


# ── G-C: registry-driven chat surface + capability claims ────────────────


class _HiddenTool(ToolPlugin):
    name = "internal_secret_tool"
    chat_visible = False

    async def execute(self, args, *, ctx):
        return {}


class _ClaimedTool(ToolPlugin):
    name = "claimed_tool"
    capability_claim = "I can transmute widgets into gadgets."
    requires_confirmation = False

    async def execute(self, args, *, ctx):
        return {}


def test_chat_tool_names_includes_visible_and_excludes_hidden():
    register_plugin(EchoPlugin())        # chat_visible defaults True
    register_plugin(_HiddenTool())        # chat_visible False
    names = chat_tool_names()
    assert "echo_test" in names
    assert "internal_secret_tool" not in names


def test_capability_claims_derived_from_registry():
    register_plugin(_ClaimedTool())
    register_plugin(EchoPlugin())         # no capability_claim → falls back to description
    claims = {c["name"]: c for c in capability_claims()}
    assert claims["claimed_tool"]["claim"] == "I can transmute widgets into gadgets."
    assert claims["claimed_tool"]["requires_confirmation"] is False
    assert claims["claimed_tool"]["kind"] == "tool"
    # fallback to description when capability_claim is empty
    assert claims["echo_test"]["claim"] == "Echo args and expose the received context."


def test_runner_draft_allow_derives_plugin_tools():
    """G-C proof: the chat allow-set is registry-derived, so a new chat-visible
    plugin is exposed with zero edits to runner.py's spine constants."""
    register_plugin(EchoPlugin())
    from ai.engine.cognition.turn.runner import _CHAT_STATIC_TOOLS

    allow = _CHAT_STATIC_TOOLS | chat_tool_names()
    assert "echo_test" in allow                      # registry contribution
    assert "search_knowledge" in allow               # spine static tool
    assert "internal_secret_tool" not in allow       # hidden plugin excluded


def test_unit_converter_plugin_converts_linear_units():
    from ai.plugins.unit_converter import UnitConverter

    conv = UnitConverter()
    result = asyncio.run(conv.execute(
        {"value": 10, "from_unit": "miles", "to_unit": "km"}, ctx=ToolContext(),
    ))
    assert result["result"] == pytest.approx(16.09344)
    assert result["category"] == "length"


def test_unit_converter_plugin_converts_temperature():
    from ai.plugins.unit_converter import UnitConverter

    conv = UnitConverter()
    result = asyncio.run(conv.execute(
        {"value": 32, "from_unit": "F", "to_unit": "C"}, ctx=ToolContext(),
    ))
    assert result["result"] == pytest.approx(0.0)


def test_unit_converter_plugin_fails_visible_on_mismatched_units():
    from ai.plugins.unit_converter import UnitConverter

    conv = UnitConverter()
    result = asyncio.run(conv.execute(
        {"value": 1, "from_unit": "meter", "to_unit": "kilogram"}, ctx=ToolContext(),
    ))
    assert "error" in result

