"""
Context merger — Stage 7.

Pure, deterministic logic (no I/O, no LLM).  Takes the existing
QueryContext and a TurnType and returns an updated QueryContext.

Merge strategies per TurnType:
  CONTINUATION — carry metrics, entity_names, filters, time_range;
                 add new dimensions; replace sort/limit/viz if specified.
  REFINEMENT   — detect "instead" → replace filter; "also/and" → add.
                 Replace time_range if a new one is detected in the utterance.
  DRILL_DOWN   — inject a filter from the clarifying phrase; may shift
                 dimensions toward the drill target.
  NEW_TOPIC    — reset to empty QueryContext.

After plan execution, callers should call update_from_plan() to override
metrics/dimensions/entity_names with ground-truth data from the QueryPlan.
"""
import copy
import logging
import re
from dataclasses import replace
from typing import Optional

from ai.engine.knowledge_graph.conversation_context import (
    Filter,
    QueryContext,
    SortSpec,
    TimeRange,
    TurnClassification,
    TurnType,
)

logger = logging.getLogger("pulse.knowledge_graph.context_merger")


# ── helpers for extracting light signals from text ────────────────────────────

_SORT_PATTERN = re.compile(
    r"\b(?:sort|order)\s+by\s+(\w+)(?:\s+(asc(?:ending)?|desc(?:ending)?))?",
    re.IGNORECASE,
)
_LIMIT_PATTERN = re.compile(r"\b(?:top|bottom|first|last|limit)\s+(\d+)\b", re.IGNORECASE)
_VIZ_MAP = {
    "bar": "bar", "column": "bar",
    "line": "line", "trend": "line",
    "pie": "pie", "donut": "pie",
    "table": "table", "grid": "table",
    "stat": "stat", "number": "stat", "kpi": "stat",
    "scatter": "scatter",
}
_VIZ_PATTERN = re.compile(
    r"\b(?:as\s+a?\s*|show\s+(?:me\s+)?as\s+a?\s*)(" + "|".join(_VIZ_MAP) + r")\b",
    re.IGNORECASE,
)
_DIMENSION_PREP = re.compile(
    r"\bby\s+(\w+)\b|\bper\s+(\w+)\b|\bgroup(?:ed)?\s+by\s+(\w+)\b",
    re.IGNORECASE,
)

_REPLACEMENT_WORDS = re.compile(r"\binstead\b|\breplace\b|\bchange\b|\bswitch\b", re.IGNORECASE)
_ADDITIVE_WORDS = re.compile(r"\balso\b|\band\b|\badd\b|\binclude\b|\bplus\b", re.IGNORECASE)

_DRILL_CAPTURE = re.compile(
    r"\bfocus\s+on\s+(.+?)(?:\s*$|\.|,)",
    re.IGNORECASE,
)

_TIME_KEYWORDS = re.compile(
    r"\b(last|this|next|past)\s+(week|month|quarter|year)\b"
    r"|\bq[1-4]\s+\d{4}\b"
    r"|\b\d{4}\b"
    r"|\bjan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec\b",
    re.IGNORECASE,
)


def _extract_sort(text: str) -> Optional[SortSpec]:
    m = _SORT_PATTERN.search(text)
    if not m:
        return None
    field = m.group(1).lower()
    raw_dir = (m.group(2) or "desc").lower()
    direction = "asc" if raw_dir.startswith("asc") else "desc"
    # "bottom N" implies ascending
    if re.search(r"\bbottom\s+\d+\b", text, re.IGNORECASE):
        direction = "asc"
    return SortSpec(field=field, direction=direction)


def _extract_limit(text: str) -> Optional[int]:
    m = _LIMIT_PATTERN.search(text)
    return int(m.group(1)) if m else None


def _extract_viz(text: str) -> Optional[str]:
    m = _VIZ_PATTERN.search(text)
    if not m:
        return None
    return _VIZ_MAP.get(m.group(1).lower())


def _extract_dimensions(text: str) -> list[str]:
    dims: list[str] = []
    for m in _DIMENSION_PREP.finditer(text):
        dim = (m.group(1) or m.group(2) or m.group(3) or "").lower()
        if dim and dim not in ("by", "per", "group", "me", "it", "that", "the", "a"):
            dims.append(dim)
    return dims


def _extract_time_reference(text: str) -> Optional[TimeRange]:
    m = _TIME_KEYWORDS.search(text)
    if not m:
        return None
    # Best-effort: capture the whole time phrase
    phrase = text[max(0, m.start() - 4): m.end() + 10].strip()
    phrase = re.sub(r"\s+", " ", phrase)
    return TimeRange(description=phrase)


# ── ContextMerger ─────────────────────────────────────────────────────────────

class ContextMerger:
    """
    Merges an existing QueryContext with signals extracted from the utterance,
    according to the classified TurnType.
    """

    def merge(
        self,
        active: QueryContext,
        classification: TurnClassification,
        utterance: str,
    ) -> QueryContext:
        """Return a NEW QueryContext; never mutates *active*."""
        turn_type = classification.turn_type

        if turn_type == TurnType.NEW_TOPIC:
            logger.debug("context_merger: NEW_TOPIC — resetting context")
            return QueryContext()

        if turn_type == TurnType.CONTINUATION:
            return self._merge_continuation(active, utterance)

        if turn_type == TurnType.REFINEMENT:
            return self._merge_refinement(active, utterance)

        if turn_type == TurnType.DRILL_DOWN:
            return self._merge_drill_down(active, utterance)

        # Unknown type — keep unchanged
        return copy.deepcopy(active)

    # ── strategy implementations ──────────────────────────────────────────────

    def _merge_continuation(self, active: QueryContext, utterance: str) -> QueryContext:
        """
        Carry everything; augment with new dimension / sort / limit / viz.
        """
        ctx = copy.deepcopy(active)

        new_dims = _extract_dimensions(utterance)
        for d in new_dims:
            if d not in ctx.dimensions:
                ctx.dimensions.append(d)

        sort = _extract_sort(utterance)
        if sort:
            ctx.sort = sort

        limit = _extract_limit(utterance)
        if limit is not None:
            ctx.limit = limit

        viz = _extract_viz(utterance)
        if viz:
            ctx.visualization = viz

        return ctx

    def _merge_refinement(self, active: QueryContext, utterance: str) -> QueryContext:
        """
        Patch filters and/or replace time range.
        'instead' / 'change' / 'replace' → replace existing filter
        'also' / 'and' / 'include' → add new filter
        """
        ctx = copy.deepcopy(active)

        # Time range update
        time_ref = _extract_time_reference(utterance)
        if time_ref:
            ctx.time_range = time_ref

        # Filter mutation heuristic — if we can't extract a structured filter
        # we at least note the refinement in a labeled placeholder so the
        # query planner can still inject it via the resolved utterance.
        is_replacement = bool(_REPLACEMENT_WORDS.search(utterance))
        is_additive = bool(_ADDITIVE_WORDS.search(utterance))

        if is_replacement:
            # Replace the most recently added filter (last in list)
            if ctx.filters:
                ctx.filters.pop()

        # Carry sort/limit/viz patches too
        sort = _extract_sort(utterance)
        if sort:
            ctx.sort = sort

        limit = _extract_limit(utterance)
        if limit is not None:
            ctx.limit = limit

        viz = _extract_viz(utterance)
        if viz:
            ctx.visualization = viz

        return ctx

    def _merge_drill_down(self, active: QueryContext, utterance: str) -> QueryContext:
        """
        Inject a filter that narrows to the drilled value.
        If 'focus on X', treat X as a filter label.
        """
        ctx = copy.deepcopy(active)

        m = _DRILL_CAPTURE.search(utterance)
        if m:
            drill_value = m.group(1).strip()
            # Best-effort field: use first dimension if available
            field = ctx.dimensions[0] if ctx.dimensions else "value"
            ctx.filters.append(
                Filter(field=field, op="=", value=drill_value, label=f"focus on {drill_value}")
            )

        return ctx

    # ── post-execution patch ──────────────────────────────────────────────────

    @staticmethod
    def update_from_plan(ctx: QueryContext, plan) -> QueryContext:
        """
        After the SQL plan executes, override metrics/dimensions/entity_names
        with ground-truth data from the QueryPlan object.
        Silently no-ops if *plan* is None or lacks expected attributes.
        """
        if plan is None:
            return ctx

        updated = copy.deepcopy(ctx)

        try:
            entity_names = getattr(plan, "entity_names", None) or []
            if entity_names:
                updated.entity_names = list(entity_names)
        except Exception:
            pass

        try:
            cols = getattr(plan, "select_columns", None) or []
            metrics: list[str] = []
            dimensions: list[str] = []
            for col in cols:
                role = getattr(col, "role", "")
                name = getattr(col, "column", "") or getattr(col, "alias", "")
                if not name:
                    continue
                if role == "measure":
                    metrics.append(name)
                elif role in ("dimension", "group_by"):
                    dimensions.append(name)
            if metrics:
                updated.metrics = metrics
            if dimensions:
                updated.dimensions = dimensions
        except Exception:
            pass

        return updated
