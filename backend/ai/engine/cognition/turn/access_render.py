"""Deterministic access inventory from ``list_my_capabilities``.

Typed envelope tables are the Chat answer. GFM is kept only as a fallback
string for tests and non-envelope callers.
"""
from __future__ import annotations

import json
from typing import Any


def _md_escape(text: str) -> str:
    """Escape GFM table-cell metacharacters (``|`` and newlines)."""
    return str(text or "").replace("|", "\\|").replace("\n", " ")


def _md_link(label: str, route: str) -> str:
    """Internal page link for a table cell; '—' when no route exists."""
    route = str(route or "").strip()
    if not route:
        return "—"
    return f"[{label}]({route})"


def _payload(raw: Any) -> dict:
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("error"):
        return {}
    inner = data.get("result")
    if isinstance(inner, dict) and inner.get("action") == "list_capabilities":
        return inner
    if data.get("action") == "list_capabilities":
        return data
    return {}


def access_tables(data: dict) -> list[dict]:
    """Typed envelope tables. Empty when the payload is not an inventory."""
    if not isinstance(data, dict) or data.get("action") != "list_capabilities":
        return []

    tables: list[dict] = []

    work_rows = [
        [
            str(wa.get("label") or wa.get("key") or ""),
            str(wa.get("description") or ""),
            _md_link("Open", wa.get("route") or ""),
        ]
        for wa in data.get("capabilities") or []
        if isinstance(wa, dict) and wa.get("route")
    ]
    if work_rows:
        tables.append({
            "title": "Work areas",
            "columns": ["Work area", "Description", "Open"],
            "rows": work_rows,
        })

    app_rows = [
        [
            str(a.get("name") or a.get("key") or ""),
            str(a.get("description") or ""),
            _md_link("Open", a.get("route") or ""),
        ]
        for a in data.get("apps") or []
        if isinstance(a, dict) and a.get("route")
    ]
    if app_rows:
        tables.append({
            "title": "Apps you can open",
            "columns": ["App", "Description", "Open"],
            "rows": app_rows,
        })

    module_rows = [
        [
            str(m.get("name") or m.get("key") or ""),
            _md_link("Open", m.get("route") or ""),
        ]
        for m in data.get("modules") or []
        if isinstance(m, dict) and m.get("route")
    ]
    if module_rows:
        tables.append({
            "title": "Data areas",
            "columns": ["Data area", "Open"],
            "rows": module_rows,
        })
    return tables


def access_envelope_from_tools(
    completed_tools: list[dict] | None,
    *,
    headline: str = "",
) -> dict | None:
    """Envelope for a capabilities turn. None when the tool did not run."""
    tables = access_tables_from_tools(completed_tools)
    if not tables:
        return None
    return {
        "headline": headline,
        "prose": [],
        "tables": tables,
        "charts": [],
        "caveats": [],
        "sources": [],
    }


def access_tables_from_tools(completed_tools: list[dict] | None) -> list[dict]:
    for item in completed_tools or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        tables = access_tables(_payload(item.get("result")))
        if tables:
            return tables
    return []


def render_access_inventory(data: dict) -> str:
    """``## Your Access`` from one capabilities payload. Empty when nothing to show."""
    if not isinstance(data, dict) or data.get("action") != "list_capabilities":
        return ""

    sections: list[str] = []

    work_areas = [wa for wa in data.get("capabilities") or [] if isinstance(wa, dict)]
    rows = "\n".join(
        f"| {_md_escape(wa.get('label') or wa.get('key') or '')}"
        f" | {_md_escape(wa.get('description') or '')}"
        f" | {_md_link('Open', wa.get('route') or '')} |"
        for wa in work_areas
        if wa.get("route")
    )
    if rows:
        sections.append(
            "### Work areas\n\n"
            "| Work area | Description | Open |\n"
            "|---|---|---|\n" + rows
        )

    apps = [a for a in data.get("apps") or [] if isinstance(a, dict)]
    rows = "\n".join(
        f"| {_md_escape(a.get('name') or a.get('key') or '')}"
        f" | {_md_escape(a.get('description') or '')}"
        f" | {_md_link('Open', a.get('route') or '')} |"
        for a in apps
        if a.get("route")
    )
    if rows:
        sections.append(
            "### Apps you can open\n\n"
            "| App | Description | Open |\n"
            "|---|---|---|\n" + rows
        )

    modules = [m for m in data.get("modules") or [] if isinstance(m, dict)]
    rows = "\n".join(
        f"| {_md_escape(m.get('name') or m.get('key') or '')}"
        f" | {_md_link('Open', m.get('route') or '')} |"
        for m in modules
        if m.get("route")
    )
    if rows:
        sections.append(
            "### Data areas (modules)\n\n"
            "| Data area | Open |\n"
            "|---|---|\n" + rows
        )

    if not sections:
        return ""
    return "## Your Access\n\n" + "\n\n".join(sections)


def access_inventory_from_tools(completed_tools: list[dict] | None) -> str:
    """First successful capabilities row, rendered. Empty when the tool did not run."""
    for item in completed_tools or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        doc = render_access_inventory(_payload(item.get("result")))
        if doc:
            return doc
    return ""
