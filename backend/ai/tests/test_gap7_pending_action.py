"""Tests for PendingActionStore (GAP-M6).

PendingActionStore tracks Pulse's open "shall I remember X?" proposal so a
short "yes" is recognised as a confirmation, not a fresh query.

All assertions are domain-agnostic.
"""
import pytest
from ai.engine.cognition.dialogue.pending_action import (
    PendingActionStore,
    get_pending_action_store,
)


@pytest.fixture
def store():
    return PendingActionStore()


# ── detect_proposal ─────────────────────────────────────────────────────────

def test_detects_store_proposal(store):
    result = store.detect_proposal(
        "Would you like me to store that your name is Alex?"
    )
    assert result is not None
    assert result["fact"]
    assert "Alex" in result["fact"]


def test_detects_remember_proposal(store):
    result = store.detect_proposal(
        "Shall I remember that you prefer weekly reports?"
    )
    assert result is not None
    assert result["fact"]
    assert "weekly reports" in result["fact"]


def test_detects_save_proposal(store):
    result = store.detect_proposal("Should I save the Widget settings for later?")
    assert result is not None
    assert "Widget settings" in result["fact"]


def test_infers_preference_category(store):
    result = store.detect_proposal("Shall I remember that you prefer brief answers?")
    assert result is not None
    assert result["category"] == "preference"


def test_infers_identity_category(store):
    result = store.detect_proposal("Should I remember that my name is Sam?")
    assert result is not None
    assert result["category"] == "identity"


def test_observation_category_default(store):
    result = store.detect_proposal("Would you like me to store the Alpha Table size?")
    assert result is not None
    assert result["category"] == "observation"


def test_detect_proposal_returns_none_for_non_proposal(store):
    for text in [
        "What is a table?",
        "Explain the standard.",
        "Please analyze the Dataset.",
        "Here are your results.",
        "The pipeline is running.",
    ]:
        assert store.detect_proposal(text) is None, text


def test_detect_proposal_none_for_empty(store):
    assert store.detect_proposal("") is None
    assert store.detect_proposal(None) is None


# ── check_confirmation ──────────────────────────────────────────────────────

def test_confirms_yes_when_pending(store):
    store.set_pending("conv1", "your name is Alex", "identity")
    assert store.check_confirmation("conv1", "yes") is not None


def test_confirms_ok_when_pending(store):
    store.set_pending("conv1", "your name is Alex")
    assert store.check_confirmation("conv1", "ok") is not None


def test_confirms_do_it_when_pending(store):
    store.set_pending("conv1", "your name is Alex")
    assert store.check_confirmation("conv1", "do it") is not None


def test_confirms_store_it_when_pending(store):
    store.set_pending("conv1", "you prefer weekly reports", "preference")
    result = store.check_confirmation("conv1", "store it")
    assert result is not None
    assert result["fact"] == "you prefer weekly reports"


def test_confirmation_returns_fact_and_category(store):
    store.set_pending("conv1", "the Alpha Table has 12 rows", "observation")
    result = store.check_confirmation("conv1", "yes")
    assert result["fact"] == "the Alpha Table has 12 rows"
    assert result["category"] == "observation"


def test_long_message_with_yes_is_not_confirmation(store):
    store.set_pending("conv1", "your name is Alex")
    long_msg = "yes I would also like you to explain the Dataset schema in detail"
    assert store.check_confirmation("conv1", long_msg) is None


def test_bare_yes_without_pending_returns_none(store):
    assert store.check_confirmation("conv1", "yes") is None


def test_yes_for_different_conversation_returns_none(store):
    store.set_pending("conv1", "your name is Alex")
    assert store.check_confirmation("conv2", "yes") is None


def test_non_affirmative_short_message_returns_none(store):
    store.set_pending("conv1", "your name is Alex")
    assert store.check_confirmation("conv1", "no") is None
    assert store.check_confirmation("conv1", "not now") is None


def test_round_trip_set_check_clear(store):
    store.set_pending("conv1", "you manage the Alpha Table", "observation")
    assert store.get_pending("conv1") is not None
    assert store.check_confirmation("conv1", "yes please") is not None
    store.clear("conv1")
    assert store.get_pending("conv1") is None
    assert store.check_confirmation("conv1", "yes") is None


def test_clear_missing_conversation_is_noop(store):
    store.clear("conv-does-not-exist")  # must not raise


def test_singleton_returns_same_instance():
    a = get_pending_action_store()
    b = get_pending_action_store()
    assert a is b
