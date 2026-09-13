"""PATH 3 — WORKER mutation attempts.

A worker subagent is read-only by design (ADR-001).  Every call_host_api
mutation — however obfuscated — is cancelled by readonly_worker_hook before it
reaches the executor.
"""

from __future__ import annotations

import pytest

from ai.engine.agent.guardrails import readonly_worker_hook
from ai.tests.redteam import mutations
from ai.tests.redteam.conftest import make_hook_ctx, run_hook


@pytest.mark.parametrize("case", mutations.WORKER, ids=[c["id"] for c in mutations.WORKER])
def test_worker_mutation_is_blocked(case):
    ctx = make_hook_ctx("call_host_api", case["tool_args"], is_worker=True)
    result = run_hook(readonly_worker_hook, ctx)

    assert result.action == "cancel", (
        f"{case['id']}: expected cancel, got {result.action!r} "
        f"reason={result.reason!r}"
    )
    assert case["expects"] in result.flags, (
        f"{case['id']}: expected {case['expects']!r} in {result.flags}"
    )


def test_worker_readonly_tool_still_passes():
    """A genuinely read-only worker tool is not blocked (control)."""
    ctx = make_hook_ctx("query_knowledge_graph", {"query": "asset T-3"}, is_worker=True)
    result = run_hook(readonly_worker_hook, ctx)
    assert result.action == "pass"


def test_non_worker_context_does_not_trigger_worker_hook():
    """The same mutation is not blocked by this hook outside worker context."""
    ctx = make_hook_ctx(
        "call_host_api",
        {"api_name": "create_record", "_method": "POST", "body": {"v": 1}},
        is_worker=False,
    )
    result = run_hook(readonly_worker_hook, ctx)
    assert result.action == "pass"
