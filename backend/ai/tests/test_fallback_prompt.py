from pathlib import Path

from ai.engine.knowledge.skill_folder import load_skill_folders, skill_body
from ai.engine.llm.playbook import _fallback_prompt
from ai.engine.llm.prompts import RENDERING_CAPABILITIES_SUMMARY

_CARBON_SKILLS = Path(__file__).resolve().parents[3] / "domain_packs" / "carbon" / "skills"


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


def test_positive_statements_present_in_domain_guidance_pack():
    # DEFERRED(F1a): packs are not injected live; content retained for possible
    # instance.yaml fold. Locks pack body text only.
    skills = load_skill_folders(_CARBON_SKILLS)
    body = skill_body("domain-guidance", skills)
    assert "Lead with the answer" in body
    assert "Ground every claim" in body
    assert "time-aware" in body
    assert "confirmation" in body
    assert "access scope" in body


def test_rendering_capabilities_present():
    out = _fallback_prompt(_ctx())
    assert RENDERING_CAPABILITIES_SUMMARY in out
