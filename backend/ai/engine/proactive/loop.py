"""
Proactive Loop — the main orchestration that ties everything together.

Called periodically by the cognition scheduler, it:
  1. Evaluates all triggers against live data
  2. Applies suppression (cooldown, deduplication)
  3. Assembles context for fired triggers
  4. Generates scheduled insights (daily briefing, etc.)
  5. Delivers everything through the appropriate channels
  6. Expires stale insights
"""
import json
import logging
from datetime import datetime

from ai.engine.core.config import get_settings
from ai.engine.core.models import Instance

logger = logging.getLogger("pulse.proactive.loop")


async def run_proactive_evaluation(db, instance: Instance) -> dict:
    """
    Main proactive evaluation — called per instance by the cognition scheduler.
    Returns a summary dict for status reporting.
    """
    settings = get_settings()
    if not settings.KG_PROACTIVE_ENABLED:
        return {"status": "disabled"}

    instance_id = instance.id
    host_db_url = instance.host_db_url
    summary = {
        "instance_id": instance_id,
        "triggers_evaluated": 0,
        "triggers_fired": 0,
        "insights_delivered": 0,
        "insights_expired": 0,
        "errors": [],
    }

    try:
        # 1) Evaluate triggers
        from ai.engine.proactive.trigger_evaluator import evaluate_triggers
        results = await evaluate_triggers(db, instance_id, host_db_url)
        summary["triggers_evaluated"] = len(results)

        # 2) Apply suppression — deduplication
        from ai.engine.proactive.suppression import deduplicate_results
        fired_results = deduplicate_results(results, settings.KG_PROACTIVE_DEDUP_WINDOW_MINUTES)
        summary["triggers_fired"] = len(fired_results)

        # 3) For each fired trigger: assemble context, deliver
        from ai.engine.proactive.trigger_registry import get_trigger, record_fire
        from ai.engine.proactive.context_assembler import assemble_context
        from ai.engine.proactive.delivery import deliver_insight

        for tr in fired_results:
            try:
                trigger = await get_trigger(db, tr.trigger_id)
                if not trigger:
                    continue

                # Assemble context
                context = await assemble_context(
                    db, trigger, tr, instance_id, host_db_url
                )

                # Build insight
                insight_data = {
                    "insight_type": f"{tr.category}_alert",
                    "severity": tr.severity,
                    "title": f"{tr.trigger_name}: {tr.detail[:80]}",
                    "narrative": context.get("narrative", tr.detail),
                    "context": context,
                    "recommended_actions": context.get("recommended_actions", []),
                    "trigger_id": tr.trigger_id,
                }

                group_id = getattr(tr, "_group_id", None)
                await deliver_insight(db, instance_id, insight_data, tr.trigger_id, group_id)
                await record_fire(db, tr.trigger_id)
                summary["insights_delivered"] += 1

            except Exception as e:
                logger.warning(f"Error processing trigger {tr.trigger_id}: {e}")
                summary["errors"].append(str(e))

        # 4) Expire stale insights
        from ai.engine.proactive.delivery import expire_stale_insights
        expired = await expire_stale_insights(db, instance_id)
        summary["insights_expired"] = expired

    except Exception as e:
        logger.error(f"Proactive evaluation failed for {instance_id}: {e}")
        summary["errors"].append(str(e))

    return summary


async def run_daily_briefing(db, instance: Instance) -> dict:
    """
    Generate and deliver a daily briefing for an instance.
    Should be called once per day at the configured briefing hour.
    """
    settings = get_settings()
    if not settings.KG_PROACTIVE_ENABLED:
        return {"status": "disabled"}

    instance_id = instance.id
    summary = {"instance_id": instance_id, "delivered": False}

    try:
        from ai.engine.proactive.insight_generator import generate_daily_briefing
        briefing = await generate_daily_briefing(db, instance_id)

        if briefing:
            from ai.engine.proactive.delivery import deliver_insight
            await deliver_insight(db, instance_id, briefing)
            summary["delivered"] = True
            summary["title"] = briefing["title"]

    except Exception as e:
        logger.error(f"Daily briefing failed for {instance_id}: {e}")
        summary["error"] = str(e)

    return summary
