"""PATH 1 — DIRECT mutation attempts, all vetoed by the S4 critic.

An openly state-changing tool call (non-GET call_host_api) or a
mutation-classified step must be hard-vetoed before S5 execution.
"""

from __future__ import annotations

import pytest

from ai.tests.redteam import mutations
from ai.tests.redteam.conftest import make_draft, review_draft


@pytest.mark.parametrize("case", mutations.DIRECT, ids=[c["id"] for c in mutations.DIRECT])
def test_direct_mutation_is_vetoed(case):
    verdict = review_draft(
        make_draft(tool_calls=case["tool_calls"]),
        is_mutation=case["is_mutation"],
    )

    assert verdict.verdict == "veto", (
        f"{case['id']}: expected hard veto, got {verdict.verdict!r} "
        f"with flags {verdict.flags}"
    )
    assert case["expects"] in verdict.flags, (
        f"{case['id']}: expected flag {case['expects']!r} in {verdict.flags}"
    )


def test_dry_run_preview_does_not_execute_but_records_preview_flag():
    """A preview (dry_run) of a mutation never hard-blocks, but is marked."""
    case = mutations.DIRECT[0]

    verdict = review_draft(
        make_draft(tool_calls=case["tool_calls"]),
        is_mutation=case["is_mutation"],
        dry_run=True,
    )

    assert verdict.verdict != "veto"
    assert "dry_run_preview" in verdict.flags
