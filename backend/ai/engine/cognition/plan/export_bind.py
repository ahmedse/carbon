"""Deterministic bind of prior step structured outputs → ``export_document`` args.

RULE_20 pure (no Django). Called by the plan loop immediately before
``export_document`` executes so Word/Excel deliverables receive real tables
and charts even when the draft LLM emitted placeholders or title-only args.
"""
from __future__ import annotations

import json
import re
from typing import Any

# Cap rows so export args stay bounded for docx/xlsx writers.
_MAX_TABLE_ROWS = 50
_MAX_IMAGES = 4
_MAX_PROSE_CHARS = 3500

_PLACEHOLDER_RE = re.compile(
    r"\[?\s*placeholder[^\]]*\]?"
    r"|chart and table to be inserted"
    r"|to be inserted"
    r"|TODO:?\s*fill"
    r"|lorem ipsum",
    re.IGNORECASE,
)


def content_is_placeholder(md: str | None) -> bool:
    """True when markdown is empty or a hollow skeleton (placeholder tokens)."""
    text = (md or "").strip()
    if not text:
        return True
    if _PLACEHOLDER_RE.search(text):
        return True
    # Mostly bracketed stubs like "[Placeholder for insights]"
    brackets = re.findall(r"\[[^\]]{3,80}\]", text)
    if brackets and len("".join(brackets)) >= max(24, int(len(text) * 0.35)):
        return True
    return False


def _parse_maybe_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s or s[0] not in "{[":
            return value
        try:
            return json.loads(s)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


def _unwrap_payload(tool_output: dict | None) -> dict:
    """Normalize execute-wrapper / sandbox / host-API shapes to a flat dict."""
    if not isinstance(tool_output, dict):
        return {}
    data = dict(tool_output)
    result = _parse_maybe_json(data.get("result"))
    if isinstance(result, dict):
        # Prefer nested sandbox keys when present.
        merged = {**result, **{k: v for k, v in data.items() if k != "result"}}
        return merged
    if isinstance(result, list):
        return {**data, "rows": result}
    return data


def _rows_from_records(records: list) -> dict | None:
    """Convert list[dict] or list[list] into {headers, rows}."""
    if not records:
        return None
    first = records[0]
    if isinstance(first, dict):
        headers = list(first.keys())
        rows = [
            [str(r.get(h, "")) for h in headers]
            for r in records[:_MAX_TABLE_ROWS]
            if isinstance(r, dict)
        ]
        return {"headers": [str(h) for h in headers], "rows": rows} if headers else None
    if isinstance(first, (list, tuple)):
        # Treat first row as headers when all cells look like strings and rest differ.
        headers = [str(c) for c in first]
        body = records[1:_MAX_TABLE_ROWS + 1]
        rows = [
            [str(c) for c in (row if isinstance(row, (list, tuple)) else [row])]
            for row in body
        ]
        return {"headers": headers, "rows": rows}
    return None


def _table_from_breakdown(breakdown: list | dict) -> dict | None:
    """Host API analyze_* often returns breakdown: [{label, count, …}]."""
    if isinstance(breakdown, dict):
        # {category: stats} map
        rows = []
        for key, val in list(breakdown.items())[:_MAX_TABLE_ROWS]:
            if isinstance(val, dict):
                rows.append({"category": key, **val})
            else:
                rows.append({"category": key, "value": val})
        return _rows_from_records(rows)
    if isinstance(breakdown, list):
        return _rows_from_records(breakdown)
    return None


def extract_structured_facts(tool_output: dict | None) -> dict:
    """Pull tables, images, and short prose hints from one step tool_output.

    Returns ``{"tables": [...], "images": [...], "stats_prose": str}``.
    """
    tables: list[dict] = []
    images: list[dict] = []
    prose_bits: list[str] = []

    data = _unwrap_payload(tool_output)
    if not data:
        return {"tables": tables, "images": images, "stats_prose": ""}

    # code_execute sandbox
    if data.get("table_rows"):
        t = _rows_from_records(data["table_rows"] if isinstance(data["table_rows"], list) else [])
        if t:
            tables.append(t)
    if isinstance(data.get("image_b64"), str) and data["image_b64"].strip():
        images.append({
            "caption": "Chart",
            "image_b64": data["image_b64"].strip(),
        })

    # Explicit table shape
    if isinstance(data.get("headers"), list) and isinstance(data.get("rows"), list):
        tables.append({
            "headers": [str(h) for h in data["headers"]],
            "rows": [
                [str(c) for c in (row if isinstance(row, (list, tuple)) else [row])]
                for row in data["rows"][:_MAX_TABLE_ROWS]
            ],
        })

    # Host API analyze / distribution payloads
    for key in ("breakdown", "distribution", "by_category", "buckets", "groups"):
        if key in data and data[key] is not None:
            t = _table_from_breakdown(data[key])
            if t:
                tables.append(t)

    # Nested data / result envelopes
    for nest_key in ("data", "payload", "response"):
        nested = _parse_maybe_json(data.get(nest_key))
        if isinstance(nested, dict):
            inner = extract_structured_facts(nested)
            tables.extend(inner["tables"])
            images.extend(inner["images"])
            if inner["stats_prose"]:
                prose_bits.append(inner["stats_prose"])
        elif isinstance(nested, list) and nested and isinstance(nested[0], dict):
            t = _rows_from_records(nested)
            if t:
                tables.append(t)

    # Caveats / summary strings
    for key in ("summary", "message", "note", "caveat", "stdout"):
        val = data.get(key)
        if isinstance(val, str) and val.strip() and len(val) < 800:
            if key == "stdout" and len(val) > 400:
                continue
            prose_bits.append(val.strip())

    # Cap images
    images = images[:_MAX_IMAGES]
    return {
        "tables": tables,
        "images": images,
        "stats_prose": "\n".join(prose_bits)[:1200],
    }


def _richest_table(tables: list[dict]) -> dict | None:
    if not tables:
        return None
    return max(tables, key=lambda t: len(t.get("rows") or []) * 10 + len(t.get("headers") or []))


def _synthesize_content(
    title: str,
    prior_drafts: list[str],
    tables: list[dict],
    stats_prose: str,
) -> str:
    """Build short markdown findings from prior step prose + table headlines."""
    parts: list[str] = []
    parts.append(f"## Summary")
    if prior_drafts:
        for draft in prior_drafts[:4]:
            cleaned = re.sub(r"\s+", " ", (draft or "").strip())
            if not cleaned or content_is_placeholder(cleaned):
                continue
            parts.append(cleaned[:600])
    elif stats_prose:
        parts.append(stats_prose[:800])
    else:
        parts.append(
            f"This report consolidates measured findings for **{title or 'the analysis'}**."
        )

    for i, table in enumerate(tables[:3]):
        headers = table.get("headers") or []
        rows = table.get("rows") or []
        label = headers[0] if headers else f"Dimension {i + 1}"
        parts.append(f"## {label}")
        parts.append(f"- Categories in view: **{len(rows)}**")
        if headers and rows:
            # Top few lines as bullets
            for row in rows[:8]:
                cells = [str(c) for c in row]
                if len(cells) >= 2:
                    parts.append(f"- **{cells[0]}**: {', '.join(cells[1:4])}")
                elif cells:
                    parts.append(f"- {cells[0]}")
    body = "\n\n".join(parts)
    return body[:_MAX_PROSE_CHARS]


def bind_export_args(
    llm_args: dict | None,
    prior_results: list[Any],
    *,
    title_fallback: str = "Agent report",
) -> dict:
    """Merge prior structured facts into ``export_document`` tool args.

    ``prior_results`` are ``StepResult``-like objects with optional
    ``tool_output`` and ``draft_text`` attributes (or plain dicts).
    """
    args = dict(llm_args or {})
    if not args.get("title"):
        args["title"] = title_fallback

    all_tables: list[dict] = []
    all_images: list[dict] = []
    prose_chunks: list[str] = []
    drafts: list[str] = []

    for r in prior_results or []:
        if isinstance(r, dict):
            tool_output = r.get("tool_output")
            draft_text = r.get("draft_text") or ""
        else:
            tool_output = getattr(r, "tool_output", None)
            draft_text = getattr(r, "draft_text", "") or ""
        if draft_text:
            drafts.append(draft_text[:800])
        facts = extract_structured_facts(tool_output if isinstance(tool_output, dict) else None)
        all_tables.extend(facts["tables"])
        all_images.extend(facts["images"])
        if facts["stats_prose"]:
            prose_chunks.append(facts["stats_prose"])

    existing_table = args.get("table")
    table_empty = not (
        isinstance(existing_table, dict)
        and (existing_table.get("headers") or existing_table.get("rows"))
    )
    if table_empty:
        richest = _richest_table(all_tables)
        if richest:
            args["table"] = richest

    # Images: keep LLM-supplied, else attach prior charts
    existing_images = args.get("images")
    if not (isinstance(existing_images, list) and existing_images):
        if all_images:
            args["images"] = all_images[:_MAX_IMAGES]

    if content_is_placeholder(args.get("content")):
        args["content"] = _synthesize_content(
            str(args.get("title") or title_fallback),
            drafts,
            all_tables[:3] if all_tables else (
                [args["table"]] if isinstance(args.get("table"), dict) else []
            ),
            "\n".join(prose_chunks),
        )

    return args


def apply_bind_to_tool_calls(
    tool_calls: list[dict] | None,
    prior_results: list[Any],
    *,
    step_tool_name: str | None = None,
    step_tool_args: dict | None = None,
    title_fallback: str = "Agent report",
) -> list[dict]:
    """Return a copy of ``tool_calls`` with export_document args bound.

    When the draft omitted tool_calls but the plan step is ``export_document``,
    synthesize a single call from ``step_tool_args``.
    """
    calls = [dict(tc) for tc in (tool_calls or [])]

    def _bind_one(tc: dict) -> dict:
        fn = dict(tc.get("function") or {})
        name = fn.get("name") or ""
        if name != "export_document":
            return tc
        raw_args = fn.get("arguments", "{}")
        if isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args) if raw_args.strip() else {}
            except (json.JSONDecodeError, TypeError):
                parsed = {}
        elif isinstance(raw_args, dict):
            parsed = dict(raw_args)
        else:
            parsed = {}
        bound = bind_export_args(parsed, prior_results, title_fallback=title_fallback)
        fn["arguments"] = json.dumps(bound, ensure_ascii=False, default=str)
        out = dict(tc)
        out["function"] = fn
        return out

    if calls:
        return [_bind_one(tc) for tc in calls]

    if (step_tool_name or "") == "export_document":
        bound = bind_export_args(
            step_tool_args or {},
            prior_results,
            title_fallback=title_fallback,
        )
        return [{
            "id": "export_bind_synth",
            "type": "function",
            "function": {
                "name": "export_document",
                "arguments": json.dumps(bound, ensure_ascii=False, default=str),
            },
        }]
    return calls
