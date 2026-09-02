"""Tiered, budgeted context assembly for AI conversations.

Sprint 15 — replaces the prior "send ALL history every turn" behaviour with a
tiered assembler that caps verbatim history and budgets the knowledge-graph (T3)
and long-term memory (T4) retrieval tiers.

Token estimates are approximate: ``len(text) // 4`` (~4 chars/token).
"""

from __future__ import annotations

from typing import Any

from ai.protocol import WorkspaceContext


def _estimate_tokens(text: str) -> int:
    """Approximate token count at ~4 characters per token."""
    return max(0, len(text or "") // 4)


def _default_adapter():
    """Lazily instantiate the default host adapter (avoids import cycles).

    The adapter is the single seam through which context assembly reaches the
    host ORM; callers may inject their own ``HostAdapterContract`` (or a mock)
    to test without a live Django DB.
    """
    from ai.adapter.carbon import CarbonHostAdapter

    return CarbonHostAdapter()


def _compute_context_signature(
    message_ids: list[str],
    model: str | None,
    profile_content: str | None,
) -> str:
    """Return an opaque, short SHA-256 hash of the assembled context window.

    The signature captures the *identity* of the window (message-id vector),
    the requested model, and the user-profile content — never any message text
    (Phase 19-A).  It lets a retry/regenerate detect context drift and rebuild
    the exact window even after later messages are added or deleted.
    """
    import hashlib

    payload = "\x1f".join(
        [
            "\x00".join(message_ids),
            model or "",
            profile_content or "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _resolve_mention_descriptors(
    mentions: list[dict[str, Any]],
    adapter=None,
) -> list[dict[str, Any]]:
    """Resolve mention ids into compact entity descriptors (via the adapter)."""
    adapter = adapter or _default_adapter()
    return adapter.resolve_mentions(mentions)


def _workspace_context_message(conversation, adapter=None) -> dict[str, Any] | None:
    payload = getattr(conversation, "task_payload_json", {}) or {}
    ctx = WorkspaceContext.from_dict(payload.get("workspace_context"))
    if ctx is None:
        return None

    resolved_mentions = _resolve_mention_descriptors(ctx.mentions, adapter)
    lines = ["[Workspace Context]", ctx.to_prompt_prefix()]
    if resolved_mentions:
        lines.append("[Resolved Mentions]")
        for mention in resolved_mentions:
            bits = [f"id={mention['id']}"]
            if mention.get("name"):
                bits.insert(0, f"name={mention['name']}")
            if mention.get("label"):
                bits.insert(0, f"label={mention['label']}")
            if mention.get("rule_type"):
                bits.append(f"rule_type={mention['rule_type']}")
            if mention.get("type"):
                bits.append(f"type={mention['type']}")
            if mention.get("module_id"):
                bits.append(f"module_id={mention['module_id']}")
            if mention.get("table_id"):
                bits.append(f"table_id={mention['table_id']}")
            if mention.get("org_unit_id"):
                bits.append(f"org_unit_id={mention['org_unit_id']}")
            lines.append(f"- {mention['kind']}: " + ", ".join(bits))

    return {
        "role": "system",
        "content": "\n".join(lines),
        "timestamp": None,
    }


def _retrieve_long_term_memory(
    scope,
    memory_budget: int,
    adapter=None,
) -> tuple[list[dict[str, Any]], int]:
    """Retrieve durable long-term facts scoped to the requesting user/org.

    Delegated to the host adapter (T4).  Returns ``(facts, tokens_used)`` with
    plain dicts (no DB handles).
    """
    adapter = adapter or _default_adapter()
    return adapter.retrieve_long_term_memory(scope, memory_budget)


def _resolve_entity_attributes(entity, instance_id: str, adapter=None) -> list[str]:
    """Return an ENTITY's attribute names (prefix-stripped, deterministic).

    Delegated to the host adapter.
    """
    adapter = adapter or _default_adapter()
    return adapter.resolve_entity_attributes(entity, instance_id)


def _retrieve_knowledge_graph(
    scope,
    retrieval_budget: int,
    adapter=None,
) -> tuple[list[dict[str, Any]], int]:
    """Retrieve schema knowledge-graph context for an AI turn.

    Delegated to the host adapter (T3).  Returns ``(entries, tokens_used)``
    with no DB handles leaked.
    """
    adapter = adapter or _default_adapter()
    return adapter.retrieve_knowledge_graph(scope, retrieval_budget)


def _user_profile_message(scope, user, adapter=None) -> dict[str, Any] | None:
    """Build a compact ``[User Profile]`` system message (Phase 15).

    Delegated to the host adapter.  Returns ``None`` (message skipped) when
    ``scope`` carries no ``user_identifier`` (anonymous/empty scope).
    """
    adapter = adapter or _default_adapter()
    return adapter.build_user_profile(scope, user)


def _user_memory_enabled(conversation, adapter=None) -> bool:
    """Phase 22-A — whether the conversation owner enables the T4 memory tier.

    Delegated to the host adapter.
    """
    adapter = adapter or _default_adapter()
    return adapter.user_memory_enabled(conversation)


def assemble_context(
    conversation,
    messages,
    scope,
    *,
    recent_turns: int = 8,
    summary_budget: int = 1500,
    retrieval_budget: int = 2000,
    memory_budget: int = 1000,
    model: str | None = None,
    adapter=None,
) -> dict[str, Any]:
    """Assemble tiered, budgeted context for a conversation turn.

    Tier rules:
      * T2 history  — the most recent ``recent_turns`` messages verbatim;
                      anything older is NOT sent.
      * T2b summary — prepend ``conversation.summary`` (as a system note) when
                      non-empty.
      * T3 retrieval — app/instance-scoped schema knowledge graph
                       (``_retrieve_knowledge_graph``) injected as a system
                       note and capped at ``retrieval_budget``.  Reference data
                       is NOT visibility/org-partitioned (unlike T4).
      * T4 memory    — durable long-term facts scoped to the requesting user/org
                       (``_retrieve_long_term_memory``), injected as a system
                       note and capped at ``memory_budget``.

    ``scope`` is used for T4 memory retrieval; T3 is instance-scoped and does
    not gate on ``scope``.  ``summary_budget`` gates summary inclusion.
    Cross-user/cross-org reads never happen (memory is visibility + org scoped).

    Returns ``{"messages": [...], "budget": {tier: token_estimate},
    "kg_entities": [...], "context_signature": sha256hex}``.  The ``messages``
    list is the verbatim history actually sent to the provider; the ``budget``
    dict records token telemetry for every tier.  T3 and T4 report the tokens
    actually injected.  ``context_signature`` (Phase 19-A) is an opaque hash of
    the message-id vector + model + profile — no message text is stored.
    """
    adapter = adapter or _default_adapter()

    tiered: list[dict[str, Any]] = []

    # Phase 15 — user profile (server-derived; skipped when anonymous).
    profile_message = _user_profile_message(
        scope, getattr(conversation, "user", None), adapter
    )
    if profile_message:
        tiered.append(profile_message)
    profile_content = profile_message["content"] if profile_message else None

    workspace_message = _workspace_context_message(conversation, adapter)
    if workspace_message:
        tiered.append(workspace_message)

    # T2b — rolling compaction summary as the leading system note.
    summary = getattr(conversation, "summary", "") or ""
    summary_tokens = _estimate_tokens(summary)
    include_summary = bool(summary) and summary_tokens <= summary_budget
    if include_summary:
        tiered.append(
            {
                "role": "system",
                "content": f"[Summary]\n{summary}",
                "timestamp": None,
            }
        )

    # T4 — durable long-term memory facts as a compact system note.
    # Phase 22-A: gated by the user's ``memory_enabled`` preference — a user
    # who turns personal memory off gets no T4 tier this turn.
    memory_facts, memory_tokens = [], 0
    if _user_memory_enabled(conversation, adapter):
        memory_facts, memory_tokens = _retrieve_long_term_memory(
            scope, memory_budget, adapter
        )
    if memory_facts:
        lines = ["[Long-Term Memory]"]
        for fact in memory_facts:
            lines.append(
                f"- ({fact['category']}, confidence {fact['confidence']:.2f}) "
                f"{fact['content']}"
            )
        tiered.append(
            {
                "role": "system",
                "content": "\n".join(lines),
                "timestamp": None,
            }
        )

    # T3 — app/instance-scoped schema knowledge graph (NOT user/org-partitioned).
    kg_entries, kg_tokens = _retrieve_knowledge_graph(scope, retrieval_budget, adapter)
    if kg_entries:
        lines = ["[Knowledge Graph]"]
        for entry in kg_entries:
            attrs = (
                ", ".join(entry["attributes"])
                if entry["attributes"]
                else "(no attributes)"
            )
            lines.append(
                f"- {entry['name']} (ENTITY, confidence {entry['confidence']:.2f}): {attrs}"
            )
        tiered.append(
            {
                "role": "system",
                "content": "\n".join(lines),
                "timestamp": None,
            }
        )

    # Phase 19-A — soft-deleted messages never consume budget; filter them out
    # BEFORE the recent-turns window is truncated.
    live_messages = [m for m in messages if not m.get("is_deleted")]

    # T2 — most recent turns verbatim; anything older is NOT sent.
    recent = list(live_messages[-recent_turns:])
    for message in recent:
        created_at = message.get("created_at")
        tiered.append(
            {
                "role": message.get("role"),
                "content": message.get("content"),
                "timestamp": (
                    created_at.isoformat() if created_at is not None else None
                ),
            }
        )

    budget = {
        "T2_history": sum(_estimate_tokens(m["content"]) for m in recent),
        "T2b_summary": summary_tokens if include_summary else 0,
        "T3_retrieval": kg_tokens,
        "T4_memory": memory_tokens,
    }

    # Phase 19-A — opaque context signature of the window actually sent.
    message_ids = [str(m["id"]) for m in recent if m.get("id") is not None]
    context_signature = _compute_context_signature(
        message_ids, model, profile_content
    )

    return {
        "messages": tiered,
        "budget": budget,
        "kg_entities": kg_entries,
        "context_signature": context_signature,
    }
