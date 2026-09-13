"""Shared harness for the P1-17 red-team suite.

Small, offline helpers that wrap the fail-closed guards under test.  No live
LLM, no host connection, no DB session is created by these helpers — each test
module supplies exactly the context its guard needs.
"""

from __future__ import annotations

import asyncio
from typing import Any


def make_draft(text: str = "", tool_calls: list[dict] | None = None) -> Any:
    from ai.engine.cognition.turn.witnesses import DraftResult

    return DraftResult(text=text, tool_calls=tool_calls or [], claimed_citations=[])


def make_retrieval() -> Any:
    from ai.engine.cognition.turn.witnesses import RetrievalResult

    return RetrievalResult()


def review_draft(
    draft: Any,
    *,
    is_mutation: bool = False,
    confirmation_token: str | None = None,
    dry_run: bool = False,
) -> Any:
    """Run the S4 critic rules-tier (LLM critic disabled) and return the verdict."""
    from ai.engine.cognition.turn.critic import CriticWitness

    return asyncio.run(
        CriticWitness().review(
            draft,
            make_retrieval(),
            is_mutation=is_mutation,
            dry_run=dry_run,
            confirmation_token=confirmation_token,
            enable_llm_critic=False,
        )
    )


def make_hook_ctx(
    tool_name: str,
    tool_args: dict,
    *,
    is_worker: bool = False,
    agent_role: str = "orchestrator",
) -> Any:
    from ai.engine.agent.guardrails import HookContext

    return HookContext(
        tool_name=tool_name,
        tool_args=tool_args,
        instance_id="redteam-instance",
        host_user_id="redteam-user",
        is_worker=is_worker,
        agent_role=agent_role,
    )


def run_hook(hook: Any, ctx: Any) -> Any:
    return asyncio.run(hook(ctx))


def make_skill(
    *,
    kind: str,
    body: str,
    signature: str = "{}",
    description: str = "",
    name: str = "redteam_skill",
) -> Any:
    """Build an in-memory Skill model object (no DB session required)."""
    from ai.engine.core.models import Skill

    return Skill(
        id="redteam-skill",
        instance_id="redteam-instance",
        name=name,
        description=description,
        signature=signature,
        body=body,
        kind=kind,
        status="draft",
        author_user_id="redteam-user",
        gate_status="pending",
    )
