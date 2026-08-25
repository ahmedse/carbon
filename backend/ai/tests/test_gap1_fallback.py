"""Tests for FallbackHandler and HonestUncertaintyHandler (GAP-1).

FallbackHandler: fires on empty draft (routing/outage failure only).
HonestUncertaintyHandler: fires on knowledge gaps — never fabricates.

All assertions are domain-agnostic.
"""
import pytest
from ai.engine.cognition.dialogue.fallback import FallbackHandler, HonestUncertaintyHandler


@pytest.fixture
def handler():
    return FallbackHandler()


@pytest.fixture
def uncertainty_handler():
    return HonestUncertaintyHandler()


# ── FallbackHandler ─────────────────────────────────────────────────────────

def test_non_empty_draft_passes_through(handler):
    original = "Here is the answer you asked for."
    result = handler.handle("What does the pipeline do?", original)
    assert result == original


def test_empty_draft_returns_navigable_response(handler):
    result = handler.handle("Tell me about the reporting module", "")
    assert result.strip() != ""
    assert len(result) > 20


def test_whitespace_only_draft_treated_as_empty(handler):
    result = handler.handle("Tell me about the reporting module", "   \n  ")
    assert result.strip() != ""


def test_ambiguous_query_triggers_clarification_path(handler):
    result = handler.handle("Which one — Option A or Option B?", "")
    assert "clarify" in result.lower() or "which" in result.lower()


def test_non_ambiguous_empty_returns_try_again_message(handler):
    # Empty draft on specific query = routing/outage failure, not a knowledge gap.
    # Must NOT pretend to ask for clarification — that would mask a routing error.
    result = handler.handle("Explain the processing step", "")
    assert "try again" in result.lower() or "temporary" in result.lower() or "rephrase" in result.lower()


def test_fallback_contains_no_domain_terms(handler):
    for msg in ["Tell me about invoices", "What happened to the shipment?", "Analyze patient records"]:
        result = handler.handle(msg, "")
        low = result.lower()
        assert "carbon" not in low
        assert "ghg" not in low
        assert "dq rule" not in low


def test_is_ambiguous_detects_or(handler):
    assert handler._is_ambiguous("Should I use A or B?")


def test_is_ambiguous_detects_which(handler):
    assert handler._is_ambiguous("Which pipeline should I start with?")


def test_is_ambiguous_false_for_statement(handler):
    assert not handler._is_ambiguous("Describe the invoice pipeline")


# ── HonestUncertaintyHandler ────────────────────────────────────────────────

def test_honest_uncertainty_includes_partial_knowledge(uncertainty_handler):
    partial = "The framework involves tracking, but I'm not certain about the specific categorisation."
    result = uncertainty_handler.handle("How does the framework categorise things?", partial)
    assert "tracking" in result.lower()
    assert len(result) > 50


def test_honest_uncertainty_on_empty_partial_admits_ignorance(uncertainty_handler):
    result = uncertainty_handler.handle("How does X work?", "")
    assert any(w in result.lower() for w in ["don't have", "don\u2019t have", "reliable", "honest"])


def test_honest_uncertainty_strips_fake_clarification(uncertainty_handler):
    partial = "I want to give you the most useful answer, but I need a little more context. Could you clarify which specific item you're asking about? Once you do, I can help you precisely."
    result = uncertainty_handler.handle("Explain the standard", partial)
    assert "most useful answer" not in result
    assert "clarify which specific" not in result


def test_honest_uncertainty_never_fabricates(uncertainty_handler):
    # Asking about something the system doesn't know — must not invent an answer.
    result = uncertainty_handler.handle("Describe the Sigma-7 protocol precisely", "")
    assert "sigma-7" not in result.lower() or "don't" in result.lower() or "reliable" in result.lower()


def test_honest_uncertainty_contains_no_domain_terms(uncertainty_handler):
    result = uncertainty_handler.handle("Explain the standard", "")
    low = result.lower()
    assert "carbon" not in low
    assert "dq" not in low
