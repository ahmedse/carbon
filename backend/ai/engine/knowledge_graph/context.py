"""
Graph-aware context assembly for the LLM prompt (formerly retrieval.py).

Replaces the old "dump all schema descriptions" approach with a targeted
subgraph that contains only what's relevant to the user's query.

BE-02-2: Added rerank_with_llm() for LLM-based candidate reranking and
fuse_scores() for pgvector+BM25 score fusion.
"""

import json
import logging
from typing import TYPE_CHECKING

from ai.engine.core.config import get_settings
from ai.models.knowledge_graph import KnowledgeNode
from ai.store import first

if TYPE_CHECKING:
    from ai.engine.knowledge_graph.store import KnowledgeGraphStore

logger = logging.getLogger("pulse.knowledge_graph.context")

# Rough tokens-per-character for English prose
_CHARS_PER_TOKEN = 4
# Importance threshold above which an entity is pulled into context even as a non-seed
_IMPORTANCE_BOOST_THRESHOLD = 0.7


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _normalize_scores(
    items: list[tuple[str, float]],
) -> dict[str, float]:
    """Min-max normalize a list of (id, score) tuples to [0, 1]."""
    if not items:
        return {}
    scores = [s for _, s in items]
    min_s, max_s = min(scores), max(scores)
    if max_s == min_s:
        return {nid: 0.5 for nid, _ in items}  # all equal
    return {nid: (s - min_s) / (max_s - min_s) for nid, s in items}


def fuse_scores(
    vector_results: list[tuple[str, float]],
    bm25_results: list[tuple[str, float]],
    alpha: float = 0.6,
) -> list[dict]:
    """Fuse pgvector and BM25 scores using weighted linear combination.

    alpha: weight for vector scores. BM25 weight = 1 - alpha.
    Returns list of dicts: [{node_id, name, description, vector_score, bm25_score, fused_score}]
    sorted by fused_score descending.
    """
    vec_norm = _normalize_scores(vector_results)
    bm25_norm = _normalize_scores(bm25_results)

    all_ids: set[str] = set(vec_norm.keys()) | set(bm25_norm.keys())

    fused: list[dict] = []
    for nid in sorted(all_ids):
        v_score = vec_norm.get(nid, 0.0)
        b_score = bm25_norm.get(nid, 0.0)
        fused_score = alpha * v_score + (1 - alpha) * b_score
        fused.append({
            "node_id": nid,
            "vector_score": round(v_score, 4),
            "bm25_score": round(b_score, 4),
            "fused_score": round(fused_score, 4),
        })

    # Deterministic total order: score desc, then node_id asc on ties
    fused.sort(key=lambda x: (-x["fused_score"], x["node_id"]))
    return fused


async def rerank_with_llm(
    query: str,
    candidates: list[dict],
    instance_id: str,
    top_k: int = 10,
) -> list[dict]:
    """LLM rerank: given query + candidates, return top_k ranked by relevance.

    Uses route_chat(task="cognition") with a structured rerank prompt.
    Falls back to score fusion ordering if LLM call fails.

    Args:
        query: The user's search query.
        candidates: List of dicts with keys: node_id, name, description,
                    vector_score, bm25_score, fused_score.
        instance_id: Pulse instance ID.
        top_k: Maximum number of results to return.

    Returns:
        Candidates reordered with added 'relevance' and 'reason' fields.
    """
    if not candidates:
        return []

    settings = get_settings()
    if not settings.RETRIEVAL_LLM_RERANK:
        # Skip rerank, just annotate top_k with the fused scores
        return candidates[:top_k]

    try:
        from ai.engine.llm.router import route_chat

        # Build candidate list for the LLM
        candidate_lines: list[str] = []
        for i, c in enumerate(candidates):
            name = c.get("name", c.get("node_id", "unknown"))
            desc = c.get("description", "")[:200]
            candidate_lines.append(f"[{i}] {name}: {desc}")

        candidates_text = "\n".join(candidate_lines)

        rerank_prompt = f"""You are a search relevance judge. Given a user query and a list of candidate results, rank them by relevance to the query.

User query: {query}

Candidates:
{candidates_text}

Return JSON with ONLY these fields:
{{"ranked": [{{"index": <int>, "relevance": "high"|"medium"|"low", "reason": "<brief>"}}]}}

- Include only candidates that are actually relevant to the query.
- Discard completely irrelevant ones.
- "high" = directly answers the query.
- "medium" = partially relevant or provides useful context.
- "low" = weakly related but might help.
- Return at most {top_k} results."""

        response = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id="rerank",
            messages=[{"role": "user", "content": rerank_prompt}],
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        content = response.get("content", "")
        if not content:
            raise ValueError("Empty LLM rerank response")

        # Parse JSON response
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if not json_match:
            raise ValueError(f"No JSON found in rerank response: {content[:200]}")

        ranked_data = json.loads(json_match.group(0))
        ranked_items = ranked_data.get("ranked", [])

        # Reorder candidates by LLM judgment
        reranked: list[dict] = []
        seen_ids: set[str] = set()
        for item in ranked_items:
            idx = item.get("index", -1)
            if 0 <= idx < len(candidates):
                c = candidates[idx].copy()
                c["relevance"] = item.get("relevance", "medium")
                c["reason"] = item.get("reason", "")
                if c["node_id"] not in seen_ids:
                    reranked.append(c)
                    seen_ids.add(c["node_id"])

        # Append any high-fused-score candidates the LLM didn't mention
        for c in candidates:
            if c["node_id"] not in seen_ids and len(reranked) < top_k:
                c_copy = c.copy()
                c_copy["relevance"] = "medium"
                c_copy["reason"] = "Backfilled from fusion ranking"
                reranked.append(c_copy)
                seen_ids.add(c["node_id"])

        logger.debug(
            "LLM rerank: %d candidates → %d after rerank (query=%r)",
            len(candidates), len(reranked), query[:60],
        )
        return reranked[:top_k]

    except Exception as exc:
        logger.warning(
            "LLM rerank failed, falling back to fusion scores: %s",
            exc,
        )
        # Fallback: return top_k by fused score
        return candidates[:top_k]


def _attr_summary(attr: KnowledgeNode) -> str:
    """Build a richer attribute label including semantic_group and business_role."""
    props: dict = {}
    try:
        props = json.loads(attr.properties) if attr.properties else {}
    except Exception:
        pass

    col_name = props.get("column_name", attr.name.split(".")[-1])
    col_type = props.get("data_type", "")
    br = props.get("business_role", "")
    sg = props.get("semantic_group", "")
    ah = props.get("aggregation_hint")
    fk_target = props.get("fk_target_table")

    # Build the annotation part
    annotation_parts = []
    if col_type:
        annotation_parts.append(col_type)
    if br == "foreign_key" and fk_target:
        annotation_parts.append(f"FK → {fk_target}")
    elif br == "primary_key":
        annotation_parts.append("PK")
    elif br == "measure" and ah:
        annotation_parts.append(f"measure, {ah}")
    elif br == "dimension":
        annotation_parts.append("dimension")
    elif br == "timestamp":
        annotation_parts.append("timestamp")
    elif br == "soft_delete":
        annotation_parts.append("soft-delete")
    elif br == "audit":
        annotation_parts.append("audit")
    elif sg and sg not in ("other", "text", "numeric") and not col_type:
        annotation_parts.append(sg)

    if annotation_parts:
        return f"{col_name} ({', '.join(annotation_parts)})"
    return col_name


async def assemble_context(
    store: "KnowledgeGraphStore",
    user_query: str,
    instance_id: str,
    token_budget: int = 4000,
) -> str:
    """
    Build a natural-language context string from the knowledge graph,
    targeted to the user's query.

    Steps
    -----
    1. Semantic search → up to 10 seed nodes most relevant to the query.
       Boost ENTITY nodes with importance_score ≥ 0.7 into the seed set.
    2. 1-hop neighborhood of each seed → collect union.
    3. Prune to token_budget (seeds + high-importance entities always kept).
    4. Serialise to prose.
    5. Append "Key Entities in This Domain" footer.
    """
    if not user_query or not user_query.strip():
        return "No system context available."

    # ── Step 1: Seed nodes via semantic search + importance boost ─────────────
    seed_nodes = await store.semantic_search(user_query, instance_id, top_k=10)

    if not seed_nodes:
        logger.debug(
            f"assemble_context: no seed nodes found for instance={instance_id}, "
            f"query={user_query[:60]!r}"
        )
        return "No relevant knowledge found for this query."

    seed_ids = {n.id for n in seed_nodes}

    # Fetch all ENTITY nodes that have a high importance score and aren't seeds yet
    entity_nodes_db = await store.get_nodes_by_type("ENTITY", instance_id)
    boosted_ids: set[str] = set()
    for en in entity_nodes_db:
        if en.id in seed_ids:
            continue
        try:
            props = json.loads(en.properties) if en.properties else {}
            if props.get("importance_score", 0.0) >= _IMPORTANCE_BOOST_THRESHOLD:
                seed_nodes.append(en)     # treat as seed so it's never pruned
                seed_ids.add(en.id)
                boosted_ids.add(en.id)
        except Exception:
            pass

    # ── Step 2: Expand 1-hop from each seed (in-memory traversal) ────────────
    all_node_dicts: dict[str, dict] = {}
    all_edge_dicts: list[dict] = []
    edge_ids_seen: set[str] = set()

    for seed in seed_nodes:
        all_node_dicts[seed.id] = {
            "id": seed.id,
            "name": seed.name,
            "node_type": seed.node_type,
            "description": seed.description,
            "instance_id": seed.instance_id,
        }
        subgraph = store.get_neighbors(seed.id, seed.instance_id, depth=1)
        for neighbor in subgraph["nodes"]:
            all_node_dicts[neighbor["id"]] = neighbor
        for edge in subgraph["edges"]:
            if edge["id"] not in edge_ids_seen:
                edge_ids_seen.add(edge["id"])
                all_edge_dicts.append(edge)

    # ── Step 3: Prune to token budget ─────────────────────────────────────────
    non_seed_ids = [nid for nid in all_node_dicts if nid not in seed_ids]

    def _max_weight(node_id: str) -> float:
        return max(
            (e["weight"] for e in all_edge_dicts
             if e["source"] == node_id or e["target"] == node_id),
            default=0.0,
        )

    non_seed_ids.sort(key=_max_weight, reverse=True)
    ordered_node_ids = list(seed_ids) + non_seed_ids

    selected_node_ids: list[str] = []
    token_used = 0
    for nid in ordered_node_ids:
        node = all_node_dicts.get(nid)
        if not node:
            continue
        desc_tokens = _estimate_tokens(node.get("description", ""))
        if token_used + desc_tokens > token_budget:
            if nid in seed_ids:
                pass  # always include seeds even if over budget
            else:
                continue
        selected_node_ids.append(nid)
        token_used += desc_tokens

    selected_set = set(selected_node_ids)
    selected_edges = [
        e for e in all_edge_dicts
        if e["source"] in selected_set and e["target"] in selected_set
    ]

    # ── Fetch full node objects from PostgreSQL ───────────────────────────────
    full_nodes: dict[str, KnowledgeNode] = {}
    for nid in selected_node_ids:
        node_obj = first(await store.db.select(KnowledgeNode, ("id", nid)))
        if node_obj:
            full_nodes[nid] = node_obj

    # ── Step 4: Serialise to prose ─────────────────────────────────────────────
    if not full_nodes:
        return "No relevant knowledge found for this query."

    lines: list[str] = ["Relevant System Context:\n"]

    entity_nodes = [n for n in full_nodes.values() if n.node_type == "ENTITY"]
    attribute_nodes = [n for n in full_nodes.values() if n.node_type == "ATTRIBUTE"]
    workflow_nodes = [n for n in full_nodes.values() if n.node_type == "WORKFLOW"]
    rule_nodes = [n for n in full_nodes.values() if n.node_type == "BUSINESS_RULE"]

    # Build entity_name → list[attribute nodes]
    entity_attrs: dict[str, list[KnowledgeNode]] = {}
    for attr in attribute_nodes:
        tbl = attr.name.split(".")[0] if "." in attr.name else attr.name
        entity_attrs.setdefault(tbl, []).append(attr)

    id_to_name: dict[str, str] = {n.id: n.name for n in full_nodes.values()}

    # --- Entity sections ---
    for entity in entity_nodes:
        lines.append(f"{entity.name}: {entity.description}")

        # Attributes — richer annotations now
        attrs = entity_attrs.get(entity.name, [])
        if attrs:
            summaries = [_attr_summary(a) for a in attrs]
            lines.append(f"  Attributes: {', '.join(summaries)}.")

        # Relationships
        rel_lines = []
        for edge in selected_edges:
            if edge["source"] == entity.id:
                tgt_name = id_to_name.get(edge["target"], edge["target"])
                rel = edge["relationship"]
                if rel == "DEPENDS_ON":
                    rel_lines.append(f"References {tgt_name}")
                elif rel == "RELATED_TO":
                    # Distinguish inferred from confirmed
                    try:
                        eprops = json.loads(edge.get("properties", "{}")) if isinstance(edge.get("properties"), str) else {}
                    except Exception:
                        eprops = {}
                    via = eprops.get("via_column")
                    if eprops.get("inferred"):
                        via_str = f" via {via}" if via else ""
                        rel_lines.append(f"Likely references {tgt_name}{via_str} (inferred, not FK-constrained)")
                    else:
                        rel_lines.append(f"Related to {tgt_name}")
                elif rel == "HAS_ATTRIBUTE":
                    pass
                else:
                    rel_lines.append(f"{rel.replace('_', ' ').title()} {tgt_name}")
            elif edge["target"] == entity.id:
                src_name = id_to_name.get(edge["source"], edge["source"])
                rel = edge["relationship"]
                if rel == "DEPENDS_ON":
                    rel_lines.append(f"Referenced by {src_name}")
                elif rel == "RELATED_TO":
                    rel_lines.append(f"Likely referenced by {src_name} (inferred)")

        if rel_lines:
            lines.append(f"  Relationships: {'; '.join(rel_lines)}.")
        lines.append("")

    # --- Workflow sections ---
    for wf in workflow_nodes:
        lines.append(f"Workflow — {wf.name}: {wf.description}")
        step_edges = [
            e for e in selected_edges
            if e["source"] == wf.id and e["relationship"] == "CONTAINS"
        ]
        if step_edges:
            steps = [id_to_name.get(e["target"], e["target"]) for e in step_edges]
            lines.append(f"  Steps: {', '.join(steps)}.")
        lines.append("")

    # --- Business rule sections ---
    for rule in rule_nodes:
        lines.append(f"Rule — {rule.name}: {rule.description}")
        connected = [
            id_to_name.get(e["target"], e["target"])
            for e in selected_edges if e["source"] == rule.id
        ] + [
            id_to_name.get(e["source"], e["source"])
            for e in selected_edges if e["target"] == rule.id
        ]
        if connected:
            lines.append(f"  Applies to: {', '.join(set(connected))}.")
        lines.append("")

    # --- Standalone attribute nodes ---
    entity_names_in_context = {e.name for e in entity_nodes}
    standalone_attrs = [
        a for a in attribute_nodes
        if a.name.split(".")[0] not in entity_names_in_context
    ]
    if standalone_attrs:
        lines.append("Related fields:")
        for attr in standalone_attrs:
            lines.append(f"  {_attr_summary(attr)}: {attr.description}")
        lines.append("")

    # ── Step 5: "Key Entities" footer ─────────────────────────────────────────
    # List top-3 by importance that are in the subgraph but weren't direct semantic hits
    non_seed_entities = [
        n for n in entity_nodes
        if n.id not in boosted_ids and n.id not in (s.id for s in seed_nodes[:10])
    ]
    if non_seed_entities:
        try:
            scored = []
            for n in non_seed_entities:
                props = json.loads(n.properties) if n.properties else {}
                scored.append((n.name, props.get("importance_score", 0.0)))
            scored.sort(key=lambda x: x[1], reverse=True)
            top3 = [name for name, _ in scored[:3] if _ > 0]
            if top3:
                lines.append(f"Key Entities in This Domain: {', '.join(top3)}.")
        except Exception:
            pass

    context = "\n".join(lines).strip()
    logger.debug(
        f"assemble_context: {len(entity_nodes)} entities, "
        f"{len(attribute_nodes)} attributes, "
        f"{len(boosted_ids)} boosted, "
        f"~{_estimate_tokens(context)} tokens, "
        f"instance={instance_id}"
    )
    return context
