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

from ai.envelope import AnswerEnvelope, EnvelopeChart, EnvelopeSource, envelope_from_json
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
        return None

    content = (result.get("content") or "").strip()
    if not content:
        return None
    try:
        envelope = envelope_from_json(content)
    except ValueError:
        logger.warning("Envelope synthesis returned invalid JSON/schema", exc_info=True)
        return None

    try:
        envelope = enrich_envelope_charts(envelope, usable)
        return sanitize_envelope_tables(envelope)
    except Exception:
        logger.warning("Envelope enrichment failed; returning raw envelope", exc_info=True)
        return envelope


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
