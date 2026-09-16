"""
ai/tests/test_prompt_grounding_directive.py

Failing tests that prove the two highest-trust (agree=2) audit findings
from the ensemble prompt audit (raw/reviews/audit-prompts.json):

Finding #7 — AGGREGATION RULES hardcoded even when no analyze_* endpoint exists
  _build_grounding_directive includes instructions to call analyze_* endpoints
  even when the catalog has none. A model reading this prompt will attempt to
  call a non-existent tool, fail, and likely fabricate data instead.

Finding #6 — blanket "GET needs no confirmation" conflicts with per-endpoint flag
  _build_api_catalog_section says "Read-only (GET) endpoints need no
  confirmation", but individual endpoints may carry requires_confirmation=True.
  The blanket statement overrides the per-endpoint flag in the model's mind.

Both are deterministic (no LLM, no DB) — they run in milliseconds.
"""

import pytest

from ai.engine.llm.prompts import _build_api_catalog_section, _build_grounding_directive


# ── Finding #7 ───────────────────────────────────────────────────────────────


def test_grounding_directive_without_analyze_endpoints_omits_aggregation_rule():
    """CURRENTLY FAILING: analyze_* rules emitted even when no such endpoint exists."""
    catalog = [
        {"name": "list_employees",    "method": "GET", "description": "List employees"},
        {"name": "list_payroll_runs", "method": "GET", "description": "List payroll runs"},
        {"name": "list_leave_records","method": "GET", "description": "List leave records"},
    ]
    result = _build_grounding_directive(catalog)
    assert "analyze_*" not in result, (
        "_build_grounding_directive emits AGGREGATION RULES referencing analyze_* "
        "even though no analyze_* endpoint is present in the catalog. This tells "
        "the model to call a tool that does not exist."
    )


def test_grounding_directive_with_analyze_endpoints_keeps_aggregation_rule():
    """Positive: when analyze_* IS in the catalog the aggregation rules MUST stay."""
    catalog = [
        {"name": "list_employees",      "method": "GET", "description": "List"},
        {"name": "analyze_employees",   "method": "GET", "description": "Analyze"},
    ]
    result = _build_grounding_directive(catalog)
    assert "analyze_*" in result, (
        "When the catalog contains analyze_* endpoints the aggregation rules "
        "must be present so the model uses them."
    )


def test_grounding_directive_truncation_rule_always_present_with_any_list_endpoint():
    """The truncation rule (rule 2) applies to any list endpoint and must always appear."""
    catalog = [{"name": "list_employees", "method": "GET", "description": "List"}]
    result = _build_grounding_directive(catalog)
    assert "truncated" in result, (
        "The truncated: true rule must always appear when there are list endpoints "
        "so the model never presents a partial page as the full set."
    )


def test_grounding_directive_empty_catalog_returns_empty():
    assert _build_grounding_directive(None) == ""
    assert _build_grounding_directive([]) == ""


# ── Finding #6 ───────────────────────────────────────────────────────────────


def test_api_catalog_section_does_not_make_blanket_get_no_confirmation_claim():
    """CURRENTLY FAILING: blanket 'GET needs no confirmation' overrides per-endpoint flag."""
    # A GET endpoint that requires confirmation (e.g. a read that has side effects
    # or exposes sensitive PII requiring explicit consent).
    catalog = [
        {"name": "get_salary_details", "method": "GET",
         "description": "Return full salary breakdown",
         "requires_confirmation": True},
        {"name": "list_employees", "method": "GET",
         "description": "List employees",
         "requires_confirmation": False},
    ]
    result = _build_api_catalog_section(catalog)

    # The blanket "Read-only (GET) endpoints need no confirmation" must not
    # appear when at least one GET endpoint requires confirmation.
    blanket = "Read-only (GET) endpoints need no confirmation"
    assert blanket not in result, (
        f"_build_api_catalog_section emits the blanket statement "
        f"'{blanket}' even though get_salary_details has requires_confirmation=True. "
        "This overrides the per-endpoint flag in the model's mind."
    )


def test_api_catalog_section_confirmation_flag_annotated_on_endpoint():
    """Positive: a GET endpoint with requires_confirmation=True must be annotated."""
    catalog = [
        {"name": "get_salary_details", "method": "GET",
         "description": "Return full salary breakdown",
         "requires_confirmation": True},
    ]
    result = _build_api_catalog_section(catalog)
    assert "requires user confirmation" in result.lower() or "[confirmation]" in result.lower(), (
        "A GET endpoint with requires_confirmation=True must be annotated in the "
        "catalog section so the model knows to stage it before calling."
    )


def test_api_catalog_section_blanket_ok_when_no_get_requires_confirmation():
    """When NO GET endpoint needs confirmation the blanket claim is accurate and may stay."""
    catalog = [
        {"name": "list_employees",    "method": "GET",  "requires_confirmation": False},
        {"name": "create_leave",      "method": "POST", "requires_confirmation": True},
    ]
    result = _build_api_catalog_section(catalog)
    # At minimum the POST endpoint should still be annotated.
    assert "requires user confirmation" in result.lower() or "create_leave" in result
