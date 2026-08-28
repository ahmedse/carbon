"""
Phase 2b-3a — DQ task wiring proof.

Proves ``dq.validate`` and ``dq.suggest`` complete end-to-end through
``dispatch_task`` with a stubbed LLM, and fail visible on LLM outage:

    dq.validate  -> {"results": [{"rule_id", "status", "details": [...]}]}
    dq.suggest   -> {"suggestions": [{"prompt", "rule_type", "rationale",
                                      "suggested_severity", "confidence"}]}

Fail-visible contract:
- LLM outage -> ``pulse_unavailable``/``llm_unavailable`` (never a fabricated
  verdict or a fake suggestion).
- Unparseable ``dq.validate`` verdict -> per-rule ``skipped_unavailable``.
- Unparseable ``dq.suggest`` verdict -> ``pulse_unavailable``.

The LLM is stubbed (``get_llm_client``) because the dev environment has no
``LLM_API_KEY``.  Durable writes (LLMCallLog budget logging) land in the
PostgreSQL test DB via the DjangoStore, mirroring ``test_kg_wiring.py``.
"""

from __future__ import annotations

import json
import types
from unittest.mock import patch

import pytest
from django.test import override_settings

from ai.engine.core.config import get_settings
from ai.store import reset_store


# ── Fixtures ─────────────────────────────────────────────────────────────


def _fake_completion(content: str) -> types.SimpleNamespace:
    """Return an OpenAI-shaped completion whose content is *content*."""

    async def _create(**kw):
        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(content=content, tool_calls=None),
                    finish_reason="stop",
                )
            ],
            usage=types.SimpleNamespace(
                prompt_tokens=10, completion_tokens=4, total_tokens=14
            ),
        )

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=_create))
    )


@pytest.fixture
def django_store():
    """Use the Django backend so durable writes land in the test DB."""
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


@pytest.fixture
def cfg():
    """Clear the settings cache around each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _stub_llm(content: str):
    """Patch the LLM client to return *content* as the completion."""
    return patch(
        "ai.engine.llm.provider.get_llm_client",
        return_value=_fake_completion(content),
    )


# ── Shared payloads ──────────────────────────────────────────────────────

VALIDATE_PAYLOAD = {
    "rules": [
        {
            "id": "r1",
            "prompt": "co2e_kg must be non-negative",
            "fields": ["co2e_kg"],
            "severity": "error",
        }
    ],
    "rows": [
        {"co2e_kg": 10.5, "source": "a"},
        {"co2e_kg": -3.2, "source": "b"},
    ],
    "context": {"table_name": "emissions", "row_count_hint": 2},
}

SUGGEST_PAYLOAD = {
    "table": {
        "name": "emissions",
        "description": "facility emissions records",
        "columns": [
            {"name": "co2e_kg", "type": "float"},
            {"name": "recorded_at", "type": "timestamp"},
        ],
        "row_count": 1200,
    },
}


def _validate_verdict() -> str:
    return json.dumps(
        {
            "results": [
                {"index": 0, "passed": True, "explanation": "ok"},
                {"index": 1, "passed": False, "explanation": "negative co2e"},
            ]
        }
    )


def _suggest_verdict() -> str:
    return json.dumps(
        {
            "suggestions": [
                {
                    "prompt": "co2e_kg must be non-negative",
                    "rule_type": "nl_check",
                    "rationale": "emissions cannot be negative",
                    "suggested_severity": "error",
                    "confidence": 0.95,
                }
            ]
        }
    )


# ── dq.validate ──────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_dq_validate_returns_completed_with_fail(django_store, cfg):
    """A rule with a failing row completes with status='fail' + row details."""
    from ai.engine_runtime import dispatch_task

    with _stub_llm(_validate_verdict()):
        data = dispatch_task("dq.validate", VALIDATE_PAYLOAD, instance_id="carbon")

    assert data.get("status") == "completed", data
    results = (data.get("result") or {}).get("results")
    assert isinstance(results, list) and len(results) == 1, data
    rule = results[0]
    assert rule["rule_id"] == "r1", data
    assert rule["status"] == "fail", data  # row index 1 fails
    details = rule["details"]
    assert len(details) == 2, data  # positionally indexed by row
    assert details[0] == {"passed": True, "explanation": "ok"}, data
    assert details[1] == {"passed": False, "explanation": "negative co2e"}, data


@pytest.mark.django_db(transaction=True)
def test_dq_validate_all_rows_pass(django_store, cfg):
    """A rule satisfied by every row completes with status='pass'."""
    from ai.engine_runtime import dispatch_task

    verdict = json.dumps(
        {
            "results": [
                {"index": 0, "passed": True, "explanation": "ok"},
                {"index": 1, "passed": True, "explanation": "ok"},
            ]
        }
    )
    with _stub_llm(verdict):
        data = dispatch_task("dq.validate", VALIDATE_PAYLOAD, instance_id="carbon")

    assert data.get("status") == "completed", data
    rule = (data.get("result") or {}).get("results")[0]
    assert rule["status"] == "pass", data
    assert all(d["passed"] for d in rule["details"]), data


@pytest.mark.django_db(transaction=True)
def test_dq_validate_missing_verdict_indices_fail_open(django_store, cfg):
    """Rows absent from the LLM verdict are treated as failed (never a pass)."""
    from ai.engine_runtime import dispatch_task

    verdict = json.dumps({"results": [{"index": 0, "passed": True, "explanation": "ok"}]})
    with _stub_llm(verdict):
        data = dispatch_task("dq.validate", VALIDATE_PAYLOAD, instance_id="carbon")

    assert data.get("status") == "completed", data
    rule = (data.get("result") or {}).get("results")[0]
    assert rule["status"] == "fail", data
    assert len(rule["details"]) == 2, data
    assert rule["details"][1]["passed"] is False, data


@pytest.mark.django_db(transaction=True)
def test_dq_validate_llm_outage_is_fail_visible(django_store, cfg):
    """An LLM outage yields pulse_unavailable/llm_unavailable — no fake verdict."""
    from ai.engine_runtime import dispatch_task

    with patch("ai.engine.llm.router.route_chat", side_effect=RuntimeError("no key")):
        data = dispatch_task("dq.validate", VALIDATE_PAYLOAD, instance_id="carbon")

    assert data.get("status") == "pulse_unavailable", data
    assert data.get("error", {}).get("code") == "llm_unavailable", data


@pytest.mark.django_db(transaction=True)
def test_dq_validate_unparseable_verdict_skips_rule(django_store, cfg):
    """An unparseable verdict degrades that rule to skipped_unavailable."""
    from ai.engine_runtime import dispatch_task

    with _stub_llm("this is not json"):
        data = dispatch_task("dq.validate", VALIDATE_PAYLOAD, instance_id="carbon")

    assert data.get("status") == "completed", data
    rule = (data.get("result") or {}).get("results")[0]
    assert rule["rule_id"] == "r1", data
    assert rule["status"] == "skipped_unavailable", data
    assert rule["details"] == [], data


@pytest.mark.django_db(transaction=True)
def test_dq_validate_empty_inputs_is_noop(django_store, cfg):
    """No rules or no rows -> completed with an empty results list."""
    from ai.engine_runtime import dispatch_task

    data = dispatch_task(
        "dq.validate", {"rules": [], "rows": [], "context": {}}, instance_id="carbon"
    )

    assert data.get("status") == "completed", data
    assert (data.get("result") or {}).get("results") == [], data


# ── dq.suggest ───────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_dq_suggest_returns_completed(django_store, cfg):
    """A valid suggestion payload completes with the full suggestion shape."""
    from ai.engine_runtime import dispatch_task

    with _stub_llm(_suggest_verdict()):
        data = dispatch_task("dq.suggest", SUGGEST_PAYLOAD, instance_id="carbon")

    assert data.get("status") == "completed", data
    suggestions = (data.get("result") or {}).get("suggestions")
    assert isinstance(suggestions, list) and len(suggestions) == 1, data
    suggestion = suggestions[0]
    assert suggestion["prompt"] == "co2e_kg must be non-negative", data
    assert suggestion["rule_type"] == "nl_check", data
    assert suggestion["rationale"], data
    assert suggestion["suggested_severity"] == "error", data
    assert suggestion["confidence"] == 0.95, data


@pytest.mark.django_db(transaction=True)
def test_dq_suggest_confidence_is_coerced_and_clamped(django_store, cfg):
    """Confidence is coerced to float and clamped to [0.0, 1.0]."""
    from ai.engine_runtime import dispatch_task

    verdict = json.dumps(
        {
            "suggestions": [
                {
                    "prompt": "p1",
                    "rule_type": "nl_check",
                    "rationale": "r",
                    "suggested_severity": "error",
                    "confidence": 5.0,
                },
                {
                    "prompt": "p2",
                    "rule_type": "nl_check",
                    "rationale": "r",
                    "suggested_severity": "info",
                    "confidence": -1.0,
                },
                {
                    "prompt": "p3",
                    "rule_type": "nl_check",
                    "rationale": "r",
                    "suggested_severity": "wat",
                    "confidence": "high",
                },
            ]
        }
    )
    with _stub_llm(verdict):
        data = dispatch_task("dq.suggest", SUGGEST_PAYLOAD, instance_id="carbon")

    assert data.get("status") == "completed", data
    suggestions = (data.get("result") or {}).get("suggestions")
    assert suggestions[0]["confidence"] == 1.0, data
    assert suggestions[1]["confidence"] == 0.0, data
    # Uncoercible confidence -> neutral 0.5; invalid severity -> "warn".
    assert suggestions[2]["confidence"] == 0.5, data
    assert suggestions[2]["suggested_severity"] == "warn", data


@pytest.mark.django_db(transaction=True)
def test_dq_suggest_llm_outage_is_fail_visible(django_store, cfg):
    """An LLM outage yields pulse_unavailable/llm_unavailable — no fake rules."""
    from ai.engine_runtime import dispatch_task

    with patch("ai.engine.llm.router.route_chat", side_effect=RuntimeError("no key")):
        data = dispatch_task("dq.suggest", SUGGEST_PAYLOAD, instance_id="carbon")

    assert data.get("status") == "pulse_unavailable", data
    assert data.get("error", {}).get("code") == "llm_unavailable", data


@pytest.mark.django_db(transaction=True)
def test_dq_suggest_unparseable_verdict_is_fail_visible(django_store, cfg):
    """An unparseable suggestion payload is fail-visible, never fabricated."""
    from ai.engine_runtime import dispatch_task

    with _stub_llm("this is not json"):
        data = dispatch_task("dq.suggest", SUGGEST_PAYLOAD, instance_id="carbon")

    assert data.get("status") == "pulse_unavailable", data
    assert data.get("error", {}).get("code") == "llm_unavailable", data
