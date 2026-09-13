"""PATH 2 — INDIRECT PHRASING mutation attempts.

Destructive SQL/shell is smuggled through a read-only tool's arguments
(blocked by tool_safety_hook), or the method verb is obfuscated by case
(blocked by the critic's case-insensitive mutation check).
"""

from __future__ import annotations

import pytest

from ai.engine.agent.guardrails import tool_safety_hook
from ai.tests.redteam import mutations
from ai.tests.redteam.conftest import make_draft, make_hook_ctx, review_draft, run_hook


@pytest.mark.parametrize("case", mutations.INDIRECT, ids=[c["id"] for c in mutations.INDIRECT])
def test_indirect_phrasing_is_blocked(case):
    if case["guard"] == "safety":
        ctx = make_hook_ctx(case["tool_name"], case["tool_args"])
        result = run_hook(tool_safety_hook, ctx)

        assert result.action == "cancel", (
            f"{case['id']}: expected cancel, got {result.action!r} "
            f"reason={result.reason!r}"
        )
        assert case["expects"] in result.flags, (
            f"{case['id']}: expected {case['expects']!r} in {result.flags}"
        )
    else:  # critic
        verdict = review_draft(make_draft(tool_calls=case["tool_calls"]))

        assert verdict.verdict == "veto", (
            f"{case['id']}: expected veto, got {verdict.verdict!r}"
        )
        assert case["expects"] in verdict.flags, (
            f"{case['id']}: expected {case['expects']!r} in {verdict.flags}"
        )
