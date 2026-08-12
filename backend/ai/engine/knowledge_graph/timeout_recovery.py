"""
TimeoutRecovery — Stage 10.

When a query exceeds the execution time budget, this module applies
safe SQL simplifications in order and retries:

  1. Add LIMIT 1000 if no LIMIT is present.
  2. Add a time-range filter (CURRENT_DATE − N days) if a date/time column
     is detectable in the SQL text.

Both simplifications can apply together. The user is told what was changed.
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("pulse.knowledge_graph.timeout_recovery")


# Common date/time column name patterns — searched anywhere in the SQL text
_DATE_COL_RE = re.compile(
    r"(?<!\w)("
    r"created_at|updated_at|recorded_at|event_at|occurred_at|"
    r"started_at|completed_at|event_time|reading_time|reading_date|"
    r"created_date|event_date|start_date|end_date|logged_at|"
    r"ingested_at|inserted_at|timestamp"
    r")(?!\w)",
    re.IGNORECASE,
)


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class TimeoutRecoveryResult:
    """Outcome of a timeout simplification attempt."""
    succeeded: bool = False
    simplified_sql: str = ""
    simplification_description: str = ""   # user-facing sentence
    final_result: Optional[object] = None  # ExecutionResult | None
    strategy_used: str = "none"            # "limit" | "time_range" | "limit+time_range"


# ── Recovery class ────────────────────────────────────────────────────────────

class TimeoutRecovery:
    """
    Simplify a timed-out SQL query and re-execute it within the budget.
    """

    def __init__(self, instance_id: str):
        self.instance_id = instance_id

    async def recover(
        self,
        sql: str,
        question: str,
        remaining_budget: int = 1,
    ) -> TimeoutRecoveryResult:
        """
        Simplify *sql* and re-execute if budget allows.

        Parameters
        ----------
        sql:              The SQL that timed out.
        question:         Original user utterance (for logging).
        remaining_budget: Maximum additional host-DB executions allowed.

        Returns
        -------
        TimeoutRecoveryResult — ``succeeded=True`` if simplified query ran.
        """
        from ai.engine.core.config import get_settings
        days = get_settings().KG_RECOVERY_TIME_RANGE_DAYS

        result = TimeoutRecoveryResult()

        if remaining_budget < 1:
            logger.debug("TimeoutRecovery: no budget remaining")
            return result

        simplified, description, strategy = _simplify_sql(sql, days)
        if not simplified:
            logger.debug("TimeoutRecovery: no simplification applicable")
            return result

        result.simplified_sql = simplified
        result.simplification_description = description
        result.strategy_used = strategy

        logger.info(
            "TimeoutRecovery: retrying with simplified SQL  strategy=%s  sql=%r",
            strategy, simplified[:120],
        )

        from ai.engine.knowledge_graph.engine import ExecutionEngine
        engine = ExecutionEngine(self.instance_id)
        exec_result = await engine.execute(simplified)

        if exec_result.success:
            result.succeeded = True
            result.final_result = exec_result
            logger.info(
                "TimeoutRecovery: succeeded  strategy=%s  rows=%d",
                strategy, exec_result.row_count,
            )
        else:
            err_msg = exec_result.error.message[:120] if exec_result.error else "unknown"
            logger.debug("TimeoutRecovery: simplified query also failed: %s", err_msg)

        return result


# ── SQL simplification helpers ────────────────────────────────────────────────

def _simplify_sql(original_sql: str, days: int) -> tuple[str, str, str]:
    """
    Apply safe simplifications to a timeout-causing query.

    Returns (simplified_sql, user_facing_description, strategy_code).
    Returns ("", "", "none") when no simplification is applicable or safe.
    """
    sql = original_sql.strip().rstrip(";")
    strategies: list[str] = []
    descriptions: list[str] = []

    # ── Step 1: Add LIMIT if absent ────────────────────────────────────────────
    if not re.search(r"\bLIMIT\s+\d+", sql, re.IGNORECASE):
        sql = sql + " LIMIT 1000"
        strategies.append("limit")
        descriptions.append("limited to 1,000 rows")

    # ── Step 2: Add a time-range filter if a date column is identifiable ───────
    date_col_m = _DATE_COL_RE.search(sql)
    if date_col_m:
        date_col = date_col_m.group(1)
        filter_clause = (
            f"{date_col} >= CURRENT_DATE - INTERVAL '{days} days'"
        )
        has_where = bool(re.search(r"\bWHERE\b", sql, re.IGNORECASE))

        if has_where:
            # Prepend our condition to the existing WHERE
            sql = re.sub(
                r"\bWHERE\b",
                f"WHERE {filter_clause} AND",
                sql,
                count=1,
                flags=re.IGNORECASE,
            )
        else:
            # Insert WHERE before the first clause keyword, or append
            rewritten = re.sub(
                r"\b(GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT)\b",
                f"WHERE {filter_clause} \\1",
                sql,
                count=1,
                flags=re.IGNORECASE,
            )
            sql = rewritten if rewritten != sql else (sql + f" WHERE {filter_clause}")

        strategies.append("time_range")
        descriptions.append(f"filtered to the last {days} days")

    if not strategies:
        return "", "", "none"

    strategy = "+".join(strategies)
    desc_items = " and ".join(descriptions)
    description = f"The full query was too slow, so I've {desc_items}."
    return sql, description, strategy
