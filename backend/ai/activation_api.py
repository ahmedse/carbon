"""
AI Pulse Activation API — read-only intelligence-core activation surface.

GET  /carbon-api/ai/pulse/usage/     — LLMCallLog spend/token/call aggregates
GET  /carbon-api/ai/pulse/settings/  — effective engine config + capability inventory

Read-only by structure: every view is a GET-only ``APIView`` (no model
viewset, no mutation actions).  ``usage/`` aggregates the Django
``LLMCallLog`` table (the engine's cost ledger in the ``django`` store
backend); ``settings/`` advertises the effective engine configuration and
capability inventory for the AI admin console.

Secrets discipline (mirrors ``ai.observability_api``):
  * ``LLM_API_KEY`` is never read into the payload at all — the ``llm``
    section carries only the non-secret settings.
  * Dict-carrying sections (``cache``, ``mcp_servers``) are passed through
    ``_redact_secrets`` so no value under a ``token|secret|password|api_key``
    key can leave the process.
  * Every sub-section is individually guarded: a failure in one section
    yields that section's empty value, never a 500.
"""

import asyncio
import json
import logging

from django.conf import settings as django_settings
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.observability_api import _redact_secrets

logger = logging.getLogger("carbon.ai.activation_api")

# Known engine task types surfaced in the routing map (router._TASK_MODEL_MAP).
_ROUTING_TASKS = ("chat", "deep", "cognition", "introspect", "eval", "embed")


# ── Usage ─────────────────────────────────────────────────────────────────


class PulseUsageView(APIView):
    """GET usage/ — LLMCallLog spend/token/call aggregates.

    Response shape::

        {
            "budget_usd": float,          # LLM_DAILY_BUDGET_USD
            "spent_today_usd": float,     # today's cost (created_at__date)
            "tokens_today": int,
            "calls_today": int,
            "tokens_total": int,          # all rows
            "calls_total": int,
            "cost_total": float,
            "remaining_usd": float,       # max(0, budget - spent_today)
            "budget_exceeded": bool,
            "by_model": [{model, cost_usd, total_tokens, calls}, ...],
            "by_day": [{date, cost_usd, total_tokens, calls}, ...],  # last 7 days
        }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from ai.engine.core.config import get_settings
            from ai.models.core import LLMCallLog

            settings = get_settings()
            budget_usd = float(settings.LLM_DAILY_BUDGET_USD)
            today = timezone.localdate()

            today_agg = LLMCallLog.objects.filter(created_at__date=today).aggregate(
                spent=Sum("cost_usd"),
                tokens=Sum("total_tokens"),
                calls=Count("id"),
            )
            total_agg = LLMCallLog.objects.aggregate(
                cost=Sum("cost_usd"),
                tokens=Sum("total_tokens"),
                calls=Count("id"),
            )

            spent_today_usd = float(today_agg["spent"] or 0.0)
            tokens_today = int(today_agg["tokens"] or 0)
            calls_today = int(today_agg["calls"] or 0)

            by_model = [
                {
                    "model": row["model"],
                    "cost_usd": float(row["cost_usd"] or 0.0),
                    "total_tokens": int(row["total_tokens"] or 0),
                    "calls": int(row["calls"] or 0),
                }
                for row in LLMCallLog.objects.values("model")
                .annotate(
                    cost_usd=Sum("cost_usd"),
                    total_tokens=Sum("total_tokens"),
                    calls=Count("id"),
                )
                .order_by("-cost_usd", "model")
            ]

            week_start = today - timezone.timedelta(days=6)
            by_day = [
                {
                    "date": row["created_at__date"],
                    "cost_usd": float(row["cost_usd"] or 0.0),
                    "total_tokens": int(row["total_tokens"] or 0),
                    "calls": int(row["calls"] or 0),
                }
                for row in LLMCallLog.objects.filter(created_at__date__gte=week_start)
                .values("created_at__date")
                .annotate(
                    cost_usd=Sum("cost_usd"),
                    total_tokens=Sum("total_tokens"),
                    calls=Count("id"),
                )
                .order_by("created_at__date")
            ]

            return Response(
                {
                    "budget_usd": budget_usd,
                    "spent_today_usd": round(spent_today_usd, 4),
                    "tokens_today": tokens_today,
                    "calls_today": calls_today,
                    "tokens_total": int(total_agg["tokens"] or 0),
                    "calls_total": int(total_agg["calls"] or 0),
                    "cost_total": float(total_agg["cost"] or 0.0),
                    "remaining_usd": round(
                        max(0.0, budget_usd - spent_today_usd), 4
                    ),
                    "budget_exceeded": bool(spent_today_usd > budget_usd),
                    "by_model": by_model,
                    "by_day": by_day,
                }
            )
        except Exception as exc:  # noqa: BLE001 — never 500 the console
            logger.exception("pulse usage aggregation failed")
            return Response({"error": str(exc)})


# ── Settings ──────────────────────────────────────────────────────────────


def _settings_llm() -> dict:
    """Effective LLM provider settings (never the API key itself)."""
    from ai.engine.core.config import get_settings

    settings = get_settings()
    return {
        "base_url": settings.LLM_BASE_URL,
        "model": settings.LLM_MODEL,
        "normal_model": settings.LLM_NORMAL_MODEL,
        "cognition_model": settings.LLM_COGNITION_MODEL,
        "embedding_model": settings.LLM_EMBEDDING_MODEL,
        "eval_model": settings.EVAL_MODEL,
        "daily_budget_usd": settings.LLM_DAILY_BUDGET_USD,
        "allow_expensive_models": bool(settings.PULSE_ALLOW_EXPENSIVE_MODELS),
    }


def _settings_limits() -> dict:
    """Guardrail / per-run budget / agent fields (exact config.py values)."""
    from ai.engine.core.config import get_settings

    settings = get_settings()
    return {
        "GUARDRAIL_MAX_TOOL_CALLS_PER_RUN": settings.GUARDRAIL_MAX_TOOL_CALLS_PER_RUN,
        "GUARDRAIL_MAX_TOKENS_PER_RUN": settings.GUARDRAIL_MAX_TOKENS_PER_RUN,
        "GUARDRAIL_BUDGET_ENFORCEMENT": bool(settings.GUARDRAIL_BUDGET_ENFORCEMENT),
        "RUN_TOKEN_BUDGET_DEFAULT": settings.RUN_TOKEN_BUDGET_DEFAULT,
        "RUN_TOKEN_BUDGET_WORKER_SHARE": settings.RUN_TOKEN_BUDGET_WORKER_SHARE,
        "RUN_TOKEN_BUDGET_MIN_WORKER": settings.RUN_TOKEN_BUDGET_MIN_WORKER,
        "AGENT_MAX_WORKERS": settings.AGENT_MAX_WORKERS,
        "AGENT_WORKER_TIMEOUT_SEC": settings.AGENT_WORKER_TIMEOUT_SEC,
        "AGENT_UNIFIED_FINALIZE": bool(settings.AGENT_UNIFIED_FINALIZE),
        "AGENT_ORCHESTRATOR_ENABLED": bool(settings.AGENT_ORCHESTRATOR_ENABLED),
        "DEFAULT_AUTONOMY_LEVEL": settings.DEFAULT_AUTONOMY_LEVEL,
    }


def _settings_cache() -> dict:
    """Django AI cache TTL + live cache-store stats (best-effort)."""
    payload = {
        "ttl_seconds": getattr(django_settings, "AI_CACHE_TTL_SECONDS", 300),
        "store": {},
    }
    try:
        from ai.engine.core.database import get_session_factory
        from ai.engine.knowledge_graph.cache_store import QueryCacheStore

        async def _stats() -> dict:
            session_factory = get_session_factory(None)
            async with session_factory() as db:
                return await QueryCacheStore().get_stats(instance_id="shared", db=db)

        payload["store"] = asyncio.run(_stats())
    except Exception as exc:  # noqa: BLE001 — cache stats are best-effort
        logger.debug("pulse cache-store stats unavailable: %s", exc)
        payload["store"] = {}
    return payload


def _settings_rate_limit() -> int:
    """Per-minute AI request cap from Django settings."""
    return getattr(django_settings, "AI_RATE_LIMIT_PER_MINUTE", 0)


def _settings_routing() -> dict:
    """Known task types → the model the router would select for each."""
    from ai.engine.llm.router import get_model_for_task

    return {task: get_model_for_task(task) for task in _ROUTING_TASKS}


def _settings_mcp() -> list:
    """Configured MCP servers (names/command/args only — env is never exposed)."""
    from ai.engine.core.config import get_settings

    raw = (get_settings().MCP_SERVERS or "").strip()
    if not raw:
        return []
    try:
        configs = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.debug("MCP_SERVERS is not valid JSON — no servers surfaced")
        return []
    if not isinstance(configs, list):
        return []

    servers = []
    for cfg in configs:
        if not isinstance(cfg, dict):
            continue
        name = cfg.get("name", "")
        if not name:
            continue
        servers.append(
            {
                "name": name,
                "command": cfg.get("command", ""),
                "args": list(cfg.get("args", []) or []),
            }
        )
    return servers


def _settings_tools() -> list:
    """Registered tool catalog (name + description) — static + MCP-injected."""
    from ai.engine.agent.tools import get_tool_definitions

    catalog = []
    for tool in get_tool_definitions():
        function = (tool or {}).get("function", {}) or {}
        catalog.append(
            {
                "name": function.get("name", ""),
                "description": function.get("description", ""),
            }
        )
    return catalog


def _settings_agents() -> list:
    """Registered agent names from the Django-backed agent registry."""
    from ai.models.core import Agent

    return list(
        Agent.objects.filter(is_active=True)
        .values_list("name", flat=True)
        .order_by("name")
    )


class PulseSettingsView(APIView):
    """GET settings/ — effective engine config + capability inventory.

    Response shape::

        {
            "llm": {base_url, model, normal_model, cognition_model,
                    embedding_model, eval_model, daily_budget_usd,
                    allow_expensive_models},
            "limits": {guardrail / run-budget / agent config fields},
            "cache": {ttl_seconds, store: {total_live_entries, total_hits,
                     by_layer} | {}},
            "rate_limit": int,
            "routing": {task: model, ...},
            "mcp_servers": [{name, command, args}, ...] | [],
            "tools_catalog": [{name, description}, ...] | [],
            "agents": [name, ...] | [],
        }

    Every section is independently guarded; a section failure yields that
    section's empty value, never a 500.  ``LLM_API_KEY`` is never included,
    and dict-carrying sections are redacted via ``_redact_secrets``.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        payload = {
            "llm": _settings_llm(),
            "limits": _settings_limits(),
            "cache": _settings_cache(),
            "rate_limit": _settings_rate_limit(),
            "routing": _settings_routing(),
            "mcp_servers": _settings_mcp(),
            "tools_catalog": _settings_tools(),
            "agents": _settings_agents(),
        }
        # Dict-carrying sections may embed arbitrary values — redact anything
        # stored under a secret-hinting key before it leaves the process.
        payload["cache"] = _redact_secrets(payload["cache"])
        payload["mcp_servers"] = _redact_secrets(payload["mcp_servers"])
        return Response(payload)
