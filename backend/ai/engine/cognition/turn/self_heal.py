"""Tool self-heal — one bounded repair hop when a tool misses by a hair.

The failure class this exists for: the model asks for something that is
genuinely available, under a slightly different name, and the turn dead-ends
on "not found" while the live capability sits one step away. Hand-patching
each alias is endless; the miss itself is the signal.

Contract, deliberately narrow:

* **Reads only.** A repair may only ever re-dispatch a read. Mutations keep
  the RULE_21 propose→confirm path untouched — self-heal never re-submits
  anything.
* **One hop.** Exactly one repair per tool call. No loops, no ladders.
* **Only on a miss.** A tool that returned data is never second-guessed.
* **Visible.** A repaired result carries ``self_heal`` provenance so the
  trace shows what was substituted and why — never silent magic.
* **Fail back, not closed.** If the repair also misses, the ORIGINAL result
  is returned so ADR-0021 recovery synthesis explains the real gap.

Strategies live in ``_STRATEGIES`` — adding a repair means adding a function,
not touching the dispatcher.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

#: Tools whose misses are worth a repair hop. All read-only.
_REPAIRABLE_TOOLS: frozenset[str] = frozenset({
    "get_entity_details",
    "search_knowledge",
    "call_host_api",
})

_UNKNOWN_API_PHRASES = (
    "unknown api", "api not found", "no such api", "not in catalog",
    "not in the catalog",
)


@dataclass(frozen=True)
class Repair:
    """A single alternative call to try in place of a missed one."""

    tool_name: str
    tool_args: dict = field(default_factory=dict)
    strategy: str = ""
    #: Outcome-worded note for the trace (RULE_23 — no endpoint paths).
    reason: str = ""


def _as_dict(result) -> dict | None:
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except (TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def is_repairable_miss(tool_name: str, result) -> bool:
    """True when the tool came back empty-handed in a way a retry could fix.

    A legitimately empty answer ("you have no leave records") is NOT a miss —
    only a lookup that never reached real data is.
    """
    if tool_name not in _REPAIRABLE_TOOLS:
        return False
    data = _as_dict(result)
    if data is None:
        return False

    error = str(data.get("error") or "")
    if error:
        # Only a naming error is repairable; a real host failure is not.
        from ai.engine.text.word_match import contains_any_phrase

        return contains_any_phrase(error, _UNKNOWN_API_PHRASES)

    if "entity" in data and not data.get("entity"):
        return True
    if str(data.get("status") or "") == "no_match":
        return True
    try:
        code = int(data["status_code"]) if data.get("status_code") is not None else None
    except (TypeError, ValueError):
        code = None
    return code == 404


def _catalog_alias_repair(
    tool_name: str, args: dict, result, instance_config: dict | None,
) -> Repair | None:
    """A knowledge lookup that names a live READ endpoint → call that endpoint.

    ``get_entity_details("leave_balance")`` means ``get_my_leave_balance``.
    """
    from ai.engine.agent.tools import _resolve_catalog_alias

    if tool_name not in ("get_entity_details", "search_knowledge"):
        return None
    asked = str(
        args.get("entity_name") or args.get("query") or args.get("name") or ""
    ).strip()
    if not asked:
        return None
    resolved = _resolve_catalog_alias(asked, instance_config)
    if not resolved:
        return None
    return Repair(
        tool_name="call_host_api",
        tool_args={
            "api_name": resolved,
            "explanation": f"Self-heal: {asked!r} resolved to live platform data",
        },
        strategy="catalog_alias",
        reason="Read the live platform record instead of the knowledge base",
    )


def _unknown_api_repair(
    tool_name: str, args: dict, result, instance_config: dict | None,
) -> Repair | None:
    """An invented endpoint name → the nearest real READ endpoint."""
    from ai.engine.agent.tools import _nearest_catalog_reads, _resolve_catalog_alias

    if tool_name != "call_host_api":
        return None
    asked = str(args.get("api_name") or args.get("api") or "").strip()
    if not asked:
        return None
    resolved = _resolve_catalog_alias(asked, instance_config)
    if not resolved or resolved == asked:
        nearest = _nearest_catalog_reads(asked, instance_config, limit=1)
        resolved = nearest[0] if nearest else ""
    if not resolved or resolved == asked:
        return None
    return Repair(
        tool_name="call_host_api",
        tool_args={
            **{k: v for k, v in args.items() if k not in ("api_name", "api")},
            "api_name": resolved,
            "explanation": f"Self-heal: {asked!r} matched to an available lookup",
        },
        strategy="unknown_api",
        reason="Used the closest available lookup",
    )


#: Ordered — the first strategy that proposes a repair wins.
_STRATEGIES = (_catalog_alias_repair, _unknown_api_repair)


def _is_read_only(repair: Repair, instance_config: dict | None) -> bool:
    """Hard gate: a repair may never resolve to a mutation."""
    if repair.tool_name != "call_host_api":
        return repair.tool_name in _REPAIRABLE_TOOLS
    api = str(repair.tool_args.get("api_name") or "")
    for ep in (instance_config or {}).get("api_catalog") or []:
        if isinstance(ep, dict) and ep.get("name") == api:
            return (
                str(ep.get("method") or "GET").upper() == "GET"
                and not ep.get("requires_confirmation")
            )
    return False


def propose_repair(
    tool_name: str,
    args: dict | None,
    result,
    *,
    instance_config: dict | None = None,
) -> Repair | None:
    """Return one read-only alternative call for a missed lookup, or None."""
    if not is_repairable_miss(tool_name, result):
        return None
    call_args = args if isinstance(args, dict) else {}
    for strategy in _STRATEGIES:
        try:
            repair = strategy(tool_name, call_args, result, instance_config)
        except Exception:  # noqa: BLE001 - a broken strategy must not break the turn
            logger.exception("self-heal strategy %s failed", strategy.__name__)
            continue
        if repair is None:
            continue
        if not _is_read_only(repair, instance_config):
            logger.warning(
                "self-heal: dropped non-read repair %s → %s",
                tool_name, repair.tool_args.get("api_name"),
            )
            continue
        return repair
    return None


def annotate_repair(result, repair: Repair, original_tool: str) -> dict:
    """Attach visible provenance to a repaired result."""
    data = _as_dict(result)
    if data is None:
        return {"result": result, "self_heal": {
            "from": original_tool,
            "to": repair.tool_name,
            "strategy": repair.strategy,
            "note": repair.reason,
        }}
    data["self_heal"] = {
        "from": original_tool,
        "to": repair.tool_name,
        "strategy": repair.strategy,
        "note": repair.reason,
    }
    return data
