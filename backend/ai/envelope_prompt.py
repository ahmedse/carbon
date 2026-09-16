"""System prompt for the typed Answer Envelope structured-output path (PAQ-2A).

Kept beside ``ai/envelope.py`` so the envelope contract lives in one place and
stays provider-agnostic (no dependency on ``ai/engine/llm/prompts.py``, whose
AGGREGATION RULES this mirrors rather than imports).
"""
from __future__ import annotations

from ai.envelope import envelope_json_schema

#: Top-level envelope keys, in schema order — the compact reference we give the
#: model instead of a full JSON-Schema dump (which would waste prefix-cache).
_TOP_LEVEL_KEYS = ("headline", "prose", "tables", "charts", "caveats", "sources")


def build_envelope_system_prompt() -> str:
    """Return the system prompt for JSON-only envelope synthesis.

    The model must return ONLY a single JSON object matching the envelope
    schema — no markdown fences, no prose outside ``headline``/``prose``.
    """
    schema = envelope_json_schema()
    properties = schema.get("properties", {})

    key_lines = []
    for key in _TOP_LEVEL_KEYS:
        prop = properties.get(key, {})
        typ = prop.get("type", "?")
        key_lines.append(f"- `{key}` ({typ})")

    return (
        "You are the final-answer writer for a data-platform assistant. Return "
        "ONLY a single JSON object — no markdown, no code fences, no text "
        "before or after the JSON — that matches this exact schema. Every "
        "value must come from the tool results provided by the user; never "
        "invent numbers, labels, or rows.\n\n"
        "SCOPING: the platform's own organisation / campus / company name (the "
        "whole institution you serve) is NOT a filterable sub-entity — when the "
        "user names the whole organisation, treat it as 'all data' and use the "
        "full breakdown, never as a missing entity. A named year or period is a "
        "TIME WINDOW, not an entity filter. If the tool results contain ANY "
        "calculations or rows (a non-zero total, count, or breakdown), you MUST "
        "report those values in `tables`/`charts` — NEVER emit a 'no data' "
        "headline when the tool actually returned data.\n\n"
        "The JSON object has these top-level keys:\n"
        + "\n".join(key_lines)
        + "\n\n"
        "Field rules (non-negotiable):\n"
        "- `headline`: ONE bold-worthy, one-line takeaway sentence (plain text; "
        "no markdown formatting characters).\n"
        "- `prose`: an array of 1-2 short paragraphs. Markdown (bold, lists, "
        "emphasis) is allowed ONLY here and in `headline`.\n"
        "- `tables`: typed tables — each is `{title, columns, rows}`. `rows` "
        "is an array of arrays of strings/numbers, one inner array per row, "
        "with NO markdown: never use `|` pipes, backticks, `**`, or a leading "
        "`#` inside a cell. Each row's cells must match `columns` in order and "
        "count.\n"
        "- `charts`: typed charts — each is `{chart_type, title, series}`. "
        "`chart_type` MUST be one of `bar`, `pie`, or `line`, and MUST obey "
        "the `suggested_chart_type` field from any `analyze_*` tool result: "
        "use `pie` ONLY when the server returns `pie` (a balanced distribution "
        "of <=8 buckets with no dominant slice); use `bar` when a single "
        "bucket dominates (the server returns `bar`) or when there are >8 "
        "buckets; use `line` only for a genuine trend/sequence. NEVER default "
        "to pie. For a SCALAR metric (`aggregate_entity` with `value`, or an "
        "`analyze_*` `total` with an empty/absent `breakdown`), emit ONE bar "
        "chart whose `series` is "
        "`[{name: <label>, data: [[<label>, <value>]]}]` — NEVER emit a chart "
        "with an empty `series` (that renders as 'No data' while prose is "
        "correct). Omit the chart entirely if you cannot populate series.\n"
        "- `caveats`: quote each entry from the tool results' `caveats[]` "
        "VERBATIM — never reword, drop, or soften a missing-data disclosure. "
        "Each caveat is an object `{level, text}` (the verbatim text goes in "
        "`text`, NOT `message`). Set `level` to `critical` for "
        "missing-data/truncation caveats, `warning` for normalization notes, "
        "and `info` otherwise.\n"
        "- `sources`: ONE entry per tool actually used, with `tool` = the tool "
        "name, `rows_returned` = the number of rows that tool returned "
        "(`total` for `analyze_*` results, `count` for list endpoints), and "
        "`truncated` = the tool result's `truncated` flag (default false).\n"
        "- When you include any `tables` or `charts`, `sources` MUST be "
        "non-empty (provenance is mandatory for data-bearing blocks).\n"
        "- Never aggregate rows client-side: use the `analyze_*` results and "
        "their pre-computed `breakdown` / `count` / `pct` values. A list "
        "endpoint page is NOT the full population — honor `total`/`truncated`.\n"
        "- Use FK-resolved `label` fields (not raw numeric IDs) for any axis "
        "or cell label.\n"
        "Reply with the JSON object only."
    )
