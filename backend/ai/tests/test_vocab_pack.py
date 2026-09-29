"""Vocabulary resolves from the pack bound for the turn."""
from __future__ import annotations

import yaml
from pathlib import Path

from ai.engine.pack_vocab import LV, V, bind_pack

_VOCAB = (
    Path(__file__).resolve().parents[3]
    / "domain_packs"
    / "nibras"
    / "vocab.yaml"
)
_ROWS = {
    key: value
    for key, value in yaml.safe_load(_VOCAB.read_text(encoding="utf-8")).items()
    if isinstance(value, str)
}
_SAMPLE = "t_leave"


def test_nibras_bind_returns_that_packs_strings():
    with bind_pack("nibras"):
        for key, value in _ROWS.items():
            assert V(key) == value


def test_other_pack_does_not_receive_nibras_strings():
    with bind_pack("aast-med"):
        assert V(_SAMPLE) == ""
        assert all(V(key) == "" for key in _ROWS)


def test_escape_does_not_read_the_nibras_file():
    with bind_pack("../nibras"):
        assert V(_SAMPLE) == ""
    with bind_pack("nibras/../nibras"):
        assert V(_SAMPLE) == ""


def test_module_binding_follows_the_active_pack():
    from ai.engine.cognition.plan.process_dial import PROCESS_LEAVE

    with bind_pack("nibras"):
        nibras = str(PROCESS_LEAVE)
    with bind_pack("aast-med"):
        other = str(PROCESS_LEAVE)
    assert nibras == _ROWS["t_leave_request_lifecycle"]
    assert other == ""
    assert nibras != other
