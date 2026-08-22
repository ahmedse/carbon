"""
Phase W4-D — Learning flywheel (Reflexion-style step feedback).

Feeds finalized plan-run outcomes (critic verdicts + tool outcomes + latency)
back into the SkillRegistry as learnt signals:

    Django Run/RunStep rows → outcome (success / vetoed / latency / flags)
        → SkillsStore.update_stats (skill's own learning-ledger columns)

Successful plans promote their source skill's score; vetoed/failed steps
depress it — so decomposition quality improves with use.

Mirrors the Phase D ``ai/feedback/`` pattern (capture → pipeline → learning)
but is keyed on plan-run outcomes instead of DQ events. Lives OUTSIDE the
engine core (RULE_6 — no learning inside ``engine/**``); it only *reads*
engine Skill rows through the store seam and *writes* the skill's own
learning-ledger columns (``usage_count`` / ``success_rate`` /
``avg_latency_ms`` / ``last_executed_at``).

RULE_21 is satisfied: the flywheel never writes host data and never
auto-promotes a skill's status. ``promote_on_success`` only *reports*
readiness so a caller can surface "promote?" to the user.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging

logger = logging.getLogger("carbon.ai.feedback.skill_flywheel")

# Engine instance namespace — must match ``ai.plans_service.PLAN_INSTANCE_ID``.
PLAN_INSTANCE_ID = "carbon"

# Terminal run states — the flywheel only fires after the run is final, so
# the retry loop never double-feeds mid-flight.
_TERMINAL_STATUSES = ("completed", "failed")

# RunStep status for declined / never-executed steps (not judged).
_STEP_SKIPPED = "skipped"


def _run_async(coro):
    """Run an async engine-store coroutine from a sync context.

    Mirrors ``ai.plans_service._run_async``: ``asyncio.run`` when no loop is
    running (sync tests, ``sync_to_async`` worker threads), otherwise on a
    worker thread to avoid nesting loops.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def feed_run_feedback(run_id: str, *, instance_id: str = PLAN_INSTANCE_ID) -> dict | None:
    """Feed one finalized plan run's outcome back into the SkillRegistry.

    No-ops (returns ``None``) unless the run is a skill-sourced plan in a
    terminal state (``completed``/``failed`` — retry-loop safety). On a hit,
    resolves the skill through the engine store and applies
    ``SkillsStore.update_stats`` — which only mutates the skill's own
    learning-ledger columns, never host data and never status (RULE_21).

    Returns ``{"skill_id", "skill_name", "success", "vetoed", "latency_ms",
    "updated"}``, or ``None`` when there is nothing to learn from.
    """
    from ai.models.core import Run, RunStep

    try:
        run = Run.objects.get(id=run_id)
    except Run.DoesNotExist:
        return None

    plan_json = run.plan_json or {}
    if plan_json.get("source") != "skill":
        return None
    skill_name = plan_json.get("skill_name")
    if not isinstance(skill_name, str) or not skill_name.strip():
        return None
    # Retry-loop safety: only terminal runs feed the ledger.
    if run.status not in _TERMINAL_STATUSES:
        return None

    steps = list(RunStep.objects.filter(run_id=run.id).order_by("step_index"))
    # Mirror the ReAct loop's ``succeeded`` predicate (loop.py) — every
    # executed (non-skipped) step must pass and carry no error.
    non_skipped = [s for s in steps if s.status != _STEP_SKIPPED]
    success = run.status == "completed" and all(
        s.critic_verdict in ("pass", "pass_with_flag") and not s.error
        for s in non_skipped
    )
    vetoed = sum(1 for s in steps if s.critic_verdict == "veto")
    latency_ms = run.total_latency_ms or None
    flags = [f for s in steps for f in (s.critic_flags_json or [])]

    from ai.engine.core.database import get_session_factory
    from ai.engine.skills.crud import SkillsStore

    async def _apply():
        async with get_session_factory(instance_id)() as db:
            store = SkillsStore(db)
            skill = await store.resolve_skill(instance_id, skill_name)
            if skill is None:
                return None
            # 0.0 when unmeasured — ``avg_latency_ms`` is NOT NULL in the
            # Django mirror and the EMA treats a 0 observation as "no time".
            await store.update_stats(skill.id, success, latency_ms or 0.0)
            return skill

    skill = _run_async(_apply())
    if skill is None:
        return None

    result = {
        "skill_id": skill.id,
        "skill_name": skill_name,
        "success": success,
        "vetoed": vetoed,
        "latency_ms": latency_ms,
        "updated": True,
    }
    logger.info("skill flywheel: %s (flags=%d)", result, len(flags))
    return result


def promote_on_success(
    skill_id: str,
    threshold_successes: int = 3,
    min_success_rate: float = 0.75,
    *,
    instance_id: str = PLAN_INSTANCE_ID,
) -> bool:
    """Report whether a skill has crossed the promote-ready bar.

    Read-only helper (RULE_21): never writes status. Returns True when the
    skill has enough proven successes and is not already
    ``instance_promoted``, so a caller can surface "promote?" to the user.
    """
    from ai.engine.core.database import get_session_factory
    from ai.engine.core.models import Skill

    async def _check() -> bool:
        async with get_session_factory(instance_id)() as db:
            skill = await db.get(Skill, skill_id)
            if skill is None:
                return False
            return (
                skill.usage_count >= threshold_successes
                and skill.success_rate >= min_success_rate
                and skill.status != "instance_promoted"
            )

    return _run_async(_check())
