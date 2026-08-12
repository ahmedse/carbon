"""
knowledge_graph/engine — SQL execution engine (formerly execution_engine.py).

Executes SQL queries against the host database with:
  - Structured result type (ExecutionResult)
  - Typed error classification (ErrorCategory / ExecutionError)
  - Configurable row limit and statement timeout (from Settings)

This is the single, authoritative path for running host-DB queries from the
knowledge-graph pipeline.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("pulse.knowledge_graph.engine")


# ── Error taxonomy ────────────────────────────────────────────────────────────

class ErrorCategory(Enum):
    SYNTAX         = "syntax"
    TABLE_NOT_FOUND  = "table_not_found"
    COLUMN_NOT_FOUND = "column_not_found"
    TYPE_MISMATCH  = "type_mismatch"
    TIMEOUT        = "timeout"
    PERMISSION     = "permission"
    UNKNOWN        = "unknown"


@dataclass
class ExecutionError:
    category: ErrorCategory
    message: str
    hint: str = ""


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class ExecutionResult:
    success: bool
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    columns: list[str] = field(default_factory=list)
    duration_ms: int = 0
    sql_executed: str = ""
    error: Optional[ExecutionError] = None
    truncated: bool = False


# ── Engine ────────────────────────────────────────────────────────────────────

class ExecutionEngine:
    """Thin async wrapper around psycopg2 for read-only host-DB queries."""

    def __init__(self, instance_id: str):
        self.instance_id = instance_id

    async def _resolve_db_url(self) -> str:
        from ai.engine.core.config import get_settings
        db_url = get_settings().HOST_DB_URL
        if self.instance_id:
            try:
                from ai.engine.core.database import get_session_factory
                from ai.engine.core.models import Instance
                from sqlalchemy import select as sa_select
                _sf = get_session_factory()
                async with _sf() as _s:
                    _r = await _s.execute(
                        sa_select(Instance.host_db_url).where(Instance.id == self.instance_id)
                    )
                    _url = _r.scalar_one_or_none()
                    if _url:
                        db_url = _url
            except Exception:
                pass
        return db_url

    async def execute(self, sql: str) -> ExecutionResult:
        from ai.engine.core.config import get_settings

        settings = get_settings()
        timeout_ms = settings.KG_QUERY_TIMEOUT_MS
        row_limit  = settings.KG_QUERY_ROW_LIMIT

        db_url = await self._resolve_db_url()

        if not db_url:
            return ExecutionResult(
                success=False,
                sql_executed=sql,
                error=ExecutionError(
                    category=ErrorCategory.UNKNOWN,
                    message="HOST_DB_URL is not configured.",
                    hint="Set HOST_DB_URL in .env before querying the host database.",
                ),
            )

        from ai.engine.core.sql_validator import validate_sql
        try:
            validate_sql(sql)
        except Exception as val_err:
            return ExecutionResult(
                success=False,
                sql_executed=sql,
                error=ExecutionError(
                    category=ErrorCategory.UNKNOWN,
                    message=str(val_err),
                    hint="Only read-only SELECT queries are allowed.",
                ),
            )

        t0 = time.perf_counter()
        try:
            result = await asyncio.to_thread(
                _execute_sync, sql, db_url, timeout_ms, row_limit
            )
            result.duration_ms = int((time.perf_counter() - t0) * 1000)
            result.sql_executed = sql
            logger.debug(
                f"ExecutionEngine  instance={self.instance_id}  "
                f"rows={result.row_count}  truncated={result.truncated}  "
                f"duration={result.duration_ms}ms"
            )
            return result
        except Exception as exc:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            err = _classify_error(str(exc))
            logger.warning(
                f"ExecutionEngine  instance={self.instance_id}  "
                f"category={err.category.value}  duration={duration_ms}ms  "
                f"msg={err.message[:120]!r}"
            )
            return ExecutionResult(
                success=False,
                duration_ms=duration_ms,
                sql_executed=sql,
                error=err,
            )


# ── Sync worker (runs in thread) ──────────────────────────────────────────────

def _execute_sync(
    sql: str,
    db_url: str,
    timeout_ms: int,
    row_limit: int,
) -> ExecutionResult:
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(db_url)
    try:
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"SET statement_timeout = '{timeout_ms}'")
        cur.execute(sql)

        raw = cur.fetchmany(row_limit + 1)
        truncated = len(raw) > row_limit
        rows = raw[:row_limit]
        columns = [d[0] for d in cur.description] if cur.description else []

        return ExecutionResult(
            success=True,
            rows=[dict(r) for r in rows],
            row_count=len(rows),
            columns=columns,
            truncated=truncated,
        )
    finally:
        conn.close()


# ── Error classifier ──────────────────────────────────────────────────────────

def _classify_error(msg: str) -> ExecutionError:
    m = msg.lower()

    if "syntax error" in m or "parse error" in m:
        return ExecutionError(
            category=ErrorCategory.SYNTAX,
            message=msg,
            hint=(
                "Fix the SQL syntax. Check for missing commas, unclosed parentheses, "
                "misplaced keywords, or unsupported syntax."
            ),
        )

    if ("relation" in m or "table" in m) and "does not exist" in m:
        return ExecutionError(
            category=ErrorCategory.TABLE_NOT_FOUND,
            message=msg,
            hint=(
                "The referenced table does not exist. Use the exact table name from "
                "the schema — check for typos or schema prefix issues."
            ),
        )

    if "column" in m and ("does not exist" in m or "unknown column" in m):
        return ExecutionError(
            category=ErrorCategory.COLUMN_NOT_FOUND,
            message=msg,
            hint=(
                "One or more columns don't exist on the referenced table. "
                "Verify column names against the schema."
            ),
        )

    if "type" in m and ("mismatch" in m or "cannot cast" in m or "operator does not exist" in m):
        return ExecutionError(
            category=ErrorCategory.TYPE_MISMATCH,
            message=msg,
            hint=(
                "Type mismatch. Cast values explicitly (e.g. ::text, ::integer) "
                "or compare with compatible types."
            ),
        )

    if "timeout" in m or "statement timeout" in m or "canceling statement" in m:
        return ExecutionError(
            category=ErrorCategory.TIMEOUT,
            message=msg,
            hint=(
                "Query timed out. Add a LIMIT clause, a more selective WHERE condition, "
                "or simplify the aggregation."
            ),
        )

    if "permission denied" in m or "access denied" in m or "privilege" in m:
        return ExecutionError(
            category=ErrorCategory.PERMISSION,
            message=msg,
            hint="Permission denied for this table or operation.",
        )

    return ExecutionError(
        category=ErrorCategory.UNKNOWN,
        message=msg,
        hint="An unexpected database error occurred. Review the SQL for correctness.",
    )
