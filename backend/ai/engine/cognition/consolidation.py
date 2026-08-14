"""P4.2 — Nightly consolidation sweep (Extract → Reflect → Curate).

Processes unprocessed trajectory rows and produces draft Skill entries
for the admission gate (P4.3).  All learning is sleep-time — never on
the hot path.

Phases
------
1. EXTRACT  (SQL only — no LLM)
   - Reads trajectory rows where consolidation_round = 0
   - Groups by task_intent to find repeating tool sequences, recurring
     failures, high-cost runs, and user corrections.
2. REFLECT  (LLM per candidate, capped)
   - For each extraction candidate, calls route_chat(task="cognition")
     with a structured prompt that asks: "What reusable skill or playbook
     rule would improve future performance?"
3. CURATE  (rules + Skill row creation)
   - Converts reflections into Skill rows with gate_status='pending'.
   - Deduplicates by (name, kind).
   - Bumps trajectory.consolidation_round and sets extracted_at.
"""

import json
import logging

from ai.engine.core.clock import utcnow

from ai.store import first

from ai.engine.core.config import get_settings
from ai.engine.core.models import Skill, Trajectory, generate_uuid

logger = logging.getLogger("pulse.cognition.consolidation")

# ── Minimum thresholds for extraction to fire ─────────────────────────────

_MIN_OCCURRENCES_PATTERN = 3  # repeated tool sequences
_MIN_OCCURRENCES_FAILURE = 2  # recurring failures


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1 — EXTRACT (SQL only, no LLM)
# ═══════════════════════════════════════════════════════════════════════════

async def extract_candidates(
    db,
    instance_id: str,
) -> list[dict]:
    """Read unprocessed trajectory rows and return extraction candidates.

    Each candidate is::

        {
            "trajectory_ids": [...],
            "pattern_type": "repeated_success" | "recurring_failure"
                           | "high_cost" | "user_correction",
            "description": "...",
            "raw_data": {...},
        }
    """
    settings = get_settings()
    candidates: list[dict] = []

    # ── Fetch unprocessed trajectories ─────────────────────────────────────
    rows = await db.select(
        Trajectory,
        ("instance_id", instance_id),
        ("consolidation_round", 0),
    )
    rows.sort(key=lambda r: r.created_at, reverse=True)
    rows = rows[:200]

    if len(rows) < 2:
        logger.debug(
            "extract_candidates: only %d unprocessed trajectory rows for %s — "
            "skipping (need ≥ 2)",
            len(rows), instance_id,
        )
        return candidates

    # ── 1) Repeated successful tool sequences (group by task_intent) ────────
    by_intent: dict[str, list[dict]] = {}
    for row in rows:
        tc = _safe_json(row.tool_calls_json) if row.tool_calls_json else []
        if isinstance(tc, list) and tc:
            tool_seq = tuple(t["tool_name"] for t in tc)
            by_intent.setdefault(row.task_intent or "unknown", []).append({
                "traj_id": row.id,
                "run_id": row.run_id,
                "tool_seq": tool_seq,
                "success": row.status == "completed",
            })

    for intent, entries in by_intent.items():
        seq_counts: dict[tuple, list[dict]] = {}
        for e in entries:
            if e["success"]:
                seq_counts.setdefault(e["tool_seq"], []).append(e)
        for seq, items in seq_counts.items():
            if len(items) >= _MIN_OCCURRENCES_PATTERN:
                candidates.append({
                    "trajectory_ids": [i["traj_id"] for i in items],
                    "pattern_type": "repeated_success",
                    "description": (
                        f"Users with intent '{intent}' repeatedly succeed "
                        f"with tool sequence: {' → '.join(seq)} "
                        f"({len(items)} occurrences)"
                    ),
                    "raw_data": {
                        "intent": intent,
                        "tool_sequence": list(seq),
                        "occurrences": len(items),
                        "sample_run_ids": [i["run_id"] for i in items[:3]],
                    },
                })

    # ── 2) Recurring failures ──────────────────────────────────────────────
    failed = [r for r in rows if r.status == "failed" and r.tool_calls_json]
    fail_buckets: dict[str, list] = {}
    for r in failed:
        tc = _safe_json(r.tool_calls_json)
        if isinstance(tc, list):
            for t in tc:
                if not t.get("success"):
                    key = t.get("tool_name", "unknown")
                    fail_buckets.setdefault(key, []).append(r.id)

    for tool_name, traj_ids in fail_buckets.items():
        if len(traj_ids) >= _MIN_OCCURRENCES_FAILURE:
            candidates.append({
                "trajectory_ids": traj_ids,
                "pattern_type": "recurring_failure",
                "description": (
                    f"Tool '{tool_name}' failed {len(traj_ids)} times"
                ),
                "raw_data": {
                    "tool_name": tool_name,
                    "failure_count": len(traj_ids),
                },
            })

    # ── 3) High-cost runs (top 10 % by total_tokens) ───────────────────────
    if len(rows) >= 5:
        sorted_by_tokens = sorted(rows, key=lambda r: r.total_tokens, reverse=True)
        top_n = max(1, len(sorted_by_tokens) // 10)
        high_cost = sorted_by_tokens[:top_n]
        if high_cost:
            avg_tokens = sum(r.total_tokens for r in rows) / len(rows)
            high_avg = sum(r.total_tokens for r in high_cost) / len(high_cost)
            if high_avg > avg_tokens * 1.5:
                candidates.append({
                    "trajectory_ids": [r.id for r in high_cost],
                    "pattern_type": "high_cost",
                    "description": (
                        f"Top {top_n} runs consumed {high_avg:.0f} avg tokens "
                        f"vs {avg_tokens:.0f} global avg"
                    ),
                    "raw_data": {
                        "high_avg_tokens": high_avg,
                        "global_avg_tokens": avg_tokens,
                        "count": top_n,
                    },
                })

    # ── 4) User corrections (thumbs_down / clarified feedback) ─────────────
    corrections = [
        r for r in rows
        if r.user_feedback in ("thumbs_down", "clarified")
    ]
    if len(corrections) >= 1:
        candidates.append({
            "trajectory_ids": [r.id for r in corrections],
            "pattern_type": "user_correction",
            "description": (
                f"{len(corrections)} runs received thumbs_down/clarified feedback"
            ),
            "raw_data": {
                "correction_count": len(corrections),
                "sample_messages": [
                    r.user_message[:200] for r in corrections[:3]
                ],
            },
        })

    logger.info(
        "extract_candidates: instance=%s rows=%d candidates=%d",
        instance_id, len(rows), len(candidates),
    )
    return candidates


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2 — REFLECT (LLM per candidate, capped)
# ═══════════════════════════════════════════════════════════════════════════

_REFLECT_PROMPT = """You are a self-improving AI copilot for a software platform.

Given this INTERACTION PATTERN, identify a reusable skill or playbook rule
that would improve future performance.  A skill is an automated procedure
(specific tool sequence, api_call, prompt_template, heuristic, etc.) that
turns this pattern into a reliable capability.

PATTERN TYPE: {pattern_type}
DESCRIPTION: {description}
RAW DATA: {raw_data}

Return ONLY a JSON object with these fields:
{{
    "skill_name": "short_snake_case_name",
    "skill_kind": "one of: procedure, api_call, prompt_template, heuristic, resolution, sql_macro, multi_step_plan, tool_preset, code_snippet",
    "skill_body": {{ ... actual skill payload as a JSON object ... }},
    "skill_description": "one sentence describing when to use this skill",
    "playbook_delta": "optional string: a prompt-template fragment to add to the playbook",
    "confidence": 0.0-1.0,
    "rationale": "one sentence explaining why this improvement helps"
}}

If this pattern doesn't warrant a skill, return: {{"skip": true, "rationale": "..."}}"""


async def reflect_on_candidates(
    db,
    instance_id: str,
    candidates: list[dict],
) -> list[dict]:
    """Run the reflection LLM pass on each candidate. Returns reflection dicts.

    Capped at CONSOLIDATION_SWEEP_MAX_LLM_CALLS.  Remaining candidates are
    left for the next sweep.
    """
    settings = get_settings()
    from ai.engine.llm.router import route_chat

    max_calls = max(1, settings.CONSOLIDATION_SWEEP_MAX_LLM_CALLS)
    reflections: list[dict] = []

    for idx, candidate in enumerate(candidates):
        if idx >= max_calls:
            logger.info(
                "reflect_on_candidates: cap reached (%d/%d), %d remaining for next sweep",
                max_calls, len(candidates), len(candidates) - idx,
            )
            break

        prompt = _REFLECT_PROMPT.format(
            pattern_type=candidate["pattern_type"],
            description=candidate["description"],
            raw_data=json.dumps(candidate["raw_data"], default=str),
        )

        try:
            router_result = await route_chat(
                task="cognition",
                instance_id=instance_id,
                conversation_id=f"consolidation-reflect-{instance_id}",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                response_format={"type": "json_object"},
            )

            content = (router_result.get("content") or "").strip()
            parsed = _safe_json(content)

            if isinstance(parsed, dict) and parsed.get("skip"):
                logger.debug("reflect_on_candidates: LLM skipped candidate %d", idx)
                continue

            if isinstance(parsed, dict) and parsed.get("skill_name"):
                parsed["trajectory_ids"] = candidate["trajectory_ids"]
                parsed["pattern_type"] = candidate["pattern_type"]
                parsed["_llm_tokens"] = router_result.get("output_tokens", 0)
                reflections.append(parsed)
                logger.debug(
                    "reflect_on_candidates: candidate %d → skill=%s confidence=%.2f",
                    idx, parsed["skill_name"], parsed.get("confidence", 0),
                )
            else:
                logger.warning(
                    "reflect_on_candidates: unexpected LLM response for candidate %d: %s",
                    idx, content[:200],
                )

        except Exception as exc:
            logger.warning(
                "reflect_on_candidates: LLM call failed for candidate %d: %s",
                idx, exc,
            )

    logger.info("reflect_on_candidates: produced %d reflections from %d candidates",
                 len(reflections), min(len(candidates), max_calls))
    return reflections


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3 — CURATE (rules + Skill row creation)
# ═══════════════════════════════════════════════════════════════════════════

async def curate_deltas(
    db,
    instance_id: str,
    reflections: list[dict],
) -> int:
    """Create draft Skill rows from reflections. Returns count of new skills.

    Deduplicates by (name, kind).  Bumps trajectory.consolidation_round.
    """
    settings = get_settings()
    min_confidence = settings.CONSOLIDATION_SWEEP_MIN_CONFIDENCE
    created = 0

    # ── Pre-fetch existing skill names for dedup ──────────────────────────
    existing_rows = await db.select(Skill, ("instance_id", instance_id))
    existing_pairs = {(row.name, row.kind) for row in existing_rows}

    for ref in reflections:
        confidence = float(ref.get("confidence", 0))

        if confidence < min_confidence:
            logger.debug(
                "curate_deltas: skipping '%s' — confidence %.2f < %.2f",
                ref.get("skill_name"), confidence, min_confidence,
            )
            continue

        skill_name = str(ref.get("skill_name", "")).strip()
        skill_kind = str(ref.get("skill_kind", "procedure")).strip()

        if not skill_name:
            continue

        # Dedup
        if (skill_name, skill_kind) in existing_pairs:
            logger.debug("curate_deltas: skill '%s' (%s) already exists — skipping",
                          skill_name, skill_kind)
            continue

        # Build Skill row
        skill = Skill(
            id=generate_uuid(),
            instance_id=instance_id,
            name=skill_name,
            description=str(ref.get("skill_description", "")),
            signature=json.dumps(ref.get("skill_signature", {})),
            body=json.dumps(ref.get("skill_body", {})),
            kind=skill_kind,
            status="draft",
            author_user_id="system",  # learned skills are system-authored
            gate_status="pending",
            provenance_run_ids=json.dumps(ref.get("trajectory_ids", [])),
        )
        db.add(skill)
        existing_pairs.add((skill_name, skill_kind))
        created += 1
        logger.info("curate_deltas: created skill '%s' (%s)", skill_name, skill_kind)

    # ── Bump trajectory.consolidation_round for all referenced rows ────────
    all_traj_ids: set[str] = set()
    for ref in reflections:
        for tid in ref.get("trajectory_ids", []):
            all_traj_ids.add(tid)

    if all_traj_ids:
        now = utcnow()
        for tid in all_traj_ids:
            traj = first(await db.select(Trajectory, ("id", tid)))
            if traj is not None:
                traj.consolidation_round = (traj.consolidation_round or 0) + 1
                traj.extracted_at = now

    try:
        await db.flush()
    except Exception as exc:
        logger.warning("curate_deltas: flush failed: %s", exc)

    logger.info("curate_deltas: created %d skills, bumped %d trajectories",
                 created, len(all_traj_ids))
    return created


# ═══════════════════════════════════════════════════════════════════════════
# FACT EXPIRY — Bi-temporal KG edge expiry during consolidation
# ═══════════════════════════════════════════════════════════════════════════

async def _expire_superseded_facts(
    db,
    instance_id: str,
    candidates: list[dict],
) -> int:
    """Expire KG edges that have been superseded by new consolidation candidates.

    For each candidate that represents a tool sequence or pattern, check if an
    existing KG edge (same subject+predicate, still valid) stores different
    information. If so, call update_edge() to expire the old edge and create
    a new one with the updated data.
    """
    from ai.engine.knowledge_graph.store import KnowledgeGraphStore
    from ai.engine.knowledge_graph.models import KnowledgeNode, KnowledgeEdge

    store = KnowledgeGraphStore(db)
    expired = 0

    for candidate in candidates:
        raw = candidate.get("raw_data", {})
        tool_seq = raw.get("tool_sequence", [])
        tool_name = raw.get("tool_name", "")
        intent = raw.get("intent", "")
        pattern_type = candidate.get("pattern_type", "")

        # Skip candidates without enough data to match
        if not tool_seq and not tool_name:
            continue

        # Build a search predicate from the candidate data
        if tool_seq:
            predicate_id = f"tool_sequence_{'_'.join(tool_seq)}"
        elif tool_name:
            predicate_id = f"tool_{tool_name}_{pattern_type}"
        else:
            continue

        # Look for existing non-expired edges with this pattern
        existing = await db.select(
            KnowledgeEdge,
            ("instance_id", instance_id),
            ("source_node_id", f"pattern_{instance_id}"),
            ("relationship", "HAS_ATTRIBUTE"),
            ("valid_to__isnull", True),
        )
        old_edge = None
        for edge in existing:
            props_json = json.dumps(edge.properties) if edge.properties else ""
            if predicate_id in props_json:
                old_edge = edge
                break

        if old_edge is not None:
            # Check if the description changed
            old_props = json.loads(old_edge.properties) if old_edge.properties else {}
            new_desc = candidate.get("description", "")
            if old_props.get("description") != new_desc:
                await store.update_edge(old_edge.id, {
                    "instance_id": instance_id,
                    "source_node_id": old_edge.source_node_id,
                    "target_node_id": old_edge.target_node_id,
                    "relationship": old_edge.relationship,
                    "properties": json.dumps({
                        **old_props,
                        "description": new_desc,
                        "updated_by": "consolidation_sweep",
                    }),
                    "confidence": candidate.get("raw_data", {}).get("occurrences", 1) / 10.0,
                })
                expired += 1
                logger.debug(
                    "Expired edge %s (pattern=%s, type=%s)",
                    old_edge.id, predicate_id, pattern_type,
                )

    return expired


# ═══════════════════════════════════════════════════════════════════════════
# TOP-LEVEL ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════

async def run_consolidation_sweep(db, instance_id: str) -> dict:
    """Run the full extract → reflect → curate pipeline for one instance.

    Returns a summary dict suitable for logging / API responses::

        {"candidates_extracted": N, "reflections": N, "skills_created": N}
    """
    settings = get_settings()
    if not settings.CONSOLIDATION_SWEEP_ENABLED:
        logger.debug("Consolidation sweep disabled — skipping")
        return {"candidates_extracted": 0, "reflections": 0, "skills_created": 0}

    logger.info("Consolidation sweep starting for instance=%s", instance_id)

    # 1. Extract
    candidates = await extract_candidates(db, instance_id)
    if not candidates:
        logger.info("Consolidation sweep: no candidates for instance=%s", instance_id)
        return {"candidates_extracted": 0, "reflections": 0, "skills_created": 0}

    # 1.5 — Fact expiry: expire KG edges that have been superseded by new
    # candidate patterns. If a tool sequence was previously stored as a
    # CONTAINS/HAS_ATTRIBUTE edge and the new candidate's description or
    # data differs, we expire the old edge and create a fresh one.
    expired_count = await _expire_superseded_facts(db, instance_id, candidates)
    if expired_count:
        logger.info("Expired %d superseded KG facts for instance=%s", expired_count, instance_id)

    # 2. Reflect
    reflections = await reflect_on_candidates(db, instance_id, candidates)
    if not reflections:
        logger.info("Consolidation sweep: no reflections for instance=%s", instance_id)
        return {
            "candidates_extracted": len(candidates),
            "reflections": 0,
            "skills_created": 0,
        }

    # 3. Curate
    skills_created = await curate_deltas(db, instance_id, reflections)

    summary = {
        "candidates_extracted": len(candidates),
        "reflections": len(reflections),
        "skills_created": skills_created,
    }
    logger.info("Consolidation sweep complete: %s", summary)
    return summary


# ── Scheduler helper (called from loop.py via _for_each_instance) ───────────

async def _run_consolidation_for_all_instances():
    """Nightly: run consolidation sweep for every active instance.

    Designed to be used as the callback for _for_each_instance or
    directly from the scheduler.
    """
    from ai.store import get_store
    from ai.engine.core.models import Instance

    factory = get_store().get_session_factory()
    async with factory() as db:
        instances = await db.select(Instance, ("status", "active"))

        for inst in instances:
            try:
                summary = await run_consolidation_sweep(db, inst.id)
                logger.info(
                    "Consolidation sweep: instance=%s result=%s",
                    inst.name, summary,
                )
            except Exception:
                logger.exception(
                    "Consolidation sweep failed for %s", inst.name,
                )


# ── Helpers ─────────────────────────────────────────────────────────────────

def _safe_json(raw: str | None) -> dict | list | None:
    """Parse JSON safely, returning None on any failure."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
