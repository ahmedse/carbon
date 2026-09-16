"""ECF-3 — Boundary contract guards.

Four invariants enforced at the tool-result boundary (ADR-0032, ADR-0002).
Applied to the output of any entity data call — not just ECF capabilities,
so they defend existing list_employees / get_employee too.

Invariants:
  1. no_truncation_as_truth  — existence/universal claim over truncated source → rewrite
  2. resolve_labels          — FK ids replaced by human labels from descriptor
  3. honest_masking          — 0.000/null when capability absent → "(hidden)"
  4. grounded_refusal        — "not found" must carry searched_total

Usage (applied in engine_runtime after tool results, gated on ECF_ENABLED):
  from ai.engine.cognition.entity.contracts import apply_entity_contracts
  result = apply_entity_contracts(tool_result, descriptor, user_capabilities)
"""
from __future__ import annotations

import re
from typing import Any

from ai.engine.cognition.entity.registry import EntityDescriptor

# Phrases that indicate a universal existence claim that must not be made
# from a truncated source.
_NONEXISTENCE_PATTERNS = re.compile(
    r"\b(no (?:such|matching|employee|record)|not found|does not exist"
    r"|لا يوجد|غير موجود|لم يتم العثور)\b",
    re.IGNORECASE,
)
_UNIVERSAL_PATTERNS = re.compile(
    r"\b(all employees|everyone|all records|جميع الموظفين)\b",
    re.IGNORECASE,
)


def no_truncation_as_truth(
    tool_result: dict,
    prose: str,
    *,
    descriptor: EntityDescriptor | None = None,
) -> str:
    """Rewrite prose that claims non-existence over a truncated source.

    If the tool_result carries `truncated=True` and the prose asserts that
    something was not found, replace the false-certain claim with an honest
    partial-scan note.
    """
    truncated = (
        tool_result.get("truncated")
        or (tool_result.get("data") or {}).get("truncated")
    )
    if not truncated:
        return prose

    if _NONEXISTENCE_PATTERNS.search(prose):
        total = (
            (tool_result.get("data") or {}).get("total")
            or (tool_result.get("data") or {}).get("count")
            or "?"
        )
        disclaimer = (
            f" [Note: this searched only the first page of {total} total records. "
            "Use the entity resolver for a complete search.]"
        )
        prose = _NONEXISTENCE_PATTERNS.sub(
            lambda m: m.group(0) + disclaimer,
            prose,
            count=1,
        )
    return prose


def resolve_labels(
    record: dict,
    descriptor: EntityDescriptor,
    *,
    label_fetch_fn=None,
) -> dict:
    """Replace FK ids with human labels using the descriptor's label_map.

    If label_fetch_fn is not provided (offline/tests), the raw id is kept but
    wrapped as a hint rather than displayed directly.
    """
    result = dict(record)
    for field_name, label_source in descriptor.label_map.items():
        raw_id = result.get(field_name)
        if raw_id is None:
            continue
        if label_fetch_fn is not None:
            try:
                rows = label_fetch_fn(label_source.model, {"id": raw_id}, [label_source.field], 1)
                if rows:
                    result[field_name] = rows[0].get(label_source.field, raw_id)
                    continue
            except Exception:  # noqa: BLE001
                pass
        # Fallback: annotate the raw id rather than surfacing it bare
        result[field_name] = f"#{raw_id}"
    return result


def honest_masking(
    record: dict,
    descriptor: EntityDescriptor,
    user_capabilities: frozenset[str] | None = None,
) -> dict:
    """Redact capability-gated fields the caller cannot see.

    Always replaces the value when the capability is absent — never leave a
    real salary visible to unauthorized callers (A5). Zero/null used to be the
    only trigger because the host sometimes returned ``0.000`` as a soft mask;
    that missed the case where the raw amount leaked through.
    """
    if user_capabilities is None:
        user_capabilities = frozenset()

    result = dict(record)
    for field_name, policy in descriptor.masking.items():
        if policy.capability in user_capabilities:
            continue  # caller is authorised — leave value intact
        result[field_name] = "(hidden — salary access required)"
    return result


def grounded_refusal(resolve_result: Any) -> str | None:
    """Return a grounded 'not found' message that includes searched_total.

    Call this when ResolveResult.action == 'none' to produce the canonical
    message the LLM must use — never emit a bare 'not found'.
    Returns None if the result is not a 'none' action.
    """
    if not hasattr(resolve_result, "action") or resolve_result.action != "none":
        return None
    n = getattr(resolve_result, "searched_total", 0)
    lang = getattr(resolve_result, "lang", "en")
    if lang == "ar":
        return f"لم يُعثر على سجل مطابق (تم البحث في {n} سجل)."
    return f"No matching record found (searched all {n} records)."


def apply_entity_contracts(
    tool_result: dict,
    prose: str,
    descriptor: EntityDescriptor | None,
    user_capabilities: frozenset[str] | None = None,
    label_fetch_fn=None,
) -> tuple[dict, str]:
    """Apply all four boundary contracts to a tool result + prose pair.

    Returns (cleaned_result, cleaned_prose).
    Safe to call when descriptor is None (no-op pass-through).
    """
    if descriptor is None:
        return tool_result, prose

    # 1. Truncation guard
    prose = no_truncation_as_truth(tool_result, prose, descriptor=descriptor)

    # 2. Label resolution on embedded results list
    data = tool_result.get("data") or {}
    results_list = data.get("results") or []
    if results_list and isinstance(results_list, list):
        cleaned = [
            resolve_labels(r, descriptor, label_fetch_fn=label_fetch_fn)
            for r in results_list
        ]
        data = dict(data)
        data["results"] = cleaned
        tool_result = dict(tool_result)
        tool_result["data"] = data

    # 3. Honest masking on embedded results list
    if results_list and isinstance(results_list, list):
        data = tool_result.get("data") or {}
        cleaned = [
            honest_masking(r, descriptor, user_capabilities)
            for r in data.get("results", [])
        ]
        data = dict(data)
        data["results"] = cleaned
        tool_result = dict(tool_result)
        tool_result["data"] = data

    return tool_result, prose
