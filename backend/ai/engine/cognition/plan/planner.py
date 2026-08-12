"""
SkillAwarePlanner — Agentic multi-step plan decomposition using skills.

PR-20: This planner searches the SkillRegistry for matching skills and produces
a Plan with tool-centric PlanSteps (tool_name + tool_args from TOOL_EXECUTORS).
Falls back to LLM decomposition if no skill matches, and to single-step for
simple queries. Distinct from the SQL-focused MultiStepPlanner.
"""
import json
import logging
from dataclasses import dataclass, field

from ai.engine.core.config import get_settings

logger = logging.getLogger("pulse.cognition.plan.planner")


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class PlanStep:
    """One step in a multi-step agentic plan — NOT SQL, but tool-name + args."""
    step_id: int
    intent: str                     # natural-language description
    tool_name: str | None = None    # key in agent.tools.TOOL_EXECUTORS
    tool_args: dict = field(default_factory=dict)
    skill_name: str | None = None   # non-null if step came from a skill
    depends_on: list[int] = field(default_factory=list)
    is_mutation: bool = False
    dry_run_supported: bool = False


@dataclass
class Plan:
    """A decomposed agentic plan — consumed by ReActLoop."""
    pattern: str                    # "root_cause" | "comparative" | … | "custom"
    steps: list[PlanStep]
    synthesis_instruction: str
    source: str                     # "skill" | "llm_decompose" | "single_step"
    skill_name: str | None = None
    needs_confirmation: bool = False


# ── Keyword scoring ────────────────────────────────────────────────────────────

def _score_skill(skill, utterance_lower: str) -> float:
    """Score a skill against the utterance using simple keyword overlap.

    Returns 0.0–1.0 where higher = better match.
    """
    name_lower = skill.name.lower()
    desc_lower = (skill.description or "").lower()

    # Direct name match is strongest signal
    if name_lower in utterance_lower:
        return 0.95

    # Word overlap on name tokens
    name_tokens = set(name_lower.split())
    utterance_tokens = set(utterance_lower.split())
    name_hits = len(name_tokens & utterance_tokens)
    if name_hits > 0:
        return min(0.6 + name_hits * 0.1, 0.9)

    # Description overlap
    desc_tokens = set(desc_lower.split())
    desc_hits = len(desc_tokens & utterance_tokens)
    if desc_hits > 0:
        return min(0.3 + desc_hits * 0.1, 0.6)

    return 0.0


# ── LLM decompose prompt (agentic tool format, not SQL) ────────────────────────

_DECOMPOSE_AGENT_PROMPT = """\
You are an agentic planning assistant. The user asked a task that may need
multiple tool calls. Decompose it into sequential or parallel steps using the
available tools.

Available tools:
{tools_list}

Return ONLY valid JSON (no markdown, no fences):
{{
  "pattern": "<root_cause|comparative|custom>",
  "steps": [
    {{
      "step_id": 0,
      "intent": "<natural-language description>",
      "tool_name": "<one of the available tools>",
      "tool_args": {{}},
      "depends_on": [],
      "is_mutation": false
    }}
  ],
  "synthesis_instruction": "<how to combine steps into final answer>"
}}

Rules:
- Each step must use one of the available tools listed above.
- depends_on lists step_id values whose results are needed before this step.
- Steps with no dependencies can run in parallel.
- Keep plans small — prefer 2-4 steps.
- Set is_mutation: true only for steps that modify host state.

User task: {task}
"""


# ── Pattern signals (reused from the SQL planner, simplified) ──────────────────

_MULTI_SIGNALS: list[str] = [
    " and then ", " after that ", " followed by ",
    " also ", " additionally ", " as well as ",
    "compare", "root cause", "what if",
    " both ", " each ", "multi-step", "multiple steps",
]


def _looks_agent_multi_step(utterance: str) -> bool:
    """Does this utterance likely benefit from multi-step decomposition?"""
    lower = utterance.lower()
    return sum(1 for s in _MULTI_SIGNALS if s in lower) >= 1


# ── Planner ────────────────────────────────────────────────────────────────────

class SkillAwarePlanner:
    """Agentic planner — skill-first, LLM-fallback, single-step-final.

    Workflow:
      1. Search SkillRegistry for matching skills
      2. If a multi_step_plan skill matches → parse its body steps
      3. If utterance looks multi-step → LLM decompose
      4. Else → single-step passthrough
    """

    _MATCH_THRESHOLD = 0.5

    def __init__(self, llm_client=None, model: str = ""):
        self.llm_client = llm_client
        self.model = model

    async def decompose(
        self,
        utterance: str,
        skill_registry,          # SkillRegistry instance
        llm_client=None,
        model: str = "",
        instance_id: str = "",
        user_id: str = "",
    ) -> Plan:
        """Decompose utterance into a Plan.

        Args:
            utterance: the user's natural-language request
            skill_registry: SkillRegistry with AsyncSession
            llm_client: AsyncOpenAI client (uses self.llm_client if None)
            model: LLM model name (uses self.model if empty)
            instance_id: pulse instance id
            user_id: host user identifier (author_user_id)

        Returns:
            Plan — always non-None; source="single_step" for trivial queries
        """
        client = llm_client or self.llm_client
        model_name = model or self.model or ""

        # ── Step 1: search skills ───────────────────────────────────────────
        skills = await self._search_skills(skill_registry, instance_id, user_id)
        logger.debug(
            "SkillAwarePlanner: found %d skills for instance=%s user=%s",
            len(skills), instance_id, user_id,
        )

        # ── Step 2: score and match ─────────────────────────────────────────
        utterance_lower = utterance.lower()
        scored = [(s, _score_skill(s, utterance_lower)) for s in skills]
        scored.sort(key=lambda pair: pair[1], reverse=True)

        if scored and scored[0][1] >= self._MATCH_THRESHOLD:
            top_skill, top_score = scored[0]
            logger.info(
                "SkillAwarePlanner: matched skill=%s score=%.2f kind=%s",
                top_skill.name, top_score, top_skill.kind,
            )
            if top_skill.kind == "multi_step_plan":
                plan = self._parse_skill_plan(top_skill)
                if plan and plan.steps:
                    logger.info("SkillAwarePlanner: using skill plan '%s'", top_skill.name)
                    return plan

        # ── Step 3: LLM decomposition fallback ──────────────────────────────
        if _looks_agent_multi_step(utterance) and client is not None:
            plan = await self._llm_decompose(utterance, client, model_name, instance_id=instance_id)
            if plan and plan.steps:
                logger.info("SkillAwarePlanner: LLM decomposition returned %d steps", len(plan.steps))
                return plan

        # ── Step 4: single-step passthrough ─────────────────────────────────
        logger.debug("SkillAwarePlanner: single-step passthrough for utterance")
        return Plan(
            pattern="custom",
            steps=[PlanStep(step_id=0, intent=utterance)],
            synthesis_instruction="Respond directly to the user.",
            source="single_step",
        )

    # ── helpers ─────────────────────────────────────────────────────────────

    async def _search_skills(self, skill_registry, instance_id: str, user_id: str) -> list:
        """Return all skills available to this user: draft + user_approved + promoted."""
        skills: list = []
        if skill_registry is None:
            return skills
        try:
            # Use search with empty query to get promoted + user's own
            skills = await skill_registry.search(instance_id, user_id, "")
            logger.debug("Skill search returned %d skills", len(skills))
        except Exception:
            logger.exception("Skill search failed")
        return skills

    def _parse_skill_plan(self, skill) -> Plan | None:
        """Parse a multi_step_plan skill body into a Plan."""
        try:
            body = skill.body
            if isinstance(body, str):
                body = json.loads(body)
            steps_data = body.get("steps", [])
            steps = []
            for i, s in enumerate(steps_data):
                step = PlanStep(
                    step_id=s.get("step_id", i),
                    intent=s.get("intent", ""),
                    tool_name=s.get("tool_name"),
                    tool_args=s.get("tool_args", {}),
                    skill_name=skill.name,
                    depends_on=s.get("depends_on", []),
                    is_mutation=s.get("is_mutation", False),
                    dry_run_supported=s.get("dry_run_supported", False),
                )
                steps.append(step)
            return Plan(
                pattern=body.get("pattern", "custom"),
                steps=steps,
                synthesis_instruction=body.get("synthesis_instruction", ""),
                source="skill",
                skill_name=skill.name,
                needs_confirmation=any(s.is_mutation for s in steps),
            )
        except Exception:
            logger.exception("Failed to parse skill body for '%s'", skill.name)
            return None

    async def _llm_decompose(self, utterance: str, llm_client, model: str, instance_id: str = "") -> Plan | None:
        """Use LLM to decompose utterance into agentic steps."""
        from ai.engine.llm.router import route_chat
        from ai.engine.agent.tools import get_tool_executors

        _execs = await get_tool_executors()
        tool_names = sorted(_execs.keys())
        tools_list = "\n".join(f"- {n}" for n in tool_names)
        prompt = _DECOMPOSE_AGENT_PROMPT.format(tools_list=tools_list, task=utterance)

        try:
            router_result = await route_chat(
                task="cognition",
                instance_id=instance_id,
                conversation_id=f"plan-decompose-{instance_id}",
                messages=[
                    {"role": "system", "content": "You are an agentic planning assistant. Respond with JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            raw = router_result["content"] or ""
        except Exception as e:
            logger.warning("LLM decomposition call failed: %s", e)
            return None

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown fences
            if "```" in raw:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    try:
                        parsed = json.loads(raw[start:end])
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse plan JSON from LLM response")
                        return None
                else:
                    return None
            else:
                logger.warning("Failed to parse plan JSON from LLM response")
                return None

        steps_data = parsed.get("steps", [])
        steps = []
        for s in steps_data:
            step = PlanStep(
                step_id=s.get("step_id", 0),
                intent=s.get("intent", ""),
                tool_name=s.get("tool_name"),
                tool_args=s.get("tool_args", {}),
                depends_on=s.get("depends_on", []),
                is_mutation=s.get("is_mutation", False),
                dry_run_supported=s.get("dry_run_supported", False),
            )
            steps.append(step)

        # Validate tool names
        from ai.engine.agent.tools import get_tool_executors
        _vexecs = await get_tool_executors()
        for step in steps:
            if step.tool_name and step.tool_name not in _vexecs:
                logger.warning(
                    "LLM returned unknown tool_name=%r, stripping", step.tool_name,
                )
                step.tool_name = None

        return Plan(
            pattern=parsed.get("pattern", "custom"),
            steps=steps,
            synthesis_instruction=parsed.get("synthesis_instruction", ""),
            source="llm_decompose",
            needs_confirmation=any(s.is_mutation for s in steps),
        )
