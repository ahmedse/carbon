"""Tests for WorkingMemory (GAP-2).

All assertions are domain-agnostic.
"""
import threading

import pytest
from ai.engine.memory.working import WorkingMemory, WorkingFocus, get_working_memory


@pytest.fixture
def wm():
    return WorkingMemory()


def test_set_and_get_focus(wm):
    wm.set_focus("conv1", "Invoice", "table")
    focus = wm.get_focus("conv1")
    assert focus is not None
    assert focus.entity == "Invoice"
    assert focus.entity_type == "table"


def test_get_focus_unknown_conversation_returns_none(wm):
    assert wm.get_focus("never-set") is None


def test_set_focus_overwrites_previous(wm):
    wm.set_focus("conv1", "First", "item")
    wm.set_focus("conv1", "Second", "table")
    assert wm.get_focus("conv1").entity == "Second"


def test_clear_removes_focus(wm):
    wm.set_focus("conv1", "SomeRecord", "item")
    wm.clear("conv1")
    assert wm.get_focus("conv1") is None


def test_clear_unknown_conversation_is_safe(wm):
    wm.clear("never-set")  # must not raise


def test_prompt_fragment_includes_entity_name(wm):
    wm.set_focus("conv1", "Lab Results", "dataset")
    fragment = wm.to_prompt_fragment("conv1")
    assert "Lab Results" in fragment
    assert "dataset" in fragment


def test_prompt_fragment_empty_if_no_focus(wm):
    assert wm.to_prompt_fragment("conv-no-focus") == ""


def test_thread_safety_concurrent_writes():
    wm = WorkingMemory()
    errors: list[Exception] = []

    def set_focus(cid: str, entity: str) -> None:
        try:
            wm.set_focus(cid, entity, "item")
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=set_focus, args=(f"conv{i}", f"Entity{i}"))
        for i in range(50)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors


def test_singleton_returns_same_instance():
    a = get_working_memory()
    b = get_working_memory()
    assert a is b
