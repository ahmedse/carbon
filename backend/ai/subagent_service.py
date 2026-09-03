"""Wave I4-B — user-dispatched read-only subagent service."""
from __future__ import annotations

import asyncio
import logging
import threading
import time

from django.utils import timezone

from ai.models import AISubagent

SUBAGENT_READONLY_TOOLS = frozenset({
    "search_knowledge", "get_entity_details", "query_knowledge_graph",
    "get_schema_info", "get_relationship_info", "get_table_profile",
    "web_research",
})

MUTATION_TOOLS_DENIED = frozenset({
    "create_dq_rule", "call_host_api", "learn_fact", "forget_fact",
    "run_ops_workflow", "invoke_skill", "code.execute", "export_document",
    "delegate_to_workers", "synthesize_worker_results",
    "plan_task", "edit_plan", "approve_plan",
})

logger = logging.getLogger("carbon.ai.subagent_service")


def resolve_subagent_tool_definitions() -> list[dict]:
    """Read-only tool definitions for a subagent (unified static+plugin+MCP)."""
    from ai.engine.agent.tools import get_tool_definitions
    return [td for td in get_tool_definitions() if td["function"]["name"] in SUBAGENT_READONLY_TOOLS]


def _build_subagent_messages(name: str, brief: str, scope_restriction: dict | None = None) -> list[dict]:
    parts = [f"You are the '{name}' subagent, a read-only research assistant."]
    parts.append(f"Task: {brief}")
    if scope_restriction:
        parts.append("Scope restriction:")
        for k, v in scope_restriction.items():
            parts.append(f"  {k}: {v}")
    return [
        {"role": "system", "content": "\n".join(parts)},
        {"role": "user", "content": brief},
    ]


def serialize_subagent(sub) -> dict:
    return {
        "id": sub.id,
        "parent_conversation_id": sub.parent_conversation_id,
        "name": sub.name,
        "status": sub.status,
        "is_worker": sub.is_worker,
        "scope_restriction": sub.scope_restriction or {},
        "tool_allowlist": sub.tool_allowlist_json or [],
        "result_summary": sub.result_summary,
        "result_detail": sub.result_detail,
        "error": sub.error,
        "tokens_used": sub.tokens_used,
        "latency_ms": sub.latency_ms,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
        "completed_at": sub.completed_at.isoformat() if sub.completed_at else None,
    }


class SubagentService:
    """Dispatch + run read-only subagents (Wave I4-B)."""

    async def _invoke_llm(self, sub, messages, tool_defs) -> dict:
        from ai.engine.llm.router import route_chat
        from ai.engine.core.database import get_session_factory
        factory = get_session_factory("carbon")
        async with factory() as db:
            return await route_chat(
                task="chat",
                instance_id="carbon",
                conversation_id=f"subagent-{sub.id}",
                messages=messages,
                tools=tool_defs or None,
                db=db,
            )

    def run_subagent(self, subagent_id) -> AISubagent:
        sub = AISubagent.objects.get(id=subagent_id)
        sub.status = "running"
        sub.tool_allowlist_json = sorted(SUBAGENT_READONLY_TOOLS)
        sub.save(update_fields=["status", "tool_allowlist_json"])
        tool_defs = resolve_subagent_tool_definitions()
        messages = _build_subagent_messages(sub.name, sub.brief, sub.scope_restriction)
        t0 = time.monotonic()
        try:
            resp = asyncio.run(self._invoke_llm(sub, messages, tool_defs))
            content = (resp or {}).get("content") or ""
            sub.result_summary = content[:200].strip()
            sub.result_detail = content[:2000] if len(content) > 200 else content
            sub.tokens_used = int((resp or {}).get("input_tokens", 0)) + int((resp or {}).get("output_tokens", 0))
            sub.status = "completed"
        except Exception as exc:  # noqa: BLE001 — fail-visible, never raise into caller
            logger.exception("Subagent %s failed", subagent_id)
            sub.status = "failed"
            sub.error = str(exc)
        sub.latency_ms = (time.monotonic() - t0) * 1000
        sub.completed_at = timezone.now()
        sub.save()
        return sub

    def dispatch_subagent(self, user, conversation, *, name, brief, scope_restriction=None, tool_budget=None, run_async=True) -> AISubagent:
        sub = AISubagent.objects.create(
            parent_conversation_id=str(conversation.id),
            name=name,
            brief=brief,
            scope_restriction=scope_restriction,
            tool_budget=tool_budget,
            host_user_id=str(user.pk),
            app_identifier="carbon",
            visibility="private",
            status="pending",
            is_worker=True,
        )
        if run_async:
            threading.Thread(target=self.run_subagent, args=(sub.id,), daemon=True).start()
        return sub

    def get_subagent(self, user, conversation_id, sub_id) -> AISubagent | None:
        sub = AISubagent.objects.filter(id=sub_id, parent_conversation_id=str(conversation_id)).first()
        if sub is None:
            return None
        if sub.host_user_id not in (None, str(user.pk)):
            return None
        return sub

    def list_subagents(self, user, conversation_id) -> list[AISubagent]:
        """Return this conversation's subagents (CBAC-scoped), newest first."""
        from django.db.models import Q

        return list(
            AISubagent.objects.filter(
                Q(parent_conversation_id=str(conversation_id))
                & (Q(host_user_id__isnull=True) | Q(host_user_id=str(user.pk)))
            ).order_by("-created_at")
        )
