"""Envelope synthesis service — the structured-output path for AI answers.

``synthesize_envelope`` asks the LLM (JSON mode) to emit a typed
:class:`AnswerEnvelope` from executed tool results. It is independent of the
markdown path and fails open: any exception returns ``None`` so the caller can
fall back to the existing markdown synthesis unchanged.

After the LLM returns, :func:`enrich_envelope_charts` deterministically fills
(or drops) single-metric charts so a scalar tool result (e.g. aggregate
headcount ``value: 530``) never ships as a titled chart with an empty series.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ai.envelope import AnswerEnvelope, EnvelopeChart, EnvelopeSource, envelope_from_json
from ai.envelope_prompt import build_envelope_system_prompt
from ai.engine.core.resolution import payload_status

logger = logging.getLogger("pulse.envelope")


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
        return enrich_envelope_charts(envelope, usable)
    except Exception:
        logger.warning("Envelope chart enrichment failed; returning raw envelope", exc_info=True)
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


def enrich_envelope_charts(
    envelope: AnswerEnvelope,
    usable_tools: list[dict] | None,
) -> AnswerEnvelope:
    """Fill empty single-metric charts from tool scalars; drop still-empty charts.

    The LLM often emits ``{title: "Active Employee Count", series: []}`` for an
    ``aggregate_entity`` headcount. That ships as a titled "No data" shell on
    the frontend even when prose correctly states 530. This pass:

    1. Fills empty/malformed chart series from scalar tool results.
    2. Synthesises one bar chart when the envelope has no charts but a scalar
       exists (so chart and prose agree).
    3. Omits charts that still have zero renderable points.
    """
    usable = list(usable_tools or [])
    scalars = _extract_scalar_metrics(usable)
    scalar_queue = list(scalars)

    filled: list[EnvelopeChart] = []
    for chart in envelope.charts or []:
        if _series_point_count(chart.series) > 0:
            filled.append(chart)
            continue
        if not scalar_queue:
            # Empty series + no scalar to fill → omit (never ship title-only).
            continue
        s = scalar_queue.pop(0)
        title = (chart.title or "").strip() or s["label"]
        filled.append(
            chart.model_copy(update={
                "title": title,
                "series": _scalar_series(s["label"], s["value"]),
                "chart_type": chart.chart_type if chart.chart_type in ("bar", "pie", "line") else "bar",
            })
        )

    # No charts at all, but we have a scalar total → synthesise one bar chart.
    if not filled and scalars:
        s = scalars[0]
        filled.append(EnvelopeChart(
            chart_type="bar",
            title=s["label"],
            series=_scalar_series(s["label"], s["value"]),
        ))

    if filled == list(envelope.charts or []):
        return envelope

    sources = list(envelope.sources or [])
    if filled and not sources:
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
