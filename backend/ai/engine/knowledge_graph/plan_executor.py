"""
PlanExecutor — Stage 12.

Executes a MultiStepPlan's DAG of steps:
  - Resolves dependencies (topological order)
  - Runs independent steps in parallel when KG_MULTI_STEP_PARALLEL is True
  - For each step: generates SQL via LLM, executes via ExecutionEngine + QueryRetryLoop
  - Evaluates branch_condition to decide whether to skip conditional steps
  - Persists step results and status to KgPlanStep rows

The executor reuses the existing single-query pipeline (QueryRetryLoop + ExecutionEngine)
for each individual step, so all retry/error-recovery behaviour is inherited.
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ai.engine.core.clock import utcnow
from ai.engine.core.config import get_settings
from ai.engine.knowledge_graph.engine import ExecutionEngine, ExecutionResult
from ai.engine.knowledge_graph.multi_step_planner import MultiStepPlan, StepSpec
from ai.engine.knowledge_graph.retry import QueryOutcome, QueryRetryLoop
from ai.models.knowledge_graph import KgPlanStep, KgQueryPlan
from ai.store import first

logger = logging.getLogger("pulse.knowledge_graph.plan_executor")


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class StepResult:
    """The outcome of executing a single step."""
    step_order: int
    intent: str
    sql: str = ""
    outcome: Optional[QueryOutcome] = None
    status: str = "pending"     # completed | failed | skipped
    error: str = ""
    duration_ms: int = 0
    rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PlanExecutionResult:
    """The outcome of executing the entire plan."""
    plan_id: str
    step_results: list[StepResult] = field(default_factory=list)
    succeeded: bool = False
    total_duration_ms: int = 0
    total_llm_calls: int = 0


# ── SQL generation prompt ─────────────────────────────────────────────────────

_STEP_SQL_PROMPT = """\
You are a SQL generation assistant. Generate a single PostgreSQL SELECT query for this step.

Step intent: {intent}
{dependency_context}

Respond with ONLY the SQL query inside a ```sql``` code fence. No explanation.
"""


class PlanExecutor:
    """Executes a multi-step query plan as a DAG."""

    def __init__(
        self,
        llm_client=None,
        model: str = "",
        instance_id: str = "",
        db=None,
        knowledge_context: str = "",
    ):
        self.llm_client = llm_client  # kept for backward compat; new code uses route_chat
        self.model = model
        self.instance_id = instance_id
        self.db = db
        self.knowledge_context = knowledge_context
        self._current_plan_id: str = ""

    async def execute(
        self,
        plan: MultiStepPlan,
        messages: list[dict],
    ) -> PlanExecutionResult:
        """
        Execute all steps in the plan, respecting dependencies.
        Returns the combined result.
        """
        settings = get_settings()
        t0 = time.perf_counter()
        total_llm = 0
        self._current_plan_id = plan.db_plan_id or ""

        # Build step lookup by step_order
        steps_by_order: dict[int, StepSpec] = {s.step_order: s for s in plan.steps}
        results_by_order: dict[int, StepResult] = {}

        # Topological execution: process levels of the DAG
        remaining = set(steps_by_order.keys())
        while remaining:
            # Find steps whose dependencies are all satisfied
            ready = []
            for order in remaining:
                spec = steps_by_order[order]
                deps = spec.depends_on
                if all(d in results_by_order for d in deps):
                    # Check branch condition
                    if spec.branch_condition:
                        if not _evaluate_branch(spec.branch_condition, results_by_order):
                            results_by_order[order] = StepResult(
                                step_order=order,
                                intent=spec.intent,
                                status="skipped",
                            )
                            continue
                    ready.append(order)

            if not ready:
                # All remaining steps have unsatisfied deps — break to avoid infinite loop
                for order in remaining:
                    results_by_order[order] = StepResult(
                        step_order=order,
                        intent=steps_by_order[order].intent,
                        status="failed",
                        error="Unsatisfied dependencies",
                    )
                break

            # Remove from remaining
            for order in ready:
                remaining.discard(order)
            # Also remove newly-skipped steps
            for order in list(remaining):
                if order in results_by_order:
                    remaining.discard(order)

            # Execute ready steps (parallel if enabled)
            if settings.KG_MULTI_STEP_PARALLEL and len(ready) > 1:
                tasks = [
                    self._execute_step(
                        steps_by_order[order], results_by_order, messages
                    )
                    for order in ready
                ]
                step_results = await asyncio.gather(*tasks, return_exceptions=True)
                for order, result in zip(ready, step_results):
                    if isinstance(result, Exception):
                        results_by_order[order] = StepResult(
                            step_order=order,
                            intent=steps_by_order[order].intent,
                            status="failed",
                            error=str(result),
                        )
                    else:
                        results_by_order[order] = result
                        total_llm += 1  # at least 1 LLM call per step
            else:
                for order in ready:
                    result = await self._execute_step(
                        steps_by_order[order], results_by_order, messages
                    )
                    results_by_order[order] = result
                    total_llm += 1

        # Compile results in step order
        ordered_results = sorted(results_by_order.values(), key=lambda r: r.step_order)
        all_ok = all(r.status in ("completed", "skipped") for r in ordered_results)

        total_ms = int((time.perf_counter() - t0) * 1000)

        result = PlanExecutionResult(
            plan_id=plan.db_plan_id or "",
            step_results=ordered_results,
            succeeded=all_ok,
            total_duration_ms=total_ms,
            total_llm_calls=total_llm,
        )

        # Persist plan completion
        if plan.db_plan_id:
            await self._update_plan_status(plan.db_plan_id, result)

        logger.info(
            "plan execution done  plan=%s  steps=%d  succeeded=%s  duration=%dms",
            plan.db_plan_id[:8] if plan.db_plan_id else "?",
            len(ordered_results), all_ok, total_ms,
        )

        return result

    async def _execute_step(
        self,
        spec: StepSpec,
        prior_results: dict[int, StepResult],
        messages: list[dict],
    ) -> StepResult:
        """Generate SQL for a step and execute it."""
        t0 = time.perf_counter()

        # Build dependency context from prior step results
        dep_context = ""
        if spec.depends_on:
            dep_parts = []
            for dep_order in spec.depends_on:
                dep_result = prior_results.get(dep_order)
                if dep_result and dep_result.rows:
                    # Summarize: first 5 rows
                    summary = json.dumps(dep_result.rows[:5], default=str)
                    dep_parts.append(
                        f"Step {dep_order} result ({dep_result.intent}): {summary}"
                    )
            dep_context = "Prior step results:\n" + "\n".join(dep_parts) if dep_parts else ""

        # Generate SQL via LLM
        sql = await self._generate_step_sql(spec.intent, dep_context, messages)
        if not sql:
            return StepResult(
                step_order=spec.step_order,
                intent=spec.intent,
                status="failed",
                error="Could not generate SQL for this step",
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )

        # Execute via retry loop
        engine = ExecutionEngine(self.instance_id)
        retry_loop = QueryRetryLoop(
            engine=engine,
            llm_client=self.llm_client,
            model=self.model,
            messages=messages,
        )
        outcome = await retry_loop.run(sql, plan=None)

        duration = int((time.perf_counter() - t0) * 1000)

        if outcome.succeeded and outcome.final_result:
            result = StepResult(
                step_order=spec.step_order,
                intent=spec.intent,
                sql=outcome.final_result.sql_executed,
                outcome=outcome,
                status="completed",
                duration_ms=duration,
                rows=outcome.final_result.rows,
            )
        else:
            error_msg = ""
            if outcome.final_result and outcome.final_result.error:
                error_msg = outcome.final_result.error.message
            result = StepResult(
                step_order=spec.step_order,
                intent=spec.intent,
                sql=sql,
                outcome=outcome,
                status="failed",
                error=error_msg,
                duration_ms=duration,
            )

        # Persist step result
        if self.db:
            await self._persist_step_result(spec, result)

        return result

    async def _generate_step_sql(
        self,
        intent: str,
        dep_context: str,
        messages: list[dict],
    ) -> str:
        """Ask LLM to generate SQL for a single plan step."""
        import re

        prompt = _STEP_SQL_PROMPT.format(
            intent=intent,
            dependency_context=dep_context or "No dependencies — this is the first step.",
        )

        # Include knowledge context in system message
        system_msg = messages[0]["content"] if messages else ""
        if self.knowledge_context:
            system_msg += "\n\n" + self.knowledge_context

        try:
            from ai.engine.llm.router import route_chat
            result = await route_chat(
                task="cognition",
                instance_id=self.instance_id,
                conversation_id=f"plan-execute-{step.step_id}",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            raw = result.get("content") or ""
        except Exception as e:
            logger.warning("Step SQL generation failed: %s", e)
            return ""

        # Extract SQL from response
        match = (
            re.search(r"```sql\s*(.*?)```", raw, re.I | re.S)
            or re.search(r"```\s*(SELECT.*?)```", raw, re.I | re.S)
        )
        if match:
            return match.group(1).strip()
        # Bare SELECT
        bare = re.search(r"\b(SELECT\s+.+?)(?:\n\n|$)", raw, re.I | re.S)
        return bare.group(1).strip() if bare else ""

    async def _persist_step_result(self, spec: StepSpec, result: StepResult):
        """Update the KgPlanStep row with execution results."""
        try:
            step_row = first(
                await self.db.select(
                    KgPlanStep,
                    ("plan_id", self._current_plan_id or ""),
                    ("step_order", spec.step_order),
                )
            )
            if step_row is None:
                return
            step_row.generated_sql = result.sql[:2000] if result.sql else None
            step_row.result_json = (
                json.dumps(result.rows[:20], default=str) if result.rows else None
            )
            step_row.status = result.status
            step_row.error_message = result.error[:1000] if result.error else None
            step_row.duration_ms = result.duration_ms
            await self.db.commit()
        except Exception as e:
            logger.debug("_persist_step_result failed: %s", e)

    async def _update_plan_status(self, plan_id: str, result: PlanExecutionResult):
        """Update the KgQueryPlan row with final status."""
        try:
            status = "completed" if result.succeeded else "failed"
            summary = json.dumps(
                [{"step": r.step_order, "status": r.status, "rows": len(r.rows)} for r in result.step_results],
                default=str,
            )
            plan_row = first(await self.db.select(KgQueryPlan, ("id", plan_id)))
            if plan_row is None:
                return
            plan_row.status = status
            plan_row.result_summary = summary
            plan_row.total_duration_ms = result.total_duration_ms
            plan_row.total_llm_calls = result.total_llm_calls
            plan_row.completed_at = utcnow()
            await self.db.commit()
        except Exception as e:
            logger.debug("_update_plan_status failed: %s", e)


# ── Branch evaluation helper ─────────────────────────────────────────────────

def _evaluate_branch(condition: str, prior_results: dict[int, StepResult]) -> bool:
    """
    Evaluate a simple branch condition against prior step results.
    Conditions are in the form: "step_0.row_count > 0" or "step_1.rows[0].status == 'active'"
    Returns True if the condition is met or cannot be parsed (fail-open).
    """
    try:
        # Simple row_count check: "step_N.row_count > 0"
        import re
        m = re.match(r"step_(\d+)\.row_count\s*(>|>=|<|<=|==|!=)\s*(\d+)", condition.strip())
        if m:
            step_order = int(m.group(1))
            op = m.group(2)
            threshold = int(m.group(3))
            result = prior_results.get(step_order)
            if not result:
                return True
            count = len(result.rows)
            ops = {">": count > threshold, ">=": count >= threshold,
                   "<": count < threshold, "<=": count <= threshold,
                   "==": count == threshold, "!=": count != threshold}
            return ops.get(op, True)
    except Exception:
        pass
    return True  # fail-open
