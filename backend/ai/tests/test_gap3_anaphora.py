"""Tests for AnaphoraResolver (GAP-3).

All assertions are domain-agnostic — entity names are from generic domains.
"""
import pytest
from ai.engine.memory.working import WorkingMemory
from ai.engine.cognition.dialogue.anaphora import AnaphoraResolver


@pytest.fixture
def wm_with_inventory():
    wm = WorkingMemory()
    wm.set_focus("conv1", "Inventory Report", "table")
    return wm


def test_resolves_validate_it(wm_with_inventory):
    resolver = AnaphoraResolver(wm_with_inventory)
    result = resolver.resolve("conv1", "Should I validate it first?")
    assert "Inventory Report" in result


def test_resolves_profile_it(wm_with_inventory):
    resolver = AnaphoraResolver(wm_with_inventory)
    result = resolver.resolve("conv1", "profile it now")
    assert "Inventory Report" in result


def test_resolves_analyze_it(wm_with_inventory):
    resolver = AnaphoraResolver(wm_with_inventory)
    result = resolver.resolve("conv1", "analyze it before proceeding")
    assert "Inventory Report" in result


def test_resolves_it_adverb(wm_with_inventory):
    resolver = AnaphoraResolver(wm_with_inventory)
    result = resolver.resolve("conv1", "review it first")
    assert "Inventory Report" in result


def test_no_resolution_without_focus():
    wm = WorkingMemory()
    resolver = AnaphoraResolver(wm)
    msg = "Should I validate it first?"
    result = resolver.resolve("conv1", msg)
    assert result == msg  # unchanged when no focus


def test_subject_position_it_not_replaced(wm_with_inventory):
    """'It's a good idea' must NOT substitute the entity."""
    resolver = AnaphoraResolver(wm_with_inventory)
    msg = "It's a good idea to start early."
    result = resolver.resolve("conv1", msg)
    assert "Inventory Report" not in result


def test_subject_position_how_many_resolved(wm_with_inventory):
    """'How many rows should it have?' — subject 'it' should be resolved."""
    resolver = AnaphoraResolver(wm_with_inventory)
    result = resolver.resolve("conv1", "How many rows should it have?")
    assert "Inventory Report" in result


def test_how_much_subject_it_resolved(wm_with_inventory):
    """'How much data does it contain?' — subject 'it' should be resolved."""
    resolver = AnaphoraResolver(wm_with_inventory)
    result = resolver.resolve("conv1", "How much data does it contain?")
    assert "Inventory Report" in result


def test_unknown_conversation_returns_unchanged():
    wm = WorkingMemory()
    wm.set_focus("conv-other", "Something", "item")
    resolver = AnaphoraResolver(wm)
    msg = "validate it now"
    # "conv-missing" has no focus → unchanged
    result = resolver.resolve("conv-missing", msg)
    assert result == msg


def test_different_entity_types_resolve_same_way():
    for entity, etype in [("Order", "table"), ("Customer ID", "field"), ("Batch", "item")]:
        wm = WorkingMemory()
        wm.set_focus("c1", entity, etype)
        resolver = AnaphoraResolver(wm)
        result = resolver.resolve("c1", "check it now")
        assert entity in result
