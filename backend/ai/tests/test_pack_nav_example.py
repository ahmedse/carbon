"""The intent navigation example uses a listed destination name."""
from __future__ import annotations

from pathlib import Path

import yaml

from ai.engine.cognition.turn.intent import (
    _build_nav_targets,
    _build_system_prompt,
    _nav_example_target,
)

_ROOT = Path(__file__).resolve().parents[3] / "domain_packs"


def _routes(pack_id: str) -> list:
    doc = yaml.safe_load((_ROOT / pack_id / "instance.yaml").read_text(encoding="utf-8"))
    return list((doc or {}).get("navigation_routes") or [])


def test_nibras_example_is_the_first_listed_name():
    targets = _build_nav_targets(_routes("nibras"))
    text = _build_system_prompt([], targets)
    assert '"target":"people_home"' in text
    assert 'For navigation respond: {"action":"navigate","target":"people_home","confidence":0.9}' in text
    assert 'For navigation respond: {"action":"navigate","target":"people","confidence":0.9}' not in text


def test_course_only_list_does_not_invent_people():
    targets = [{"name": "Course", "label": "Course", "aliases": []}]
    text = _build_system_prompt([], targets)
    assert '"target":"Course"' in text
    assert '"target":"people"' not in text


def test_medicine_current_routes_list_nothing():
    targets = _build_nav_targets(_routes("aast-med"))
    assert targets == []
    text = _build_system_prompt([], targets)
    assert "NAVIGATION:" not in text
    assert '"target":"people"' not in text


def test_unsafe_destination_name_is_not_an_example():
    assert _nav_example_target([]) == ""
    assert _nav_example_target([{"name": '../x', "label": "x"}]) == ""
    assert _nav_example_target([{"name": 'a"b', "label": "x"}]) == ""
    assert _nav_example_target([{"name": "Course", "label": "Course"}]) == "Course"
