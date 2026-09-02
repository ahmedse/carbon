"""``cross_synthesize`` — join already-fetched cross-domain results via the KG.

The assistant gathers answers from several domain tools first; this tool joins
those *already-retrieved* results into one answer, naming which domain each
fact came from.  Provenance is verifiable because the join goes through the
knowledge graph — shared entity nodes and the temporal/causal edges between
them — never through an LLM "combine the text" step and never by re-querying a
domain database.

Guardrails honored:

  * **RULE_20** — zero upward imports: this module imports only ``ai.engine.*``
    plus stdlib/typing.  It never touches the Django ORM or a domain app
    directly; KG access is ``get_session_factory(instance_id)`` →
    ``KnowledgeGraphStore`` (the ``ai.engine`` store is the only thing that
    reaches the data layer).
  * **RULE_21** — read-only: ``requires_confirmation=False``; nothing is staged
    and nothing is written.
  * **Fail-visible** — if the KG cannot be reached, per-domain provenance is
    still returned and ``shared_nodes`` stays empty, so the synthesis never
    fabricates a connection and the tool never raises into the turn.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ai.engine.agent.plugins import ToolPlugin

logger = logging.getLogger("carbon.ai.plugins.cross_synthesize")

# Relationships that express a temporal/causal link worth surfacing.
_ALIGNMENT_RELATIONSHIPS = ("TRIGGERS", "FEEDS_INTO", "DEPENDS_ON", "RELATED_TO")


def _iso(value: Any) -> str | None:
    """Render a datetime/str as an ISO string (or None), never raise."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return value.isoformat()
    except Exception:  # noqa: BLE001 — provenance must not raise
        return str(value)


class CrossDomainSynthesisTool(ToolPlugin):
    name = "cross_synthesize"
    description = (
        "Combine results already retrieved from multiple domains into one "
        "answer, citing which domain each fact came from."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "description": "Results already fetched from the domain tools.",
                "items": {
                    "type": "object",
                    "properties": {
                        "domain": {"type": "string"},
                        "data": {"type": "object"},
                        "entity_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["domain", "data"],
                },
            },
            "question": {"type": "string"},
        },
        "required": ["results", "question"],
    }
    requires_confirmation = False
    # Platform Core — always active; per-domain CBAC was already enforced when
    # each domain tool produced its result.
    capability: str | None = None
    app_identifier: str | None = None

    async def execute(self, args: dict, *, ctx) -> dict:
        results = self._validated_results(args)
        if results is None:
            return {
                "error": (
                    "'results' must be a non-empty list of objects, each with "
                    "a 'domain' and a 'data'."
                ),
                "requires_confirmation": False,
            }

        # Provenance is built straight from the passed results — it never
        # depends on the KG, so it is always available.
        sources = self._build_sources(results)
        instance_id = getattr(ctx, "instance_id", "") or ""

        shared_nodes: list[dict[str, Any]] = []
        temporal_alignment: list[dict[str, Any]] = []
        kg_ok = False

        try:
            from ai.engine.core.database import get_session_factory
            from ai.engine.knowledge_graph.store import KnowledgeGraphStore

            factory = get_session_factory(instance_id)
            async with factory() as db:
                store = KnowledgeGraphStore(db)
                nodes_by_id, node_domains = await self._resolve_entities(
                    store, results, instance_id
                )
                shared_nodes = self._shared_nodes(nodes_by_id, node_domains)
                temporal_alignment = await self._temporal_alignment(
                    store, nodes_by_id, node_domains, instance_id
                )
                kg_ok = True
        except Exception as exc:  # fail-visible — never raise into the turn
            logger.warning(
                "cross_synthesize KG join failed for %r: %s", instance_id, exc
            )

        synthesis = self._build_synthesis(
            sources, shared_nodes, temporal_alignment, kg_ok
        )
        return {
            "synthesis": synthesis,
            "sources": sources,
            "shared_nodes": shared_nodes,
            "temporal_alignment": temporal_alignment,
            "requires_confirmation": False,
        }

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _validated_results(args: dict) -> list[dict] | None:
        results = args.get("results")
        if not isinstance(results, list) or not results:
            return None
        valid: list[dict] = []
        for item in results:
            if not isinstance(item, dict):
                return None
            if not item.get("domain") or "data" not in item:
                return None
            valid.append(item)
        return valid

    def _build_sources(self, results: list[dict]) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for result in results:
            sources.append(
                {
                    "domain": result.get("domain", ""),
                    "entity_ids": list(result.get("entity_ids") or []),
                    "evidence": self._evidence(result.get("data")),
                }
            )
        return sources

    @staticmethod
    def _evidence(data: Any, limit: int = 5) -> str:
        """A short, honest summary of the passed data — never fabricated."""
        if not isinstance(data, dict) or not data:
            return ""
        parts: list[str] = []
        for key, value in list(data.items())[:limit]:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, default=str)
            text = str(value)
            if len(text) > 80:
                text = text[:80] + "…"
            parts.append(f"{key}: {text}")
        return "; ".join(parts)

    @staticmethod
    async def _resolve_entities(store, results, instance_id):
        """Resolve ENTITY nodes referenced (by id or name) by each domain.

        Returns ``(nodes_by_id, node_domains)`` where ``node_domains`` maps a
        resolved node id → the set of domains that referenced it.
        """
        nodes = await store.get_nodes_by_type("ENTITY", instance_id)
        nodes_by_id: dict[str, Any] = {n.id: n for n in nodes}
        nodes_by_name: dict[str, Any] = {
            n.name.lower(): n for n in nodes if n.name
        }

        node_domains: dict[str, set[str]] = {}
        for result in results:
            domain = result.get("domain", "")
            for ref in result.get("entity_ids") or []:
                key = str(ref)
                node = nodes_by_id.get(key) or nodes_by_name.get(key.lower())
                if node is not None:
                    node_domains.setdefault(node.id, set()).add(domain)
        return nodes_by_id, node_domains

    @staticmethod
    def _shared_nodes(nodes_by_id, node_domains) -> list[dict[str, Any]]:
        shared: list[dict[str, Any]] = []
        for node_id, domains in node_domains.items():
            if len(domains) >= 2:
                node = nodes_by_id[node_id]
                shared.append(
                    {
                        "id": node.id,
                        "name": node.name,
                        "node_type": node.node_type,
                    }
                )
        return shared

    @staticmethod
    async def _temporal_alignment(
        store, nodes_by_id, node_domains, instance_id
    ) -> list[dict[str, Any]]:
        """Surface temporal/causal edges between the resolved entity nodes."""
        resolved_ids = set(node_domains.keys())
        if len(resolved_ids) < 2:
            return []

        edges = await store.query_edges(instance_id)
        alignment: list[dict[str, Any]] = []
        for edge in edges:
            if (
                edge.source_node_id not in resolved_ids
                or edge.target_node_id not in resolved_ids
                or edge.relationship not in _ALIGNMENT_RELATIONSHIPS
            ):
                continue
            source = nodes_by_id.get(edge.source_node_id)
            target = nodes_by_id.get(edge.target_node_id)
            alignment.append(
                {
                    "relationship": edge.relationship,
                    "source": {
                        "id": edge.source_node_id,
                        "name": getattr(source, "name", edge.source_node_id),
                        "valid_from": _iso(getattr(source, "valid_from", None)),
                        "valid_to": _iso(getattr(source, "valid_to", None)),
                    },
                    "target": {
                        "id": edge.target_node_id,
                        "name": getattr(target, "name", edge.target_node_id),
                        "valid_from": _iso(getattr(target, "valid_from", None)),
                        "valid_to": _iso(getattr(target, "valid_to", None)),
                    },
                }
            )
        return alignment

    @staticmethod
    def _build_synthesis(
        sources, shared_nodes, temporal_alignment, kg_ok
    ) -> str:
        domains = [s["domain"] for s in sources if s.get("domain")]
        domain_phrase = ", ".join(domains) if domains else "the provided results"

        sentences = [
            f"Combined results from {len(sources)} domain(s): {domain_phrase}."
        ]

        if not kg_ok:
            sentences.append(
                "Entity connections could not be verified, so only the "
                "per-domain findings are reported."
            )
        elif shared_nodes:
            names = ", ".join(n["name"] for n in shared_nodes)
            label = "entity" if len(shared_nodes) == 1 else "entities"
            sentences.append(
                f"These domains describe the same {label}: {names}."
            )
        else:
            sentences.append(
                "The results reference separate entities, so no shared entity "
                "connects them."
            )

        if temporal_alignment:
            links = []
            for t in temporal_alignment:
                rel = t["relationship"].lower().replace("_", " ")
                links.append(f"{t['source']['name']} {rel} {t['target']['name']}")
            sentences.append(
                "Connections between them: " + "; ".join(links) + "."
            )

        return " ".join(sentences)
