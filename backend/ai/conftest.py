"""Phrase tables follow the pack bound for the turn.

Engine unit tests call those tables without a chat turn. This workspace's
banks are the Nibras pack, so an unbound lookup would hide that pack's rows.
A test that wants another world calls bind_pack itself; the inner bind wins.
"""
from __future__ import annotations

import pytest

from ai.engine.cognition.phrase_tables import bind_pack


@pytest.fixture(autouse=True)
def _phrase_pack_for_engine_tests():
    with bind_pack("nibras"):
        yield
