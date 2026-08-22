"""TurnPipelineRunner — orchestrates the six-witness pipeline for one turn.

BE-01-5: Spine is the default path. Runs S1→S2→S3→S4→S5→S6 sequentially,
writing one TurnLedgerRow per stage. PulseAgent.think() has been deleted.
"""
import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

from ai.engine.core.config import get_settings
from ai.engine.cognition.turn.witnesses import (
    TurnLedger,
)

logger = logging.getLogger("pulse.cognition.turn.runner")

# Lazy import — avoids circular dependency with notifier
broadcast_run_event = None


async def _write_trajectory_own_session(run_id: str) -> None:
    """Write the trajectory on a DEDICATED session (fire-and-forget safe).

    Must not reuse the turn session: the caller may close it while this
    background task is still running, which triggers an asyncpg
    "another operation is in progress" race (seen in evals, where the
    harness closes the session immediately after the turn).
    """
    from ai.store import get_store
    from ai.engine.cognition.trajectory import write_trajectory

    factory = get_store().get_session_factory()
    async with factory() as traj_db:
        await write_trajectory(run_id, traj_db)


class TurnPipelineRunner:
    """Runs the six-witness pipeline for every turn — the only codepath.

    BE-01-5: PulseAgent.think() has been deleted.
    """

    def __init__(
        self,
        llm_client=None,
        knowledge_store=None,
        memory_manager=None,
        executor=None,
        db=None,              # Store session for S6 ledger writes
    ):
        self.llm_client = llm_client
        self.knowledge_store = knowledge_store
        self.memory_manager = memory_manager
        self.executor = executor
        self.db = db
        # Curated tool set exposed to the S3 planner when an executor is
        # wired. Mutation/confirmation tools (create_dq_rule) plus read tools
        # that ground answers; host-API/misc tools are excluded so the planner
        # never wastes turns on endpoints it cannot reach from chat.
        self._draft_tools: list[dict] | None = None
        if executor is not None:
            try:
                from ai.engine.agent.tools import get_tool_definitions

                allow = {
                    "create_dq_rule", "search_knowledge", "get_entity_details",
                    "list_my_capabilities", "plan_task",
                    "edit_plan", "approve_plan",
                    "web_research", "export_document",
                }
                self._draft_tools = [
                    d for d in get_tool_definitions()
                    if d.get("function", {}).get("name") in allow
                ]
            except Exception:  # noqa: BLE001 - tools are best-effort, never fatal
                logger.warning("Could not load draft tool definitions", exc_info=True)
                self._draft_tools = None

    async def run(
        self,
        instance_id: str,
        conversation_id: str,
        user_message: str,
        host_user_id: str | None = None,
        page_context: str = "",
        conversation_history: list[dict] | None = None,
        instance_config: dict | None = None,
        user_info: dict | None = None,
        progress_callback=None,
        stream_callback=None,
        model: str | None = None,
        # Phase 22-A — per-user default chat temperature (0.0-2.0); None
        # keeps the draft witness's built-in default (0.3).
        temperature: float | None = None,
    ) -> tuple:
        """Execute one turn. Returns (AgentResponse, TurnLedger)."""
        from ai.engine.agent.reasoning import AgentResponse

        settings = get_settings()
        turn_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        t0 = time.monotonic()

        ledger = TurnLedger(
            turn_id=turn_id,
            instance_id=instance_id,
            host_user_id=host_user_id,
            conversation_id=conversation_id,
            user_message=user_message,
            created_at=created_at,
        )

        # ── P3.4: Per-run token budget ────────────────────────────────────
        from ai.engine.agent.budget import BudgetTracker
        budget = None
        if self.db is not None:
            budget = BudgetTracker(
                run_id=turn_id,
                total_budget=settings.RUN_TOKEN_BUDGET_DEFAULT,
                db_session=self.db,
            )

        # ── Six-witness pipeline (always active) ──────────────────────────
        total_tokens = 0
        total_llm_calls = 0
        logger.info(f"[{turn_id[:8]}] Pipeline start  user={host_user_id}'")

        from ai.engine.cognition.notifier import broadcast_run_event as _broadcast_run
        await _broadcast_run(instance_id, "run.started", {
            "run_id": turn_id,
            "conversation_id": conversation_id,
            "host_user_id": host_user_id,
            "user_message": user_message,
        })

        # S1 — Salience
        s1_start = time.monotonic()
        await _broadcast_run(instance_id, "run.step.started", {
            "run_id": turn_id,
            "stage": "s1_salience",
            "stage_index": 0,
        })
        from ai.engine.cognition.turn.salience import SalienceWitness
        salience_witness = SalienceWitness()
        salience = await salience_witness.assess(user_message)
        ledger.salience = salience
        s1_latency = (time.monotonic() - s1_start) * 1000
        await _broadcast_run(instance_id, "run.step.completed", {
            "run_id": turn_id,
            "stage": "s1_salience",
            "stage_index": 0,
            "latency_ms": s1_latency,
        })
        await self._write_ledger_row(
            turn_id, instance_id, conversation_id, host_user_id,
            "salience", 0, {"domain": salience.domain, "route": salience.route, "weight": salience.weight},
            s1_latency, verdict="pass",
        )

        # S2 — Retrieval
        s2_start = time.monotonic()
        await _broadcast_run(instance_id, "run.step.started", {
            "run_id": turn_id,
            "stage": "s2_retrieval",
            "stage_index": 1,
        })
        from ai.engine.cognition.turn.retrieve import RetrievalWitness
        retrieve_witness = RetrievalWitness(
            knowledge_store=self.knowledge_store,
            memory_manager=self.memory_manager,
        )
        retrieval = await retrieve_witness.retrieve(
            instance_id, conversation_id, user_message, user_info,
        )
        ledger.retrieval = retrieval
        s2_latency = retrieval.retrieval_latency_ms
        await _broadcast_run(instance_id, "run.step.completed", {
            "run_id": turn_id,
            "stage": "s2_retrieval",
            "stage_index": 1,
            "latency_ms": s2_latency,
        })
        await self._write_ledger_row(
            turn_id, instance_id, conversation_id, host_user_id,
            "retrieval", 1, {"chunks": len(retrieval.knowledge_chunks)},
            s2_latency, verdict="pass",
        )

        # ── P3.2: Orchestrator fan-out gate (after S2, before PR-20) ──────
        # If an orchestrator agent is active and the user message warrants
        # parallel decomposition, fan out to workers and synthesize results.
        fan_out_result = None
        if settings.AGENT_ORCHESTRATOR_ENABLED and self.db is not None:
            try:
                fan_out_result = await self._try_fan_out(
                    instance_id=instance_id,
                    conversation_id=conversation_id,
                    user_message=user_message,
                    host_user_id=host_user_id,
                    page_context=page_context,
                    conversation_history=conversation_history,
                    instance_config=instance_config,
                    user_info=user_info,
                    retrieval=retrieval,
                    turn_id=turn_id,
                    budget_tracker=budget,
                )
            except Exception:
                logger.exception("Fan-out attempt failed; falling back to multi-step / single-pass")

        if fan_out_result is not None:
            # ── Fan-out path: skip S3→S5 and PR-20, go straight to S6 ─────
            final_text = fan_out_result.final_text
            total_tokens = fan_out_result.total_tokens
            total_llm_calls = 1  # orchestrator synthesis call

            # Record fan-out ledger fields
            ledger.fan_out_used = True
            ledger.fan_out_worker_count = len(fan_out_result.worker_ids)
            ledger.fan_out_worker_ids = fan_out_result.worker_ids
            ledger.fan_out_artifact_refs = fan_out_result.artifact_refs
            ledger.fan_out_total_tokens = fan_out_result.total_tokens
            ledger.fan_out_latency_ms = fan_out_result.total_latency_ms

            logger.info(
                "TurnPipelineRunner: fan-out complete turn=%s workers=%d succeeded=%d",
                turn_id[:8], fan_out_result.worker_count, fan_out_result.succeeded_count,
            )

            # S6 — Final ledger summary
            s6_start = time.monotonic()
            total_latency = (time.monotonic() - t0) * 1000
            s6_latency = (time.monotonic() - s6_start) * 1000

            # P3.4: Consume budget for fan-out LLM calls + log snapshot
            if budget is not None:
                await budget.consume(total_tokens)
                ledger.budget_snapshot = budget.snapshot()
                ledger.budget_exceeded = budget.exceeded

            await self._write_ledger_row(
                turn_id, instance_id, conversation_id, host_user_id,
                "final", 5,
                {
                    "total_latency_ms": total_latency,
                    "total_tokens": total_tokens,
                    "total_llm_calls": total_llm_calls,
                    "verdict": "pass",
                    "fan_out_path": True,
                    "fan_out_worker_count": fan_out_result.worker_count,
                    "fan_out_artifact_count": len(fan_out_result.artifact_refs),
                },
                s6_latency, verdict="pass",
            )
            await self.db.commit()

            ledger.final_response = final_text[:500]
            ledger.total_latency_ms = total_latency
            ledger.total_tokens = total_tokens
            ledger.total_llm_calls = total_llm_calls

            response = AgentResponse(
                text=final_text,
                sources_cited=[],
                tools_used=[],
                confidence=0.8,
                total_tokens=total_tokens,
                llm_calls=total_llm_calls,
                model="",
            )
            await _broadcast_run(instance_id, "run.completed", {
                "run_id": turn_id,
                "total_latency_ms": total_latency,
                "total_tokens": total_tokens,
                "total_llm_calls": total_llm_calls,
                "fan_out_path": True,
            })
            return response, ledger

        # ── PR-20: Multi-step planning gate (after S2, before S3) ──────────
        # If a multi-step plan is needed, run ReActLoop instead of single-pass S3→S5.
        react_result = None
        if settings.KG_MULTI_STEP_ENABLED and self.db is not None:
            try:
                react_result = await self._try_multi_step_plan(
                    instance_id=instance_id,
                    conversation_id=conversation_id,
                    user_message=user_message,
                    host_user_id=host_user_id,
                    page_context=page_context,
                    conversation_history=conversation_history,
                    instance_config=instance_config,
                    user_info=user_info,
                    retrieval=retrieval,
                    progress_callback=progress_callback,
                    stream_callback=stream_callback,
                )
            except Exception:
                logger.exception("Multi-step plan attempt failed; falling back to single-pass")

        if react_result is not None:
            # ── ReAct path: skip S3→S5 single-pass, go straight to S6 ──────
            final_text = react_result.final_response
            total_tokens = 0  # ReAct loop tracks its own token usage
            total_llm_calls = react_result.replans_used + len(react_result.step_results)

            for i, sr in enumerate(react_result.step_results):
                await self._write_ledger_row(
                    turn_id, instance_id, conversation_id, host_user_id,
                    f"react_step_{i}", 2 + i,
                    {
                        "step_id": sr.step_id,
                        "intent": sr.intent,
                        "critic_verdict": sr.critic_verdict,
                        "executed": sr.executed,
                        "error": sr.error,
                    },
                    0.0,  # latency tracked per-step in ReActLoop
                    verdict=sr.critic_verdict,
                    flags=sr.critic_flags,
                )

            logger.info(
                "TurnPipelineRunner: ReAct loop complete steps=%d replans=%d succeeded=%s",
                len(react_result.step_results), react_result.replans_used, react_result.succeeded,
            )

            # S6 — Final ledger summary
            s6_start = time.monotonic()
            total_latency = (time.monotonic() - t0) * 1000
            s6_latency = (time.monotonic() - s6_start) * 1000
            await self._write_ledger_row(
                turn_id, instance_id, conversation_id, host_user_id,
                "final", 5,
                {
                    "total_latency_ms": total_latency,
                    "total_tokens": total_tokens,
                    "total_llm_calls": total_llm_calls,
                    "critic_verdict": "pass" if react_result.succeeded else "veto",
                    "react_path": True,
                },
                s6_latency, verdict="pass" if react_result.succeeded else "veto",
            )
            await self.db.commit()

            # P4.1: Write trajectory (fire-and-forget, own session)
            _ = asyncio.ensure_future(_write_trajectory_own_session(turn_id))

            ledger.final_response = final_text[:500]
            ledger.total_latency_ms = total_latency
            ledger.total_tokens = total_tokens
            ledger.total_llm_calls = total_llm_calls

            response = AgentResponse(
                text=final_text,
                sources_cited=[],
                tools_used=[],
                confidence=0.8 if react_result.succeeded else 0.3,
                total_tokens=total_tokens,
                llm_calls=total_llm_calls,
                model="",
            )
            await _broadcast_run(instance_id, "run.completed", {
                "run_id": turn_id,
                "total_latency_ms": total_latency,
                "total_tokens": total_tokens,
                "total_llm_calls": total_llm_calls,
            })
            return response, ledger

        # ── Existing single-pass S3→S5 path ────────────────────────────────

        # S3 — Draft (LLM tool-use loop via DraftWitness)
        s3_start = time.monotonic()
        await _broadcast_run(instance_id, "run.step.started", {
            "run_id": turn_id,
            "stage": "s3_draft",
            "stage_index": 2,
        })
        from ai.engine.cognition.turn.draft import DraftWitness
        draft_witness = DraftWitness(
            llm_client=self.llm_client,
            knowledge_store=self.knowledge_store,
            memory_manager=self.memory_manager,
            executor=self.executor,
        )
        # Build system prompt — LLM-synthesized
        config = instance_config or {}
        from ai.engine.llm.prompts import build_chat_prompt
        system_prompt = await build_chat_prompt(
            instance_name=config.get("display_name", "Unknown System"),
            system_description=config.get("description", ""),
            relevant_knowledge=(
                retrieval.knowledge_chunks[0]["content"]
                if retrieval.knowledge_chunks else "No knowledge loaded yet."
            ),
            relevant_memories=(
                retrieval.memory_chunks[0]["content"]
                if retrieval.memory_chunks else "No memories available."
            ),
            page_context=page_context or "unknown",
            user_info=user_info,
            persona=config.get("persona"),
            api_catalog=config.get("api_catalog"),
            navigation_routes=config.get("navigation_routes"),
            domain_topics=config.get("domain_topics"),
            instance_config=config,
            conversation_id=conversation_id,
            instance_id=instance_id,
        )

        # Tool-aware drafting: when an executor is wired, expose the curated
        # tool set to the LLM and append the anti-fabrication grounding rules.
        draft_tools = self._draft_tools if self.executor is not None else None
        if draft_tools:
            system_prompt = (
                f"{system_prompt}\n\n"
                "GROUNDING RULES — follow them exactly:\n"
                "- You have tools available. Use them to do real work instead "
                "of guessing. When a tool matches the user's request, call it "
                "right away — do not answer in prose instead of using it, and "
                "do not say you cannot run/execute tasks.\n"
                "- PLAN FIRST, CONVERT ON CONFIRMATION: when the user asks you "
                "to plan, study, research, audit, orchestrate, or 'make a "
                "multi-agent workflow' for something, DO NOT call plan_task "
                "and DO NOT create any task yet. Instead, think it through and "
                "PROPOSE a plan directly in chat: a short numbered list of "
                "steps, each naming the tool or agent that would do it and the "
                "deliverable it produces. Then invite the user to discuss, add, "
                "remove, or reword steps. This proposal lives only in the chat "
                "— it is NOT a task yet. A plain question (e.g. 'what is the "
                "GHG Protocol?') should just be answered directly, with no "
                "plan proposal at all.\n"
                "- Iterate the proposal in chat as the user gives feedback. "
                "Re-present the revised numbered plan after each change and ask "
                "whether it is settled.\n"
                "- ONLY when the user explicitly confirms the plan is settled "
                "(e.g. 'settled', 'go', 'convert it to a task', 'create the "
                "task', 'make it a task', 'yes build it'), call plan_task with "
                "the final agreed brief. That single call turns the agreed plan "
                "into a real pending_approval task. Never call plan_task before "
                "this confirmation, and never auto-create a task on detection.\n"
                "- The plan_task tool DRAFTS a plan and returns a plan id in "
                "pending_approval; it does not execute anything. After calling "
                "it, tell the user the plan id and that it awaits approval in "
                "the Tasks panel. Never claim a task ran or completed.\n"
                "- After plan_task has created the task, if the user asks to "
                "change a step of that task, use edit_plan. If the user asks to "
                "run/approve it, use approve_plan. Never approve or run without "
                "the user's confirmation.\n"
                "- NEVER claim an action succeeded (e.g. 'rule created') unless "
                "a tool result confirms it.\n"
                "- The create_dq_rule tool only STAGES a proposal — it returns "
                "a confirmation execution. Nothing is written until the user "
                "confirms. Tell the user a confirmation button appeared; do "
                "NOT say the rule was created.\n"
                "- Use web_research when the task needs internet facts (e.g. a "
                "study comparing carbon standards) — cite its results; never "
                "invent sources.\n"
                "- Use export_document to produce a downloadable Word/Excel "
                "artifact when the user wants the findings as a document; tell "
                "them the download link appeared.\n"
                "- If a tool errors, report the error plainly.\n"
                "- When the user asks what you can do, use the capability-list "
                "tool so the app can attach the matching page links as small "
                "buttons under your reply."
            )
        draft = await draft_witness.draft(
            instance_id=instance_id,
            conversation_id=conversation_id,
            user_message=user_message,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            instance_config=instance_config,
            user_info=user_info,
            budget_tracker=budget,
            model=model,
            tools=draft_tools,
            temperature=temperature,
        )
        ledger.draft = draft
        total_tokens += draft.tokens_used
        total_llm_calls += 1  # S3 is one direct route_chat() call

        # Phase 21-A: carry the prompt/completion split + resolved model for
        # per-generation usage attribution (written once at completion).
        ledger.prompt_tokens += draft.prompt_tokens
        ledger.completion_tokens += draft.completion_tokens
        ledger.model_used = draft.model_used or ledger.model_used

        # P3.4: Consume budget for S3 draft LLM call
        if budget is not None:
            await budget.consume(draft.tokens_used)

        s3_latency = (time.monotonic() - s3_start) * 1000
        await _broadcast_run(instance_id, "run.step.completed", {
            "run_id": turn_id,
            "stage": "s3_draft",
            "stage_index": 2,
            "latency_ms": s3_latency,
        })
        await self._write_ledger_row(
            turn_id, instance_id, conversation_id, host_user_id,
            "draft", 2,
            {"text_len": len(draft.text), "tool_calls": len(draft.tool_calls), "confidence": draft.confidence},
            s3_latency, tokens_used=draft.tokens_used, model_used=draft.model_used, verdict="pass",
        )

        # S4 — Critic (rules-tier + LLM-tier when flags raised)
        s4_start = time.monotonic()
        await _broadcast_run(instance_id, "run.step.started", {
            "run_id": turn_id,
            "stage": "s4_critic",
            "stage_index": 3,
        })
        from ai.engine.cognition.turn.critic import CriticWitness
        critic_witness = CriticWitness()
        critic = await critic_witness.review(
            draft,
            retrieval,
            enable_llm_critic=True,
            instance_id=instance_id,
            conversation_id=conversation_id,
            user_message=user_message,
        )
        ledger.critic = critic
        s4_latency = (time.monotonic() - s4_start) * 1000
        await _broadcast_run(instance_id, "run.step.completed", {
            "run_id": turn_id,
            "stage": "s4_critic",
            "stage_index": 3,
            "latency_ms": s4_latency,
        })
        await self._write_ledger_row(
            turn_id, instance_id, conversation_id, host_user_id,
            "critic", 3,
            {
                "verdict": critic.verdict,
                "flags": critic.flags,
                "rewritten": bool(critic.rewritten_text),
                "llm_critic_enabled": True,
            },
            s4_latency, verdict=critic.verdict, flags=critic.flags,
        )

        # Use rewritten text if critic provided one
        final_text = critic.rewritten_text if critic.rewritten_text else draft.text

        # S5 — Execute (real parallel tool dispatch + streaming)
        s5_start = time.monotonic()
        await _broadcast_run(instance_id, "run.step.started", {
            "run_id": turn_id,
            "stage": "s5_execute",
            "stage_index": 4,
        })
        from ai.engine.cognition.turn.execute import ExecuteWitness
        from ai.engine.agent.guardrails import build_default_pipeline

        hook_pipeline = build_default_pipeline()
        hook_ctx_defaults = {
            "instance_id": instance_id,
            "conversation_id": conversation_id,
            "host_user_id": host_user_id,
            "run_id": turn_id,
            "agent_role": "orchestrator",
            "is_worker": False,
            "instance_config": instance_config,
        }
        execute_witness = ExecuteWitness(
            executor=self.executor,
            hook_pipeline=hook_pipeline,
            hook_ctx_defaults=hook_ctx_defaults,
            run_id=turn_id,
            instance_id=instance_id,
        )
        execution = await execute_witness.execute(
            text=final_text,
            tool_calls=draft.tool_calls,
            stream_callback=stream_callback,
            progress_callback=progress_callback,
        )
        ledger.execution = execution
        s5_latency = execution.execution_latency_ms
        await _broadcast_run(instance_id, "run.step.completed", {
            "run_id": turn_id,
            "stage": "s5_execute",
            "stage_index": 4,
            "latency_ms": s5_latency,
        })
        await self._write_ledger_row(
            turn_id, instance_id, conversation_id, host_user_id,
            "execution", 4,
            {
                "streamed": execution.streamed,
                "tools_executed": len(execution.completed_tools),
                "per_tool_latency_ms": execution.per_tool_latency_ms,
            },
            s5_latency, verdict="pass",
        )

        # S6 — Final ledger summary
        s6_start = time.monotonic()
        await _broadcast_run(instance_id, "run.step.started", {
            "run_id": turn_id,
            "stage": "s6_finalize",
            "stage_index": 5,
        })
        total_latency = (time.monotonic() - t0) * 1000
        s6_latency = (time.monotonic() - s6_start) * 1000

        # P3.4: Log budget snapshot to ledger
        if budget is not None:
            ledger.budget_snapshot = budget.snapshot()
            ledger.budget_exceeded = budget.exceeded

        await self._write_ledger_row(
            turn_id, instance_id, conversation_id, host_user_id,
            "final", 5,
            {
                "total_latency_ms": total_latency,
                "total_tokens": total_tokens,
                "total_llm_calls": total_llm_calls,
                "critic_verdict": critic.verdict,
            },
            s6_latency, verdict=critic.verdict,
        )
        await self.db.commit()

        # P4.1: Write trajectory (fire-and-forget, own session)
        _ = asyncio.ensure_future(_write_trajectory_own_session(turn_id))

        ledger.final_response = final_text[:500]
        ledger.total_latency_ms = total_latency
        ledger.total_tokens = total_tokens
        ledger.total_llm_calls = total_llm_calls

        logger.info(
            "TurnPipelineRunner: turn=%s domain=%s route=%s critic=%s latency=%.0fms tokens=%d",
            turn_id[:8], salience.domain, salience.route, critic.verdict,
            total_latency, total_tokens,
        )

        response = AgentResponse(
            text=final_text,
            sources_cited=draft.claimed_citations,
            tools_used=draft.tool_calls,
            confidence=draft.confidence,
            total_tokens=total_tokens,
            llm_calls=total_llm_calls,
            model=draft.model_used,
        )

        await _broadcast_run(instance_id, "run.step.completed", {
            "run_id": turn_id,
            "stage": "s6_finalize",
            "stage_index": 5,
            "latency_ms": s6_latency,
        })
        await _broadcast_run(instance_id, "run.completed", {
            "run_id": turn_id,
            "total_latency_ms": total_latency,
            "total_tokens": total_tokens,
            "total_llm_calls": total_llm_calls,
        })

        return response, ledger

    async def _write_ledger_row(
        self, turn_id, instance_id, conversation_id, host_user_id,
        stage, stage_index, payload, latency_ms,
        tokens_used=None, model_used=None, verdict=None, flags=None,
    ):
        """Write one row to turn_ledger via the LedgerWitness."""
        from ai.engine.cognition.turn.ledger import LedgerWitness
        ledger_witness = LedgerWitness()
        await ledger_witness.record_stage(
            db=self.db,
            turn_id=turn_id,
            instance_id=instance_id,
            conversation_id=conversation_id,
            host_user_id=host_user_id,
            stage=stage,
            stage_index=stage_index,
            payload=payload,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            model_used=model_used,
            verdict=verdict,
            flags=flags,
        )

    async def _try_multi_step_plan(
        self,
        instance_id: str,
        conversation_id: str,
        user_message: str,
        host_user_id: str | None,
        page_context: str,
        conversation_history: list[dict] | None,
        instance_config: dict | None,
        user_info: dict | None,
        retrieval,  # RetrievalResult
        progress_callback=None,
        stream_callback=None,
    ):
        """PR-20: Attempt multi-step planning. Returns ReActResult or None.

        None means "fall through to single-pass S3→S5" — the caller should
        treat this as "no multi-step needed."
        """
        from ai.engine.cognition.plan.planner import SkillAwarePlanner
        from ai.engine.cognition.plan.loop import ReActLoop
        from ai.engine.cognition.turn.draft import DraftWitness
        from ai.engine.cognition.turn.critic import CriticWitness
        from ai.engine.skills.registry import SkillRegistry
        from ai.engine.llm.prompts import build_chat_prompt
        from ai.engine.core.config import get_settings

        settings = get_settings()

        # Build skill registry from self.db
        skill_registry = SkillRegistry(self.db)

        # Build planner
        planner = SkillAwarePlanner(
            llm_client=self.llm_client,
            model=settings.LLM_MODEL,
        )

        plan = await planner.decompose(
            utterance=user_message,
            skill_registry=skill_registry,
            instance_id=instance_id,
            user_id=host_user_id or "",
        )

        # Only activate ReAct loop for multi-step plans or skill-sourced plans
        if plan.source == "single_step" and len(plan.steps) <= 1:
            logger.debug("TurnPipelineRunner: single-step plan, skipping ReAct loop")
            return None

        logger.info(
            "TurnPipelineRunner: activating ReAct loop source=%s steps=%d",
            plan.source, len(plan.steps),
        )

        # Build system prompt — LLM-synthesized
        config = instance_config or {}
        system_prompt = await build_chat_prompt(
            instance_name=config.get("display_name", "Unknown System"),
            system_description=config.get("description", ""),
            relevant_knowledge=(
                retrieval.knowledge_chunks[0]["content"]
                if retrieval.knowledge_chunks else "No knowledge loaded yet."
            ),
            relevant_memories=(
                retrieval.memory_chunks[0]["content"]
                if retrieval.memory_chunks else "No memories available."
            ),
            page_context=page_context or "unknown",
            user_info=user_info,
            persona=config.get("persona"),
            api_catalog=config.get("api_catalog"),
            navigation_routes=config.get("navigation_routes"),
            domain_topics=config.get("domain_topics"),
            instance_config=config,
            conversation_id=conversation_id,
            instance_id=instance_id,
        )

        # Build witnesses
        draft_witness = DraftWitness(
            llm_client=self.llm_client,
            knowledge_store=self.knowledge_store,
            memory_manager=self.memory_manager,
            executor=self.executor,
        )
        critic_witness = CriticWitness()

        loop = ReActLoop(
            draft_witness=draft_witness,
            critic_witness=critic_witness,
            llm_client=self.llm_client,
            knowledge_store=self.knowledge_store,
            memory_manager=self.memory_manager,
            db=self.db,
        )

        react_result = await loop.run(
            plan=plan,
            instance_id=instance_id,
            conversation_id=conversation_id,
            user_message=user_message,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            instance_config=instance_config,
            user_info=user_info,
            retrieval=retrieval,
            progress_callback=progress_callback,
            stream_callback=stream_callback,
            host_user_id=host_user_id,
        )

        return react_result

    async def _try_fan_out(
        self,
        instance_id: str,
        conversation_id: str,
        user_message: str,
        host_user_id: str | None,
        page_context: str,
        conversation_history: list[dict] | None,
        instance_config: dict | None,
        user_info: dict | None,
        retrieval,
        turn_id: str,
        budget_tracker=None,  # P3.4: BudgetTracker for per-run token limits
    ):
        """P3.2: Attempt orchestrator fan-out. Returns _FanOutResponse or None.

        None means "fall through to PR-20 / single-pass" — the caller should
        treat this as "fan-out not applicable."
        """
        from dataclasses import dataclass

        @dataclass
        class _FanOutResponse:
            final_text: str
            total_tokens: int
            total_latency_ms: float
            worker_ids: list[str]
            worker_count: int
            succeeded_count: int
            artifact_refs: list[dict]

        from ai.engine.agent.registry import AgentRegistry
        from ai.engine.agent.workers import WorkerPool, WorkerTask
        from ai.engine.llm.router import route_chat

        settings = get_settings()

        # Look up orchestrator agent
        registry = AgentRegistry(self.db)
        await registry.seed_defaults(instance_id)

        orchestrator = await registry.get_agent(instance_id, "orchestrator")
        if orchestrator is None or not orchestrator.is_active:
            logger.debug("TurnPipelineRunner: no active orchestrator for instance=%s", instance_id)
            return None

        # Check orchestrator has valid workers
        workers = await registry.get_workers_for(orchestrator.id)
        active_workers = [(a, h) for a, h in workers if a.is_active]
        if not active_workers:
            logger.debug("TurnPipelineRunner: orchestrator has no active workers")
            return None

        # Build orchestrator system prompt
        config = instance_config or {}
        from ai.engine.llm.prompts import build_chat_prompt
        system_prompt = await build_chat_prompt(
            instance_name=config.get("display_name", "Unknown System"),
            system_description=config.get("description", ""),
            relevant_knowledge=(
                retrieval.knowledge_chunks[0]["content"]
                if retrieval.knowledge_chunks else "No knowledge loaded yet."
            ),
            relevant_memories=(
                retrieval.memory_chunks[0]["content"]
                if retrieval.memory_chunks else "No memories available."
            ),
            page_context=page_context or "unknown",
            user_info=user_info,
            persona=config.get("persona"),
            api_catalog=config.get("api_catalog"),
            navigation_routes=config.get("navigation_routes"),
            domain_topics=config.get("domain_topics"),
            instance_config=config,
            conversation_id=conversation_id,
            instance_id=instance_id,
        )

        # Orchestrator decision call: should we fan out?
        orchestrator_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": (
                "You are the orchestrator agent. Your role is to decide whether this "
                "user request would benefit from parallel decomposition across worker "
                "agents. If the request has multiple independent sub-questions or "
                "requires diverse expertise, call delegate_to_workers. If it's a simple "
                "single-focus question, respond with a brief text reply (no tool call) "
                "and the pipeline will fall through to single-pass processing."
            )},
        ]
        if conversation_history:
            orchestrator_messages.extend(conversation_history[-6:])
        orchestrator_messages.append({"role": "user", "content": user_message})

        # Only give orchestrator the fan-out tools
        from ai.engine.agent.tools import STATIC_TOOL_DEFINITIONS
        orch_tools = [
            t for t in STATIC_TOOL_DEFINITIONS
            if t.get("function", {}).get("name") in ("delegate_to_workers", "synthesize_worker_results")
        ]

        decision = await route_chat(
            task="chat",
            instance_id=instance_id,
            conversation_id=conversation_id,
            messages=orchestrator_messages,
            tools=orch_tools,
            db=self.db,
        )

        tool_calls = decision.get("tool_calls") or []
        if not tool_calls:
            # Orchestrator chose not to fan out — fall through
            logger.debug("TurnPipelineRunner: orchestrator chose not to fan out")
            return None

        # Process delegate_to_workers tool call
        delegate_call = None
        for tc in tool_calls:
            if tc.get("function", {}).get("name") == "delegate_to_workers":
                delegate_call = tc
                break

        if delegate_call is None:
            return None

        import json as _json
        try:
            delegate_args = _json.loads(delegate_call["function"]["arguments"])
        except (_json.JSONDecodeError, KeyError, TypeError):
            logger.warning("TurnPipelineRunner: invalid delegate_to_workers args")
            return None

        worker_specs = delegate_args.get("workers", [])
        if not worker_specs:
            return None

        # Build WorkerTask list
        tasks = []
        for spec in worker_specs:
            tasks.append(WorkerTask(
                agent_role=spec.get("agent_role", ""),
                task=spec.get("task", ""),
                context_hints=spec.get("context_hints"),
            ))

        if not tasks:
            return None

        # P3.4: Allocate worker budgets and record justification
        worker_budgets = None
        if budget_tracker is not None:
            justification = delegate_args.get("justification", f"Fan-out: {len(tasks)} parallel workers")
            await budget_tracker.set_justification(justification)
            worker_budgets = budget_tracker.allocate_worker_budget(len(tasks))
            logger.info(
                "BudgetTracker: fan-out allocation workers=%d total_pool=%d per_worker=%d",
                len(tasks), sum(worker_budgets), worker_budgets[0] if worker_budgets else 0,
            )

        # Run fan-out
        pool = WorkerPool(
            llm_client=self.llm_client,
            db=self.db,
            instance_id=instance_id,
            conversation_id=conversation_id,
        )
        fan_out_result = await pool.fan_out(
            tasks=tasks,
            agent_registry=registry,
            orchestrator_id=orchestrator.id,
            system_prompt=system_prompt,
            worker_budgets=worker_budgets,
        )

        # Synthesize results
        if fan_out_result.artifact_refs:
            synthesis_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "system", "content": (
                    "You are the orchestrator. Synthesize the following worker findings "
                    "into a single coherent response to the user's original request. "
                    "Do NOT mention workers or internal mechanics — just present the "
                    "combined answer naturally.\n\n"
                    "User request: " + user_message
                )},
                {"role": "user", "content": _json.dumps(fan_out_result.artifact_refs, indent=2)},
            ]

            synthesis = await route_chat(
                task="chat",
                instance_id=instance_id,
                conversation_id=conversation_id,
                messages=synthesis_messages,
                db=self.db,
            )
            final_text = synthesis.get("content") or ""
            synth_tokens = synthesis.get("input_tokens", 0) + synthesis.get("output_tokens", 0)
        else:
            final_text = "I wasn't able to gather information from my workers. Let me try a different approach."
            synth_tokens = 0

        total_tokens = (
            decision.get("input_tokens", 0) + decision.get("output_tokens", 0)
            + fan_out_result.total_tokens
            + synth_tokens
        )

        return _FanOutResponse(
            final_text=final_text,
            total_tokens=total_tokens,
            total_latency_ms=fan_out_result.total_latency_ms,
            worker_ids=fan_out_result.worker_ids,
            worker_count=len(tasks),
            succeeded_count=fan_out_result.succeeded_count,
            artifact_refs=fan_out_result.artifact_refs,
        )
