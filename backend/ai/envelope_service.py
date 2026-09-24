"""Envelope synthesis service — the structured-output path for AI answers.

``synthesize_envelope`` asks the LLM (JSON mode) to emit a typed
:class:`AnswerEnvelope` from executed tool results. It is independent of the
markdown path and fails open: any exception returns ``None`` so the caller can
fall back to the existing markdown synthesis unchanged.

After the LLM returns, :func:`enrich_envelope_charts` keeps multi-bucket
charts, injects charts from ``analyze_*`` breakdowns when the LLM omitted
them, drops empty / single-point bars (a lone headcount bar is never worth
the ink), and :func:`sanitize_envelope_tables` strips sample payslip row dumps.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from ai.envelope import (
    AnswerEnvelope,
    EnvelopeCaveat,
    EnvelopeChart,
    EnvelopeSource,
    EnvelopeTable,
    envelope_from_json,
)
from ai.envelope_prompt import build_envelope_system_prompt
from ai.engine.core.resolution import payload_status

logger = logging.getLogger("pulse.envelope")

#: Titles that scream "employee-by-employee dump" — never ship these.
_DUMP_TABLE_TITLE_RE = re.compile(
    r"("
    r"sample\s+payslip|payslip\s+line\s+items|first\s+\d+\s+employees?"
    r"|employee[\s_-]?by[\s_-]?employee|raw\s+(?:salary|payslip)"
    r")",
    re.IGNORECASE,
)
#: Column sets that look like a payslip row dump.
_DUMP_COL_MARKERS = frozenset({
    "employee name", "employee no", "employee number", "emp no",
    "gross", "net", "gosi", "gosi/pifss", "pifss",
})


async def synthesize_envelope(
    *,
    instance_id: str,
    conversation_id: str,
    user_message: str,
    usable_tools: list[dict],
    model: str | None = None,
) -> AnswerEnvelope | None:
    """Synthesize a typed envelope from usable tool results, or ``None``.

    Never raises: parse/validation/LLM errors are logged and folded to ``None``
    so the caller falls back to the markdown path unchanged.
    """
    from ai.engine.llm.router import route_chat

    # Mirror the usable/no_match filtering in ``_synthesize_tool_results`` so
    # this service is safe to call even with an unfiltered list (idempotent).
    usable = _filter_usable(usable_tools)
    if not usable:
        return None

    results_text = _render_tool_results(usable)
    if not results_text.strip():
        return None

    system = build_envelope_system_prompt()
    user = f"User's question: {user_message}\n\nTool results (JSON):\n{results_text}"

    try:
        result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"envelope-{conversation_id}",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            model=model,
            tools=None,
            response_format={"type": "json_object"},
        )
    except Exception:
        logger.warning("Envelope synthesis LLM call failed", exc_info=True)
        return _deterministic_fallback_envelope(usable, user_message)

    content = (result.get("content") or "").strip()
    if not content:
        return _deterministic_fallback_envelope(usable, user_message)
    try:
        envelope = envelope_from_json(content)
    except ValueError:
        logger.warning("Envelope synthesis returned invalid JSON/schema", exc_info=True)
        return _deterministic_fallback_envelope(usable, user_message)

    try:
        envelope = ground_envelope_blocks(envelope, usable, user_message=user_message)
        envelope = enrich_envelope_charts(envelope, usable)
        return sanitize_envelope_tables(envelope)
    except Exception:
        logger.warning("Envelope enrichment failed; returning raw envelope", exc_info=True)
        return envelope


def _deterministic_fallback_envelope(
    usable: list[dict],
    user_message: str,
) -> AnswerEnvelope | None:
    """Typed data blocks when prose synthesis is unavailable."""
    blocks = deterministic_envelope_blocks(usable, user_message=user_message)
    if not (blocks["tables"] or blocks["charts"]) or not blocks["sources"]:
        return None
    return AnswerEnvelope(
        headline="Live data summary",
        prose=[
            "The tables and charts below are computed directly from the "
            "returned platform data."
        ],
        **blocks,
    )


# ── Chart enrichment (scalar → series) ───────────────────────────────────────

def _series_point_count(series: list | None) -> int:
    """Count flattenable ``[label, value]`` pairs in an envelope chart series."""
    count = 0
    for s in series or []:
        if not isinstance(s, dict):
            continue
        data = s.get("data")
        if not isinstance(data, list):
            continue
        for entry in data:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                count += 1
    return count


def _humanize_metric(metric: str) -> str:
    raw = (metric or "").strip().replace("_", " ")
    if not raw:
        return "Total"
    return raw[:1].upper() + raw[1:]


def _unwrap_tool_payload(raw: Any) -> Any:
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return raw
    if isinstance(data, dict) and "status_code" in data and "data" in data:
        data = data["data"]
    return data


def _extract_scalar_metrics(usable: list[dict]) -> list[dict[str, Any]]:
    """Pull single-number metrics from tool results for chart series fill.

    Recognises:
    - ``aggregate_entity`` → ``{metric, value, description}``
    - ``analyze_*`` (or any result) with a numeric ``total`` and empty/absent
      ``breakdown`` — the headcount-without-dimension shape
    """
    scalars: list[dict[str, Any]] = []
    for tr in usable or []:
        data = _unwrap_tool_payload(tr.get("result"))
        if not isinstance(data, dict):
            continue
        # A10: never chart unauthorized / empty-scope soft-zeros
        if data.get("unauthorized") or data.get("error"):
            continue

        if "metric" in data and isinstance(data.get("value"), (int, float)):
            label = (
                (data.get("description") or "").strip()
                or _humanize_metric(str(data.get("metric") or ""))
            )
            scalars.append({
                "label": label,
                "value": int(data["value"]) if float(data["value"]).is_integer()
                else float(data["value"]),
                "metric": str(data.get("metric") or ""),
                "tool": tr.get("tool_name") or "aggregate_entity",
            })
            continue

        breakdown = data.get("breakdown")
        total = data.get("total")
        if isinstance(total, (int, float)) and not breakdown:
            dim = (data.get("dimension") or "").strip()
            label = _humanize_metric(dim) if dim else "Total"
            scalars.append({
                "label": label,
                "value": int(total) if float(total).is_integer() else float(total),
                "metric": dim or "total",
                "tool": tr.get("tool_name") or "analyze",
            })
    return scalars


def _scalar_series(label: str, value: int | float) -> list[dict]:
    return [{"name": label, "data": [[label, value]]}]


def _ensure_sources_for_charts(
    envelope: AnswerEnvelope,
    usable: list[dict],
    scalars: list[dict[str, Any]],
) -> list[EnvelopeSource]:
    if envelope.sources:
        return list(envelope.sources)
    sources: list[EnvelopeSource] = []
    seen: set[str] = set()
    for s in scalars:
        tool = s.get("tool") or "unknown"
        if tool in seen:
            continue
        seen.add(tool)
        sources.append(EnvelopeSource(
            tool=tool,
            rows_returned=1,
            truncated=False,
        ))
    if sources:
        return sources
    for tr in usable or []:
        name = tr.get("tool_name") or "unknown"
        if name in seen:
            continue
        seen.add(name)
        data = _unwrap_tool_payload(tr.get("result"))
        rows = 0
        if isinstance(data, dict):
            if isinstance(data.get("total"), (int, float)):
                rows = int(data["total"])
            elif isinstance(data.get("value"), (int, float)):
                rows = 1
        sources.append(EnvelopeSource(tool=name, rows_returned=rows, truncated=False))
    return sources


def _is_dump_table(table) -> bool:
    """True when a table is a sample payslip / employee-row dump."""
    title = str(getattr(table, "title", None) or "").strip()
    if _DUMP_TABLE_TITLE_RE.search(title):
        return True
    cols = [
        str(c).strip().lower()
        for c in (getattr(table, "columns", None) or [])
    ]
    if not cols:
        return False
    hits = sum(1 for c in cols if c in _DUMP_COL_MARKERS)
    # Employee identity + pay columns → row dump, not an aggregate summary.
    has_identity = any(
        c in {"employee name", "employee no", "employee number", "emp no"}
        for c in cols
    )
    has_pay = any(c in {"gross", "net", "gosi", "gosi/pifss", "pifss"} for c in cols)
    return has_identity and has_pay and hits >= 3


def sanitize_envelope_tables(envelope: AnswerEnvelope) -> AnswerEnvelope:
    """Drop sample payslip / employee-row dump tables from the envelope."""
    tables = list(envelope.tables or [])
    kept = [t for t in tables if not _is_dump_table(t)]
    if kept == tables:
        return envelope
    return envelope.model_copy(update={"tables": kept})


def _chart_from_breakdown(data: dict[str, Any]) -> EnvelopeChart | None:
    """Build one multi-bucket chart from an analyze_* / breakdown payload."""
    breakdown = data.get("breakdown")
    if not isinstance(breakdown, list) or len(breakdown) < 2:
        return None
    points: list[list] = []
    for b in breakdown[:12]:
        if not isinstance(b, dict):
            continue
        label = str(b.get("label") or b.get("name") or "").strip() or "-"
        raw = b.get("count", b.get("value", b.get("pct")))
        try:
            val = float(raw) if raw is not None else 0.0
        except (TypeError, ValueError):
            continue
        if val <= 0:
            continue
        points.append([label[:48], int(val) if float(val).is_integer() else val])
    if len(points) < 2:
        return None
    chart_type = str(data.get("suggested_chart_type") or "bar").lower()
    if chart_type not in ("bar", "pie", "line"):
        chart_type = "bar"
    if chart_type == "pie" and len(points) > 8:
        chart_type = "bar"
    dim = str(data.get("dimension") or "").strip()
    title = _humanize_metric(dim) if dim else "Distribution"
    return EnvelopeChart(
        chart_type=chart_type,  # type: ignore[arg-type]
        title=title[:80],
        series=[{"name": title[:40], "data": points}],
    )


def _charts_from_tool_breakdowns(usable: list[dict]) -> list[EnvelopeChart]:
    """Deterministic charts when the LLM omitted multi-bucket series."""
    out: list[EnvelopeChart] = []
    seen: set[str] = set()
    for tr in usable or []:
        data = _unwrap_tool_payload(tr.get("result"))
        if not isinstance(data, dict):
            continue
        # Nested host shape: {data: {breakdown: ...}}
        if "breakdown" not in data and isinstance(data.get("data"), dict):
            inner = data["data"]
            if "breakdown" in inner:
                data = inner
        chart = _chart_from_breakdown(data)
        if chart is None:
            continue
        key = f"{chart.title}:{_series_point_count(chart.series)}"
        if key in seen:
            continue
        seen.add(key)
        out.append(chart)
        if len(out) >= 3:
            break
    return out


def enrich_envelope_charts(
    envelope: AnswerEnvelope,
    usable_tools: list[dict] | None,
) -> AnswerEnvelope:
    """Keep multi-bucket charts; inject from tool breakdowns when missing.

    A lone ``Total active employees = 555`` bar wastes a viewport and looks
    broken. Prose already carries the scalar — charts need ≥2 categories.
    Empty series are omitted (never ship a titled "No data" shell).
    When the LLM ships tables but no charts while ``analyze_*`` returned a
    multi-bucket breakdown, inject those charts so "with charts" is honest.
    """
    usable = list(usable_tools or [])
    filled: list[EnvelopeChart] = []
    for chart in envelope.charts or []:
        n = _series_point_count(chart.series)
        if n >= 2:
            filled.append(chart)
            # else: 0 or 1 point → omit

    if not filled:
        filled = _charts_from_tool_breakdowns(usable)

    original = list(envelope.charts or [])
    if filled == original:
        return envelope

    sources = list(envelope.sources or [])
    if filled and not sources:
        scalars = _extract_scalar_metrics(usable)
        sources = _ensure_sources_for_charts(envelope, usable, scalars)

    return envelope.model_copy(update={"charts": filled, "sources": sources})



def _filter_usable(tools: list[dict] | None) -> list[dict]:
    """Keep only tool results that are usable data (mirrors the runner filter)."""
    usable: list[dict] = []
    for tr in tools or []:
        if tr.get("error"):
            continue
        if tr.get("requires_confirmation"):
            continue
        if tr.get("result") is None:
            continue
        if payload_status(tr.get("result")) == "no_match":
            continue
        usable.append(tr)
    return usable


def _render_tool_results(completed_tools: list[dict], max_chars: int = 20000) -> str:
    """Render tool results as JSON for the envelope synthesis prompt.

    Mirrors ``_render_tool_results_for_synthesis`` (unwraps the host envelope
    ``{"status_code": ..., "data": ...}``) so the model sees ``total``,
    ``truncated``, ``caveats``, and ``suggested_chart_type`` for its sources
    and charts.
    """
    sections: list[str] = []
    used = 0
    for tr in completed_tools:
        name = tr.get("tool_name", "unknown")
        raw = tr.get("result")

        data = raw
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except (TypeError, ValueError):
                data = raw

        # Unwrap the host executor envelope.
        if isinstance(data, dict) and "status_code" in data and "data" in data:
            data = data["data"]

        header = f"### {name}\n"
        body = json.dumps(data, ensure_ascii=False, indent=2, default=str)

        section = header + body
        if used + len(section) > max_chars:
            remaining = max_chars - used
            section = section[:remaining] + "\n…(truncated)"
        sections.append(section)
        used += len(section)
        if used >= max_chars:
            break

    return "\n\n".join(sections)


# ── Deterministic typed blocks (host rows → tables/charts) ─────────────────


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().replace(",", "").replace("%", "")
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _salary_bands(values: list[float]) -> list[list[str | int]]:
    """Bucket gross amounts into operator-readable salary bands."""
    bands = (
        ("≤500", 0, 500),
        ("501–1k", 500, 1000),
        ("1k–2k", 1000, 2000),
        ("2k–5k", 2000, 5000),
        ("5k+", 5000, float("inf")),
    )
    rows: list[list[str | int]] = []
    for label, low, high in bands:
        count = sum(
            1 for value in values
            if (value <= high if low == 0 else low < value <= high)
        )
        if count:
            rows.append([label, count])
    return rows


#: Keys that identify a record rather than describe a category, and keys whose
#: numbers are identifiers/timestamps. Neither can become a chart axis.
_NON_LABEL_KEY_RE = re.compile(
    r"(?:^|_)(?:id|pk|uuid|code|no|number|url|slug|created|updated|date|"
    r"datetime|timestamp|from|to|start|end|period|month|year|status)(?:_|$)",
    re.IGNORECASE,
)
_NON_VALUE_KEY_RE = re.compile(
    r"(?:^|_)(?:id|pk|uuid|no|number|year|month|day|version|order|index|"
    r"sequence|seq)(?:_|$)",
    re.IGNORECASE,
)
#: Display titles for well-known series shapes. Presentation only — never a
#: routing decision. An unknown label key is humanized from its own name, so a
#: new catalog endpoint charts without touching this module.
_SERIES_TITLES = {
    "leave_type": "Leave balance",
    "leave_type_label": "Leave balance",
    "line_type": "Payslip lines",
    "category": "Breakdown",
}


def _label_text(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("label", "name", "code", "title"):
            if value.get(key) not in (None, ""):
                return str(value[key]).strip()
        return ""
    return str(value or "").strip()


def _series_keys(rows: list[dict]) -> tuple[str, str] | None:
    """Find the (category, measure) pair in host rows by shape, not by name.

    A chartable series needs one key whose values read as distinct category
    labels and one key whose values are measures. Identifier / date / status
    columns are excluded because they are neither. Works for any endpoint that
    returns rows in this shape — no per-topic key list to maintain.
    """
    keys = [str(k) for k in rows[0]]
    label_key = None
    for key in keys:
        if _NON_LABEL_KEY_RE.search(key):
            continue
        texts = [_label_text(row.get(key)) for row in rows]
        if any(not t for t in texts):
            continue
        if any(_numeric(row.get(key)) is not None for row in rows):
            continue  # a number is a measure, not a category
        if len({t.casefold() for t in texts}) < 2:
            continue  # one repeated label is not a breakdown
        label_key = key
        break
    if label_key is None:
        return None
    candidates: list[str] = []
    for key in keys:
        if key == label_key or _NON_VALUE_KEY_RE.search(key):
            continue
        values = [_numeric(row.get(key)) for row in rows]
        if all(v is not None for v in values) and any(v > 0 for v in values):
            candidates.append(key)
    if not candidates:
        return None
    # A column with the same number in every row draws a flat chart and answers
    # nothing. Prefer a measure that varies; fall back to the first candidate.
    value_key = next(
        (
            key for key in candidates
            if len({_numeric(row.get(key)) for row in rows}) > 1
        ),
        candidates[0],
    )
    return label_key, value_key


def labeled_numeric_points(rows: list[dict]) -> tuple[str, list[list]] | None:
    """Chart points from any host rows shaped as category → measure.

    Needs two or more positive values. Employee-by-employee dumps are not a
    chart: those aggregate into salary bands instead.
    """
    if len(rows) < 2 or not isinstance(rows[0], dict):
        return None
    names = {
        _label_text(row.get(key))
        for row in rows
        for key in _PERSON_KEYS
        if _label_text(row.get(key))
    }
    if len(names) > 1:
        return None
    keys = _series_keys(rows)
    if keys is None:
        return None
    label_key, value_key = keys
    points: list[list] = []
    for row in rows[:12]:
        label = _label_text(row.get(label_key))[:48]
        value = _numeric(row.get(value_key))
        if not label or value is None or value <= 0:
            continue
        points.append([label, int(value) if value.is_integer() else value])
    if len(points) < 2:
        return None
    title = _SERIES_TITLES.get(label_key) or _humanize_metric(label_key)
    return title, points


_PERSON_KEYS = ("employee_id", "employee_no", "employee_name", "employee")


def _gross_per_person(rows: list[dict]) -> list[float]:
    """One gross value per distinct employee; rows without an identity don't count.

    An "Employees" axis is a head count. A single person's payslip lines or
    months carry no second identity, so they can never become salary bands.
    """
    seen: dict[str, float] = {}
    for row in rows:
        person = next(
            (_label_text(row.get(key)) for key in _PERSON_KEYS if _label_text(row.get(key))),
            "",
        )
        value = _numeric(row.get("gross", row.get("amount")))
        if not person or person in seen or value is None or value < 0:
            continue
        seen[person] = value
    return list(seen.values()) if len(seen) >= 2 else []


def _payload_rows(data: dict) -> list[dict]:
    for key in ("results", "rows", "items"):
        rows = data.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def deterministic_envelope_blocks(
    usable_tools: list[dict] | None,
    *,
    user_message: str = "",
) -> dict[str, list]:
    """Build tables/charts/caveats/sources directly from typed tool data.

    The LLM may write headline/prose, but it never owns numeric data blocks.
    Employee-level payslip rows are aggregated into salary bands; identities
    are never copied into the envelope.
    """
    tables: list[EnvelopeTable] = []
    charts: list[EnvelopeChart] = []
    caveats: list[EnvelopeCaveat] = []
    sources: list[EnvelopeSource] = []
    seen_source: set[str] = set()

    for tr in usable_tools or []:
        tool = str(tr.get("tool_name") or "unknown")
        data = _unwrap_tool_payload(tr.get("result"))
        if isinstance(data, list):
            data = {"results": [row for row in data if isinstance(row, dict)]}
        if not isinstance(data, dict) or data.get("error") or data.get("unauthorized"):
            continue
        if "breakdown" not in data and isinstance(data.get("data"), dict):
            inner = data["data"]
            if "breakdown" in inner or _payload_rows(inner):
                data = inner

        source_rows = 0
        truncated = bool(data.get("truncated"))
        breakdown = data.get("breakdown")
        if isinstance(breakdown, list) and breakdown:
            rows: list[list[str | int | float]] = []
            for item in breakdown:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("label") or item.get("name") or "-")
                value = _numeric(item.get("count", item.get("value")))
                if value is None:
                    continue
                row: list[str | int | float] = [
                    label,
                    int(value) if value.is_integer() else value,
                ]
                pct = _numeric(item.get("pct", item.get("percentage")))
                if pct is not None:
                    row.append(f"{pct:g}%")
                rows.append(row)
            if len(rows) >= 2:
                dim = _humanize_metric(str(data.get("dimension") or "distribution"))
                columns = ["Category", "Count"]
                if any(len(row) == 3 for row in rows):
                    columns.append("Percentage")
                    rows = [row if len(row) == 3 else [*row, ""] for row in rows]
                tables.append(EnvelopeTable(title=dim, columns=columns, rows=rows))
                chart = _chart_from_breakdown(data)
                if chart is not None:
                    charts.append(chart)
                source_rows = len(rows)

        raw_rows = _payload_rows(data)
        if raw_rows and all("status" in r for r in raw_rows):
            counts: dict[str, int] = {}
            for row in raw_rows:
                status = str(row.get("status") or "Unknown").strip().title()
                counts[status] = counts.get(status, 0) + 1
            status_rows = [[key, value] for key, value in sorted(counts.items())]
            if len(status_rows) >= 2:
                tables.append(EnvelopeTable(
                    title="Payroll Run Status",
                    columns=["Status", "Count"],
                    rows=status_rows,
                ))
                charts.append(EnvelopeChart(
                    chart_type="bar",
                    title="Payroll Run Status",
                    series=[{"name": "Runs", "data": status_rows}],
                ))
                source_rows = len(raw_rows)

        if raw_rows and any("gross" in row or "net" in row for row in raw_rows):
            band_rows = _salary_bands(_gross_per_person(raw_rows))
            if len(band_rows) >= 2:
                tables.append(EnvelopeTable(
                    title="Gross Pay Distribution",
                    columns=["Salary band", "Employees"],
                    rows=band_rows,
                ))
                charts.append(EnvelopeChart(
                    chart_type="bar",
                    title="Gross Pay Distribution",
                    series=[{"name": "Employees", "data": band_rows}],
                ))
                source_rows = len(raw_rows)

        # Any category → measure series charts on shape alone, exactly like a
        # ``breakdown`` payload does. No topic, endpoint name, or "did they say
        # chart?" test: a new endpoint that returns this shape charts for free.
        if raw_rows and source_rows == 0:
            labeled = labeled_numeric_points(raw_rows)
            if labeled is not None:
                title, points = labeled
                tables.append(EnvelopeTable(
                    title=title,
                    columns=["Category", "Value"],
                    rows=points,
                ))
                charts.append(EnvelopeChart(
                    chart_type="bar",
                    title=title,
                    series=[{"name": title, "data": points}],
                ))
                source_rows = len(raw_rows)

        for raw_caveat in data.get("caveats") or []:
            if not isinstance(raw_caveat, dict):
                continue
            text = str(
                raw_caveat.get("text") or raw_caveat.get("message") or ""
            ).strip()
            level = str(raw_caveat.get("level") or "warning").lower()
            if text:
                caveats.append(EnvelopeCaveat(
                    level=level if level in {"info", "warning", "critical"} else "warning",
                    text=text,
                ))
        if truncated and not any("truncat" in c.text.lower() for c in caveats):
            caveats.append(EnvelopeCaveat(
                level="critical",
                text="The source result was truncated; totals may exceed returned rows.",
            ))

        if source_rows and tool not in seen_source:
            seen_source.add(tool)
            sources.append(EnvelopeSource(
                tool=tool,
                rows_returned=source_rows,
                truncated=truncated,
            ))

    return {
        "tables": tables,
        "charts": charts,
        "caveats": caveats,
        "sources": sources,
    }


def ground_envelope_blocks(
    envelope: AnswerEnvelope,
    usable_tools: list[dict] | None,
    *,
    user_message: str = "",
) -> AnswerEnvelope:
    """Replace LLM-authored data blocks when deterministic blocks exist."""
    blocks = deterministic_envelope_blocks(
        usable_tools, user_message=user_message,
    )
    if not (blocks["tables"] or blocks["charts"]):
        return sanitize_envelope_tables(envelope)
    return envelope.model_copy(update=blocks)
