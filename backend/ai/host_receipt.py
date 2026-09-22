"""Host write → operator action receipt (Chat + Agent Output, one contract).

Successful mutating host calls attach Chat-compatible navigate fields on the
tool result. Chat already turns those into message actions via
``engine_runtime._derive_actions_from_tools``. Agent Output serializes the same
shape as ``output_actions`` on the plan DTO and renders the same buttons.

Contract — top-level keys on the host tool-result dict (alongside
``status_code`` / ``data``)::

    action:  "navigate"
    route:   "/my/requests/{id}"   # safe SPA path
    label:   "Open leave request"
    summary: "Leave request annual 2026-09-22→… · CRS-…"

Do not invent leave-only helpers. Correspondence (ADR-0030) and any other host
write that can deep-link should emit this same receipt.
"""
from __future__ import annotations

import json
from typing import Any


def navigate_receipt(*, route: str, label: str, summary: str = "") -> dict[str, str]:
    return {
        "action": "navigate",
        "route": str(route or "").strip(),
        "label": str(label or "Open").strip() or "Open",
        "summary": str(summary or "").strip(),
    }


def _payload_summary(payload: Any, *, limit: int = 4) -> str:
    if not isinstance(payload, dict):
        return ""
    parts: list[str] = []
    for key, value in payload.items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, (dict, list)):
            continue
        label = str(key).replace("_", " ").strip()
        parts.append(f"{label} {value}")
        if len(parts) >= limit:
            break
    return " · ".join(parts)


def correspondence_navigate_receipt(
    data: Any,
    *,
    fallback_route: str = "/my/requests",
) -> dict[str, str] | None:
    """Build a navigate receipt from CorrespondenceDetailSerializer data."""
    if not isinstance(data, dict):
        return None
    corr_id = data.get("id")
    route = f"/my/requests/{corr_id}" if corr_id else fallback_route
    ctype = (
        data.get("corr_type_label")
        or data.get("corr_type_code")
        or "request"
    )
    label = f"Open {ctype}" if ctype else "Open request"
    summary = str(data.get("title") or "").strip()
    if not summary:
        summary = _payload_summary(data.get("payload"))
    ref = str(data.get("reference_no") or "").strip()
    if ref and ref not in summary:
        summary = f"{summary} · {ref}".strip(" ·")
    status = str(data.get("status") or "").strip()
    if status and status not in summary:
        summary = f"{summary} · {status}".strip(" ·")
    # ESS leave/loan: corr is submitted → manager acts in Team (not Pulse).
    ctype_code = str(data.get("corr_type_code") or "").strip().lower()
    if status in ("submitted", "in_review") and ctype_code in (
        "leave_request",
        "loan_request",
        "attendance_permission",
    ):
        if "manager" not in summary.lower():
            summary = f"{summary} · awaiting your manager in Team".strip(" ·")
    if not summary:
        summary = label
    return navigate_receipt(route=route, label=label, summary=summary)


def attach_receipt(api_result: Any, receipt: dict[str, str] | None) -> Any:
    """Merge a navigate receipt onto a host ``{status_code, data}`` result."""
    if not isinstance(api_result, dict) or not receipt:
        return api_result
    route = str(receipt.get("route") or "").strip()
    if not route.startswith("/") or route.startswith("//"):
        return api_result
    out = dict(api_result)
    out["action"] = "navigate"
    out["route"] = route
    out["label"] = str(receipt.get("label") or "Open").strip() or "Open"
    out["summary"] = str(receipt.get("summary") or "").strip()
    return out


def _iter_result_dicts(tool_output: Any) -> list[dict[str, Any]]:
    """Yield dict layers that may carry ``action`` / ``route``."""
    if not isinstance(tool_output, dict):
        return []
    layers = [tool_output]
    data = tool_output.get("data")
    if isinstance(data, dict):
        layers.append(data)
    raw = tool_output.get("result")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            raw = None
    if isinstance(raw, dict):
        layers.append(raw)
        nested = raw.get("data")
        if isinstance(nested, dict):
            layers.append(nested)
    return layers


def collect_navigate_actions(tool_outputs: list[Any]) -> list[dict[str, str]]:
    """Chat-compatible actions: ``[{type, route, label, summary}, ...]``."""
    actions: list[dict[str, str]] = []
    seen: set[str] = set()
    for output in tool_outputs or []:
        for layer in _iter_result_dicts(output):
            if layer.get("action") != "navigate":
                continue
            route = str(layer.get("route") or "").strip()
            if not route.startswith("/") or route.startswith("//"):
                continue
            if route in seen:
                continue
            seen.add(route)
            actions.append({
                "type": "navigate",
                "route": route,
                "label": str(layer.get("label") or "Open").strip() or "Open",
                "summary": str(layer.get("summary") or "").strip(),
            })
    return actions


def format_actions_markdown(actions: list[dict[str, str]]) -> str:
    """Operator Answer fragment from navigate receipts (RULE_23)."""
    if not actions:
        return ""
    blocks: list[str] = []
    for action in actions:
        summary = action.get("summary") or action.get("label") or "Done"
        label = action.get("label") or "Open"
        route = action.get("route") or ""
        blocks.append(f"{summary}\n\n[{label}]({route})")
    return "\n\n".join(blocks).strip()[:2000]
