"""
cognition/plan — Skill-aware multi-step planning + ReAct-style execution loop.

PR-20: Introduces a ReAct-style planning loop that decomposes user goals using
skills from the SkillRegistry, gates each step through the S4 critic, requires
confirmation for mutations, and replans on failure (max 2 replans).

Distinct from knowledge_graph/multi_step_planner.py which plans SQL query DAGs.
"""
from ai.engine.cognition.plan.planner import SkillAwarePlanner, Plan, PlanStep
from ai.engine.cognition.plan.loop import ReActLoop, ReActResult, StepResult

__all__ = [
    "SkillAwarePlanner",
    "Plan",
    "PlanStep",
    "ReActLoop",
    "ReActResult",
    "StepResult",
]
