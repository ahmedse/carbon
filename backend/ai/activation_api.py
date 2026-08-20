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

from accounts.ai_scoping import scope_ai_queryset
from accounts.permissions import AdminOrSuperuserOnly
from ai.models import ModelCatalog
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

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "ai:view_console"

    def get(self, request):
        try:
            from ai.engine.core.config import get_settings
            from ai.models.core import LLMCallLog

            settings = get_settings()
            budget_usd = float(settings.LLM_DAILY_BUDGET_USD)
            today = timezone.localdate()

            base = scope_ai_queryset(LLMCallLog.objects, request.user)

            today_agg = base.filter(created_at__date=today).aggregate(
                spent=Sum("cost_usd"),
                tokens=Sum("total_tokens"),
                calls=Count("id"),
            )
            total_agg = base.aggregate(
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
                for row in base.values("model")
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
                for row in base.filter(created_at__date__gte=week_start)
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


# Static tools that mutate durable state or are confirmation-gated by design
# (RULE_21: AI suggests, Carbon executes).  Reads are never confirmation-gated.
_STATIC_CONFIRMATION_TOOLS = {
    "call_host_api",
    "run_ops_workflow",
    "learn_fact",
    "forget_fact",
    "draft_skill",
}


def _settings_tools() -> list:
    """Registered tool catalog (rich metadata) — static + plugin + MCP.

    Sprint 12 (ARCH_AI_EXTENSIBILITY): each entry carries ``kind``,
    ``requires_confirmation``, ``capability`` and ``app_identifier`` so the
    admin console can show the growth surface — not just a flat name list.

    Sprint W1-A: each entry also carries the tool's JSON ``parameters``
    schema so the console can render an args form for the action seam.
    """
    from ai.engine.agent.plugins import WorkflowPlugin, registered_plugins
    from ai.engine.agent.tools import (
        MCP_TOOLS,
        STATIC_TOOL_DEFINITIONS,
        get_tool_definitions,
    )

    static_names = {t["function"]["name"] for t in STATIC_TOOL_DEFINITIONS}
    mcp_names = {t["function"]["name"] for t in MCP_TOOLS}

    plugin_meta = {}
    for plugin in registered_plugins():
        plugin_meta[plugin.name] = {
            "kind": "workflow" if isinstance(plugin, WorkflowPlugin) else "plugin",
            "requires_confirmation": bool(plugin.requires_confirmation),
            "capability": plugin.capability,
            "app_identifier": plugin.app_identifier,
        }

    catalog = []
    for tool in get_tool_definitions():
        function = (tool or {}).get("function", {}) or {}
        name = function.get("name", "")
        if name in static_names:
            meta = {
                "kind": "static",
                "requires_confirmation": name in _STATIC_CONFIRMATION_TOOLS,
                "capability": None,
                "app_identifier": None,
            }
        elif name in plugin_meta:
            meta = plugin_meta[name]
        elif name in mcp_names:
            meta = {
                "kind": "mcp",
                "requires_confirmation": False,
                "capability": None,
                "app_identifier": None,
            }
        else:
            meta = {
                "kind": "unknown",
                "requires_confirmation": False,
                "capability": None,
                "app_identifier": None,
            }
        catalog.append(
            {
                "name": name,
                "description": function.get("description", ""),
                "parameters": function.get("parameters", {}),
                **meta,
            }
        )
    return catalog


def _settings_agents() -> list:
    """Registered agents (rich metadata) from the Django-backed agent registry.

    Sprint W1-A: each entry is a dict ``{id, name, role, tool_set, is_active}``
    so the console can render agent cards and wire the action seam.  The
    Django model stores the tool set in ``tool_set_json`` (a JSON array of
    tool names); it is surfaced here as ``tool_set``.
    """
    from ai.models.core import Agent

    agents = Agent.objects.filter(is_active=True).values(
        "id", "name", "role", "tool_set_json", "is_active"
    )
    return [
        {
            "id": str(agent["id"]),
            "name": agent["name"],
            "role": agent["role"],
            "tool_set": agent["tool_set_json"] or [],
            "is_active": agent["is_active"],
        }
        for agent in agents.order_by("name")
    ]


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
            "tools_catalog": [{name, description, parameters, kind,
                              requires_confirmation, capability,
                              app_identifier}, ...] | [],
            "agents": [{id, name, role, tool_set, is_active}, ...] | [],
        }

    Every section is independently guarded; a section failure yields that
    section's empty value, never a 500.  ``LLM_API_KEY`` is never included,
    and dict-carrying sections are redacted via ``_redact_secrets``.
    """

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "ai:view_console"

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


# ── Model catalog ─────────────────────────────────────────────────────────


def _is_default_model(row: ModelCatalog, default_key: str) -> bool:
    """True when *row* is the configured default chat model.

    *default_key* is pre-normalized (lowercased, provider prefix stripped) by
    the caller.  Matches against the stable ``model_id`` slug and the bare
    model name at the tail of the server-side ``version`` (e.g.
    ``anthropic/claude-haiku-4.5`` → ``claude-haiku-4.5``), so raw provider
    routing never leaks into the response while the configured default still
    resolves to a catalog row.
    """
    if not default_key:
        return False
    candidates = {row.model_id.lower(), row.version.rsplit("/", 1)[-1].lower()}
    return default_key in candidates


class AIModelsView(APIView):
    """GET models/ — chat-model catalog for the frontend model picker.

    Available to any authenticated user (the picker lives in the chat input
    bar, not the admin console).

    Phase 20-A: the catalog is now sourced from the ``ModelCatalog`` table
    (single source of truth for cost, tier, version, and retirement). The
    response is a backward-compatible superset of the legacy router shape —
    the legacy keys (``id``/``label``/``description``/costs/``is_default``)
    are preserved so the existing picker keeps working, while new keys
    (``display_name``, ``tier``, ``version``, ``context_window``,
    ``deprecated``, ``superseded_by``, ``capabilities``) are appended.

    Response shape::

        {
            "models": [
                {
                    "id": str,
                    "label": str,
                    "description": str,
                    "input_cost_per_1m": float,
                    "output_cost_per_1m": float,
                    "is_default": bool,
                    # ── Phase 20-A superset ──
                    "display_name": str,
                    "tier": "fast" | "balanced" | "brain",
                    "version": str,
                    "context_window": int,
                    "deprecated": bool,
                    "superseded_by": str | None,
                    "capabilities": [str, ...],
                },
                ...
            ],
        }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from ai.engine.llm.router import get_model_for_task

        try:
            # Normalize: lowercase and strip any leading "provider/" prefix so a
            # configured default like "anthropic/claude-haiku-4.5" resolves to the
            # bare "claude-haiku-4.5" catalog slug.
            default_key = (get_model_for_task("chat") or "").strip().lower().rsplit("/", 1)[-1]
        except Exception:
            logger.exception("Failed to resolve default chat model")
            default_key = ""

        models = []
        try:
            rows = ModelCatalog.objects.all()
            for row in rows:
                models.append(
                    {
                        # Legacy keys — picker compatibility.
                        "id": row.model_id,
                        "label": row.display_name,
                        "description": row.description,
                        "input_cost_per_1m": float(row.input_cost_per_1m),
                        "output_cost_per_1m": float(row.output_cost_per_1m),
                        "is_default": _is_default_model(row, default_key),
                        # Phase 20-A superset.
                        "display_name": row.display_name,
                        "tier": row.tier,
                        "version": row.version,
                        "context_window": row.context_window,
                        "deprecated": row.deprecated,
                        "superseded_by": (
                            row.superseded_by.model_id if row.superseded_by else None
                        ),
                        "capabilities": row.capabilities or [],
                    }
                )
        except Exception:
            logger.exception("Failed to build chat-model catalog")
            models = []
        return Response({"models": models})
