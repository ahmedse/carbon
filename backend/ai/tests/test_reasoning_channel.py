"""ADR-0054 — the reasoning channel is typed state, not a phrase list."""
from __future__ import annotations

from types import SimpleNamespace

from ai.engine.cognition.turn.reasoning import budget_on, revision, scrub, step_narration


def test_scrub_drops_fences_backticks_and_call_tokens():
    raw = "Understood.\n```\ncall_host_api()\n```\nUse `call_abc` only."
    assert "```" not in scrub(raw)
    assert "call_" not in scrub(raw)
    assert scrub(raw).startswith("Understood.")


def test_budget_reads_state_not_the_message():
    quiet = SimpleNamespace(intent={"confidence": 0.9}, decisions=[], open_question={})
    assert budget_on(quiet) is False
    low = SimpleNamespace(intent={"confidence": 0.4}, decisions=[], open_question={})
    assert budget_on(low) is True
    failed = SimpleNamespace(
        intent={"confidence": 0.9},
        decisions=[{"why": "degraded"}],
        open_question={},
    )
    assert budget_on(failed) is True
    correcting = SimpleNamespace(
        intent={"confidence": 0.9},
        decisions=[],
        open_question={"kind": "correct_previous"},
    )
    assert budget_on(correcting) is True
    assert budget_on(None) is False


def test_revision_only_when_shown_text_changes():
    assert revision("Same.", "Same.", "x") is None
    assert revision("", "New.", "x") is None
    changed = revision("Live data summary.", "Gender is mostly blank.", "rewritten")
    assert changed["shown"].startswith("Live")
    assert changed["reason"] == "rewritten."


def test_step_narration_names_unfinished_dependencies():
    assert step_narration("Count the rows.", []) == "Count the rows."
    assert "Waiting on step 2, 4." in step_narration("Write the file.", ["2", "4"])
