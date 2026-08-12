"""
Evaluation harness for prompt self-improvement.

Given a prompt version and a set of queries, simulates agent responses
and computes quality scores. Uses LLM-as-judge for relevance scoring.
"""
import json
import logging
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.config import get_settings
from ai.engine.core.models import Message, PromptEval, PromptVersion, generate_uuid
from ai.engine.llm.provider import chat_completion

logger = logging.getLogger("pulse.llm.prompt_eval")

# ── Synthetic eval queries (fallback when no Message history exists) ─────

_SYNTHETIC_QUERIES = [
    "What can you help me with?",
    "Show me a summary of recent activity.",
    "What data is available in this system?",
    "Find the most important entities and explain their relationships.",
    "How do I get started with this platform?",
    "What are the key metrics I should monitor?",
    "Explain the main workflows available.",
]


# ── Judge prompt — LLM scores relevance ──────────────────────────────────

_JUDGE_PROMPT = """You are an evaluation judge. Score the assistant's response for relevance to the user's query.

User query: {query}

Assistant response: {response}

Rate relevance on a scale of 0.0 to 1.0:
- 1.0: Perfectly relevant, directly answers the query with domain-specific detail.
- 0.7: Mostly relevant, covers the topic but misses some specifics.
- 0.4: Partially relevant, touches the topic but drifts significantly.
- 0.0: Completely off-topic or nonsensical.

Return ONLY a single float number, nothing else. Example: 0.85"""


# ── Public API ────────────────────────────────────────────────────────────

async def evaluate_prompt(
    db: AsyncSession,
    prompt_text: str,
    instance_id: str,
    eval_queries: list[str],
    model: str | None = None,
) -> list[PromptEval]:
    """Simulate agent response for each query using prompt_text, compute metrics.

    For each query:
    1. Send it as a user message with prompt_text as the system prompt
    2. Collect the LLM response
    3. Use LLM-as-judge to score relevance
    4. Create and return PromptEval rows (NOT committed — caller decides)

    Tool call accuracy is approximate: we record tool_calls_made as [] since
    chat_completion() does not return tool calls. Real tool-call evaluation
    would require a full agent loop simulation.
    """
    settings = get_settings()
    eval_model = model or settings.EVAL_MODEL or settings.LLM_MODEL
    evals: list[PromptEval] = []

    for query in eval_queries:
        try:
            # 1. Get agent response
            messages = [
                {"role": "system", "content": prompt_text},
                {"role": "user", "content": query},
            ]
            response_text = await chat_completion(messages, model=eval_model, temperature=0.2)

            # 2. Judge relevance with LLM
            judge_messages = [
                {"role": "system", "content": "You are an impartial evaluation judge. Return only a float."},
                {"role": "user", "content": _JUDGE_PROMPT.format(query=query, response=response_text)},
            ]
            relevance_raw = await chat_completion(judge_messages, model=eval_model, temperature=0.0)
            try:
                relevance_score = float(relevance_raw.strip())
                relevance_score = max(0.0, min(1.0, relevance_score))
            except (ValueError, TypeError):
                logger.warning(f"Judge returned non-float for query {query[:40]!r}: {relevance_raw!r}")
                relevance_score = 0.5

            # 3. Determine task_completion: True if relevance >= 0.5
            task_completion = relevance_score >= 0.5

            pe = PromptEval(
                id=generate_uuid(),
                prompt_version_id="",  # filled by caller after version is saved
                instance_id=instance_id,
                query_text=query,
                response_text=response_text,
                tool_calls_made="[]",
                tool_calls_expected=None,
                task_completion=task_completion,
                relevance_score=relevance_score,
                user_feedback=None,
                eval_source="auto",
            )
            evals.append(pe)

        except Exception as exc:
            logger.error(f"Eval failed for query {query[:40]!r}: {exc}", exc_info=True)
            # Record a failed eval
            pe = PromptEval(
                id=generate_uuid(),
                prompt_version_id="",
                instance_id=instance_id,
                query_text=query,
                response_text=None,
                tool_calls_made="[]",
                tool_calls_expected=None,
                task_completion=False,
                relevance_score=0.0,
                user_feedback=None,
                eval_source="auto_error",
            )
            evals.append(pe)

    return evals


async def compute_prompt_score(db: AsyncSession, prompt_version_id: str) -> float:
    """Aggregate PromptEval rows for this version into a 0–1 score.

    Weights:
      - 40% task_completion rate
      - 30% mean relevance_score
      - 20% tool accuracy (1.0 if no expected tool calls, else ratio matched)
      - 10% user_feedback (normalised -1/+1 → 0–1)
    """
    result = await db.execute(
        select(PromptEval).where(PromptEval.prompt_version_id == prompt_version_id)
    )
    evals = result.scalars().all()

    if not evals:
        return 0.0

    n = len(evals)

    # 40% — task completion rate
    completed = sum(1 for e in evals if e.task_completion)
    completion_rate = completed / n if n > 0 else 0.0

    # 30% — mean relevance
    relevance_scores = [e.relevance_score for e in evals if e.relevance_score is not None]
    mean_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0

    # 20% — tool accuracy (simplified: 1.0 when no expected, else 0.5 avg)
    tool_accs = []
    for e in evals:
        if e.tool_calls_expected is None:
            tool_accs.append(1.0)
        else:
            try:
                expected = set(json.loads(e.tool_calls_expected))
                made = set(json.loads(e.tool_calls_made))
                if not expected:
                    tool_accs.append(1.0)
                else:
                    tool_accs.append(len(made & expected) / len(expected))
            except (json.JSONDecodeError, TypeError):
                tool_accs.append(0.5)
    tool_accuracy = sum(tool_accs) / len(tool_accs) if tool_accs else 0.5

    # 10% — user feedback (normalised: -1→0, 0→0.5, +1→1)
    feedbacks = [e.user_feedback for e in evals if e.user_feedback is not None]
    if feedbacks:
        avg_feedback = sum(feedbacks) / len(feedbacks)
        norm_feedback = (avg_feedback + 1) / 2  # map -1..+1 → 0..1
    else:
        norm_feedback = 0.5  # neutral default

    score = (
        0.40 * completion_rate
        + 0.30 * mean_relevance
        + 0.20 * tool_accuracy
        + 0.10 * norm_feedback
    )

    return round(score, 4)


async def get_eval_queries(
    db: AsyncSession, instance_id: str, count: int = 5
) -> list[str]:
    """Sample diverse user queries from Message history for a given instance.

    Messages have no direct instance_id — join through Conversation.
    Falls back to synthetic queries when history is insufficient.
    """
    from ai.engine.core.models import Conversation

    result = await db.execute(
        select(Message.content)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.instance_id == instance_id,
            Message.role == "user",
            Message.content.isnot(None),
            Message.content != "",
        )
        .order_by(func.random())
        .limit(count)
    )
    rows = result.scalars().all()

    if rows and len(rows) >= count:
        return [str(r) for r in rows if str(r).strip()]

    # If we got some but not enough, combine with synthetics
    real = [str(r) for r in rows if str(r).strip()]
    needed = max(0, count - len(real))
    return real + _SYNTHETIC_QUERIES[:needed]


def is_prompt_healthy(score: float, min_score: float = 0.6) -> bool:
    """Return True if the prompt score meets the minimum threshold."""
    return score >= min_score
