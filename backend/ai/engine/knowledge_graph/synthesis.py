"""
knowledge_graph/synthesis — Response synthesis (formerly response_synthesizer.py).

Converts a QueryOutcome (execution result) + draft LLM answer text into a
SynthesizedAnswer that carries:
  - shape classification  (scalar / series / table / kpis / timeseries / empty)
  - formatted rows        (numbers with commas, dates as ISO strings, currency prefix)
  - visualization hint    (bar / line / pie / table / stat / none)
  - enriched answer text  (LLM rewrite grounded in actual result data)
  - provenance            (entities queried)
  - retry metadata        (how many SQL repairs were needed)
"""
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("pulse.knowledge_graph.synthesis")

# ── QueryPlan dataclasses (preserved from query_planner.py) ────────────────────

@dataclass
class ResolvedColumn:
    entity: str
    column: str
    data_type: str
    role: str               # "measure" | "dimension" | "filter" | "key" | "timestamp"
    aggregation: Optional[str] = None   # "sum" | "avg" | "count" | "min" | "max" | None
    display_hint: Optional[str] = None


@dataclass
class SuggestedFilter:
    entity: str
    column: str
    operator: str           # "=" | ">" | "<" | "between" | "in" | "like" | "is_not_null"
    value_hint: Optional[str] = None   # e.g. "last 30 days" — LLM resolves to SQL


@dataclass
class QueryPlan:
    intent: str                             # "aggregation" | "lookup" | "listing" | "comparison" | "trend"
    target_entities: list[str] = field(default_factory=list)
    join_paths: list[Any] = field(default_factory=list)  # list[JoinPath]
    select_columns: list["ResolvedColumn"] = field(default_factory=list)
    group_by_columns: list["ResolvedColumn"] = field(default_factory=list)
    order_by_hint: Optional[str] = None    # "desc by measure" | "asc by dimension" | "chronological"
    suggested_filters: list["SuggestedFilter"] = field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    raw_join_sql: str = ""


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


# ── Column-name heuristics ────────────────────────────────────────────────────

_CURRENCY_HEURISTICS = frozenset({
    "amount", "total", "revenue", "cost", "price", "value", "salary",
    "budget", "fee", "balance", "payment", "income", "sales",
})
_DATE_HEURISTICS = frozenset({
    "date", "time", "created", "updated", "at", "on", "timestamp",
    "day", "month", "year", "week",
})
_TIMESERIES_DATE_TYPES = frozenset({
    "date", "datetime", "timestamp", "timestamptz",
    "timestamp with time zone", "timestamp without time zone",
})


# ── Shape classification ──────────────────────────────────────────────────────

class ShapeType(Enum):
    SCALAR     = "scalar"      # one row, one numeric column
    SERIES     = "series"      # list of same-type items (names / IDs)
    TABLE      = "table"       # general multi-column result
    KPIS       = "kpis"        # one row, several named metrics
    TIMESERIES = "timeseries"  # rows with a leading date/time column
    EMPTY      = "empty"       # zero rows or no execution result


class VizType(Enum):
    NONE  = "none"
    BAR   = "bar"
    LINE  = "line"
    PIE   = "pie"
    TABLE = "table"
    STAT  = "stat"    # big-number KPI card


# ── Public dataclasses ────────────────────────────────────────────────────────

@dataclass
class VisualizationHint:
    viz_type: str                    # VizType.value
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    series_column: Optional[str] = None
    title: str = ""


@dataclass
class SynthesizedAnswer:
    """
    Enriched chat response produced by ResponseSynthesizer.

    ``answer_text`` is always present (the main chat bubble text).
    Structured fields (rows, columns, viz_hint …) are populated only when
    a successful SQL execution result is available.
    """
    answer_text: str
    shape: str = ShapeType.EMPTY.value
    row_count: int = 0
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)     # formatted display rows
    viz_hint: Optional[VisualizationHint] = None
    sql_executed: str = ""
    truncated: bool = False
    retry_count: int = 0
    provenance: list[str] = field(default_factory=list)     # entity names queried
    cached: bool = False


# ── Synthesizer ───────────────────────────────────────────────────────────────

class ResponseSynthesizer:
    """
    Converts (answer_text, QueryOutcome, question, QueryPlan) → SynthesizedAnswer.
    """

    def __init__(self, llm_client=None, model: str = "", instance_id: str = ""):
        self.llm_client = llm_client  # kept for backward compat
        self.model = model
        self.instance_id = instance_id

    async def synthesize(
        self,
        answer_text: str,
        outcome: Optional[Any] = None,   # QueryOutcome | None
        question: str = "",
        plan: Optional[Any] = None,      # QueryPlan | None
        enrich: bool = True,
    ) -> "SynthesizedAnswer":
        from ai.engine.core.config import get_settings
        settings = get_settings()
        max_display = settings.KG_MAX_DISPLAY_ROWS

        if outcome is None or not outcome.succeeded or outcome.final_result is None:
            return SynthesizedAnswer(
                answer_text=answer_text,
                shape=ShapeType.EMPTY.value,
                retry_count=outcome.retry_count if outcome else 0,
            )

        result = outcome.final_result

        if not result.rows:
            return SynthesizedAnswer(
                answer_text=answer_text,
                shape=ShapeType.EMPTY.value,
                sql_executed=result.sql_executed,
                truncated=result.truncated,
                retry_count=outcome.retry_count,
                provenance=list(plan.target_entities) if plan and plan.target_entities else [],
            )

        shape = _classify_shape(result, plan)
        formatted_rows = _format_rows(result.rows, result.columns, settings)
        display_rows = formatted_rows[:max_display]
        viz = _suggest_viz(shape, result.columns, plan)
        provenance = list(plan.target_entities) if plan and plan.target_entities else []

        if enrich and result.rows and answer_text:
            enriched = await self._enrich_answer(
                answer_text=answer_text,
                rows=result.rows[:20],
                columns=result.columns,
                shape=shape,
                question=question,
                settings=settings,
            )
        else:
            enriched = answer_text

        return SynthesizedAnswer(
            answer_text=enriched,
            shape=shape.value,
            row_count=result.row_count,
            columns=result.columns,
            rows=display_rows,
            viz_hint=viz,
            sql_executed=result.sql_executed,
            truncated=result.truncated,
            retry_count=outcome.retry_count,
            provenance=provenance,
        )

    async def _enrich_answer(
        self,
        answer_text: str,
        rows: list[dict],
        columns: list[str],
        shape: ShapeType,
        question: str,
        settings,
    ) -> str:
        data_preview = json.dumps(rows[:10], default=str, indent=2)

        prompt = (
            f"User question: {question}\n\n"
            f"Draft answer: {answer_text}\n\n"
            f"Actual query result ({len(rows)} rows):\n{data_preview}\n\n"
            "Rewrite the answer to accurately reflect the actual data. "
            "Be concise and specific — use the real numbers and values from the results. "
            "Do not mention SQL, queries, or database internals. "
            "If the draft is already accurate and specific, return it unchanged."
        )

        try:
            from ai.engine.llm.router import route_chat
            result = await route_chat(
                task="cognition",
                instance_id=self.instance_id or "system",
                conversation_id="enrich-answer",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            enriched = result.get("content") or answer_text
            return enriched
        except Exception as exc:
            logger.warning(f"Answer enrichment LLM call failed: {exc}")
            return answer_text


# ── Shape classifier ──────────────────────────────────────────────────────────

def _classify_shape(result, plan) -> ShapeType:
    rows    = result.rows
    columns = result.columns

    if not rows:
        return ShapeType.EMPTY
    if len(rows) == 1 and len(columns) == 1:
        return ShapeType.SCALAR
    if len(rows) == 1 and len(columns) >= 2:
        return ShapeType.KPIS
    if columns and _col_looks_like_date(columns[0], rows[0]):
        return ShapeType.TIMESERIES
    if len(columns) == 1:
        return ShapeType.SERIES
    return ShapeType.TABLE


def _col_looks_like_date(col_name: str, sample_row: dict) -> bool:
    name_l = col_name.lower()
    if any(tok in name_l for tok in _DATE_HEURISTICS):
        return True
    val = sample_row.get(col_name)
    if val is None:
        return False
    import datetime
    return isinstance(val, (datetime.date, datetime.datetime))


# ── Row formatter ─────────────────────────────────────────────────────────────

def _format_rows(
    rows: list[dict],
    columns: list[str],
    settings,
) -> list[list[Any]]:
    formatted = []
    currency = settings.KG_CURRENCY_SYMBOL
    for row in rows:
        cells = []
        for col in columns:
            val = row.get(col)
            cells.append(_format_cell(val, col, currency))
        formatted.append(cells)
    return formatted


def _format_cell(val: Any, col_name: str, currency_symbol: str) -> Any:
    import datetime
    import decimal

    if val is None:
        return None

    col_l = col_name.lower()

    if isinstance(val, datetime.datetime):
        return val.isoformat(timespec="seconds")
    if isinstance(val, datetime.date):
        return val.isoformat()

    if isinstance(val, (int, float, decimal.Decimal)):
        num = float(val) if isinstance(val, decimal.Decimal) else val
        is_currency = any(tok in col_l for tok in _CURRENCY_HEURISTICS)
        if is_currency:
            return f"{currency_symbol}{num:,.2f}"
        if isinstance(val, int) or (isinstance(val, float) and val == int(val)):
            return f"{int(num):,}"
        return round(num, 4)

    if isinstance(val, str) and len(val) > 200:
        return val[:197] + "…"

    return val


# ── Visualization recommender ─────────────────────────────────────────────────

def _suggest_viz(
    shape: ShapeType,
    columns: list[str],
    plan,
) -> Optional[VisualizationHint]:
    intent = plan.intent if plan else ""

    if shape == ShapeType.SCALAR:
        return VisualizationHint(viz_type=VizType.STAT.value)
    if shape == ShapeType.KPIS:
        return VisualizationHint(viz_type=VizType.STAT.value)
    if shape == ShapeType.TIMESERIES:
        x = columns[0] if columns else None
        y = columns[1] if len(columns) > 1 else None
        return VisualizationHint(viz_type=VizType.LINE.value, x_axis=x, y_axis=y)
    if shape == ShapeType.SERIES:
        return VisualizationHint(viz_type=VizType.TABLE.value, y_axis=columns[0] if columns else None)
    if shape == ShapeType.TABLE:
        if intent in ("aggregation", "comparison") and len(columns) == 2:
            x = columns[0]
            y = columns[1]
            return VisualizationHint(viz_type=VizType.BAR.value, x_axis=x, y_axis=y)
        return VisualizationHint(viz_type=VizType.TABLE.value)
    return None
