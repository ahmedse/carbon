"""Catalog-metadata-driven ESS read renderers (I4).

Resolve renderers by ``kind`` / ``empty_render`` from the instance catalog,
not by hard-coded ``api_name`` branches in the runner.
"""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T
from ai.engine.pack_vocab import V


import json
from typing import Any

from ai.engine.cognition.turn.ess_read import empty_render_text
from ai.engine.cognition.turn.ess_read_i18n import RENDER_SCOPE, UNSUMMARIZED_FALLBACK

# APIs that share the balance renderer (same row shape / alias in one place).
BALANCE_APIS = T("turn/catalog_render.py::BALANCE_APIS")

PAYSLIP_APIS = T("turn/catalog_render.py::PAYSLIP_APIS")

# Fallback when the scoped catalog entry is not passed into the renderer.
_API_RENDER_META: dict[str, dict[str, str]] = {
    "get_my_leave_balance": {"kind": "balance", "empty_render": "no_balance_configured"},
    "list_leave_entitlements": {"kind": "balance", "empty_render": "no_balance_configured"},
    "list_my_leave": {"kind": "history", "empty_render": "no_leave_requests", "scope": "leave_history"},
    "list_my_loans": {"kind": "history", "empty_render": "no_loans", "scope": V("t_loans")},
    "list_my_payslips": {"kind": V("t_payslip_2"), "empty_render": "no_payslips", "scope": V("t_payslip_2")},
    "list_attendance": {"kind": "history", "empty_render": "no_attendance_rows", "scope": V("t_attendance")},
    "list_my_attendance": {"kind": "history", "empty_render": "no_attendance_rows", "scope": V("t_attendance")},
    "list_my_attendance_permissions": {
        "kind": "history",
        "empty_render": "no_attendance_permissions",
        "scope": "permissions",
    },
}


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


def _lang_code(language: str) -> str:
    return "ar" if str(language or "en").strip().casefold().startswith("ar") else "en"


def _scope_prefix(scope_key: str, language: str) -> str:
    lang = _lang_code(language)
    row = RENDER_SCOPE.get(scope_key) or {}
    return str(row.get(lang) or row.get("en") or "").strip()


_MAX_DECLARED_ROWS = 5
_MAX_DECLARED_FIELDS = 12
_DECLARED_KINDS = frozenset({"list", "detail", "read"})


def catalog_entry_named(catalog: list | None, api_name: str) -> dict | None:
    """The catalog dict whose ``name`` is ``api_name``, or None."""
    wanted = str(api_name or "").strip()
    if not wanted:
        return None
    for entry in catalog or []:
        if isinstance(entry, dict) and str(entry.get("name") or "").strip() == wanted:
            return entry
    return None


def resolve_render_meta(api_name: str, catalog_entry: dict | None = None) -> dict[str, str] | None:
    """Return ``{kind, empty_render, scope?}`` for a catalog GET read."""
    api = str(api_name or "").strip()
    if not api:
        return None
    entry = catalog_entry if isinstance(catalog_entry, dict) else None
    if entry is None:
        entry = _API_RENDER_META.get(api)
    if not isinstance(entry, dict):
        return _API_RENDER_META.get(api)
    kind = str(entry.get("kind") or entry.get("render") or "").strip()
    if kind == "write" or not kind:
        return _API_RENDER_META.get(api)
    meta = {
        "kind": kind,
        "empty_render": str(entry.get("empty_render") or "").strip(),
    }
    scope = entry.get("scope")
    if scope:
        meta["scope"] = str(scope)
    elif api in BALANCE_APIS:
        meta["scope"] = "balance"
    elif api in PAYSLIP_APIS:
        meta["scope"] = V("t_payslip_2")
    elif api == "list_my_leave":
        meta["scope"] = "leave_history"
    elif api == "list_my_loans":
        meta["scope"] = V("t_loans")
    elif api in {"list_attendance", "list_my_attendance"}:
        meta["scope"] = V("t_attendance")
    elif api == "list_my_attendance_permissions":
        meta["scope"] = "permissions"
    if not meta["empty_render"]:
        fallback = _API_RENDER_META.get(api) or {}
        meta["empty_render"] = str(fallback.get("empty_render") or "").strip()
    return meta


def _balance_row_chunk(row: dict, *, ar: bool) -> str | None:
    kind = (
        _code_or_text(row.get("leave_type"))
        or _code_or_text(row.get("leave_type_label"))
    )
    if not kind:
        return None
    remaining = row.get("remaining")
    entitled = row.get("entitled")
    if entitled is None:
        entitled = row.get("entitled_days")
    used = row.get("used_days")
    if used is None:
        used = row.get("used")
    if remaining is not None:
        if ar:
            chunk = f"{kind} المتبقي {remaining}"
            if entitled is not None:
                chunk += f" (المستحق {entitled})"
        else:
            chunk = f"{kind} remaining {remaining}"
            if entitled is not None:
                chunk += f" (entitled {entitled})"
        return chunk
    if entitled is not None:
        if ar:
            chunk = f"{kind} المستحق {entitled}"
            if used is not None:
                chunk += f" (المستخدم {used})"
        else:
            chunk = f"{kind} entitled {entitled}"
            if used is not None:
                chunk += f" (used {used})"
        return chunk
    return None


def _balance_who(row: dict) -> str:
    V("t_employee_label_on_an_org_wide")
    name = str(row.get("employee_name") or "").strip()
    no = str(row.get("employee_no") or "").strip()
    if not name and not no:
        return ""
    who = f"{name} ({no})" if name and no else (name or no)
    year = row.get("year")
    return f"{who}, {year}" if year not in (None, "") else who


def render_balance_rows(rows: list[dict], language: str, *, empty_render: str) -> str | None:
    ar = _lang_code(language) == "ar"
    # An org list (HR) carries employee_name on every row. Rendering it as
    # "Your  balance" drops the name, so the same six types repeat once
    # per  and look like one person's balance printed over and over.
    roster = any(_balance_who(row) for row in rows)
    if roster:
        lines: list[str] = []
        seen: set[str] = set()
        for row in rows:
            who = _balance_who(row)
            chunk = _balance_row_chunk(row, ar=ar)
            if not chunk:
                continue
            if who and who not in seen:
                seen.add(who)
                lines.append(f"{who}")
            lines.append(f"- {chunk}")
        if not lines:
            return empty_render_text(empty_render or "no_balance_configured", language)
        prefix = "أرصدة الإجازات" if ar else V("t_leave_balances")
        return f"{prefix}\n\n" + "\n".join(lines)

    parts: list[str] = []
    for row in rows:
        chunk = _balance_row_chunk(row, ar=ar)
        if chunk:
            parts.append(chunk)
    if not parts:
        return empty_render_text(empty_render or "no_balance_configured", language)
    # Markdown bullets — Chat MarkdownMessage renders a readable list instead of
    # one semicolon-glued paragraph (which looked oversized / washed out).
    # Plain prefix (not **bold**) so Chat never promotes the label to a big heading.
    prefix = _scope_prefix("balance", language)
    bullets = "\n".join(f"- {chunk}" for chunk in parts)
    return f"{prefix}\n\n{bullets}" if prefix else bullets


def render_history_rows(
    rows: list[dict],
    language: str,
    *,
    empty_render: str,
    scope_key: str,
    row_formatter,
) -> str | None:
    if not rows:
        return empty_render_text(empty_render, language)
    ar = _lang_code(language) == "ar"
    parts = [row_formatter(row, ar=ar) for row in rows[:5]]
    parts = [p for p in parts if p]
    if not parts:
        return empty_render_text(empty_render, language)
    body = "; ".join(parts) if not ar else "؛ ".join(parts)
    prefix = _scope_prefix(scope_key, language)
    return f"{prefix} ({len(rows)}): {body}."


def _format_leave_history_row(row: dict, *, ar: bool) -> str:
    kind = _code_or_text(row.get("leave_type")) or V("t_leave")
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
    return ", ".join(bits) if not ar else "، ".join(bits)


def _format_loan_history_row(row: dict, *, ar: bool) -> str:
    kind = _code_or_text(row.get("loan_type")) or V("t_loan_2")
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
    return ", ".join(bits) if not ar else "، ".join(bits)


def _format_payslip_row(row: dict, *, ar: bool) -> str:
    line = _code_or_text(row.get("line_type")) or "line"
    amount = row.get("amount")
    bits = [line]
    if amount is not None:
        bits.append(str(amount))
    return ", ".join(bits) if not ar else "، ".join(bits)


def _format_attendance_row(row: dict, *, ar: bool) -> str:
    day = row.get("date")
    status = _code_or_text(row.get("status")) or ""
    bits: list[str] = []
    if day:
        bits.append(str(day))
    if status:
        bits.append(status)
    return ", ".join(bits) if not ar else "، ".join(bits)


def _format_permission_row(row: dict, *, ar: bool) -> str:
    kind = _code_or_text(row.get("permission_type")) or "permission"
    hours = row.get("hours")
    day = row.get("date")
    bits = [kind]
    if hours is not None:
        bits.append(f"{hours}h" if not ar else f"{hours} س")
    if day:
        bits.append(str(day))
    return ", ".join(bits) if not ar else "، ".join(bits)


def _declared_fields(entry: dict | None) -> list[str]:
    if not isinstance(entry, dict):
        return []
    raw = entry.get("returns")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        name = str(item or "").strip()
        if name and name not in out:
            out.append(name)
        if len(out) >= _MAX_DECLARED_FIELDS:
            break
    return out


def _declared_cell(row: dict, field: str) -> str | None:
    if field not in row:
        return None
    value = row.get(field)
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        text = _code_or_text(value)
        return text or None
    if isinstance(value, (list, tuple)):
        return None
    return str(value)


def _field_label(labels: dict | None, field: str, *, ar: bool) -> str:
    entry = (labels or {}).get(field)
    if isinstance(entry, dict):
        text = str(entry.get("ar" if ar else "en") or entry.get("en") or "").strip()
        if text:
            return text
    return ""


def _format_declared_row(
    row: dict, fields: list[str], *, ar: bool, labels: dict | None = None,
) -> str:
    bits: list[str] = []
    for field in fields:
        cell = _declared_cell(row, field)
        if cell is None:
            continue
        value = row.get(field)
        if labels and isinstance(value, dict):
            cell = str(value.get("label") or value.get("name") or cell).strip()
        label = _field_label(labels, field, ar=ar)
        bits.append(f"{label}: {cell}" if label else f"{field}={cell}")
    if labels:
        return " · ".join(bits)
    return ("، " if ar else ", ").join(bits)


def _field_key(name: str) -> str:
    return "_".join(str(name or "").strip().lower().replace("-", " ").split())


def project_fields(
    declared: list[str],
    asked: list[str] | None,
    labels: dict | None = None,
) -> list[str] | None:
    """The declared fields the user asked for, in declared order.

    An ask matches a field name or any of its display labels. ``None`` when a
    name matches no declared field: that ask is the writer's, which may say
    the record does not carry it. No ask keeps every field.
    """
    if not asked:
        return list(declared)
    keys = _field_keys(declared, labels)
    picked: set[str] = set()
    for raw in asked:
        want = _field_key(raw)
        if not want:
            continue
        hit = _match_field(keys, want)
        if hit is None:
            return None
        picked.add(hit)
    return [d for d in declared if d in picked]


def _sensitive_fields(entry: dict | None) -> list[str]:
    raw = (entry or {}).get("sensitive_fields")
    if not isinstance(raw, list):
        return []
    return [str(name).strip() for name in raw if str(name).strip()]


def visible_fields(
    declared: list[str],
    asked: list[str] | None,
    labels: dict | None = None,
    sensitive: list[str] | None = None,
) -> list[str] | None:
    """Declared fields to restate. Pay/secret fields stay off a record dump.

    Catalog ``sensitive_fields`` appear only when the ask names them and is
    not the whole public record. No ask, or an ask of every public field,
    hides them — the user must request those values.
    """
    shown = project_fields(declared, asked, labels)
    if shown is None:
        return None
    hidden = {name for name in (sensitive or []) if name in declared}
    if not hidden:
        return shown
    public = [name for name in declared if name not in hidden]
    dump = not asked or set(shown) >= set(public)
    if dump:
        return [name for name in shown if name not in hidden]
    return shown


def unmatched_fields(
    declared: list[str], asked: list[str] | None, labels: dict | None = None,
) -> list[str]:
    """The asked names that match no declared field or label. Empty when none declared."""
    if not declared or not asked:
        return []
    keys = _field_keys(declared, labels)
    return [
        str(raw) for raw in asked
        if _field_key(raw) and _match_field(keys, _field_key(raw)) is None
    ]


def _field_keys(declared: list[str], labels: dict | None) -> dict[str, str]:
    keys = {_field_key(d): d for d in declared}
    for field, label in (labels or {}).items():
        if field not in declared:
            continue
        texts = label.values() if isinstance(label, dict) else [label]
        for text in texts:
            keys.setdefault(_field_key(str(text).rstrip(".")), field)
    return keys


def _match_field(keys: dict[str, str], want: str) -> str | None:
    hit = keys.get(want)
    if hit is None:
        near = {d for k, d in keys.items() if want in k or k in want}
        hit = next(iter(near)) if len(near) == 1 else None
    return hit


def _empty_declared(empty_render: str, language: str, *, ar: bool) -> str:
    return empty_render_text(empty_render, language) or (
        "لا توجد صفوف." if ar else "No rows."
    )


def restate_last_view(view: dict | None, language: str = "en") -> str:
    """0-LLM restatement of the last table. Invents no values."""
    if not isinstance(view, dict):
        return ""
    tables = view.get("tables") or []
    table = next(
        (item for item in tables if isinstance(item, dict) and item.get("rows")),
        None,
    )
    if table is None:
        return ""
    columns = [str(col).strip() for col in (table.get("columns") or []) if str(col).strip()]
    records: list[dict] = []
    for row in table.get("rows") or []:
        if isinstance(row, dict):
            records.append(row)
            continue
        if isinstance(row, (list, tuple)) and columns:
            records.append({
                columns[i]: row[i]
                for i in range(min(len(columns), len(row)))
            })
    if not records:
        return ""
    fields = columns[:_MAX_DECLARED_FIELDS] or [
        str(key) for key in records[0] if str(key).strip()
    ][:_MAX_DECLARED_FIELDS]
    return render_declared_rows(
        records,
        language,
        empty_render="",
        fields=fields,
        kind="detail" if len(records) == 1 else "list",
        label=str(table.get("title") or "").strip(),
    ) or ""


def render_declared_rows(
    rows: list[dict],
    language: str,
    *,
    empty_render: str,
    fields: list[str],
    latest_by: str = "",
    kind: str = "list",
    label: str = "",
    labels: dict | None = None,
) -> str | None:
    """0-LLM restatement of catalog ``returns`` fields. Invents no values."""
    if not fields:
        return None
    ar = _lang_code(language) == "ar"
    if not rows:
        return _empty_declared(empty_render, language, ar=ar)
    ordered = list(rows)
    if latest_by:
        ordered = sorted(
            ordered,
            key=lambda row: str(row.get(latest_by) or ""),
            reverse=True,
        )
    if kind == "detail":
        body = _format_declared_row(ordered[0], fields, ar=ar, labels=labels)
        return body or _empty_declared(empty_render, language, ar=ar)
    shown = ordered[:_MAX_DECLARED_ROWS]
    parts = [_format_declared_row(row, fields, ar=ar, labels=labels) for row in shown]
    parts = [p for p in parts if p]
    if not parts:
        return _empty_declared(empty_render, language, ar=ar)
    count = str(len(rows))
    head = f"{label} ({count})" if label else count
    joiner = "؛ " if ar else "; "
    return f"{head}: {joiner.join(parts)}."


def _aggregate_kind(payload: Any) -> str:
    """``metric`` or ``breakdown`` when the payload itself cites the bind.

    Shape only. No catalog name and no words from the user message.
    """
    if not isinstance(payload, dict):
        return ""
    if (
        payload.get("total") is not None
        and str(payload.get("dimension") or "").strip()
        and isinstance(payload.get("breakdown"), list)
    ):
        return "breakdown"
    if payload.get("value") is not None and (
        str(payload.get("citation") or "").strip()
        or str(payload.get("metric") or "").strip()
    ):
        return "metric"
    return ""


def render_metric_bind(payload: dict, language: str = "en") -> str | None:
    """Value plus the host citation. Adds no filter."""
    value = payload.get("value")
    if value is None:
        return None
    bind = str(payload.get("citation") or payload.get("metric") or "").strip()
    if _lang_code(language) == "ar":
        return f"العدد: {value} ({bind})" if bind else f"العدد: {value}"
    return f"{value}. {bind}" if bind else str(value)


def _bucket_label(label: Any, *, ar: bool) -> str:
    text = str(label)
    if ar and text.lower() in {"true", "false"}:
        return "نعم" if text.lower() == "true" else "لا"
    return text


def render_breakdown_bind(
    payload: dict, language: str = "en", labels: dict | None = None,
) -> str | None:
    """Total plus the dimension, applied filters, and bucket counts.

    A filter that is not in ``applied_filters`` or ``dimension`` is not said.
    ``labels`` are the catalog's display labels for a dimension key.
    """
    lines: list[str] = []
    ar = _lang_code(language) == "ar"
    total = payload.get("total")
    if total is not None:
        lines.append(f"الإجمالي: {total}" if ar else f"Total: {total}")
    dimension = str(payload.get("dimension") or "").strip()
    if dimension:
        shown = _field_label(labels, dimension, ar=ar) or dimension
        lines.append(f"حسب: {shown}" if ar else f"By: {shown}")
    applied = payload.get("applied_filters")
    if isinstance(applied, dict):
        for key, value in applied.items():
            if value in (None, "", [], {}):
                continue
            lines.append(f"{key}: {value}")
    rows = payload.get("breakdown")
    if isinstance(rows, list):
        for row in rows[:8]:
            if not isinstance(row, dict):
                continue
            label = row.get("label")
            count = row.get("count")
            if label is None or count is None:
                continue
            lines.append(f"{_bucket_label(label, ar=ar)}: {count}")
    if not lines:
        return None
    return "\n".join(lines)


def render_catalog_read(
    tool_output: Any,
    api_name: str,
    language: str = "en",
    *,
    catalog_entry: dict | None = None,
    fields: list[str] | None = None,
) -> str | None:
    """0-LLM restatement resolved by catalog ``kind``. Invents no numbers.

    ``fields`` are the returned fields the user asked about; a declared-row
    restatement shows only those.
    """
    api = str(api_name or "").strip()
    payload = _unwrap_tool_payload(tool_output)
    meta = resolve_render_meta(api, catalog_entry)
    kind = str((meta or {}).get("kind") or "")
    structural = _aggregate_kind(payload)
    # A payload that cites its own bind restates that bind, unless the catalog
    # gave the read another renderer: the writer could narrate a filter the
    # payload never applied.
    if structural and kind in ("", structural):
        dim_labels = (catalog_entry or {}).get("field_labels") if isinstance(catalog_entry, dict) else None
        rendered = (
            render_breakdown_bind(payload, language, dim_labels if isinstance(dim_labels, dict) else None)
            if structural == "breakdown"
            else render_metric_bind(payload, language)
        )
        if rendered:
            return rendered
    if not meta:
        return None
    rows = _as_record_list(payload)
    kind = meta["kind"]
    empty_key = meta.get("empty_render") or ""

    if kind == "balance" or api in BALANCE_APIS:
        return render_balance_rows(rows, language, empty_render=empty_key or "no_balance_configured")

    if kind == V("t_payslip_2") or api in PAYSLIP_APIS:
        return render_history_rows(
            rows,
            language,
            empty_render=empty_key or "no_payslips",
            scope_key=meta.get("scope") or V("t_payslip_2"),
            row_formatter=_format_payslip_row,
        )

    if kind == "history":
        if api == "list_my_leave":
            return render_history_rows(
                rows, language,
                empty_render=empty_key or "no_leave_requests",
                scope_key="leave_history",
                row_formatter=_format_leave_history_row,
            )
        if api == "list_my_loans":
            return render_history_rows(
                rows, language,
                empty_render=empty_key or "no_loans",
                scope_key=V("t_loans"),
                row_formatter=_format_loan_history_row,
            )
        if api in {"list_attendance", "list_my_attendance"}:
            return render_history_rows(
                rows, language,
                empty_render=empty_key or "no_attendance_rows",
                scope_key=V("t_attendance"),
                row_formatter=_format_attendance_row,
            )
        if api == "list_my_attendance_permissions":
            return render_history_rows(
                rows, language,
                empty_render=empty_key or "no_attendance_permissions",
                scope_key="permissions",
                row_formatter=_format_permission_row,
            )

    if kind in _DECLARED_KINDS:
        entry = catalog_entry if isinstance(catalog_entry, dict) else None
        labels = (entry or {}).get("field_labels")
        shown = visible_fields(
            _declared_fields(entry),
            fields,
            labels if isinstance(labels, dict) else None,
            _sensitive_fields(entry),
        )
        if not shown:
            return None
        return render_declared_rows(
            rows,
            language,
            empty_render=empty_key or ("no_detail_row" if kind == "detail" else "no_list_rows"),
            fields=shown,
            latest_by=str((entry or {}).get("latest_by") or "").strip(),
            kind=kind,
            label=str((entry or {}).get("label") or "").strip(),
            labels=labels if isinstance(labels, dict) else None,
        )

    return None


def honest_unsummarized_fallback(language: str = "en") -> str:
    """User-visible fallback when catalog render and synthesis both miss."""
    lang = _lang_code(language)
    return UNSUMMARIZED_FALLBACK[lang]


def should_honest_fallback(final_text: str | None, completed_tools: list | None) -> bool:
    V("t_stage_invariant_adr_0049_the_fallback")
    if not completed_tools:
        return False
    return not (final_text or "").strip()
