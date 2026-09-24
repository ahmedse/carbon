"""S3 — Draft witness (dedicated LLM planning call).

Calls the LLM directly through route_chat() for a single planning pass.
The tool-use loop stays in ReActLoop — S3 just produces a draft with
optional tool calls for S5 to execute in parallel.

BE-01-5: Real S3 planner via route_chat — PulseAgent.think() is deleted.
"""
import logging
import re
import time

from ai.engine.cognition.turn.clarify import evaluate_clarification
from ai.engine.cognition.turn.witnesses import DraftResult
from ai.engine.llm.router import route_chat

logger = logging.getLogger("pulse.cognition.turn.draft")


class DraftWitness:
    """Dedicated LLM planning call. Produces draft text + tool calls."""

    def __init__(self, llm_client=None, knowledge_store=None, memory_manager=None, executor=None, mode="normal"):
        self.llm_client = llm_client
        self.knowledge_store = knowledge_store
        self.memory_manager = memory_manager
        self.executor = executor
        self.mode = mode

    async def draft(
        self,
        instance_id: str,
        conversation_id: str,
        user_message: str,
        system_prompt: str = "",
        conversation_history: list[dict] | None = None,
        instance_config: dict | None = None,
        user_info: dict | None = None,
        budget_tracker=None,  # P3.4: BudgetTracker for per-run token limits
        model: str | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        strict_tools: bool = False,
        # Phase 22-A — per-user default chat temperature (0.0-2.0); None
        # keeps this witness's built-in default (0.3).
        temperature: float | None = None,
        # P4-06 — deterministic clarification gate. When provided, the policy
        # runs FIRST (after the budget check, before any LLM call) and may
        # short-circuit the draft with a clarifying question.
        clarify_inputs: dict | None = None,
        # PV2-2A — preferred: ContextPack; system_prompt is its .system_prompt().
        pack=None,
    ) -> DraftResult:
        """Single LLM call to plan and draft a response.

        No tool-use loop — the loop stays in ReActLoop. This produces
        draft text and optional tool_calls that S5 will execute in parallel.

        ``tools`` — optional OpenAI tool definitions; when provided the
        planner can emit tool_calls for S5 to execute (e.g. create_dq_rule).

        ``clarify_inputs`` — optional dict that MAY contain any of
        ``object_candidates`` (int), ``evidence_available`` (bool),
        ``evidence_required`` (bool), ``authority_granted`` (frozenset/set),
        and ``authority_required`` (str | None). When provided, the
        deterministic clarification policy runs FIRST (after the budget
        check, before any LLM call) and short-circuits the draft with a
        clarifying question if needed — the LLM is never invoked in that case.
        Missing keys default to a "clear" value.
        """
        # P3.4: Check budget before LLM call — graceful fallback if exceeded
        if budget_tracker is not None and budget_tracker.exceeded:
            logger.warning(
                "DraftWitness: budget exceeded before call conv=%s",
                conversation_id[:8],
            )
            return DraftResult(
                text="I've reached my processing limit for this request. Here's what I found so far: "
                     "Please try a more specific question or try again later.",
                tool_calls=[],
                claimed_citations=[],
                confidence=0.3,
                model_used="budget_fallback",
                tokens_used=0,
            )

        # P4-06: deterministic clarification gate. Runs before any LLM call
        # and short-circuits when the policy says to ask instead of guess.
        if clarify_inputs is not None:
            decision = evaluate_clarification(
                object_candidates=clarify_inputs.get("object_candidates", 1),
                evidence_available=clarify_inputs.get("evidence_available", True),
                evidence_required=clarify_inputs.get("evidence_required", False),
                authority_granted=clarify_inputs.get(
                    "authority_granted", frozenset({"*"})
                ),
                authority_required=clarify_inputs.get("authority_required", None),
            )
            if decision.needs_clarification:
                logger.warning(
                    "DraftWitness: clarification required conv=%s reason=%s",
                    conversation_id[:8],
                    decision.reason,
                )
                return DraftResult(
                    text=decision.question,
                    tool_calls=[],
                    claimed_citations=[],
                    confidence=0.3,
                    model_used="clarification_policy",
                    tokens_used=0,
                )

        if pack is None:
            from ai.engine.cognition.context_pack import build_context_pack

            pack = build_context_pack(
                None,
                surface="chat",
                stage="draft",
                user_info=user_info,
                instance_config=instance_config,
                conversation_history=conversation_history,
                task_body=system_prompt,
                include_state=False,
                include_knowledge=False,
                include_memory=False,
                include_history=False,
            )
        messages = [{"role": "system", "content": pack.system_prompt()}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        t0 = time.monotonic()
        # Identity + Task come from ContextPack.system_prompt() (PV2-2A).
        result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"draft-{conversation_id}",
            messages=messages,
            temperature=temperature if temperature is not None else 0.3,
            model=model,
            tools=tools,
            tool_choice=tool_choice,
            strict_tools=strict_tools,
        )
        draft_latency = (time.monotonic() - t0) * 1000

        text = result.get("content") or ""
        tool_calls = result.get("tool_calls") or []
        model_used = result.get("model", "")
        prompt_tokens = result.get("input_tokens", 0) or 0
        completion_tokens = result.get("output_tokens", 0) or 0
        tokens_used = prompt_tokens + completion_tokens

        # Extract inline citations from the text
        claimed_citations = _extract_citations(text)

        logger.info(
            "DraftWitness: conv=%s latency=%.0fms tokens=%d tool_calls=%d text_len=%d model=%s",
            conversation_id[:8], draft_latency, tokens_used, len(tool_calls), len(text), model_used,
        )

        return DraftResult(
            text=text,
            tool_calls=tool_calls,
            claimed_citations=claimed_citations,
            confidence=0.8,
            model_used=model_used,
            tokens_used=tokens_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


def _extract_citations(text: str) -> list[str]:
    """Extract inline citation references from draft text."""
    citations: list[str] = []
    for match in re.finditer(r"\[(?:node|mem|src):([^\]]+)\]", text):
        citations.append(match.group(0))
    return citations
