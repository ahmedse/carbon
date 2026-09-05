"""Phase 9 — Model policy / turn profiles.

Verifies ``model_for_profile()`` routes each turn profile to the right model
override (or None for the instance default), and that the "verify" profile
falls back to the "investigate" model when no dedicated verify model is set.
"""
from types import SimpleNamespace
from unittest.mock import patch


def test_model_for_profile_returns_none_for_default_profiles():
    """interactive / extract / unknown profiles must return None (instance default)."""
    from ai.engine.llm.router import model_for_profile

    assert model_for_profile("interactive") is None
    assert model_for_profile(None) is None
    assert model_for_profile("extract") is None
    assert model_for_profile("unknown") is None


def test_model_for_profile_returns_investigate_model_when_set():
    """investigate profile must return LLM_INVESTIGATE_MODEL when configured."""
    from ai.engine.llm.router import model_for_profile

    with patch(
        "ai.engine.llm.router.get_settings",
        return_value=SimpleNamespace(
            LLM_INVESTIGATE_MODEL="anthropic/claude-sonnet-4-5",
            LLM_VERIFY_MODEL="",
        ),
    ):
        assert model_for_profile("investigate") == "anthropic/claude-sonnet-4-5"


def test_model_for_profile_returns_none_when_investigate_unset():
    """investigate profile must return None (instance default) when unset."""
    from ai.engine.llm.router import model_for_profile

    with patch(
        "ai.engine.llm.router.get_settings",
        return_value=SimpleNamespace(
            LLM_INVESTIGATE_MODEL="",
            LLM_VERIFY_MODEL="",
        ),
    ):
        assert model_for_profile("investigate") is None


def test_verify_profile_falls_back_to_investigate():
    """verify profile must fall back to the investigate model when unset."""
    from ai.engine.llm.router import model_for_profile

    with patch(
        "ai.engine.llm.router.get_settings",
        return_value=SimpleNamespace(
            LLM_INVESTIGATE_MODEL="anthropic/claude-sonnet-4-5",
            LLM_VERIFY_MODEL="",
        ),
    ):
        assert model_for_profile("verify") == "anthropic/claude-sonnet-4-5"


def test_verify_profile_prefers_verify_model_when_set():
    """verify profile must prefer LLM_VERIFY_MODEL when configured."""
    from ai.engine.llm.router import model_for_profile

    with patch(
        "ai.engine.llm.router.get_settings",
        return_value=SimpleNamespace(
            LLM_INVESTIGATE_MODEL="anthropic/claude-sonnet-4-5",
            LLM_VERIFY_MODEL="anthropic/claude-haiku-4-5",
        ),
    ):
        assert model_for_profile("verify") == "anthropic/claude-haiku-4-5"
