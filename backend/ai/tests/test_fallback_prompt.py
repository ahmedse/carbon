from ai.domain_skills import get_guidance_skills
from ai.engine.knowledge.skill_folder import skill_body
from ai.engine.llm.playbook import _fallback_prompt
from ai.engine.llm.prompts import RENDERING_CAPABILITIES_SUMMARY


def _ctx():
    return {
        "instance_name": "Test",
        "current_datetime": "now",
        "user_context": "u",
        "page_context": "p",
    }


def test_no_prohibition_language():
    out = _fallback_prompt(_ctx())
    # Strip the compact rendering summary — the identity body must stay positive.
    body_part = out.replace(RENDERING_CAPABILITIES_SUMMARY, "")
    lower = body_part.lower()
    assert "never " not in lower and "do not" not in lower


def test_positive_statements_present_in_domain_guidance_skill():
    # The domain-rule bullets were migrated out of _fallback_prompt into the
    # domain-guidance skill folder (progressive disclosure, P4-03).
    body = skill_body("domain-guidance", get_guidance_skills("carbon"))
    assert "Lead with the answer" in body
    assert "Ground every claim" in body
    assert "time-aware" in body
    assert "confirmation" in body
    assert "access scope" in body


def test_rendering_capabilities_present():
    out = _fallback_prompt(_ctx())
    assert RENDERING_CAPABILITIES_SUMMARY in out
