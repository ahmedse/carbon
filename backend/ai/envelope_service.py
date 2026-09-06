"""Envelope synthesis service — the structured-output path for AI answers.

``synthesize_envelope`` asks the LLM (JSON mode) to emit a typed
:class:`AnswerEnvelope` from executed tool results. It is independent of the
markdown path and fails open: any exception returns ``None`` so the caller can
fall back to the existing markdown synthesis unchanged.
"""
from __future__ import annotations

import json
import logging

from ai.envelope import AnswerEnvelope, envelope_from_json
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
        return envelope_from_json(content)
    except ValueError:
        logger.warning("Envelope synthesis returned invalid JSON/schema", exc_info=True)
        return None


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
