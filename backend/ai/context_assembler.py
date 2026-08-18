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


def _resolve_mention_descriptors(mentions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve mention ids into compact entity descriptors."""
    if not mentions:
        return []

    from core.models import Module
    from dataschema.models import DataField, DataTable
    from dq.models import DQRule

    resolved: list[dict[str, Any]] = []
    model_map = {
        "table": DataTable,
        "datatable": DataTable,
        "rule": DQRule,
        "dqrule": DQRule,
        "field": DataField,
        "datafield": DataField,
        "module": Module,
    }

    for mention in mentions:
        if not isinstance(mention, dict):
            continue
        kind = str(mention.get("kind") or "").strip().lower()
        raw_id = mention.get("id")
        model = model_map.get(kind)
        if not model or raw_id is None:
            continue

        obj = model.objects.filter(pk=raw_id).first()
        if obj is None:
            continue

        if kind in ("table", "datatable"):
            resolved.append(
                {
                    "kind": "table",
                    "id": str(obj.id),
                    "name": obj.name,
                    "module_id": str(obj.module_id) if obj.module_id else None,
                }
            )
        elif kind in ("rule", "dqrule"):
            resolved.append(
                {
                    "kind": "rule",
                    "id": str(obj.id),
                    "name": obj.name,
                    "rule_type": obj.rule_type,
                }
            )
        elif kind in ("field", "datafield"):
            resolved.append(
                {
                    "kind": "field",
                    "id": str(obj.id),
                    "label": obj.label,
                    "type": obj.type,
                    "table_id": str(obj.data_table_id) if obj.data_table_id else None,
                }
            )
        elif kind == "module":
            resolved.append(
                {
                    "kind": "module",
                    "id": str(obj.id),
                    "name": obj.name,
                    "org_unit_id": str(obj.org_unit_id) if obj.org_unit_id else None,
                }
            )

    return resolved


def _workspace_context_message(conversation) -> dict[str, Any] | None:
    payload = getattr(conversation, "task_payload_json", {}) or {}
    ctx = WorkspaceContext.from_dict(payload.get("workspace_context"))
    if ctx is None:
        return None

    resolved_mentions = _resolve_mention_descriptors(ctx.mentions)
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
) -> tuple[list[dict[str, Any]], int]:
    """Retrieve durable long-term facts scoped to the requesting user/org.

    Scoping mirrors ``ai.store.scope_q`` and ``accounts.ai_scoping`` so no
    cross-user or cross-org fact ever leaks:

      * ``visibility`` in (global, shared) is visible to the instance; a
        ``private`` fact is visible only to its owner (``host_user_id``).
      * org subtree: superusers / ``["*"]`` see everything; everyone else sees
        facts in their org subtree plus null-org facts.

    Facts are stored under the single-tenant ``app_identifier="carbon"``
    (the learning bridge writes them there), so the query pins that app
    regardless of the conversation's domain ``app_identifier``.

    Deterministic + budgeted: newest + highest-confidence facts win, then the
    list is truncated once ``memory_budget`` tokens are spent.  Returns
    ``(facts, tokens_used)``; facts are plain dicts (no DB handles).
    """
    if scope is None or not getattr(scope, "user_identifier", ""):
        return [], 0

    from django.db.models import Q
    from django.utils import timezone

    from ai.models import MemoryLongTerm
    from ai.store import DEFAULT_APP_IDENTIFIER

    user_id = str(scope.user_identifier)
    now = timezone.now()

    qs = MemoryLongTerm.objects.filter(
        app_identifier=DEFAULT_APP_IDENTIFIER,
        archived=False,
        superseded_by__isnull=True,
    )
    qs = qs.filter(
        Q(valid_from__isnull=True) | Q(valid_from__lte=now),
        Q(valid_to__isnull=True) | Q(valid_to__gt=now),
    )

    # Visibility partition (mirror ai.store.scope_q).
    qs = qs.filter(
        Q(visibility="global")
        | Q(visibility="shared")
        | Q(visibility="private", host_user_id=user_id),
    )

    # Org partition. ``org_unit_id`` is a BigIntegerField; Scope carries
    # stringified org ids, so coerce to ints (drop anything non-numeric).
    org_unit_ids = list(getattr(scope, "org_unit_ids", None) or [])
    if not getattr(scope, "is_superuser", False) and "*" not in org_unit_ids:
        int_ids = [int(o) for o in org_unit_ids if str(o).isdigit()]
        if int_ids:
            qs = qs.filter(
                Q(org_unit_id__in=int_ids) | Q(org_unit_id__isnull=True)
            )
        else:
            qs = qs.filter(org_unit_id__isnull=True)

    # Deterministic preference: highest confidence first, then newest.
    qs = qs.order_by("-confidence", "-created_at")

    facts: list[dict[str, Any]] = []
    used_tokens = 0
    for fact in qs.iterator():
        content = (fact.content or "").strip()
        if not content:
            continue
        category = (fact.category or "").strip()
        tokens = _estimate_tokens(content) + _estimate_tokens(category)
        if used_tokens + tokens > memory_budget:
            break
        facts.append(
            {
                "category": category,
                "content": content,
                "confidence": float(fact.confidence or 1.0),
                "source": fact.source or "",
            }
        )
        used_tokens += tokens

    return facts, used_tokens


def _resolve_entity_attributes(entity, instance_id: str) -> list[str]:
    """Return an ENTITY's attribute names (prefix-stripped, deterministic).

    Attribute nodes are joined through ``KnowledgeEdge`` rows with
    ``relationship="HAS_ATTRIBUTE"``; the leading ``"<entity>."`` prefix that
    the schema bootstrap stores (e.g. ``"table.column"``) is stripped.  Order
    is deterministic: attribute node ``name``, then ``created_at``.
    """
    from ai.models import KnowledgeEdge, KnowledgeNode

    edges = KnowledgeEdge.objects.filter(
        instance_id=instance_id,
        relationship="HAS_ATTRIBUTE",
        source_node_id=entity.id,
    )
    target_ids = {edge.target_node_id for edge in edges}
    if not target_ids:
        return []

    attr_nodes = KnowledgeNode.objects.filter(
        instance_id=instance_id,
        id__in=target_ids,
    ).order_by("name", "created_at")

    prefix = f"{entity.name}."
    return [node.name.removeprefix(prefix) for node in attr_nodes]


def _retrieve_knowledge_graph(
    scope,
    retrieval_budget: int,
) -> tuple[list[dict[str, Any]], int]:
    """Retrieve schema knowledge-graph context for an AI turn.

    Unlike T4 (``_retrieve_long_term_memory``), the schema KG is
    app/instance-scoped *reference* data, not user/org-partitioned.  The
    bootstrap writes ``KnowledgeNode`` rows with ``visibility="private"``,
    ``org_unit_id=None``, ``host_user_id=None`` — copying T4's
    visibility/org partition would filter every node out.  Reference data is
    global (like emission factors), so T3 pins ``instance_id`` +
    ``app_identifier`` to ``DEFAULT_APP_IDENTIFIER``, filters
    ``node_type="ENTITY"``, and does NOT partition by visibility/org.

    Deterministic + budgeted: highest-confidence, newest entities win.  An
    entity whose base line (name + label + description) alone would exceed the
    remaining budget is skipped entirely; otherwise its attributes are
    appended greedily and truncated when the next attribute would exceed the
    budget.  Returns ``(entries, tokens_used)`` with no DB handles leaked.
    """
    if retrieval_budget <= 0:
        return [], 0

    from django.db.models import Q
    from django.utils import timezone

    from ai.models import KnowledgeNode
    from ai.store import DEFAULT_APP_IDENTIFIER

    now = timezone.now()
    qs = KnowledgeNode.objects.filter(
        app_identifier=DEFAULT_APP_IDENTIFIER,
        instance_id=DEFAULT_APP_IDENTIFIER,
        node_type="ENTITY",
    )
    qs = qs.filter(
        Q(valid_from__isnull=True) | Q(valid_from__lte=now),
        Q(valid_to__isnull=True) | Q(valid_to__gt=now),
    )
    qs = qs.order_by("-confidence", "-created_at")

    entries: list[dict[str, Any]] = []
    used_tokens = 0
    for entity in qs.iterator():
        base_tokens = (
            _estimate_tokens(entity.name or "")
            + _estimate_tokens("(ENTITY)")
            + _estimate_tokens(entity.description or "")
        )
        if used_tokens + base_tokens > retrieval_budget:
            continue

        used_tokens += base_tokens

        attributes: list[str] = []
        for attr in _resolve_entity_attributes(entity, DEFAULT_APP_IDENTIFIER):
            attr_tokens = _estimate_tokens(attr)
            if used_tokens + attr_tokens > retrieval_budget:
                break
            attributes.append(attr)
            used_tokens += attr_tokens

        entries.append(
            {
                "name": entity.name,
                "node_type": entity.node_type,
                "confidence": float(entity.confidence or 1.0),
                "attributes": attributes,
            }
        )

    return entries, used_tokens


_PROFILE_MAX_CHARS = 300


def _user_profile_message(scope, user) -> dict[str, Any] | None:
    """Build a compact ``[User Profile]`` system message (Phase 15).

    Derived server-side from the passed ``user`` (``conversation.user`` /
    ``request.user``) and the already-computed ``scope`` (``build_scope``) —
    never from client-sent identity (RULE_20). The numeric ``user_identifier``
    is deliberately omitted: it stays on the audit/scoping side only and never
    leaks into semantic context (RULE_23).

    Returns ``None`` (message skipped) when ``scope`` carries no
    ``user_identifier`` (anonymous/empty scope).
    """
    if scope is None or not getattr(scope, "user_identifier", ""):
        return None

    from accounts.models import ScopedRole
    from core.models import Module
    from mdm.models import OrgUnit

    parts: list[str] = []

    # Name: first/last, fall back to username.
    if user is not None:
        first = (getattr(user, "first_name", "") or "").strip()
        last = (getattr(user, "last_name", "") or "").strip()
        name = " ".join(part for part in (first, last) if part).strip()
        name = name or (getattr(user, "username", "") or "").strip()
        if name:
            parts.append(f"name={name}")

    # Active role names (deduped, order-preserving).
    role_names: list[str] = []
    if user is not None and getattr(user, "pk", None) is not None:
        for group_name in (
            ScopedRole.objects.filter(user=user, is_active=True)
            .select_related("group")
            .values_list("group__name", flat=True)
        ):
            if group_name and group_name not in role_names:
                role_names.append(group_name)
    if role_names:
        parts.append(f"roles={', '.join(role_names)}")

    # Org-unit names (scope ids, skip the "*" wildcard).
    org_ids = [
        o for o in (getattr(scope, "org_unit_ids", None) or []) if str(o) != "*"
    ]
    if org_ids:
        org_names = list(
            OrgUnit.objects.filter(id__in=org_ids).values_list("name", flat=True)
        )
        if org_names:
            parts.append(f"org_units={', '.join(org_names)}")

    # Module names (scope ids).
    module_ids = [
        m for m in (getattr(scope, "module_ids", None) or []) if str(m) != "*"
    ]
    if module_ids:
        module_names = list(
            Module.objects.filter(id__in=module_ids).values_list("name", flat=True)
        )
        if module_names:
            parts.append(f"modules={', '.join(module_names)}")

    # Access flags.
    parts.append(
        "read-only" if getattr(scope, "is_read_only", False) else "can write"
    )
    if getattr(scope, "is_superuser", False):
        parts.append("superuser")

    content = "[User Profile]\n" + "; ".join(parts)

    # Budget: cap at ~300 chars (~75 tokens) via the shared token estimator.
    if _estimate_tokens(content) > _PROFILE_MAX_CHARS // 4:
        content = content[: _PROFILE_MAX_CHARS - 1].rstrip() + "…"

    return {
        "role": "system",
        "content": content,
        "timestamp": None,
    }


def _user_memory_enabled(conversation) -> bool:
    """Phase 22-A — whether the conversation owner enables the T4 memory tier.

    Defaults to True when there is no profile row or the conversation carries
    no real user (anonymous).  A False ``memory_enabled`` skips long-term
    memory injection for this turn (the profile preference — never the
    per-message path — decides memory gating).
    """
    user = getattr(conversation, "user", None)
    if user is None or getattr(user, "pk", None) is None:
        return True
    from ai.models import AIUserProfile

    try:
        return AIUserProfile.objects.values_list(
            "memory_enabled", flat=True,
        ).get(user=user)
    except AIUserProfile.DoesNotExist:
        return True


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
    tiered: list[dict[str, Any]] = []

    # Phase 15 — user profile (server-derived; skipped when anonymous).
    profile_message = _user_profile_message(
        scope, getattr(conversation, "user", None)
    )
    if profile_message:
        tiered.append(profile_message)
    profile_content = profile_message["content"] if profile_message else None

    workspace_message = _workspace_context_message(conversation)
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
    if _user_memory_enabled(conversation):
        memory_facts, memory_tokens = _retrieve_long_term_memory(scope, memory_budget)
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
    kg_entries, kg_tokens = _retrieve_knowledge_graph(scope, retrieval_budget)
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
