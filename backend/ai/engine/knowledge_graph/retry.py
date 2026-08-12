"""
knowledge_graph/retry — SQL retry loop (formerly retry_loop.py).

Runs a SQL query against the host database with automatic error-driven retry.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ai.engine.knowledge_graph.engine import ErrorCategory, ExecutionEngine, ExecutionResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger("pulse.knowledge_graph.retry")

_NON_RETRYABLE = {ErrorCategory.PERMISSION, ErrorCategory.TIMEOUT}


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class QueryAttempt:
    """A single SQL execution attempt."""
    sql: str
    result: ExecutionResult
    retry_reason: str = ""


@dataclass
class QueryOutcome:
    """Complete execution history for one user question."""
    attempts: list[QueryAttempt] = field(default_factory=list)
    final_result: Optional[ExecutionResult] = None
    succeeded: bool = False
    retry_count: int = 0


@dataclass
class QueryFeedback:
    """Value object for writing a KgQueryFeedback row."""
    instance_id: str
    question: str
    sql_final: str
    succeeded: bool
    retry_count: int
    error_category: str = ""
    duration_ms: int = 0
    row_count: int = 0
    shape: str = ""


# ── Retry loop ─────────────────────────────────────────────────────────────────

class QueryRetryLoop:
    """Two-phase execution loop with LLM-driven SQL repair on failure."""

    def __init__(
        self,
        engine: ExecutionEngine,
        llm_client,
        model: str,
        messages: list[dict],
    ):
        self.engine  = engine
        self.llm_client = llm_client
        self.model   = model
        self.messages = messages

    async def run(self, sql: str, plan=None) -> QueryOutcome:
        from ai.engine.core.config import get_settings
        settings = get_settings()
        max_retries = settings.KG_MAX_RETRIES

        outcome = QueryOutcome()
        current_sql = sql

        for attempt_num in range(max_retries + 1):
            logger.debug(
                f"QueryRetryLoop  attempt={attempt_num + 1}/{max_retries + 1}  "
                f"sql={current_sql[:80]!r}"
            )

            result = await self.engine.execute(current_sql)
            attempt = QueryAttempt(
                sql=current_sql,
                result=result,
                retry_reason="" if attempt_num == 0 else (
                    result.error.category.value if result.error else "unknown"
                ),
            )
            outcome.attempts.append(attempt)

            if result.success:
                outcome.final_result = result
                outcome.succeeded = True
                outcome.retry_count = attempt_num
                logger.info(
                    f"QueryRetryLoop succeeded  attempt={attempt_num + 1}  "
                    f"rows={result.row_count}  truncated={result.truncated}"
                )
                return outcome

            err = result.error
            if not err:
                logger.warning("QueryRetryLoop: execution failed with no error detail")
                break

            logger.warning(
                f"QueryRetryLoop  attempt={attempt_num + 1}  "
                f"error={err.category.value}  msg={err.message[:120]!r}"
            )

            if err.category in _NON_RETRYABLE:
                logger.warning(
                    f"Non-retryable error category={err.category.value} — aborting"
                )
                break

            if attempt_num >= max_retries:
                break

            fixed_sql = await self._repair_sql(current_sql, err, attempt_num)
            if not fixed_sql or fixed_sql.strip().upper() == current_sql.strip().upper():
                logger.warning("LLM repair returned identical SQL — stopping retry loop")
                break

            current_sql = fixed_sql

        outcome.final_result = outcome.attempts[-1].result if outcome.attempts else None
        outcome.succeeded = False
        outcome.retry_count = len(outcome.attempts) - 1
        return outcome

    async def _repair_sql(
        self,
        sql: str,
        error,
        attempt_num: int,
    ) -> str:
        from ai.engine.llm.prompts import build_retry_prompt

        repair_content = build_retry_prompt(
            sql=sql,
            error_message=error.message,
            error_hint=error.hint,
            attempt=attempt_num,
        )
        repair_messages = list(self.messages) + [
            {"role": "user", "content": repair_content},
        ]

        try:
            resp = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=repair_messages,
                temperature=0.1,
            )
            content = resp.choices[0].message.content or ""

            sql_match = re.search(r"```sql\s*(.*?)```", content, re.I | re.S)
            if sql_match:
                fixed = sql_match.group(1).strip()
                logger.info(
                    f"LLM SQL repair  attempt={attempt_num + 1}  "
                    f"fixed={fixed[:80]!r}"
                )
                return fixed

            sel_match = re.search(r"\b(SELECT\s+.+?)(?:\n\n|$)", content, re.I | re.S)
            if sel_match:
                return sel_match.group(1).strip()

            logger.warning("LLM repair response contained no SQL block")
            return ""

        except Exception as exc:
            logger.warning(f"LLM SQL repair call failed: {exc}")
            return ""
