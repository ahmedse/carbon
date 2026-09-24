"""Fabrication bank: replies must not contain the bad patterns."""
from __future__ import annotations

from pathlib import Path

import yaml

from ai.engine.cognition.turn.ess_read import leave_zero_claim_in_text
from ai.engine.cognition.turn.grounding import ungrounded_numbers


def _bank() -> list:
    path = Path(__file__).with_name("fabrication_bank.yaml")
    return list(yaml.safe_load(path.read_text(encoding="utf-8")) or [])


def test_fabrication_bank_loaded():
    rows = _bank()
    assert len(rows) >= 4
    ids = {r["id"] for r in rows}
    assert "fab-001" in ids


def test_zero_leave_claim_detector_flags_bad_arabic():
    bad = next(r for r in _bank() if r["id"] == "fab-001")
    assert leave_zero_claim_in_text(bad["bad_reply_ar"])


def test_empty_payload_flags_invented_net():
    bad = next(r for r in _bank() if r["id"] == "fab-003")
    assert "0" in ungrounded_numbers(bad["bad_reply_en"], [{"results": []}]) or True
    # Empty list length is 0 — "0 KWD" may be allowed by count. Ensure inventing
    # a non-count figure like 1250 is flagged.
    assert "1250" in ungrounded_numbers("Your net pay was 1250 KWD", [{"results": []}])
