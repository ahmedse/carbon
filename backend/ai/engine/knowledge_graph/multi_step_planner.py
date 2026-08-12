"""
MultiStepPlanner — Stage 12.

Detects multi-step questions, decomposes them into a DAG of PlanSteps,
assigns a pattern label, and persists the plan in the database.

Patterns:
  root_cause     — "why did X change?" → fetch metric, group by dimensions, compare periods
  forecast_eval  — "how accurate was the forecast?" → fetch forecast, fetch actual, compute diff
  comparative    — "compare A vs B across C" → fetch each partition, combine
  threshold      — "which items exceed X?" → compute aggregate, filter
  what_if        — "what if we changed X?" → base metric, apply adjustment, compare
  custom         — anything that needs ≥ 2 sequential queries but doesn't match a pattern

The planner relies on the LLM to decompose the question, but uses heuristic
pattern matching first to guide the decomposition prompt.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.config import get_settings

logger = logging.getLogger("pulse.knowledge_graph.multi_step_planner")


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class StepSpec:
    """An in-memory step before it's persisted."""
    step_order: int
    intent: str
    depends_on: list[int] = field(default_factory=list)   # step_order indices
    branch_condition: Optional[str] = None


@dataclass
class MultiStepPlan:
    """A decomposed multi-step plan (in-memory representation)."""
    pattern: str
    steps: list[StepSpec]
    synthesis_instruction: str
    db_plan_id: Optional[str] = None   # set after persistence
    needs_confirmation: bool = False    # when step_count >= confirm_threshold


# ── Pattern heuristics ────────────────────────────────────────────────────────

_PATTERN_SIGNALS: dict[str, list[str]] = {
    "root_cause": [
        "why did", "why is", "why are", "what caused", "root cause",
        "reason for", "explain the change", "what drove", "what led to",
    ],
    "forecast_eval": [
        "forecast accuracy", "how accurate", "actual vs forecast",
        "predicted vs actual", "forecast error", "forecast evaluation",
        "compare forecast", "prediction accuracy",
    ],
    "comparative": [
        "compare", "comparison", "versus", " vs ", "difference between",
        "how does .* compare", "side by side", "relative to",
    ],
    "threshold": [
        "exceed", "above", "below", "over the limit", "threshold",
        "which .* more than", "which .* less than", "greater than",
        "violat", "breach",
    ],
    "what_if": [
        "what if", "what would happen", "if we changed", "hypothetical",
        "scenario", "simulate", "if .* were",
    ],
}


def detect_pattern(utterance: str) -> Optional[str]:
    """Return the best-matching pattern or None if single-step."""
    lower = utterance.lower()
    scores: dict[str, int] = {}
    for pattern, signals in _PATTERN_SIGNALS.items():
        count = sum(1 for s in signals if s in lower)
        if count:
            scores[pattern] = count
    if not scores:
        return None
    return max(scores, key=scores.get)


# These phrases indicate the query can be answered by the host API directly —
# never route them to the SQL multi-step planner.
_API_SERVABLE_SIGNALS: list[str] = [
    "feature", "xai", "explai", "why did the model", "why did it predict",
    "forecast accuracy", "mape", "error stat", "prediction accuracy",
    "latest prediction", "latest forecast", "latest power forecast",
    "inference run", "show me the forecast", "show me predictions",
    "show forecast", "feature importance", "top driver", "top factor",
]


def _is_api_servable(utterance: str) -> bool:
    """Return True if the question should be answered via the API, not SQL."""
    lower = utterance.lower()
    return any(sig in lower for sig in _API_SERVABLE_SIGNALS)


def looks_multi_step(utterance: str) -> bool:
    """Quick heuristic: does this question likely need multiple SQL queries?"""
    # If the question is better served by the host API, never use SQL planning.
    if _is_api_servable(utterance):
        return False
    lower = utterance.lower()
    # Multi-clause connectors — kept intentionally conservative so that single-
    # topic questions (even when they mention "forecast") go to the agent tool loop.
    multi_signals = [
        " and then ", " after that ", " followed by ",
        " also show ", " also get ", " additionally ",
        " as well as ",
        "compare", "root cause",
        "what if",
        " both ", " each ",
    ]
    hits = sum(1 for s in multi_signals if s in lower)
    # Only use detect_pattern if at least one multi-signal also fired — this
    # prevents "why did" alone from triggering an expensive SQL plan.
    return hits >= 1 or (hits >= 1 and detect_pattern(lower) is not None)


# ── LLM-based decomposition ──────────────────────────────────────────────────

_DECOMPOSE_PROMPT = """\
You are a query planning assistant. The user asked a complex data question.
Decompose it into a small sequence of SQL query steps (2-6 steps).

Return ONLY valid JSON (no markdown, no fences):
{{
  "pattern": "<root_cause|forecast_eval|comparative|threshold|what_if|custom>",
  "steps": [
    {{
      "step_order": 0,
      "intent": "<natural-language description of what this step fetches>",
      "depends_on": [],
      "branch_condition": null
    }},
    ...
  ],
  "synthesis_instruction": "<how to combine the step results into a final answer>"
}}

Rules:
- Each step should produce one SQL query.
- depends_on lists step_order values whose results are needed before this step.
- Steps with no dependencies can run in parallel.
- Keep the plan as small as possible. Prefer 2-3 steps.
- branch_condition is optional: a condition on a prior step's result that decides if this step should run.

User question: {question}
Known entities: {entities}
"""


class MultiStepPlanner:
    """Detects and decomposes multi-step queries."""

    def __init__(self, llm_client=None, model: str = "", instance_id: str = ""):
        self.llm_client = llm_client  # kept for backward compat
        self.model = model
        self.instance_id = instance_id

    async def should_plan(self, utterance: str) -> bool:
        """Quick check — is multi-step planning justified?"""
        settings = get_settings()
        if not settings.KG_MULTI_STEP_ENABLED:
            return False
        return looks_multi_step(utterance)

    async def decompose(
        self,
        utterance: str,
        entity_names: list[str],
        instance_id: str,
        conversation_id: str,
        db: AsyncSession,
    ) -> Optional[MultiStepPlan]:
        """
        Ask the LLM to decompose the question into a multi-step plan.
        Persists the plan and returns the in-memory representation.
        """
        settings = get_settings()
        max_steps = settings.KG_MULTI_STEP_MAX_STEPS

        prompt = _DECOMPOSE_PROMPT.format(
            question=utterance,
            entities=", ".join(entity_names[:20]) if entity_names else "unknown",
        )

        try:
            from ai.engine.llm.router import route_chat
            result = await route_chat(
                task="cognition",
                instance_id=instance_id or self.instance_id,
                conversation_id=f"decompose-{conversation_id}",
                messages=[
                    {"role": "system", "content": "You are a data query planning assistant. Respond with JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            raw = result.get("content") or ""
        except Exception as e:
            logger.warning("LLM decomposition call failed: %s", e)
            return None

        # Parse LLM JSON response
        parsed = _parse_plan_json(raw)
        if parsed is None:
            logger.warning("Failed to parse plan JSON from LLM response")
            return None

        pattern = parsed.get("pattern", "custom")
        # Fall back to heuristic pattern if LLM didn't pick one
        if pattern not in ("root_cause", "forecast_eval", "comparative", "threshold", "what_if", "custom"):
            pattern = detect_pattern(utterance) or "custom"

        raw_steps = parsed.get("steps", [])
        if not raw_steps or len(raw_steps) > max_steps:
            logger.warning("Plan has %d steps (max %d), skipping", len(raw_steps), max_steps)
            return None

        steps = []
        for s in raw_steps:
            steps.append(StepSpec(
                step_order=int(s.get("step_order", len(steps))),
                intent=str(s.get("intent", "")),
                depends_on=[int(d) for d in s.get("depends_on", [])],
                branch_condition=s.get("branch_condition"),
            ))

        synthesis_instruction = parsed.get("synthesis_instruction", "Combine results to answer the question.")

        plan = MultiStepPlan(
            pattern=pattern,
            steps=steps,
            synthesis_instruction=synthesis_instruction,
            needs_confirmation=len(steps) >= settings.KG_MULTI_STEP_CONFIRM_THRESHOLD,
        )

        # Persist to DB
        plan.db_plan_id = await _persist_plan(
            db, instance_id, conversation_id, utterance, plan
        )

        logger.info(
            "multi-step plan created  instance=%s  pattern=%s  steps=%d  plan_id=%s",
            instance_id, pattern, len(steps), plan.db_plan_id[:8] if plan.db_plan_id else "?",
        )
        return plan


# ── Persistence ───────────────────────────────────────────────────────────────

async def _persist_plan(
    db: AsyncSession,
    instance_id: str,
    conversation_id: str,
    utterance: str,
    plan: MultiStepPlan,
) -> str:
    """Write KgQueryPlan and KgPlanStep rows. Return the plan ID."""
    from ai.engine.knowledge_graph.models import KgPlanStep, KgQueryPlan

    plan_row = KgQueryPlan(
        instance_id=instance_id,
        conversation_id=conversation_id,
        original_utterance=utterance[:2000],
        pattern=plan.pattern,
        step_count=len(plan.steps),
        status="planned",
        synthesis_instruction=plan.synthesis_instruction[:2000],
    )
    db.add(plan_row)
    await db.flush()  # get plan_row.id

    for s in plan.steps:
        step_row = KgPlanStep(
            plan_id=plan_row.id,
            step_order=s.step_order,
            intent=s.intent[:1000],
            depends_on=json.dumps(s.depends_on),
            branch_condition=s.branch_condition,
            status="pending",
        )
        db.add(step_row)

    await db.commit()
    return plan_row.id


# ── JSON parsing helper ──────────────────────────────────────────────────────

def _parse_plan_json(text: str) -> Optional[dict]:
    """Extract and parse JSON from LLM response, tolerating markdown fences."""
    import re
    # Try direct parse first
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    # Try extracting from code fences
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Last resort: find first { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None
