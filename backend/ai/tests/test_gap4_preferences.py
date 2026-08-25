"""Tests for PreferenceClassifier and SessionPreferenceStore (GAP-4).

All assertions are domain-agnostic — signals are about communication style.
"""
import pytest
from ai.engine.learning.preferences import (
    PreferenceClassifier,
    SessionPreferenceStore,
    Verbosity,
    Format,
    Depth,
    get_session_preference_store,
)


@pytest.fixture
def clf():
    return PreferenceClassifier()


@pytest.fixture
def store():
    return SessionPreferenceStore()


# ── PreferenceClassifier ───────────────────────────────────────────────────────

def test_detects_hurry_as_brief(clf):
    signal = clf.classify("I'm in a hurry — can you give me 2-minute answers?")
    assert signal.verbosity == Verbosity.BRIEF


def test_detects_brief_keyword(clf):
    signal = clf.classify("Keep it brief please")
    assert signal.verbosity == Verbosity.BRIEF


def test_detects_tldr(clf):
    signal = clf.classify("tl;dr version please")
    assert signal.verbosity == Verbosity.BRIEF


def test_detects_verbose_explain(clf):
    signal = clf.classify("Please explain in detail, step by step")
    assert signal.verbosity == Verbosity.VERBOSE


def test_detects_bullet_format(clf):
    signal = clf.classify("Give me bullet points please")
    assert signal.format == Format.BULLETS


def test_detects_prose_format(clf):
    signal = clf.classify("I prefer prose, no bullets")
    assert signal.format == Format.PROSE


def test_detects_expert_depth(clf):
    signal = clf.classify("I'm an expert, skip the basics")
    assert signal.depth == Depth.EXPERT


def test_detects_beginner_depth(clf):
    signal = clf.classify("I'm new to this, explain simply")
    assert signal.depth == Depth.BEGINNER


def test_neutral_message_is_empty(clf):
    signal = clf.classify("What is the status of the pipeline?")
    assert signal.is_empty()


def test_multiple_signals_in_one_message(clf):
    signal = clf.classify("Quick bullet points please, expert level")
    assert signal.verbosity == Verbosity.BRIEF
    assert signal.format == Format.BULLETS
    assert signal.depth == Depth.EXPERT


# ── SessionPreferenceStore ─────────────────────────────────────────────────────

def test_store_updates_on_signal(store, clf):
    signal = clf.classify("Keep it brief")
    store.update("conv1", signal)
    constraints = store.to_prompt_constraints("conv1")
    assert constraints  # non-empty
    assert "concise" in constraints.lower() or "150" in constraints or "200" in constraints


def test_store_constraints_empty_for_normal_preferences(store):
    constraints = store.to_prompt_constraints("conv-new")
    assert constraints == ""


def test_store_update_with_empty_signal_has_no_effect(store):
    from ai.engine.learning.preferences import PreferenceSignal
    store.update("conv1", PreferenceSignal())  # empty signal
    constraints = store.to_prompt_constraints("conv1")
    assert constraints == ""


def test_store_clear_resets_preferences(store, clf):
    store.update("conv1", clf.classify("Keep it brief"))
    store.clear("conv1")
    constraints = store.to_prompt_constraints("conv1")
    assert constraints == ""


def test_singleton_returns_same_instance():
    a = get_session_preference_store()
    b = get_session_preference_store()
    assert a is b
