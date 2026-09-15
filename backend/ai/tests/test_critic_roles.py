"""P4-07 — the S4 critic's three roles are explicit and the LLM critique is
never framed as a security control.

Locks in the reframing contract:
- ``CRITIC_SYSTEM_PROMPT`` is a plausibility/quality reviewer, not security.
- The module docstring names the three roles (boundary / deterministic / LLM).
- The deterministic hard veto (unconfirmed mutation) still holds.
"""

from __future__ import annotations

import ai.engine.cognition.turn.critic as m
from ai.engine.cognition.turn.critic import (
    CRITIC_SYSTEM_PROMPT,
    CriticWitness,
    _rules_only_verdict,
)


def test_llm_critic_prompt_is_not_framed_as_security():
    prompt = CRITIC_SYSTEM_PROMPT.lower()
    assert "security" not in prompt
    assert "safety" not in prompt
    assert "plausibility" in prompt


def test_llm_critic_prompt_names_alternatives():
    assert "alternative" in CRITIC_SYSTEM_PROMPT.lower()


def test_module_docstring_names_three_roles():
    doc = (m.__doc__ or "").lower()
    assert "boundary" in doc
    assert "deterministic" in doc
    assert ("plausibility" in doc) or ("alternative" in doc)


def test_critic_class_docstring_not_security():
    assert "security" not in CriticWitness.__doc__.lower()


def test_deterministic_veto_still_holds():
    assert _rules_only_verdict(["unconfirmed_mutation"]).verdict == "veto"


def test_review_docstring_reframed():
    assert "safety" not in CriticWitness.review.__doc__.lower()
