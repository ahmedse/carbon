"""Reproduce: decompose the user's exact brief and print the phase-aware plan.

Run: cd backend && /home/ahmed/aast/carbon/.venv/bin/python ../scripts/repro_phase_plan.py
"""
import asyncio
import json
import os
import sys

# Script lives in scripts/; backend package lives in backend/.
_BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, _BACKEND)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()

from ai.engine.core.config import get_settings  # noqa: E402
from ai.engine.core.database import get_session_factory  # noqa: E402
from ai.engine.llm.provider import get_llm_client  # noqa: E402
from ai.engine.cognition.plan.planner import SkillAwarePlanner  # noqa: E402
from ai.engine.skills.registry import SkillRegistry  # noqa: E402

INSTANCE_ID = "carbon"
BRIEF = (
    "plan and execute a task to do research on internet for top carbon footprint "
    "systems and protocols and standards, and compare with our carbon footprint. "
    "create a word file and excel file with results and give me links to download them. "
    "make a multi agent workflow"
)


async def main():
    settings = get_settings()
    factory = get_session_factory(INSTANCE_ID)
    async with factory() as db:
        registry = SkillRegistry(db)
        planner = SkillAwarePlanner(llm_client=get_llm_client(), model=settings.LLM_MODEL)
        plan = await planner.decompose(
            utterance=BRIEF,
            skill_registry=registry,
            instance_id=INSTANCE_ID,
            user_id="1",
        )
        print("=== PLAN ===")
        print("pattern:", plan.pattern)
        print("source:", plan.source)
        print("skill_name:", plan.skill_name)
        print("needs_confirmation:", plan.needs_confirmation)
        print("synthesis_instruction:", (plan.synthesis_instruction or "")[:200])
        print("phases:", json.dumps([
            {
                "phase_id": p.phase_id,
                "name": p.name,
                "goal": p.goal,
                "strategy": p.strategy,
                "step_ids": p.step_ids,
            }
            for p in plan.phases
        ], ensure_ascii=False, indent=2))
        print("steps:", json.dumps([
            {
                "step_id": s.step_id,
                "intent": s.intent,
                "tool_name": s.tool_name,
                "agent_role": s.agent_role,
                "depends_on": s.depends_on,
                "is_mutation": s.is_mutation,
            }
            for s in plan.steps
        ], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
