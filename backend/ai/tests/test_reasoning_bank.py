"""ADR-0054 banks: a tool answer keeps its rationale; a replacement is a revision."""
from __future__ import annotations

from pathlib import Path

import yaml

from ai.engine.cognition.turn.decision import Command, Decision
from ai.engine.cognition.turn.reasoning import revision, scrub


def _cases():
    text = (Path(__file__).resolve().parents[1] / "eval" / "reasoning_bank.yaml").read_text()
    return yaml.safe_load(text)["cases"]


def test_reasoning_bank():
    for case in _cases():
        if case["kind"] == "thinking":
            decision = Decision(
                commands=[Command(op="call_tool", name="read")],
                reason=case["reason"],
            )
            shown = scrub(decision.reason)
            assert bool(shown) is case["expect_rationale"], case["id"]
        else:
            changed = revision(case["shown"], case["replacement"], "rewritten")
            assert (changed is not None) is case["expect_revision"], case["id"]
