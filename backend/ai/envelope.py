"""Typed Answer Envelope — the structured-output contract for AI answers.

PAQ-2A: the AI emits a validated :class:`AnswerEnvelope` — typed blocks
(``tables`` / ``charts`` / ``caveats`` / ``sources``) — so the frontend can
render deterministically from data instead of reflowing free-form markdown.
Markdown survives ONLY inside ``headline`` and ``prose[]``.

This module is contract-first and side-effect-free: the pydantic models,
:func:`envelope_from_json`, and :func:`envelope_json_schema` perform no I/O and
have no LLM dependency, so they are unit-testable without a live model.
"""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

#: Markdown markers forbidden inside typed table cells. Typed data must be
#: machine-renderable; markdown belongs only in ``headline`` / ``prose``.
_MARKDOWN_CONTAINED = ("`", "**", "|")
#: A cell may not *lead* with a markdown heading.
_HEADING_PREFIX = "#"

_FENCE_OPEN_RE = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
_FENCE_CLOSE_RE = re.compile(r"\s*```\s*$")


def _cell_has_raw_markdown(cell: object) -> bool:
    """True when a table cell carries raw markdown (forbidden in typed data)."""
    if not isinstance(cell, str):
        return False
    if cell.startswith(_HEADING_PREFIX):
        return True
    return any(marker in cell for marker in _MARKDOWN_CONTAINED)


class EnvelopeTable(BaseModel):
    """A typed table block: named columns plus rectangular typed rows."""

    title: str
    columns: list[str]
    rows: list[list[str | int | float]]

    @field_validator("columns")
    @classmethod
    def _columns_non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("columns must be non-empty")
        return v

    @model_validator(mode="after")
    def _validate_rows(self) -> "EnvelopeTable":
        width = len(self.columns)
        for i, row in enumerate(self.rows):
            if len(row) != width:
                raise ValueError(
                    f"row {i} has {len(row)} cell(s) but the table has {width} column(s)"
                )
            for j, cell in enumerate(row):
                if _cell_has_raw_markdown(cell):
                    raise ValueError(
                        f"cell ({i},{j}) contains raw markdown: {cell!r}"
                    )
        return self


class EnvelopeChart(BaseModel):
    """A typed chart block. ``chart_type`` is restricted to renderable kinds."""

    chart_type: Literal["bar", "pie", "line"]
    title: str
    series: list[dict]


class EnvelopeCaveat(BaseModel):
    """A machine-computed disclosure (missing data, truncation, normalization)."""

    level: Literal["info", "warning", "critical"]
    text: str

    @model_validator(mode="before")
    @classmethod
    def _accept_message_alias(cls, data):
        """Tolerate ``message`` as an alias for ``text``.

        The host tool results carry caveats as ``{level, message}`` and the
        envelope LLM occasionally copies ``message`` verbatim instead of the
        contract key ``text``. Normalize it here so a trivial key-name drift
        never silently discards the whole envelope (which would fall back to
        an ungrounded draft).
        """
        if isinstance(data, dict) and "text" not in data and "message" in data:
            data = {**data, "text": data.pop("message")}
        return data


class EnvelopeSource(BaseModel):
    """Provenance for one tool whose data grounded the answer."""

    tool: str
    rows_returned: int
    truncated: bool = False
    resolved_at: str | None = None


class AnswerEnvelope(BaseModel):
    """The typed answer contract: prose + typed data blocks + provenance."""

    headline: str
    prose: list[str]
    tables: list[EnvelopeTable] = Field(default_factory=list)
    charts: list[EnvelopeChart] = Field(default_factory=list)
    caveats: list[EnvelopeCaveat] = Field(default_factory=list)
    sources: list[EnvelopeSource] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sources_required_for_data(self) -> "AnswerEnvelope":
        if (self.tables or self.charts) and not self.sources:
            raise ValueError(
                "sources is mandatory when tables or charts are present"
            )
        return self


def _strip_json_fences(raw: str) -> str:
    """Remove a leading/trailing ```json fence (and surrounding whitespace)."""
    text = (raw or "").strip()
    text = _FENCE_OPEN_RE.sub("", text)
    text = _FENCE_CLOSE_RE.sub("", text)
    return text.strip()


def envelope_from_json(raw: str) -> AnswerEnvelope:
    """Parse an envelope from (possibly fenced) JSON.

    Raises :class:`ValueError` on any parse or validation failure — never
    silently swallows a malformed envelope.
    """
    text = _strip_json_fences(raw)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"envelope JSON parse failed: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("envelope JSON must be a JSON object")
    return AnswerEnvelope.model_validate(data)


def envelope_json_schema() -> dict:
    """Return the JSON Schema for :class:`AnswerEnvelope` (structured-output prompt)."""
    return AnswerEnvelope.model_json_schema()
