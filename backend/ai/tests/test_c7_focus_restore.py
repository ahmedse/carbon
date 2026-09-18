"""Tests for C7 focus-stack restore + anaphora ("Back to Abrar")."""
from __future__ import annotations

import pytest

from ai.engine.cognition.dialogue.anaphora import AnaphoraResolver
from ai.engine.memory.working import (
    WorkingMemory,
    update_focus_from_resolve_results,
)


@pytest.fixture
def wm():
    return WorkingMemory()


def _set_abrar(wm: WorkingMemory, cid: str = "conv1") -> None:
    wm.set_focus(
        cid,
        "Abrar Alam Azeemullah Ansari",
        "employee",
        entity_id="1021",
        aliases=["Abrar Alam", "Abrar", "Ansari", "1021"],
    )


def _set_1416(wm: WorkingMemory, cid: str = "conv1") -> None:
    wm.set_focus(
        cid,
        "Employee 1416",
        "employee",
        entity_id="1416",
        aliases=["1416"],
    )


def test_focus_stack_retains_prior_after_switch(wm):
    _set_abrar(wm)
    _set_1416(wm)
    assert wm.get_focus("conv1").entity_id == "1416"
    stack = wm.get_focus_stack("conv1")
    assert len(stack) >= 2
    assert any(f.entity_id == "1021" for f in stack)


def test_find_prior_focus_by_first_name(wm):
    _set_abrar(wm)
    _set_1416(wm)
    found = wm.find_prior_focus("conv1", "Abrar")
    assert found is not None
    assert found.entity_id == "1021"


def test_back_to_abrar_restores_focus_and_rewrites_employee_no(wm):
    _set_abrar(wm)
    _set_1416(wm)
    assert wm.get_focus("conv1").entity_id == "1416"

    resolver = AnaphoraResolver(wm)
    result = resolver.resolve("conv1", "Back to Abrar")

    focus = wm.get_focus("conv1")
    assert focus is not None
    assert focus.entity_id == "1021"
    assert "1021" in result
    assert "Abrar" in result or "abrar" in result.lower()


def test_tell_me_about_abrar_again_restores(wm):
    _set_abrar(wm)
    _set_1416(wm)
    resolver = AnaphoraResolver(wm)
    result = resolver.resolve("conv1", "tell me about Abrar again")
    assert wm.get_focus("conv1").entity_id == "1021"
    assert "1021" in result


def test_anaphora_it_still_resolves_current_focus(wm):
    wm.set_focus("conv1", "Inventory Report", "table")
    resolver = AnaphoraResolver(wm)
    result = resolver.resolve("conv1", "Should I validate it first?")
    assert "Inventory Report" in result


def test_anaphora_it_uses_restored_focus_after_back_to(wm):
    _set_abrar(wm)
    _set_1416(wm)
    resolver = AnaphoraResolver(wm)
    # Restore Abrar, then a follow-up "it" on a later message would use Abrar —
    # same turn: restore only.
    restored = resolver.resolve("conv1", "Back to Abrar")
    assert "1021" in restored
    follow = resolver.resolve("conv1", "describe it now")
    assert "Abrar" in follow


def test_update_focus_from_resolve_entity_match(wm):
    tools = [
        {
            "tool_name": "resolve_entity",
            "result": {
                "found": True,
                "action": "match",
                "record": {
                    "employee_no": "1021",
                    "full_name": "Abrar Alam Azeemullah Ansari",
                    "name_en_given": "Abrar Alam",
                    "name_en_family": "Ansari",
                },
            },
        }
    ]
    focus = update_focus_from_resolve_results(wm, "conv1", tools)
    assert focus is not None
    assert focus.entity_id == "1021"
    assert wm.find_prior_focus("conv1", "Abrar") is not None


def test_c7_scenario_abrar_then_1416_then_back(wm):
    """Full C7 path: Abrar → 1416 → Back to Abrar restores 1021."""
    update_focus_from_resolve_results(
        wm,
        "conv1",
        [
            {
                "tool_name": "resolve_entity",
                "result": {
                    "found": True,
                    "action": "match",
                    "record": {
                        "employee_no": "1021",
                        "full_name": "Abrar Alam Azeemullah Ansari",
                        "name_en_given": "Abrar Alam",
                        "name_en_family": "Ansari",
                    },
                },
            }
        ],
    )
    update_focus_from_resolve_results(
        wm,
        "conv1",
        [
            {
                "tool_name": "resolve_entity",
                "result": {
                    "found": True,
                    "action": "match",
                    "record": {
                        "employee_no": "1416",
                        "full_name": "Other Person",
                        "name_en_given": "Other",
                        "name_en_family": "Person",
                    },
                },
            }
        ],
    )
    assert wm.get_focus("conv1").entity_id == "1416"

    resolved = AnaphoraResolver(wm).resolve("conv1", "Back to Abrar")
    assert wm.get_focus("conv1").entity_id == "1021"
    assert "1021" in resolved
    # Must not leave the message as a bare name with no stable id.
    assert "employee_no" in resolved


def test_prompt_fragment_includes_entity_id(wm):
    _set_abrar(wm)
    frag = wm.to_prompt_fragment("conv1")
    assert "1021" in frag
    assert "Abrar" in frag


def test_stack_dedupes_same_entity_id_on_reactivate(wm):
    _set_abrar(wm)
    _set_1416(wm)
    _set_abrar(wm)
    stack = wm.get_focus_stack("conv1")
    ids = [f.entity_id for f in stack]
    assert ids.count("1021") == 1
    assert stack[0].entity_id == "1021"
