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
    agent_role: str = "orchestrator"   # AGENT_ROLES value — who executes this step


@dataclass
class PlanPhase:
    """A named stage of a plan grouping steps under a strategy.

    ``strategy`` is "sequential" (steps run one at a time, in order) or
    "parallel" (independent steps run concurrently). ``step_ids`` reference
    PlanStep.step_id values in this phase. Phases give the plan a workflow
    shape beyond a flat step list — visible in chat proposals and the Tasks
    panel DAG.
    """
    phase_id: int = 0
    name: str = ""
    goal: str = ""
    strategy: str = "sequential"      # "sequential" | "parallel"
    step_ids: list[int] = field(default_factory=list)


@dataclass
class Plan:
    """A decomposed agentic plan — consumed by ReActLoop."""
    pattern: str                    # "root_cause" | "comparative" | … | "custom"
    steps: list[PlanStep]
    synthesis_instruction: str
    source: str                     # "skill" | "llm_decompose" | "single_step"
    skill_name: str | None = None
    needs_confirmation: bool = False
    phases: list[PlanPhase] = field(default_factory=list)  # workflow stages


# ── Keyword scoring ────────────────────────────────────────────────────────────

def _score_skill(skill, utterance_lower: str) -> float:
    """Score a skill against the utterance using simple keyword overlap.

    Returns 0.0–1.0 where higher = better match.
    """
    name_lower = skill.name.lower()
    desc_lower = (skill.description or "").lower()

    # Direct name match is strongest signal
    if name_lower in utterance_lower:
        score = 0.95
    # Word overlap on name tokens
    else:
        name_tokens = set(name_lower.split())
        utterance_tokens = set(utterance_lower.split())
        name_hits = len(name_tokens & utterance_tokens)
        if name_hits > 0:
            score = min(0.6 + name_hits * 0.1, 0.9)
        else:
            # Description overlap
            desc_tokens = set(desc_lower.split())
            desc_hits = len(desc_tokens & utterance_tokens)
            if desc_hits > 0:
                score = min(0.3 + desc_hits * 0.1, 0.6)
            else:
                score = 0.0

    # Learnt-signal boost (W4-D): skills with a proven success record rank
    # above cold matches at equal keyword overlap. Pure read — never writes.
    if getattr(skill, "success_rate", 0) and getattr(skill, "usage_count", 0):
        boost = min(0.1, 0.05 + 0.05 * float(skill.success_rate))
        if skill.usage_count >= 3 and skill.success_rate >= 0.75:
            boost = min(0.15, boost + 0.05)
        return min(score + boost, 0.99)
    return score


# ── LLM decompose prompt (agentic tool format, not SQL) ────────────────────────

_DECOMPOSE_AGENT_PROMPT = """\
You are an agentic planning assistant. The user asked a task that may need
multiple tool calls. Decompose it into phases (workflow stages) and steps.

Available tools:
{tools_list}

Registered skills (for invoke_skill only — exact names):
{skills_list}

Return ONLY valid JSON (no markdown, no fences):
{{
  "pattern": "<root_cause|comparative|custom>",
  "phases": [
    {{
      "phase_id": 0,
      "name": "<short stage name, e.g. Research>",
      "goal": "<what this stage accomplishes>",
      "strategy": "<sequential|parallel>",
      "step_ids": [0, 1]
    }}
  ],
  "steps": [
    {{
      "step_id": 0,
      "intent": "<natural-language description>",
      "tool_name": "<one of the available tools>",
      "tool_args": {{}},
      "depends_on": [],
      "is_mutation": false,
      "agent_role": "<orchestrator|researcher|domain_specialist>"
    }}
  ],
  "synthesis_instruction": "<how to combine steps into final answer>"
}}

Rules:
- Each step must use one of the available tools listed above.
- invoke_skill may ONLY reference an exact name from the Registered skills
  list. NEVER invent a skill name — if no skill matches, do not use
  invoke_skill at all.
- Analysis, comparison, synthesis and other REASONING steps are NOT skills:
  they are done by the LLM itself. For such a step use a real tool to gather
  the raw inputs it needs, then set "tool_name": null and
  "agent_role": "domain_specialist" so the model reasons directly from the
  prior step results (available via depends_on).
- depends_on lists step_id values whose results are needed before this step.
- Steps with no dependencies can run in parallel.
- Group steps into 2-4 phases that tell a workflow story: research/collect
  first, then analyze, then produce output. Keep plans small — prefer 4-7
  total steps. A single phase is fine for simple jobs.
- strategy "parallel" only when the phase's steps are truly independent;
  otherwise "sequential".
- agent_role selects who executes the step: "researcher" for read-only
  internet/knowledge research, "domain_specialist" for deep domain
  expertise, "orchestrator" for everything else (the main agent).
- Set is_mutation: true only for steps that modify host state.

User task: {task}
"""


# ── Pattern signals (reused from the SQL planner, simplified) ──────────────────

# Sequential / explicit "do several things" signals.
_MULTI_SIGNALS: list[str] = [
    " and then ", " after that ", " followed by ",
    " also ", " additionally ", " as well as ",
    "root cause", "what if",
    " both ", " each ", "multi-step", "multiple steps",
]

# Explicit requests to plan / convert a conversation into a task. These are the
# strongest signal that the user wants decomposition, NOT a prose answer.
_PLAN_SIGNALS: list[str] = [
    "plan a ", "plan the ", "plan this", "plan an ", "plan my ",
    "make a plan", "create a plan", "draft a plan", "build a plan",
    "set up a task", "create a task", "make a task", "turn this into a task",
    "convert this into a task", "convert what we talk", "as a task",
    "break it down", "break this down", "decompose",
]

# Task verbs that imply a multi-step job (stemmed so inflections match:
# "compar" → compare/comparing/comparison/comparative; "analy" → analyze/analysis).
_TASK_VERB_STEMS: list[str] = [
    "compar", "study", "audit", "investigate", "research", "analyz", "analy",
    "assess", "evaluate", "reconcile", "benchmark", "orchestrat", "workflow",
]

# ── Deterministic mutation classification ─────────────────────────────────
# A step that writes host state (files, DB rows, host APIs) MUST carry
# is_mutation=True so the ReAct loop's pre-execution consent gate pauses it
# (RULE_21 — never auto-mutate). The LLM's decompose output is advisory only:
# it routinely marks mutation steps is_mutation=False (the export step in the
# Sprint-18 E2E was marked False and would have run without consent). Mutation
# is a CAPABILITY FACT of the tool, not a reasoning output — so the planner
# overrides it deterministically here.
#
# Tools excluded: those with their own tool-level staging
# (requires_confirmation=True) — call_host_api (non-GET), create_dq_rule,
# learn_fact, forget_fact, run_ops_workflow — already gate at execution time;
# marking them is_mutation here would double-gate. export_document writes
# files with requires_confirmation=False, so it relies on this gate.
_MUTATION_TOOL_NAMES: set[str] = {"export_document"}


def _looks_agent_multi_step(utterance: str) -> bool:
    """Does this utterance likely benefit from multi-step decomposition?

    True when the user (a) explicitly asks to plan / convert into a task,
    (b) names a multi-step job verb (compare, audit, study, …), or (c) uses a
    sequential connective.  A bare factual question ("what is X?") stays
    single-step so it answers with prose instead of burning an LLM decompose.
    """
    lower = utterance.lower()
    if any(s in lower for s in _MULTI_SIGNALS):
        return True
    if any(s in lower for s in _PLAN_SIGNALS):
        return True
    return any(stem in lower for stem in _TASK_VERB_STEMS)


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
            plan = await self._llm_decompose(
                utterance, client, model_name,
                instance_id=instance_id, skills=skills,
            )
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
            phases=[PlanPhase(
                phase_id=0, name="All steps", goal="",
                strategy="sequential", step_ids=[0],
            )],
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
                # Deterministic mutation classification (capability fact) —
                # never trust authorial is_mutation for write-capable tools.
                if step.tool_name in _MUTATION_TOOL_NAMES:
                    step.is_mutation = True
                steps.append(step)
            return Plan(
                pattern=body.get("pattern", "custom"),
                steps=steps,
                synthesis_instruction=body.get("synthesis_instruction", ""),
                source="skill",
                skill_name=skill.name,
                needs_confirmation=any(s.is_mutation for s in steps),
                phases=self._parse_phases(body, steps),
            )
        except Exception:
            logger.exception("Failed to parse skill body for '%s'", skill.name)
            return None

    async def _llm_decompose(
        self, utterance: str, llm_client, model: str, instance_id: str = "",
        skills: list | None = None,
    ) -> Plan | None:
        """Use LLM to decompose utterance into agentic steps."""
        from ai.engine.llm.router import route_chat
        from ai.engine.agent.tools import get_tool_executors

        _execs = await get_tool_executors()
        tool_names = sorted(_execs.keys())
        tools_list = "\n".join(f"- {n}" for n in tool_names)

        # Only advertise real, registered skills — the LLM must never invent
        # a skill name for invoke_skill (reasoning is the LLM's job, not a
        # skill). If no skills are registered, state that clearly.
        skill_names = sorted({s.name for s in (skills or [])})
        skills_list = (
            "\n".join(f"- {n}" for n in skill_names)
            if skill_names
            else "- (none registered — do NOT use invoke_skill)"
        )
        prompt = _DECOMPOSE_AGENT_PROMPT.format(
            tools_list=tools_list, skills_list=skills_list, task=utterance,
        )

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
                agent_role=s.get("agent_role", "orchestrator"),
            )
            steps.append(step)

        # Validate tool names
        from ai.engine.agent.tools import get_tool_executors
        _vexecs = await get_tool_executors()
        _skill_names = {s.name for s in (skills or [])}
        for step in steps:
            if step.tool_name and step.tool_name not in _vexecs:
                logger.warning(
                    "LLM returned unknown tool_name=%r, stripping", step.tool_name,
                )
                step.tool_name = None
            # invoke_skill must reference a REAL registered skill. If the LLM
            # invented a name, downgrade the step to a pure reasoning step
            # (LLM does the thinking — comparison/analysis is not a skill).
            if step.tool_name == "invoke_skill":
                _sn = (step.tool_args or {}).get("skill_name", "")
                if _sn not in _skill_names:
                    logger.warning(
                        "LLM referenced unregistered skill_name=%r for "
                        "invoke_skill; downgrading step %d to reasoning",
                        _sn, step.step_id,
                    )
                    step.tool_name = None
                    step.agent_role = step.agent_role or "domain_specialist"

        # Deterministic mutation classification — a capability fact of the
        # tool, NOT the LLM's judgment. The LLM routinely under-marks mutation
        # steps (Sprint-18 E2E: export marked is_mutation=False), which would
        # bypass the loop's pre-execution consent gate. Override here.
        for step in steps:
            if step.tool_name in _MUTATION_TOOL_NAMES:
                step.is_mutation = True

        # Validate / coerce agent roles against AGENT_ROLES.
        from ai.engine.core.models import AGENT_ROLES
        for step in steps:
            if step.agent_role not in AGENT_ROLES:
                step.agent_role = "orchestrator"

        # Phases: prefer explicit phases from the LLM; fall back to a single
        # "All steps" phase so downstream phase-aware rendering always works.
        phases = self._parse_phases(parsed, steps)

        return Plan(
            pattern=parsed.get("pattern", "custom"),
            steps=steps,
            synthesis_instruction=parsed.get("synthesis_instruction", ""),
            source="llm_decompose",
            needs_confirmation=any(s.is_mutation for s in steps),
            phases=phases,
        )

    @staticmethod
    def _parse_phases(parsed: dict, steps: list[PlanStep]) -> list[PlanPhase]:
        """Parse ``phases`` from an LLM decomposition result with a safe
        fallback: if the LLM omitted phases (older model / non-compliant
        JSON), derive a minimal single-phase shape from the steps.

        Steps listed in no phase are appended to a trailing "Remaining"
        phase so no step ever disappears from the workflow view.
        """
        raw_phases = parsed.get("phases") or []
        valid_ids = {s.step_id for s in steps}

        phases: list[PlanPhase] = []
        claimed: set[int] = set()
        if isinstance(raw_phases, list):
            for i, p in enumerate(raw_phases):
                if not isinstance(p, dict):
                    continue
                step_ids = [
                    int(sid) for sid in (p.get("step_ids") or [])
                    if isinstance(sid, (int, str)) and str(sid).isdigit()
                ]
                step_ids = [sid for sid in step_ids if sid in valid_ids]
                strategy = p.get("strategy", "sequential")
                if strategy not in ("sequential", "parallel"):
                    strategy = "sequential"
                phases.append(PlanPhase(
                    phase_id=i,
                    name=p.get("name") or f"Phase {i + 1}",
                    goal=p.get("goal") or "",
                    strategy=strategy,
                    step_ids=step_ids,
                ))
                claimed.update(step_ids)

        # Fallback: no phases parsed → one phase holding every step.
        if not phases:
            phases.append(PlanPhase(
                phase_id=0,
                name="All steps",
                goal="",
                strategy="sequential",
                step_ids=sorted(valid_ids),
            ))
            return phases

        # Any steps not claimed by a phase get their own trailing phase.
        unclaimed = sorted(valid_ids - claimed)
        if unclaimed:
            phases.append(PlanPhase(
                phase_id=len(phases),
                name="Remaining",
                goal="",
                strategy="sequential",
                step_ids=unclaimed,
            ))

        return phases
