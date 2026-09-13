"""PATH 4 — SKILL admission attempts with destructive payloads.

A draft skill carrying a dangerous body or a malformed/unknown shape must be
rejected by the admission gate's rules-only critics (harmlessness for
destructive payloads, structural for malformed JSON / unknown kind).
"""

from __future__ import annotations

import asyncio

import pytest

from ai.tests.redteam import mutations
from ai.tests.redteam.conftest import make_skill


def _run_critic(critic: str, case):
    from ai.engine.skills.gate import harmlessness_critic, structural_critic

    skill = make_skill(
        kind=case["kind"],
        body=case["body"],
        signature=case["signature"],
    )
    if critic == "harmlessness":
        return asyncio.run(harmlessness_critic(skill))
    return asyncio.run(structural_critic(skill, db=None))


@pytest.mark.parametrize("case", mutations.SKILL, ids=[c["id"] for c in mutations.SKILL])
def test_destructive_skill_is_rejected(case):
    verdict = _run_critic(case["critic"], case)

    assert verdict.passed is False, (
        f"{case['id']}: expected rejection, got flags {verdict.flags}"
    )
    assert any(case["expects"] in f for f in verdict.flags), (
        f"{case['id']}: expected {case['expects']!r} in {verdict.flags}"
    )


def test_clean_procedure_skill_passes_rules_critics():
    """Control: a benign procedure draft passes the rules-only critics."""
    from ai.engine.skills.gate import harmlessness_critic, structural_critic

    skill = make_skill(
        kind="procedure",
        body='{"steps": ["fetch", "summarize"]}',
        signature='{"in": {"type": "object"}, "out": {"type": "object"}}',
    )

    structural = asyncio.run(structural_critic(skill, db=None))
    harmless = asyncio.run(harmlessness_critic(skill))

    assert structural.passed is True, structural.flags
    assert harmless.passed is True, harmless.flags


# ── Supplementary: promotion authority is gate-only ──────────────────────


def test_skill_promotion_requires_gate_token():
    """A forged or missing promotion token fails closed (RuntimeError)."""
    from ai.engine.skills._authority import check_promotion_token

    with pytest.raises(RuntimeError):
        check_promotion_token(None)
    with pytest.raises(RuntimeError):
        check_promotion_token(object())


def test_skill_illegal_transition_is_rejected():
    """A deprecated skill cannot be re-promoted (closed transition table)."""
    from ai.engine.skills._authority import assert_allowed_transition

    with pytest.raises(ValueError):
        assert_allowed_transition("deprecated", "instance_promoted")
    with pytest.raises(ValueError):
        assert_allowed_transition("unknown_state", "instance_promoted")
