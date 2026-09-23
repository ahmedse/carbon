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

# Template slots the LLM leaves in prose/tables — e.g. [Insert specific insights…],
# [Avg Kuwaiti Salary], [Median Non-Kuwaiti Salary]. Any of these = hollow pack.
_UNFILLED_SLOT_RE = re.compile(
    r"\["
    r"(?:"
    r"Insert\b"
    r"|Placeholder\b"
    r"|TODO\b"
    r"|TBD\b"
    r"|N/?A\b"
    r"|Avg(?:erage)?\b"
    r"|Median\b"
    r"|Highest\b"
    r"|Lowest\b"
    r"|Specific insights?\b"
    r"|actionable recommendations?\b"
    r"|[A-Za-z][^\]]{0,60}?\b(?:Salary|Value|Count|Rate|Amount|Figure|Metric)\b"
    r")"
    r"[^\]]*\]",
    re.IGNORECASE,
)

# Mid-run / incomplete language that must not ship as a finished deliverable.
_MID_RUN_RE = re.compile(
    r"\b(?:in progress|work in progress|WIP|awaiting|pending results?"
    r"|results? (?:will|to) (?:follow|come|be (?:added|inserted))"
    r"|partial (?:results?|findings?|data)|TBD|to be (?:determined|confirmed)"
    r"|once (?:the )?(?:run|computation|validation) completes?)\b",
    re.IGNORECASE,
)

_MIN_PROSE_CHARS = 120
_MIN_TABLE_CELLS = 2


def text_has_unfilled_slots(text: str | None) -> bool:
    """True when prose still contains LLM template brackets."""
    if not (text or "").strip():
        return False
    return bool(_UNFILLED_SLOT_RE.search(text))


def content_is_placeholder(md: str | None) -> bool:
    """True when markdown is empty or a hollow skeleton (placeholder tokens)."""
    text = (md or "").strip()
    if not text:
        return True
    if _PLACEHOLDER_RE.search(text):
        return True
    if text_has_unfilled_slots(text):
        return True
    # Mostly bracketed stubs like "[Placeholder for insights]"
    brackets = re.findall(r"\[[^\]]{3,80}\]", text)
    if brackets and len("".join(brackets)) >= max(24, int(len(text) * 0.35)):
        return True
    return False


def content_is_mid_run(md: str | None) -> bool:
    """True when prose advertises incomplete / pending work."""
    text = (md or "").strip()
    if not text:
        return False
    return bool(_MID_RUN_RE.search(text))


def cell_is_placeholder(cell: Any) -> bool:
    """True when a table cell is an unfilled template slot."""
    s = str(cell or "").strip()
    if not s:
        return False
    if text_has_unfilled_slots(s):
        return True
    # Whole-cell bracket stub: [anything]
    if re.fullmatch(r"\[[^\]]{2,80}\]", s):
        return True
    return False


def table_has_unfilled_slots(table: dict | None) -> bool:
    if not isinstance(table, dict):
        return False
    for row in table.get("rows") or []:
        cells = row if isinstance(row, (list, tuple)) else [row]
        if any(cell_is_placeholder(c) for c in cells):
            return True
    return False


def table_has_substance(table: dict | None) -> bool:
    """True when table carries real data cells (not headers-only / blank / stubs)."""
    if not isinstance(table, dict):
        return False
    if table_has_unfilled_slots(table):
        return False
    rows = table.get("rows")
    if not isinstance(rows, list) or not rows:
        return False
    filled = 0
    for row in rows:
        cells = row if isinstance(row, (list, tuple)) else [row]
        for c in cells:
            if str(c or "").strip() and not cell_is_placeholder(c):
                filled += 1
    return filled >= _MIN_TABLE_CELLS


def images_have_substance(images: list | None) -> bool:
    if not isinstance(images, list):
        return False
    return any(
        isinstance(img, dict) and str(img.get("image_b64") or "").strip()
        for img in images
    )


def export_has_substance(
    content: str | None,
    table: dict | None = None,
    images: list | None = None,
) -> tuple[bool, str]:
    """Gate finished deliverables: refuse hollow, mid-run, or title-only packs.

    Returns ``(ok, reason)``. Reason is empty when ok.

    A chart alone does **not** excuse unfilled ``[Insert…]`` / ``[Avg … Salary]``
    slots in prose or tables — that is the hollow Word the operator already saw.
    """
    if text_has_unfilled_slots(content) or table_has_unfilled_slots(table):
        return False, (
            "Export refused — the draft still contains unfilled template slots "
            "(e.g. [Insert …], [Avg … Salary]). Bind real findings from prior "
            "steps, then export."
        )
    if content_is_placeholder(content) and not table_has_substance(table) and not images_have_substance(images):
        return False, (
            "Export refused — no real findings to write. Provide markdown "
            "content with measured results, and/or a table, and/or chart images."
        )
    if content_is_mid_run(content) and not table_has_substance(table):
        return False, (
            "Export refused — content still reads as in-progress / pending. "
            "Finish the analysis steps, then export a complete findings pack."
        )
    prose = (content or "").strip()
    if (
        not table_has_substance(table)
        and not images_have_substance(images)
        and len(prose) < _MIN_PROSE_CHARS
    ):
        return False, (
            "Export refused — findings are too thin for a deliverable "
            f"(need ≥{_MIN_PROSE_CHARS} characters of prose, a data table, or a chart)."
        )
    return True, ""


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


# ── PV2-3A: deterministic-first host API steps ─────────────────────────────

_MUSTACHE_RE = re.compile(r"\{\{[^{}]+\}\}")


def contains_mustache_placeholders(value: Any) -> bool:
    """True when any string in ``value`` still has ``{{…}}`` template slots."""
    if isinstance(value, str):
        return bool(_MUSTACHE_RE.search(value))
    if isinstance(value, dict):
        return any(contains_mustache_placeholders(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_mustache_placeholders(v) for v in value)
    return False


def _write_slots_for_api(api_name: str, api_catalog: Any) -> list[dict[str, Any]]:
    """Catalog ``write_slots`` for ``api_name`` (empty when undeclared)."""
    name = str(api_name or "").strip()
    if not name or not isinstance(api_catalog, (list, tuple)):
        return []
    for entry in api_catalog:
        if not isinstance(entry, dict) or entry.get("name") != name:
            continue
        slots = entry.get("write_slots")
        return [s for s in slots if isinstance(s, dict)] if isinstance(slots, list) else []
    return []


def is_fully_bound_host_api(
    tool_name: str | None,
    tool_args: dict | None,
    api_catalog: Any,
) -> bool:
    """True when a ``call_host_api`` step can skip draft/observe (PV2-3A).

    Requires: tool is ``call_host_api``, catalog declares ``write_slots``, no
    ``{{…}}`` placeholders remain, and every ``required`` slot is present and
    non-blank in ``tool_args.body``. Partial / unbound steps keep the LLM path.
    """
    if (tool_name or "").strip() != "call_host_api":
        return False
    if not isinstance(tool_args, dict):
        return False
    if contains_mustache_placeholders(tool_args):
        return False
    api_name = str(tool_args.get("api_name") or "").strip()
    if not api_name:
        return False
    slots = _write_slots_for_api(api_name, api_catalog)
    if not slots:
        return False
    body = tool_args.get("body") if isinstance(tool_args.get("body"), dict) else {}
    for slot in slots:
        if not bool(slot.get("required", True)):
            continue
        field = str(slot.get("field") or "").strip()
        if not field:
            continue
        val = body.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            return False
    return True


# First-person ESS GETs with no path id. Bind even when the scoped catalog
# copy was not passed into the loop (same contract as /people/me/).
_SELF_GET_NO_PATH = frozenset({
    "get_my_profile",
    "get_my_leave_balance",
    "list_my_leave",
    "list_my_loans",
    "list_my_payslips",
    "list_my_attendance_permissions",
})


def is_bound_catalog_read(
    tool_name: str | None,
    tool_args: dict | None,
    api_catalog: Any,
) -> bool:
    """True when a GET ``call_host_api`` needs no path params and is fully named.

    First-person ESS lookups skip DraftWitness and LLM observe; restatement
    is ``render_bound_catalog_read``. Mutations stay on
    ``is_fully_bound_host_api``.
    """
    if (tool_name or "").strip() != "call_host_api":
        return False
    if not isinstance(tool_args, dict):
        return False
    if contains_mustache_placeholders(tool_args):
        return False
    api_name = str(tool_args.get("api_name") or "").strip()
    if not api_name:
        return False
    entry = None
    for item in api_catalog or []:
        if isinstance(item, dict) and str(item.get("name") or "") == api_name:
            entry = item
            break
    if not isinstance(entry, dict):
        return api_name in _SELF_GET_NO_PATH
    if str(entry.get("method") or "GET").upper() != "GET":
        return False
    path = str(entry.get("path") or "")
    if re.search(r"\{[^}]+\}", path):
        return False
    if entry.get("requires_confirmation"):
        return False
    return True


def _unwrap_tool_payload(tool_output: Any) -> Any:
    if not isinstance(tool_output, dict):
        return tool_output
    raw = tool_output.get("result", tool_output.get("data"))
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return raw
    if isinstance(raw, dict) and "data" in raw and "status_code" in raw:
        return raw.get("data")
    return raw


def _code_or_text(value: Any) -> str:
    if isinstance(value, dict):
        text = value.get("code") or value.get("name") or value.get("label")
        return str(text).strip() if text else ""
    if value is None:
        return ""
    return str(value).strip()


def _as_record_list(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("results", "rows", "items", "records", "data"):
            if isinstance(payload.get(key), list):
                return [row for row in payload[key] if isinstance(row, dict)]
        return [payload]
    return []


def render_bound_catalog_read(
    tool_output: Any,
    api_name: str,
    language: str = "en",
) -> str | None:
    """0-LLM restatement of a bound ESS lookup. Invents no numbers."""
    api = str(api_name or "").strip()
    payload = _unwrap_tool_payload(tool_output)
    ar = str(language or "en").strip().casefold().startswith("ar")
    rows = _as_record_list(payload)

    if api == "get_my_leave_balance":
        parts: list[str] = []
        for row in rows:
            kind = _code_or_text(row.get("leave_type"))
            remaining = row.get("remaining")
            if not kind or remaining is None:
                continue
            entitled = row.get("entitled")
            if ar:
                chunk = f"{kind} المتبقي {remaining}"
                if entitled is not None:
                    chunk += f" (المستحق {entitled})"
            else:
                chunk = f"{kind} remaining {remaining}"
                if entitled is not None:
                    chunk += f" (entitled {entitled})"
            parts.append(chunk)
        if not parts:
            return "لا يوجد رصيد إجازة." if ar else "No leave-balance rows."
        joined = "؛ ".join(parts) if ar else "; ".join(parts)
        return (f"رصيد الإجازة: {joined}." if ar else f"Leave balance: {joined}.")

    if api == "list_my_leave":
        if not rows:
            return (
                "لا توجد طلبات إجازة مسجّلة."
                if ar
                else "No leave requests on record."
            )
        parts = []
        for row in rows[:5]:
            kind = _code_or_text(row.get("leave_type")) or "leave"
            status = _code_or_text(row.get("status") or row.get("correspondence_status"))
            start = row.get("start_date") or row.get("from_date")
            end = row.get("end_date") or row.get("to_date")
            bits = [kind]
            if start:
                bits.append(str(start))
            if end:
                bits.append(str(end))
            if status:
                bits.append(status)
            parts.append(", ".join(bits) if not ar else "، ".join(bits))
        body = "; ".join(parts) if not ar else "؛ ".join(parts)
        return (
            f"طلبات الإجازة ({len(rows)}): {body}."
            if ar
            else f"Leave requests ({len(rows)}): {body}."
        )

    if api == "list_my_loans":
        if not rows:
            return "لا توجد قروض قائمة." if ar else "No existing loans."
        parts = []
        for row in rows[:5]:
            kind = _code_or_text(row.get("loan_type")) or "loan"
            principal = row.get("principal")
            months = row.get("term_months")
            status = _code_or_text(row.get("status") or row.get("correspondence_status"))
            bits = [kind]
            if principal is not None:
                bits.append(str(principal))
            if months is not None:
                bits.append(f"{months} mo" if not ar else f"{months} شهر")
            if status:
                bits.append(status)
            parts.append(", ".join(bits) if not ar else "، ".join(bits))
        body = "; ".join(parts) if not ar else "؛ ".join(parts)
        return (
            f"القروض القائمة ({len(rows)}): {body}."
            if ar
            else f"Existing loans ({len(rows)}): {body}."
        )

    if api == "list_my_attendance_permissions":
        if not rows:
            return (
                "لا توجد أذونات حضور قائمة."
                if ar
                else "No existing attendance permissions."
            )
        parts = []
        for row in rows[:5]:
            kind = _code_or_text(row.get("permission_type")) or "permission"
            hours = row.get("hours")
            day = row.get("date")
            bits = [kind]
            if hours is not None:
                bits.append(f"{hours}h" if not ar else f"{hours} س")
            if day:
                bits.append(str(day))
            parts.append(", ".join(bits) if not ar else "، ".join(bits))
        body = "; ".join(parts) if not ar else "؛ ".join(parts)
        return (
            f"أذونات الحضور القائمة ({len(rows)}): {body}."
            if ar
            else f"Existing permissions ({len(rows)}): {body}."
        )

    if api in _SELF_GET_NO_PATH:
        from ai.engine.cognition.tool_digest import build_tool_digest

        item = tool_output if isinstance(tool_output, dict) else {
            "tool_name": "call_host_api",
            "tool_args": {"api_name": api},
            "result": payload,
        }
        if isinstance(item, dict) and not item.get("tool_args"):
            item = {**item, "tool_args": {"api_name": api}}
        digest = build_tool_digest([item], None)
        return digest or None
    return None


def is_bound_resolve_entity(
    tool_name: str | None,
    tool_args: dict | None,
) -> bool:
    """True when ``resolve_entity`` already has a query — skip draft."""
    if (tool_name or "").strip() != "resolve_entity":
        return False
    if not isinstance(tool_args, dict):
        return False
    if contains_mustache_placeholders(tool_args):
        return False
    return bool(str(tool_args.get("query") or "").strip())


def render_step_template(
    api_name: str,
    values: dict[str, Any] | None,
    language: str,
    step_templates: Any,
) -> str | None:
    """Render a bilingual ``step_templates`` entry for ``api_name``.

    ``step_templates`` shape (instance.yaml)::

        step_templates:
          submit_my_leave:
            en: "Leave submitted: {leave_type} …"
            ar: "تم تقديم الإجازة: {leave_type} …"

    Returns ``None`` when no template matches. Missing value keys render empty.
    """
    if not isinstance(step_templates, dict):
        return None
    entry = step_templates.get(str(api_name or "").strip())
    if not isinstance(entry, dict):
        return None
    lang = str(language or "en").strip().casefold()
    if lang.startswith("ar"):
        tpl = entry.get("ar") or entry.get("en")
    else:
        tpl = entry.get("en") or entry.get("ar")
    if not isinstance(tpl, str) or not tpl.strip():
        return None
    raw = dict(values or {})
    # Coerce for format — keep numbers/dates readable.
    mapping = {str(k): ("" if v is None else str(v)) for k, v in raw.items()}

    class _Safe(dict):
        def __missing__(self, key: str) -> str:
            return ""

    try:
        return tpl.format_map(_Safe(mapping)).strip() or None
    except (ValueError, KeyError):
        return tpl.strip()


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

    # Process-dial / bound plan steps: when the draft narrates instead of
    # calling the tool, synthesize from the plan's tool_args so Approve→resume
    # still writes (loan/leave/attendance). Never invent args — only when the
    # step already carries them.
    if (
        (step_tool_name or "") == "resolve_entity"
        and isinstance(step_tool_args, dict)
        and step_tool_args.get("query")
    ):
        return [{
            "id": "plan_step_bind_synth",
            "type": "function",
            "function": {
                "name": "resolve_entity",
                "arguments": json.dumps(
                    step_tool_args, ensure_ascii=False, default=str,
                ),
            },
        }]
    if (
        (step_tool_name or "") == "call_host_api"
        and isinstance(step_tool_args, dict)
        and step_tool_args.get("api_name")
    ):
        return [{
            "id": "plan_step_bind_synth",
            "type": "function",
            "function": {
                "name": "call_host_api",
                "arguments": json.dumps(
                    step_tool_args, ensure_ascii=False, default=str,
                ),
            },
        }]
    return calls
