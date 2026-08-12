"""
PlanSynthesizer — Stage 12.

Combines the results of multiple plan steps into a single coherent answer.
Uses the LLM to produce a natural-language summary grounded in the step data,
along with a merged structured answer (combined rows, shape, viz hint).

This is the final stage of the multi-step pipeline: after PlanExecutor runs
all steps, PlanSynthesizer produces the response the user sees.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from ai.engine.knowledge_graph.plan_executor import PlanExecutionResult, StepResult
from ai.engine.knowledge_graph.synthesis import (
    ShapeType,
    SynthesizedAnswer,
    VisualizationHint,
    VizType,
)

logger = logging.getLogger("pulse.knowledge_graph.plan_synthesizer")


# ── Synthesis prompt ──────────────────────────────────────────────────────────

_SYNTHESIS_PROMPT = """\
You executed a multi-step data query plan for the user's question.
Below are the step results. Combine them into a clear, concise answer.

User question: {question}
Synthesis instruction: {instruction}

Step results:
{step_summaries}

Rules:
- Ground your answer in the actual data. Cite specific numbers.
- If a step failed, acknowledge it briefly and answer with what succeeded.
- Be concise — aim for 2-4 sentences unless the data warrants more detail.
- Do NOT include SQL in your response.
"""


class PlanSynthesizer:
    """Synthesizes multi-step execution results into a single answer."""

    def __init__(self, llm_client=None, model: str = "", instance_id: str = ""):
        self.llm_client = llm_client  # kept for backward compat
        self.model = model
        self.instance_id = instance_id

    async def synthesize(
        self,
        question: str,
        plan_result: PlanExecutionResult,
        synthesis_instruction: str = "",
    ) -> SynthesizedAnswer:
        """
        Produce a SynthesizedAnswer from the combined plan results.
        """
        step_results = plan_result.step_results
        completed = [r for r in step_results if r.status == "completed" and r.rows]

        if not completed:
            # All steps failed or returned no data
            return SynthesizedAnswer(
                answer_text="I wasn't able to retrieve the data needed to answer that question. "
                           "Some of the query steps failed.",
                shape=ShapeType.EMPTY.value,
                retry_count=sum(
                    r.outcome.retry_count if r.outcome else 0 for r in step_results
                ),
            )

        # Build step summaries for the LLM
        step_summaries = _build_step_summaries(step_results)

        # Ask LLM to synthesize
        answer_text = await self._llm_synthesize(
            question, synthesis_instruction, step_summaries
        )

        # Build merged structured data from completed steps
        merged = _merge_step_data(completed)

        # Compute shape and viz hint from merged data
        shape = _classify_merged_shape(merged)
        viz_hint = _suggest_merged_viz(merged, shape)

        total_retries = sum(
            r.outcome.retry_count if r.outcome else 0 for r in step_results
        )

        return SynthesizedAnswer(
            answer_text=answer_text,
            shape=shape.value,
            row_count=len(merged["rows"]),
            columns=merged["columns"],
            rows=merged["rows"],
            viz_hint=viz_hint,
            truncated=False,
            retry_count=total_retries,
            provenance=[r.intent for r in completed],
        )

    async def _llm_synthesize(
        self,
        question: str,
        instruction: str,
        step_summaries: str,
    ) -> str:
        """Ask the LLM to produce a natural-language synthesis."""
        prompt = _SYNTHESIS_PROMPT.format(
            question=question,
            instruction=instruction or "Combine step results into a coherent answer.",
            step_summaries=step_summaries,
        )

        try:
            from ai.engine.llm.router import route_chat
            result = await route_chat(
                task="cognition",
                instance_id=self.instance_id or "system",
                conversation_id=f"synthesize-{self.instance_id or 'system'}",
                messages=[
                    {"role": "system", "content": "You are a data analysis assistant. Summarize query results clearly and concisely."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            return (result.get("content") or "").strip()
        except Exception as e:
            logger.warning("LLM synthesis failed: %s", e)
            # Fall back to mechanical summary
            return _fallback_summary(question, step_summaries)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_step_summaries(step_results: list[StepResult]) -> str:
    """Build a formatted string of step results for the LLM prompt."""
    parts = []
    for r in step_results:
        status_label = r.status.upper()
        if r.status == "completed" and r.rows:
            # Show first 10 rows as a compact table
            preview = json.dumps(r.rows[:10], default=str)
            parts.append(
                f"Step {r.step_order} ({r.intent}) — {status_label}\n"
                f"  Rows returned: {len(r.rows)}\n"
                f"  Data preview: {preview}"
            )
        elif r.status == "failed":
            parts.append(
                f"Step {r.step_order} ({r.intent}) — {status_label}\n"
                f"  Error: {r.error}"
            )
        elif r.status == "skipped":
            parts.append(
                f"Step {r.step_order} ({r.intent}) — SKIPPED (branch condition not met)"
            )
        else:
            parts.append(f"Step {r.step_order} ({r.intent}) — {status_label}")
    return "\n\n".join(parts)


def _merge_step_data(completed: list[StepResult]) -> dict[str, Any]:
    """
    Merge rows from completed steps.
    If all steps share the same columns, concatenate rows.
    Otherwise, keep each step's rows as separate labeled sections.
    """
    if len(completed) == 1:
        rows = completed[0].rows
        columns = list(rows[0].keys()) if rows else []
        return {"columns": columns, "rows": [list(r.values()) for r in rows]}

    # Check if columns are compatible
    col_sets = [frozenset(r.rows[0].keys()) if r.rows else frozenset() for r in completed]
    all_same = len(set(col_sets)) == 1 and col_sets[0]

    if all_same:
        columns = list(completed[0].rows[0].keys())
        all_rows = []
        for r in completed:
            for row in r.rows:
                all_rows.append([row.get(c) for c in columns])
        return {"columns": columns, "rows": all_rows}

    # Different schemas — add a "step" label column
    all_columns: list[str] = ["_step"]
    column_set: set[str] = set()
    for r in completed:
        if r.rows:
            for k in r.rows[0].keys():
                if k not in column_set:
                    column_set.add(k)
                    all_columns.append(k)

    all_rows = []
    for r in completed:
        for row in r.rows:
            merged_row = [r.intent]
            for c in all_columns[1:]:
                merged_row.append(row.get(c))
            all_rows.append(merged_row)

    return {"columns": all_columns, "rows": all_rows}


def _classify_merged_shape(merged: dict) -> ShapeType:
    """Classify the shape of merged data."""
    rows = merged["rows"]
    cols = merged["columns"]
    if not rows:
        return ShapeType.EMPTY
    if len(rows) == 1 and len(cols) == 1:
        return ShapeType.SCALAR
    if len(rows) == 1:
        return ShapeType.KPIS
    return ShapeType.TABLE


def _suggest_merged_viz(
    merged: dict, shape: ShapeType
) -> Optional[VisualizationHint]:
    """Suggest visualization for merged data."""
    if shape == ShapeType.EMPTY:
        return None
    if shape == ShapeType.SCALAR:
        return VisualizationHint(viz_type=VizType.STAT.value, title="Result")
    if shape == ShapeType.KPIS:
        return VisualizationHint(viz_type=VizType.STAT.value, title="Key Metrics")
    cols = merged["columns"]
    rows = merged["rows"]
    if len(cols) >= 2 and len(rows) >= 2:
        return VisualizationHint(
            viz_type=VizType.BAR.value,
            x_axis=cols[0],
            y_axis=cols[1] if len(cols) > 1 else None,
            title="Comparison",
        )
    return VisualizationHint(viz_type=VizType.TABLE.value, title="Results")


def _fallback_summary(question: str, step_summaries: str) -> str:
    """Produce a simple mechanical summary when LLM synthesis fails."""
    return (
        f"Here are the results for your question.\n\n"
        f"Step details:\n{step_summaries}"
    )
