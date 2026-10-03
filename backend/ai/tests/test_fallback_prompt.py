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
    # ``RENDERING_CAPABILITIES_SUMMARY`` is a lazy pack string (``_LiveStr``);
    # coerce it to a plain ``str`` at this read boundary, as ``_fallback_prompt``
    # itself does when it renders the prompt.
    body_part = out.replace(str(RENDERING_CAPABILITIES_SUMMARY), "")
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
    assert str(RENDERING_CAPABILITIES_SUMMARY) in out


def test_rendering_summary_reads_as_plain_str():
    """The lazy pack summary resolves to a plain ``str`` at the read boundary.

    ``RENDERING_CAPABILITIES_SUMMARY`` stays a ``_LiveStr`` bound to the turn's
    pack; reading it with ``str`` (JSON/prompt boundary) yields a real string,
    and it is non-empty under the bound pack.
    """
    from ai.engine.pack_vocab import _LiveText

    assert isinstance(RENDERING_CAPABILITIES_SUMMARY, _LiveText)
    resolved = str(RENDERING_CAPABILITIES_SUMMARY)
    assert isinstance(resolved, str)
    assert resolved
