"""The intent answer example uses a listed read name."""
from __future__ import annotations

from pathlib import Path

import yaml

from ai.engine.cognition.turn.intent import (
    _answer_example_line,
    _build_label_set,
    _build_nav_targets,
    _build_system_prompt,
    _safe_example_name,
)

_ROOT = Path(__file__).resolve().parents[3] / "domain_packs"


def _catalog(pack_id: str) -> list:
    doc = yaml.safe_load((_ROOT / pack_id / "instance.yaml").read_text(encoding="utf-8"))
    return list((doc or {}).get("api_catalog") or [])


def _routes(pack_id: str) -> list:
    doc = yaml.safe_load((_ROOT / pack_id / "instance.yaml").read_text(encoding="utf-8"))
    return list((doc or {}).get("navigation_routes") or [])


def test_nibras_answer_example_is_the_first_read():
    labels = _build_label_set(_catalog("nibras"))
    text = _build_system_prompt(labels, _build_nav_targets(_routes("nibras")))
    assert '"endpoint":"analyze_employees"' in text
    assert "list_gwp_gases" not in text
    assert '"target":"people_home"' in text


def test_medicine_answer_example_is_get_course():
    labels = _build_label_set(_catalog("aast-med"))
    text = _build_system_prompt(labels, [])
    assert '"endpoint":"get_course"' in text
    assert "list_gwp_gases" not in text
    assert "NAVIGATION:" not in text


def test_empty_label_set_writes_null():
    text = _build_system_prompt([], [])
    assert '"endpoint":null' in text
    assert "list_gwp_gases" not in text
    assert "Respond with ONLY valid JSON matching exactly this shape:" in text


def test_unsafe_label_name_is_skipped():
    assert _safe_example_name([{"name": 'a"b'}, {"name": "get_course"}]) == "get_course"
    assert _safe_example_name([{"name": "a/b"}, {"name": "has space"}]) == ""
    line = _answer_example_line([{"name": "../x"}])
    assert '"endpoint":null' in line
    assert "list_gwp_gases" not in line
