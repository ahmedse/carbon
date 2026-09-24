"""ECF-5 — MAPE-K feedback loop.

Monitor: detects contract violations + user-correction signals.
Analyze: classifies failure tier.
Plan + Execute:
  Tier 1 — auto-heal (reversible, no human gate):
    re-resolve with broader normalization; abstain honestly; no data write.
  Tier 2 — propose (structural, human-gated):
    auto-draft a GoldenCase and write to pending_golden_nominations.json.
    A human reviews, promotes to test_ecf_golden.py, CI locks it forever.

This module never auto-mutates business data (RULE_21).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from ai.engine.cognition.entity.heal_i18n import CORRECTION_AR, any_needle

logger = logging.getLogger("pulse.ecf.heal")

# Correction signals from the user in Arabic or English
_CORRECTION_PHRASES = ("wrong", "incorrect", "not right", "that's wrong")

# Confidence threshold below which a result is considered suspect
_LOW_CONFIDENCE_THRESHOLD = 0.5

# Nominations queue — reviewed by human before merging into the golden test file
_NOMINATIONS_FILE = Path(__file__).parent.parent.parent.parent / "eval" / "pending_golden_nominations.json"


# ── Tier classification ───────────────────────────────────────────────────────

def _is_correction_signal(user_message: str) -> bool:
    from ai.engine.text.word_match import contains_any_phrase

    raw = user_message or ""
    return bool(
        contains_any_phrase(raw, _CORRECTION_PHRASES)
        or any_needle(raw, CORRECTION_AR)
    )


def _is_contract_violation(tool_result: dict) -> bool:
    """Detect a contract violation in a resolved tool result."""
    data = tool_result.get("data") or {}
    # Grounded-refusal violation: claims not-found without searched_total
    if tool_result.get("found") is False and not tool_result.get("searched_total"):
        return True
    # Truncation-as-truth: truncated source with an empty results list (possible false-none)
    if data.get("truncated") and not data.get("results"):
        return True
    return False


def classify_failure(
    user_message: str,
    prior_tool_result: dict | None,
) -> str:
    """Return "tier1", "tier2", or "none"."""
    if prior_tool_result and _is_contract_violation(prior_tool_result):
        return "tier1"  # contract violation → immediate re-resolve
    if _is_correction_signal(user_message):
        return "tier2"  # user explicitly says we're wrong → nominate golden case
    return "none"


# ── Tier 1 — Auto-heal ────────────────────────────────────────────────────────

def tier1_heal(
    entity_type: str,
    query: str,
    instance_config: dict,
    fetch_fn,
) -> dict:
    """Re-resolve with broader normalization; return honest grounded result."""
    from ai.engine.cognition.entity import get_descriptor
    from ai.engine.cognition.entity.resolver import resolve
    from ai.engine.cognition.entity.contracts import grounded_refusal

    descriptor = get_descriptor(instance_config, entity_type)
    if descriptor is None:
        return {"error": "Entity type not registered", "healed": False}

    result = resolve(descriptor, query, fetch_fn=fetch_fn)
    if result.action == "none":
        return {
            "healed": False,
            "message": grounded_refusal(result),
            "searched_total": result.searched_total,
        }
    return {
        "healed": True,
        "action": result.action,
        "record": result.record,
        "candidates": result.candidates,
        "searched_total": result.searched_total,
    }


# ── Tier 2 — Nominate a golden case ──────────────────────────────────────────

def nominate_golden_case(
    user_message: str,
    prior_assistant_response: str,
    entity_type: str,
    query: str,
    *,
    nominated_by: str = "mape_k",
    conversation_id: str = "",
) -> dict:
    """Write a Tier-2 golden-case nomination to the pending queue.

    A human reviews pending_golden_nominations.json, promotes good cases to
    test_ecf_golden.py, and CI locks them permanently.
    """
    nomination = {
        "id": f"nominated_{entity_type}_{re.sub(r'[^a-z0-9]', '_', query.lower())[:40]}",
        "nominated_at": datetime.now(timezone.utc).isoformat(),
        "nominated_by": nominated_by,
        "conversation_id": conversation_id,
        "entity_type": entity_type,
        "query": query,
        "user_correction": user_message,
        "prior_response": prior_assistant_response[:300],
        "suggested_invariants": [
            "response does not repeat the user-flagged incorrect claim",
            f"if entity_type={entity_type}: grounded-none must include searched_total",
        ],
        "status": "pending_human_review",
    }

    try:
        _NOMINATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing: list[dict] = []
        if _NOMINATIONS_FILE.exists():
            try:
                existing = json.loads(_NOMINATIONS_FILE.read_text())
            except json.JSONDecodeError:
                existing = []
        # Avoid duplicate nominations for the same query in the same session
        dup = any(
            n.get("query") == query and n.get("entity_type") == entity_type
            for n in existing
        )
        if not dup:
            existing.append(nomination)
            _NOMINATIONS_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
            logger.info("ECF MAPE-K: nominated golden case '%s' for query '%s'", nomination["id"], query)
    except Exception:  # noqa: BLE001 — nomination failure must never crash a turn
        logger.warning("ECF MAPE-K: failed to write golden nomination", exc_info=True)

    return nomination


# ── Public entry point ────────────────────────────────────────────────────────

def handle_turn_signal(
    user_message: str,
    prior_tool_result: dict | None,
    prior_assistant_response: str,
    *,
    entity_type: str = "employee",
    query: str = "",
    instance_config: dict | None = None,
    fetch_fn=None,
    conversation_id: str = "",
) -> dict:
    """Called after each turn that involves entity resolution.

    Classifies the failure tier and acts:
      tier1 → re-resolve; return healed result
      tier2 → nominate golden case; return nomination receipt
      none  → no-op
    """
    tier = classify_failure(user_message, prior_tool_result)
    if tier == "tier1" and fetch_fn and instance_config and query:
        healed = tier1_heal(entity_type, query, instance_config, fetch_fn)
        healed["tier"] = "tier1"
        return healed
    if tier == "tier2" and query:
        nomination = nominate_golden_case(
            user_message, prior_assistant_response,
            entity_type, query,
            conversation_id=conversation_id,
        )
        return {"tier": "tier2", "nomination": nomination}
    return {"tier": "none"}
