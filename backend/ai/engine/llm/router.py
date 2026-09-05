"""
LLM Router — task-based model routing, cost tracking, budget enforcement.

Every LLM call in Pulse should route through this module. It:

1. Selects the right model for each task type (chat, cognition, introspection, eval).
2. Logs every call to ``llm_call_logs`` with token counts and estimated cost.
3. Enforces a per-instance daily budget cap (graceful degradation).
4. Provides cost estimation helpers.

Usage::

    from ai.engine.llm.router import route_chat

    response = await route_chat(
        task="chat",
        instance_id="gigacast",
        conversation_id="conv-123",
        messages=[{"role": "user", "content": "Hello"}],
    )
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from ai.engine.core.config import get_settings

logger = logging.getLogger("pulse.llm.router")

# ── Task → model mapping ─────────────────────────────────────────────────────

_TASK_MODEL_MAP: dict[str, str] = {}


def _load_task_model_map() -> dict[str, str]:
    """Build task→model mapping from settings (cached)."""
    global _TASK_MODEL_MAP
    if _TASK_MODEL_MAP:
        return _TASK_MODEL_MAP

    settings = get_settings()
    _TASK_MODEL_MAP = {
        "chat": settings.LLM_NORMAL_MODEL or settings.LLM_MODEL,
        "deep": settings.LLM_MODEL,
        # Adaptive reasoning lane (C1): genuinely hard problems (deep salience
        # or a knowledge_gap) escalate here. Falls back through the legacy
        # escalation model to the deep/fallback model when unset.
        "reason": settings.LLM_REASON_MODEL or settings.LLM_ESCALATION_MODEL or settings.LLM_MODEL,
        "cognition": settings.LLM_COGNITION_MODEL or settings.LLM_MODEL,
        "introspect": settings.LLM_INTROSPECT_MODEL or settings.LLM_NORMAL_MODEL or settings.LLM_MODEL,
        "eval": settings.EVAL_MODEL or settings.LLM_MODEL,
        "embed": settings.LLM_EMBEDDING_MODEL,
    }
    return _TASK_MODEL_MAP


def get_model_for_task(task: str) -> str:
    """Return the model name configured for *task*."""
    return _load_task_model_map().get(task, get_settings().LLM_MODEL)


# ── Turn profile → model (Pulse v2 Phase 9 — model policy) ───────────────────

def model_for_profile(profile: str | None) -> str | None:
    """Map a turn profile to an explicit model override, or None for default.

    Profiles (Pulse v2 Phase 9):
      - "interactive" → instance default (always None — the default model).
      - "investigate" → ``LLM_INVESTIGATE_MODEL`` when configured, else None
        (falls back to the instance default).
      - "verify"      → ``LLM_VERIFY_MODEL`` when configured, else the
        investigate model, else None (instance default).

    Returns None when no explicit model is configured for the profile, which
    callers interpret as "use the default model" (so an unset strong model
    silently degrades to the default rather than erroring).
    """
    if not profile or profile == "interactive":
        return None

    settings = get_settings()

    if profile == "investigate":
        return settings.LLM_INVESTIGATE_MODEL or None

    if profile == "verify":
        return settings.LLM_VERIFY_MODEL or settings.LLM_INVESTIGATE_MODEL or None

    return None


# ── Cost estimation ──────────────────────────────────────────────────────────

_COST_CACHE: dict[str, dict[str, float]] | None = None


def _get_cost_table() -> dict[str, dict[str, float]]:
    """Parse ``LLM_COST_MODELS`` JSON into {model: {input, output}} (per 1M tokens)."""
    global _COST_CACHE
    if _COST_CACHE is not None:
        return _COST_CACHE
    try:
        _COST_CACHE = json.loads(get_settings().LLM_COST_MODELS)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Invalid LLM_COST_MODELS JSON — cost tracking disabled")
        _COST_CACHE = {}
    return _COST_CACHE


def _find_rates(model: str) -> dict[str, float] | None:
    """Look up a model's cost rates, matching the key case-insensitively.

    Providers may return a different case than the ``LLM_COST_MODELS`` keys
    (e.g. POE returns ``gpt-4o`` while the cost table uses ``GPT-4o``).
    """
    key = (model or "").strip().lower()
    if not key:
        return None
    for name, rates in _get_cost_table().items():
        if name.strip().lower() == key:
            return rates
    return None


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for token counts. Returns 0.0 if model rates unknown."""
    rates = _find_rates(model)
    if not rates:
        return 0.0
    input_cost = (input_tokens / 1_000_000) * rates.get("input", 0)
    output_cost = (output_tokens / 1_000_000) * rates.get("output", 0)
    return round(input_cost + output_cost, 6)


# ── Selectable chat models (user-facing model picker) ────────────────────────

# Curated, provider-specific model IDs exposed in the AI workspace model picker.
# ``id`` is the exact model name sent to the LLM provider; ``cost_key`` maps to
# an ``LLM_COST_MODELS`` entry for pricing. Keep this list small and verified —
# retired or budget-guardrailed models are intentionally excluded.
_CHAT_MODEL_CATALOG: tuple[dict, ...] = (
    {
        "id": "gpt-4o",
        "label": "GPT-4o",
        "description": "High-quality general-purpose model for complex tasks.",
        "cost_key": "GPT-4o",
    },
    {
        "id": "gpt-4o-mini",
        "label": "GPT-4o mini",
        "description": "Fast and economical for everyday tasks.",
        "cost_key": "GPT-4o-mini",
    },
    {
        "id": "claude-3-5-sonnet",
        "label": "Claude Sonnet",
        "description": "Balanced reasoning and strong coding.",
        "cost_key": "Claude-Sonnet-4.5",
    },
)


def list_chat_models() -> list[dict]:
    """Return the selectable chat models with resolved pricing.

    Each entry carries ``id``, ``label``, ``description``, per-1M-token
    ``input_cost_per_1m``/``output_cost_per_1m``, and ``is_default`` (True
    when the model matches the configured default chat model).
    """
    default_key = (get_model_for_task("chat") or "").strip().lower()
    models: list[dict] = []
    for entry in _CHAT_MODEL_CATALOG:
        rates = _find_rates(entry["cost_key"]) or {}
        models.append(
            {
                "id": entry["id"],
                "label": entry["label"],
                "description": entry["description"],
                "input_cost_per_1m": rates.get("input", 0.0),
                "output_cost_per_1m": rates.get("output", 0.0),
                "is_default": entry["id"].strip().lower() == default_key,
            }
        )
    return models


# ── Budget enforcement ───────────────────────────────────────────────────────

async def _check_budget(instance_id: str, db) -> float | None:
    """Return today's spend, or None if budget exceeded.

    Returns:
        Today's spend so far (USD), or None if the budget has been exceeded.
    """
    from ai.engine.core.models import LLMCallLog

    settings = get_settings()
    budget = settings.LLM_DAILY_BUDGET_USD
    if budget <= 0:
        return 0.0  # unlimited

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    agg = await db.aggregate(
        LLMCallLog,
        {"spend": ("Sum", "cost_usd")},
        {"instance_id": instance_id, "created_at__gte": today},
    )
    spent = agg.get("spend") or 0.0

    if spent >= budget:
        logger.warning(
            "Budget exceeded for instance %s: $%.4f / $%.2f", instance_id, spent, budget
        )
        return None
    return spent


# ── Main routing function ────────────────────────────────────────────────────

async def route_chat(
    task: str,
    instance_id: str,
    conversation_id: str,
    messages: list[dict],
    *,
    temperature: float = 0.3,
    tools: list[dict] | None = None,
    max_tokens: int | None = None,
    response_format: dict | None = None,
    model: str | None = None,
    db=None,  # optional: if None, creates its own session
) -> dict:
    """Route an LLM call by task type, logging cost and enforcing budget.

    Args:
        task:         One of 'chat', 'deep', 'reason', 'cognition', 'introspect', 'eval'.
        instance_id:  Pulse instance ID.
        conversation_id: Conversation UUID.
        messages:     OpenAI-format message list.
        temperature:  Model temperature.
        tools:        Optional tool definitions.
        max_tokens:   Optional max output tokens.
        model:        Optional model override (defaults to the task's model).
        db:           Optional async session. If None, a short-lived session is created.

    Returns:
        {
            "content": str | None,
            "tool_calls": list | None,
            "finish_reason": str,
            "model": str,
            "input_tokens": int,
            "output_tokens": int,
            "cost_usd": float,
        }
    """
    from ai.engine.llm.provider import create_completion, get_llm_client

    settings = get_settings()
    model = model or get_model_for_task(task)

    # Budget check
    need_own_db = db is None
    _own_session = None
    if need_own_db:
        from ai.engine.core.database import get_session_factory
        _own_session = get_session_factory()()
        db = _own_session

    try:
        spent = await _check_budget(instance_id, db)
        if spent is None:
            # Budget exceeded — return a polite refusal
            return {
                "content": (
                    "I'm sorry, but the daily AI usage budget for this instance has been "
                    "reached. Please try again tomorrow or contact your administrator to "
                    "adjust the budget."
                ),
                "tool_calls": None,
                "finish_reason": "budget_exceeded",
                "model": model,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
            }

        t0 = time.monotonic()
        client = get_llm_client()

        kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if response_format:
            kwargs["response_format"] = response_format

        response = await create_completion(client, **kwargs)
        duration_ms = int((time.monotonic() - t0) * 1000)

        choice = response.choices[0]
        content = choice.message.content
        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        total_tokens = response.usage.total_tokens if response.usage else 0
        cost_usd = estimate_cost(model, input_tokens, output_tokens)

        # Log to llm_call_logs
        await _log_call(
            db,
            instance_id=instance_id,
            conversation_id=conversation_id,
            task=task,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
            cost_usd=cost_usd,
        )

        result = {
            "content": content,
            "tool_calls": tool_calls,
            "finish_reason": choice.finish_reason,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
        }

        logger.debug(
            "LLM call: task=%s model=%s tokens=%d cost=$%.6f duration=%dms",
            task, model, total_tokens, cost_usd, duration_ms,
        )
        return result

    except Exception as exc:
        logger.error("LLM call failed (task=%s, model=%s): %s", task, model, exc)
        raise
    finally:
        if _own_session is not None:
            await _own_session.close()


# ── Internal logging ─────────────────────────────────────────────────────────

async def _log_call(
    db,
    instance_id: str,
    conversation_id: str,
    task: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    duration_ms: int,
    cost_usd: float,
) -> None:
    """Write a row to llm_call_logs."""
    from uuid import uuid4
    from ai.engine.core.models import LLMCallLog

    log = LLMCallLog(
        id=str(uuid4()),
        instance_id=instance_id,
        conversation_id=conversation_id,
        model=model,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
    )
    try:
        # Use a savepoint so a log-write failure doesn't poison the outer transaction
        async with db.begin_nested():
            db.add(log)
            await db.flush()
    except Exception as exc:
        logger.debug("Failed to write llm_call_logs: %s", exc)


# ── Query helpers ────────────────────────────────────────────────────────────

async def get_daily_spend(instance_id: str, db) -> float:
    """Return today's total estimated spend for *instance_id*."""
    from ai.engine.core.models import LLMCallLog

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    agg = await db.aggregate(
        LLMCallLog,
        {"spend": ("Sum", "cost_usd")},
        {"instance_id": instance_id, "created_at__gte": today},
    )
    return round(agg.get("spend") or 0.0, 4)


async def get_instance_stats(instance_id: str, db, days: int = 7) -> dict:
    """Return 7-day stats: total calls, tokens, cost, by model."""
    from collections import defaultdict
    from ai.engine.core.models import LLMCallLog

    since = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None,
    )
    from datetime import timedelta
    since = since - timedelta(days=days - 1)

    rows = await db.select(
        LLMCallLog,
        {"instance_id": instance_id, "created_at__gte": since},
    )

    by_model_map: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "tokens": 0, "cost": 0.0}
    )
    for row in rows:
        m = by_model_map[row.model]
        m["calls"] += 1
        m["tokens"] += row.total_tokens or 0
        m["cost"] += row.cost_usd or 0.0

    by_model = [
        {
            "model": k,
            "calls": v["calls"],
            "tokens": v["tokens"],
            "cost_usd": round(v["cost"], 4),
        }
        for k, v in sorted(
            by_model_map.items(), key=lambda item: item[1]["cost"], reverse=True
        )
    ]
    return {
        "instance_id": instance_id,
        "days": days,
        "total_calls": sum(r["calls"] for r in by_model),
        "total_tokens": sum(r["tokens"] for r in by_model),
        "total_cost_usd": round(sum(r["cost_usd"] for r in by_model), 4),
        "by_model": by_model,
    }
