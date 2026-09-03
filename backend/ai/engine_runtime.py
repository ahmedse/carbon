"""
In-process engine runtime — replaces the retired HTTP transport.

Phase 2 wires the vendored engine in-process: instead of POSTing tasks to the
external Pulse server over HTTP, Carbon calls this runtime directly.  It is
the in-process counterpart of Pulse's ``POST /instances/carbon/tasks`` and
``GET /instances/carbon/tasks/{id}`` endpoints.

Each task type will map to a concrete engine capability (KG query, turn
runner, LLM) in Phase 2b.  Until a task is wired, ``dispatch_task`` returns a
graceful ``pulse_unavailable`` result — fail-visible, never a fabricated
answer.
"""

from __future__ import annotations

import json
import logging
import math
import queue
import re
import threading
import time
import types
import uuid
from typing import Any

logger = logging.getLogger("carbon.ai.engine_runtime")

# Task types the engine advertises (mirrors the retired Pulse task API).
MODULES: list[str] = [
    "dq.validate",
    "dq.suggest",
    "dq.rule_test",
    "carbon.query.nl",
    "carbon.query.explain",
    "carbon.anomaly.detect",
    "carbon.anomaly.explain",
    "carbon.report.draft",
    "carbon.schema.analyze",
    "carbon.fix.suggest",
    "investigate",
    "chat",
]


def _new_task_id() -> str:
    return f"inproc-{uuid.uuid4().hex[:16]}"


def _run_async(coro):
    """Run an async coroutine from a sync context.

    ``dispatch_task`` is sync (the AIProvider ABC is sync).  The vendored
    engine is async, so we bridge with ``asyncio.run``.  If we are already
    inside a running loop (rare — e.g. a caller awaiting a sync wrapper),
    run the coroutine on a worker thread to avoid nesting loops.
    """
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def _run_chat(
    instance_id: str, payload: dict[str, Any], task_id: str, *, stream_callback=None
) -> dict[str, Any]:
    """Run a single chat turn through the six-witness pipeline.

    This is the Phase 2b-1 proof path: the in-process engine's ``chat``
    task calls ``TurnPipelineRunner.run`` directly (no HTTP), writing
    durable ``TurnLedgerRow`` / ``LLMCallLog`` rows through the configured
    ``ai.store`` backend (DjangoStore in production).

    Since Sprint "fly to rule detail", the chat turn also carries the
    authenticated user + a Carbon instance config so the engine's tool layer
    (``create_dq_rule`` plugin, navigation) runs with real context:
      * ``host_user_id`` — Django user PK (from the chat Scope); the in-process
        host executor stages + confirms mutations as this user.
      * ``instance_config`` — display/persona/navigation_routes for the system
        prompt, and the executor's route table.
    Tool outcomes are surfaced deterministically as ``actions`` (navigate) and
    ``pending_actions`` (staged confirmations) — never as LLM prose.
    """
    from ai.engine.cognition.turn.runner import TurnPipelineRunner
    from ai.engine.core.database import get_session_factory
    from ai.host_executor import CarbonHostExecutor

    message = payload.get("message") or ""
    model = payload.get("model")
    # Phase 22-A — per-user default chat temperature (0.0-2.0); None keeps the
    # engine's built-in draft default (0.3).
    temperature = payload.get("temperature")
    host_user_id = payload.get("host_user_id") or None
    conversation = payload.get("conversation_history") or {}
    conversation_id = (
        conversation.get("conversation_id")
        or f"conv-{uuid.uuid4().hex[:12]}"
    )
    history_messages = conversation.get("messages") or []

    instance_config = _carbon_instance_config(host_user_id)
    user_info = _build_chat_user_info(host_user_id)

    factory = get_session_factory(instance_id)
    async with factory() as db:
        executor = CarbonHostExecutor(
            db=db,
            instance_config=instance_config,
            user_token=f"inproc:carbon:{host_user_id}" if host_user_id else None,
            host_user_id=host_user_id,
        )
        runner = TurnPipelineRunner(db=db, executor=executor)
        response, ledger = await runner.run(
            instance_id=instance_id,
            conversation_id=conversation_id,
            user_message=message,
            host_user_id=host_user_id,
            conversation_history=history_messages,
            instance_config=instance_config,
            user_info=user_info,
            stream_callback=stream_callback,
            model=model,
            temperature=temperature,
        )

        # Deterministic, tool-grounded outcome surfacing — the assistant text
        # is LLM prose, so success/failure claims ride here, not in prose.
        completed_tools = getattr(getattr(ledger, "execution", None), "completed_tools", None) or []
        actions, pending_actions = _extract_tool_actions(completed_tools)
        tool_trace = _build_tool_trace(completed_tools)
        external_sources = _build_external_sources(completed_tools)
        code_result = _build_code_result(completed_tools)
        grounded_note = _grounded_outcome_note(completed_tools)
        # Anti-hallucination gate: strip false success claims from the LLM
        # prose BEFORE the truthful grounded note is appended, so a staged
        # "I remembered X" / "rule created" claim never reaches the user.
        content, anti_flags = apply_anti_hallucination_gate(response.text, completed_tools)
        if grounded_note:
            content = f"{content}\n\n{grounded_note}" if content else grounded_note
        # Capability listing → unified rich "Your Access" document (GFM table
        # with page links), appended deterministically — never LLM prose.
        access_table = _grounded_access_table(completed_tools)
        if access_table:
            content = f"{content}\n\n{access_table}" if content else access_table
        # F1-B — annotate scoped entity mentions in the final answer as
        # serialized refs ([[kind:id:label]]) for the frontend EntityChip.
        # Runs on the finalized answer text, scoped to the requesting user so
        # no cross-tenant name ever resolves (deterministic, never-raising).
        content = _annotate_entity_mentions(content, host_user_id)
        # G-E: persist the F1–F3 gate flags so the §4.3 "truthfulness hit-rate"
        # metric is measurable from the turn_ledger (observability surface).
        await _record_truthfulness_gate(db=db, ledger=ledger, anti_flags=anti_flags)

        # C2 — surface calibrated confidence (Faculty 7): prefer the runner's
        # OWN label (it already maps clarify/disambiguate short-circuits →
        # "medium") and only fall back to the raw draft score on the normal
        # answer path. Honest uncertainty fires on the critic "I don't know"
        # path OR when the intent resolver short-circuited to a clarification
        # (conf≈0) — both are "not a confident answer" states, never a bluff
        # (RULE_23 — outcome words only, no raw floats or critic internals).
        _draft = getattr(ledger, "draft", None)
        _critic = getattr(ledger, "critic", None)
        _critic_verdict = (getattr(_critic, "verdict", "") or "").strip()
        _critic_flags = getattr(_critic, "flags", None) or []
        # The critic is the quality gate. A VETO verdict means the answer was
        # REJECTED as unsupported — it can NEVER surface as confident,
        # regardless of the draft's self-reported confidence float. Note: the
        # "ungrounded_claim" FLAG is advisory (the critic also attaches it to
        # `pass` verdicts for general-knowledge answers it cannot ground
        # against retrieval) — only the verdict is a rejection, so only `veto`
        # forces uncertainty. `knowledge_gap` (honest "I don't know") and the
        # clarify short-circuit are handled as their own honest states below.
        if _critic_verdict == "veto":
            confidence_label = "uncertain"
            honest_uncertainty = True
        else:
            confidence_label = response.confidence_label or _confidence_label(
                getattr(_draft, "confidence", None)
            )
            honest_uncertainty = bool(
                getattr(_draft, "model_used", "") == "honest_uncertainty"
                or "knowledge_gap" in _critic_flags
                or response.response_type == "clarification"
            )

        return {
            "status": "completed",
            "task_id": task_id,
            "result": {
                "content": content,
                "follow_up_questions": list(response.follow_ups or []),
                "execution_ms": int(ledger.total_latency_ms or 0),
                "actions": actions,
                "pending_actions": pending_actions,
                # F3-B — read-only, outcome-language tool trace for the
                # frontend "Considered…" planning pill (multi-step only).
                "tool_trace": tool_trace,
                # Wave I3-B — external web sources the answer drew on
                # ({"title","url","source","retrieved_at"}), independent of
                # the multi-step tool_trace filter.
                "external_sources": external_sources,
                # Wave I2-F — code-sandbox result ({"stdout","error","image_b64",
                # "table_rows","result"}) threaded to the frontend for chart/table/
                # scalar rendering, independent of the multi-step tool_trace filter.
                "code_result": code_result,
                # G-E: truthfulness gate signal (F1–F3), surfaced verbatim so
                # the workspace layer can reflect it and QA can assert on it.
                "truthfulness_flags": list(anti_flags),
                "truthful": not anti_flags,
                # C2 — calibrated confidence (Faculty 7): outcome-shaped signal
                # for the frontend confidence indicator + honest-uncertainty state.
                "confidence_label": confidence_label,
                "honest_uncertainty": honest_uncertainty,
                # Phase 21-A: surface per-turn usage so the workspace layer
                # can persist it on the generation at completion (cost is
                # computed from the ModelCatalog, never here).
                "usage": {
                    "prompt_tokens": int(ledger.prompt_tokens or 0),
                    "completion_tokens": int(ledger.completion_tokens or 0),
                    "total_tokens": int(ledger.total_tokens or 0),
                    "model": ledger.model_used or "",
                },
            },
        }


async def _record_truthfulness_gate(db, ledger, anti_flags: list[str]) -> None:
    """Persist the anti-hallucination gate flags as a ``turn_ledger`` stage.

    Writes one extra ``TurnLedgerRow`` (``stage="truthfulness_gate"``,
    ``stage_index=7``) per turn so the observability layer can compute the
    §4.3 truthfulness hit-rate (fraction of turns with zero gate flags).
    A clean turn records ``flags_json=None`` (the runner's convention for
    "no flags"); a flagged turn records the F1–F3 flag list.

    Best-effort and never-raising: observability must never fail a turn.
    """
    try:
        from ai.engine.cognition.turn.ledger import LedgerWitness

        await LedgerWitness().record_stage(
            db=db,
            turn_id=ledger.turn_id,
            instance_id=ledger.instance_id,
            conversation_id=ledger.conversation_id,
            host_user_id=ledger.host_user_id,
            stage="truthfulness_gate",
            stage_index=7,
            verdict="pass" if not anti_flags else "flag",
            flags=list(anti_flags),
        )
    except Exception as exc:  # pragma: no cover — best-effort observability
        logger.warning("Failed to record truthfulness gate flags: %s", exc)


def _confidence_label(score: float | None) -> str:
    """Map a 0.0-1.0 confidence score to an outcome label (RULE_23).

    ``high | medium | low | uncertain`` — mirrors the agent's confidence
    ladder so the frontend can render a calibrated indicator without ever
    seeing a raw float or critic internals.
    """
    if score is None:
        return ""
    if score >= 0.8:
        return "high"
    if score >= 0.6:
        return "medium"
    if score >= 0.35:
        return "low"
    return "uncertain"


# ── Chat tool-action surfacing (Sprint "fly to rule detail") ──────────────


def _carbon_instance_config(host_user_id: str | None = None) -> dict[str, Any]:
    """Thin loader — all domain knowledge lives in instances/carbon/instance.yaml.

    The engine core (cognition/, memory/, learning/) never imports from here.
    To bootstrap Pulse for a new project: replace instances/carbon/instance.yaml
    with instances/<project>/instance.yaml and point this loader at the new name.
    """
    from asgiref.sync import sync_to_async

    def _resolve_user_access() -> dict:
        from ai.access_manifest import build_user_access_manifest

        return build_user_access_manifest(host_user_id)

    try:
        user_access = _run_async(sync_to_async(_resolve_user_access, thread_sensitive=True)())
    except Exception:  # noqa: BLE001 - inventory is best-effort; never fatal
        logger.exception("Could not resolve user access manifest; using empty inventory")
        user_access = {
            "platform_name": _platform_display_name(),
            "access_level": "unknown",
            "platform_wide": False,
            "is_read_only": True,
            "apps": [],
            "capabilities": [],
            "modules": [],
            "routes": [],
        }

    from ai.engine.core.archetypes import load_instance_config

    # All Carbon-specific config (persona, api_catalog, navigation_routes,
    # domain_topics) is declared in instances/carbon/instance.yaml — not here.
    config: dict[str, Any] = load_instance_config("carbon")

    # Runtime-only fields that cannot live in a static file.
    config["display_name"] = config.get("display_name") or _platform_display_name()
    config["host_user_id"] = host_user_id
    config["user_access"] = user_access

    # E2: CBAC-filter the api_catalog so the LLM-facing "Available Host API
    # Endpoints" list (and the executor's catalog) only expose domain endpoints
    # the user may actually call. Anonymous users keep the full catalog — host
    # RBAC still rejects execution.
    config["api_catalog"] = _cbac_filter_api_catalog(
        config.get("api_catalog") or [], host_user_id
    )

    return config


def _cbac_filter_api_catalog(api_catalog: list, host_user_id: str | None) -> list:
    """CBAC-filter the ``api_catalog`` to endpoints the user may call (E2).

    Only domain-owned endpoints (those declared by a registered domain's
    ``get_tools()``) are filtered; platform-level endpoints (e.g. DQ) stay.
    The "may call" set is derived from the *same* registry-driven catalog used
    by ``CarbonHostAdapter.get_tool_catalog``, so the system-prompt tool list
    and the executor catalog never diverge.

    Fails open (returns ``api_catalog`` unchanged) when the user cannot be
    resolved or the registry is unavailable — host RBAC remains the backstop.
    """
    if not api_catalog or not host_user_id:
        return api_catalog

    from asgiref.sync import sync_to_async

    def _filter() -> list:
        from django.contrib.auth import get_user_model

        from ai.adapter.carbon import CarbonHostAdapter
        from ai.domain_protocol import get_domain, list_domains

        user_model = get_user_model()
        try:
            user = user_model.objects.get(pk=host_user_id)
        except (user_model.DoesNotExist, ValueError, TypeError):
            return api_catalog

        adapter = CarbonHostAdapter()
        catalog = adapter.get_tool_catalog(user, None)
        accessible = {
            tool.id.rsplit(".", 1)[-1]
            for tool in catalog.tools
            if tool.domain and tool.domain != "core"
        }

        # All domain-owned endpoint names (unfiltered) — used to decide which
        # catalog entries are domain-gated (vs. platform-level).
        domain_names: set[str] = set()
        for app_id in list_domains():
            for tool in get_domain(app_id)().get_tools():
                domain_names.add(tool.id.rsplit(".", 1)[-1])

        return [
            entry
            for entry in api_catalog
            if entry.get("name") not in domain_names
            or entry.get("name") in accessible
        ]

    try:
        return _run_async(sync_to_async(_filter, thread_sensitive=True)())
    except Exception:  # noqa: BLE001 - never let filtering break the chat path
        logger.exception("CBAC api_catalog filter failed; leaving catalog unchanged")
        return api_catalog


def _platform_display_name() -> str:
    """Config-driven platform name (settings, never hardcoded)."""
    from django.conf import settings as dj_settings

    title = getattr(dj_settings, "PLATFORM_TITLE", "") or ""
    name = getattr(dj_settings, "PLATFORM_NAME", "") or ""
    return title or name or "Data Trust Platform"


def _build_chat_user_info(host_user_id: str | None) -> dict | None:
    """Resolve user-facing identity for the chat system prompt.

    Returns ``None`` for anonymous/unresolvable users so the engine's default
    "anonymous" context applies (which itself never fabricates identity).
    Only user-facing fields travel here (name/roles) — never internal ids or
    secrets (RULE_23).
    """
    if not host_user_id:
        return None

    from asgiref.sync import sync_to_async
    from django.contrib.auth import get_user_model

    def _resolve() -> dict | None:
        User = get_user_model()
        try:
            user = User.objects.get(pk=host_user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            return None
        roles: list[str] = []
        try:
            from accounts.models import ScopedRole

            roles = list(
                ScopedRole.objects.filter(user=user, is_active=True)
                .values_list("group__name", flat=True)
                .distinct()
            )
        except Exception:  # noqa: BLE001 - roles are best-effort decoration
            pass
        display_name = (
            getattr(user, "display_name", "") or user.get_full_name() or user.username
        )
        return {
            "username": user.username,
            "display_name": display_name,
            "email": user.email or "",
            "roles": roles,
        }

    try:
        return _run_async(sync_to_async(_resolve, thread_sensitive=True)())
    except Exception:  # noqa: BLE001 - identity is best-effort, never fatal
        logger.exception("Could not resolve chat user_info; using anonymous")
        return None


def _classify_pending(data: dict, item: dict) -> tuple[str | None, dict | None]:
    """Classify a staged (``requires_confirmation``) tool result by its kind.

    Anti-fabrication gate: a staged proposal must be surfaced under its true
    kind — a memory write, a DQ rule, or a generic host mutation — and never
    as an empty "DQ rule" card when the result carries no rule definition.

    (Historical bug: ``learn_fact``/``forget_fact`` return
    ``requires_confirmation=True`` with NO ``proposed_rule``/``proposed_body``,
    but the old code treated every staged result as a DQ rule and fabricated
    ``proposed_rule={}`` + ``proposed_body=None`` — the "Proposed DQ rule
    'rule' with an empty {} body" card the user saw.)
    """
    method = str(data.get("method") or "").upper()
    operation = str(data.get("operation") or "").lower()
    tool_name = str(item.get("tool_name") or "").lower()

    # 1. Memory writes (learn_fact / forget_fact → method=MEMORY,
    #    operation=learn|forget). Surfaced truthfully, never as a DQ rule.
    if method == "MEMORY" or operation in {"learn", "forget"} or tool_name in {"learn_fact", "forget_fact"}:
        return "memory", {
            "execution_id": str(data["execution_id"]),
            "tool": tool_name,
            "operation": operation or ("forget" if "forget" in tool_name else "learn"),
            "confirmation_message": str(data.get("confirmation_message") or ""),
            "fact": str(data.get("fact") or data.get("content") or ""),
            "category": str(data.get("category") or ""),
        }

    # 2. DQ rule — only when there is a REAL rule definition (non-empty name).
    proposed_rule = data.get("proposed_rule")
    if isinstance(proposed_rule, dict) and (proposed_rule.get("name") or "").strip():
        name = str(proposed_rule.get("name") or "").strip()
        rtype = str(proposed_rule.get("type") or "").strip()
        return "dq_rule", {
            "execution_id": str(data["execution_id"]),
            "tool": tool_name,
            "confirmation_message": (
                str(data.get("confirmation_message") or "")
                or f"Create DQ rule '{name}' ({rtype})?"
            ),
            "proposed_rule": proposed_rule,
            "proposed_body": data.get("proposed_body"),
            "validation": data.get("validation"),
        }

    # 3. Generic host mutation (call_host_api) — a real endpoint/method.
    if method or data.get("endpoint"):
        return "host", {
            "execution_id": str(data["execution_id"]),
            "tool": tool_name,
            "method": method,
            "endpoint": str(data.get("endpoint") or ""),
            "body": data.get("body") or data.get("params") or {},
            "confirmation_message": str(data.get("confirmation_message") or ""),
        }

    # 4. Unrecognized — refuse to fabricate a card.
    return None, None


def _extract_tool_actions(completed_tools: list[dict]) -> tuple[list[dict], list[dict]]:
    """Derive machine-readable actions from the turn's executed tools.

    Returns ``(actions, pending_actions)``:
      * ``actions`` — navigate-style actions (``{"action": "navigate"}`` in a
        tool result); deduped by route, last occurrence wins.
      * ``pending_actions`` — staged, confirmation-gated proposals
        (``requires_confirmation`` + ``execution_id``) awaiting the user,
        each tagged with its true ``kind`` (memory / dq_rule / host).
    """
    actions: list[dict] = []
    pending_actions: list[dict] = []
    seen_routes: set[str] = set()

    for item in completed_tools or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        raw = item.get("result")
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue

        if data.get("action") == "navigate":
            route = str(data.get("route") or "").strip()
            if not route or route in seen_routes:
                continue
            seen_routes.add(route)
            actions.append({
                "type": "navigate",
                "route": route,
                "label": str(data.get("label") or "Open"),
                "summary": str(data.get("summary") or ""),
            })

        if data.get("action") == "plan_created":
            # plan_task outcome — jump the user straight to the workspace
            # Tasks panel where approve/run/edit/fork/pause live. The panel is
            # a workspace surface (not a URL route), so the action type is
            # ``open_panel`` and the UI switches the active panel + focuses
            # the created plan (RULE_23 — product copy, plan id, no engine
            # names).
            plan_id = str(data.get("plan_id") or "").strip()
            actions.append({
                "type": "open_panel",
                "panel": "tasks",
                "plan_id": plan_id,
                "label": "Open in Tasks",
                "summary": "Review, approve and run the plan",
            })

        if data.get("action") == "plan_approved":
            # approve_plan outcome — the plan is now a real runnable task.
            # Surface the Tasks panel so the user can run it (execution is a
            # separate, explicit user action — never auto-run from chat).
            plan_id = str(data.get("plan_id") or "").strip()
            actions.append({
                "type": "open_panel",
                "panel": "tasks",
                "plan_id": plan_id,
                "label": "Run the plan",
                "summary": "Approved — open Tasks to run and observe each step",
            })

        if data.get("action") == "plan_edited":
            # edit_plan outcome — re-open the Tasks panel on the revised plan
            # so the user can review the step diff and (re-)approve.
            plan_id = str(data.get("plan_id") or "").strip()
            actions.append({
                "type": "open_panel",
                "panel": "tasks",
                "plan_id": plan_id,
                "label": "Review revised plan",
                "summary": "Check the changed steps and approve when settled",
            })

        # export_document outcome — one download link per generated file.
        if data.get("action") == "download":
            files = data.get("files") or []
            if not isinstance(files, list) or not files:
                files = [{"filename": data.get("filename") or "document"}]
            for f in files:
                if not isinstance(f, dict):
                    continue
                filename = str(f.get("filename") or "").strip()
                if not filename:
                    continue
                actions.append({
                    "type": "download",
                    "path": str(f.get("path") or f"/media/ai_exports/{filename}"),
                    "filename": filename,
                    "label": str(f.get("label") or f"Download {filename}"),
                    "summary": str(f.get("format") or "").upper(),
                })

        # Capability listing (list_my_capabilities): emit one navigate action
        # per scoped page link — the UI renders these as small buttons under
        # the listing reply.
        if isinstance(data.get("routes"), list):
            for link in data["routes"]:
                if not isinstance(link, dict):
                    continue
                route = str(link.get("route") or "").strip()
                if not route or route in seen_routes:
                    continue
                seen_routes.add(route)
                actions.append({
                    "type": "navigate",
                    "route": route,
                    "label": str(link.get("label") or "Open"),
                    "summary": str(link.get("summary") or ""),
                })

        if data.get("requires_confirmation") and data.get("execution_id"):
            kind, payload = _classify_pending(data, item)
            if kind is not None and payload is not None:
                payload["kind"] = kind
                pending_actions.append(payload)

    return actions, pending_actions


#: Outcome-language step labels for common tools (RULE_23 — human-readable,
#: no raw tool args / result JSON, no engine stage names).  F3-B "Considered…"
#: planning pill.
_TOOL_STEP_LABELS: dict[str, str] = {
    "search_knowledge": "Searched the knowledge base",
    "get_entity_details": "Looked up entity details",
    "learn_fact": "Saved a fact to memory",
    "forget_fact": "Removed a fact from memory",
}


def _build_tool_trace(completed_tools: list[dict]) -> list[dict]:
    """Read-only, outcome-language ``tool_trace`` for the "Considered…" pill.

    Each step is ``{"step_label", "tool_id", "duration_ms"}``.  Only successful
    (no ``error``) and non-staged (no ``requires_confirmation``) tools are
    included, and the trace is only emitted for multi-step (>=2) responses so
    single-tool turns don't clutter the UI (F3-B contract).

    ``step_label`` uses outcome language only (RULE_23): a non-empty
    ``summary`` / ``label`` already in the result, else a static
    ``_TOOL_STEP_LABELS`` entry, else "Queried live platform data" for
    ``call_host_api*``, else a generic step label.  Never raises — malformed
    results are skipped rather than surfaced.
    """
    steps: list[dict] = []
    for item in completed_tools or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        try:
            raw = item.get("result")
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            data = None
        if isinstance(data, dict) and data.get("requires_confirmation"):
            continue

        step_label = None
        if isinstance(data, dict):
            for key in ("summary", "label"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    step_label = value.strip()
                    break
        if step_label is None:
            tool_name = str(item.get("tool_name") or "")
            step_label = (
                _TOOL_STEP_LABELS.get(tool_name)
                or ("Queried live platform data" if tool_name.startswith("call_host_api") else None)
                or "Completed a background step"
            )

        try:
            duration_ms = int(item.get("latency_ms") or 0)
        except (TypeError, ValueError):
            duration_ms = 0
        steps.append({
            "step_label": step_label,
            "tool_id": str(item.get("tool_name") or ""),
            "duration_ms": duration_ms,
        })

    if len(steps) < 2:
        return []
    return steps


def _build_external_sources(completed_tools: list[dict]) -> list[dict]:
    """External-source provenance for answers that drew on the open web."""
    sources: list[dict] = []
    for item in completed_tools or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        raw = item.get("result")
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict) or data.get("source") != "external_web":
            continue
        retrieved_at = data.get("retrieved_at")
        for r in data.get("results") or []:
            if isinstance(r, dict) and r.get("url"):
                sources.append({
                    "title": r.get("title") or "",
                    "url": r.get("url"),
                    "source": r.get("source") or "external_web",
                    "retrieved_at": r.get("retrieved_at") or retrieved_at,
                })
    return sources


def _build_code_result(completed_tools: list[dict]) -> dict | None:
    """Code-sandbox result (I2-F) for answers that ran ``code_execute``.

    Returns the sandbox dict verbatim ({"stdout","error","image_b64",
    "table_rows","result"}), or ``None`` when no ``code_execute`` tool ran.
    Never raises — malformed results are skipped.
    """
    for item in completed_tools or []:
        if not isinstance(item, dict):
            continue
        # Match the tool FIRST, before any error-skip. A user-code failure in
        # ``code_execute`` is "nested-error promoted" by ExecuteWitness: the
        # inner sandbox ``error`` string is lifted to ``item["error"]`` while
        # the FULL sandbox dict (still carrying its own ``error`` key) is
        # preserved in ``item["result"]``. Skipping on ``item["error"]`` here
        # would drop that dict and hide the friendly error state from the UI.
        if str(item.get("tool_name") or "") != "code_execute":
            continue
        raw = item.get("result")
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        # Must look like the sandbox shape (not a guardrail-cancel / unknown-tool
        # payload whose ``result`` is None). The sandbox dict itself carries
        # ``error`` (None on success, traceback on user-code failure) so the
        # frontend can render the friendly error state when it is non-empty.
        if not any(k in data for k in ("stdout", "error", "image_b64", "table_rows", "result")):
            continue
        return data
    return None


#: Outcome-oriented copy for a failed tool action (RULE_23 — never leak raw
#: internal exception text into user-facing chat; QA F2).
_FAILED_ACTION_COPY = (
    "⚠️ That action didn't complete — nothing was created or changed. "
    "Please try again in a moment."
)


def _clarification_question(missing: list[str] | None) -> str:
    """Friendly next-step question when a tool needs more info to proceed.

    ``missing`` carries internal field ids (``data_table`` / ``data_field``);
    this maps them to plain product language so the user is told *what* to
    provide rather than a generic "try again" (RULE_23: no internal names).
    """
    missing = list(missing or [])
    needs_field = "data_field" in missing
    needs_table = "data_table" in missing
    if needs_field and needs_table:
        return (
            "ℹ️ I need to know which table and field this rule applies to "
            "before I can stage it — which column should I check?"
        )
    if needs_field:
        return "ℹ️ Which field/column should this rule apply to?"
    if needs_table:
        return "ℹ️ Which table should this rule apply to?"
    return "ℹ️ A little more information is needed before I can stage this."


def _md_escape(text: str) -> str:
    """Escape GFM table-cell metacharacters (``|`` and newlines)."""
    return str(text or "").replace("|", "\\|").replace("\n", " ")


def _md_link(label: str, route: str) -> str:
    """Internal page link for a table cell; '—' when no route exists."""
    route = str(route or "").strip()
    if not route:
        return "—"
    return f"[{label}]({route})"


def _grounded_access_table(completed_tools: list[dict]) -> str:
    """Deterministic, capability-scoped ``## Your Access`` document.

    When ``list_my_capabilities`` ran this turn, render its machine-readable
    inventory as a rich GFM table (work areas / apps / modules with page
    links).  The generic markdown renderer turns it into a formal table with
    links — the format is platform-owned and unified, never improvised by the
    LLM (no ad-hoc, per-use-case presentation).

    Returns ``""`` when the tool did not run or had nothing to show, so the
    assistant text is the only content in those turns.
    """
    for item in completed_tools or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        raw = item.get("result")
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict) or data.get("error"):
            continue
        if data.get("action") != "list_capabilities":
            continue

        sections: list[str] = []

        work_areas = [wa for wa in data.get("capabilities") or [] if isinstance(wa, dict)]
        rows = "\n".join(
            f"| {_md_escape(wa.get('label') or wa.get('key') or '')}"
            f" | {_md_escape(wa.get('description') or '')}"
            f" | {_md_link('Open', wa.get('route') or '')} |"
            for wa in work_areas
            if wa.get("route")
        )
        if rows:
            sections.append(
                "### Work areas\n\n"
                "| Work area | Description | Open |\n"
                "|---|---|---|\n" + rows
            )

        apps = [a for a in data.get("apps") or [] if isinstance(a, dict)]
        rows = "\n".join(
            f"| {_md_escape(a.get('name') or a.get('key') or '')}"
            f" | {_md_escape(a.get('description') or '')}"
            f" | {_md_link('Open', a.get('route') or '')} |"
            for a in apps
            if a.get("route")
        )
        if rows:
            sections.append(
                "### Apps you can open\n\n"
                "| App | Description | Open |\n"
                "|---|---|---|\n" + rows
            )

        modules = [m for m in data.get("modules") or [] if isinstance(m, dict)]
        rows = "\n".join(
            f"| {_md_escape(m.get('name') or m.get('key') or '')}"
            f" | {_md_link('Open', m.get('route') or '')} |"
            for m in modules
            if m.get("route")
        )
        if rows:
            sections.append(
                "### Data areas (modules)\n\n"
                "| Data area | Open |\n"
                "|---|---|\n" + rows
            )

        if not sections:
            return ""

        return "## Your Access\n\n" + "\n\n".join(sections)

    return ""


def _grounded_outcome_note(completed_tools: list[dict]) -> str:
    """Deterministic summary of what the tools actually did (anti-fabrication).

    The LLM drafts text before tools run; without this patch a hallucinated
    "created successfully" could stand.  This note only reports real tool
    outcomes — staging proposals and failures — appended to the assistant text.
    """
    lines: list[str] = []
    for item in completed_tools or []:
        if not isinstance(item, dict):
            continue
        if item.get("error"):
            lines.append(_FAILED_ACTION_COPY)
            continue
        raw = item.get("result")
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if data.get("error"):
            # A structured clarification (e.g. a deterministic DQ rule missing
            # its field binding) is a user-facing question, not an internal
            # exception — surface the actionable next step instead of the
            # generic "try again" copy.
            clarification = data.get("clarification") or {}
            if clarification.get("needed"):
                lines.append(_clarification_question(clarification.get("missing")))
            else:
                lines.append(_FAILED_ACTION_COPY)
            continue
        if data.get("requires_confirmation"):
            kind, payload = _classify_pending(data, item)
            if kind == "memory":
                operation = (payload or {}).get("operation") or "learn"
                fact = (payload or {}).get("fact") or ""
                if operation == "forget":
                    lines.append(
                        f"✅ Proposed to forget: {fact} — nothing was archived "
                        "yet. Confirm below to archive it (Agent mode required)."
                    )
                else:
                    lines.append(
                        f"✅ Proposed to remember: {fact} — nothing was stored "
                        "yet. Confirm below to save it (Agent mode required)."
                    )
            elif kind == "dq_rule":
                proposed = data.get("proposed_rule") or {}
                name = str(proposed.get("name") or "").strip() or "rule"
                lines.append(
                    f"✅ Proposed DQ rule '{name}' validated and staged — nothing "
                    "was created yet. Confirm & create below (Agent mode required)."
                )
            elif kind == "host":
                method = str(data.get("method") or "").strip() or "action"
                endpoint = str(data.get("endpoint") or "").strip()
                lines.append(
                    f"✅ Proposed {method} {endpoint} — staged, nothing executed "
                    "yet. Confirm below to proceed (Agent mode required)."
                )
            # kind is None → unrecognized staged result; emit nothing rather
            # than fabricate a DQ-rule note (anti-fabrication).
        elif data.get("action") == "navigate":
            summary = str(data.get("summary") or data.get("label") or "").strip()
            if summary:
                lines.append(f"✅ {summary}")
        elif data.get("action") == "plan_created":
            # plan_task outcome (RULE_23 — product terms: plan, steps,
            # pending_approval, Tasks panel; never engine class names).
            plan_id = str(data.get("plan_id") or "").strip()
            short_id = plan_id[:8] if plan_id else ""
            steps = data.get("steps") or []
            status = str(data.get("status") or "pending_approval")
            step_copy = f"{len(steps)} step{'s' if len(steps) != 1 else ''}"
            if short_id:
                lines.append(
                    f"✅ Plan {short_id} drafted ({step_copy}, status: "
                    f"{status}) — nothing has run yet. Review and approve it "
                    "in the Tasks panel to execute."
                )
            else:
                lines.append(
                    f"✅ Plan drafted ({step_copy}, status: {status}) — "
                    "nothing has run yet. Review and approve it in the "
                    "Tasks panel to execute."
                )
            for s in steps:
                intent = str(s.get("intent") or "").strip()
                if intent:
                    lines.append(f"  • {intent}")
        elif data.get("action") == "plan_edited":
            plan_id = str(data.get("plan_id") or "").strip()
            short_id = plan_id[:8] if plan_id else ""
            steps = data.get("steps") or []
            diff = data.get("diff") or {}
            step_copy = f"{len(steps)} step{'s' if len(steps) != 1 else ''}"
            lines.append(
                f"✅ Plan {short_id} updated ({step_copy}; "
                f"added {len(diff.get('added', []))}, "
                f"removed {len(diff.get('removed', []))}, "
                f"changed {len(diff.get('changed', []))}) — still awaiting "
                "your approval before anything runs."
            )
        elif data.get("action") == "plan_approved":
            plan_id = str(data.get("plan_id") or "").strip()
            short_id = plan_id[:8] if plan_id else ""
            steps = data.get("steps") or []
            step_copy = f"{len(steps)} step{'s' if len(steps) != 1 else ''}"
            lines.append(
                f"✅ Plan {short_id} approved ({step_copy}) — it is now a "
                "runnable task. Open the Tasks panel to run it."
            )
        elif data.get("action") == "download":
            files = data.get("files") or []
            if isinstance(files, list) and files:
                names = ", ".join(str(f.get("filename") or "") for f in files)
                lines.append(f"✅ Generated: {names} — download below.")
    return "\n\n".join(lines)


# ── F1-B entity mention annotation (deterministic answer post-processor) ──

# Cap the scoped entity lookup set per kind so a large tenant can never make
# this post-processor unbounded. Names are resolved from the ORM (never
# hardcoded) and matched longest-first, each name replaced at most once.
_ANNOTATION_MAX_PER_KIND = 200


def _sanitize_annotation_label(name: str) -> str:
    """Strip serialized-ref metacharacters from a display label.

    ``]``, ``:``, ``[[`` and ``]]`` are reserved by the ``[[kind:id:label]]``
    format; removing them keeps a hostile/odd entity name from breaking the
    chip syntax. An emptied label is skipped by the caller.
    """
    label = str(name or "")
    label = label.replace("[[", "").replace("]]", "")
    label = label.replace(":", "").replace("]", "")
    return label


def _annotation_protected_spans(text: str) -> list[tuple[int, int]]:
    """Return ``(start, end)`` spans the annotator must never rewrite.

    Protected: fenced code blocks (triple backticks), already-serialized
    ``[[...]]`` spans, and URLs (``scheme://`` or ``www.``).
    """
    spans: list[tuple[int, int]] = []
    pattern = re.compile(
        r"```.*?```"                              # fenced code block
        r"|\[\[.*?\]\]"                           # already-serialized ref
        r"|[A-Za-z][A-Za-z0-9+.-]*://\S+"         # scheme:// URL
        r"|www\.[A-Za-z0-9.-]+(?:/\S*)?",         # www. URL
        re.DOTALL,
    )
    for match in pattern.finditer(text):
        spans.append((match.start(), match.end()))
    return spans


def _resolve_annotation_user(scope) -> Any:
    """Resolve the ``scope`` user handle to a Django ``User`` (or ``None``).

    Accepts either a ``Scope``-like object (``ai.protocol.Scope`` exposes
    ``user_identifier``) or a raw user id (str/int) — the latter is what
    ``_run_chat`` passes via ``host_user_id``. ``None`` on any failure.
    """
    if scope is None:
        return None
    if hasattr(scope, "user_identifier"):
        uid = scope.user_identifier
    else:
        uid = scope
    if uid is None or (isinstance(uid, str) and not uid.strip()):
        return None
    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        return User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError):
        return None


def _collect_annotatable_entities(user) -> list[dict[str, str]]:
    """Resolve user-accessible entity names into ``{kind, id, name}`` descriptors.

    Scoping reuses ``accounts.rbac_utils``' canonical visibility helpers — the
    same helpers the emissions/DQ read views use — so a name the user cannot
    access never resolves (no cross-tenant leakage):

      * ``get_visible_module_ids`` → ``None`` (unrestricted) or a set of module
        ids; Modules, DataTables (via ``module_id``) and DQRules (via
        ``field_assignments → data_table → module``) are filtered by it.
      * ``get_visible_org_units`` → the user's visible org subtree (already
        ``is_active``-filtered).

    ``field``/``employee``/``EmissionRecord`` are intentionally out of scope.
    Lookups are bounded (``_ANNOTATION_MAX_PER_KIND``) and never raise — the
    caller degrades to the unchanged answer on any failure.
    """
    from accounts.rbac_utils import get_visible_module_ids, get_visible_org_units
    from core.models import Module
    from dataschema.models import DataTable
    from dq.models import DQRule
    from mdm.models import OrgUnit

    entities: list[dict[str, str]] = []

    module_ids = get_visible_module_ids(user)
    unrestricted = module_ids is None

    module_qs = Module.objects.all()
    if not unrestricted:
        module_qs = module_qs.filter(id__in=module_ids)
    for module in module_qs.order_by("name", "pk")[:_ANNOTATION_MAX_PER_KIND]:
        entities.append(
            {"kind": "module", "id": str(module.id), "name": module.name}
        )

    for org_unit in get_visible_org_units(user)[:_ANNOTATION_MAX_PER_KIND]:
        entities.append(
            {"kind": "org-unit", "id": str(org_unit.id), "name": org_unit.name}
        )

    table_qs = DataTable.objects.filter(is_archived=False)
    if not unrestricted:
        table_qs = table_qs.filter(module_id__in=module_ids)
    for table in table_qs.order_by("name", "pk")[:_ANNOTATION_MAX_PER_KIND]:
        entities.append({"kind": "table", "id": str(table.id), "name": table.name})

    rule_qs = DQRule.objects.filter(archived=False, is_active=True)
    if not unrestricted:
        rule_qs = rule_qs.filter(
            field_assignments__data_table__module_id__in=module_ids
        ).distinct()
    for rule in rule_qs.order_by("name", "pk")[:_ANNOTATION_MAX_PER_KIND]:
        entities.append({"kind": "rule", "id": str(rule.id), "name": rule.name})

    return entities


def _annotate_entity_mentions(answer: str, scope) -> str:
    """Annotate scoped entity mentions in the final answer as ``[[kind:id:label]]``.

    Deterministic, budgeted and never-raising: on any failure the answer is
    returned unchanged. Resolves the user-accessible DataTable/DQRule/Module/
    OrgUnit names via the ORM (scoped with ``accounts.rbac_utils`` visibility
    helpers), then matches them case-insensitively on word boundaries,
    longest-name-first, each name replaced at most once. Fenced code blocks,
    URLs and pre-existing ``[[...]]`` spans are left untouched.
    """
    try:
        if not answer:
            return answer
        user = _resolve_annotation_user(scope)
        if user is None:
            return answer
        descriptors = _collect_annotatable_entities(user)
        if not descriptors:
            return answer

        # Dedupe by casefolded name (first occurrence wins → deterministic id).
        unique: dict[str, dict[str, str]] = {}
        for descriptor in descriptors:
            name = str(descriptor.get("name") or "").strip()
            if not name:
                continue
            key = name.casefold()
            if key not in unique:
                unique[key] = {
                    "kind": str(descriptor.get("kind") or ""),
                    "id": str(descriptor.get("id") or ""),
                    "name": name,
                }
        candidates = sorted(
            unique.values(), key=lambda d: len(d["name"]), reverse=True
        )

        # Occupancy mask: protected spans + spans already consumed by an
        # earlier (longer) match. A later, shorter name can never overlap one.
        occupied = [False] * len(answer)
        for start, end in _annotation_protected_spans(answer):
            for index in range(start, end):
                occupied[index] = True

        replacements: list[tuple[int, int, str]] = []
        for candidate in candidates:
            label = _sanitize_annotation_label(candidate["name"])
            if not label:
                continue
            token = f"[[{candidate['kind']}:{candidate['id']}:{label}]]"
            pattern = re.compile(
                r"(?<![\w])" + re.escape(candidate["name"]) + r"(?![\w])",
                re.IGNORECASE,
            )
            for match in pattern.finditer(answer):
                start, end = match.start(), match.end()
                if any(occupied[start:end]):
                    continue
                for index in range(start, end):
                    occupied[index] = True
                replacements.append((start, end, token))
                break  # each entity name is replaced at most once

        if not replacements:
            return answer

        replacements.sort(key=lambda item: item[0])
        parts: list[str] = []
        cursor = 0
        for start, end, token in replacements:
            parts.append(answer[cursor:start])
            parts.append(token)
            cursor = end
        parts.append(answer[cursor:])
        return "".join(parts)
    except Exception:  # noqa: BLE001 - never raise from an answer post-processor
        logger.exception("Entity mention annotation failed; returning answer unchanged")
        return answer


# ── Anti-hallucination gate (post-S5, deterministic) ──────────────────────

_STAGED = "staged"
_FAILED = "failed"
_SUCCEEDED = "succeeded"

# Success-claim patterns per mutation/staging tool. When a tool's true outcome
# is staged or failed, any matching sentence in the LLM prose is a
# hallucination and is stripped. The deterministic `_grounded_outcome_note`
# supplies the truthful replacement, so the user never sees a false "done".
_CLAIM_PATTERNS: dict[str, "re.Pattern"] = {
    "learn_fact": re.compile(
        r"(?:\bI(?:'ve| have)?\s+)?(?:remembered|memorized|stored|saved|noted)\b[^.!?\n]*[.!?]?",
        re.IGNORECASE,
    ),
    "forget_fact": re.compile(
        r"(?:\bI(?:'ve| have)?\s+)?(?:forgotten|forgot|removed\s+from\s+memory)\b[^.!?\n]*[.!?]?",
        re.IGNORECASE,
    ),
    "create_dq_rule": re.compile(
        r"(?:\bI(?:'ve| have)?\s+)?(?:created|added)\b[^.!?\n]*\brule\b[^.!?\n]*[.!?]?",
        re.IGNORECASE,
    ),
    "plan_task": re.compile(
        r"(?:\bI(?:'ve| have)?\s+)?(?:created|generated)\b[^.!?\n]*\b(?:task|plan)\b[^.!?\n]*[.!?]?",
        re.IGNORECASE,
    ),
}

# Future-tense staging promises that are false when a staging tool FAILED
# (no confirmation card was created). "I will stage a rule… confirm to
# proceed" contradicts a failed outcome and is stripped so the grounded
# clarification/failure note stands alone. Applied only on _FAILED.
_FAILED_STAGING_CLAIMS: dict[str, "re.Pattern"] = {
    "create_dq_rule": re.compile(
        r"\bI\s+(?:will|'ll)\s+(?:stage|create|add|propose|write)\b[^.!?\n]*[.!?]?"
        r"|\b(?:confirm|click|press|hit)\s+(?:to\s+)?(?:proceed|create|confirm)\b[^.!?\n]*[.!?]?",
        re.IGNORECASE,
    ),
}

# A concrete-work execution claim ("I ran the audit", "I completed the
# validation"). Without a successful tool result, this is fabricated reasoning.
_EXECUTION_NARRATION_RE = re.compile(
    r"\bI\s+(?:executed|ran|performed|carried\s+out|completed|finished)\s+(?:the\s+)?"
    r"(?:validation|check|audit|analysis|query|workflow|task|plan|job|rule|test|"
    r"scan|assessment|comparison|review|report|export|migration|import|sync|cleanup)\b"
    r"[^.!?\n]*[.!?]?",
    re.IGNORECASE,
)

# A false memory-capability DENIAL ("I don't have memory", "I won't retain
# this"). When learn_fact/forget_fact actually staged a proposal (or stored
# something), this prose contradicts the tool result — the propose→confirm
# flow IS the memory system. Stripped so the truthful grounded note stands.
_MEMORY_DENIAL_RE = re.compile(
    r"\bI\s+(?:currently\s+)?(?:do\s+not|don'?t)\s+have\s+memory\s+enabled\b[^.!?\n]*[.!?]?"
    r"|\bI\s+(?:don'?t|do\s+not|cannot|can'?t|won'?t|will\s+not)\s+"
    r"(?:retain|remember|store|keep)\s+(?:this|that|it|the\s+information|anything)\b[^.!?\n]*[.!?]?"
    r"|\bI\s+(?:can'?t|cannot)\s+(?:remember|retain|store)\b[^.!?\n]*[.!?]?"
    r"|\b(?:my\s+)?memory\s+is\s+not\s+(?:enabled|available|on)\b[^.!?\n]*[.!?]?"
    r"|\b(?:long-?term\s+)?memory\s+is\s+not\s+(?:enabled|available|on)\b[^.!?\n]*[.!?]?"
    # Conditional / future framing: the LLM hedges that memory might become
    # available later — but a learn/forget proposal is memory working NOW.
    r"|\b(?:if|when|once|unless|until|should)\s+(?:my\s+|long-?term\s+|standalone\s+|"
    r"persistent\s+)?memory\s+(?:is|becomes|gets|were|was|has\s+been)\s+"
    r"(?:enabled|available|on|activated|turned\s+on|connected)\b[^.!?\n]*[.!?]?"
    r"|\bI\s+(?:can|could|will|would|may|might)\s+(?:let\s+you\s+know\s+what\s+I\s+"
    r"(?:remember|recall|retain|store)|tell\s+you\s+what\s+I\s+(?:remember|recall|retain))\b"
    r"[^.!?\n]*[.!?]?",
    re.IGNORECASE,
)

# LLM provider refusal/error messages that contradict a successful or staged
# tool execution. When tools executed successfully or were staged for
# confirmation, generic error messages like "I wasn't able to generate a
# response" are false — the tool DID work and produced a valid result.
_LLM_REFUSAL_RE = re.compile(
    r"\bI\s+(?:was\s+not|wasn'?t)\s+able\s+to\s+(?:generate|provide|create|complete)\s+(?:a\s+)?(?:response|reply|answer)\b[^.!?\n]*[.!?]?"
    r"|\bI\s+(?:could\s+not|couldn'?t|can'?t|cannot)\s+(?:generate|provide|create|complete|process)\s+(?:a\s+)?(?:response|reply|answer|that)\b[^.!?\n]*[.!?]?"
    r"|\bThis\s+(?:may|might)\s+be\s+a\s+temporary\s+issue\b[^.!?\n]*[.!?]?"
    r"|\bPlease\s+try\s+again\s+(?:in\s+a\s+moment|later|or\s+rephrase)\b[^.!?\n]*[.!?]?"
    r"|\bI\s+(?:don'?t|do\s+not)\s+have\s+(?:the\s+)?(?:ability|capability|permission)\s+to\b[^.!?\n]*[.!?]?"
    r"|\bI\s+(?:encountered|experienced)\s+(?:an\s+)?(?:error|issue|problem)\b[^.!?\n]*[.!?]?"
    r"|\bSomething\s+went\s+wrong\b[^.!?\n]*[.!?]?",
    re.IGNORECASE,
)


def _classify_tool_outcomes(completed_tools: list[dict]) -> dict[str, str]:
    """Map tool_name → staged/failed/succeeded from executed tool results.

    Grounds the anti-hallucination gate: only a real, non-empty, non-error,
    non-staged result counts as a success.
    """
    outcomes: dict[str, str] = {}
    for item in completed_tools or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("tool_name") or "")
        if not name:
            continue
        if item.get("error"):
            outcomes[name] = _FAILED
            continue
        raw = item.get("result")
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            outcomes[name] = _FAILED
            continue
        if not isinstance(data, dict):
            # Non-dict, non-error result (bare string/scalar) counts as success
            # only if truthy; an empty result is a failure.
            outcomes[name] = _SUCCEEDED if raw else _FAILED
            continue
        if data.get("error"):
            outcomes[name] = _FAILED
        elif data.get("requires_confirmation"):
            outcomes[name] = _STAGED
        else:
            outcomes[name] = _SUCCEEDED
    return outcomes


def apply_anti_hallucination_gate(
    text: str,
    completed_tools: list[dict],
) -> tuple[str, list[str]]:
    """Strip false success claims from the LLM prose (deterministic).

    The LLM drafts text before tools run, so it can claim "I remembered X" or
    "rule created" when the tool only *staged* a proposal (or failed). This
    gate removes those claims; the deterministic grounded note supplies the
    truth. It also removes fabricated execution narratives ("I ran the audit")
    when no tool actually succeeded.

    Returns ``(corrected_text, flags)``.
    """
    if not text:
        return text, []

    outcomes = _classify_tool_outcomes(completed_tools)
    flags: list[str] = []
    corrected = text

    # Gate 1 — anti-hallucination: a staged/failed tool's success claim is
    # removed so the grounded note is the only thing that speaks to the result.
    for tool_name, outcome in outcomes.items():
        if outcome == _SUCCEEDED:
            continue
        pattern = _CLAIM_PATTERNS.get(tool_name)
        if pattern is not None:
            corrected, removed = pattern.subn("", corrected)
            if removed:
                flags.append(f"{outcome}_success_claim_corrected:{tool_name}")
        # A FAILED staging tool cannot promise a confirmation flow.
        if outcome == _FAILED:
            failed_pattern = _FAILED_STAGING_CLAIMS.get(tool_name)
            if failed_pattern is not None:
                corrected, removed = failed_pattern.subn("", corrected)
                if removed:
                    flags.append(f"failed_staging_claim_corrected:{tool_name}")

    # Gate 2 — anti-reasoning: no tool succeeded, yet the prose narrates a
    # concrete execution ("I ran the audit"). That chain is fabricated.
    if corrected and not any(o == _SUCCEEDED for o in outcomes.values()):
        corrected, removed = _EXECUTION_NARRATION_RE.subn("", corrected)
        if removed:
            flags.append("fabricated_reasoning_chain_corrected")

    # Gate 3 — anti-false-denial: a memory tool actually staged (or stored)
    # something, yet the prose claims "I don't have memory" / "I won't retain
    # this". That denial contradicts the tool result and is stripped.
    memory_engaged = any(
        name in ("learn_fact", "forget_fact") and outcome in (_STAGED, _SUCCEEDED)
        for name, outcome in outcomes.items()
    )
    if corrected and memory_engaged:
        corrected, removed = _MEMORY_DENIAL_RE.subn("", corrected)
        if removed:
            flags.append("false_memory_denial_corrected")

    # Gate 4 — anti-refusal: any tool succeeded or was staged, yet the prose
    # contains a generic LLM error/refusal message ("I wasn't able to generate
    # a response", "This may be a temporary issue"). These contradict the
    # successful tool execution and are stripped so the grounded note stands alone.
    any_tool_worked = any(outcome in (_STAGED, _SUCCEEDED) for outcome in outcomes.values())
    if corrected and any_tool_worked:
        corrected, removed = _LLM_REFUSAL_RE.subn("", corrected)
        if removed:
            flags.append("false_llm_refusal_corrected")

    # Normalize whitespace left behind by removed sentences.
    corrected = re.sub(r"\s{2,}", " ", corrected).strip()
    return corrected, flags


# ── Shared helpers ────────────────────────────────────────────────────────────


def _now_iso() -> str:
    """Timezone-aware ISO-8601 timestamp."""
    from django.utils.timezone import now

    return now().isoformat()


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    var = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var)


async def _llm_text(
    task: str,
    instance_id: str,
    conversation_id: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.3,
    response_format: dict[str, Any] | None = None,
) -> str | None:
    """Return trimmed LLM reply content, or ``None`` if the LLM is unavailable.

    LLM *unavailability* (no API key, provider error, empty reply) degrades to
    a deterministic answer — never a fabricated one.  Anything that is *not* an
    LLM failure propagates to ``dispatch_task``'s fail-visible handler.

    ``response_format`` (e.g. ``{"type": "json_object"}``) is forwarded to the
    LLM router for structured-output tasks such as ``dq.validate``/``dq.suggest``.
    """
    from ai.engine.llm.router import route_chat

    try:
        resp = await route_chat(
            task,
            instance_id,
            conversation_id,
            messages,
            temperature=temperature,
            response_format=response_format,
        )
    except Exception as exc:  # noqa: BLE001 - LLM outage → deterministic fallback
        logger.warning("LLM unavailable for %s: %s", task, exc)
        return None
    content = (resp or {}).get("content")
    return content.strip() if isinstance(content, str) and content.strip() else None


def _extract_sql(text: str) -> str:
    """Pull the first SQL block (or leading SELECT/WITH line) out of LLM text."""
    if not text:
        return ""
    lowered = text.lower()
    for marker in ("```sql", "```"):
        idx = lowered.find(marker)
        if idx != -1:
            start = idx + len(marker)
            end = lowered.find("```", start)
            if end != -1:
                return text[start:end].strip()
    for line in text.splitlines():
        s = line.strip()
        if s.upper().startswith(("SELECT", "WITH")):
            return s
    return ""


def _deterministic_sql(tables: list[str], max_rows: int) -> str:
    table = (tables or [""])[0]
    if not table:
        return ""
    return f"SELECT * FROM {table} LIMIT {max_rows}"


def _nl_prompt(question: str, tables: list[str], max_rows: int) -> str:
    table_list = ", ".join(tables) if tables else "(infer from question)"
    return (
        f"Write a single read-only SQL query to answer this question: {question}\n"
        f"Relevant tables: {table_list}\n"
        f"Limit results to {max_rows} rows. Return only the SQL inside a ```sql block."
    )


def _explain_prompt(
    question: str, sql: str, row_count: int, sample_rows: list[Any]
) -> str:
    sample = json.dumps(sample_rows[:5], default=str)[:800] if sample_rows else "none"
    return (
        f"Explain this SQL query in plain language.\n"
        f"Question: {question}\n"
        f"SQL: {sql}\n"
        f"Rows returned: {row_count}\n"
        f"Sample rows: {sample}\n"
        f"Explain what the query does, how to read the result, and any caveats."
    )


def _deterministic_explanation(
    question: str, sql: str, row_count: int, sample_rows: list[Any]
) -> dict[str, Any]:
    caveats: list[str] = []
    if sample_rows:
        caveats.append("Rows shown are a sample, not the complete result set.")
    if not sql:
        return {
            "explanation": (
                "No SQL was provided to explain. Supply a query to receive a "
                "step-by-step interpretation."
            ),
            "caveats": caveats or ["No SQL to analyze."],
        }
    explanation = (
        f"This query returns {row_count or 'an unknown number of'} row(s) "
        f"for the question: {question or '(no question provided)'}."
    )
    if row_count:
        caveats.append(f"Results reflect {row_count} row(s); verify against the full dataset.")
    return {"explanation": explanation, "caveats": caveats}


def _analyze_schema_change(change: dict[str, Any]) -> dict[str, Any]:
    raw = (change.get("change") or "").lower()
    table_name = change.get("table_name") or "table"
    field_name = change.get("field_name") or ""
    if any(k in raw for k in ("drop", "remove", "delete")):
        impact = (
            f"Removing {field_name or 'an object'} from {table_name} may break "
            "queries, reports, and downstream pipelines that reference it."
        )
        severity = "high"
        action = (
            "Audit all consumers before removal; stage a deprecation window and "
            "a compatibility view where feasible."
        )
    elif "rename" in raw:
        impact = (
            f"Renaming {field_name or 'an object'} in {table_name} breaks "
            "references unless aliases are preserved."
        )
        severity = "high"
        action = "Introduce a compatibility alias and update referencing queries before cutover."
    elif any(k in raw for k in ("type", "cast", "alter", "modify")):
        impact = (
            f"Changing the type of {field_name or 'a column'} in {table_name} "
            "can truncate data or alter comparison semantics."
        )
        severity = "medium"
        action = "Validate coercion on a copy of the data and update consumers of the changed type."
    elif any(k in raw for k in ("add", "create", "new")):
        impact = (
            f"Adding {field_name or 'a column or table'} to {table_name} is "
            "backward compatible but must be documented."
        )
        severity = "low"
        action = "Update the data catalog and schema documentation."
    else:
        impact = (
            f"Schema change '{change.get('change') or '(unknown)'}' on "
            f"{table_name} needs review."
        )
        severity = "medium"
        action = "Review the change against the data catalog and downstream consumers."
    return {
        "change": change.get("change") or "",
        "impact": impact,
        "severity": severity,
        "suggested_action": action,
    }


def _deterministic_anomaly_explanation(
    table_name: str, anomaly: dict[str, Any]
) -> dict[str, Any]:
    metric = anomaly.get("metric") or f"{table_name}.unknown"
    z = anomaly.get("z_score")
    z_text = f" ({z}σ)" if isinstance(z, (int, float)) else ""
    explanation = (
        f"Anomaly detected in metric '{metric}'{z_text}. Compare the observed "
        "value against the historical range and trace recent data loads or "
        "process changes that could explain the deviation."
    )
    return {
        "explanation": explanation,
        "investigation_steps": [
            "Compare the affected period against previous periods.",
            "Check source ingestion jobs for partial or duplicate loads.",
            "Verify unit-of-measure and sensor/feed configuration.",
        ],
    }


def _deterministic_report_summary(
    report_type: str, period_start: str, period_end: str
) -> str:
    window = ""
    if period_start and period_end:
        window = f" for {period_start} through {period_end}"
    elif period_start:
        window = f" starting {period_start}"
    return (
        f"{report_type.replace('_', ' ').title()} report{window}. "
        "Figures below should be verified against source systems before "
        "external release."
    )


def _deterministic_fix_suggestions(
    issue_type: str, table_name: str, affected_rows: int
) -> list[dict[str, Any]]:
    t = (issue_type or "").lower()
    base = {
        "estimated_affected_rows": affected_rows,
    }
    if any(k in t for k in ("null", "missing", "empty")):
        return [
            {
                **base,
                "description": (
                    f"Fill or flag null/missing values in {table_name} using "
                    "domain defaults or imputation."
                ),
                "confidence": 0.8,
                "suggested_action_type": "impute",
            },
            {
                **base,
                "description": f"Exclude rows missing required fields from analysis.",
                "confidence": 0.7,
                "suggested_action_type": "filter",
            },
        ]
    if any(k in t for k in ("duplicate", "dup")):
        return [
            {
                **base,
                "description": (
                    f"Deduplicate {table_name} on its natural key, keeping the "
                    "most recent row."
                ),
                "confidence": 0.85,
                "suggested_action_type": "deduplicate",
            }
        ]
    if any(k in t for k in ("outlier", "anomaly", "spike")):
        return [
            {
                **base,
                "description": (
                    f"Review and quarantine outlier rows in {table_name} before "
                    "aggregation."
                ),
                "confidence": 0.75,
                "suggested_action_type": "review",
            }
        ]
    if any(k in t for k in ("type", "format", "cast", "invalid")):
        return [
            {
                **base,
                "description": (
                    f"Coerce invalid values in {table_name} to the declared type, "
                    "logging rejected values."
                ),
                "confidence": 0.8,
                "suggested_action_type": "coerce",
            }
        ]
    return [
        {
            **base,
            "description": (
                f"Investigate {table_name} ({issue_type or 'unknown issue'}) and "
                "apply a targeted corrective update."
            ),
            "confidence": 0.6,
            "suggested_action_type": "investigate",
        }
    ]


async def _write_query_feedback(
    instance_id: str,
    task_id: str,
    question: str,
    sql: str,
    outcome: Any,
) -> None:
    from ai.engine.core.config import get_settings

    if not get_settings().KG_FEEDBACK_ENABLED:
        return

    from ai.engine.core.database import get_session_factory
    from ai.models.knowledge_graph import KgQueryFeedback

    factory = get_session_factory(instance_id)
    async with factory() as db:
        db.add(
            KgQueryFeedback(
                instance_id=instance_id,
                question=(question or "")[:500],
                sql_final=(sql or "")[:2000],
                succeeded=bool(outcome.success),
                retry_count=0,
                error_category=(outcome.error.category.value if outcome.error else ""),
                duration_ms=int(outcome.duration_ms or 0),
                row_count=int(outcome.row_count or 0),
                shape="",
            )
        )
        await db.commit()


# ── Task handlers ─────────────────────────────────────────────────────────────


async def _run_query_nl(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    from ai.engine.core.config import get_settings
    from ai.engine.knowledge_graph.engine import ExecutionEngine

    settings = get_settings()
    question = payload.get("question") or ""
    tables = [str(t) for t in (payload.get("tables") or [])]
    max_rows = int(payload.get("max_rows") or settings.TASK_NL_QUERY_MAX_ROWS)

    llm_text = await _llm_text(
        task="query_nl",
        instance_id=instance_id,
        conversation_id=f"nl-{task_id}",
        messages=[{"role": "user", "content": _nl_prompt(question, tables, max_rows)}],
        temperature=0.1,
    )
    sql = _extract_sql(llm_text) if llm_text else ""
    if not sql:
        sql = _deterministic_sql(tables, max_rows)

    if not sql:
        # No tables supplied and LLM unavailable -> cannot generate SQL.
        return {
            "status": "pulse_unavailable",
            "task_id": task_id,
            "error": {
                "code": "engine_error",
                "message": (
                    "Unable to generate SQL: no tables supplied and the LLM "
                    "is unavailable."
                ),
            },
        }

    engine = ExecutionEngine(instance_id)
    outcome = await engine.execute(sql)

    await _write_query_feedback(instance_id, task_id, question, sql, outcome)

    # Fail-visible: a failed execution (table_not_found, syntax, permission,
    # timeout) must NOT be reported as a completed query with empty rows.
    if not outcome.success:
        err = outcome.error
        return {
            "status": "pulse_unavailable",
            "task_id": task_id,
            "error": {
                "code": "engine_error",
                "message": err.message if err else "SQL execution failed.",
            },
        }

    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "sql": outcome.sql_executed or sql,
            "rows": outcome.rows,
            "row_count": outcome.row_count,
            "execution_ms": outcome.duration_ms,
            "recovery_applied": False,
        },
    }


async def _run_query_explain(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    question = payload.get("question") or ""
    sql = payload.get("sql") or ""
    row_count = int(payload.get("row_count") or 0)
    sample_rows = payload.get("sample_rows") or []

    deterministic = _deterministic_explanation(question, sql, row_count, sample_rows)
    llm_text = await _llm_text(
        task="query_explain",
        instance_id=instance_id,
        conversation_id=f"explain-{task_id}",
        messages=[
            {
                "role": "user",
                "content": _explain_prompt(question, sql, row_count, sample_rows),
            }
        ],
    )
    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "explanation": llm_text or deterministic["explanation"],
            "caveats": deterministic["caveats"],
            "execution_ms": 0,
        },
    }


def _iter_schema_tables(payload: dict[str, Any]) -> list[tuple[str, list[dict]]]:
    """Yield (table_name, columns) pairs from ``schema`` / ``schema_changes``.

    Tolerates list-of-dicts, dict-of-lists, and bare-name entries.
    Returns [] when the payload carries no schema information (the
    deterministic fallback path).
    """
    tables: list[tuple[str, list[dict]]] = []

    schema = payload.get("schema")
    if isinstance(schema, dict):
        for tname, cols in schema.items():
            if isinstance(cols, list):
                tables.append(
                    (str(tname), [c for c in cols if isinstance(c, dict)])
                )
    elif isinstance(schema, list):
        for item in schema:
            if isinstance(item, dict):
                tname = item.get("table_name") or item.get("name") or ""
                cols = item.get("columns") or item.get("fields") or []
                if tname:
                    tables.append(
                        (str(tname), [c for c in cols if isinstance(c, dict)])
                    )
            elif isinstance(item, str):
                tables.append((item, []))

    for c in payload.get("schema_changes") or []:
        if isinstance(c, dict) and c.get("table_name"):
            tables.append((str(c["table_name"]), []))

    # Dedupe by table name, keeping the first (richest) column list.
    seen: set[str] = set()
    unique: list[tuple[str, list[dict]]] = []
    for tname, cols in tables:
        if tname not in seen:
            seen.add(tname)
            unique.append((tname, cols))
    return unique


async def _bootstrap_schema_graph(
    store: Any, instance_id: str, payload: dict[str, Any]
) -> dict[str, int]:
    """Upsert ENTITY/ATTRIBUTE nodes + HAS_ATTRIBUTE edges from the payload.

    Idempotent (exact-name upsert).  Returns creation counts.  Never raises:
    per-table failures are logged and skipped.
    """
    counts = {"entities": 0, "attributes": 0, "edges": 0}
    tables = _iter_schema_tables(payload)
    if not tables:
        return counts

    for tname, columns in tables:
        try:
            entity = await store.upsert_node(
                name=tname,
                instance_id=instance_id,
                node_type="ENTITY",
                properties={
                    "schema_json": json.dumps(columns, default=str),
                    "columns": columns,
                },
            )
            counts["entities"] += 1
        except Exception as exc:
            logger.debug("schema bootstrap ENTITY %s failed: %s", tname, exc)
            continue

        for col in columns:
            cname = col.get("column_name") or col.get("name") or ""
            if not cname:
                continue
            props = dict(col)
            if "column_name" not in props and "name" in props:
                props["column_name"] = props.pop("name")
            try:
                attr = await store.upsert_node(
                    name=f"{tname}.{cname}",
                    instance_id=instance_id,
                    node_type="ATTRIBUTE",
                    properties=props,
                )
                counts["attributes"] += 1
                try:
                    await store.add_edge(
                        {
                            "instance_id": instance_id,
                            "source_node_id": entity.id,
                            "target_node_id": attr.id,
                            "relationship": "HAS_ATTRIBUTE",
                            "properties": {"schema": True},
                            "confidence": 0.9,
                            "source": "SCHEMA",
                        }
                    )
                    counts["edges"] += 1
                except ValueError:
                    logger.debug(
                        "HAS_ATTRIBUTE edge skipped (duplicate): %s → %s",
                        tname, cname,
                    )
            except Exception as exc:
                logger.debug("schema bootstrap ATTRIBUTE %s failed: %s", cname, exc)

    return counts


async def _run_schema_analyze(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    """
    Run the real KG schema-analysis pipeline (``run_schema_analysis``).

    When the payload carries schema information (``schema`` /
    ``schema_changes``), the KG is bootstrapped (ENTITY/ATTRIBUTE nodes +
    HAS_ATTRIBUTE edges) and ``run_schema_analysis(force=True)`` runs.
    Per-change deterministic analysis is always included (backward
    compatible).  Any failure — or a payload with no schema — degrades
    gracefully to the deterministic result only.
    """
    from ai.engine.core.database import get_session_factory
    from ai.engine.knowledge_graph.schema_analyzer import run_schema_analysis
    from ai.engine.knowledge_graph.store import KnowledgeGraphStore

    t0 = time.perf_counter()

    schema_changes = payload.get("schema_changes") or []
    analysis = [
        _analyze_schema_change(c) for c in schema_changes if isinstance(c, dict)
    ]

    kg_analysis: dict[str, Any] = {}
    if _iter_schema_tables(payload):
        try:
            factory = get_session_factory(instance_id)
            async with factory() as db:
                store = KnowledgeGraphStore(db)
                bootstrap = await _bootstrap_schema_graph(store, instance_id, payload)
                kg_analysis = await run_schema_analysis(
                    instance_id, force=True, session=db
                )
                kg_analysis["bootstrap"] = bootstrap
        except Exception as exc:
            logger.warning(
                "schema.analyze KG analysis failed for %s: %s", instance_id, exc
            )
            kg_analysis = {"error": str(exc), "degraded": True}

    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "analysis": analysis,
            "kg_analysis": kg_analysis,
            "execution_ms": int((time.perf_counter() - t0) * 1000),
        },
    }


async def _run_anomaly_detect(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    from ai.engine.core.config import get_settings

    table_name = payload.get("table_name") or "table"
    history = payload.get("profile_history") or []
    sensitivity = float(payload.get("sensitivity") or 2.0)
    volume_threshold_pct = float(payload.get("volume_threshold_pct") or 30.0)

    history_snapshots = len(history)
    anomalies: list[dict[str, Any]] = []

    if history_snapshots >= 2:
        baseline = history[:-1]
        latest = history[-1]

        # Volume anomaly on row_count.
        past = [
            float(s["row_count"])
            for s in baseline
            if isinstance(s.get("row_count"), (int, float))
        ]
        current = latest.get("row_count")
        if past and isinstance(current, (int, float)):
            mean = _mean(past)
            std = _std(past)
            z = (current - mean) / std if std > 0 else 0.0
            pct = abs(current - mean) / mean * 100 if mean else 0.0
            if (std > 0 and abs(z) >= sensitivity) or pct >= volume_threshold_pct:
                anomalies.append(
                    {
                        "metric": f"{table_name}.row_count",
                        "expected_range": {
                            "low": round(mean - sensitivity * std, 2),
                            "high": round(mean + sensitivity * std, 2),
                        },
                        "observed": float(current),
                        "z_score": round(z, 2),
                        "severity": "error" if abs(z) >= sensitivity + 1 else "warning",
                        "explanation": (
                            f"row_count is {z:.2f}σ "
                            f"{'above' if z >= 0 else 'below'} the historical "
                            f"mean of {mean:.0f}."
                        ),
                    }
                )

        # Completeness anomaly (drop is bad).
        past_c = [
            float(s["completeness_pct"])
            for s in baseline
            if isinstance(s.get("completeness_pct"), (int, float))
        ]
        current_c = latest.get("completeness_pct")
        if past_c and isinstance(current_c, (int, float)):
            mean_c = _mean(past_c)
            std_c = _std(past_c)
            z_c = (current_c - mean_c) / std_c if std_c > 0 else 0.0
            if std_c > 0 and z_c <= -sensitivity:
                anomalies.append(
                    {
                        "metric": f"{table_name}.completeness",
                        "expected_range": {
                            "low": round(mean_c - sensitivity * std_c, 2),
                            "high": round(mean_c + sensitivity * std_c, 2),
                        },
                        "observed": float(current_c),
                        "z_score": round(z_c, 2),
                        "severity": "error" if z_c <= -(sensitivity + 1) else "warning",
                        "explanation": (
                            f"completeness dropped {abs(z_c):.2f}σ below the "
                            f"historical mean of {mean_c:.1f}%."
                        ),
                    }
                )

    # Real KG path: live profile of the table when a host DB is configured.
    # Best-effort — any failure degrades gracefully to the heuristic above.
    real_profile: dict[str, Any] = {}
    try:
        from ai.engine.knowledge_graph.engine import _default_host_db_url

        # Prefer an explicit HOST_DB_URL, but fall back to Django's default
        # database (Carbon's own PostgreSQL) so live profiling works without
        # any manual connection-string config — mirroring ExecutionEngine.
        host_db_url = get_settings().HOST_DB_URL or _default_host_db_url()
        if host_db_url:
            from ai.engine.knowledge_graph.data_profiler import DataProfiler

            profile = await DataProfiler(
                host_db_url=host_db_url,
                schema=get_settings().HOST_DB_SCHEMA,
            ).profile_table(
                table_name=table_name,
                columns=payload.get("columns") or [],
                sample_size=get_settings().KG_PROFILE_SAMPLE_SIZE,
                max_cardinality=get_settings().KG_PROFILE_MAX_CARDINALITY,
            )
            real_profile = {
                "table_name": profile.table_name,
                "row_count": profile.row_count,
                "columns": len(profile.columns),
                "profiled_at": profile.profiled_at,
            }
            # If the live count deviates from the latest snapshot, flag it.
            if history:
                latest = history[-1]
                live = profile.row_count
                last_count = latest.get("row_count")
                # ``row_count == 0`` is ambiguous (empty table vs. missing
                # table), so only flag a live deviation when the profiler
                # actually found rows in the host database.
                if (
                    live > 0
                    and isinstance(last_count, (int, float))
                    and isinstance(live, int)
                ):
                    delta_pct = (
                        abs(live - last_count) / last_count * 100
                        if last_count
                        else 0.0
                    )
                    if delta_pct >= volume_threshold_pct:
                        anomalies.append(
                            {
                                "metric": f"{table_name}.row_count.live",
                                "expected_range": {
                                    "low": float(last_count),
                                    "high": float(last_count),
                                },
                                "observed": float(live),
                                "z_score": None,
                                "severity": "warning",
                                "explanation": (
                                    f"Live row count {live} differs from the most "
                                    f"recent snapshot by {delta_pct:.1f}%."
                                ),
                            }
                        )
    except Exception as exc:
        logger.warning(
            "anomaly.detect live profile failed for %s: %s", table_name, exc
        )

    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "anomalies": anomalies,
            "history_snapshots": history_snapshots,
            "live_profile": real_profile,
        },
    }


async def _run_anomaly_explain(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    table_name = payload.get("table_name") or "table"
    anomaly = payload.get("anomaly") or {}
    deterministic = _deterministic_anomaly_explanation(table_name, anomaly)
    llm_text = await _llm_text(
        task="anomaly_explain",
        instance_id=instance_id,
        conversation_id=f"anomaly-{task_id}",
        messages=[
            {
                "role": "user",
                "content": (
                    f"Explain the likely cause of this anomaly on {table_name}: "
                    f"{json.dumps(anomaly, default=str)}."
                ),
            }
        ],
    )
    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "explanation": llm_text or deterministic["explanation"],
            "investigation_steps": deterministic["investigation_steps"],
            "execution_ms": 0,
        },
    }


async def _run_report_draft(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    report_type = payload.get("report_type") or "summary"
    period_start = payload.get("period_start") or ""
    period_end = payload.get("period_end") or ""

    title = f"{report_type.replace('_', ' ').title()} Report"
    summary = _deterministic_report_summary(report_type, period_start, period_end)

    # Real KG context: report only what the store actually holds — never
    # invent figures.  Best-effort; failure degrades to no context.
    kg_context: dict[str, Any] = {}
    try:
        from ai.engine.core.database import get_session_factory
        from ai.models.knowledge_graph import KnowledgeEdge, KnowledgeNode

        factory = get_session_factory(instance_id)
        async with factory() as db:
            entities = await db.select(
                KnowledgeNode,
                ("instance_id", instance_id),
                ("node_type", "ENTITY"),
            )
            attributes = await db.select(
                KnowledgeNode,
                ("instance_id", instance_id),
                ("node_type", "ATTRIBUTE"),
            )
            edges = await db.select(KnowledgeEdge, ("instance_id", instance_id))
        kg_context = {
            "entities": len(entities),
            "attributes": len(attributes),
            "edges": len(edges),
        }
    except Exception as exc:
        logger.warning(
            "report.draft KG context failed for %s: %s", instance_id, exc
        )
        kg_context = {"error": str(exc)}

    # Real host-DB grounding: pull live table volume from the host database
    # so the report references actual data present in the platform, never
    # invented figures.  Best-effort — failure degrades to no live metrics.
    host_metrics: dict[str, Any] = {}
    try:
        from ai.engine.knowledge_graph.engine import ExecutionEngine

        engine = ExecutionEngine(instance_id)
        outcome = await engine.execute(
            "SELECT relname AS table_name, n_live_tup AS row_count "
            "FROM pg_stat_user_tables "
            "WHERE schemaname = 'public' AND n_live_tup > 0 "
            "ORDER BY n_live_tup DESC LIMIT 25"
        )
        if outcome.success:
            host_metrics = {
                "tables": outcome.rows,
                "total_tables": len(outcome.rows),
            }
        else:
            host_metrics = {"error": "host query failed"}
    except Exception as exc:
        logger.warning(
            "report.draft host metrics failed for %s: %s", instance_id, exc
        )
        host_metrics = {"error": str(exc)}

    llm_text = await _llm_text(
        task="report_draft",
        instance_id=instance_id,
        conversation_id=f"report-{task_id}",
        messages=[
            {
                "role": "user",
                "content": (
                    f"Draft a {report_type} report summary for "
                    f"{period_start} → {period_end}."
                    f"\n\nKnowledge-graph context: {json.dumps(kg_context, default=str)}"
                    f"\nLive host-data volume: {json.dumps(host_metrics, default=str)}"
                    "\n\nGround the narrative in these figures; do not invent numbers."
                ),
            }
        ],
    )
    if llm_text:
        summary = llm_text

    caveats = [
        "Verify figures against source systems before release.",
    ]
    if kg_context.get("error") or not kg_context:
        caveats.append(
            "Knowledge-graph context unavailable; figures are not sourced "
            "from the live graph."
        )
    if host_metrics.get("error") or not host_metrics.get("tables"):
        caveats.append(
            "Live host-data volume unavailable; table figures are not "
            "sourced from the live database."
        )

    sections = [
        {
            "title": "Summary",
            "narrative": summary,
            "sql": None,
            "data_table": kg_context or None,
            "caveats": caveats,
        },
        {
            "title": "Data Volume (Live)",
            "narrative": (
                "Live row counts for the largest platform tables "
                "(pg_stat_user_tables)."
            ),
            "sql": None,
            "data_table": host_metrics or None,
            "caveats": [],
        },
    ]
    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "title": title,
            "summary": summary,
            "report_type": report_type,
            "period_start": period_start,
            "period_end": period_end,
            "generated_at": _now_iso(),
            "kg_context": kg_context,
            "host_metrics": host_metrics,
            "sections": sections,
        },
    }


async def _run_fix_suggest(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    issue_type = payload.get("issue_type") or ""
    table_name = payload.get("table_name") or "table"
    affected_rows = int(payload.get("affected_rows") or 0)

    suggestions = _deterministic_fix_suggestions(issue_type, table_name, affected_rows)
    llm_text = await _llm_text(
        task="fix_suggest",
        instance_id=instance_id,
        conversation_id=f"fix-{task_id}",
        messages=[
            {
                "role": "user",
                "content": (
                    f"Suggest fixes for issue '{issue_type}' on table {table_name} "
                    f"({affected_rows} affected rows)."
                ),
            }
        ],
    )
    if llm_text:
        suggestions[0]["description"] = llm_text

    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "issue_type": issue_type,
            "table_name": table_name,
            "suggestions": suggestions,
        },
    }


# ── DQ handlers (Phase 2b-3a) ────────────────────────────────────────────────
#
# ``dq.validate`` / ``dq.suggest`` are LLM-only task types: arbitrary
# natural-language DQ rules have no deterministic evaluator, so an LLM outage
# returns ``pulse_unavailable`` (fail-visible) — never a fabricated verdict.
# ``backend/dq/engine.py`` is the *caller* (via PulseProvider), not a
# dependency: these handlers use the engine LLM only.


def _dq_validate_prompt(
    rule: dict[str, Any], rows: list[Any], context: dict[str, Any]
) -> str:
    """Build the evaluator message for one rule against all rows.

    Requires a JSON object with one ``{index, passed, explanation}`` entry per
    row; ``index`` must match the row's 0-based position in ``rows``.
    """
    ctx = context or {}
    table_name = ctx.get("table_name") or "table"
    row_count_hint = ctx.get("row_count_hint") or len(rows)
    fields = ", ".join(str(f) for f in (rule.get("fields") or [])) or "(all columns)"
    row_json = json.dumps(rows, default=str)
    return (
        "You are a data-quality rule evaluator. Evaluate the business rule "
        "against EVERY data row and return a single JSON object:\n"
        '{"results": [{"index": int, "passed": bool, "explanation": str}, ...]}\n'
        "with exactly one entry per row. \"index\" must match the row's 0-based "
        "position in the provided list; \"passed\" is true if the row satisfies "
        "the rule, false otherwise; \"explanation\" is a short reason.\n"
        f"Rule id: {rule.get('id') or '(none)'}\n"
        f"Rule: {rule.get('prompt') or '(no prompt)'}\n"
        f"Relevant fields: {fields}\n"
        f"Severity: {rule.get('severity') or 'unknown'}\n"
        f"Table: {table_name} (row count hint: {row_count_hint})\n"
        f"Rows: {row_json}\n"
        "Return only the JSON object, nothing else."
    )


def _suggest_columns(table: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalise table columns for the suggest prompt.

    ``build_suggest_payload`` emits ``fields`` (name/type/stats); the legacy
    provider path emits ``columns``.  Return a list of ``{name, type, ...}``
    dicts regardless of which key arrived.
    """
    raw = table.get("fields") or table.get("columns") or []
    out: list[dict[str, Any]] = []
    for entry in raw:
        if isinstance(entry, str):
            out.append({"name": entry})
        elif isinstance(entry, dict) and (entry.get("name") or entry.get("field")):
            out.append(entry)
    return out


def _dq_suggest_prompt(
    table: dict[str, Any], retrieval: dict[str, Any] | None = None
) -> str:
    """Build the suggestion message for a table's metadata.

    Requires a JSON object of proposed natural-language DQ business rules
    (completeness, cross-field consistency, temporal plausibility,
    range/outlier plausibility).

    ``retrieval`` (Phase C) is the output of
    ``ai.knowledge.dq_retriever.retrieve_suggest_context`` — field profiles,
    canonical per-type examples, and the N most-similar existing rules.  When
    present it is rendered into the prompt so suggestions are grounded in the
    platform's own data rather than emitted from metadata alone.  When absent
    (or when retrieval failed to resolve a ``table_id``) the prompt degrades
    to the pre-Phase-C baseline.
    """
    columns = _suggest_columns(table)
    col_json = json.dumps(columns, default=str)[:2400]

    lines = [
        "You are a data-quality analyst. Propose natural-language data-quality "
        "business rules for the table below — consider completeness, "
        "cross-field consistency, temporal plausibility, and range/outlier "
        "plausibility — and return a single JSON object:\n",
        '{"suggestions": [{"prompt": str, "rule_type": "nl_check", '
        '"rationale": str, "suggested_severity": "info"|"warn"|"error", '
        '"confidence": float}, ...]}\n',
        f"Table name: {table.get('name') or '(unknown)'}",
        f"Description: {table.get('description') or '(none)'}",
        f"Columns: {col_json}",
        f"Row count: {table.get('row_count') or 'unknown'}",
    ]

    retrieval = retrieval or {}
    if retrieval.get("field_profiles"):
        profiles_json = json.dumps(
            retrieval["field_profiles"], default=str
        )[:2400]
        lines.append(f"Column profiles (observed stats): {profiles_json}")

    if retrieval.get("canonical_examples"):
        examples_json = json.dumps(
            retrieval["canonical_examples"], default=str
        )[:2400]
        lines.append(
            "Canonical v1 rule definitions (by type) already used elsewhere — "
            f"reuse these shapes where applicable: {examples_json}"
        )

    if retrieval.get("similar_rules"):
        similar_json = json.dumps(
            retrieval["similar_rules"], default=str
        )[:2000]
        lines.append(
            "Existing rules on similar fields (avoid duplicating these): "
            f"{similar_json}"
        )

    lines.append("Return only the JSON object, nothing else.")
    return "\n".join(lines)


def _coerce_confidence(value: Any) -> float:
    """Coerce an LLM-provided confidence to a float clamped to [0.0, 1.0].

    Missing/uncoercible values default to a neutral 0.5.
    """
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.5
    return max(0.0, min(1.0, confidence))


def _llm_unavailable(task_id: str, message: str) -> dict[str, Any]:
    """Fail-visible result for an LLM outage (never fabricate a verdict)."""
    return {
        "status": "pulse_unavailable",
        "task_id": task_id,
        "error": {
            "code": "llm_unavailable",
            "message": message,
        },
    }


async def _run_dq_validate(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    """Evaluate each DQ rule against all rows in ONE LLM call per rule.

    Per-rule verdict JSON: ``{"results": [{"index", "passed", "explanation"}]}``.
    An LLM outage → ``pulse_unavailable``/``llm_unavailable``; an unparseable
    verdict degrades that rule to ``skipped_unavailable`` (never a fabricated
    pass/fail).  ``details`` is positionally indexed by row.
    """
    rules = [r for r in (payload.get("rules") or []) if isinstance(r, dict)]
    rows = payload.get("rows") or []
    context = payload.get("context") or {}

    if not rules or not rows:
        # The consumer treats "no rules / no rows" as a local no-op.
        return {
            "status": "completed",
            "task_id": task_id,
            "result": {"results": []},
        }

    results: list[dict[str, Any]] = []
    for rule in rules:
        rule_id = str(rule.get("id") or "")
        llm_text = await _llm_text(
            task="eval",
            instance_id=instance_id,
            conversation_id=f"dq-validate-{task_id}",
            messages=[
                {"role": "user", "content": _dq_validate_prompt(rule, rows, context)}
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        if not llm_text:
            return _llm_unavailable(
                task_id, f"LLM unavailable while evaluating rule {rule_id!r}."
            )

        try:
            verdicts = json.loads(llm_text).get("results")
        except (json.JSONDecodeError, TypeError, AttributeError):
            verdicts = None
        if not isinstance(verdicts, list):
            # Unparseable/empty verdict → fail-visible skip, never a pass.
            results.append(
                {"rule_id": rule_id, "status": "skipped_unavailable", "details": []}
            )
            continue

        by_index: dict[int, dict[str, Any]] = {}
        for verdict in verdicts:
            if not isinstance(verdict, dict):
                continue
            try:
                idx = int(verdict.get("index"))
            except (TypeError, ValueError):
                continue
            by_index[idx] = verdict

        details = [
            {
                "passed": bool(by_index.get(i, {}).get("passed", False)),
                "explanation": str(by_index.get(i, {}).get("explanation") or ""),
            }
            for i in range(len(rows))
        ]
        status = "pass" if all(d["passed"] for d in details) else "fail"
        results.append({"rule_id": rule_id, "status": status, "details": details})

    return {
        "status": "completed",
        "task_id": task_id,
        "result": {"results": results},
    }


async def _run_dq_suggest(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    """Propose natural-language DQ rules for a table via the LLM.

    Verdict JSON: ``{"suggestions": [{"prompt", "rule_type", "rationale",
    "suggested_severity", "confidence"}]}``.  No deterministic fallback — an
    LLM outage or unparseable verdict returns ``pulse_unavailable``.
    """
    table = payload.get("table") or {}

    # Phase C — retrieval-augmented context.  A missing/foreign table id (or a
    # retriever failure) degrades to the metadata-only baseline prompt, never
    # blocks the suggestion.
    retrieval: dict[str, Any] | None = None
    table_id = table.get("table_id")
    if table_id:
        try:
            from ai.knowledge.dq_retriever import retrieve_suggest_context

            retrieval = retrieve_suggest_context(int(table_id))
        except Exception as exc:  # noqa: BLE001 - retrieval is best-effort
            logger.warning(
                "dq.suggest retrieval skipped for table %s: %s", table_id, exc
            )
            retrieval = None

    llm_text = await _llm_text(
        task="cognition",
        instance_id=instance_id,
        conversation_id=f"dq-suggest-{task_id}",
        messages=[
            {"role": "user", "content": _dq_suggest_prompt(table, retrieval)}
        ],
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    if not llm_text:
        return _llm_unavailable(
            task_id, "LLM unavailable while suggesting data-quality rules."
        )

    try:
        raw = json.loads(llm_text).get("suggestions")
    except (json.JSONDecodeError, TypeError, AttributeError):
        raw = None
    if not isinstance(raw, list):
        # Unparseable payload — fabricating rules is worse than saying no.
        return _llm_unavailable(
            task_id, "LLM returned an unparseable suggestion payload."
        )

    suggestions: list[dict[str, Any]] = []
    for suggestion in raw:
        if not isinstance(suggestion, dict):
            continue
        severity = str(suggestion.get("suggested_severity") or "warn").lower()
        if severity not in ("info", "warn", "error"):
            severity = "warn"
        suggestions.append(
            {
                "prompt": str(suggestion.get("prompt") or ""),
                "rule_type": str(suggestion.get("rule_type") or "nl_check"),
                "rationale": str(suggestion.get("rationale") or ""),
                "suggested_severity": severity,
                "confidence": _coerce_confidence(suggestion.get("confidence")),
            }
        )

    return {
        "status": "completed",
        "task_id": task_id,
        "result": {"suggestions": suggestions},
    }


# Deterministic v1 rule types that ``dq.engine.evaluate`` can dry-run without
# an NL-check round-trip.  The LLM is constrained to emit only these; anything
# else is fail-visible (never a fabricated pass/fail).
_DETERMINISTIC_RULE_TYPES = {
    "not_null",
    "unique",
    "allowed_values",
    "range",
    "regex",
    "reference_integrity",
    "threshold",
}


def _nl_rule_test_prompt(
    nl: str,
    schema: list[dict[str, Any]],
    table_name: str,
    retrieval: dict[str, Any] | None = None,
) -> str:
    """Build the parse message that turns NL into a v1 rule definition.

    Requires a JSON object using ``type`` + ``params`` keys (NOT
    ``rule_type``) so the output matches ``dq.engine.evaluate`` directly.

    ``retrieval`` (Phase C) carries the field profile (observed stats) and
    similar existing rules so the parse is grounded in the data the rule will
    actually run against — and so it reuses existing rules instead of
    re-inventing them.
    """
    schema_json = json.dumps(schema, default=str)[:2000]
    lines = [
        "You are a data-quality engineer. Convert the natural-language rule "
        "below into a single JSON object describing a deterministic v1 DQ "
        "rule definition:\n",
        '{"type": str, "params": object, "severity": "info"|"warn"|"error", '
        '"confidence": float, "field": str}\n',
        '"type" must be one of: not_null, unique, allowed_values, range, '
        'regex, reference_integrity, threshold.\n',
        '"params" hold the parameters for that type: range -> {"min","max"}; '
        'threshold -> {"operator","value"}; regex -> {"pattern"}; '
        'allowed_values -> {"values":[...]}; unique -> {}; not_null -> {}; '
        'reference_integrity -> {"reference_set_id": int}.\n',
        '"field" is the column name the rule applies to (use one of the '
        'columns below).\n',
        f"Table name: {table_name}",
        f"Columns: {schema_json}",
    ]

    retrieval = retrieval or {}
    if retrieval.get("field_profile"):
        profile_json = json.dumps(retrieval["field_profile"], default=str)[:1200]
        lines.append(f"Field profile (observed stats): {profile_json}")
    if retrieval.get("similar_rules"):
        similar_json = json.dumps(retrieval["similar_rules"], default=str)[:2000]
        lines.append(
            "Existing rules on similar fields (prefer reusing these shapes): "
            f"{similar_json}"
        )

    lines.append(f"Natural-language rule: {nl}")
    lines.append("Return only the JSON object, nothing else.")
    return "\n".join(lines)


def _is_empty_value(v: Any) -> bool:
    """Mirror dq.engine's emptiness rule (None/''/[] are empty)."""
    return v is None or v == "" or v == []


def _rule_test_rows(
    rule_type: str,
    params: dict[str, Any],
    rows: list[Any],
    field_name: str | None,
) -> list[dict[str, Any]]:
    """Per-row detail for the Phase 8-B threshold slider re-score.

    One entry per *applicable* row carrying ``{row_id, actual, expected,
    passed}`` so the frontend can re-score client-side with no server
    round-trip.  Mirrors dq.engine.evaluate's deterministic branches; pure
    and read-only.
    """
    out: list[dict[str, Any]] = []

    # Pre-compute uniqueness counts (the 'unique' verdict depends on the set).
    unique_counts: dict[str, int] = {}
    if rule_type == "unique":
        for r in rows:
            v = r.values.get(field_name)
            if _is_empty_value(v):
                continue
            unique_counts[str(v)] = unique_counts.get(str(v), 0) + 1

    # Pre-compute allowed values for reference-set-backed rules (read-only).
    allowed: set[str] | None = None
    if rule_type == "allowed_values":
        from mdm.models import ReferenceValue

        rs_id = params.get("reference_set")
        if rs_id:
            allowed = {
                str(c)
                for c in ReferenceValue.objects.filter(
                    reference_set_id=rs_id, is_active=True
                ).values_list("code", flat=True)
            }
        else:
            allowed = {str(a) for a in (params.get("values") or [])}
    elif rule_type == "reference_integrity":
        rs_id = params.get("reference_set_id")
        if rs_id:
            from mdm.models import ReferenceSet

            try:
                ref_set = ReferenceSet.objects.get(id=rs_id)
                allowed = {
                    str(c)
                    for c in ref_set.get_current_values().values_list("code", flat=True)
                }
            except ReferenceSet.DoesNotExist:
                allowed = set()
        else:
            allowed = set()

    for r in rows:
        v = r.values.get(field_name)
        row_id = r.id

        if rule_type == "not_null":
            out.append(
                {
                    "row_id": row_id,
                    "actual": v,
                    "expected": "non-empty",
                    "passed": not _is_empty_value(v),
                }
            )
            continue

        if _is_empty_value(v):
            continue  # not applicable for every other deterministic type

        if rule_type == "unique":
            passed = unique_counts.get(str(v), 0) <= 1
            out.append(
                {"row_id": row_id, "actual": v, "expected": "unique", "passed": passed}
            )
        elif rule_type == "allowed_values":
            out.append(
                {
                    "row_id": row_id,
                    "actual": v,
                    "expected": sorted(allowed) if allowed is not None else [],
                    "passed": str(v) in (allowed or set()),
                }
            )
        elif rule_type == "range":
            lo = params.get("min")
            hi = params.get("max")
            try:
                fv = float(v)
                passed = (lo is None or fv >= lo) and (hi is None or fv <= hi)
            except (TypeError, ValueError):
                passed = False
            out.append(
                {
                    "row_id": row_id,
                    "actual": v,
                    "expected": {"min": lo, "max": hi},
                    "passed": passed,
                }
            )
        elif rule_type == "regex":
            pat = params.get("pattern", "")
            try:
                rx = re.compile(pat) if pat else None
            except re.error:
                rx = None
            passed = rx is None or rx.search(str(v)) is not None
            out.append(
                {
                    "row_id": row_id,
                    "actual": v,
                    "expected": pat,
                    "passed": passed,
                }
            )
        elif rule_type == "threshold":
            op = params.get("operator", "gte")
            tv = params.get("value")
            try:
                fv = float(v)
                t = float(tv) if tv is not None else None
                if t is None:
                    passed = False
                elif op == "gte":
                    passed = fv >= t
                elif op == "gt":
                    passed = fv > t
                elif op == "lte":
                    passed = fv <= t
                elif op == "lt":
                    passed = fv < t
                elif op == "eq":
                    passed = fv == t
                elif op == "neq":
                    passed = fv != t
                else:
                    passed = True  # unknown operator → no-op (matches evaluate)
            except (TypeError, ValueError):
                passed = False
            out.append(
                {
                    "row_id": row_id,
                    "actual": v,
                    "expected": {"operator": op, "value": tv},
                    "passed": passed,
                }
            )
        elif rule_type == "reference_integrity":
            out.append(
                {
                    "row_id": row_id,
                    "actual": v,
                    "expected": params.get("reference_set_id"),
                    "passed": str(v) in (allowed or set()),
                }
            )

    return out


async def _run_nl_rule_test(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    """Parse an NL rule into a v1 definition and dry-run it (read-only).

    Never writes a DQRule/DQResult: the LLM parse and the
    ``dq.engine.evaluate`` call are both pure.  An LLM outage, an unparseable
    definition, or an unsupported rule type returns ``pulse_unavailable`` —
    never a fabricated pass/fail.
    """
    nl = str(payload.get("nl") or "").strip()
    table_name = str(payload.get("table_name") or "table")
    schema = payload.get("schema") or []
    rows = payload.get("rows") or []
    field_name = payload.get("field_name")
    table_id = payload.get("table_id")

    if not nl:
        return {
            "status": "completed",
            "task_id": task_id,
            "result": {
                "rule_preview": None,
                "test_summary": {
                    "total_rows": len(rows),
                    "applicable_rows": 0,
                    "passed": 0,
                    "failed": 0,
                    "pass_rate": 0.0,
                },
                "violations": [],
                "rows": [],
                "recommendation": "No natural-language rule was provided.",
            },
        }

    # Phase C — retrieval-augmented context (field profile + similar rules).
    # Degrades to the schema-only baseline when ``table_id`` is missing or the
    # retriever cannot resolve it.
    retrieval: dict[str, Any] | None = None
    if table_id:
        try:
            from ai.knowledge.dq_retriever import retrieve_nl_check_context

            retrieval = retrieve_nl_check_context(
                int(table_id), field_name=field_name
            )
        except Exception as exc:  # noqa: BLE001 - retrieval is best-effort
            logger.warning(
                "nl_rule_test retrieval skipped for table %s: %s", table_id, exc
            )
            retrieval = None

    llm_text = await _llm_text(
        task="cognition",
        instance_id=instance_id,
        conversation_id=f"nl-rule-test-{task_id}",
        messages=[
            {
                "role": "user",
                "content": _nl_rule_test_prompt(
                    nl, schema, table_name, retrieval
                ),
            }
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    if not llm_text:
        return _llm_unavailable(
            task_id, "LLM unavailable while parsing the natural-language rule."
        )

    try:
        parsed = json.loads(llm_text)
    except (json.JSONDecodeError, TypeError):
        parsed = None
    if not isinstance(parsed, dict):
        return _llm_unavailable(
            task_id, "LLM returned an unparseable rule definition."
        )

    rule_type = str(parsed.get("type") or "")
    if rule_type not in _DETERMINISTIC_RULE_TYPES:
        return _llm_unavailable(
            task_id, f"LLM returned an unsupported rule type {rule_type!r}."
        )

    params = parsed.get("params")
    if not isinstance(params, dict):
        params = {}
    severity = str(parsed.get("severity") or "warn").lower()
    if severity not in ("info", "warn", "error"):
        severity = "warn"
    confidence = _coerce_confidence(parsed.get("confidence"))
    resolved_field = parsed.get("field") or field_name

    rule_def = {
        "type": rule_type,
        "params": params,
        "severity": severity,
    }

    # ``dq.engine.evaluate`` only needs ``field.name`` (and, for
    # reference_integrity, ``field.reference_set_id``) — pass a lightweight
    # namespace rather than importing dataschema models into the engine.
    field_obj = (
        types.SimpleNamespace(name=resolved_field, reference_set_id=None)
        if resolved_field
        else None
    )

    from dq.engine import evaluate as engine_evaluate

    _passed, checked, failed, sample_failures, _score = engine_evaluate(
        rule_def, rows, field=field_obj
    )

    passed_count = checked - failed
    pass_rate = round(passed_count / checked, 4) if checked else 0.0

    # Per-applicable-row detail (actual vs expected) so the Phase 8-B
    # threshold slider can re-score client-side with no server round-trip.
    detail_rows = _rule_test_rows(rule_type, params, rows, resolved_field)

    if failed == 0:
        recommendation = "All applicable rows pass — this rule can be saved as-is."
    else:
        recommendation = (
            f"{failed} of {checked} applicable row(s) fail. Review the "
            "violations before saving the rule."
        )

    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "rule_preview": {
                "type": rule_type,
                "params": params,
                "severity": severity,
                "confidence": confidence,
                "field": resolved_field,
            },
            "test_summary": {
                "total_rows": len(rows),
                "applicable_rows": checked,
                "passed": passed_count,
                "failed": failed,
                "pass_rate": pass_rate,
            },
            "violations": sample_failures,
            "rows": detail_rows,
            "recommendation": recommendation,
        },
    }


# Severity mapping for investigate findings (DQ + anomaly → high|medium|low).
_INVESTIGATE_SEVERITY_MAP = {
    "error": "high",
    "warn": "medium",
    "warning": "medium",
    "info": "low",
}


def _investigate_severity(value: str) -> str:
    """Map a DQ/anomaly severity string to high|medium|low."""
    return _INVESTIGATE_SEVERITY_MAP.get(str(value or "").lower(), "medium")


async def _run_investigate(
    instance_id: str, payload: dict[str, Any], task_id: str
) -> dict[str, Any]:
    """Read-only investigation pipeline (Phase 9-A).

    Consumes a pre-loaded payload (assembled by the intelligence layer) and
    produces ``plan_steps`` + ``findings`` + ``summary``.  Never writes to DQ:
    the DQ step calls the pure ``dq.engine.evaluate`` loop (RULE_21), the
    anomaly step reuses the already-registered ``_run_anomaly_detect``, and
    the KG step reports entities retrieved upstream (retrieval needs
    ``scope``, which only the intelligence layer holds).

    An LLM outage only degrades the narrative ``summary`` — deterministic
    findings are still returned, and the synthesis step is marked
    ``llm_unavailable`` (never ``pulse_unavailable``).
    """
    from dq.engine import evaluate as engine_evaluate

    table_id = payload.get("table_id")
    table_name = str(payload.get("table_name") or "table")
    schema = payload.get("schema") or []
    rows = payload.get("rows") or []
    profile_summary = payload.get("profile_summary") or {}
    rule_defs = [r for r in (payload.get("rule_defs") or []) if isinstance(r, dict)]
    anomaly_payload = payload.get("anomaly_payload")
    kg_entries = payload.get("kg_entries") or []

    field_type_by_name = {
        str(f.get("name")): f.get("type")
        for f in schema
        if isinstance(f, dict) and f.get("name")
    }

    plan_steps: list[dict[str, Any]] = []

    # Step 1 — Profile (read-only, from the latest TableProfile summary).
    row_count = profile_summary.get("row_count", len(rows))
    field_count = profile_summary.get("field_count", len(schema))
    plan_steps.append(
        {
            "step": 1,
            "label": "Profile table",
            "status": "done",
            "detail": f"{row_count} rows · {field_count} fields",
        }
    )

    # Step 2 — DQ rules (pure evaluate loop mirroring run_dq's selection, but
    # with no persistence).
    findings: list[dict[str, Any]] = []
    rules_run = 0
    rules_failed = 0
    for rule_def in rule_defs:
        field_name = rule_def.get("field_name")
        field = (
            types.SimpleNamespace(
                name=field_name,
                data_type=field_type_by_name.get(field_name),
                reference_set_id=rule_def.get("reference_set_id"),
            )
            if field_name
            else None
        )
        try:
            _passed, checked, failed, _sample, _score = engine_evaluate(
                rule_def, rows, field=field
            )
        except Exception as exc:  # noqa: BLE001 - a bad rule def must not kill the turn
            logger.warning(
                "investigate DQ eval failed for rule %s: %s",
                rule_def.get("name"),
                exc,
            )
            continue
        rules_run += 1
        if failed > 0:
            rules_failed += 1
            label = rule_def.get("name") or rule_def.get("id")
            findings.append(
                {
                    "severity": _investigate_severity(rule_def.get("severity")),
                    "title": f"DQ rule '{label}' failed",
                    "detail": f"{failed} of {checked} applicable row(s) violated rule '{label}'.",
                    "recommended_action": "Review the failing rows and correct or quarantine them.",
                    "entity_ref": field_name,
                }
            )
    plan_steps.append(
        {
            "step": 2,
            "label": "Evaluate DQ rules",
            "status": "done",
            "detail": f"{rules_run} rules run · {rules_failed} failed",
        }
    )

    # Step 3 — Anomalies (reuse the already-registered _run_anomaly_detect).
    anomalies: list[dict[str, Any]] = []
    if anomaly_payload:
        anomaly_result = await _run_anomaly_detect(instance_id, anomaly_payload, task_id)
        anomalies = (anomaly_result.get("result") or {}).get("anomalies") or []
        for anomaly in anomalies:
            if not isinstance(anomaly, dict):
                continue
            findings.append(
                {
                    "severity": _investigate_severity(anomaly.get("severity")),
                    "title": f"Anomaly: {anomaly.get('metric', table_name)}",
                    "detail": str(anomaly.get("explanation") or "Detected an anomalous value."),
                    "recommended_action": "Investigate this anomaly before it propagates downstream.",
                    "entity_ref": anomaly.get("metric") or table_name,
                }
            )
        detail = f"{len(anomalies)} anomalies" if anomalies else "0 anomalies"
    else:
        detail = "insufficient history"
    plan_steps.append(
        {
            "step": 3,
            "label": "Detect anomalies",
            "status": "done",
            "detail": detail,
        }
    )

    # Step 4 — Knowledge graph (retrieved upstream in the intelligence layer).
    plan_steps.append(
        {
            "step": 4,
            "label": "Retrieve knowledge graph",
            "status": "done",
            "detail": f"{len(kg_entries)} entities",
        }
    )

    counts = {
        "rules_run": rules_run,
        "rules_failed": rules_failed,
        "anomalies": len(anomalies),
        "kg_entities": len(kg_entries),
    }

    # Step 5 — Synthesis (best-effort LLM narrative; deterministic fallback).
    llm_text = await _llm_text(
        task="investigate",
        instance_id=instance_id,
        conversation_id=f"investigate-{task_id}",
        messages=[
            {
                "role": "user",
                "content": (
                    f"Summarize the data-quality investigation of table "
                    f"{table_name!r}. Return a JSON object: "
                    '{"summary": str}.\n'
                    f"Findings: {json.dumps(findings, default=str)}"
                ),
            }
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    summary = None
    if llm_text:
        try:
            parsed_summary = json.loads(llm_text)
            if isinstance(parsed_summary, dict):
                summary = str(parsed_summary.get("summary") or "").strip()
        except (json.JSONDecodeError, TypeError):
            summary = None

    if summary:
        synthesis_status = "done"
        synthesis_detail = summary
    else:
        summary = (
            f"{rules_failed} of {rules_run} rule(s) failed, "
            f"{len(anomalies)} anomaly(s) detected."
        )
        synthesis_status = "llm_unavailable"
        synthesis_detail = "LLM unavailable — deterministic summary used."
    plan_steps.append(
        {
            "step": 5,
            "label": "Synthesize findings",
            "status": synthesis_status,
            "detail": synthesis_detail,
        }
    )

    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "table_id": table_id,
            "table_name": table_name,
            "plan_steps": plan_steps,
            "findings": findings,
            "summary": summary,
            "counts": counts,
        },
    }


# Handler registry: task type → async handler.
_TASK_HANDLERS: dict[str, Any] = {
    "dq.validate": _run_dq_validate,
    "dq.suggest": _run_dq_suggest,
    "dq.rule_test": _run_nl_rule_test,
    "carbon.query.nl": _run_query_nl,
    "carbon.query.explain": _run_query_explain,
    "carbon.schema.analyze": _run_schema_analyze,
    "carbon.anomaly.detect": _run_anomaly_detect,
    "carbon.anomaly.explain": _run_anomaly_explain,
    "carbon.report.draft": _run_report_draft,
    "carbon.fix.suggest": _run_fix_suggest,
    "investigate": _run_investigate,
}


def list_modules(instance_id: str = "carbon") -> dict[str, Any]:
    """Return the modules the in-process engine advertises."""
    return {"modules": [{"type": m} for m in MODULES]}


def dispatch_task(
    task_type: str,
    payload: dict[str, Any],
    *,
    instance_id: str = "carbon",
    timeout: int | None = None,
) -> dict[str, Any]:
    """Dispatch a task in-process.

    Returns a Pulse-shaped result dict::

        {"status": "completed"|"pending"|"failed"|"pulse_unavailable",
         "task_id": str,
         "result": {...} | "error": {"code": str, "message": str}}
    """
    if task_type not in MODULES:
        return {
            "status": "pulse_unavailable",
            "task_id": "",
            "error": {
                "code": "unknown_task",
                "message": f"Unknown task type: {task_type!r}",
            },
        }

    # Phase 2b-1: ``chat`` is wired end-to-end through the turn runner.
    # Fail-visible: any error returns ``pulse_unavailable`` — never a fake
    # answer.
    if task_type == "chat":
        task_id = _new_task_id()
        try:
            return _run_async(_run_chat(instance_id, payload, task_id))
        except Exception as exc:  # noqa: BLE001 - fail-visible contract
            logger.exception("chat dispatch failed for instance=%s", instance_id)
            return {
                "status": "pulse_unavailable",
                "task_id": task_id,
                "error": {
                    "code": "engine_error",
                    "message": f"chat failed: {exc}",
                },
            }

    # Phase 2b-2/2b-3: the KG/analytics and DQ task types are wired
    # in-process.  Every entry in MODULES is covered by ``chat`` above and
    # ``_TASK_HANDLERS`` below, so no ``not_wired`` path remains — a missing
    # handler is a programming error and surfaces fail-visible via
    # ``engine_error``.
    handler = _TASK_HANDLERS.get(task_type)
    task_id = _new_task_id()
    try:
        if handler is None:
            raise LookupError(f"no in-process handler for {task_type!r}")
        return _run_async(handler(instance_id, payload, task_id))
    except Exception as exc:  # noqa: BLE001 - fail-visible contract
        logger.exception("%s dispatch failed for instance=%s", task_type, instance_id)
        return {
            "status": "pulse_unavailable",
            "task_id": task_id,
            "error": {
                "code": "engine_error",
                "message": f"{task_type} failed: {exc}",
            },
        }


def dispatch_task_stream(task_type: str, payload: dict[str, Any], *, instance_id: str = "carbon"):
    """Stream a ``chat`` turn as ``(kind, value)`` tuples from a background thread.

    The engine's turn runner is async and yields text deltas through an async
    ``stream_callback``; this generator bridges that async stream to a sync
    iterator using a ``queue.Queue`` and a daemon thread so Django views can
    consume it inside a ``StreamingHttpResponse`` without blocking the event
    loop.

    Yields:
        ("chunk", delta)  — one text delta (may repeat)
        ("done", result)  — terminal success (same dict shape ``chat()`` reads)
        ("error", message, {"error_kind": "transient"|"permanent"}) — terminal failure
    """
    if task_type != "chat":
        yield "error", f"streaming not supported for {task_type!r}"
        return

    q: queue.Queue = queue.Queue()

    async def _collect():
        async def cb(delta: str):
            q.put(("chunk", delta))

        try:
            result = await _run_chat(instance_id, payload, _new_task_id(), stream_callback=cb)
            q.put(("done", result))
        except Exception as exc:  # noqa: BLE001 - fail-visible
            from ai.engine.llm.provider import classify_llm_error
            logger.exception("chat stream failed for instance=%s", instance_id)
            q.put(("error", f"chat failed: {exc}", {"error_kind": classify_llm_error(exc)}))
        finally:
            q.put(("eof", None))

    def _thread_target():
        _run_async(_collect())

    threading.Thread(target=_thread_target, daemon=True).start()

    while True:
        frame = q.get()
        if frame[0] == "eof":
            break
        yield frame


def get_task(task_id: str, *, timeout: int | None = None) -> dict[str, Any]:
    """Retrieve an in-process task's status."""
    return {
        "status": "pulse_unavailable",
        "error": {
            "code": "not_found",
            "message": f"No in-process task with id {task_id!r}",
        },
    }


# ── Agent/Tool action execution seam (Sprint W1-A) ────────────────────────
#
# ``dispatch_action_stream`` is the sync-to-async bridge the workspace SSE
# endpoint consumes (identical shape to ``dispatch_task_stream``).  The async
# work lives in ``_run_action_stream`` which:
#   * resolves the step list — one tool, or an agent's declared tool_set
#     (AgentRegistry, NOT a second registry),
#   * emits the clustered frame protocol (design §2.5):
#         turn_start {turn_id, label, verbosity}
#         tool_start {turn_id, step_id, tool, category}  category ∈ agent|mcp|tool
#         tool_arg   {step_id, args}                     verbosity="full" only
#         tool_result{step_id, result}                   verbosity="full" only (redacted)
#         tool_end   {step_id, status}                   completed|failed|stopped|needs_confirmation
#         turn_end   {turn_id, status, summary}          completed|failed|stopped
#   * writes a durable ``ai.models.ToolExecution`` row per step
#     (status running → completed|failed|stopped),
#   * stages host-mutating tools via ``create_pending_execution`` and emits
#     ``tool_end{status:"needs_confirmation", execution_id}`` (RULE_21 —
#     never auto-runs a mutation),
#   * checks ``GENERATIONS.is_cancelled`` between steps: a cancel mid-run
#     emits ``tool_end{status:"stopped"}`` + ``turn_end{status:"stopped",
#     summary:"Stopped by user"}`` and returns — never ``error``, and the
#     caller never leaves the conversation stuck in ``working``.


def _finalize_execution_row(row, status: str, output: dict | None) -> None:
    """Terminal-state update for a durable ToolExecution step row (sync)."""
    from django.utils import timezone

    row.status = status
    row.output = output or {}
    row.executed_at = timezone.now()
    row.save(update_fields=["status", "output", "executed_at"])


async def _create_execution_row(**kwargs):
    """Create a durable ToolExecution row from the async runtime (thread-safe)."""
    from asgiref.sync import sync_to_async

    from ai.models.core import ToolExecution

    return await sync_to_async(
        ToolExecution.objects.create, thread_sensitive=True
    )(**kwargs)


async def _save_execution_row(row, status: str, output: dict | None) -> None:
    """Persist a step row's terminal state from the async runtime."""
    from asgiref.sync import sync_to_async

    await sync_to_async(_finalize_execution_row, thread_sensitive=True)(
        row, status, output
    )


async def _run_action_stream(
    instance_id: str,
    payload: dict[str, Any],
) -> Any:
    """Run one agent/tool action, emitting clustered frames (async generator)."""
    from ai.engine.agent.plugins import ToolContext, set_tool_context
    from ai.engine.agent.registry import AgentRegistry
    from ai.engine.agent.tools import MCP_EXECUTORS, get_tool_executors
    from ai.engine.core.database import get_session_factory
    from ai.generation_registry import GENERATIONS
    from ai.host_executor import CarbonHostExecutor
    from ai.observability_api import _redact_secrets

    conversation_id = str(payload.get("conversation_id") or "")
    action_type = payload.get("action_type") or "tool"
    verbosity = payload.get("verbosity") or "concise"
    if verbosity not in ("concise", "full"):
        verbosity = "concise"
    tool_name = payload.get("tool") or ""
    agent_name = payload.get("agent") or ""
    args = payload.get("args") or {}
    host_user_id = payload.get("host_user_id")

    turn_id = f"turn-{uuid.uuid4().hex[:12]}"
    label = (
        f"Run agent {agent_name}"
        if action_type == "agent"
        else f"Run tool {tool_name}"
    )
    yield {
        "type": "turn_start",
        "turn_id": turn_id,
        "label": label,
        "verbosity": verbosity,
    }

    instance_config = _carbon_instance_config(host_user_id)
    factory = get_session_factory(instance_id)
    async with factory() as db:
        executor = CarbonHostExecutor(
            db=db,
            instance_config=instance_config,
            user_token=f"inproc:carbon:{host_user_id}" if host_user_id else None,
            host_user_id=host_user_id,
        )
        executors = await get_tool_executors()

        # Resolve the step list: a single tool, or an agent's declared tool_set.
        if action_type == "agent":
            registry = AgentRegistry(db)
            agent = await registry.get_agent(instance_id, agent_name)
            if agent is None:
                yield {
                    "type": "tool_start",
                    "turn_id": turn_id,
                    "step_id": 1,
                    "tool": agent_name,
                    "category": "agent",
                }
                yield {"type": "tool_end", "step_id": 1, "status": "failed"}
                yield {
                    "type": "turn_end",
                    "turn_id": turn_id,
                    "status": "failed",
                    "summary": f"Agent {agent_name!r} not found.",
                }
                return
            raw_tool_set = agent.tool_set_json or []
            if isinstance(raw_tool_set, str):
                try:
                    raw_tool_set = json.loads(raw_tool_set)
                except (json.JSONDecodeError, TypeError):
                    raw_tool_set = []
            steps = [
                {"tool": t, "category": "agent"} for t in (raw_tool_set or [])
            ]
            if not steps:
                # No runnable tools declared — surface the agent profile as an
                # informational step so the UI still gets a truthful outcome.
                steps = [
                    {
                        "tool": agent_name,
                        "category": "agent",
                        "profile": {
                            "role": agent.role or "",
                            "tool_set": [],
                        },
                    }
                ]
        else:
            category = "mcp" if tool_name in MCP_EXECUTORS else "tool"
            steps = [{"tool": tool_name, "category": category}]

        failed = 0
        completed = 0
        for index, step in enumerate(steps, start=1):
            step_tool = step.get("tool") or ""
            category = step.get("category") or "tool"

            # Durable step log — created first so a cancel mid-run leaves a
            # ``stopped`` row (acceptance bar for abort correctness).
            row = await _create_execution_row(
                conversation_id=conversation_id,
                tool_name=step_tool,
                input_params=args or None,
                status="running",
                host_user_id=host_user_id,
            )

            if GENERATIONS.is_cancelled(conversation_id):
                await _save_execution_row(
                    row, "stopped", {"message": "Cancelled before execution"}
                )
                yield {
                    "type": "tool_start",
                    "turn_id": turn_id,
                    "step_id": index,
                    "tool": step_tool,
                    "category": category,
                }
                yield {"type": "tool_end", "step_id": index, "status": "stopped"}
                yield {
                    "type": "turn_end",
                    "turn_id": turn_id,
                    "status": "stopped",
                    "summary": "Stopped by user",
                }
                return

            yield {
                "type": "tool_start",
                "turn_id": turn_id,
                "step_id": index,
                "tool": step_tool,
                "category": category,
            }
            if verbosity == "full":
                yield {
                    "type": "tool_arg",
                    "step_id": index,
                    "args": args,
                }

            profile = step.get("profile")
            if profile is not None:
                result = {
                    "agent": step_tool,
                    **profile,
                    "note": "No runnable tools declared for this agent.",
                }
                await _save_execution_row(row, "completed", result)
                if verbosity == "full":
                    yield {
                        "type": "tool_result",
                        "step_id": index,
                        "result": _redact_secrets(result),
                    }
                yield {"type": "tool_end", "step_id": index, "status": "completed"}
                completed += 1
                continue

            executor_fn = executors.get(step_tool)
            if executor_fn is None:
                await _save_execution_row(
                    row, "failed", {"error": f"Unknown tool: {step_tool}"}
                )
                yield {"type": "tool_end", "step_id": index, "status": "failed"}
                failed += 1
                continue

            # Engine tool convention: executors are called with a single args
            # dict; the host executor + turn context ride along as keys, and
            # plugins receive the ToolContext (RULE_20/RULE_21).
            call_args = dict(args or {})
            call_args["executor"] = executor
            call_args["conversation_id"] = conversation_id
            set_tool_context(
                ToolContext(
                    instance_id=instance_id,
                    conversation_id=conversation_id,
                    host_user_id=host_user_id,
                    instance_config=instance_config,
                    host_api=executor,
                )
            )
            try:
                # Dispatch by signature: static tools declare named params and
                # accept **kwargs; plugin/MCP executors take the args dict
                # positionally. Unpack kwargs when the function accepts them.
                import inspect as _inspect

                try:
                    _sig = _inspect.signature(executor_fn)
                    _has_var_kw = any(
                        p.kind == _inspect.Parameter.VAR_KEYWORD
                        for p in _sig.parameters.values()
                    )
                    _all_named = all(k in _sig.parameters for k in call_args)
                except (TypeError, ValueError):
                    _has_var_kw, _all_named = False, False

                if _has_var_kw or _all_named:
                    result = await executor_fn(**call_args)
                else:
                    result = await executor_fn(call_args)
            except Exception as exc:  # noqa: BLE001 - fail-visible
                logger.exception("tool %s failed during action run", step_tool)
                result = {"error": str(exc)}
            if not isinstance(result, dict):
                result = {"result": result}

            if result.get("requires_confirmation"):
                # RULE_21 — never auto-run a mutation: the executor already
                # staged a pending ToolExecution row; surface its id so the
                # workspace confirm/decline flow can drive it.
                await _save_execution_row(row, "needs_confirmation", result)
                yield {
                    "type": "tool_end",
                    "step_id": index,
                    "status": "needs_confirmation",
                    "execution_id": result.get("execution_id"),
                }
                completed += 1
                continue

            if result.get("error"):
                await _save_execution_row(row, "failed", result)
                yield {"type": "tool_end", "step_id": index, "status": "failed"}
                failed += 1
                continue

            await _save_execution_row(row, "completed", result)
            if verbosity == "full":
                yield {
                    "type": "tool_result",
                    "step_id": index,
                    "result": _redact_secrets(result),
                }
            yield {"type": "tool_end", "step_id": index, "status": "completed"}
            completed += 1

        if failed:
            yield {
                "type": "turn_end",
                "turn_id": turn_id,
                "status": "failed",
                "summary": f"{failed} of {len(steps)} step(s) failed.",
            }
        else:
            yield {
                "type": "turn_end",
                "turn_id": turn_id,
                "status": "completed",
                "summary": f"{completed} step(s) completed.",
            }


def dispatch_action_stream(
    payload: dict[str, Any],
    *,
    instance_id: str = "carbon",
):
    """Stream an agent/tool action run as ``(kind, value)`` tuples.

    Parallel to :func:`dispatch_task_stream`: the action runner is async and
    this generator bridges it to a sync iterator with a ``queue.Queue`` and a
    daemon thread so Django views can consume it inside a
    ``StreamingHttpResponse`` without blocking the event loop.

    Payload::

        conversation_id  — conversation the run is attached to (abort key)
        action_type      — "tool" | "agent"
        tool             — tool name (action_type="tool")
        agent            — agent name (action_type="agent")
        args             — tool args dict
        verbosity        — "concise" | "full"
        host_user_id     — Django user PK (stamps ToolExecution rows)

    Yields:
        ("frame", frame)  — one clustered frame (turn_start / tool_start /
                            tool_arg / tool_result / tool_end / turn_end)
        ("done", result)  — terminal success ({"status": "completed"|"stopped"})
        ("error", message, {"error_kind": ...}) — terminal failure

    Cancellation between steps (``GENERATIONS.cancel``) yields
    ``tool_end{status:"stopped"}`` + ``turn_end{status:"stopped"}`` — never
    ``error``, never leaves the conversation stuck in ``working``.
    """
    q: queue.Queue = queue.Queue()

    async def _collect():
        final_status = "completed"
        try:
            async for frame in _run_action_stream(instance_id, payload):
                if frame.get("type") == "turn_end":
                    final_status = frame.get("status", final_status)
                q.put(("frame", frame))
            q.put(("done", {"status": final_status}))
        except Exception as exc:  # noqa: BLE001 - fail-visible contract
            from ai.engine.llm.provider import classify_llm_error

            logger.exception("action stream failed for instance=%s", instance_id)
            q.put(
                (
                    "error",
                    f"action failed: {exc}",
                    {"error_kind": classify_llm_error(exc)},
                )
            )
        finally:
            q.put(("eof", None))

    def _thread_target():
        _run_async(_collect())

    threading.Thread(target=_thread_target, daemon=True).start()

    while True:
        frame = q.get()
        if frame[0] == "eof":
            break
        yield frame


__all__ = [
    "MODULES",
    "list_modules",
    "dispatch_task",
    "dispatch_task_stream",
    "dispatch_action_stream",
    "get_task",
]
