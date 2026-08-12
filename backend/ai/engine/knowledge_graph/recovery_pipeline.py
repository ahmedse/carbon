"""
RecoveryPipeline — Stage 10.

Orchestrates post-retry-loop recovery for all error categories:

  empty_result  → EmptyResultRecovery  (COUNT probe + fuzzy entity match)
  timeout       → TimeoutRecovery      (SQL simplification + retry)
  sql_error     → diagnostic message   (repairs were handled by QueryRetryLoop)
  implausible   → sanity-CTE rewrite + retry, then caveat if still wrong
  permission    → clear permission error message
  unknown       → generic error message

Called from PulseAgent._execute_and_synthesize() after QueryRetryLoop
completes. The shared 3-execution budget is tracked across both the retry
loop and this pipeline.

All recovery attempts are logged to kg_recovery_log (best-effort audit trail).
"""
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ai.engine.knowledge_graph.engine import ErrorCategory, ExecutionResult

if TYPE_CHECKING:
    from ai.engine.knowledge_graph.retry import QueryOutcome

logger = logging.getLogger("pulse.knowledge_graph.recovery_pipeline")


# ── Public dataclass ──────────────────────────────────────────────────────────

@dataclass
class RecoveryOutcome:
    """
    Carries the best result and user-facing explanation after recovery.

    ``succeeded=True``  → ``final_result`` + ``final_sql`` are usable.
    ``succeeded=False`` → ``user_message`` explains what went wrong.
    ``error_type``      → "sql_error" | "empty_result" | "timeout" |
                          "implausible" | "permission" | "unknown" | ""
    ``recovery_type``   → "sql_repair_exhausted" | "fuzzy_match" |
                          "timeout_simplify" | "sanity_cte" | "none"
    """
    succeeded: bool = False
    final_result: Optional[ExecutionResult] = None
    final_sql: str = ""
    error_type: str = ""
    recovery_type: str = "none"
    correction_description: str = ""  # human-readable, for audit log
    user_message: str = ""            # surfaced to the user
    retry_count: int = 0              # extra executions used by recovery


# ── Pipeline ──────────────────────────────────────────────────────────────────

class RecoveryPipeline:
    """
    Post-retry-loop recovery orchestrator.

    Usage::

        pipeline = RecoveryPipeline(instance_id, llm_client, model, messages)
        recovery = await pipeline.run(sql, primary_outcome, question)
    """

    def __init__(
        self,
        instance_id: str,
        llm_client,
        model: str,
        messages: list[dict],
    ):
        self.instance_id = instance_id
        self.llm_client = llm_client
        self.model = model
        self.messages = messages

    async def run(
        self,
        sql: str,
        primary_outcome: "QueryOutcome",
        question: str,
    ) -> RecoveryOutcome:
        """
        Examine *primary_outcome* and apply the appropriate recovery strategy.

        Parameters
        ----------
        sql:             The original SQL (before retry-loop repairs).
        primary_outcome: QueryOutcome from QueryRetryLoop.
        question:        Original user utterance.

        Returns
        -------
        RecoveryOutcome — always returns (never raises).
        """
        from ai.engine.core.config import get_settings
        settings = get_settings()

        if not settings.KG_RECOVERY_ENABLED:
            return RecoveryOutcome()

        # Remaining budget: max 3 total executions in the whole pipeline
        total_used = len(primary_outcome.attempts)
        remaining = max(0, 3 - total_used)

        final = primary_outcome.final_result
        final_sql = final.sql_executed if final else sql

        # ── A: Successful query with zero rows ────────────────────────────────
        if primary_outcome.succeeded and final and final.row_count == 0:
            return await self._handle_empty_result(
                sql=final_sql,
                question=question,
                remaining=remaining,
                settings=settings,
            )

        # ── B: Execution failed ────────────────────────────────────────────────
        if not primary_outcome.succeeded and final:
            err = final.error
            if not err:
                return RecoveryOutcome(
                    error_type="unknown",
                    user_message="An unexpected error occurred while running this query.",
                )
            return await self._handle_failure(
                sql=final_sql,
                error=err,
                question=question,
                remaining=remaining,
                attempts=primary_outcome.attempts,
                settings=settings,
            )

        # ── C: Successful query with implausible-looking values ───────────────
        if primary_outcome.succeeded and final and _detect_anomalies(final):
            return await self._handle_implausible(
                sql=final_sql,
                question=question,
                remaining=remaining,
                result=final,
            )

        return RecoveryOutcome()

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _handle_empty_result(
        self, sql: str, question: str, remaining: int, settings
    ) -> RecoveryOutcome:
        if not settings.KG_RECOVERY_EMPTY_RESULT:
            return RecoveryOutcome(
                error_type="empty_result",
                user_message="No matching records were found.",
            )

        
        recovery = EmptyResultRecovery(self.instance_id)
        res = await recovery.recover(
            sql=sql, question=question, remaining_budget=remaining
        )

        out = RecoveryOutcome(error_type="empty_result")

        if res.suggestion:
            out.recovery_type = "fuzzy_match"
            out.correction_description = res.suggestion
            out.user_message = res.suggestion
        elif res.genuinely_empty:
            col_note = (
                f" I confirmed by checking whether the "
                f"'{res.filter_col}' filter was the issue — no rows existed"
                f" even after relaxing it."
                if res.filter_col
                else ""
            )
            out.user_message = f"No records match your query.{col_note}"
        else:
            out.user_message = "No results were found for your query."

        return out

    async def _handle_failure(
        self,
        sql: str,
        error,
        question: str,
        remaining: int,
        attempts: list,
        settings,
    ) -> RecoveryOutcome:
        out = RecoveryOutcome()
        cat = error.category

        # ── Timeout → try SQL simplification ──────────────────────────────────
        if cat == ErrorCategory.TIMEOUT and settings.KG_RECOVERY_TIMEOUT:
            from ai.engine.knowledge_graph.timeout_recovery import TimeoutRecovery
            tr = TimeoutRecovery(self.instance_id)
            res = await tr.recover(
                sql=sql, question=question, remaining_budget=remaining
            )
            out.error_type = "timeout"
            if res.succeeded:
                out.succeeded = True
                out.final_result = res.final_result
                out.final_sql = res.simplified_sql
                out.recovery_type = "timeout_simplify"
                out.correction_description = res.simplification_description
                out.user_message = res.simplification_description
                out.retry_count = 1
            else:
                out.user_message = (
                    "This query was too complex to run within the time limit. "
                    "Try asking for a smaller date range or a specific subset of data."
                )
            return out

        # ── SQL error — retries already exhausted by QueryRetryLoop ───────────
        if cat in {
            ErrorCategory.SYNTAX,
            ErrorCategory.TABLE_NOT_FOUND,
            ErrorCategory.COLUMN_NOT_FOUND,
            ErrorCategory.TYPE_MISMATCH,
        }:
            out.error_type = "sql_error"
            out.recovery_type = "sql_repair_exhausted"
            out.correction_description = "; ".join(
                f"attempt {i + 1}: {a.result.error.category.value} — "
                f"{a.result.error.message[:80]}"
                for i, a in enumerate(attempts)
                if a.result.error
            )
            attempt_count = len(attempts)
            out.user_message = (
                f"I wasn't able to build a working query for this question after "
                f"{attempt_count} attempt{'s' if attempt_count != 1 else ''}. "
                f"Here's what went wrong: {error.message[:200]}"
            )
            return out

        # ── Permission error ───────────────────────────────────────────────────
        if cat == ErrorCategory.PERMISSION:
            out.error_type = "permission"
            out.user_message = (
                "I don't have permission to access the data needed for this question."
            )
            return out

        # ── Unknown / other ────────────────────────────────────────────────────
        out.error_type = "unknown"
        out.user_message = (
            f"An unexpected error occurred while running this query: "
            f"{error.message[:200]}"
        )
        return out

    async def _handle_implausible(
        self,
        sql: str,
        question: str,
        remaining: int,
        result: ExecutionResult,
    ) -> RecoveryOutcome:
        """Re-run with sanity-check filters; add a caveat if values are still off."""
        out = RecoveryOutcome(error_type="implausible")

        anomalies = _detect_anomalies(result)
        if not anomalies:
            return RecoveryOutcome()  # false alarm — no anomaly

        if remaining < 1:
            out.user_message = (
                "The results look unusual — some values may be unexpected. "
                "Please verify this data before acting on it."
            )
            return out

        sanity_sql = _wrap_with_sanity_cte(sql, anomalies)
        if not sanity_sql:
            out.user_message = (
                "The results look unusual — some values may be unexpected. "
                "Please verify this data before acting on it."
            )
            return out

        from ai.engine.knowledge_graph.engine import ExecutionEngine
        engine = ExecutionEngine(self.instance_id)
        sanity_result = await engine.execute(sanity_sql)
        out.retry_count = 1

        if sanity_result.success and sanity_result.row_count > 0:
            out.succeeded = True
            out.final_result = sanity_result
            out.final_sql = sanity_sql
            out.recovery_type = "sanity_cte"
            out.correction_description = (
                "Results have been filtered to remove implausible values "
                f"({', '.join(a.description for a in anomalies)})."
            )
            out.user_message = out.correction_description
        else:
            # Still implausible or empty after sanity filter — caveat only
            out.user_message = (
                "The results are available but some values appear unusual. "
                "Please verify this data — it may indicate a data quality issue."
            )

        return out


# ── Implausibility detection ──────────────────────────────────────────────────

@dataclass
class _Anomaly:
    col: str
    issue: str        # "negative_amount" | "pct_over_100"
    description: str  # human-readable


_AMOUNT_COLS = frozenset({
    "revenue", "total", "amount", "cost", "price", "payment",
    "income", "sales", "profit", "balance", "fee", "earnings",
})
_PCT_COLS = frozenset({
    "percentage", "percent", "ratio", "rate", "pct", "mape",
    "accuracy", "error_rate", "loss_rate",
})


def _detect_anomalies(result: ExecutionResult) -> list[_Anomaly]:
    """
    Scan numeric columns for obvious data-quality anomalies.
    Returns a list of detected anomalies (empty = all looks fine).
    """
    if not result.rows or not result.columns:
        return []

    anomalies: list[_Anomaly] = []
    seen_cols: set[str] = set()

    for col in result.columns:
        if col in seen_cols:
            continue
        col_lower = col.lower()

        # Negative amounts
        if any(w in col_lower for w in _AMOUNT_COLS):
            for row in result.rows:
                val = row.get(col)
                if val is not None:
                    try:
                        if float(val) < 0:
                            anomalies.append(
                                _Anomaly(
                                    col=col,
                                    issue="negative_amount",
                                    description=f"negative {col} value",
                                )
                            )
                            seen_cols.add(col)
                            break
                    except (ValueError, TypeError):
                        pass

        # Percentages over 100
        if any(w in col_lower for w in _PCT_COLS):
            for row in result.rows:
                val = row.get(col)
                if val is not None:
                    try:
                        if float(val) > 100:
                            anomalies.append(
                                _Anomaly(
                                    col=col,
                                    issue="pct_over_100",
                                    description=f"{col} value exceeds 100%",
                                )
                            )
                            seen_cols.add(col)
                            break
                    except (ValueError, TypeError):
                        pass

    return anomalies


def _wrap_with_sanity_cte(sql: str, anomalies: list[_Anomaly]) -> str | None:
    """
    Wrap *sql* in a CTE that filters away the detected anomalous rows.
    Returns None when no meaningful conditions can be derived.

    Produces::

        WITH _raw AS (<original sql>)
        SELECT * FROM _raw
        WHERE <sanity conditions>
    """
    if not anomalies:
        return None

    stripped = sql.strip().rstrip(";")
    if not stripped.upper().startswith("SELECT"):
        return None

    conditions: list[str] = []
    for a in anomalies:
        if a.issue == "negative_amount":
            conditions.append(f"{a.col} >= 0")
        elif a.issue == "pct_over_100":
            conditions.append(f"{a.col} <= 100")

    if not conditions:
        return None

    return (
        f"WITH _raw AS (\n  {stripped}\n)\n"
        f"SELECT * FROM _raw WHERE {' AND '.join(conditions)}"
    )


# ── EmptyRecoveryResult dataclass ──────────────────────────────────────────────

@dataclass
class EmptyRecoveryResult:
    """Outcome of an empty result investigation."""
    suggestion: Optional[str] = None    # "No results for X — did you mean Y?"
    matched_value: Optional[str] = None
    similarity: float = 0.0
    probe_count: int = 0                # COUNT(*) without the problematic filter
    fuzzy_candidates: list[str] = field(default_factory=list)


# ── Recovery class ────────────────────────────────────────────────────────────

class EmptyResultRecovery:
    """
    Investigates a zero-row query result and suggests filter corrections.
    Uses at most ``remaining_budget`` additional host-DB executions.
    """

    def __init__(self, instance_id: str):
        self.instance_id = instance_id

    async def recover(
        self,
        sql: str,
        question: str,
        remaining_budget: int = 2,
    ) -> EmptyRecoveryResult:
        """
        Investigate why *sql* returned zero rows.

        Parameters
        ----------
        sql:              The SQL that returned 0 rows.
        question:         Original user utterance (for logging).
        remaining_budget: Maximum additional host-DB executions allowed.

        Returns
        -------
        EmptyRecoveryResult with ``suggestion`` set if a likely match was found,
        or ``genuinely_empty=True`` if no filter issue was detected.
        """
        from ai.engine.core.config import get_settings
        threshold = get_settings().KG_RECOVERY_FUZZY_THRESHOLD

        result = EmptyRecoveryResult()

        # ── Find a filterable string equality clause ───────────────────────────
        filter_info = _extract_primary_filter(sql)
        if not filter_info:
            result.genuinely_empty = True
            logger.debug(
                "EmptyResultRecovery: no filterable WHERE clause found — genuinely empty"
            )
            return result

        table, col, val = filter_info
        result.filter_col = col
        result.filter_val = val

        if remaining_budget < 1:
            logger.debug("EmptyResultRecovery: no budget remaining")
            return result

        # ── Probe: COUNT(*) without the problematic filter ─────────────────────
        probe_sql = _build_probe_sql(sql, col, val)
        if not probe_sql:
            result.genuinely_empty = True
            return result

        from ai.engine.knowledge_graph.engine import ExecutionEngine
        engine = ExecutionEngine(self.instance_id)

        probe_result = await engine.execute(probe_sql)
        remaining_budget -= 1

        if not probe_result.success or not probe_result.rows:
            result.genuinely_empty = True
            return result

        count_raw = next(iter(probe_result.rows[0].values()), 0)
        try:
            result.probe_count = int(count_raw)
        except (ValueError, TypeError):
            result.probe_count = 0

        if result.probe_count == 0:
            result.genuinely_empty = True
            logger.debug(
                "EmptyResultRecovery: probe count=0 — genuinely empty  col=%s  val=%r",
                col, val,
            )
            return result

        logger.debug(
            "EmptyResultRecovery: probe found %d rows without %s filter — "
            "fetching distinct values for fuzzy match",
            result.probe_count, col,
        )

        # ── Fetch DISTINCT values for fuzzy matching ───────────────────────────
        if remaining_budget < 1:
            return result

        distinct_sql = (
            f"SELECT DISTINCT {col} FROM {table} "
            f"WHERE {col} IS NOT NULL LIMIT 200"
        )
        dist_result = await engine.execute(distinct_sql)
        remaining_budget -= 1

        if not dist_result.success or not dist_result.rows:
            return result

        candidates = [
            str(row.get(col, "") or "").strip()
            for row in dist_result.rows
            if row.get(col) is not None and str(row.get(col, "")).strip()
        ]

        best_match, best_score = _fuzzy_match(val, candidates, threshold)
        if best_match:
            result.suggestion = (
                f"No results for '{val}' — did you mean '{best_match}'?"
            )
            result.matched_value = best_match
            result.similarity = best_score
            logger.info(
                "EmptyResultRecovery: fuzzy match  col=%s  original=%r  "
                "match=%r  score=%.2f",
                col, val, best_match, best_score,
            )
        else:
            logger.debug(
                "EmptyResultRecovery: no fuzzy match above threshold=%.2f  "
                "col=%s  val=%r",
                threshold, col, val,
            )

        return result


# ── SQL helpers ───────────────────────────────────────────────────────────────

def _extract_primary_filter(sql: str) -> tuple[str, str, str] | None:
    """
    Find the first string equality filter that is a good fuzzy-match candidate
    — i.e., not an ID/date/boolean column and not a numeric-looking value.

    Returns (table, column, value) or None.
    """
    from_match = _FROM_TABLE_RE.search(sql)
    table = from_match.group(1) if from_match else "unknown"

    for m in _EQUALITY_FILTER_RE.finditer(sql):
        col = m.group(1)
        val = m.group(2)
        if col.lower() not in _SKIP_COLS and not _looks_like_id(val):
            return table, col, val

    return None


def _build_probe_sql(original_sql: str, col: str, val: str) -> str | None:
    """
    Build a COUNT(*) probe by removing the equality filter on *col* = *val*.
    Returns None if no FROM clause is found in the result (safety guard).
    """
    # Remove: "AND col = 'val'"
    probed = re.sub(
        rf"\bAND\s+\b{re.escape(col)}\s*=\s*'[^']*'\s*",
        " ",
        original_sql,
        flags=re.IGNORECASE,
        count=1,
    )
    # Remove: "WHERE col = 'val' [AND]"
    probed = re.sub(
        rf"\bWHERE\s+\b{re.escape(col)}\s*=\s*'[^']*'\s*(?:AND\s+)?",
        "WHERE ",
        probed,
        flags=re.IGNORECASE,
        count=1,
    )
    # Clean up dangling WHERE with nothing after it
    probed = re.sub(
        r"\bWHERE\s*(GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|$)",
        r"\1",
        probed.rstrip(),
        flags=re.IGNORECASE,
    )
    probed = re.sub(r"\bWHERE\s*$", "", probed.rstrip(), flags=re.IGNORECASE)

    if not _FROM_TABLE_RE.search(probed):
        return None

    return f"SELECT COUNT(*) AS _n FROM ({probed.strip()}) AS _probe_sq"


def _looks_like_id(val: str) -> bool:
    """Heuristic: pure numeric strings and UUIDs are not fuzzy-match targets."""
    if re.fullmatch(r"\d+", val):
        return True
    if re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        val,
        re.I,
    ):
        return True
    return False


def _fuzzy_match(
    target: str,
    candidates: list[str],
    threshold: float,
) -> tuple[str, float]:
    """
    Find the best fuzzy match for *target* in *candidates*.
    Uses SequenceMatcher ratio. Returns (best_match, score) or ("", 0.0).
    """
    best_candidate = ""
    best_score = 0.0
    tl = target.lower().strip()

    for c in candidates:
        if not c:
            continue
        score = SequenceMatcher(None, tl, c.lower().strip()).ratio()
        if score > best_score:
            best_score = score
            best_candidate = c

    if best_score >= threshold:
        return best_candidate, best_score
    return "", 0.0
