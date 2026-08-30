"""Tests for Redis-backed ShortTermMemory (Pulse 0.2 Phase A1).

The critical anti-drift invariant (L1): Redis is the source of truth. A fresh
ShortTermMemory instance must read back what another instance wrote — proving
reads come from Redis, not from an in-process dict.
"""
import pytest

from ai.engine.memory.short_term import ShortTermMemory


@pytest.fixture
def st():
    return ShortTermMemory()


def test_add_and_get_all_round_trips(st):
    st.clear("conv-roundtrip")
    st.add_message("conv-roundtrip", "user", "hello")
    st.add_message("conv-roundtrip", "assistant", "hi there")
    msgs = st.get_all_messages("conv-roundtrip")
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "hello"
    st.clear("conv-roundtrip")


def test_context_window_returns_recent_messages(st):
    st.clear("conv-ctx")
    st.add_message("conv-ctx", "user", "first")
    st.add_message("conv-ctx", "assistant", "second")
    window = st.get_context_window("conv-ctx", max_tokens=4096)
    assert [m["content"] for m in window] == ["first", "second"]
    st.clear("conv-ctx")


def test_fresh_instance_reads_from_redis(st):
    """Anti-drift (L1): a brand-new instance sees data another instance wrote."""
    st.clear("conv-shared")
    ShortTermMemory().add_message("conv-shared", "user", "persisted-across-instances")

    reader = ShortTermMemory()
    contents = [m["content"] for m in reader.get_all_messages("conv-shared")]
    assert "persisted-across-instances" in contents
    st.clear("conv-shared")


def test_clear_empties_redis(st):
    st.add_message("conv-clear", "user", "to be cleared")
    st.clear("conv-clear")
    assert st.get_all_messages("conv-clear") == []
    # also verified through a fresh instance (Redis is source of truth)
    assert ShortTermMemory().get_all_messages("conv-clear") == []


def test_conversation_count_includes_active_conversations(st):
    st.clear("conv-count-1")
    st.clear("conv-count-2")
    st.add_message("conv-count-1", "user", "one")
    st.add_message("conv-count-2", "user", "two")
    assert st.conversation_count() >= 2
    st.clear("conv-count-1")
    st.clear("conv-count-2")
