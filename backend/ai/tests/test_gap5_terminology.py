"""Tests for TerminologyResolver (GAP-5).

All assertions are domain-agnostic — terminology maps are arbitrary.
"""
import pytest
from ai.engine.knowledge.terminology import TerminologyResolver


@pytest.fixture
def resolver():
    return TerminologyResolver()


def test_injects_terminology_section(resolver):
    prompt = "You are a helpful assistant."
    result = resolver.inject(prompt, {"null check": "not_null"})
    assert "CANONICAL TERMINOLOGY" in result
    assert "not_null" in result
    assert "null check" in result


def test_injects_multiple_terms(resolver):
    terminology = {
        "format check": "pattern",
        "duplicate detection": "dedup_check",
        "range validation": "range_check",
    }
    result = resolver.inject("base prompt", terminology)
    for platform_term in ["pattern", "dedup_check", "range_check"]:
        assert platform_term in result
    for human_phrase in terminology:
        assert human_phrase in result


def test_empty_terminology_returns_prompt_unchanged(resolver):
    prompt = "You are a helpful assistant."
    result = resolver.inject(prompt, {})
    assert result == prompt


def test_base_prompt_is_preserved(resolver):
    prompt = "System: you answer questions carefully."
    result = resolver.inject(prompt, {"old": "new_term"})
    assert prompt in result


def test_no_domain_hardcoding_in_resolver(resolver):
    # The resolver must accept any terminology without knowing the domain
    result = resolver.inject("prompt", {"invoice total": "total_amount"})
    assert "total_amount" in result
    assert "invoice total" in result
