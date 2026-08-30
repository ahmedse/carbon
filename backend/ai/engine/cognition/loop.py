"""
Conscious cognition loop — continuous monitoring, pattern detection, and wisdom synthesis.

Goes beyond scheduled health checks: the loop tracks its own state, detects patterns
across snapshots and memories, synthesizes insights, and builds intelligence over time.
"""
import asyncio
import json
import logging

from ai.engine.core.clock import utcnow
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ai.engine.core.config import get_settings

logger = logging.getLogger("pulse.cognition.loop")

_scheduler: AsyncIOScheduler | None = None

# ── Loop state (in-process, queryable via API) ──
_loop_state: dict = {
    "started_at": None,
    "running": False,
    "tasks": {},       # task_name → {last_run, last_duration_ms, last_status, run_count, next_run}
    "cycle_count": 0,  # total tick count
}


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def get_loop_status() -> dict:
    """Return current loop status for the API."""
    scheduler = get_scheduler()
    status = {**_loop_state, "scheduler_running": scheduler.running}

    # Enrich with next-run times from APScheduler
    if scheduler.running:
        for job in scheduler.get_jobs():
            if job.id in status["tasks"]:
                status["tasks"][job.id]["next_run"] = (
                    job.next_run_time.isoformat() if job.next_run_time else None
                )

    return status


async def trigger_task(task_name: str) -> dict:
    """Manually trigger a cognition task by name."""
    task_map = {
        "health_check": _run_health_check,
        "freshness_check": _run_freshness_check,
        "error_check": _run_error_check,
        "snapshot": _run_snapshot,
        "schema_drift": _run_schema_drift,
        "synthesize": _run_synthesis,
        "reflect": _run_reflection,
        "decay": _run_memory_decay,
        "episodic_decay": _run_episodic_decay,
        "preference_learning": _run_preference_learning,
        "proactive_eval": _run_proactive_eval,
        "daily_briefing": _run_daily_briefing,
        "query_patterns": _run_query_patterns,
        "self_reflect": _run_self_reflection,
        "prompt_refine": _run_prompt_refine,
        "consolidation": _run_consolidation,
        "skill_admission": _run_skill_admission,
        "kg_seeding": _run_kg_seeding,
    }

    fn = task_map.get(task_name)
    if not fn:
        return {"error": f"Unknown task: {task_name}", "available": list(task_map.keys())}

    try:
        await fn()
        return {"status": "ok", "task": task_name, "triggered_at": utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Manual trigger of {task_name} failed: {e}")
        return {"status": "error", "task": task_name, "error": str(e)}


# ── Tracked task wrapper ──────────────────────────────────────────────────

async def _tracked(task_name: str, fn):
    """Wrap a task function with state tracking, error handling, and Studio push."""
    from ai.engine.cognition.notifier import broadcast_cognition_event

    start = utcnow()
    status = "ok"

    # Notify Studio subscribers that a task started
    await _broadcast_all_instances("task_started", task_name)

    try:
        await fn()
    except Exception as e:
        status = f"error: {e}"
        logger.error(f"Task {task_name} failed: {e}")
    finally:
        elapsed = int((utcnow() - start).total_seconds() * 1000)
        task_state = _loop_state["tasks"].setdefault(task_name, {"run_count": 0})
        task_state["last_run"] = start.isoformat()
        task_state["last_duration_ms"] = elapsed
        task_state["last_status"] = status
        task_state["run_count"] += 1
        _loop_state["cycle_count"] += 1
        logger.debug(f"Task {task_name} completed in {elapsed}ms — {status}")

        # Durable best-effort ledger (Phase D) — upsert by task name.
        await _persist_sweep_run(task_name, start, elapsed, status)

        # Notify Studio subscribers of completion
        event = "task_completed" if status == "ok" else "task_failed"
        await _broadcast_all_instances(event, task_name, {
            "duration_ms": elapsed,
            "status": status,
            "run_count": task_state["run_count"],
        })


async def _persist_sweep_run(task_name: str, start, elapsed_ms: int, status: str) -> None:
    """Best-effort upsert of a CognitionSweepRun row for ``task_name``.

    Never raises — sweep persistence must not fail the loop itself.  Uses the
    Store seam (``AI_STORE_BACKEND``) so it works identically under the
    ``inmemory`` and ``django`` backends.
    """
    try:
        from ai.store import first, get_store
        from ai.models.core import CognitionSweepRun

        factory = get_store().get_session_factory()
        async with factory() as db:
            rows = await db.select(CognitionSweepRun, ("task_name", task_name))
            row = first(rows)
            error = None if status == "ok" else status
            if row is not None:
                row.last_run = start
                row.last_status = status
                row.last_duration_ms = elapsed_ms
                row.run_count += 1
                row.last_error = error
            else:
                db.add(CognitionSweepRun(
                    task_name=task_name,
                    last_run=start,
                    last_status=status,
                    last_duration_ms=elapsed_ms,
                    run_count=1,
                    last_error=error,
                ))
            await db.commit()
    except Exception as e:  # pragma: no cover - best-effort ledger
        logger.warning("Failed to persist sweep run for %s: %s", task_name, e)


async def _broadcast_all_instances(event: str, task_name: str, data: dict | None = None):
    """Broadcast a cognition event to Studio subscribers for all active instances."""
    from ai.engine.cognition.notifier import broadcast_cognition_event, _studio_subscribers

    # Send to all instances that have Studio subscribers
    for instance_id in list(_studio_subscribers.keys()):
        await broadcast_cognition_event(instance_id, event, task_name, data)


# ── Helper: iterate active instances ──────────────────────────────────────

async def _for_each_instance(callback):
    """Run an async callback(db, instance) for every active instance."""
    from ai.store import get_store
    from ai.engine.core.models import Instance

    factory = get_store().get_session_factory()
    async with factory() as db:
        instances = await db.select(Instance, ("status", "active"))
        for instance in instances:
            try:
                await callback(db, instance)
            except Exception as e:
                logger.error(f"Task failed for {instance.name}: {e}")


# ── Task implementations ──────────────────────────────────────────────────

async def _run_health_check():
    from ai.engine.cognition.monitors import check_model_health
    await _tracked("health_check", lambda: _for_each_instance(check_model_health))


async def _run_freshness_check():
    from ai.engine.cognition.monitors import check_data_freshness
    await _tracked("freshness_check", lambda: _for_each_instance(check_data_freshness))


async def _run_error_check():
    from ai.engine.cognition.monitors import check_failed_jobs
    await _tracked("error_check", lambda: _for_each_instance(check_failed_jobs))


async def _run_snapshot():
    from ai.engine.cognition.state import take_snapshot
    await _tracked("snapshot", lambda: _for_each_instance(take_snapshot))


async def _run_schema_drift():
    from ai.engine.cognition.monitors import check_schema_drift
    await _tracked("schema_drift", lambda: _for_each_instance(check_schema_drift))


async def _run_synthesis():
    """Synthesize insights from recent data — the core 'thinking' task."""
    from ai.engine.cognition.synthesis import synthesize_insights
    await _tracked("synthesize", lambda: _for_each_instance(synthesize_insights))


async def _run_reflection():
    """Reflect on accumulated insights — consolidate, supersede, prune."""
    from ai.engine.cognition.synthesis import reflect_on_insights
    await _tracked("reflect", lambda: _for_each_instance(reflect_on_insights))


async def _run_memory_decay():
    """Decay unused memories — lower confidence on stale facts."""
    from ai.engine.cognition.synthesis import decay_stale_memories
    await _tracked("decay", lambda: _for_each_instance(decay_stale_memories))


async def _run_episodic_decay():
    """Apply time-based decay to episodic memory events — reduce relevance scores
    for events past their half-life window and archive those below threshold."""
    from ai.engine.memory.episodic import EpisodicMemory

    async def _decay_one(db, instance):
        em = EpisodicMemory(db_session=db)
        archived = await em.apply_decay(
            instance_id=instance.id,
            host_user_id=None,
        )
        if archived:
            logger.info(
                "Episodic decay: archived %d episodes for %s", archived, instance.name,
            )

    await _tracked("episodic_decay", lambda: _for_each_instance(_decay_one))


async def _run_preference_learning():
    """Learn user behaviour patterns from conversation history."""
    from ai.engine.cognition.synthesis import learn_user_preferences
    await _tracked("preference_learning", lambda: _for_each_instance(learn_user_preferences))


async def _run_proactive_eval():
    """Evaluate proactive triggers — detect noteworthy conditions."""
    from ai.engine.proactive.loop import run_proactive_evaluation
    await _tracked("proactive_eval", lambda: _for_each_instance(run_proactive_evaluation))


# ── PR-14: Distillation / promotion / decay ──────────────────────────────

async def _run_distillation():
    """Daily episodic→semantic distillation — distill facts from recent turns."""
    from ai.engine.cognition.distill.episodic_to_semantic import run_distillation
    await _tracked("distill", lambda: _for_each_instance(run_distillation))


async def _run_fact_promotion():
    """Weekly promotion — promote sustained high-confidence facts to confirmed."""
    from ai.engine.cognition.distill.promotion import run_promotion
    await _tracked("promote_facts", lambda: _for_each_instance(run_promotion))


async def _run_fact_decay():
    """Monthly fact decay — reduce confidence on unused learned facts."""
    from ai.engine.cognition.distill.decay import run_decay
    await _tracked("decay_facts", lambda: _for_each_instance(run_decay))


async def _run_daily_briefing():
    """Generate daily briefings for all instances."""
    from ai.engine.proactive.loop import run_daily_briefing
    await _tracked("daily_briefing", lambda: _for_each_instance(run_daily_briefing))


async def _run_query_patterns():
    """Detect recurring query patterns and suggest report automation."""
    from ai.engine.cognition.synthesis import detect_recurring_queries
    await _tracked("query_patterns", lambda: _for_each_instance(detect_recurring_queries))


async def _run_self_reflection():
    """PR-15: Per-user weekly self-reflection — summary insight per host user."""
    from ai.engine.cognition.synthesis import run_self_reflection
    await _tracked("self_reflect", lambda: _for_each_instance(run_self_reflection))


async def _run_consolidation() -> None:
    """P4.2: Nightly consolidation sweep for all active instances."""
    from ai.engine.cognition.consolidation import _run_consolidation_for_all_instances
    await _tracked("consolidation", _run_consolidation_for_all_instances)


async def _run_skill_admission() -> None:
    """P4.3: Nightly skill admission gate for all active instances."""
    from ai.engine.skills.gate import _run_skill_admission_for_all_instances
    await _tracked("skill_admission", _run_skill_admission_for_all_instances)


async def _run_kg_seeding() -> None:
    """P4.4b: Seed KG nodes from trajectory user messages."""
    from ai.engine.cognition.kg_seeding import seed_nodes_from_trajectories

    async def _seed_one(db, instance):
        created = await seed_nodes_from_trajectories(db, instance.id)
        if created:
            await db.commit()
            logger.info(
                "kg_seeding: %d new nodes for %s", created, instance.name,
            )

    await _tracked("kg_seeding", lambda: _for_each_instance(_seed_one))


async def _run_prompt_refine() -> None:
    """Check qualifying instances for prompt improvement.

    Triggered every 6 hours. For each active instance with >=10 new user
    messages since the last refinement, run the synthesize→optimize loop.
    The optimizer already handles score comparison and activation internally.
    """
    logger.info("prompt_refine: scanning instances for prompt improvement candidates")

    async def _refine_instance(db, instance) -> None:
        import json
        from datetime import timedelta
        from ai.engine.core.models import Conversation, Message, PromptVersion
        from ai.engine.llm.prompt_synthesizer import synthesize_system_prompt, _prompt_cache

        instance_id = instance.id
        instance_name = instance.name
        display_name = instance.display_name

        def _one(rows):
            return rows[0] if rows else None

        def _latest_synth(rows):
            return max(rows, key=lambda v: v.synthesized_at) if rows else None

        def _max_score(rows):
            return max(
                rows,
                key=lambda v: v.score if v.score is not None else float("-inf"),
            ) if rows else None

        try:
            # ── 0. Resolve previous A/B candidate (if any) ───────────────────
            # A candidate is a PromptVersion with improvement_round=0 and
            # is_active=False — it was staged 6h ago for 20% traffic testing.
            cand_rows = await db.select(
                PromptVersion,
                ("instance_id", instance_id),
                ("is_active", False),
                ("improvement_round", 0),
            )
            old_candidate = _latest_synth(cand_rows)

            if old_candidate is not None:
                # Compare candidate vs current active
                active_rows = await db.select(
                    PromptVersion,
                    ("instance_id", instance_id),
                    ("is_active", True),
                )
                current_active = _one(active_rows)

                if current_active is not None and old_candidate.score is not None:
                    active_score = current_active.score or 0.0
                    candidate_score = old_candidate.score

                    if candidate_score > active_score:
                        # Promote candidate → active, demote current active
                        current_active.is_active = False
                        old_candidate.is_active = True
                        old_candidate.improvement_round = (
                            (current_active.improvement_round or 0) + 1
                        )
                        await db.commit()
                        logger.info(
                            f"prompt_refine: PROMOTED candidate {old_candidate.id[:8]} "
                            f"for {instance_name} (score {candidate_score:.4f} > active {active_score:.4f})"
                        )
                    else:
                        # Discard underperforming candidate
                        await db.delete(old_candidate)
                        await db.commit()
                        logger.info(
                            f"prompt_refine: DISCARDED candidate {old_candidate.id[:8]} "
                            f"for {instance_name} (score {candidate_score:.4f} <= active {active_score:.4f})"
                        )
                else:
                    # No active version — promote candidate directly
                    old_candidate.is_active = True
                    old_candidate.improvement_round = 1
                    await db.commit()
                    logger.info(
                        f"prompt_refine: PROMOTED candidate {old_candidate.id[:8]} "
                        f"(no active version) for {instance_name}"
                    )

            # ── 1. Count user messages since last refinement ────────────────
            all_versions = await db.select(PromptVersion, ("instance_id", instance_id))
            last_version = _latest_synth(all_versions)

            if last_version is not None and last_version.synthesized_at is not None:
                since = last_version.synthesized_at
            else:
                since = utcnow() - timedelta(hours=24)

            # Message has no instance_id — resolve conversation IDs first, then count.
            conv_rows = await db.select(Conversation, ("instance_id", instance_id))
            conv_ids = [c.id for c in conv_rows]
            count_result = await db.aggregate(
                Message,
                {"count": ("Count", "id")},
                ("conversation_id__in", conv_ids),
                ("role", "user"),
                ("timestamp__gte", since),
            )
            msg_count = int(count_result.get("count") or 0)

            if msg_count < 10:
                logger.info(
                    f"prompt_refine: {instance_name} has {msg_count} "
                    f"new messages (<10 threshold) — skipping"
                )
                return

            logger.info(
                f"prompt_refine: {instance_name} has {msg_count} new "
                f"messages — running optimization"
            )

            # Record old score for comparison
            old_score = last_version.score if last_version is not None else 0.0

            # 2. Parse instance config for description / domain
            config_data = instance.config or {}
            if isinstance(config_data, str):
                config_data = json.loads(config_data)
            description = config_data.get("description", "")
            domain = config_data.get("domain", "")

            # 3. Run synthesize→optimize
            best_prompt = await synthesize_system_prompt(
                instance_name=instance_name,
                display_name=display_name,
                description=description,
                domain=domain,
                optimize=True,
                db=db,
                instance_id=instance_id,
            )

            if not best_prompt:
                logger.warning(f"prompt_refine: empty result for {instance_name}")
                return

            # 4. Compare scores and notify
            active_rows = await db.select(
                PromptVersion,
                ("instance_id", instance_id),
                ("is_active", True),
            )
            active = _max_score(active_rows)
            new_score = active.score if active else 0.0

            improvement_pct = (
                (new_score - old_score) / old_score * 100
                if old_score > 0
                else 100.0
            )

            logger.info(
                f"prompt_refine: {instance_name} "
                f"old_score={old_score:.4f} → new_score={new_score:.4f} "
                f"({improvement_pct:+.1f}%)"
            )

            # ── 4b. Save current active ID, then demote winner → candidate ──
            # The optimizer activates the winner.  We demote it to a candidate
            # so build_chat_prompt can route 20% traffic to it for real-world
            # A/B testing.  The old active version stays live for the other 80%.
            save_rows = await db.select(
                PromptVersion,
                ("instance_id", instance_id),
                ("is_active", True),
            )
            new_winner = _one(save_rows)
            saved_active_id = None

            if new_winner is not None:
                # Find the version that was active BEFORE this optimization run
                prev_rows = await db.select(
                    PromptVersion,
                    ("instance_id", instance_id),
                    ("is_active", False),
                )
                prev_rows = [v for v in prev_rows if v.id != new_winner.id]
                prev_active = _latest_synth(prev_rows)

                # Demote winner to candidate
                new_winner.is_active = False
                new_winner.improvement_round = 0  # candidate marker
                await db.commit()

                # Restore previously active version
                if prev_active is not None:
                    prev_active.is_active = True
                    await db.commit()
                    saved_active_id = prev_active.id

                # Invalidate in-memory cache so next chat call re-synthesizes
                # using the restored active version, not the candidate.
                _prompt_cache.pop(instance_name, None)

                logger.info(
                    f"prompt_refine: STAGED candidate {new_winner.id[:8]} "
                    f"(score={new_winner.score:.4f}) for A/B testing in {instance_name}"
                    f"{' — restored active ' + saved_active_id[:8] if saved_active_id else ''}"
                )

            await broadcast_cognition_event(
                instance_id=instance_id,
                event="task_completed",
                task_name="prompt_refine",
                data={
                    "improvement_pct": round(improvement_pct, 1),
                    "old_score": round(old_score, 4),
                    "new_score": round(new_score, 4),
                },
            )

        except Exception as exc:
            logger.error(f"prompt_refine failed for {instance_name}: {exc}", exc_info=True)

    await _for_each_instance(_refine_instance)


# ── Scheduler lifecycle ───────────────────────────────────────────────────

def _write_heartbeat() -> None:
    """Write a liveness timestamp to the supervisor heartbeat file.

    This is the signal the Docker healthcheck watches: as long as the file is
    fresh, the scheduler process is alive and its event loop is ticking.  A
    wedged loop (e.g. a blocked await) stops updating the file and Docker marks
    the container unhealthy → restart policy recovers it.

    Never raises — a healthcheck must not crash the scheduler.
    """
    settings = get_settings()
    path = settings.COGNITION_HEARTBEAT_FILE
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"{utcnow().isoformat()}\n")
    except OSError as exc:
        logger.warning("Failed to write heartbeat to %s: %s", path, exc)


async def _run_heartbeat() -> None:
    """Scheduler job: refresh the liveness heartbeat every tick."""
    _write_heartbeat()


def start_scheduler():
    """Start the conscious cognition loop with all jobs."""
    settings = get_settings()
    scheduler = get_scheduler()

    if scheduler.running:
        logger.info("Scheduler already running")
        return

    # ── Supervisor liveness heartbeat (Phase H) — registered first so the
    #    healthcheck has a signal immediately after startup. ──
    _write_heartbeat()
    scheduler.add_job(
        _run_heartbeat, "interval",
        seconds=settings.COGNITION_HEARTBEAT_INTERVAL,
        id="heartbeat", replace_existing=True,
    )

    # ── Monitoring tasks (existing) ──
    scheduler.add_job(
        _run_health_check, "interval",
        seconds=settings.COGNITION_HEALTH_INTERVAL,
        id="health_check", replace_existing=True,
    )
    scheduler.add_job(
        _run_freshness_check, "interval",
        seconds=settings.COGNITION_FRESHNESS_INTERVAL,
        id="freshness_check", replace_existing=True,
    )
    scheduler.add_job(
        _run_error_check, "interval",
        seconds=settings.COGNITION_ERROR_CHECK_INTERVAL,
        id="error_check", replace_existing=True,
    )
    scheduler.add_job(
        _run_snapshot, "interval",
        seconds=settings.COGNITION_SNAPSHOT_INTERVAL,
        id="snapshot", replace_existing=True,
    )
    scheduler.add_job(
        _run_schema_drift, "interval",
        seconds=settings.COGNITION_SCHEMA_DRIFT_INTERVAL,
        id="schema_drift", replace_existing=True,
    )

    # ── Intelligence tasks (new) ──
    scheduler.add_job(
        _run_synthesis, "interval",
        seconds=settings.COGNITION_SYNTHESIS_INTERVAL,
        id="synthesize", replace_existing=True,
    )
    scheduler.add_job(
        _run_reflection, "interval",
        seconds=settings.COGNITION_REFLECTION_INTERVAL,
        id="reflect", replace_existing=True,
    )
    scheduler.add_job(
        _run_memory_decay, "interval",
        seconds=settings.COGNITION_DECAY_INTERVAL,
        id="decay", replace_existing=True,
    )

    # ── Episodic decay (B4) — time-based relevance decay + archive ──
    scheduler.add_job(
        _run_episodic_decay, "interval",
        seconds=settings.COGNITION_EPISODIC_DECAY_INTERVAL,
        id="episodic_decay", replace_existing=True,
    )

    # ── User preference learning ──
    scheduler.add_job(
        _run_preference_learning, "interval",
        seconds=86400,  # once per day
        id="preference_learning", replace_existing=True,
    )

    # ── Proactive Intelligence (Stage 13) ──
    scheduler.add_job(
        _run_proactive_eval, "interval",
        seconds=settings.KG_PROACTIVE_EVAL_INTERVAL,
        id="proactive_eval", replace_existing=True,
    )
    scheduler.add_job(
        _run_daily_briefing, "cron",
        hour=settings.KG_PROACTIVE_BRIEFING_HOUR,
        id="daily_briefing", replace_existing=True,
    )

    # ── Query pattern detection (weekly) ──
    scheduler.add_job(
        _run_query_patterns, "interval",
        seconds=604800,  # once per week
        id="query_patterns", replace_existing=True,
    )

    # ── PR-14: Distillation / promotion / decay ──
    scheduler.add_job(
        _run_distillation, "interval",
        seconds=settings.COGNITION_DISTILLATION_INTERVAL,
        id="distill", replace_existing=True,
    )
    scheduler.add_job(
        _run_fact_promotion, "interval",
        seconds=settings.COGNITION_PROMOTION_INTERVAL,
        id="promote_facts", replace_existing=True,
    )
    scheduler.add_job(
        _run_fact_decay, "interval",
        seconds=settings.COGNITION_FACT_DECAY_INTERVAL,
        id="decay_facts", replace_existing=True,
    )

    # ── PR-15: Weekly self-reflection per host user ──
    scheduler.add_job(
        _run_self_reflection, "interval",
        seconds=settings.COGNITION_SELF_REFLECT_INTERVAL,
        id="self_reflect", replace_existing=True,
    )

    # ── Prompt self-improvement (every 6h) ──
    scheduler.add_job(
        _run_prompt_refine, "interval",
        seconds=21600,  # every 6 hours
        id="prompt_refine", replace_existing=True,
    )

    # ── P4.2: Consolidation sweep (nightly at 3:00 AM) ──
    scheduler.add_job(
        _run_consolidation, "cron",
        hour=3, minute=0, id="consolidation_sweep",
        replace_existing=True,
    )

    # ── P4.3: Skill admission gate (nightly at 3:30 AM) ──
    # Runs after the 3:00 AM consolidation sweep so newly-drafted pending
    # skills are admitted the same night.
    scheduler.add_job(
        _run_skill_admission, "cron",
        hour=3, minute=30, id="skill_admission",
        replace_existing=True,
    )

    # ── P4.4b: KG node seeding (nightly at 4:30 AM) ──
    scheduler.add_job(
        _run_kg_seeding, "cron",
        hour=4, minute=30, id="kg_seeding",
        replace_existing=True,
    )

    scheduler.start()

    _loop_state["started_at"] = utcnow().isoformat()
    _loop_state["running"] = True

    # Initialize task state entries
    for job in scheduler.get_jobs():
        _loop_state["tasks"].setdefault(job.id, {
            "run_count": 0,
            "last_run": None,
            "last_status": "pending",
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        })

    logger.info(
        f"Conscious cognition loop started with {len(scheduler.get_jobs())} tasks: "
        + ", ".join(j.id for j in scheduler.get_jobs())
    )


def stop_scheduler():
    """Shut down the scheduler gracefully."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        _loop_state["running"] = False
        logger.info("Cognition loop stopped")
