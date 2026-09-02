from ai.engine.llm.playbook import _fallback_prompt, RENDERING_CAPABILITIES


def test_no_prohibition_language():
    out = _fallback_prompt({"instance_name": "Test", "current_datetime": "now", "user_context": "u", "page_context": "p"})
    # Strip RENDERING_CAPABILITIES — it contains "never say you cannot" by design.
    body_part = out.replace(RENDERING_CAPABILITIES, "")
    lower = body_part.lower()
    assert "never " not in lower and "do not" not in lower


def test_positive_statements_present():
    out = _fallback_prompt({"instance_name": "Test", "current_datetime": "now", "user_context": "u", "page_context": "p"})
    assert "Lead with the answer" in out
    assert "Ground every claim" in out
    assert "time-aware" in out
    assert "confirmation" in out
    assert "access scope" in out


def test_rendering_capabilities_present():
    out = _fallback_prompt({"instance_name": "Test", "current_datetime": "now", "user_context": "u", "page_context": "p"})
    assert RENDERING_CAPABILITIES in out
