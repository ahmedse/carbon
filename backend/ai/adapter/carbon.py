"""CarbonHostAdapter — the concrete Host Adapter for the Carbon platform.

Moves the Django ORM access that used to live inside
``ai/context_assembler.py`` behind the ``HostAdapterContract`` seam so the
assembler and engine stay injectable and testable without a live Django DB.

This module is the *only* place (besides ``ai/intelligence.py`` itself) that
reaches into Carbon's Django ORM for context assembly.  ``ai/context_assembler``
and ``ai/engine/**`` import nothing from Carbon domain apps directly.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Q
from django.utils import timezone

from accounts.capabilities import has_capability
from accounts.models import ScopedRole
from core.models import Module
from dataschema.models import DataField, DataTable
from dq.models import DQRule
from mdm.models import OrgUnit

from ai.models import (
    AIUserProfile,
    KnowledgeEdge,
    KnowledgeNode,
    MemoryLongTerm,
)
from ai.store import DEFAULT_APP_IDENTIFIER

from ai.adapter.contract import HostAdapterContract
from ai.adapter.types import (
    EntityDef,
    MemorySeed,
    SessionContext,
    ToolCatalog,
    ToolDef,
    VocabularyTerm,
    WorldModel,
)

# ~4 chars/token, mirrors ai.context_assembler._estimate_tokens.  Kept local so
# this module stays self-contained and independent of the assembler.
def _estimate_tokens(text: str) -> int:
    return max(0, len(text or "") // 4)


_PROFILE_MAX_CHARS = 300


class CarbonHostAdapter(HostAdapterContract):
    """Concrete host adapter backed by Carbon's Django ORM."""

    # ── WorldModel (registry-driven, never a hardcoded list) ────────────

    def get_world_model(self) -> WorldModel:
        from ai.domain_protocol import all_manifests, list_domains

        domains = list_domains()
        entities: list[EntityDef] = []
        vocabulary: list[VocabularyTerm] = []

        for manifest in all_manifests():
            app_id = manifest.get("app_identifier", "")
            display_name = manifest.get("display_name", app_id)
            for entry_point in manifest.get("entry_points", []) or []:
                entry_point = entry_point or {}
                on_entity = entry_point.get("on_entity")
                if not on_entity or on_entity == "*":
                    continue
                description = " ".join(
                    part for part in (
                        entry_point.get("label", on_entity),
                        entry_point.get("task_type", ""),
                    ) if part
                )
                entities.append(
                    EntityDef(
                        entity_type=on_entity,
                        name=on_entity,
                        description=description,
                    )
                )
            for task_type in manifest.get("supported_task_types", []) or []:
                vocabulary.append(
                    VocabularyTerm(
                        term=task_type,
                        definition=f"{display_name} domain task type",
                    )
                )

        return WorldModel(
            entities=entities,
            vocabulary=vocabulary,
            business_rules=[],
            domains=domains,
        )

    # ── Tool catalog ────────────────────────────────────────────────────

    def get_tool_catalog(self, user, scope) -> ToolCatalog:
        # Spine tools (engine function-calling definitions) + registry-driven
        # domain tools, CBAC-filtered per user. Never hardcode tool names here.
        from ai.engine.agent.tools import STATIC_TOOL_DEFINITIONS
        from ai.engine.cognition.turn.runner import _CHAT_STATIC_TOOLS
        from ai.domain_protocol import get_domain, list_domains

        definitions: dict[str, dict[str, Any]] = {}
        for entry in STATIC_TOOL_DEFINITIONS:
            if not isinstance(entry, dict):
                continue
            function = entry.get("function") or {}
            name = function.get("name")
            if name:
                definitions[name] = function

        tools: list[ToolDef] = []
        # Spine tools are always present (required_capability=None).
        for name in sorted(_CHAT_STATIC_TOOLS):
            function = definitions.get(name, {})
            tools.append(
                ToolDef(
                    id=name,
                    description=function.get("description", ""),
                    required_capability=None,
                    is_mutation=False,
                    domain="core",
                    input_schema=function.get("parameters", {}),
                    output_description="",
                )
            )

        # Domain tools — iterate the registry, collect each instance's
        # get_tools(), then CBAC-filter by the user's capabilities.
        for app_id in sorted(list_domains()):
            domain = get_domain(app_id)()
            for tool in domain.get_tools():
                if tool.required_capability is None or has_capability(
                    user, tool.required_capability
                ):
                    tools.append(tool)

        return ToolCatalog(tools=tools)

    # ── Session context (contract-level) ────────────────────────────────

    def assemble_context(
        self, query, user, scope, page_context
    ) -> SessionContext:
        messages: list[dict[str, Any]] = []

        profile = self.build_user_profile(scope, user)
        if profile:
            messages.append(profile)

        memory_facts, memory_tokens = self.retrieve_long_term_memory(scope, 1000)
        if memory_facts:
            lines = ["[Long-Term Memory]"]
            for fact in memory_facts:
                lines.append(
                    f"- ({fact['category']}, confidence {fact['confidence']:.2f}) "
                    f"{fact['content']}"
                )
            messages.append(
                {"role": "system", "content": "\n".join(lines), "timestamp": None}
            )

        kg_entries, kg_tokens = self.retrieve_knowledge_graph(scope, 2000)
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
            messages.append(
                {"role": "system", "content": "\n".join(lines), "timestamp": None}
            )

        if query:
            messages.append({"role": "user", "content": query, "timestamp": None})

        return SessionContext(
            messages=messages,
            budget={"T3_retrieval": kg_tokens, "T4_memory": memory_tokens},
            kg_entities=kg_entries,
            context_signature="",
        )

    # ── Memory seeds ────────────────────────────────────────────────────

    def get_org_memory_seeds(self, instance_id: str) -> list[MemorySeed]:
        qs = MemoryLongTerm.objects.filter(
            instance_id=instance_id,
            archived=False,
            superseded_by__isnull=True,
        ).order_by("-confidence", "-created_at")

        seeds: list[MemorySeed] = []
        for fact in qs.iterator():
            content = (fact.content or "").strip()
            if not content:
                continue
            seeds.append(
                MemorySeed(
                    category=(fact.category or "").strip(),
                    content=content,
                    source=fact.source or "",
                    confidence=float(fact.confidence or 1.0),
                )
            )
        return seeds

    # ── Context-retrieval seam (moved verbatim from context_assembler) ──

    def resolve_mentions(self, mentions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Resolve mention ids into compact entity descriptors."""
        if not mentions:
            return []

        resolved: list[dict[str, Any]] = []
        model_map = {
            "table": DataTable,
            "datatable": DataTable,
            "rule": DQRule,
            "dqrule": DQRule,
            "field": DataField,
            "datafield": DataField,
            "module": Module,
            "org-unit": OrgUnit,
            "orgunit": OrgUnit,
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
            elif kind in ("org-unit", "orgunit"):
                resolved.append(
                    {
                        "kind": "org-unit",
                        "id": str(obj.id),
                        "name": obj.name,
                        "org_type": obj.org_type,
                    }
                )

        return resolved

    def retrieve_long_term_memory(
        self,
        scope,
        memory_budget: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Retrieve durable long-term facts scoped to the requesting user/org.

        Scoping mirrors ``ai.store.scope_q`` and ``accounts.ai_scoping`` so no
        cross-user or cross-org fact ever leaks.  Deterministic + budgeted:
        newest + highest-confidence facts win, truncated once ``memory_budget``
        tokens are spent.  Returns ``(facts, tokens_used)`` with plain dicts.
        """
        if scope is None or not getattr(scope, "user_identifier", ""):
            return [], 0

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

    def resolve_entity_attributes(self, entity, instance_id: str) -> list[str]:
        """Return an ENTITY's attribute names (prefix-stripped, deterministic)."""
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

    def retrieve_knowledge_graph(
        self,
        scope,
        retrieval_budget: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Retrieve schema knowledge-graph context for an AI turn.

        App/instance-scoped reference data (not user/org-partitioned): pins
        ``instance_id`` + ``app_identifier`` to ``DEFAULT_APP_IDENTIFIER``,
        filters ``node_type="ENTITY"``.  Deterministic + budgeted; returns
        ``(entries, tokens_used)`` with no DB handles leaked.
        """
        if retrieval_budget <= 0:
            return [], 0

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
            for attr in self.resolve_entity_attributes(
                entity, DEFAULT_APP_IDENTIFIER
            ):
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

    def build_user_profile(self, scope, user) -> dict[str, Any] | None:
        """Build a compact ``[User Profile]`` system message (Phase 15)."""
        if scope is None or not getattr(scope, "user_identifier", ""):
            return None

        parts: list[str] = []

        if user is not None:
            first = (getattr(user, "first_name", "") or "").strip()
            last = (getattr(user, "last_name", "") or "").strip()
            name = " ".join(part for part in (first, last) if part).strip()
            name = name or (getattr(user, "username", "") or "").strip()
            if name:
                parts.append(f"name={name}")

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

        org_ids = [
            o for o in (getattr(scope, "org_unit_ids", None) or []) if str(o) != "*"
        ]
        if org_ids:
            org_names = list(
                OrgUnit.objects.filter(id__in=org_ids).values_list("name", flat=True)
            )
            if org_names:
                parts.append(f"org_units={', '.join(org_names)}")

        module_ids = [
            m for m in (getattr(scope, "module_ids", None) or []) if str(m) != "*"
        ]
        if module_ids:
            module_names = list(
                Module.objects.filter(id__in=module_ids).values_list("name", flat=True)
            )
            if module_names:
                parts.append(f"modules={', '.join(module_names)}")

        parts.append(
            "read-only" if getattr(scope, "is_read_only", False) else "can write"
        )
        if getattr(scope, "is_superuser", False):
            parts.append("superuser")

        content = "[User Profile]\n" + "; ".join(parts)

        if _estimate_tokens(content) > _PROFILE_MAX_CHARS // 4:
            content = content[: _PROFILE_MAX_CHARS - 1].rstrip() + "…"

        return {
            "role": "system",
            "content": content,
            "timestamp": None,
        }

    def user_memory_enabled(self, conversation) -> bool:
        """Whether the conversation owner enables the T4 memory tier."""
        user = getattr(conversation, "user", None)
        if user is None or getattr(user, "pk", None) is None:
            return True

        try:
            return AIUserProfile.objects.values_list(
                "memory_enabled", flat=True,
            ).get(user=user)
        except AIUserProfile.DoesNotExist:
            return True
